#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import pytest
from pathlib import Path
from bookmark_cleaner.storage import (
    backup_database,
    load_bookmarks,
    save_bookmarks_atomic,
    restore_backup,
)


def test_backup_database_success(tmp_path: Path):
    src = tmp_path / "Bookmarks"
    content = {"roots": {"bookmark_bar": {"children": []}}}
    src.write_text(json.dumps(content), encoding="utf-8")

    bak = backup_database(src)
    assert bak.exists()
    assert "Bookmarks.bak_" in bak.name
    assert json.loads(bak.read_text(encoding="utf-8")) == content


def test_backup_database_not_found(tmp_path: Path):
    src = tmp_path / "NonExistent"
    with pytest.raises(FileNotFoundError):
        backup_database(src)


def test_save_and_load_bookmarks_atomic(tmp_path: Path):
    target = tmp_path / "Bookmarks"
    sample = {"version": 1, "roots": {"bookmark_bar": {"children": [{"id": "1", "name": "Google"}]}}}

    save_bookmarks_atomic(target, sample)
    assert target.exists()

    loaded = load_bookmarks(target)
    assert loaded == sample


def test_restore_backup(tmp_path: Path):
    bak = tmp_path / "Bookmarks.bak_test"
    target = tmp_path / "Bookmarks"
    data = {"restored": True}
    bak.write_text(json.dumps(data), encoding="utf-8")

    restore_backup(bak, target)
    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == data


def test_restore_backup_empty_or_corrupt_rejected(tmp_path: Path):
    target = tmp_path / "Bookmarks"
    empty_bak = tmp_path / "Bookmarks.bak_empty"
    empty_bak.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="为空文件"):
        restore_backup(empty_bak, target)

    corrupt_bak = tmp_path / "Bookmarks.bak_corrupt"
    corrupt_bak.write_text("invalid json {{{", encoding="utf-8")
    with pytest.raises(ValueError, match="已损坏"):
        restore_backup(corrupt_bak, target)


def test_load_bookmarks_invalid_json(tmp_path: Path):
    target = tmp_path / "Bookmarks"
    target.write_text("not json content", encoding="utf-8")
    with pytest.raises(ValueError, match="书签文件格式损坏"):
        load_bookmarks(target)

