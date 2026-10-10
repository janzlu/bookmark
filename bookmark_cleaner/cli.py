#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交互与编排模块：协调六阶段流水线（备份、提取去重、探活、交互确认、聚类、树重构与回写）。
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .builder import assemble_tree, create_archive_folder
from .classifier import BookmarkClassifier
from .config import (
    API_KEY,
    BASE_URL,
    BATCH_SIZE,
    DEFAULT_SSL_VERIFY,
    MAX_CONCURRENT_REQUESTS,
    MODEL_NAME,
    PRESET_CATEGORIES,
    REQUEST_TIMEOUT_SECONDS,
    get_chrome_timestamp,
    get_default_bookmark_path,
)
from .parser import IdManager, flatten_bookmarks, normalize_and_deduplicate
from .prober import run_health_check
from .storage import backup_database, load_bookmarks, save_bookmarks_atomic


def prompt_dead_link_action(
    dead_bookmarks: List[Dict[str, Any]],
    auto_choice: str | None = None
) -> str:
    """
    终端高亮展示失效链接明细，并交互式获取用户处置决策。
    返回值: 'archive' | 'delete' | 'keep'
    """
    if not dead_bookmarks:
        print("\n[✓] 链接探活全部通过，未检测到死链。\n")
        return "keep"

    if auto_choice in ("archive", "delete", "keep"):
        print(f"\n[*] 已通过参数自动指定处置策略: {auto_choice}")
        return auto_choice

    print("\n" + "=" * 80)
    print(f"⚠️  共识别出 {len(dead_bookmarks)} 个疑似无法访问的书签：")
    print("=" * 80)

    for idx, bm in enumerate(dead_bookmarks, 1):
        reason = bm.get("_dead_reason", "未知")
        title = bm.get("name") or "(无标题)"
        url = bm.get("url", "")
        print(f"[{idx:02d}] 异常状态: \033[31m{reason:<18}\033[0m | 标题: {title}")
        print(f"     链接地址: {url}")

    print("=" * 80)
    print("请选择对上述失效书签的处置方式：")
    print("  [1] 自动归档（默认：分类存入「⚠️ 失效书签归档」独立文件夹）")
    print("  [2] 直接剔除（从整理结果中彻底移除）")
    print("  [3] 忽略异常（保留并正常随同分类）")

    try:
        choice = input("请输入选项编号 [1/2/3] (直接回车默认 1): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n[*] 检测到中断，默认选择自动归档。")
        return "archive"

    if choice == "2":
        return "delete"
    elif choice == "3":
        return "keep"
    return "archive"


class BookmarkWorkflow:
    """核心流水线执行器"""

    def __init__(
        self,
        bookmark_path: Path,
        api_key: str = API_KEY,
        base_url: str = BASE_URL,
        model_name: str = MODEL_NAME,
        batch_size: int = BATCH_SIZE,
        max_concurrency: int = MAX_CONCURRENT_REQUESTS,
        timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
        ssl_verify: bool = DEFAULT_SSL_VERIFY,
        preset_categories: List[str] | None = None
    ):
        self.bookmark_path = bookmark_path
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.batch_size = batch_size
        self.max_concurrency = max_concurrency
        self.timeout_seconds = timeout_seconds
        self.ssl_verify = ssl_verify

        self.id_manager = IdManager()
        self.classifier = BookmarkClassifier(
            api_key=self.api_key,
            base_url=self.base_url,
            model_name=self.model_name,
            preset_categories=preset_categories if preset_categories is not None else PRESET_CATEGORIES
        )
        self.data: Dict[str, Any] = {}

    @property
    def max_id(self) -> int:
        return self.id_manager.max_id

    @max_id.setter
    def max_id(self, val: int):
        self.id_manager.max_id = val

    def allocate_id(self) -> str:
        return self.id_manager.allocate()

    def backup_database(self) -> Path:
        """带友好异常处理的文件备份"""
        try:
            backup_path = backup_database(self.bookmark_path)
            print(f"[+] 原始书签已备份至: {backup_path}")
            return backup_path
        except FileNotFoundError:
            print(f"[!] 错误: 未找到目标 Chrome 书签文件: {self.bookmark_path}")
            sys.exit(1)
        except PermissionError:
            print(f"[!] 错误: 无权读取或备份书签文件: {self.bookmark_path}")
            sys.exit(1)

    def _stage_load_and_dedup(self) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """阶段 2 & 3: 读取书签、同步 ID 并规范化去重"""
        self.data = load_bookmarks(self.bookmark_path)
        bookmark_bar = self.data.get("roots", {}).get("bookmark_bar", {})
        flat_list = flatten_bookmarks(bookmark_bar, self.id_manager)
        print(f"[*] 扫描到书签栏原生书签数量: {len(flat_list)} 个 (最大 ID: {self.id_manager.max_id})")

        deduped = normalize_and_deduplicate(flat_list)
        print(f"[*] URL 规范化过滤去重完成，待处理项: {len(deduped)} 个")
        return self.data, deduped

    async def _stage_probe(
        self,
        deduped: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """阶段 4: 异步并发探活"""
        print(f"[*] 正在并发检测链接可用性 (并发限制: {self.max_concurrency})...")
        alive_list, dead_list = await run_health_check(
            deduped,
            max_concurrency=self.max_concurrency,
            timeout_seconds=self.timeout_seconds,
            ssl_verify=self.ssl_verify
        )
        print(f"[+] 存活链接: {len(alive_list)} | [x] 异常链接: {len(dead_list)}")
        return alive_list, dead_list

    def _stage_classify(
        self,
        work_list: List[Dict[str, Any]]
    ) -> List[Tuple[Dict[str, Any], str]]:
        """阶段 5: LLM 语义聚类"""
        print(f"\n[*] 开始大模型批量语义分类 (模型: {self.model_name})...")

        def progress_log(start_idx: int, end_idx: int) -> None:
            print(f"    - 处理进度: {start_idx} ~ {end_idx} / {len(work_list)}")

        return self.classifier.classify_all(
            work_list,
            batch_size=self.batch_size,
            progress_callback=progress_log
        )

    def _stage_reconstruct_and_save(
        self,
        classified_pairs: List[Tuple[Dict[str, Any], str]],
        dead_list: List[Dict[str, Any]],
        action: str
    ) -> None:
        """阶段 6: 树重构与安全持久化"""
        print("[*] 正在重构书签栏目录树...")
        new_children = assemble_tree(classified_pairs, self.id_manager)

        if action == "archive" and dead_list:
            archive_folder = create_archive_folder(dead_list, self.id_manager)
            new_children.append(archive_folder)
            print(f"[+] 已创建「⚠️ 失效书签归档」文件夹，收录 {len(dead_list)} 个节点")

        # 确保根节点完备性
        roots = self.data.setdefault("roots", {})
        bookmark_bar = roots.setdefault("bookmark_bar", {})
        bookmark_bar["children"] = new_children
        bookmark_bar["date_modified"] = get_chrome_timestamp()

        save_bookmarks_atomic(self.bookmark_path, self.data)

    async def execute(
        self,
        dead_action_override: str | None = None,
        skip_confirm: bool = False
    ) -> None:
        """运行完整的书签自动化整理与健康检查流水线"""
        print("=" * 60)
        print("Chrome 书签自动整理与健康检查工具")
        print("=" * 60)
        print(f"[*] 目标书签路径: {self.bookmark_path}")

        if not skip_confirm:
            print("\n【重要提示】请确认 Chrome 浏览器已完全退出（无后台常驻进程）后再继续！")
            try:
                input("确认已退出后，按回车键 [Enter] 开始执行...")
            except (EOFError, KeyboardInterrupt):
                print("\n[!] 用户取消操作。")
                return

        # 1. 备份数据
        self.backup_database()

        # 2 & 3. 读取书签并去重
        _, deduped = self._stage_load_and_dedup()

        # 4. 探活
        alive_list, dead_list = await self._stage_probe(deduped)

        # 5. 交互决策
        action = prompt_dead_link_action(dead_list, auto_choice=dead_action_override)
        work_list = list(alive_list) + (list(dead_list) if action == "keep" else [])

        # 6. LLM 语义聚类
        classified_pairs = self._stage_classify(work_list)

        # 7 & 8. 重构与保存
        self._stage_reconstruct_and_save(classified_pairs, dead_list, action)

        print("\n" + "=" * 60)
        print("[✓] 书签全流程整理完成！重新打开 Chrome 即可生效。")
        print("=" * 60)


def build_arg_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="Chrome 书签自动整理与健康检查工具"
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=get_default_bookmark_path(),
        help="Chrome 书签文件路径（默认自动匹配当前操作系统）"
    )
    parser.add_argument(
        "--action",
        choices=["archive", "delete", "keep"],
        default=None,
        help="对失效书签的预设处置方式 (archive/delete/keep)"
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="跳过执行前的退出 Chrome 确认交互"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=f"LLM 批处理切片大小 (默认: {BATCH_SIZE})"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=MAX_CONCURRENT_REQUESTS,
        help=f"最大异步网络并发数 (默认: {MAX_CONCURRENT_REQUESTS})"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=MODEL_NAME,
        help=f"大模型名称 (默认: {MODEL_NAME})"
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=BASE_URL,
        help=f"OpenAI 兼容接口 Base URL (默认: {BASE_URL})"
    )
    parser.add_argument(
        "--ssl-verify",
        action="store_true",
        default=DEFAULT_SSL_VERIFY,
        help="启用严格 SSL 证书验证 (默认关闭以避免误判内网自建服务)"
    )
    return parser


def main() -> None:
    """CLI 入口函数"""
    parser = build_arg_parser()
    args = parser.parse_args()

    workflow = BookmarkWorkflow(
        bookmark_path=args.path,
        api_key=API_KEY,
        base_url=args.base_url,
        model_name=args.model,
        batch_size=args.batch_size,
        max_concurrency=args.concurrency,
        ssl_verify=args.ssl_verify
    )

    asyncio.run(
        workflow.execute(
            dead_action_override=args.action,
            skip_confirm=args.yes
        )
    )
