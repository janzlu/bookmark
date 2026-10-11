#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MiniMax 独立交叉代码审计脚本
严格按照规则对核心模块进行审查：
1. 是否违背“低耦合高内聚”
2. 单文件行数控制 (<= 300~500 行)
3. 是否存在虚假实现、TODO、pass 或偷工减料
4. 异常边界与幂等性是否完备
"""

import os
import sys
from pathlib import Path
from openai import OpenAI

AUDIT_FILES = [
    "bookmark_cleaner/config.py",
    "bookmark_cleaner/storage.py",
    "bookmark_cleaner/parser.py",
    "bookmark_cleaner/prober.py",
    "bookmark_cleaner/classifier.py",
    "bookmark_cleaner/builder.py",
    "bookmark_cleaner/server_helpers.py",
    "bookmark_cleaner/server_stream.py",
    "bookmark_cleaner/server.py",
    "bookmark_cleaner/cli_args.py",
    "bookmark_cleaner/cli_prompts.py",
    "bookmark_cleaner/cli.py",
    "bookmark_manager.py",
]

def run_audit():
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_API_BASE", "https://api.minimax.chat/v1")
    model = os.getenv("MODEL_NAME", "MiniMax-M2.7")

    if not api_key:
        print("[!] 未配置 OPENAI_API_KEY，无法调用 MiniMax 进行交叉审计。")
        sys.exit(1)

    print(f"[*] 正在拉起 MiniMax ({model} @ {base_url}) 进行交叉代码审计...")

    code_corpus = []
    root = Path(__file__).resolve().parent.parent

    for rel_path in AUDIT_FILES:
        file_path = root / rel_path
        if not file_path.exists():
            continue
        code = file_path.read_text(encoding="utf-8")
        lines = len(code.splitlines())
        code_corpus.append(f"### 文件: {rel_path} (行数: {lines})\n```python\n{code}\n```\n")

    full_content = "\n".join(code_corpus)

    system_prompt = (
        "你是一名严苛的资深架构师与代码安全审计专家。请对提交的代码进行全面交叉审计。\n"
        "审查红线维度：\n"
        "1. 【架构与解耦】：是否恪守“低耦合、高内聚”，模块职责边界是否清晰，有无跨层滥用。\n"
        "2. 【单文件规模】：单文件是否控制在 300~500 行合理范围内。\n"
        "3. 【交付真实性】：是否存在 TODO、pass、伪实现或偷工减料。\n"
        "4. 【健壮性与幂等性】：异常边界处理、网络重试降级、文件写入原子性、幂等性是否完备。\n"
        "请直接给出：审计结论（通过/打回）、各项检查要点结论以及改进建议（如有）。要求精炼直接。"
    )

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请审计以下模块代码：\n\n{full_content}"}
        ],
        temperature=0.1
    )

    review_text = response.choices[0].message.content
    print("\n" + "=" * 60)
    print("【MiniMax 交叉代码审计评审报告】")
    print("=" * 60)
    print(review_text)
    print("=" * 60 + "\n")

if __name__ == "__main__":
    run_audit()
