#!/usr/bin/env python3
"""评测失败模式分析：把一轮评测的失败题按原因归类，提炼技能包素材。

用法::

    python skill/analyze_failures.py [eval_results/<时间戳>_<模式>_k<k>]

默认分析 eval_results 下最新一轮。输出 Markdown 汇总（可直接贴进设计报告
的「失败分析」小节），并把编译错误按模式归类：
漏 include / 签名不符 / 类型错误 / 语法错误 / 链接错误 / 其他。
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 编译错误分类规则
_ERROR_PATTERNS = [
    ("漏 include / 未声明", re.compile(r"no such file or directory|undeclared identifier|not declared|no member named", re.I)),
    ("签名不符", re.compile(r"no matching function|candidate function|argument of type|too few arguments|too many arguments", re.I)),
    ("类型/模板错误", re.compile(r"requires template arguments|no viable conversion|cannot convert|invalid operands|template argument", re.I)),
    ("语法错误", re.compile(r"expected .*;|expected .*\)|expected .*\{|unexpected token|expected unqualified-id", re.I)),
    ("重定义/冲突", re.compile(r"redefinition|previous definition|conflicts with|using declaration conflicts", re.I)),
    ("链接错误", re.compile(r"undefined reference|multiple definition", re.I)),
]

WARN_STRIP = re.compile(r"^\.\./\.\./\.\./\.\./[^:]+:\d+:\d+:\s*(?:warning|error):\s*")


def _classify_error(line: str) -> str:
    for name, pat in _ERROR_PATTERNS:
        if pat.search(line):
            return name
    return "其他"


def _task_errors(workdir: Path, task: str) -> List[str]:
    """从工作区的 Vitis 日志里提取编译错误（前 6 条，去重）。"""
    errors: List[str] = []
    seen = set()
    for log in workdir.glob("logs/*.log"):
        try:
            text = log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if ": error:" not in line and not line.startswith("ERROR:"):
                continue
            clean = WARN_STRIP.sub("", line).strip()
            if clean and clean not in seen:
                seen.add(clean)
                errors.append(clean)
    # 也看最后一次尝试的 attempt 文件是否存在（帮助判断失败阶段）
    return errors[:6]


def analyze(round_dir: Path, workspace: Path) -> str:
    data = json.loads((round_dir / "results.json").read_text(encoding="utf-8"))
    records = data["records"]
    failed = [r for r in records if not r["passed"]]

    if not failed:
        return "## 失败分析\n\n全部通过，无失败题目。\n"

    lines: List[str] = ["## 失败分析", ""]

    # 1. 失败阶段分布
    stage = Counter()
    for r in failed:
        if r["error"]:
            stage["生成/解析失败"] += 1
        elif r["compile"] is False:
            stage["编译失败"] += 1
        elif r["run"] is False:
            stage["仿真失败"] += 1
        elif r["dump_ok"] is False:
            stage["数值不符"] += 1
        else:
            stage["其他"] += 1

    lines.append(f"- 失败总数：{len(failed)} / {len(records)}")
    lines.append(f"- 按阶段：{'，'.join(f'{k} {v}' for k, v in stage.most_common())}")
    lines.append("")

    # 2. 按变体统计
    by_var: Dict[str, List[dict]] = defaultdict(list)
    for r in failed:
        by_var[r["variant"] or "(未分组)"].append(r)
    lines.append("| 变体 | 失败数 |")
    lines.append("| --- | --- |")
    for var, rs in sorted(by_var.items(), key=lambda x: -len(x[1])):
        lines.append(f"| {var} | {len(rs)} |")
    lines.append("")

    # 3. 逐题明细 + 编译错误归类
    error_class: Counter = Counter()
    lines.append("| 题目 | 变体 | 失败阶段 | 尝试 | 墙钟 | 错误归类 | 错误摘要 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for r in sorted(failed, key=lambda x: (x["variant"], x["task"])):
        wd = workspace / r["task"]
        errs = _task_errors(wd, r["task"])
        classes = [_classify_error(e) for e in errs]
        for c in classes:
            error_class[c] += 1
        cls = "、".join(dict.fromkeys(classes)) or "-"
        if r["error"]:
            summary = r["error"][:60].replace("|", "/")
        elif r["dump_detail"]:
            summary = r["dump_detail"][:60].replace("|", "/")
        elif errs:
            summary = errs[0][:60].replace("|", "/")
        else:
            summary = "-"
        stage_of = (
            "生成失败" if r["error"] else
            "编译失败" if r["compile"] is False else
            "仿真失败" if r["run"] is False else
            "数值不符" if not r["dump_ok"] else "其他"
        )
        lines.append(
            f"| {r['task']} | {r['variant']} | {stage_of} | {r['attempts']} | "
            f"{r['elapsed_s']:.0f}s | {cls} | {summary} |"
        )
    lines.append("")

    # 4. 错误模式汇总
    lines.append("### 编译错误模式分布")
    lines.append("")
    for name, cnt in error_class.most_common():
        lines.append(f"- {name}：{cnt}")
    lines.append("")

    # 5. 技能包建议（供人工提炼）
    lines.append("### 技能包提炼建议")
    lines.append("")
    top = error_class.most_common(3)
    for name, cnt in top:
        if name == "漏 include / 未声明":
            lines.append("- 「漏 include / 未声明」高发：检查静态预检是否覆盖了对应的 include 模式；")
            lines.append("  考虑在提示词里补充「头文件必须 #include」的强调。")
        elif name == "签名不符":
            lines.append("- 「签名不符」高发：检查题面解析出的签名是否与头文件一致；")
            lines.append("  考虑把「逐字匹配签名」从提示词里再提前、加重。")
        elif name == "类型/模板错误":
            lines.append("- 「类型/模板错误」高发：多为 ap_fixed 模板参数漏写或 typedef 不一致；")
            lines.append("  考虑在技能包提示词里加「typedef 必须带模板参数」的规则。")
        elif name == "语法错误":
            lines.append("- 「语法错误」高发：多为 XML 转义残留或其他抽取问题；")
            lines.append("  检查抽取路径是否还有未还原的转义字符。")
    lines.append("")

    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    root = Path(argv[0]) if argv else None
    if root is None:
        base = Path(__file__).resolve().parent.parent / "eval_results"
        rounds = sorted(base.glob("20*_*_k*"))
        if not rounds:
            print("没有找到评测结果目录", file=sys.stderr)
            return 2
        root = rounds[-1]

    workspace = Path("D:/hls_work")
    report = analyze(root, workspace)
    print(report)
    out = root / "failure_analysis.md"
    out.write_text(report + "\n", encoding="utf-8")
    print(f"\n已保存: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
