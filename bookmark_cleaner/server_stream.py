#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web UI SSE 流式通信处理器：处理探活与大模型语义聚类的实时进度事件分发。
"""

import json
from pathlib import Path
from typing import Any, Dict
from aiohttp import web

from .classifier import BookmarkClassifier
from .parser import IdManager, flatten_bookmarks, normalize_and_deduplicate
from .prober import run_health_check
from .server_helpers import send_sse_error, send_sse_event
from .storage import load_bookmarks


async def stream_probe(
    request: web.Request,
    config: Dict[str, Any],
    bookmark_path: Path
) -> web.StreamResponse:
    """高并发异步探活流式处理器"""
    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream; charset=utf-8",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
    await response.prepare(request)

    try:
        body: Dict[str, Any] = {}
        if request.can_read_body:
            body = await request.json()

        concurrency = int(body.get("max_concurrency", config["max_concurrency"]))
        timeout = float(body.get("timeout_seconds", config["timeout_seconds"]))
        ssl_verify = bool(body.get("ssl_verify", config["ssl_verify"]))
        limit = body.get("limit")

        raw_data = load_bookmarks(bookmark_path)
        id_mgr = IdManager()
        raw_list = flatten_bookmarks(raw_data.get("roots", {}).get("bookmark_bar", {}), id_mgr)
        deduped = normalize_and_deduplicate(raw_list)

        target_items = deduped[:int(limit)] if limit else deduped

        async def on_progress(bm, is_alive, reason, completed, total):
            event = {
                "type": "progress",
                "current": completed,
                "total": total,
                "is_alive": is_alive,
                "reason": reason,
                "name": bm.get("name", "") or "(无标题)",
                "url": bm.get("url", "")
            }
            await send_sse_event(response, event)

        alive, dead = await run_health_check(
            target_items,
            max_concurrency=concurrency,
            timeout_seconds=timeout,
            ssl_verify=ssl_verify,
            progress_callback=on_progress
        )

        complete_event = {
            "type": "complete",
            "total_tested": len(target_items),
            "alive_count": len(alive),
            "dead_count": len(dead),
            "alive": alive,
            "dead": dead
        }
        await send_sse_event(response, complete_event)
        return response
    except Exception as e:
        await send_sse_error(response, str(e))
        return response


async def stream_classify(
    request: web.Request,
    config: Dict[str, Any]
) -> web.StreamResponse:
    """流式大模型语义聚类处理器"""
    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream; charset=utf-8",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
    await response.prepare(request)

    try:
        body = await request.json()
        bookmarks = body.get("bookmarks", [])
        if not bookmarks:
            await send_sse_event(response, {"type": "complete", "classified": []})
            return response

        classifier = BookmarkClassifier(
            api_key=config["api_key"],
            base_url=config["base_url"],
            model_name=config["model_name"],
            preset_categories=config["preset_categories"]
        )

        batch_size = int(body.get("batch_size", config["batch_size"]))
        total = len(bookmarks)
        classified_pairs = []

        for i in range(0, total, batch_size):
            batch = bookmarks[i:i + batch_size]
            batch_mapping = classifier.classify_single_batch(batch)
            batch_items = []
            for bm in batch:
                cat = batch_mapping.get(str(bm["id"]), "其他/待整理")
                classified_pairs.append((bm, cat))
                batch_items.append({"name": bm.get("name", "") or "(无标题)", "category": cat})

            batch_event = {
                "type": "progress",
                "current": min(i + batch_size, total),
                "total": total,
                "batch_items": batch_items
            }
            await send_sse_event(response, batch_event)

        complete_event = {
            "type": "complete",
            "classified": [
                {"bookmark": bm, "category": cat}
                for bm, cat in classified_pairs
            ]
        }
        await send_sse_event(response, complete_event)
        return response
    except Exception as e:
        await send_sse_error(response, str(e))
        return response
