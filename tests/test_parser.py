#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from bookmark_cleaner.parser import (
    IdManager,
    flatten_bookmarks,
    normalize_url,
    normalize_and_deduplicate,
)


def test_id_manager():
    id_mgr = IdManager(initial_max_id=10)
    tree = {
        "id": "12",
        "type": "folder",
        "children": [
            {"id": "25", "type": "url"},
            {
                "id": "18",
                "type": "folder",
                "children": [{"id": "99", "type": "url"}]
            }
        ]
    }
    id_mgr.sync(tree)
    assert id_mgr.max_id == 99

    next_id = id_mgr.allocate()
    assert next_id == "100"
    assert id_mgr.max_id == 100


def test_flatten_bookmarks():
    tree = {
        "id": "1",
        "name": "Bookmarks Bar",
        "type": "folder",
        "children": [
            {"id": "2", "name": "Item 1", "type": "url", "url": "https://example.com/1"},
            {
                "id": "3",
                "name": "SubFolder",
                "type": "folder",
                "children": [
                    {"id": "4", "name": "Item 2", "type": "url", "url": "https://example.com/2"}
                ]
            }
        ]
    }
    id_mgr = IdManager()
    items = flatten_bookmarks(tree, id_mgr)
    assert len(items) == 2
    assert [item["id"] for item in items] == ["2", "4"]
    assert id_mgr.max_id == 4


def test_normalize_url():
    assert normalize_url("https://example.com/path/") == "https://example.com/path"
    assert normalize_url("https://example.com/path#section") == "https://example.com/path"
    assert normalize_url("https://example.com/path?q=test#section") == "https://example.com/path?q=test"
    assert normalize_url("http://example.com") == "http://example.com"
    assert normalize_url("") == ""


def test_normalize_and_deduplicate():
    raw_bookmarks = [
        {"id": "1", "name": "A", "url": "https://example.com/page/"},
        {"id": "2", "name": "A duplicate", "url": "https://example.com/page"},
        {"id": "3", "name": "B", "url": "javascript:void(0)"},
        {"id": "4", "name": "C", "url": "chrome://bookmarks"},
        {"id": "5", "name": "D", "url": "https://example.org/another"},
    ]
    deduped = normalize_and_deduplicate(raw_bookmarks)
    assert len(deduped) == 2
    assert deduped[0]["id"] == "1"
    assert deduped[1]["id"] == "5"
