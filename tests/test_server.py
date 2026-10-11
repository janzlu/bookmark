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

    with patch("bookmark_cleaner.server.run_health_check", side_effect=mock_run_health_check):
        with patch.object(web.StreamResponse, "prepare", new_callable=AsyncMock):
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

    with patch("bookmark_cleaner.server.BookmarkClassifier.classify_single_batch", return_value={"2": "常用工具"}):
        with patch.object(web.StreamResponse, "prepare", new_callable=AsyncMock):
            with patch.object(web.StreamResponse, "write", new_callable=AsyncMock) as mock_write:
                resp = await server.handle_classify_stream(req)
                assert resp.status == 200
                assert mock_write.call_count >= 2
