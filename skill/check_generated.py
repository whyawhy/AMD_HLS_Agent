#!/usr/bin/env python3
"""生成代码的静态预检 CLI（花 Vitis 时间之前先跑一遍）。

核心实现在 hls_agent/static_check.py；本文件只是命令行入口，
保证技能包可以独立使用：python skill/check_generated.py ...

用法::

    python skill/check_generated.py <生成的.cpp> --header <给定的.h> --top <函数名>

退出码 0 = 无阻断问题；1 = 有问题。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hls_agent.static_check import CheckResult, check  # noqa: E402


def main(argv: Optional[list] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="生成代码静态预检")
    ap.add_argument("source", help="生成的 .cpp")
    ap.add_argument("--header", help="题目给定的 .h")
    ap.add_argument("--top", required=True, help="顶层函数名")
    args = ap.parse_args(argv)

    src = Path(args.source)
    if not src.is_file():
        print(f"[错误] 文件不存在: {src}", file=sys.stderr)
        return 1
    hdr = Path(args.header) if args.header else None

    print(f"静态预检: {src.name}  顶层函数={args.top}")
    res = check(src, hdr, args.top)
    print(res.render())
    return 0 if res.ok else 1


if __name__ == "__main__":
    sys.exit(main())
