#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI 参数解析器模块。
"""

import argparse
from pathlib import Path

from .config import (
    BASE_URL,
    BATCH_SIZE,
    DEFAULT_SSL_VERIFY,
    MAX_CONCURRENT_REQUESTS,
    MODEL_NAME,
    REQUEST_TIMEOUT_SECONDS,
    get_default_bookmark_path,
)


def build_arg_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="Chrome 书签自动整理与健康检查工具"
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=get_default_bookmark_path(),
        help="Chrome 书签文件路径（默认自动匹配当前操作系统）"
    )
    parser.add_argument(
        "--action",
        choices=["archive", "delete", "keep"],
        default=None,
        help="对失效书签的预设处置方式 (archive/delete/keep)"
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="跳过执行前的退出 Chrome 确认交互"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=f"LLM 批处理切片大小 (默认: {BATCH_SIZE})"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=MAX_CONCURRENT_REQUESTS,
        help=f"最大异步网络并发数 (默认: {MAX_CONCURRENT_REQUESTS})"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=MODEL_NAME,
        help=f"大模型名称 (默认: {MODEL_NAME})"
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=BASE_URL,
        help=f"OpenAI 兼容接口 Base URL (默认: {BASE_URL})"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=REQUEST_TIMEOUT_SECONDS,
        help=f"探活请求超时时间秒数 (默认: {REQUEST_TIMEOUT_SECONDS})"
    )
    parser.add_argument(
        "--ssl-verify",
        action="store_true",
        default=DEFAULT_SSL_VERIFY,
        help="启用严格 SSL 证书验证 (默认关闭以避免误判内网自建服务)"
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="启动 Web UI 智能管理工作台并在浏览器中访问"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Web UI 服务端口 (默认: 8080)"
    )
    return parser
