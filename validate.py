#!/usr/bin/env python3
"""对生成的 C++ 工程做静态完整性校验（不依赖 C++ 编译器）。

用法::

    py validate.py output          # 校验 output 下的所有题目工程

校验项：
  1. 必需文件齐全且非空
  2. 模板占位符（$XXX）已全部替换
  3. 花括号 / 圆括号 / 方括号配平（已剔除注释与字符串字面量）
  4. testbench 含 int main，且 .cpp / _tb.cpp 都 include 了本题目头文件
  5. 头文件宏保护名与题目编号一致
  6. 所有使用的全大写宏都在头文件里有 #define
  7. 顶层函数名与题目编号一致
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Tuple

REQUIRED = ["{pid}.h", "{pid}.cpp", "{pid}_tb.cpp", "run.tcl", "README.md", "question.txt"]

_COMMENT_OR_STRING = re.compile(
    r'//[^\n]*' r'|/\*.*?\*/' r'|"(?:\\.|[^"\\])*"' r"|'(?:\\.|[^'\\])*'",
    re.DOTALL,
)
_PLACEHOLDER = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*")
_MACRO_DEF = re.compile(r"^\s*#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
_ALLCAPS = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")


def strip_code(src: str) -> str:
    """剔除注释与字符串/字符字面量。"""
    return _COMMENT_OR_STRING.sub(" ", src)


def balanced(src: str) -> Tuple[bool, str]:
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: List[str] = []
    for ch in src:
        if ch in "([{":
            stack.append(ch)
        elif ch in pairs:
            if not stack or stack[-1] != pairs[ch]:
                return False, f"括号不匹配: 遇到 '{ch}'"
            stack.pop()
    if stack:
        return False, f"括号未闭合: 剩余 {''.join(stack)}"
    return True, "ok"


def check_project(proj: Path) -> List[str]:
    """返回该工程的问题列表；空列表表示通过。"""
    pid = proj.name
    errs: List[str] = []

    # 1) 文件齐全
    contents = {}
    for pat in REQUIRED:
        f = proj / pat.format(pid=pid)
        if not f.exists():
            errs.append(f"缺少文件 {f.name}")
            continue
        text = f.read_text(encoding="utf-8")
        if not text.strip():
            errs.append(f"文件为空 {f.name}")
        contents[f.name] = text

    if errs:
        return errs

    h = contents[f"{pid}.h"]
    cpp = contents[f"{pid}.cpp"]
    tb = contents[f"{pid}_tb.cpp"]

    # 2) 占位符残留
    for name, text in contents.items():
        if name == "question.txt":
            continue
        for m in _PLACEHOLDER.finditer(text):
            errs.append(f"{name} 存在未替换的占位符 {m.group(0)}")

    # 3) 括号配平
    for name in (f"{pid}.h", f"{pid}.cpp", f"{pid}_tb.cpp"):
        ok, msg = balanced(strip_code(contents[name]))
        if not ok:
            errs.append(f"{name} {msg}")

    # 4) 结构要求
    if "int main" not in tb:
        errs.append(f"{pid}_tb.cpp 中没有 int main")
    if f'#include "{pid}.h"' not in cpp:
        errs.append(f"{pid}.cpp 没有 include {pid}.h")
    if f'#include "{pid}.h"' not in tb:
        errs.append(f"{pid}_tb.cpp 没有 include {pid}.h")

    # 5) 宏保护
    guard = pid.upper() + "_H"
    if f"#ifndef {guard}" not in h or f"#define {guard}" not in h:
        errs.append(f"{pid}.h 缺少宏保护 {guard}")

    # 6) 宏定义齐全（全大写标识符必须被 #define 过）
    defined = {m.group(1) for m in _MACRO_DEF.finditer(h)}
    defined |= {m.group(1) for m in _MACRO_DEF.finditer(tb)}
    allowed = {"NULL", "EOF", "INT_MAX"}
    used = set()
    for name in (f"{pid}.h", f"{pid}.cpp", f"{pid}_tb.cpp"):
        used |= set(_ALLCAPS.findall(strip_code(contents[name])))
    undefined = used - defined - allowed - {guard}
    if undefined:
        errs.append(f"使用了未定义的宏: {', '.join(sorted(undefined))}")

    # 7) 顶层函数名
    if f"{pid}(" not in strip_code(cpp):
        errs.append(f"{pid}.cpp 中找不到顶层函数 {pid}(")

    return errs


def main(argv: List[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else "output")
    if not root.exists():
        print(f"[错误] 目录不存在: {root}")
        return 2

    projects = sorted(p for p in root.iterdir() if p.is_dir())
    if not projects:
        print(f"[错误] {root} 下没有题目工程目录")
        return 2

    total_errs = 0
    for proj in projects:
        errs = check_project(proj)
        if errs:
            total_errs += len(errs)
            print(f"[FAIL] {proj.name}")
            for e in errs:
                print(f"       - {e}")
        else:
            print(f"[ OK ] {proj.name}")

    print()
    print(f"共检查 {len(projects)} 个工程，问题数 {total_errs}")
    return 1 if total_errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
