#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chrome 书签自动整理与健康检查工具 (CLI 启动入口)
- 支持并发死链检测（HEAD + GET 降级）
- 支持终端交互式审计失效链接
- 支持 OpenAI 兼容接口的 LLM 语义聚类与目录重构
- 严格遵循 Chrome Bookmarks 格式协议
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Tuple

from bookmark_cleaner.cli import (
    BookmarkWorkflow,
    main as cli_main,
    prompt_dead_link_action,
)
from bookmark_cleaner.config import (
    API_KEY,
    BASE_URL,
    BATCH_SIZE,
    MAX_CONCURRENT_REQUESTS,
    MODEL_NAME,
    PRESET_CATEGORIES,
    REQUEST_TIMEOUT_SECONDS,
    get_chrome_timestamp,
    get_default_bookmark_path,
)
from bookmark_cleaner.parser import (
    flatten_bookmarks as extract_flatten_bookmarks,
    normalize_and_deduplicate,
)
from bookmark_cleaner.prober import run_health_check


class BookmarkManager(BookmarkWorkflow):
    """
    书签管理控制类（对外兼容接口）
    继承自 BookmarkWorkflow，保持统一核心实现的同时提供原设计文档中声明的兼容方法。
    """

    def __init__(
        self,
        bookmark_path: Path,
        api_key: str = API_KEY,
        base_url: str = BASE_URL,
        model_name: str = MODEL_NAME
    ):
        super().__init__(
            bookmark_path=bookmark_path,
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            batch_size=BATCH_SIZE,
            max_concurrency=MAX_CONCURRENT_REQUESTS,
            timeout_seconds=REQUEST_TIMEOUT_SECONDS,
            preset_categories=PRESET_CATEGORIES
        )

    @staticmethod
    def get_chrome_timestamp() -> str:
        """生成符合 WebKit 纪元标准的微秒时间戳"""
        return get_chrome_timestamp()

    def flatten_bookmarks(self, node: Dict[str, Any], result: List[Dict[str, Any]]) -> None:
        """递归提取全部 URL 类型的叶子节点并同步最大 ID"""
        items = extract_flatten_bookmarks(node, self.id_manager)
        result.extend(items)

    async def run_health_check(
        self, bookmarks: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """高并发异步探活调度器"""
        return await run_health_check(
            bookmarks,
            max_concurrency=self.max_concurrency,
            timeout_seconds=self.timeout_seconds,
            ssl_verify=self.ssl_verify
        )

    def prompt_user_for_dead_links(self, dead_bookmarks: List[Dict[str, Any]]) -> str:
        """终端高亮显示失效列表并等待处置指令"""
        return prompt_dead_link_action(dead_bookmarks)

    def classify_batch(self, batch: List[Dict[str, Any]]) -> Dict[str, str]:
        """批量调用 LLM 语义聚类"""
        return self.classifier.classify_single_batch(batch)


if __name__ == "__main__":
    cli_main()
