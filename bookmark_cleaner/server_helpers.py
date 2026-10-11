#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web UI 服务端辅助工具模块：系统进程探测、历史备份统计与 SSE 流式事件推送封装。
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List
from aiohttp import web


def is_chrome_running() -> bool:
    """检查宿主机是否存在运行中的 Google Chrome 进程"""
    try:
        res = subprocess.run(
            ["pgrep", "-fl", "Google Chrome"],
            capture_output=True,
            text=True,
            timeout=2.0
        )
        return res.returncode == 0 and bool(res.stdout.strip())
    except (subprocess.SubprocessError, OSError):
        return False


def get_backup_list(bookmark_path: Path) -> List[Dict[str, Any]]:
    """获取所有历史备份文件列表及元信息"""
    parent = bookmark_path.parent
    if not parent.exists():
        return []

    backups = []
    for p in parent.glob("Bookmarks.bak_*"):
        try:
            stat = p.stat()
            backups.append({
                "filename": p.name,
                "path": str(p),
                "size_bytes": stat.st_size,
                "modified_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
            })
        except OSError:
            pass

    backups.sort(key=lambda x: x["filename"], reverse=True)
    return backups


async def send_sse_event(response: web.StreamResponse, event_data: Dict[str, Any]) -> None:
    """向 SSE 流写入单条格式化的 JSON 事件并刷盘推送"""
    chunk = f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
    await response.write(chunk.encode("utf-8"))
    try:
        await response.drain()
    except (AssertionError, AttributeError, RuntimeError):
        pass


async def send_sse_error(response: web.StreamResponse, error_msg: str) -> None:
    """向 SSE 流推送异常中断事件"""
    await send_sse_event(response, {"type": "error", "error": error_msg})
