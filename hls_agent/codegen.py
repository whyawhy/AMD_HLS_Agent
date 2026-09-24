"""C++ 代码生成器。

对每个识别出的题目输出一个自包含的 Vitis HLS 工程目录：

    <outdir>/<pid>/
        <pid>.h          顶层函数声明 + 常量 + 数据类型
        <pid>.cpp        顶层函数实现（综合入口）
        <pid>_tb.cpp     C 仿真 testbench（含 int main）
        run.tcl          Vitis HLS 批处理脚本
        question.txt     原始题目文本
        README.md        题目、参数、运行说明、优化建议
"""

from __future__ import annotations

import os
from pathlib import Path
from string import Template
from typing import Dict, List, Optional

from .knowledge_base import DEFAULT_CLOCK_NS, DEFAULT_PART, Problem
from .matcher import MatchResult, canonical_question, describe_params

# --------------------------------------------------------------------------
# 通用模板
# --------------------------------------------------------------------------

_HEADER_TPL = Template(
    """// ============================================================================
//  $name  ($pid)
//  由 hls_agent 自动生成 —— Vitis HLS 顶层函数
//
//  题目: $question
//  类型: $dtype
// ============================================================================
#ifndef $guard
#define $guard

$includes

typedef $dtype dtype_t;

$consts

// ---- 顶层函数原型 ----------------------------------------------------------
$proto

#endif // $guard
"""
)

_SOURCE_TPL = Template(
    """// ============================================================================
//  $name  ($pid) —— 顶层函数实现
//  由 hls_agent 自动生成
// ============================================================================
#include "$pid.h"

$source
"""
)

_TB_TPL = Template(
    """// ============================================================================
//  $name  ($pid) —— C 仿真 testbench
//  由 hls_agent 自动生成
//
//  说明: 本文件不参与综合，仅用于 Vitis HLS 的 csim_design / cosim_design。
// ============================================================================
#include <stdio.h>
#include <stdlib.h>
#include <math.h>

#include "$pid.h"

// 浮点比较容差；整数类型下等价于精确比较
#define TB_TOL 1e-3

static int g_err = 0;

static void tb_check(const char* what, double got, double exp) {
    if (fabs(got - exp) > TB_TOL) {
        printf("[FAIL] %s: got %.6f, expect %.6f\\n", what, got, exp);
        g_err++;
    }
}

$testbench
"""
)

_TCL_TPL = Template(
    """# ============================================================================
#  Vitis HLS 批处理脚本 —— $name ($pid)
#  由 hls_agent 自动生成
#
#  运行方式:
#      vitis_hls -f run.tcl
#  或在 Vitis HLS GUI 的 Tcl Console 中:
#      source run.tcl
# ============================================================================

open_project -reset proj_$pid
set_top $pid
add_files $pid.cpp
add_files -tb ${pid}_tb.cpp

open_solution -reset "solution1"
set_part {$part}
create_clock -period $clock -name default

# ---- C 仿真（功能验证，必须通过）----
csim_design

# ---- C 综合（生成 RTL 与资源/时序报告）----
# 取消下面一行的注释以启用
# csynth_design

# ---- C/RTL 协同仿真 ----
# cosim_design

exit
"""
)

_README_TPL = Template(
    """# $name

> 由 **hls_agent** 自动生成 —— HLS 硬件评估标准测试题

## 一、题目

$question

## 二、识别结果

| 项目 | 内容 |
| --- | --- |
| 题库编号 | `$pid` |
| 题目类型 | $name |
| 分类 | $category |
| 匹配得分 | $score |
| 命中关键词 | $hits |
| 抽取参数 | $params |
| 数据类型 | `$dtype` |

数据类型说明：$dtype_note

## 三、生成文件

| 文件 | 说明 |
| --- | --- |
| `$pid.h` | 常量、`dtype_t` 定义、顶层函数原型 |
| `$pid.cpp` | 顶层函数实现，**Vitis HLS 的综合入口** |
| `${pid}_tb.cpp` | C 仿真 testbench，含 `int main` |
| `run.tcl` | Vitis HLS 批处理脚本 |
| `question.txt` | 原始题目文本 |

## 四、运行方法

### 方式 1：Vitis HLS 命令行

```bash
vitis_hls -f run.tcl
```

### 方式 2：Vitis HLS GUI

1. `File > New Project`，工程名任意，器件选 `$part`
2. `Add Files` 加入 `$pid.cpp` 与 `$pid.h`
3. `Add Files` 时勾选 **Add as TestBench** 加入 `${pid}_tb.cpp`
4. 右键顶层函数 → `Set as Top`
5. `Solution > Run C Simulation` 验证功能
6. `Solution > Run C Synthesis` 查看资源与时序

### 方式 3：纯算法验证（无需 Vitis，用 g++ 快速自测）

```bash
g++ -O2 -o tb_test ${pid}.cpp ${pid}_tb.cpp -I. -lm && ./tb_test
```

成功时输出 `TEST PASSED`。

## 五、HLS 优化指令建议

$pragmas

## 六、验收要点

$notes

## 七、testbench 判据

- 浮点结果容差 `1e-3`，整数结果精确相等
- 全部通过输出 `TEST PASSED`，任一不符输出 `TEST FAILED: N mismatch(es)` 并返回 1
- 使用 cosim 时，testbench 必须自包含（不依赖文件 IO）
"""
)


# --------------------------------------------------------------------------
# 渲染
# --------------------------------------------------------------------------


def _build_context(res: MatchResult, question: str) -> Dict[str, str]:
    """把题目参数、类型、包含文件合并成统一模板上下文。"""
    p = res.problem
    ctx: Dict[str, str] = {}

    # 参数（含 derive 派生量）
    for k, v in res.params.items():
        ctx[k] = v

    ctx["pid"] = p.pid
    ctx["name"] = p.name
    ctx["category"] = p.category
    ctx["guard"] = p.guard
    ctx["dtype"] = res.dtype
    ctx["dtype_note"] = res.dtype_note
    ctx["question"] = question

    return ctx


def _render_includes(res: MatchResult) -> str:
    incs = list(res.problem.includes)
    # ap_* 头文件由 dtype 解析结果携带
    if res.dtype.startswith("ap_int<"):
        incs.append("ap_int.h")
    elif res.dtype.startswith("ap_fixed<"):
        incs.append("ap_fixed.h")

    seen, ordered = set(), []
    for i in incs:
        if i not in seen:
            seen.add(i)
            ordered.append(i)

    return "\n".join(f'#include "{i}"' for i in ordered)


def render_header(res: MatchResult, question: str) -> str:
    ctx = _build_context(res, question)
    ctx["includes"] = _render_includes(res)
    ctx["consts"] = Template(res.problem.consts).safe_substitute(ctx)
    ctx["proto"] = Template(res.problem.proto).safe_substitute(ctx)
    return _HEADER_TPL.safe_substitute(ctx)


def render_source(res: MatchResult, question: str) -> str:
    ctx = _build_context(res, question)
    ctx["source"] = Template(res.problem.source).safe_substitute(ctx)
    return _SOURCE_TPL.safe_substitute(ctx)


def render_testbench(res: MatchResult, question: str) -> str:
    ctx = _build_context(res, question)
    ctx["testbench"] = Template(res.problem.testbench).safe_substitute(ctx)
    return _TB_TPL.safe_substitute(ctx)


def render_tcl(res: MatchResult, part: str, clock_ns: float) -> str:
    ctx = {
        "pid": res.problem.pid,
        "name": res.problem.name,
        "part": part,
        "clock": clock_ns,
    }
    return _TCL_TPL.safe_substitute(ctx)


def render_readme(res: MatchResult, question: str, part: str) -> str:
    p = res.problem
    ctx = _build_context(res, question)
    ctx["score"] = res.score
    ctx["hits"] = ", ".join(res.hits) if res.hits else "(无)"
    ctx["params"] = describe_params(p, res.params)
    ctx["pragmas"] = f"```cpp\n{p.pragmas}\n```" if p.pragmas else "_(本题无特别建议)_"
    ctx["notes"] = p.notes or "功能与参考模型逐元素一致。"
    ctx["part"] = part
    return _README_TPL.safe_substitute(ctx)


# --------------------------------------------------------------------------
# 落盘
# --------------------------------------------------------------------------


def generate(
    res: MatchResult,
    question: str,
    outdir: str | os.PathLike[str],
    part: str = DEFAULT_PART,
    clock_ns: float = DEFAULT_CLOCK_NS,
    overwrite: bool = True,
) -> List[Path]:
    """生成一个完整的题目工程目录，返回写入的文件列表。"""
    pid = res.problem.pid
    target = Path(outdir) / pid
    target.mkdir(parents=True, exist_ok=True)

    files = {
        f"{pid}.h": render_header(res, question),
        f"{pid}.cpp": render_source(res, question),
        f"{pid}_tb.cpp": render_testbench(res, question),
        "run.tcl": render_tcl(res, part, clock_ns),
        "README.md": render_readme(res, question, part),
        "question.txt": question.strip() + "\n",
    }

    written: List[Path] = []
    for fname, content in files.items():
        path = target / fname
        if path.exists() and not overwrite:
            continue
        # 统一使用 LF，避免 Vitis HLS 在 Windows 上对 CRLF 的兼容问题
        path.write_text(content, encoding="utf-8", newline="\n")
        written.append(path)

    return written


def generate_index(results: List[tuple[MatchResult, str]], outdir: str | os.PathLike[str]) -> Optional[Path]:
    """当一个批次生成多道题时，在输出根目录写一个总览 README。"""
    if not results:
        return None

    lines = ["# HLS 测试题生成总览", ""]
    lines.append("| # | 题目类型 | 编号 | 参数 | 数据类型 | 目录 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")

    for i, (res, _q) in enumerate(results, 1):
        p = res.problem
        lines.append(
            f"| {i} | {p.name} | `{p.pid}` | {describe_params(p, res.params)} | "
            f"`{res.dtype}` | [{p.pid}/]({p.pid}/README.md) |"
        )

    lines.append("")
    lines.append("每道题在各自目录下都有独立的 `run.tcl`，可在该目录执行 `vitis_hls -f run.tcl`。")

    path = Path(outdir) / "README.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def preview(res: MatchResult, question: str) -> str:
    """在终端预览将要生成的代码（不落盘）。"""
    pid = res.problem.pid
    bar = "=" * 74
    parts = [
        bar,
        f"  {res.problem.name}  ({pid})",
        bar,
        f"  标准题目: {canonical_question(res.problem, res.params)}",
        f"  原始输入: {question.strip()}",
        f"  匹配得分: {res.score}   命中: {', '.join(res.hits) or '(无)'}",
        f"  参数: {describe_params(res.problem, res.params)}",
        f"  类型: {res.dtype}  ({res.dtype_note})",
        "",
        "-" * 74 + f"\n  {pid}.h\n" + "-" * 74,
        render_header(res, question),
        "-" * 74 + f"\n  {pid}.cpp\n" + "-" * 74,
        render_source(res, question),
        "-" * 74 + f"\n  {pid}_tb.cpp\n" + "-" * 74,
        render_testbench(res, question),
    ]
    return "\n".join(parts)
