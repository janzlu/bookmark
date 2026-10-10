#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from bookmark_cleaner.builder import assemble_tree, create_archive_folder
from bookmark_cleaner.parser import IdManager


def test_assemble_tree_structure():
    id_mgr = IdManager(initial_max_id=10)
    classified = [
        (
            {"id": "1", "name": "DeepSeek", "type": "url", "url": "https://deepseek.com"},
            "技术研发/AI与大模型"
        ),
        (
            {"id": "2", "name": "OpenAI", "type": "url", "url": "https://openai.com"},
            "技术研发/AI与大模型"
        ),
        (
            {"id": "3", "name": "GitHub", "type": "url", "url": "https://github.com"},
            "技术研发/编程开发"
        ),
        (
            {"id": "4", "name": "Uncategorized", "type": "url", "url": "https://example.com"},
            ""
        )
    ]

    roots = assemble_tree(classified, id_mgr)

    # 根节点应包含两个一级文件夹："技术研发" 和 "其他"
    root_names = [f["name"] for f in roots]
    assert "技术研发" in root_names
    assert "其他" in root_names

    tech_folder = next(f for f in roots if f["name"] == "技术研发")
    sub_names = [sf["name"] for sf in tech_folder["children"]]
    assert "AI与大模型" in sub_names
    assert "编程开发" in sub_names

    ai_folder = next(sf for sf in tech_folder["children"] if sf["name"] == "AI与大模型")
    assert len(ai_folder["children"]) == 2
    assert ai_folder["children"][0]["name"] == "DeepSeek"
    assert ai_folder["children"][1]["name"] == "OpenAI"

    # 验证 ID 自增
    all_assigned_ids = [int(f["id"]) for f in roots]
    assert all(i > 10 for i in all_assigned_ids)


def test_create_archive_folder():
    id_mgr = IdManager(initial_max_id=50)
    dead_items = [
        {"id": "5", "name": "Dead 1", "url": "http://dead1.com", "_dead_reason": "HTTP 404"},
        {"id": "6", "name": "Dead 2", "url": "http://dead2.com", "_dead_reason": "TimeoutError"}
    ]
    folder = create_archive_folder(dead_items, id_mgr)

    assert folder["name"] == "⚠️ 失效书签归档"
    assert folder["type"] == "folder"
    assert folder["id"] == "51"
    assert len(folder["children"]) == 2
    assert "_dead_reason" not in folder["children"][0]
    assert folder["children"][0]["id"] == "5"
