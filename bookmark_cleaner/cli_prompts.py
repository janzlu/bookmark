#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI 交互提示与人工确认模块：处理终端失效链接展示与人工核验安全门禁。
"""

from typing import Any, Dict, List


def prompt_dead_link_action(
    dead_bookmarks: List[Dict[str, Any]],
    auto_choice: str | None = None
) -> str:
    """
    终端高亮展示失效链接明细，并交互式获取用户处置决策。
    返回值: 'archive' | 'delete' | 'keep'
    """
    if not dead_bookmarks:
        print("\n[✓] 链接探活全部通过，未检测到死链。\n")
        return "keep"

    if auto_choice in ("archive", "delete", "keep"):
        if auto_choice == "delete":
            print("\n" + "!" * 80)
            print(f"⚠️ 【人工安全核验警示】已指定 --action delete 参数批量物理删除 {len(dead_bookmarks)} 个书签！")
            print("!" * 80)
            try:
                confirm = input("若确认批量彻底物理删除，请手动输入 'YES' (输入其他将降级为安全归档): ").strip()
            except (EOFError, KeyboardInterrupt):
                confirm = "NO"
            if confirm == "YES":
                return "delete"
            print("[*] 未通过人工二次核验，已自动降级为安全归档模式。")
            return "archive"
        print(f"\n[*] 已通过参数自动指定处置策略: {auto_choice}")
        return auto_choice

    print("\n" + "=" * 80)
    print(f"⚠️  共识别出 {len(dead_bookmarks)} 个疑似无法访问的书签：")
    print("=" * 80)

    for idx, bm in enumerate(dead_bookmarks, 1):
        reason = bm.get("_dead_reason", "未知")
        title = bm.get("name") or "(无标题)"
        url = bm.get("url", "")
        print(f"[{idx:02d}] 异常状态: \033[31m{reason:<18}\033[0m | 标题: {title}")
        print(f"     链接地址: {url}")

    print("=" * 80)
    print("请选择对上述失效书签的处置方式：")
    print("  [1] 自动归档（默认：分类存入「⚠️ 失效书签归档」独立文件夹）")
    print("  [2] 直接剔除（从整理结果中彻底移除）")
    print("  [3] 忽略异常（保留并正常随同分类）")

    try:
        choice = input("请输入选项编号 [1/2/3] (直接回车默认 1): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n[*] 检测到中断，默认选择自动归档。")
        return "archive"

    if choice == "2":
        print("\n" + "!" * 80)
        print("⚠️ 【人工安全核验警示】物理删除是不可逆操作，所选书签将从 Chrome 中彻底移除！")
        print("!" * 80)
        try:
            confirm = input("若确认彻底物理删除，请手动输入 'YES' (输入其他任意内容将自动降级为安全归档): ").strip()
        except (EOFError, KeyboardInterrupt):
            confirm = "NO"

        if confirm == "YES":
            return "delete"
        print("[*] 未通过人工二次核验，已自动降级为安全归档模式。")
        return "archive"
    elif choice == "3":
        return "keep"
    return "archive"
