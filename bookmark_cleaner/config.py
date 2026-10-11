#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置模块：环境变量读取、默认路径及运行参数。
"""

import os
import sys
import time
from pathlib import Path
from typing import List


def get_default_base_url() -> str:
    """获取 LLM 默认 BASE_URL，兼容 OPENAI_BASE_URL 和 OPENAI_API_BASE"""
    for key in ("OPENAI_BASE_URL", "OPENAI_API_BASE"):
        val = os.getenv(key)
        if val and val.strip():
            return val.strip()
    return "https://api.openai.com/v1"


def get_default_model(base_url: str) -> str:
    """根据 BASE_URL 智能提供默认模型名称"""
    env_model = os.getenv("MODEL_NAME")
    if env_model and env_model.strip():
        return env_model.strip()
    if "minimax" in base_url.lower():
        return "MiniMax-M2.7"
    if "deepseek" in base_url.lower():
        return "deepseek-chat"
    return "gpt-4o-mini"


BASE_URL: str = get_default_base_url()
API_KEY: str = (os.getenv("OPENAI_API_KEY") or "").strip()
MODEL_NAME: str = get_default_model(BASE_URL)

def _safe_int_env(key: str, default: int) -> int:
    val = os.getenv(key)
    if not val:
        return default
    try:
        return int(val.strip())
    except (ValueError, TypeError):
        return default


def _safe_float_env(key: str, default: float) -> float:
    val = os.getenv(key)
    if not val:
        return default
    try:
        return float(val.strip())
    except (ValueError, TypeError):
        return default


# 并发与检测参数
MAX_CONCURRENT_REQUESTS: int = _safe_int_env("MAX_CONCURRENT_REQUESTS", 30)
REQUEST_TIMEOUT_SECONDS: float = _safe_float_env("REQUEST_TIMEOUT_SECONDS", 7.0)
BATCH_SIZE: int = _safe_int_env("BATCH_SIZE", 25)
DEFAULT_SSL_VERIFY: bool = os.getenv("SSL_VERIFY", "false").lower() in ("1", "true", "yes")

# 预设推荐分类树
PRESET_CATEGORIES: List[str] = [
    "技术研发/AI与大模型",
    "技术研发/编程开发",
    "效率工具/常用服务",
    "产品设计/灵感素材",
    "资讯阅读/科技博客",
    "金融投资/经济理财",
    "影音生活/休闲娱乐",
    "其他/待整理"
]


def get_default_bookmark_path() -> Path:
    """自动适配不同操作系统的 Chrome 书签路径"""
    home = Path.home()
    if sys.platform == "win32":
        return home / "AppData/Local/Google/Chrome/User Data/Default/Bookmarks"
    elif sys.platform == "darwin":
        return home / "Library/Application Support/Google/Chrome/Default/Bookmarks"
    else:
        return home / ".config/google-chrome/Default/Bookmarks"


def get_chrome_timestamp(ts: float | None = None) -> str:
    """生成符合 WebKit 纪元标准的微秒时间戳字符串"""
    if ts is None:
        ts = time.time()
    return str(int((ts + 11644473600) * 1_000_000))
