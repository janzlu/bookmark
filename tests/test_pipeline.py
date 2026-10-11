#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from pathlib import Path
from unittest.mock import patch
import pytest

from bookmark_cleaner.cli import BookmarkWorkflow
from bookmark_cleaner.storage import load_bookmarks


@pytest.mark.asyncio
async def test_end_to_end_workflow(tmp_path: Path):
    target_bm = tmp_path / "Bookmarks"
    initial_data = {
        "checksum": "abc123",
        "roots": {
            "bookmark_bar": {
                "id": "1",
                "name": "Bookmarks Bar",
                "type": "folder",
                "children": [
                    {
                        "date_added": "13300000000000000",
                        "id": "2",
                        "name": "GitHub",
                        "type": "url",
                        "url": "https://github.com"
                    },
                    {
                        "date_added": "13300000000000000",
                        "id": "3",
                        "name": "GitHub Dup",
                        "type": "url",
                        "url": "https://github.com/"
                    },
                    {
                        "date_added": "13300000000000000",
                        "id": "4",
                        "name": "Broken Link",
                        "type": "url",
                        "url": "https://broken.invalid"
                    }
                ]
            }
        },
        "version": 1
    }
    target_bm.write_text(json.dumps(initial_data), encoding="utf-8")

    workflow = BookmarkWorkflow(
        bookmark_path=target_bm,
        api_key="mock-key",
        base_url="https://api.openai.com/v1",
        model_name="mock-model"
    )

    # Mock 探活：GitHub 存活，Broken Link 死亡
    async def mock_run_health_check(bookmarks, *args, **kwargs):
        alive, dead = [], []
        for b in bookmarks:
            if "broken" in b.get("url", ""):
                dead.append({**b, "_dead_reason": "HTTP 404"})
            else:
                alive.append(b)
        return alive, dead

    # Mock 分类器：返回分类
    def mock_classify_single_batch(batch, max_retries=2):
        return {str(b["id"]): "技术研发/编程开发" for b in batch}

    with patch("bookmark_cleaner.cli.run_health_check", side_effect=mock_run_health_check), \
         patch.object(workflow.classifier, "classify_single_batch", side_effect=mock_classify_single_batch):

        await workflow.execute(dead_action_override="archive", skip_confirm=True)

    # 验证备份生成
    backups = list(tmp_path.glob("Bookmarks.bak_*"))
    assert len(backups) == 1

    # 验证最终书签结构
    final_data = load_bookmarks(target_bm)
    children = final_data["roots"]["bookmark_bar"]["children"]

    # 包含重构的文件夹 + 归档文件夹
    folder_names = [c["name"] for c in children]
    assert "技术研发" in folder_names
    assert "⚠️ 失效书签归档" in folder_names

    # 验证去重：GitHub 只有 1 个
    tech_folder = next(c for c in children if c["name"] == "技术研发")
    dev_folder = next(sc for sc in tech_folder["children"] if sc["name"] == "编程开发")
    assert len(dev_folder["children"]) == 1
    assert dev_folder["children"][0]["name"] == "GitHub"

    # 验证失效书签归档
    archive_folder = next(c for c in children if c["name"] == "⚠️ 失效书签归档")
    assert len(archive_folder["children"]) == 1
    assert archive_folder["children"][0]["name"] == "Broken Link"
    assert "_dead_reason" not in archive_folder["children"][0]


@pytest.mark.asyncio
async def test_end_to_end_workflow_batch_delete(tmp_path: Path):
    target_bm = tmp_path / "Bookmarks"
    initial_data = {
        "roots": {
            "bookmark_bar": {
                "id": "1",
                "name": "Bookmarks Bar",
                "type": "folder",
                "children": [
                    {"id": "2", "name": "Python", "type": "url", "url": "https://python.org"},
                    {"id": "3", "name": "DeadLink", "type": "url", "url": "https://dead.test"}
                ]
            }
        }
    }
    target_bm.write_text(json.dumps(initial_data), encoding="utf-8")

    workflow = BookmarkWorkflow(
        bookmark_path=target_bm,
        api_key="mock-key",
        base_url="https://api.openai.com/v1",
        model_name="mock-model"
    )

    async def mock_run_health_check(bookmarks, *args, **kwargs):
        alive = [b for b in bookmarks if "python" in b.get("url", "")]
        dead = [{**b, "_dead_reason": "HTTP 404"} for b in bookmarks if "dead" in b.get("url", "")]
        return alive, dead

    def mock_classify_single_batch(batch, max_retries=2):
        return {str(b["id"]): "开发/技术" for b in batch}

    with patch("bookmark_cleaner.cli.run_health_check", side_effect=mock_run_health_check), \
         patch.object(workflow.classifier, "classify_single_batch", side_effect=mock_classify_single_batch), \
         patch("builtins.input", return_value="YES"):

        await workflow.execute(dead_action_override="delete", skip_confirm=True)

    # 验证物理删除审计日志生成
    deleted_audits = list(tmp_path.glob("Bookmarks.deleted_*.json"))
    assert len(deleted_audits) == 1
    audit_data = json.loads(deleted_audits[0].read_text(encoding="utf-8"))
    assert audit_data["count"] == 1
    assert audit_data["deleted_bookmarks"][0]["url"] == "https://dead.test"

    # 验证最终书签结构：DeadLink 被物理剔除，且不存在归档文件夹
    final_data = load_bookmarks(target_bm)
    children = final_data["roots"]["bookmark_bar"]["children"]
    folder_names = [c["name"] for c in children]
    assert "⚠️ 失效书签归档" not in folder_names
    assert "开发" in folder_names



@pytest.mark.asyncio
async def test_bookmark_manager_backward_compatibility(tmp_path: Path):
    from bookmark_manager import BookmarkManager

    target_bm = tmp_path / "Bookmarks"
    initial_data = {
        "roots": {
            "bookmark_bar": {
                "id": "1",
                "name": "Bookmarks Bar",
                "type": "folder",
                "children": [
                    {"id": "2", "name": "Python", "type": "url", "url": "https://python.org"}
                ]
            }
        }
    }
    target_bm.write_text(json.dumps(initial_data), encoding="utf-8")

    mgr = BookmarkManager(target_bm)
    assert mgr.max_id == 1
    bak = mgr.backup_database()
    assert bak.exists()

    ts = mgr.get_chrome_timestamp()
    assert len(ts) >= 16

    new_id = mgr.allocate_id()
    assert new_id == "2"

