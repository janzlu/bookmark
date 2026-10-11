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
from typing import Any, Dict, List


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
            try:
                old_bak.unlink()
            except (FileNotFoundError, PermissionError):
                pass
    except (FileNotFoundError, PermissionError):
        pass

    return backup_path


def load_bookmarks(bookmark_path: Path) -> Dict[str, Any]:
    """读取并解析 JSON 格式的 Chrome 书签文件"""
    if not bookmark_path.exists():
        raise FileNotFoundError(f"书签文件不存在: {bookmark_path}")

    try:
        with open(bookmark_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"书签文件格式损坏，无法解析为有效 JSON: {bookmark_path} ({e})") from e


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
            except (FileNotFoundError, OSError):
                pass


def restore_backup(backup_path: Path, target_path: Path) -> None:
    """从备份文件原子性恢复书签（含内容完整性校验）"""
    if not backup_path.exists():
        raise FileNotFoundError(f"备份文件不存在: {backup_path}")

    if backup_path.stat().st_size == 0:
        raise ValueError(f"备份文件为空文件，拒绝恢复: {backup_path}")

    # 预校验备份文件是否为有效 JSON 数据，防止覆写损坏文件
    try:
        with open(backup_path, "r", encoding="utf-8") as f:
            json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"备份文件已损坏，拒绝恢复: {backup_path} ({e})") from e

    parent_dir = target_path.parent
    parent_dir.mkdir(parents=True, exist_ok=True)

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=parent_dir,
            delete=False,
            prefix="restore_temp_",
            suffix=".json"
        ) as tmp:
            temp_path = Path(tmp.name)
            shutil.copyfile(backup_path, temp_path)
            tmp.flush()
            os.fsync(tmp.fileno())

        os.replace(temp_path, target_path)
        temp_path = None
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except (FileNotFoundError, OSError):
                pass


def save_deleted_audit_log(
    bookmark_path: Path,
    deleted_bookmarks: List[Dict[str, Any]]
) -> str | None:
    """
    针对不可逆的物理删除操作，记录独立审计日志以备溯源恢复。
    返回审计文件的绝对路径字符串，若无删除记录或写入异常返回 None。
    """
    if not deleted_bookmarks:
        return None

    del_ts = time.strftime("%Y%m%d_%H%M%S")
    del_audit_path = bookmark_path.parent / f"Bookmarks.deleted_{del_ts}.json"
    try:
        with open(del_audit_path, "w", encoding="utf-8") as f:
            json.dump({
                "deleted_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "count": len(deleted_bookmarks),
                "manual_verified": True,
                "deleted_bookmarks": deleted_bookmarks
            }, f, ensure_ascii=False, indent=2)
        return str(del_audit_path)
    except OSError:
        return None

