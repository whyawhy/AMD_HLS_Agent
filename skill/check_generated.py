#!/usr/bin/env python3
"""生成代码的静态预检（花 Vitis 时间之前先跑一遍）。

Vitis 一次 csim 要 20~30 秒，csynth 要 1~2 分钟。有些问题不用编译就能发现，
先静态查一遍能省下大量等待。

检查项：
  1. 是否 include 了题目给定的头文件
  2. 顶层函数是否被定义，且参数个数/类型与给定签名一致
  3. 是否出现 HLS 不可综合的写法（printf / 动态内存 / 递归 / 变长数组）
  4. 是否含顶层函数名（防止模型写了别的函数名）

用法::

    python skill/check_generated.py <生成的.cpp> --header <给定的.h> --top <函数名>

退出码 0 = 无阻断问题；1 = 有问题。
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

# --------------------------------------------------------------------------
# 静态规则
# --------------------------------------------------------------------------

# 这些写法在 HLS 里不可综合或会拖慢综合，属于"必须修"或"建议修"
BLOCKERS = [
    (re.compile(r"\bprintf\s*\("), "使用了 printf（HLS 不可综合，需去掉）"),
    (re.compile(r"\b(sprintf|fprintf|scanf)\s*\("), "使用了格式化 IO（HLS 不可综合）"),
    (re.compile(r"\bnew\s+\w"), "使用了 new（HLS 不支持动态内存）"),
    (re.compile(r"\bmalloc\s*\("), "使用了 malloc（HLS 不支持动态内存）"),
    (re.compile(r"\bfree\s*\("), "使用了 free（HLS 不支持动态内存）"),
    (re.compile(r"#include\s*<stdio\.h>"), "包含了 <stdio.h>（顶层函数不应做 IO）"),
    (re.compile(r"#include\s*<iostream>"), "包含了 <iostream>（HLS 不可综合）"),
]

WARNINGS = [
    (re.compile(r"\bfloat\b(?!\s*[)\w])"), "出现 float，确认是否应为定点/双精度"),
    (re.compile(r"\bdouble\b"), "出现 double，确认是否应为定点类型"),
    (re.compile(r"\bwhile\s*\(\s*1\s*\)"), "出现 while(1)，HLS 中可能无法收敛"),
    (re.compile(r"#pragma\s+HLS\s+inline", re.IGNORECASE), "顶层函数上的 #pragma HLS inline 通常无意义"),
]

_FUNC_DEF = re.compile(
    r"([A-Za-z_][\w:<>,\s\*&]*?)\s+([A-Za-z_]\w*)\s*\(([^;{]*?)\)\s*\{",
    re.DOTALL,
)


def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.DOTALL)
    src = re.sub(r"//[^\n]*", " ", src)
    return src


def parse_signature(header_src: str, top: str) -> Optional[List[str]]:
    """从给定头文件里取出顶层函数的参数列表（按逗号切分，规范化空白）。"""
    body = _strip_comments(header_src)
    m = re.search(rf"\b{re.escape(top)}\s*\(([^;]*?)\)\s*;", body, re.DOTALL)
    if not m:
        return None
    params = [p.strip() for p in m.group(1).split(",")]
    return [re.sub(r"\s+", " ", p) for p in params if p.strip()]


def parse_definition(src: str, top: str) -> Optional[List[str]]:
    """从生成的实现里取出该函数的参数列表。"""
    body = _strip_comments(src)
    for m in _FUNC_DEF.finditer(body):
        if m.group(2) == top:
            params = [p.strip() for p in m.group(3).split(",")]
            return [re.sub(r"\s+", " ", p) for p in params if p.strip()]
    return None


def _param_shape(p: str) -> str:
    """把参数归一化成「类型骨架」：去掉参数名，保留类型与数组维度。

    例：'t_ap_fixed A[ 40 + 0][60 + 0]' -> 't_ap_fixed[][]'
        'bits64 *z0Ptr'                 -> 'bits64*'
        'double m1[4096]'               -> 'double[]'
    """
    p = p.replace("const", " ").strip()
    p = re.sub(r"\[[^\]]*\]", "[]", p)          # 维度归一
    brackets = p.count("[]")
    body = p.replace("[]", "").strip()

    # body 形如 "类型 [*&] 参数名"，去掉最后的参数名，保留指针/引用标记
    m = re.match(r"^(.*?)([\s\*&]*)([A-Za-z_]\w*)$", body)
    if m and m.group(1).strip():
        body = m.group(1) + m.group(2)

    return re.sub(r"\s+", "", body) + "[]" * brackets


@dataclass
class CheckResult:
    blockers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blockers

    def render(self) -> str:
        L = []
        for b in self.blockers:
            L.append(f"  [阻断] {b}")
        for w in self.warnings:
            L.append(f"  [警告] {w}")
        for i in self.info:
            L.append(f"  [信息] {i}")
        if not L:
            L.append("  [通过] 未发现静态问题")
        return "\n".join(L)


def check(source_path: Path, header_path: Optional[Path], top: str) -> CheckResult:
    src = source_path.read_text(encoding="utf-8", errors="replace")
    code = _strip_comments(src)
    res = CheckResult()

    # 1. include 头文件
    if header_path is not None:
        if f'#include "{header_path.name}"' not in src:
            res.blockers.append(f"没有 #include \"{header_path.name}\"，编译会找不到声明")

    # 2. 顶层函数存在
    if not re.search(rf"\b{re.escape(top)}\s*\(", code):
        res.blockers.append(f"找不到顶层函数 {top}")
        return res

    # 3. 参数列表一致性
    if header_path is not None:
        want = parse_signature(header_path.read_text(encoding="utf-8", errors="replace"), top)
        got = parse_definition(src, top)
        if want and got:
            if len(want) != len(got):
                res.blockers.append(
                    f"参数个数不一致：头文件 {len(want)} 个，实现 {len(got)} 个"
                )
            else:
                for i, (a, b) in enumerate(zip(want, got)):
                    if _param_shape(a) != _param_shape(b):
                        res.warnings.append(
                            f"第 {i+1} 个参数类型可能不一致：期望 `{a}`，实现 `{b}`"
                        )
                res.info.append(f"参数个数一致（{len(want)} 个）")

    # 4. 不可综合写法
    for pat, msg in BLOCKERS:
        if pat.search(code):
            res.blockers.append(msg)
    for pat, msg in WARNINGS:
        if pat.search(code):
            res.warnings.append(msg)

    return res


def main(argv: Optional[List[str]] = None) -> int:
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
