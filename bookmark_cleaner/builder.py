#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
目录树构建模块：根据分类路径重构 Chrome 目录树结构，分配唯一 ID 与时间戳。
"""

from typing import Any, Dict, List, Tuple
from .config import get_chrome_timestamp
from .parser import IdManager


def assemble_tree(
    classified_list: List[Tuple[Dict[str, Any], str]],
    id_manager: IdManager
) -> List[Dict[str, Any]]:
    """
    依据 (书签, 路径字符串) 列表，重构出符合 Chrome Bookmarks 规范的多层目录树。
    """
    folder_cache: Dict[str, Dict[str, Any]] = {}
    root_nodes: List[Dict[str, Any]] = []

    def get_or_create(path_parts: List[str]) -> Dict[str, Any]:
        cur_path = ""
        parent_children = root_nodes

        for part in path_parts:
            part = part.strip()
            if not part:
                continue

            cur_path = f"{cur_path}/{part}" if cur_path else part
            if cur_path not in folder_cache:
                folder_node: Dict[str, Any] = {
                    "date_added": get_chrome_timestamp(),
                    "date_modified": "0",
                    "id": id_manager.allocate(),
                    "name": part,
                    "type": "folder",
                    "children": []
                }
                folder_cache[cur_path] = folder_node
                parent_children.append(folder_node)

            parent_children = folder_cache[cur_path]["children"]

        return folder_cache[cur_path]

    for bm, cat_path in classified_list:
        bm.pop("_dead_reason", None)
        parts = [p.strip() for p in cat_path.replace("\\", "/").split("/") if p.strip()]
        if not parts:
            parts = ["其他", "待整理"]

        target_folder = get_or_create(parts)
        target_folder["children"].append(bm)

    return root_nodes


def create_archive_folder(
    dead_bookmarks: List[Dict[str, Any]],
    id_manager: IdManager,
    folder_name: str = "⚠️ 失效书签归档"
) -> Dict[str, Any]:
    """
    为失效书签创建独立的归档文件夹节点。
    """
    cleaned_items: List[Dict[str, Any]] = []
    for item in dead_bookmarks:
        clean_item = dict(item)
        clean_item.pop("_dead_reason", None)
        cleaned_items.append(clean_item)

    return {
        "date_added": get_chrome_timestamp(),
        "date_modified": "0",
        "id": id_manager.allocate(),
        "name": folder_name,
        "type": "folder",
        "children": cleaned_items
    }
