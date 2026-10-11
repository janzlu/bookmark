#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chrome 书签自动整理与健康检查工具包。
"""

from .builder import assemble_tree, create_archive_folder
from .classifier import BookmarkClassifier
from .config import (
    API_KEY,
    BASE_URL,
    BATCH_SIZE,
    MAX_CONCURRENT_REQUESTS,
    MODEL_NAME,
    PRESET_CATEGORIES,
    REQUEST_TIMEOUT_SECONDS,
    get_chrome_timestamp,
    get_default_bookmark_path,
)
from .parser import IdManager, flatten_bookmarks, normalize_and_deduplicate, normalize_url
from .prober import probe_single_url, run_health_check
from .storage import (
    backup_database,
    load_bookmarks,
    restore_backup,
    save_bookmarks_atomic,
    save_deleted_audit_log,
)

from .server import BookmarkServer, create_app

__version__ = "1.0.0"

__all__ = [
    "assemble_tree",
    "create_archive_folder",
    "BookmarkClassifier",
    "BookmarkServer",
    "create_app",
    "IdManager",
    "flatten_bookmarks",
    "normalize_and_deduplicate",
    "normalize_url",
    "probe_single_url",
    "run_health_check",
    "backup_database",
    "load_bookmarks",
    "restore_backup",
    "save_bookmarks_atomic",
    "save_deleted_audit_log",
    "get_chrome_timestamp",
    "get_default_bookmark_path",
    "API_KEY",
    "BASE_URL",
    "MODEL_NAME",
    "BATCH_SIZE",
    "MAX_CONCURRENT_REQUESTS",
    "REQUEST_TIMEOUT_SECONDS",
    "PRESET_CATEGORIES",
]
