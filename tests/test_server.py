#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from aiohttp import web
from bookmark_cleaner.server import BookmarkServer, create_app


@pytest.fixture
def mock_bookmarks_file(tmp_path: Path):
    target = tmp_path / "Bookmarks"
    data = {
        "roots": {
            "bookmark_bar": {
                "id": "1",
                "name": "Bookmarks Bar",
                "type": "folder",
                "children": [
                    {"id": "2", "name": "Google", "type": "url", "url": "https://google.com"},
                    {"id": "3", "name": "Google Dup", "type": "url", "url": "https://google.com/"},
                    {"id": "4", "name": "Dead", "type": "url", "url": "https://dead.test"}
                ]
            }
        }
    }
    target.write_text(json.dumps(data), encoding="utf-8")
    return target


@pytest.mark.asyncio
async def test_server_status_and_summary(mock_bookmarks_file: Path):
    server = BookmarkServer(bookmark_path=mock_bookmarks_file)

    # 测试 /api/status
    req_status = MagicMock()
    resp_status = await server.handle_status(req_status)
    assert resp_status.status == 200
    data_status = json.loads(resp_status.body.decode())
    assert "chrome_running" in data_status
    assert data_status["file_exists"] is True
    assert data_status["config"]["model_name"] is not None

    # 测试 /api/bookmarks/summary
    req_sum = MagicMock()
    resp_sum = await server.handle_summary(req_sum)
    assert resp_sum.status == 200
    data_sum = json.loads(resp_sum.body.decode())
    assert data_sum["total_count"] == 3
    assert data_sum["unique_count"] == 2
    assert data_sum["duplicate_count"] == 1


@pytest.mark.asyncio
async def test_server_probe_endpoint(mock_bookmarks_file: Path):
    server = BookmarkServer(bookmark_path=mock_bookmarks_file)

    async def mock_run_health_check(bookmarks, *args, **kwargs):
        alive = [b for b in bookmarks if "google" in b.get("url", "")]
        dead = [{**b, "_dead_reason": "HTTP 404"} for b in bookmarks if "dead" in b.get("url", "")]
        return alive, dead

    req = MagicMock()
    req.can_read_body = True
    req.json = AsyncMock(return_value={"limit": 10})

    with patch("bookmark_cleaner.server.run_health_check", side_effect=mock_run_health_check):
        resp = await server.handle_probe(req)
        assert resp.status == 200
        data = json.loads(resp.body.decode())
        assert data["alive_count"] == 1
        assert data["dead_count"] == 1


@pytest.mark.asyncio
async def test_server_classify_endpoint(mock_bookmarks_file: Path):
    server = BookmarkServer(bookmark_path=mock_bookmarks_file)

    req = MagicMock()
    req.json = AsyncMock(return_value={
        "bookmarks": [{"id": "2", "name": "Google", "url": "https://google.com"}]
    })

    with patch(
        "bookmark_cleaner.server.BookmarkClassifier.classify_all",
        return_value=[({"id": "2", "name": "Google", "url": "https://google.com"}, "效率工具/常用服务")]
    ):
        resp = await server.handle_classify(req)
        assert resp.status == 200
        data = json.loads(resp.body.decode())
        assert len(data["classified"]) == 1
        assert data["classified"][0]["category"] == "效率工具/常用服务"


@pytest.mark.asyncio
async def test_server_apply_and_restore(mock_bookmarks_file: Path):
    server = BookmarkServer(bookmark_path=mock_bookmarks_file)

    # Mock is_chrome_running 返回 False
    with patch("bookmark_cleaner.server.is_chrome_running", return_value=False):
        req_apply = MagicMock()
        req_apply.json = AsyncMock(return_value={
            "classified": [
                {
                    "bookmark": {"id": "2", "name": "Google", "type": "url", "url": "https://google.com"},
                    "category": "效率工具/常用服务"
                }
            ],
            "dead": [
                {"id": "4", "name": "Dead", "type": "url", "url": "https://dead.test"}
            ],
            "dead_action": "archive"
        })

        resp_apply = await server.handle_apply(req_apply)
        assert resp_apply.status == 200
        data_apply = json.loads(resp_apply.body.decode())
        assert data_apply["success"] is True

        # 检查是否生成备份
        backups = list(mock_bookmarks_file.parent.glob("Bookmarks.bak_*"))
        assert len(backups) == 1
        bak_name = backups[0].name

        # 测试恢复接口
        req_restore = MagicMock()
        req_restore.json = AsyncMock(return_value={"filename": bak_name})
        resp_restore = await server.handle_restore(req_restore)
        assert resp_restore.status == 200
        data_restore = json.loads(resp_restore.body.decode())
        assert data_restore["success"] is True


@pytest.mark.asyncio
async def test_server_config_update(mock_bookmarks_file: Path):
    server = BookmarkServer(bookmark_path=mock_bookmarks_file)

    req = MagicMock()
    req.json = AsyncMock(return_value={
        "model_name": "test-model-xyz",
        "max_concurrency": 42
    })

    resp = await server.handle_config_update(req)
    assert resp.status == 200
    assert server.config["model_name"] == "test-model-xyz"
    assert server.config["max_concurrency"] == 42


@pytest.mark.asyncio
async def test_server_probe_stream(mock_bookmarks_file: Path):
    server = BookmarkServer(bookmark_path=mock_bookmarks_file)

    async def mock_run_health_check(bookmarks, *args, **kwargs):
        progress_cb = kwargs.get("progress_callback")
        if progress_cb:
            await progress_cb(bookmarks[0], True, "HTTP 200", 1, len(bookmarks))
        return bookmarks, []

    req = MagicMock()
    req.can_read_body = True
    req.json = AsyncMock(return_value={"limit": 5})

    with patch("bookmark_cleaner.server_stream.run_health_check", side_effect=mock_run_health_check):
        with patch.object(web.StreamResponse, "prepare", new_callable=AsyncMock):
            with patch.object(web.StreamResponse, "drain", new_callable=AsyncMock):
                with patch.object(web.StreamResponse, "write", new_callable=AsyncMock) as mock_write:
                    resp = await server.handle_probe_stream(req)
                    assert resp.status == 200
                    assert mock_write.call_count >= 2


@pytest.mark.asyncio
async def test_server_classify_stream(mock_bookmarks_file: Path):
    server = BookmarkServer(bookmark_path=mock_bookmarks_file)

    req = MagicMock()
    req.json = AsyncMock(return_value={
        "bookmarks": [{"id": "2", "name": "Google", "url": "https://google.com"}]
    })

    with patch("bookmark_cleaner.server_stream.BookmarkClassifier.classify_single_batch", return_value={"2": "常用工具"}):
        with patch.object(web.StreamResponse, "prepare", new_callable=AsyncMock):
            with patch.object(web.StreamResponse, "drain", new_callable=AsyncMock):
                with patch.object(web.StreamResponse, "write", new_callable=AsyncMock) as mock_write:
                    resp = await server.handle_classify_stream(req)
                    assert resp.status == 200
                    assert mock_write.call_count >= 2


@pytest.mark.asyncio
async def test_server_apply_batch_delete_without_verification_rejected(mock_bookmarks_file: Path):
    server = BookmarkServer(bookmark_path=mock_bookmarks_file)

    with patch("bookmark_cleaner.server.is_chrome_running", return_value=False):
        req = MagicMock()
        req.json = AsyncMock(return_value={
            "classified": [],
            "deleted_bookmarks": [
                {"id": "4", "name": "Dead", "type": "url", "url": "https://dead.test"}
            ],
            "manual_verified": False
        })
        resp = await server.handle_apply(req)
        assert resp.status == 400
        data = json.loads(resp.body.decode())
        assert "安全拦截" in data["error"]


@pytest.mark.asyncio
async def test_server_apply_batch_delete_verified_creates_audit_log(mock_bookmarks_file: Path):
    server = BookmarkServer(bookmark_path=mock_bookmarks_file)

    with patch("bookmark_cleaner.server.is_chrome_running", return_value=False):
        req = MagicMock()
        req.json = AsyncMock(return_value={
            "classified": [
                {
                    "bookmark": {"id": "2", "name": "Google", "type": "url", "url": "https://google.com"},
                    "category": "通用/搜索"
                }
            ],
            "archived_bookmarks": [
                {"id": "5", "name": "ArchiveMe", "type": "url", "url": "https://archive.me"}
            ],
            "deleted_bookmarks": [
                {"id": "4", "name": "Dead", "type": "url", "url": "https://dead.test"}
            ],
            "manual_verified": True
        })
        resp = await server.handle_apply(req)
        assert resp.status == 200
        data = json.loads(resp.body.decode())
        assert data["success"] is True
        assert data["deleted_count"] == 1
        assert data["archived_count"] == 1
        assert data["deleted_audit_path"] is not None

        # 验证审计日志文件真实创建且内容完整
        audit_file = Path(data["deleted_audit_path"])
        assert audit_file.exists()
        audit_content = json.loads(audit_file.read_text(encoding="utf-8"))
        assert audit_content["manual_verified"] is True
        assert audit_content["count"] == 1
        assert audit_content["deleted_bookmarks"][0]["url"] == "https://dead.test"

        # 验证物理删除：读取重构后的书签文件，确认 Dead 不在树中，ArchiveMe 在归档文件夹中
        saved_data = json.loads(mock_bookmarks_file.read_text(encoding="utf-8"))
        bar_children = saved_data["roots"]["bookmark_bar"]["children"]
        folder_names = [f["name"] for f in bar_children if f.get("type") == "folder"]
        assert "⚠️ 失效书签归档" in folder_names
        assert "通用" in folder_names

        # 检查所有节点，确保 https://dead.test 已被物理抹除
        all_urls = []
        def collect_urls(node):
            if node.get("type") == "url":
                all_urls.append(node.get("url"))
            for c in node.get("children", []):
                collect_urls(c)
        collect_urls(saved_data["roots"]["bookmark_bar"])
        assert "https://dead.test" not in all_urls
        assert "https://archive.me" in all_urls
        assert "https://google.com" in all_urls


@pytest.mark.asyncio
async def test_server_restore_path_traversal_rejected(mock_bookmarks_file: Path):
    server = BookmarkServer(bookmark_path=mock_bookmarks_file)

    with patch("bookmark_cleaner.server.is_chrome_running", return_value=False):
        # 1. 测试跨目录穿越
        req_traversal = MagicMock()
        req_traversal.json = AsyncMock(return_value={"filename": "../../etc/passwd"})
        resp = await server.handle_restore(req_traversal)
        assert resp.status == 400
        data = json.loads(resp.body.decode())
        assert "非法的备份文件名格式" in data["error"]

        # 2. 测试非 Bookmarks.bak_ 前缀文件
        req_fake = MagicMock()
        req_fake.json = AsyncMock(return_value={"filename": "Bookmarks.deleted_123.json"})
        resp_fake = await server.handle_restore(req_fake)
        assert resp_fake.status == 400

