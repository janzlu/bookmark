#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语义分类模块：基于 OpenAI 兼容客户端调用大模型进行批量书签聚类。
"""

import json
import time
from typing import Any, Callable, Dict, List, Tuple
from openai import OpenAI
from .config import PRESET_CATEGORIES


class BookmarkClassifier:
    """批量语义聚类分类器"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        preset_categories: List[str] | None = None
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.preset_categories = (
            preset_categories if preset_categories is not None else PRESET_CATEGORIES
        )
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self.api_key or "no-key",
                base_url=self.base_url
            )
        return self._client

    def _build_system_prompt(self) -> str:
        categories_json = json.dumps(self.preset_categories, ensure_ascii=False, indent=2)
        return (
            "你是一个专业的数据归类专家。请根据提供的书签标题与URL，将其归类至合理的目录路径。\n"
            f"可选参考分类层级：\n{categories_json}\n"
            "规则要求：\n"
            "1. 格式统一为 '一级目录/二级目录' 或 '一级目录'，如无法明确分类可使用 '其他/待整理'。\n"
            "2. 输出严格为纯 JSON 对象，格式为 { \"<id>\": \"分类路径\" }。\n"
            "3. 严禁输出任何额外文本、解释说明或 Markdown 代码块包裹。"
        )

    def classify_single_batch(
        self,
        batch: List[Dict[str, Any]],
        max_retries: int = 2
    ) -> Dict[str, str]:
        """
        对单批书签调用大语言模型进行分类，带重试与降级保护。
        """
        if not self.api_key:
            print("[!] 未配置 API KEY，跳过语义聚类，默认归入 '其他/待整理'")
            return {str(bm["id"]): "其他/待整理" for bm in batch}

        payload = [
            {"id": str(bm["id"]), "title": bm.get("name", ""), "url": bm.get("url", "")}
            for bm in batch
        ]

        system_prompt = self._build_system_prompt()
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"}
                )

                content = response.choices[0].message.content or "{}"
                data = json.loads(content)

                # 兼容模型外层包裹情况，例如 {"bookmarks": {...}} 或 {"categories": {...}}
                if "bookmarks" in data and isinstance(data["bookmarks"], dict):
                    data = data["bookmarks"]
                elif "categories" in data and isinstance(data["categories"], dict):
                    data = data["categories"]

                mapping: Dict[str, str] = {}
                for bm in batch:
                    str_id = str(bm["id"])
                    cat = data.get(str_id, "其他/待整理")
                    mapping[str_id] = str(cat).strip().replace("\\", "/")

                return mapping
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue

        print(f"[!] 本批次大模型分类失败: {last_error}，已自动降级归入 '其他/待整理'")
        return {str(bm["id"]): "其他/待整理" for bm in batch}

    def classify_all(
        self,
        bookmarks: List[Dict[str, Any]],
        batch_size: int = 25,
        progress_callback: Callable[[int, int], None] | None = None
    ) -> List[Tuple[Dict[str, Any], str]]:
        """
        批量分批分类所有书签，返回 [(书签节点, 分类路径), ...]
        """
        results: List[Tuple[Dict[str, Any], str]] = []
        total = len(bookmarks)

        for i in range(0, total, batch_size):
            batch = bookmarks[i:i + batch_size]
            batch_mapping = self.classify_single_batch(batch)
            for bm in batch:
                cat = batch_mapping.get(str(bm["id"]), "其他/待整理")
                results.append((bm, cat))

            if progress_callback:
                progress_callback(i + 1, min(i + batch_size, total))

        return results
