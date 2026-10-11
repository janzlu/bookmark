#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web 服务模块：基于 aiohttp.web 提供 RESTful API 与静态页面服务，驱动前端 UI 管理界面。
"""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List
from aiohttp import web

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
from .server_helpers import get_backup_list, is_chrome_running, send_sse_error, send_sse_event
from .server_stream import stream_classify, stream_probe
from .storage import (
    backup_database,
    load_bookmarks,
    restore_backup,
    save_bookmarks_atomic,
    save_deleted_audit_log,
)


class BookmarkServer:
    """Web 管理服务端"""

    def __init__(self, bookmark_path: Path | None = None):
        self.bookmark_path = bookmark_path or get_default_bookmark_path()
        self.config: Dict[str, Any] = {
            "api_key": API_KEY,
            "base_url": BASE_URL,
            "model_name": MODEL_NAME,
            "batch_size": BATCH_SIZE,
            "max_concurrency": MAX_CONCURRENT_REQUESTS,
            "timeout_seconds": REQUEST_TIMEOUT_SECONDS,
            "ssl_verify": DEFAULT_SSL_VERIFY,
            "preset_categories": PRESET_CATEGORIES
        }
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self):
        static_dir = Path(__file__).resolve().parent.parent / "static"
        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/api/status", self.handle_status)
        self.app.router.add_get("/api/bookmarks/summary", self.handle_summary)
        self.app.router.add_post("/api/prober/start", self.handle_probe)
        self.app.router.add_post("/api/prober/stream", self.handle_probe_stream)
        self.app.router.add_post("/api/classifier/start", self.handle_classify)
        self.app.router.add_post("/api/classifier/stream", self.handle_classify_stream)
        self.app.router.add_post("/api/pipeline/apply", self.handle_apply)
        self.app.router.add_post("/api/backups/restore", self.handle_restore)
        self.app.router.add_post("/api/config/update", self.handle_config_update)
        self.app.router.add_static("/static/", path=str(static_dir), name="static")

    async def handle_index(self, request: web.Request) -> web.Response:
        """主页面重定向或返回 index.html"""
        static_index = Path(__file__).resolve().parent.parent / "static" / "index.html"
        if static_index.exists():
            return web.FileResponse(static_index)
        return web.Response(text="UI static files not found", status=404)

    async def handle_status(self, request: web.Request) -> web.Response:
        """获取系统状态、环境信息与配置"""
        try:
            file_size = self.bookmark_path.stat().st_size
            file_exists = True
        except (FileNotFoundError, OSError):
            file_exists = False
            file_size = 0

        data = {
            "chrome_running": is_chrome_running(),
            "bookmark_path": str(self.bookmark_path),
            "file_exists": file_exists,
            "file_size": file_size,
            "backups": get_backup_list(self.bookmark_path),
            "config": {
                **self.config,
                "has_api_key": bool(self.config["api_key"])
            }
        }
        return web.json_response(data)

    async def handle_summary(self, request: web.Request) -> web.Response:
        """读取并分析书签库概览信息与去重统计"""
        if not self.bookmark_path.exists():
            return web.json_response({"error": "书签文件不存在"}, status=404)

        try:
            raw_data = load_bookmarks(self.bookmark_path)
            bookmark_bar = raw_data.get("roots", {}).get("bookmark_bar", {})
            id_mgr = IdManager()
            flat_list = flatten_bookmarks(bookmark_bar, id_mgr)
            deduped = normalize_and_deduplicate(flat_list)

            return web.json_response({
                "total_count": len(flat_list),
                "unique_count": len(deduped),
                "duplicate_count": len(flat_list) - len(deduped),
                "max_id": id_mgr.max_id,
                "items": deduped[:50]  # 返回前 50 条样本用于展示
            })
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_probe(self, request: web.Request) -> web.Response:
        """执行异步并发网络探活"""
        if not self.bookmark_path.exists():
            return web.json_response({"error": "书签文件不存在"}, status=404)

        try:
            raw_data = load_bookmarks(self.bookmark_path)
            bookmark_bar = raw_data.get("roots", {}).get("bookmark_bar", {})
            flat_list = flatten_bookmarks(bookmark_bar)
            deduped = normalize_and_deduplicate(flat_list)

            # 支持自定义测试范围（默认全量）
            body = await request.json() if request.can_read_body else {}
            sample_limit = body.get("limit")
            target_items = deduped[:sample_limit] if sample_limit else deduped

            concurrency = int(body.get("concurrency", self.config["max_concurrency"]))
            timeout = float(body.get("timeout", self.config["timeout_seconds"]))
            ssl_verify = bool(body.get("ssl_verify", self.config["ssl_verify"]))

            alive, dead = await run_health_check(
                target_items,
                max_concurrency=concurrency,
                timeout_seconds=timeout,
                ssl_verify=ssl_verify
            )

            return web.json_response({
                "total_tested": len(target_items),
                "alive_count": len(alive),
                "dead_count": len(dead),
                "alive": alive,
                "dead": dead
            })
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_probe_stream(self, request: web.Request) -> web.StreamResponse:
        """流式异步探活：基于 SSE 实时输出单项检测结果与百分比进度"""
        if not self.bookmark_path.exists():
            return web.json_response({"error": "书签文件不存在"}, status=404)
        return await stream_probe(request, self.config, self.bookmark_path)

    async def handle_classify(self, request: web.Request) -> web.Response:
        """执行大语言模型批量语义聚类 (单次返回)"""
        try:
            body = await request.json()
            bookmarks = body.get("bookmarks", [])
            if not bookmarks:
                return web.json_response({"classified": []})

            classifier = BookmarkClassifier(
                api_key=self.config["api_key"],
                base_url=self.config["base_url"],
                model_name=self.config["model_name"],
                preset_categories=self.config["preset_categories"]
            )

            batch_size = int(body.get("batch_size", self.config["batch_size"]))
            classified_pairs = classifier.classify_all(bookmarks, batch_size=batch_size)

            result = [
                {"bookmark": bm, "category": cat}
                for bm, cat in classified_pairs
            ]
            return web.json_response({"classified": result})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_classify_stream(self, request: web.Request) -> web.StreamResponse:
        """流式大模型语义聚类：基于 SSE 实时输出批次完成与分类详情"""
        return await stream_classify(request, self.config)

    async def handle_apply(self, request: web.Request) -> web.Response:
        """将整理结果原子化覆写持久化至 Chrome 书签文件"""
        if is_chrome_running():
            return web.json_response({
                "error": "Google Chrome 仍在运行中！请先彻底关闭 Chrome 浏览器再提交保存。"
            }, status=409)

        try:
            body = await request.json()
            classified_data = body.get("classified", [])
            manual_verified = bool(body.get("manual_verified", False))

            # 兼容精细化批量列表与传统统一模式
            deleted_data = body.get("deleted_bookmarks")
            archived_data = body.get("archived_bookmarks")
            if deleted_data is None and archived_data is None:
                dead_data = body.get("dead", [])
                dead_action = body.get("dead_action", "archive")
                deleted_data = dead_data if dead_action == "delete" else []
                archived_data = dead_data if dead_action == "archive" else []
            else:
                deleted_data = deleted_data or []
                archived_data = archived_data or []

            # 核心安全门禁：物理删除必须经过明确的人工核验确认
            if deleted_data and not manual_verified:
                return web.json_response({
                    "error": "安全拦截：物理删除失效书签必须经过人工逐项核验！请在核验弹窗中确认核验无误后再提交。"
                }, status=400)

            # 1. 强制生成时间戳快照备份
            bak_path = backup_database(self.bookmark_path)

            # 若执行物理删除，额外记录不可逆删除专有审计日志以备溯源恢复
            deleted_audit_file = save_deleted_audit_log(self.bookmark_path, deleted_data)

            # 2. 读取当前原始数据
            raw_data = load_bookmarks(self.bookmark_path)
            id_mgr = IdManager()
            flatten_bookmarks(raw_data.get("roots", {}).get("bookmark_bar", {}), id_mgr)

            # 3. 装配目录树
            pairs = [(item["bookmark"], item["category"]) for item in classified_data]
            new_children = assemble_tree(pairs, id_mgr)

            # 4. 失效书签归档处理 (仅对明确需要归档的书签挂载)
            if archived_data:
                archive_folder = create_archive_folder(archived_data, id_mgr)
                new_children.append(archive_folder)

            # 5. 回写并原子保存
            roots = raw_data.setdefault("roots", {})
            bar = roots.setdefault("bookmark_bar", {})
            bar["children"] = new_children
            bar["date_modified"] = get_chrome_timestamp()

            save_bookmarks_atomic(self.bookmark_path, raw_data)

            return web.json_response({
                "success": True,
                "backup_path": str(bak_path),
                "deleted_audit_path": deleted_audit_file,
                "deleted_count": len(deleted_data),
                "archived_count": len(archived_data),
                "folder_count": len(new_children)
            })
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_restore(self, request: web.Request) -> web.Response:
        """从指定历史备份恢复书签"""
        if is_chrome_running():
            return web.json_response({
                "error": "Google Chrome 仍在运行中！请先彻底关闭 Chrome 浏览器再恢复备份。"
            }, status=409)

        try:
            body = await request.json()
            filename = body.get("filename")
            if not filename or not isinstance(filename, str):
                return web.json_response({"error": "缺少 filename 参数"}, status=400)

            # 严格防止路径穿越：限定必须为纯文件名且具有 Bookmarks.bak_ 前缀
            if "/" in filename or "\\" in filename or ".." in filename or not filename.startswith("Bookmarks.bak_"):
                return web.json_response({"error": "非法的备份文件名格式"}, status=400)

            bak_path = (self.bookmark_path.parent / filename).resolve()
            if bak_path.parent != self.bookmark_path.parent.resolve() or not bak_path.exists():
                return web.json_response({"error": "备份文件不存在"}, status=404)

            restore_backup(bak_path, self.bookmark_path)
            return web.json_response({"success": True, "restored_from": filename})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_config_update(self, request: web.Request) -> web.Response:
        """更新运行时配置"""
        try:
            body = await request.json()
            for k in ("api_key", "base_url", "model_name", "batch_size", "max_concurrency", "timeout_seconds", "ssl_verify"):
                if k in body:
                    self.config[k] = body[k]
            return web.json_response({"success": True, "config": self.config})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)


def create_app(bookmark_path: Path | None = None) -> web.Application:
    """创建 aiohttp web 应用实例"""
    server = BookmarkServer(bookmark_path)
    return server.app
