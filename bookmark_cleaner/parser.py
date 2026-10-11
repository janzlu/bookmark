#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解析模块：书签树遍历、扁平化提取、ID 同步与 URL 规范化去重。
"""

from typing import Any, Dict, List, Set
from urllib.parse import urlparse


class IdManager:
    """全局节点唯一递增 ID 管理器"""

    def __init__(self, initial_max_id: int = 1):
        self.max_id = initial_max_id

    def sync(self, node: Dict[str, Any]) -> None:
        """递归遍历整棵节点树，同步最大整数 ID"""
        try:
            node_id = int(node.get("id", 0))
            if node_id > self.max_id:
                self.max_id = node_id
        except (ValueError, TypeError):
            pass

        for child in node.get("children", []):
            self.sync(child)

    def allocate(self) -> str:
        """分配全新的全局唯一 ID"""
        self.max_id += 1
        return str(self.max_id)


def flatten_bookmarks(
    node: Dict[str, Any],
    id_manager: IdManager | None = None
) -> List[Dict[str, Any]]:
    """
    递归遍历书签节点树，提取所有 url 类型的叶子节点。
    同时如果传入 id_manager，同步整树的最大 ID。
    """
    result: List[Dict[str, Any]] = []

    def _traverse(current: Dict[str, Any]) -> None:
        if id_manager is not None:
            id_manager.sync(current)

        node_type = current.get("type")
        if node_type == "url":
            result.append(current)
        elif node_type == "folder":
            for child in current.get("children", []):
                _traverse(child)

    _traverse(node)
    return result


def normalize_url(url: str) -> str:
    """
    规范化 URL：去除结尾冗余斜杠与页面内部锚点片段(#fragment)，同时完整保留查询参数(?query)。
    """
    if not url:
        return ""
    p = urlparse(url)
    clean_path = p.path.rstrip("/")
    query_part = f"?{p.query}" if p.query else ""
    clean = f"{p.scheme}://{p.netloc}{clean_path}{query_part}"
    return clean


def normalize_and_deduplicate(bookmarks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    过滤非 http(s) 链接，并基于规范化 URL 进行重复项去重（保留首个）。
    """
    deduped: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    for bm in bookmarks:
        url = bm.get("url", "")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            continue

        clean_url = normalize_url(url)
        if not clean_url:
            continue

        if clean_url not in seen:
            seen.add(clean_url)
            deduped.append(bm)

    return deduped
