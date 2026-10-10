#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
存储模块：书签文件的备份、读取与原子性写入持久化。
"""

import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict


def backup_database(bookmark_path: Path, max_backups: int = 10) -> Path:
    """
    在写操作执行前强制对原始 Chrome 书签文件生成带时间戳的备份文件。
    自动清理超出保留配额的最早历史备份（默认保留最近 10 份）。
    如果书签文件不存在，抛出 FileNotFoundError。
    """
    if not bookmark_path.exists():
        raise FileNotFoundError(f"未找到 Chrome 书签文件: {bookmark_path}")

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    parent_dir = bookmark_path.parent
    backup_path = parent_dir / f"Bookmarks.bak_{timestamp}"
    shutil.copyfile(bookmark_path, backup_path)

    # 维护备份配额，清理超出数量的最旧历史备份
    try:
        existing_backups = sorted(
            parent_dir.glob("Bookmarks.bak_*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        for old_bak in existing_backups[max_backups:]:
            old_bak.unlink(missing_ok=True)
    except OSError:
        pass

    return backup_path


def load_bookmarks(bookmark_path: Path) -> Dict[str, Any]:
    """读取并解析 JSON 格式的 Chrome 书签文件"""
    if not bookmark_path.exists():
        raise FileNotFoundError(f"书签文件不存在: {bookmark_path}")

    with open(bookmark_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_bookmarks_atomic(bookmark_path: Path, data: Dict[str, Any]) -> None:
    """
    使用同目录临时文件 + fsync + os.replace 进行原子覆写，
    严格按 [flush -> fsync -> close -> replace] 顺序执行，
    避免写入中断或缓存未刷盘导致 Chrome 书签文件损坏。
    """
    parent_dir = bookmark_path.parent
    parent_dir.mkdir(parents=True, exist_ok=True)

    temp_path: Path | None = None
    try:
        # 在同级目录下创建临时文件确保在同一文件系统分区，支持原子 replace
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=parent_dir,
            delete=False,
            prefix="bookmarks_temp_",
            suffix=".json"
        ) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(data, temp_file, ensure_ascii=False, indent=2)
            temp_file.flush()
            os.fsync(temp_file.fileno())

        # 文件句柄正常关闭后，原子替换目标文件
        os.replace(temp_path, bookmark_path)
        temp_path = None
    finally:
        # 若中途异常未完成替换，清理临时残留文件
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def restore_backup(backup_path: Path, target_path: Path) -> None:
    """从备份文件恢复书签"""
    if not backup_path.exists():
        raise FileNotFoundError(f"备份文件不存在: {backup_path}")
    shutil.copyfile(backup_path, target_path)
