#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import aiohttp
from bookmark_cleaner.prober import probe_single_url, run_health_check


class DummyResponse:
    def __init__(self, status: int):
        self.status = status
        self.request_info = MagicMock()
        self.history = ()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.mark.asyncio
async def test_probe_single_url_head_success():
    session = MagicMock()
    session.head.return_value = DummyResponse(200)
    semaphore = asyncio.Semaphore(5)

    bm = {"id": "1", "url": "https://example.com"}
    res_bm, is_alive, reason = await probe_single_url(session, semaphore, bm)

    assert is_alive is True
    assert reason == "HTTP 200"
    session.head.assert_called_once()
    session.get.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403, 429])
async def test_probe_single_url_passthrough_statuses(status_code: int):
    session = MagicMock()
    session.head.return_value = DummyResponse(status_code)
    semaphore = asyncio.Semaphore(5)

    bm = {"id": "1", "url": "https://protected.com"}
    _, is_alive, reason = await probe_single_url(session, semaphore, bm)

    assert is_alive is True
    assert f"HTTP {status_code}" in reason


@pytest.mark.asyncio
async def test_probe_single_url_fallback_to_get():
    session = MagicMock()
    # HEAD 返回 405 Method Not Allowed
    session.head.return_value = DummyResponse(405)
    # GET 降级成功返回 200
    session.get.return_value = DummyResponse(200)
    semaphore = asyncio.Semaphore(5)

    bm = {"id": "1", "url": "https://no-head.com"}
    _, is_alive, reason = await probe_single_url(session, semaphore, bm)

    assert is_alive is True
    assert reason == "HTTP 200"
    session.get.assert_called_once()


@pytest.mark.asyncio
async def test_probe_single_url_dead():
    session = MagicMock()
    session.head.return_value = DummyResponse(404)
    # 第一次 HEAD 返回 404，不会报 405，直接返回 dead
    semaphore = asyncio.Semaphore(5)

    bm = {"id": "1", "url": "https://notfound.com"}
    _, is_alive, reason = await probe_single_url(session, semaphore, bm)

    assert is_alive is False
    assert reason == "HTTP 404"


@pytest.mark.asyncio
async def test_probe_single_url_timeout():
    session = MagicMock()
    session.head.side_effect = asyncio.TimeoutError()
    session.get.side_effect = asyncio.TimeoutError()
    semaphore = asyncio.Semaphore(5)

    bm = {"id": "1", "url": "https://timeout.com"}
    _, is_alive, reason = await probe_single_url(session, semaphore, bm)

    assert is_alive is False
    assert reason == "TimeoutError"


@pytest.mark.asyncio
async def test_run_health_check_empty():
    alive, dead = await run_health_check([])
    assert alive == []
    assert dead == []
