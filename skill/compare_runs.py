#!/usr/bin/env python3
"""对比两轮评测（智能体 vs 裸跑基线），算出「增益」。

赛道评分里「相对同模型裸跑基线的提升」占 40 分，是权重最大的一项，
本脚本产出那份对比数据。

用法::

    python skill/compare_runs.py <智能体结果目录> <基线结果目录>
    python skill/compare_runs.py              # 自动取最近一轮 agent 与 baseline

输出 Markdown 对比表（整体 + 分变体），可直接贴进设计报告。
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _load(round_dir: Path) -> Tuple[dict, Dict[str, dict]]:
    data = json.loads((round_dir / "results.json").read_text(encoding="utf-8"))
    by_task: Dict[str, dict] = {}
    for r in data["records"]:
        # 同一题多次运行时取最好的一次
        old = by_task.get(r["task"])
        if old is None or (r["passed"] and not old["passed"]):
            by_task[r["task"]] = r
    return data, by_task


def _rate(by_task: Dict[str, dict]) -> Tuple[int, int]:
    n = len(by_task)
    ok = sum(1 for r in by_task.values() if r["passed"])
    return ok, n


def _by_variant(by_task: Dict[str, dict]) -> Dict[str, Tuple[int, int]]:
    out: Dict[str, List[int]] = defaultdict(lambda: [0, 0])
    for r in by_task.values():
        v = r["variant"] or "(未分组)"
        out[v][1] += 1
        if r["passed"]:
            out[v][0] += 1
    return {k: (v[0], v[1]) for k, v in out.items()}


def _task_set(d: Path) -> frozenset:
    """取一轮评测跑过的题目集合。"""
    try:
        data = json.loads((d / "results.json").read_text(encoding="utf-8"))
        return frozenset(data.get("tasks", []))
    except Exception:
        return frozenset()


def _auto_find(base: Path) -> Tuple[Optional[Path], Optional[Path]]:
    """找出最近的一对「题集完全相同」的 agent / baseline。

    只按时间取最近的两个是错的——如果一次是 122 题的全量、另一次是 1 题的
    试跑，比出来的数字毫无意义（题集不同，通过率不可比）。
    """
    rounds = sorted(base.glob("20*_*_k*"))
    agents = [d for d in reversed(rounds) if "_agent_" in d.name]
    baselines = [d for d in reversed(rounds) if "_baseline_" in d.name]

    for b in baselines:
        bt = _task_set(b)
        if not bt:
            continue
        for a in agents:
            if _task_set(a) == bt:
                return a, b
    return None, None


def compare(agent_dir: Path, base_dir: Path) -> str:
    a_data, a_tasks = _load(agent_dir)
    b_data, b_tasks = _load(base_dir)

    # 只比两次都跑过的题——题集不同时通过率不可直接比较
    a_set, b_set = set(a_tasks), set(b_tasks)
    common = a_set & b_set
    only_a, only_b = sorted(a_set - b_set), sorted(b_set - a_set)
    if common:
        a_tasks = {k: v for k, v in a_tasks.items() if k in common}
        b_tasks = {k: v for k, v in b_tasks.items() if k in common}

    a_ok, a_n = _rate(a_tasks)
    b_ok, b_n = _rate(b_tasks)

    L: List[str] = []
    L.append("# 智能体 vs 基线 对比（增益）")
    L.append("")
    L.append(f"- 智能体：`{agent_dir.name}`（{a_data.get('model')}，"
             f"重试上限 {a_data.get('attempts')}，技能包+工具反馈）")
    L.append(f"- 基线　：`{base_dir.name}`（同一模型，单次生成、不重试、不带技能包）")
    L.append(f"- 判定口径：{'官方（只认 csim 返回码）' if a_data.get('official_pass') else '严格（数值一致才算通过）'}")
    if only_a or only_b:
        L.append("")
        L.append(f"> ⚠️ 两次运行的题集不完全相同，**下面只比较共同跑过的 {len(common)} 道题**。")
        if only_a:
            L.append(f"> 仅智能体跑过：{len(only_a)} 道（{', '.join(only_a[:5])}"
                     f"{' …' if len(only_a) > 5 else ''}）")
        if only_b:
            L.append(f"> 仅基线跑过：{len(only_b)} 道（{', '.join(only_b[:5])}"
                     f"{' …' if len(only_b) > 5 else ''}）")
        L.append("> 要做正式对比，请用**同一批题**跑两种模式。")
    L.append("")

    L.append("## 总览")
    L.append("")
    L.append("| 指标 | 基线 | 智能体 | 增益 |")
    L.append("| --- | --- | --- | --- |")
    L.append(f"| 通过题目数 | {b_ok}/{b_n} | {a_ok}/{a_n} | {a_ok - b_ok:+d} |")
    br = b_ok / b_n if b_n else 0.0
    ar = a_ok / a_n if a_n else 0.0
    L.append(f"| pass@1 | {br:.1%} | {ar:.1%} | **{ar - br:+.1%}** |")
    rel = ((ar - br) / br * 100) if br > 0 else float("inf")
    L.append(f"| 相对提升 | — | — | {('—' if br == 0 else f'{rel:+.0f}%')} |")
    L.append("")

    # 墙钟对比
    a_wall = a_data.get("total_elapsed_s", 0.0)
    b_wall = b_data.get("total_elapsed_s", 0.0)
    L.append(f"- 总墙钟：基线 {b_wall:.0f}s，智能体 {a_wall:.0f}s")
    L.append("")

    # 分变体
    a_var = _by_variant(a_tasks)
    b_var = _by_variant(b_tasks)
    L.append("## 分变体对比")
    L.append("")
    L.append("| 变体 | 基线 | 智能体 | 增益 |")
    L.append("| --- | --- | --- | --- |")
    for v in sorted(set(a_var) | set(b_var)):
        bo, bn = b_var.get(v, (0, 0))
        ao, an = a_var.get(v, (0, 0))
        bs = f"{bo}/{bn} ({bo/bn:.0%})" if bn else "—"
        as_ = f"{ao}/{an} ({ao/an:.0%})" if an else "—"
        gain = f"{ao - bo:+d}" if bn and an else "—"
        L.append(f"| {v} | {bs} | {as_} | {gain} |")
    L.append("")

    # 智能体独有通过的题（增益的具体来源）
    only_agent = sorted(t for t in a_tasks if a_tasks[t]["passed"] and not b_tasks.get(t, {}).get("passed"))
    only_base = sorted(t for t in b_tasks if b_tasks[t]["passed"] and not a_tasks.get(t, {}).get("passed"))
    if only_agent:
        L.append("## 智能体比基线多做对的题")
        L.append("")
        L.append(f"共 {len(only_agent)} 道：")
        L.append("")
        for t in only_agent[:40]:
            r = a_tasks[t]
            L.append(f"- `{t}`（{r['variant']}，尝试 {r['attempts']} 次）")
        if len(only_agent) > 40:
            L.append(f"- …以及另外 {len(only_agent) - 40} 道")
        L.append("")
    if only_base:
        L.append("## 基线比智能体多做对的题（回归，需分析）")
        L.append("")
        for t in only_base[:20]:
            L.append(f"- `{t}`（{b_tasks[t]['variant']}）")
        L.append("")

    return "\n".join(L)


def main(argv: Optional[List[str]] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if argv and len(argv) >= 2:
        agent_dir, base_dir = Path(argv[0]), Path(argv[1])
    else:
        base = Path(__file__).resolve().parent.parent / "eval_results"
        agent_dir, base_dir = _auto_find(base)
        if not agent_dir or not base_dir:
            print("没找到可对比的两轮结果，请显式传入两个目录", file=sys.stderr)
            return 2

    print(f"智能体: {agent_dir}")
    print(f"基线  : {base_dir}")
    print()
    report = compare(agent_dir, base_dir)
    print(report)

    out = agent_dir / "gain_vs_baseline.md"
    out.write_text(report + "\n", encoding="utf-8")
    print(f"\n已保存: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
