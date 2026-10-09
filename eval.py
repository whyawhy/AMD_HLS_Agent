#!/usr/bin/env python3
"""批量评测：pass@k 统计、分组通过率、墙钟效率，结果落盘。

赛道要求同时报告 **pass@1 与 pass@5**，并给出相对基线的增益，所以本脚本把
每次运行的结果全部记下来，最后统一算：

    pass@1 = 首轮成功的题目占比
    pass@k = k 轮里至少成功一次的题目占比

用法::

    # 基线（单次生成、不重试、不看工具反馈）
    python eval.py --variant polybench --max 28 --k 1 --mode baseline

    # 智能体（带工具反馈与重试）
    python eval.py --variant polybench --max 28 --k 5 --mode agent --attempts 3

    # 指定题目
    python eval.py --tasks 2mm,3mm,atax --k 3 --mode agent

结果写到 ``eval_results/<时间戳>_<模式>_k<k>/``：
    results.json   逐次运行的完整记录
    summary.md     人读的汇总表（可直接贴进设计报告）
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hls_agent import dataset as ds  # noqa: E402
from hls_agent.config import (  # noqa: E402
    DEFAULT_CLOCK_NS,
    DEFAULT_PART,
    AgentConfig,
    LLMConfig,
    WorkspaceError,
    find_vitis_run,
    resolve_workspace,
)
from hls_agent.runner import run_task  # noqa: E402
from hls_agent.vitis import Grade  # noqa: E402

SEP = "=" * 78


# --------------------------------------------------------------------------
# 记录模型
# --------------------------------------------------------------------------


@dataclass
class RunRecord:
    task: str
    variant: str
    run_index: int
    passed: bool
    parse: Optional[bool]
    compile: Optional[bool]
    run: Optional[bool]
    synth: Optional[bool]
    dump_ok: bool
    dump_detail: str = ""
    attempts: int = 0
    elapsed_s: float = 0.0
    gen_time_s: float = 0.0
    error: str = ""

    @property
    def level(self) -> str:
        g = Grade(parse=self.parse, compile=self.compile, run=self.run, synth=self.synth)
        return g.highest


@dataclass
class EvalReport:
    mode: str
    k: int
    attempts: int
    do_synth: bool
    official_pass: bool = False
    model: str = ""
    backend: str = ""
    part: str = ""
    clock_ns: float = 0.0
    tasks: List[str] = field(default_factory=list)
    records: List[RunRecord] = field(default_factory=list)
    started_at: str = ""
    total_elapsed_s: float = 0.0

    # ---- 统计 --------------------------------------------------------
    def by_task(self) -> Dict[str, List[RunRecord]]:
        out: Dict[str, List[RunRecord]] = {}
        for r in self.records:
            out.setdefault(r.task, []).append(r)
        return out

    @property
    def pass_at_1(self) -> float:
        """首轮成功的题目占比。"""
        groups = self.by_task()
        if not groups:
            return 0.0
        ok = sum(1 for rs in groups.values() if any(r.passed for r in rs if r.run_index == 1))
        return ok / len(groups)

    @property
    def pass_at_k(self) -> float:
        """k 轮里至少成功一次的题目占比。"""
        groups = self.by_task()
        if not groups:
            return 0.0
        ok = sum(1 for rs in groups.values() if any(r.passed for r in rs))
        return ok / len(groups)

    @property
    def sample_rate(self) -> float:
        """全部采样里的成功比例（更细粒度的稳定性指标）。"""
        if not self.records:
            return 0.0
        return sum(1 for r in self.records if r.passed) / len(self.records)

    def by_variant(self) -> Dict[str, tuple[int, int, int]]:
        """变体 -> (题目数, pass@1 命中数, pass@k 命中数)。"""
        out: Dict[str, tuple[int, int, int]] = {}
        for name, rs in self.by_task().items():
            variant = rs[0].variant or "(未分组)"
            n, p1, pk = out.get(variant, (0, 0, 0))
            out[variant] = (
                n + 1,
                p1 + (1 if any(r.passed for r in rs if r.run_index == 1) else 0),
                pk + (1 if any(r.passed for r in rs) else 0),
            )
        return out

    def level_counts(self) -> Dict[str, int]:
        """各题达到的最高级别分布（取该题最好的一次）。"""
        out: Dict[str, int] = {}
        best_order = ["未开始", "可解析", "可编译", "可运行", "可综合"]
        for rs in self.by_task().values():
            best = max(rs, key=lambda r: best_order.index(r.level)).level
            out[best] = out.get(best, 0) + 1
        return out

    def wall_clock(self) -> Dict[str, float]:
        if not self.records:
            return {"total": 0.0, "mean": 0.0, "median": 0.0, "max": 0.0}
        vals = [r.elapsed_s for r in self.records]
        return {
            "total": self.total_elapsed_s,
            "mean": statistics.mean(vals),
            "median": statistics.median(vals),
            "max": max(vals),
        }


# --------------------------------------------------------------------------
# 执行
# --------------------------------------------------------------------------


def _cfg(args: argparse.Namespace) -> AgentConfig:
    try:
        ws = resolve_workspace(args.workspace)
    except WorkspaceError as e:
        print(f"[错误] {e}", file=sys.stderr)
        raise SystemExit(2)
    return AgentConfig(
        part=args.part or DEFAULT_PART,
        clock_ns=DEFAULT_CLOCK_NS if args.clock is None else args.clock,
        workspace=ws,
        vitis_run=find_vitis_run(args.vitis),
        csim_timeout_s=args.csim_timeout,
        csynth_timeout_s=args.synth_timeout,
        verbose=False,
        strict_dump=not args.official_pass,
        llm=LLMConfig.from_env(),
    )


def _select_tasks(d: ds.HlsEvalDataset, args: argparse.Namespace) -> List[ds.Task]:
    all_tasks = d.tasks()
    if args.tasks:
        wanted = [t.strip() for t in args.tasks.split(",") if t.strip()]
        picked = []
        for w in wanted:
            picked.append(d.get(w))
        return picked
    if args.variant:
        all_tasks = [t for t in all_tasks if args.variant.lower() in t.variant.lower()]
    if args.max:
        all_tasks = all_tasks[: args.max]
    return all_tasks


def evaluate(tasks: List[ds.Task], cfg: AgentConfig, args: argparse.Namespace) -> EvalReport:
    rep = EvalReport(
        mode=args.mode,
        k=args.k,
        attempts=1 if args.mode == "baseline" else max(1, args.attempts),
        do_synth=args.synth,
        official_pass=args.official_pass,
        model=cfg.llm.model,
        backend=cfg.llm.backend,
        part=cfg.part,
        clock_ns=cfg.clock_ns,
        tasks=[t.name for t in tasks],
        started_at=time.strftime("%Y-%m-%d %H:%M:%S"),
    )

    t_all = time.time()
    total_runs = len(tasks) * args.k
    budget = args.max_total_time if args.max_total_time > 0 else None

    for ti, task in enumerate(tasks, 1):
        for k in range(1, args.k + 1):
            idx = (ti - 1) * args.k + k
            # 总时间预算：超时后剩余题目记为跳过，不再消耗模型额度和 Vitis 时间
            if budget is not None and (time.time() - t_all) > budget:
                print(f"  [跳过] 超出总时间预算（{budget}s），剩余 {total_runs - idx + 1} 次运行未执行", flush=True)
                rec = RunRecord(
                    task=task.name, variant=task.variant, run_index=k,
                    passed=False, parse=None, compile=None, run=None, synth=None,
                    dump_ok=False, attempts=0, elapsed_s=0.0, gen_time_s=0.0,
                    error=f"跳过（超出总时间预算 {budget}s）",
                )
                rep.records.append(rec)
                continue
            print(f"  [{idx}/{total_runs}] {task.name}  第 {k}/{args.k} 轮 ...", flush=True)
            try:
                r = run_task(
                    task=task,
                    cfg=cfg,
                    client=None,
                    max_attempts=rep.attempts,
                    do_synth=args.synth,
                    mode=args.mode,
                    verbose=False,
                )
                g = r.grade
                rec = RunRecord(
                    task=task.name,
                    variant=task.variant,
                    run_index=k,
                    passed=r.passed,
                    parse=g.parse,
                    compile=g.compile,
                    run=g.run,
                    synth=g.synth,
                    dump_ok=r.dump_ok,
                    dump_detail=r.dump_detail,
                    attempts=len(r.attempts),
                    elapsed_s=r.elapsed_s,
                    gen_time_s=r.gen_time_s,
                )
                print(
                    f"          {'通过' if r.passed else '失败'}   "
                    f"{g.as_row()}   {r.elapsed_s:.1f}s",
                    flush=True,
                )
            except Exception as e:
                rec = RunRecord(
                    task=task.name,
                    variant=task.variant,
                    run_index=k,
                    passed=False,
                    parse=None, compile=None, run=None, synth=None,
                    dump_ok=False, attempts=0, elapsed_s=0.0, gen_time_s=0.0,
                    error=f"{type(e).__name__}: {e}",
                )
                print(f"          异常: {rec.error[:120]}", flush=True)
            rep.records.append(rec)

    rep.total_elapsed_s = time.time() - t_all
    return rep


# --------------------------------------------------------------------------
# 输出
# --------------------------------------------------------------------------


def render_summary(rep: EvalReport) -> str:
    L: List[str] = []
    L.append("# HLS Agent 评测结果")
    L.append("")
    L.append(f"- 时间：{rep.started_at}")
    L.append(f"- 模式：**{rep.mode}**（{'单次生成、不重试、不看工具反馈' if rep.mode == 'baseline' else f'带工具反馈，失败重试至多 {rep.attempts} 次'}）")
    L.append(f"- 采样轮数 k：{rep.k}")
    L.append(f"- 是否评估综合：{'是' if rep.do_synth else '否'}")
    L.append(
        f"- 判定口径：{'官方（只认 csim 返回码）' if rep.official_pass else '严格（数值与参考 dump 一致才算通过）'}"
    )
    L.append(f"- 模型：`{rep.model}`（backend={rep.backend}）")
    L.append(f"- 器件：`{rep.part}`，时钟 {rep.clock_ns:g} ns")
    L.append(f"- 题目数：{len(rep.tasks)}")
    L.append("")

    L.append("## 核心指标")
    L.append("")
    L.append("| 指标 | 数值 |")
    L.append("| --- | --- |")
    L.append(f"| pass@1 | **{rep.pass_at_1:.1%}** |")
    if rep.k > 1:
        # k=1 时 pass@k 与 pass@1 恒等，不重复展示
        L.append(f"| pass@{rep.k} | **{rep.pass_at_k:.1%}** |")
        L.append(f"| 稳定性差值 (pass@{rep.k} − pass@1) | {rep.pass_at_k - rep.pass_at_1:+.1%} |")
        L.append(f"| 单次采样成功率 | {rep.sample_rate:.1%} |")
    wc = rep.wall_clock()
    L.append(f"| 总墙钟 | {wc['total']:.1f} s |")
    L.append(f"| 单次平均墙钟 | {wc['mean']:.1f} s |")
    L.append(f"| 单次最长墙钟 | {wc['max']:.1f} s |")
    L.append("")

    L.append("## 分级判定分布")
    L.append("")
    L.append("| 最高级别 | 题目数 |")
    L.append("| --- | --- |")
    for lv in ["可综合", "可运行", "可编译", "可解析", "未开始"]:
        c = rep.level_counts().get(lv, 0)
        if c:
            L.append(f"| {lv} | {c} |")
    L.append("")

    L.append("## 分组通过率")
    L.append("")
    if rep.k > 1:
        L.append(f"| 变体 | 题目数 | pass@1 | pass@{rep.k} |")
        L.append("| --- | --- | --- | --- |")
        for variant, (n, p1, pk) in sorted(rep.by_variant().items()):
            L.append(f"| {variant} | {n} | {p1}/{n} ({p1/n:.1%}) | {pk}/{n} ({pk/n:.1%}) |")
    else:
        L.append("| 变体 | 题目数 | pass@1 |")
        L.append("| --- | --- | --- |")
        for variant, (n, p1, _pk) in sorted(rep.by_variant().items()):
            L.append(f"| {variant} | {n} | {p1}/{n} ({p1/n:.1%}) |")
    L.append("")

    L.append("## 逐题明细")
    L.append("")
    header = "| 题目 | 变体 | " + " | ".join(f"第{i}轮" for i in range(1, rep.k + 1)) + " | 最好级别 | 平均墙钟 |"
    L.append(header)
    L.append("| --- | --- |" + " --- |" * rep.k + " --- | --- |")
    for name, rs in sorted(rep.by_task().items()):
        cells = []
        for i in range(1, rep.k + 1):
            match = [r for r in rs if r.run_index == i]
            cells.append("通过" if (match and match[0].passed) else "失败")
        best_order = ["未开始", "可解析", "可编译", "可运行", "可综合"]
        best = max(rs, key=lambda r: best_order.index(r.level)).level
        mean_t = statistics.mean(r.elapsed_s for r in rs)
        L.append(
            f"| {name} | {rs[0].variant} | " + " | ".join(cells)
            + f" | {best} | {mean_t:.1f}s |"
        )
    L.append("")

    fails = [r for r in rep.records if not r.passed]
    if fails:
        L.append("## 失败分析")
        L.append("")
        L.append("| 题目 | 轮次 | 卡在哪一级 | 原因摘要 |")
        L.append("| --- | --- | --- | --- |")
        seen = set()
        for r in fails:
            key = (r.task, r.level)
            if key in seen:
                continue
            seen.add(key)
            reason = r.error[:120] if r.error else "编译/仿真未通过，详见 results.json"
            L.append(f"| {r.task} | {r.run_index} | {r.level} | {reason} |")
        L.append("")

    return "\n".join(L)


def save_report(rep: EvalReport, outdir: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "results.json").write_text(
        json.dumps(asdict(rep), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md = render_summary(rep)
    (outdir / "summary.md").write_text(md, encoding="utf-8")
    return outdir


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="eval",
        description="HLS-Eval 批量评测：pass@k、分组通过率、墙钟效率",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  python eval.py --variant polybench --max 5 --k 1 --mode baseline
  python eval.py --variant polybench --max 5 --k 5 --mode agent --attempts 3
  python eval.py --tasks 2mm,3mm --k 3 --mode agent --synth
""",
    )
    p.add_argument("--dataset", help="HLS-Eval 数据集目录（默认自动查找）")
    p.add_argument("--variant", help="只跑某个变体，如 polybench / chstone")
    p.add_argument("--tasks", help="逗号分隔的题目名，优先级高于 --variant")
    p.add_argument("--max", type=int, default=0, help="限制题目数量")
    p.add_argument("--k", type=int, default=1, help="每题的采样轮数（pass@k 的 k）")
    p.add_argument("--attempts", type=int, default=3, help="agent 模式下每题每轮的重试上限")
    p.add_argument(
        "--mode", choices=["agent", "baseline"], default="agent",
        help="agent=带工具反馈与重试；baseline=单次生成不重试",
    )
    p.add_argument("--synth", action="store_true", help="额外跑 csynth（评估可综合）")
    p.add_argument(
        "--official-pass", action="store_true",
        help="官方口径：只认 csim 返回码，不比数值（默认严格判定，数值一致才算过）",
    )
    p.add_argument("--outdir", default="eval_results", help="结果输出根目录")
    p.add_argument("--workspace", help="Vitis 工作区（纯 ASCII 路径）")
    p.add_argument("--vitis", help="vitis-run 路径（默认自动查找）")
    p.add_argument("--part", default=None, help="目标器件")
    p.add_argument("--clock", type=float, default=None, help="时钟周期 ns")
    p.add_argument("--csim-timeout", type=int, default=240)
    p.add_argument("--synth-timeout", type=int, default=1800)
    p.add_argument(
        "--max-total-time", type=int, default=0,
        help="整批评测的总时间预算（秒，默认 0 = 不限）。超时后剩余题目记为跳过",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    args = build_parser().parse_args(argv)

    root = ds.locate_dataset(args.dataset)
    if root is None:
        print("[错误] 没找到 HLS-Eval 数据集，用 --dataset 指定", file=sys.stderr)
        return 2
    d = ds.HlsEvalDataset(root)
    tasks = _select_tasks(d, args)
    if not tasks:
        print("[错误] 没有选中任何题目", file=sys.stderr)
        return 2

    cfg = _cfg(args)

    if not cfg.vitis_ready():
        print(f"[错误] 没找到 Vitis: {cfg.vitis_run}", file=sys.stderr)
        return 2

    print(SEP)
    print("  HLS Agent 批量评测")
    print(SEP)
    print(f"  题目数   : {len(tasks)}   轮数 k = {args.k}   模式 = {args.mode}")
    print(f"  重试上限 : {1 if args.mode == 'baseline' else args.attempts}")
    print(f"  综合     : {'开' if args.synth else '关'}")
    print(f"  工作区   : {cfg.workspace}")
    print(f"  器件     : {cfg.part} @ {cfg.clock_ns:g} ns")
    print(f"  Vitis    : {cfg.vitis_run}")
    print(f"  模型     : {cfg.llm.describe()}")
    print(f"  机器     : {platform.platform()}")
    print(SEP)
    print()

    rep = evaluate(tasks, cfg, args)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    outdir = Path(args.outdir) / f"{stamp}_{rep.mode}_k{rep.k}"
    save_report(rep, outdir)

    print()
    print(render_summary(rep))
    print()
    print(SEP)
    print(f"  结果已保存: {outdir.resolve()}")
    print(f"    results.json  逐次运行记录")
    print(f"    summary.md    汇总表（可直接贴进设计报告）")
    print(SEP)
    return 0


if __name__ == "__main__":
    sys.exit(main())
