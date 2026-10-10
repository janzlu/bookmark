#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
探活模块：高并发异步双阶段探活引擎（HEAD 优先，降级 GET），放行特权状态码与容错处理。
"""

import asyncio
from typing import Any, Dict, List, Tuple
import aiohttp
from .config import DEFAULT_SSL_VERIFY, MAX_CONCURRENT_REQUESTS, REQUEST_TIMEOUT_SECONDS


# 放行状态码：401 (需要鉴权), 403 (权限受限/防爬), 429 (被限频)，判定为存活站点
PASSTHROUGH_STATUSES = {401, 403, 429}

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}


async def probe_single_url(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    bookmark: Dict[str, Any],
    max_retries: int = 1
) -> Tuple[Dict[str, Any], bool, str]:
    """
    对单条书签进行双阶段探活：
    - 阶段 1：首选 HEAD 请求降低网络带宽消耗。若返回 405 Method Not Allowed 或抛出异常，触发降级。
    - 阶段 2：降级尝试标准 GET 请求（仅检查 HTTP 状态码，不预读大体积包体）。
    对瞬时网络波动支持轻量级重试退避。
    """
    url = bookmark.get("url", "")
    async with semaphore:
        for attempt in range(max_retries + 1):
            # 阶段 1: 尝试低开销 HEAD 请求
            try:
                async with session.head(url, allow_redirects=True) as resp:
                    if resp.status < 400 or resp.status in PASSTHROUGH_STATUSES:
                        return bookmark, True, f"HTTP {resp.status}"
                    if resp.status == 405:
                        # 405 表明服务器禁止 HEAD 方法，需降级为 GET
                        raise aiohttp.ClientResponseError(
                            resp.request_info, resp.history, status=405
                        )
                    # 4xx 状态码通常是永久性错误，不重试
                    if 400 <= resp.status < 500:
                        return bookmark, False, f"HTTP {resp.status}"
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
                # HEAD 阶段网络/协议错误，降级进入阶段 2 GET 探活
                pass
            except Exception:
                # 其他异常同样降级进入 GET 探活
                pass

            # 阶段 2: 降级尝试标准 GET 请求
            try:
                async with session.get(url, allow_redirects=True) as resp:
                    if resp.status < 400 or resp.status in PASSTHROUGH_STATUSES:
                        return bookmark, True, f"HTTP {resp.status}"
                    if 400 <= resp.status < 500:
                        return bookmark, False, f"HTTP {resp.status}"
                    # 5xx 在最后一次重试前退避
                    if attempt < max_retries:
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                    return bookmark, False, f"HTTP {resp.status}"
            except asyncio.TimeoutError:
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                return bookmark, False, "TimeoutError"
            except Exception as e:
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                return bookmark, False, type(e).__name__

        return bookmark, False, "MaxRetriesExceeded"


async def run_health_check(
    bookmarks: List[Dict[str, Any]],
    max_concurrency: int = MAX_CONCURRENT_REQUESTS,
    timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
    ssl_verify: bool = DEFAULT_SSL_VERIFY
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    高并发异步调度器，批量检测书签健康状态。
    - ssl_verify: 默认为 False（符合规范：避免自建/内网证书过期导致误杀），可通过配置启用严格校验。
    返回: (存活书签列表, 失效书签列表)
    """
    if not bookmarks:
        return [], []

    semaphore = asyncio.Semaphore(max_concurrency)
    timeout = aiohttp.ClientTimeout(
        total=timeout_seconds,
        connect=min(timeout_seconds, 4.0)
    )
    connector = aiohttp.TCPConnector(ssl=ssl_verify, limit=max_concurrency)

    async with aiohttp.ClientSession(
        headers=DEFAULT_HEADERS,
        timeout=timeout,
        connector=connector
    ) as session:
        tasks = [probe_single_url(session, semaphore, bm) for bm in bookmarks]
        results = await asyncio.gather(*tasks)

    alive: List[Dict[str, Any]] = []
    dead: List[Dict[str, Any]] = []

    for bm, is_alive, reason in results:
        if is_alive:
            alive.append(bm)
        else:
            dead.append({**bm, "_dead_reason": reason})

    return alive, dead
