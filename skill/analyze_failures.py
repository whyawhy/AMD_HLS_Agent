#!/usr/bin/env python3
"""评测失败模式分析：把一轮评测的失败题按原因归类，提炼技能包素材。

用法::

    python skill/analyze_failures.py [eval_results/<时间戳>_<模式>_k<k>]

默认分析 eval_results 下最新一轮。输出 Markdown 汇总（可直接贴进设计报告
的「失败分析」小节），并把编译错误按模式归类：
漏 include / 签名不符 / 类型错误 / 语法错误 / 链接错误 / 其他。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hls_agent.errors import describe as err_desc, hint as err_hint, is_retryable  # noqa: E402

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


def _legacy_stage(r: dict) -> str:
    """老结果文件没有 failure_kind 字段时的粗分类（仅向后兼容用）。"""
    if r.get("error"):
        return "OUTPUT_FORMAT_ERROR"
    if r.get("compile") is False:
        return "CXX_COMPILE_ERROR"
    if r.get("run") is False:
        return "CSIM_RUNTIME_ERROR"
    if not r.get("dump_ok", True):
        return "TEST_MISMATCH"
    return "UNKNOWN_ERROR"


def analyze(round_dir: Path, workspace: Path) -> str:
    data = json.loads((round_dir / "results.json").read_text(encoding="utf-8"))
    records = data["records"]
    failed = [r for r in records if not r["passed"]]

    lines: List[str] = ["## 失败分析", ""]
    lines.append(f"- 评测目录：`{round_dir.name}`")
    lines.append(
        f"- 模式：{data.get('mode')}　模型：`{data.get('model')}`　"
        f"题数：{len({r['task'] for r in records})}　采样轮数 k={data.get('k')}"
    )
    lines.append(
        f"- 判定口径："
        f"{'官方（只认 csim 返回码）' if data.get('official_pass') else '严格（数值与参考 dump 一致）'}"
    )
    lines.append("")

    if not failed:
        lines.append("全部通过，无失败题目。")
        return "\n".join(lines) + "\n"

    # 1. 结构化失败类别。老结果文件没有该字段时退回到阶段推断。
    has_kind = any(r.get("failure_kind") for r in records)
    kind_count: Counter = Counter()
    for r in failed:
        kind_count[r.get("failure_kind") or _legacy_stage(r)] += 1

    lines.append(f"- 失败总数：{len(failed)} / {len(records)}")
    lines.append("")

    if has_kind:
        lines.append("### 失败类别分布")
        lines.append("")
        lines.append("| 类别 | 中文 | 题数 | 是否值得重试 | 修复方向 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for kind, cnt in kind_count.most_common():
            lines.append(
                f"| `{kind}` | {err_desc(kind)} | {cnt} | "
                f"{'是' if is_retryable(kind) else '否'} | {err_hint(kind)} |"
            )
        lines.append("")
    else:
        lines.append(
            "- 按阶段（旧结果文件，无 failure_kind 字段）："
            + "，".join(f"{k} {v}" for k, v in kind_count.most_common())
        )
        lines.append("")
        lines.append(
            "> 该批 results.json 生成于引入结构化失败分类之前，只能按阶段粗分。"
            "用新版 `eval.py` 重跑即可得到逐题的失败类别与每次尝试的经过。"
        )
        lines.append("")

    # 2. 同一个根因反复出现——这类才是"技能包该补的洞"
    lines.append("### 重复根因（同一类别命中 ≥2 题，优先补技能包）")
    lines.append("")
    repeated = [(k, v) for k, v in kind_count.most_common() if v >= 2]
    if repeated:
        lines.append("| 类别 | 命中题数 | 涉及题目 |")
        lines.append("| --- | --- | --- |")
        for kind, cnt in repeated:
            tasks = sorted(
                r["task"] for r in failed
                if (r.get("failure_kind") or _legacy_stage(r)) == kind
            )
            lines.append(
                f"| `{kind}` | {cnt} | {', '.join(tasks[:8])}{' …' if len(tasks) > 8 else ''} |"
            )
    else:
        lines.append("无——失败原因分散，暂不需要新增全局规则。")
    lines.append("")

    # 3. 重试有效性
    att = Counter(r["attempts"] for r in failed)
    lines.append("### 重试次数分布（失败题）")
    lines.append("")
    lines.append("| 尝试次数 | 题数 |")
    lines.append("| --- | --- |")
    for n, c in sorted(att.items()):
        lines.append(f"| {n} | {c} |")
    lines.append("")
    one_shot = att.get(1, 0)
    if one_shot:
        lines.append(
            f"- 有 {one_shot} 道题只试了 1 次就停。agent 模式下这通常意味着"
            f"静态预检直接阻断、或判成了环境硬限制（如测试台调用数学库）。"
            f"若它们本该重试，去看这几题的 `failure_kind`。"
        )
        lines.append("")

    # 4. 分变体的通过率与耗时（只看总体会掩盖局部退步）
    by_var: Dict[str, List[dict]] = defaultdict(list)
    for r in records:
        by_var[r["variant"] or "(未分组)"].append(r)
    lines.append("### 分变体通过率与耗时")
    lines.append("")
    lines.append("| 变体 | 题数 | 通过 | 通过率 | 平均墙钟 | 平均生成耗时 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for var, rs in sorted(by_var.items()):
        n = len(rs)
        ok = sum(1 for r in rs if r["passed"])
        mean_t = sum(r["elapsed_s"] for r in rs) / n
        mean_g = sum(r.get("gen_time_s") or 0 for r in rs) / n
        lines.append(f"| {var} | {n} | {ok} | {ok/n:.0%} | {mean_t:.1f}s | {mean_g:.1f}s |")
    lines.append("")

    # 5. 逐题明细（带每次尝试的经过）
    error_class: Counter = Counter()
    lines.append("### 逐题明细")
    lines.append("")
    lines.append("| 题目 | 变体 | 失败类别 | 尝试 | 每次尝试卡在哪 | 墙钟 | 日志错误归类 | 摘要 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in sorted(failed, key=lambda x: (x["variant"], x["task"])):
        errs = _task_errors(workspace / r["task"], r["task"])
        classes = [_classify_error(e) for e in errs]
        for c in classes:
            error_class[c] += 1
        cls = "、".join(dict.fromkeys(classes)) or "-"
        seq = " → ".join(r.get("failure_sequence") or []) or "-"
        kind = r.get("failure_kind") or _legacy_stage(r)
        summary = r.get("failure_detail") or r.get("dump_detail") or r.get("error") or "-"
        summary = re.sub(r"\s+", " ", summary)[:90].replace("|", "/")
        lines.append(
            f"| {r['task']} | {r['variant']} | `{kind}` | {r['attempts']} | {seq} | "
            f"{r['elapsed_s']:.0f}s | {cls} | {summary} |"
        )
    lines.append("")

    if error_class:
        lines.append("### 工作区日志里的编译错误模式（补充信号）")
        lines.append("")
        for name, cnt in error_class.most_common():
            lines.append(f"- {name}：{cnt}")
        lines.append("")

    lines.append("### 技能包提炼流程（走完才算一条规则）")
    lines.append("")
    lines.append("失败案例 → 根因分析 → 形成候选规则 → 针对性回归测试 → 记录效果 → 纳入技能包")
    lines.append("")
    lines.append("对应到本仓库：")
    lines.append("")
    lines.append("1. 从上面的「重复根因」里挑命中题数最多的类别；")
    lines.append("2. 打开 `eval_results/<批>/results.json` 看该题的 `failure_detail`；")
    lines.append("3. 候选规则先写进 `skill/pitfalls.md`，**标注适用范围**（哪类题、哪种数值类型）；")
    lines.append("4. 在 `selftest.py` 里补一条对应用例；")
    lines.append("5. 用同一题目集重跑，**分变体**比较通过率，避免总体数字掩盖局部退步；")
    lines.append("6. 效果记录留档后，再决定是否进提示词。")
    lines.append("")

    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(
        description="某一批评测的失败模式分析",
        epilog="不指定目录时分析 eval_results 下最新的一批",
    )
    ap.add_argument("round_dir", nargs="?",
                    help="eval_results/<时间戳>_<模式>_k<k>")
    ap.add_argument("--workspace", default=None,
                    help="Vitis 工作区（默认按 config.resolve_workspace 推断，"
                         "用于补充读取日志里的编译错误）")
    args = ap.parse_args(argv if argv is not None else sys.argv[1:])

    root = Path(args.round_dir) if args.round_dir else None
    if root is None:
        base = Path(__file__).resolve().parent.parent / "eval_results"
        # 只挑 eval_results 直属的时间戳目录，跳过 _repro / _after 这类临时目录
        rounds = sorted(p for p in base.glob("20*_*_k*") if (p / "results.json").is_file())
        if not rounds:
            print("没有找到评测结果目录", file=sys.stderr)
            return 2
        root = rounds[-1]

    if not (root / "results.json").is_file():
        print(f"[错误] {root} 下没有 results.json", file=sys.stderr)
        return 2

    if args.workspace:
        workspace = Path(args.workspace)
    else:
        try:
            from hls_agent.config import resolve_workspace
            workspace = resolve_workspace(None)
        except Exception:
            workspace = Path("hls_work")

    report = analyze(root, workspace)
    print(report)
    out = root / "failure_analysis.md"
    out.write_text(report + "\n", encoding="utf-8")
    print(f"\n已保存: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
