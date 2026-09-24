"""命令行入口。

主流程（对应赛道的 run.sh）：
    打开即出一道题 -> 打印题面与必须匹配的签名 -> 调用模型生成 ->
    调用本机 Vitis HLS 做 csim 并把 csim.exe 跑起来 -> 打印四级判定 ->
    未通过时把工具输出回灌给模型重试

离线流程（内置题库模板，不调模型、不跑 Vitis）保留在 --offline 下。
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import List, Optional

# 允许在 PyCharm 里直接右键运行本文件（否则相对导入会报
# "attempted relative import with no known parent package"）。
# 作为包模块被入口 hls_agent.py 导入时，此分支不生效。
if __package__ in (None, ""):
    _ROOT = Path(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    __package__ = "hls_agent"

from . import codegen, dataset as ds
from .config import (
    DEFAULT_CLOCK_NS,
    DEFAULT_PART,
    AgentConfig,
    LLMConfig,
    WorkspaceError,
    find_vitis_run,
    resolve_workspace,
)
from .knowledge_base import get_problem, list_problems
from .matcher import analyze, canonical_question, describe_params, rank
from .runner import TaskReport, run_task

SEP = "=" * 78


def _setup_console() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass


# --------------------------------------------------------------------------
# 题目展示
# --------------------------------------------------------------------------


def show_task(task: ds.Task, index: int = 0, total: int = 0) -> None:
    pos = f"  [{index}/{total}]" if total else ""
    print(SEP)
    print(f"  题目：{task.name}{pos}   变体：{task.variant or '-'}")
    print(SEP)
    print(f"  顶层函数 : {task.top}")
    print(f"  要生成   : {task.source_name}")
    print(f"  给定头文件: {task.header_name}   (不可修改)")
    print(f"  给定测试台: {task.tb_name}       (不可修改)")
    if task.tags:
        print(f"  标签     : {', '.join(task.tags)}")
    print()
    print("  ---- 题面 (kernel_description.md) ----")
    for line in task.description.strip().splitlines():
        print(f"  {line}")
    print()
    print(f"  ---- 给定的头文件 ({task.header_name}) ----")
    for line in task.header_src.strip().splitlines():
        print(f"  {line}")
    print(SEP)


def show_report(rep: TaskReport) -> None:
    print(SEP)
    print(f"  结果：{rep.task.name}   ({rep.headline()})")
    print(SEP)
    print(f"  模式     : {'基线（单次生成，不重试）' if rep.mode == 'baseline' else '智能体'}")
    print(f"  四级判定 : {rep.grade.as_row()}")
    print(f"  已达到   : {rep.grade.highest}")
    print(f"  尝试次数 : {len(rep.attempts)}")
    print(f"  生成耗时 : {rep.gen_time_s:.1f} s")
    print(f"  总墙钟   : {rep.elapsed_s:.1f} s")
    print(f"  工程目录 : {rep.project_dir}")

    for name, vals in rep.dumps.items():
        print(f"  输出数组 : {name}  ({len(vals)} 个值)")
    if rep.dump_detail:
        print(f"  数值比对 : {'一致' if rep.dump_ok else '不一致'}  {rep.dump_detail}")

    last = rep.attempts[-1] if rep.attempts else None
    if last and last.result:
        res = last.result
        if res.compile is not None:
            print(f"  编译     : {'通过' if res.compile.ok else '失败'}  ({res.compile.elapsed_s:.1f}s)")
        if res.run is not None:
            print(f"  仿真     : {'通过' if res.run.ok else '失败'}  ({res.run.elapsed_s:.1f}s)")
        if res.synth is not None:
            print(f"  综合     : {'通过' if res.synth.ok else '失败'}  ({res.synth.elapsed_s:.1f}s)")
        if res.synth_report:
            print(f"  综合报告 : {res.synth_report}")

        if not rep.passed:
            from .vitis import error_excerpt

            print()
            print("  ---- 错误摘要 ----")
            for line in error_excerpt(res, limit=8).splitlines()[:16]:
                print(f"  {line}")
    elif last and last.generation_error:
        print(f"  生成失败 : {last.generation_error[:400]}")

    print(SEP)


# --------------------------------------------------------------------------
# 数据集
# --------------------------------------------------------------------------


def _load_dataset(args: argparse.Namespace) -> ds.HlsEvalDataset:
    root = ds.locate_dataset(args.dataset)
    if root is None:
        print("[错误] 没找到 HLS-Eval 数据集。", file=sys.stderr)
        print("       用 --dataset <目录> 指定。数据集包含 hls_eval_config.toml 的目录才算题目。", file=sys.stderr)
        raise SystemExit(2)

    try:
        d = ds.HlsEvalDataset(root)
        tasks = d.tasks()
    except ds.DatasetError as e:
        print(f"[错误] {e}", file=sys.stderr)
        raise SystemExit(2)

    if not tasks:
        print(f"[错误] {root} 下没扫到任何题目。", file=sys.stderr)
        raise SystemExit(2)
    return d


def cmd_list_tasks(args: argparse.Namespace) -> int:
    d = _load_dataset(args)
    tasks = d.tasks()
    if args.variant:
        tasks = [t for t in tasks if args.variant.lower() in t.variant.lower()]
        if not tasks:
            print(f"[错误] 变体 '{args.variant}' 下没有题目", file=sys.stderr)
            return 2

    print(SEP)
    print(f"  HLS-Eval 题目（{len(tasks)} 道）  数据集: {d.root}")
    print(SEP)

    by_variant: dict[str, list[ds.Task]] = {}
    for t in tasks:
        by_variant.setdefault(t.variant or "(未分组)", []).append(t)

    for variant, ts in sorted(by_variant.items()):
        print(f"\n  [{variant}]  {len(ts)} 道")
        for t in ts:
            print(f"    {t.name:<28}{t.top}")

    errs = d.errors
    if errs:
        print(f"\n  跳过 {len(errs)} 个目录（不符合题目规范），前 5 个：")
        for e in errs[:5]:
            print(f"    {e}")

    print()
    print("  运行单题: py hls_agent.py --task <题目名>")
    print("  按变体跑: py hls_agent.py --variant polybench --all --max 5")
    return 0


def _build_cfg(args: argparse.Namespace) -> AgentConfig:
    try:
        ws = resolve_workspace(args.workspace)
    except WorkspaceError as e:
        print(f"[错误] {e}", file=sys.stderr)
        raise SystemExit(2)

    return AgentConfig(
        part=args.part,
        clock_ns=args.clock,
        workspace=ws,
        vitis_run=find_vitis_run(args.vitis),
        csim_timeout_s=args.csim_timeout,
        csynth_timeout_s=args.synth_timeout,
        verbose=not args.quiet,
        llm=LLMConfig.from_env(),
    )


def cmd_run_tasks(args: argparse.Namespace) -> int:
    d = _load_dataset(args)
    cfg = _build_cfg(args)

    all_tasks = d.tasks()
    if args.variant:
        all_tasks = [t for t in all_tasks if args.variant.lower() in t.variant.lower()]
        if not all_tasks:
            print(f"[错误] 变体 '{args.variant}' 下没有题目", file=sys.stderr)
            return 2

    if not args.quiet:
        print(SEP)
        print("  HLS 智能体  ——  读题 -> 生成 -> Vitis 编译仿真 -> 四级判定")
        print(SEP)
        print(f"  数据集   : {d.root}")
        print(f"  工作区   : {cfg.workspace}")
        print(f"  器件     : {cfg.part}   时钟 {cfg.clock_ns:g} ns")
        print(f"  Vitis    : {cfg.vitis_run}")
        print(f"  模型     : {cfg.llm.describe()}")
        print(f"  模式     : {'基线' if args.baseline else '智能体'}   "
              f"csynth: {'开' if args.synth else '关'}   重试上限: "
              f"{1 if args.baseline else max(1, args.attempts)}")
        print()

    if args.all:
        tasks = all_tasks[: args.max] if args.max else all_tasks
    elif args.task:
        tasks = [d.get(args.task)]
    else:
        tasks = [random.choice(all_tasks)]

    if args.dry_run:
        return _dry_run(tasks, cfg, args)

    if not cfg.vitis_ready():
        print("[错误] 没找到 Vitis。用 --vitis <vitis-run.bat 路径> 指定。", file=sys.stderr)
        print(f"       已查找: {cfg.vitis_run}", file=sys.stderr)
        return 2

    reports: List[TaskReport] = []
    for i, t in enumerate(tasks, 1):
        if not args.quiet:
            show_task(t, i, len(tasks))
        else:
            print(f"[{i}/{len(tasks)}] {t.name} ...", flush=True)

        try:
            rep = run_task(
                task=t,
                cfg=cfg,
                client=None,
                max_attempts=1 if args.baseline else max(1, args.attempts),
                do_synth=args.synth,
                mode="baseline" if args.baseline else "agent",
                verbose=not args.quiet,
            )
        except KeyboardInterrupt:
            print("\n[中断] 用户中止")
            break
        except Exception as e:
            print(f"  [异常] {t.name}: {e}")
            rep = TaskReport(task=t, project_dir=cfg.workspace, mode="error")
        reports.append(rep)

        if not args.quiet:
            show_report(rep)
        else:
            print(f"          {rep.headline()}  {rep.grade.as_row()}")

    if len(reports) > 1:
        _summary_table(reports)

    return 0 if reports and all(r.passed for r in reports) else 1


def _dry_run(tasks: List[ds.Task], cfg: AgentConfig, args: argparse.Namespace) -> int:
    """只生成代码，不跑 Vitis。"""
    from .llm import LLMClient, extract_source
    from . import prompts
    from .dataset import copy_task_into
    from .config import safe_dir_name

    client = LLMClient(cfg.llm)
    ok = 0
    for i, t in enumerate(tasks, 1):
        workdir = cfg.workspace / safe_dir_name(t.name)
        workdir.mkdir(parents=True, exist_ok=True)
        copy_task_into(t, workdir)

        prompt = prompts.build_prompt_gen_zero_shot(
            t.description_file.name, t.description, t.tb_name, t.tb_src, t.header_name, t.header_src
        )
        print(f"[{i}/{len(tasks)}] {t.name} 生成中 ...", flush=True)
        try:
            text = client.complete("", [{"role": "user", "content": prompt}])
            code = extract_source(text, t.source_name)
            (workdir / t.source_name).write_text(code, encoding="utf-8", newline="\n")
            (workdir / "raw_llm_output.txt").write_text(text, encoding="utf-8", newline="\n")
            print(f"           -> {workdir / t.source_name}  ({len(code)} 字节)")
            ok += 1
        except Exception as e:
            print(f"           [失败] {e}")
    print(f"\n完成 {ok}/{len(tasks)}，未调用 Vitis（--dry-run）")
    return 0 if ok == len(tasks) else 1


def _summary_table(reports: List[TaskReport]) -> None:
    passed = sum(1 for r in reports if r.passed)
    attempts = max((len(r.attempts) for r in reports), default=1)
    print(SEP)
    print(f"  汇总：{passed}/{len(reports)} 通过（可运行且数值一致）")
    print(SEP)
    print(f"  {'题目':<26}{'判定':<34}{'尝试':>4}{'墙钟':>9}")
    print("-" * 78)
    for r in reports:
        print(f"  {r.task.name:<26}{r.grade.as_row():<34}{len(r.attempts):>4}{r.elapsed_s:>8.1f}s")
    print()
    # 每题最多尝试 attempts 次，因此这里等价于 pass@attempts
    print(f"  pass@{attempts} = {passed}/{len(reports)}")
    print(f"  总墙钟 = {sum(r.elapsed_s for r in reports):.1f}s")
    print(SEP)


# --------------------------------------------------------------------------
# 离线流程（内置题库，不调模型、不跑 Vitis）
# --------------------------------------------------------------------------


def cmd_offline(args: argparse.Namespace) -> int:
    """内置题库的离线流程：不调模型、不跑 Vitis。"""
    texts: List[str] = []

    if args.offline:
        texts.append(args.offline)

    if args.file:
        fp = Path(args.file)
        if not fp.is_file():
            print(f"[错误] 文件不存在: {fp}", file=sys.stderr)
            return 2
        content = fp.read_text(encoding="utf-8", errors="replace")
        if args.batch:
            texts.extend(c.strip() for c in content.split("\n\n") if c.strip())
        else:
            texts.append(content)

    if not texts:
        print("[错误] 用 --offline <题目文本> 或 -f <文件> 提供题目", file=sys.stderr)
        return 2

    failed = 0
    for i, text in enumerate(texts, 1):
        if len(texts) > 1:
            print(f"--- 第 {i}/{len(texts)} 题 ---")
            print(f"  [输入] {text.strip()[:90]}")

        try:
            res = analyze(text, args.dtype)
        except LookupError:
            cands = rank(text, top_k=3)
            if not cands:
                print("  [跳过] 无法识别该题目。用 --kb-list 查看支持的题型。")
                failed += 1
                continue
            print("  [提示] 没有明确匹配，使用最接近的候选：")
            for score, p, _ in cands:
                print(f"         {p.name} ({p.pid})  得分={score}")
            from .matcher import resolve_dtype

            p0 = cands[0][1]
            dt, _inc, note = resolve_dtype(text, p0, args.dtype)
            from .matcher import MatchResult

            res = MatchResult(
                problem=p0,
                score=cands[0][0],
                hits=cands[0][2],
                params=p0.extract_params(text),
                dtype=dt,
                dtype_note=note,
            )
        except ValueError as e:
            print(f"  [跳过] {e}")
            failed += 1
            continue

        print(f"  [识别] {res.problem.name} ({res.problem.pid})  得分={res.score}")
        print(f"  [题目] {canonical_question(res.problem, res.params)}")
        print(f"  [参数] {describe_params(res.problem, res.params)}")
        print(f"  [类型] {res.dtype}")

        files = codegen.generate(res, text, args.outdir)
        print("  [生成]")
        for f in files:
            print(f"         {f}")
        print()

    if len(texts) > 1:
        print(f"完成 {len(texts) - failed}/{len(texts)} 道题，输出目录: {Path(args.outdir).resolve()}")
    return 1 if failed else 0


def cmd_kb_list() -> int:
    problems = list_problems()
    print(SEP)
    print(f"  内置题库（共 {len(problems)} 题，离线模板，不调模型）")
    print(SEP)
    for p in problems:
        print(f"  {p.pid:<16}{p.name:<22}{p.category}")
    print()
    print('  用法: py hls_agent.py --offline "实现8点FIR低通滤波器"')
    return 0


# --------------------------------------------------------------------------
# argparse
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hls_agent",
        description="HLS 智能体：读题 -> 用大模型生成 Vitis HLS C++ -> 调本机 Vitis 编译仿真 -> 四级判定",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  py hls_agent.py                            随机出一道题并跑完整流程
  py hls_agent.py --task 2mm                 指定题目
  py hls_agent.py --variant polybench --list 列出某变体的题目
  py hls_agent.py --task 2mm --synth         连综合一起跑（对应"可综合"）
  py hls_agent.py --task 2mm --attempts 5    失败自动重试最多 5 次
  py hls_agent.py --task 2mm --baseline      裸跑基线（单次生成，不重试）
  py hls_agent.py --all --max 10             批量跑前 10 道
  py hls_agent.py --task 2mm --dry-run       只生成不跑 Vitis
  py hls_agent.py --kb-list                  列出内置离线题库
  py hls_agent.py --offline "8点FIR滤波器"    离线模板流程（不调模型）
""",
    )

    # 数据集 / 题目
    p.add_argument("--dataset", help="HLS-Eval 数据集目录（默认自动查找）")
    p.add_argument("--task", help="指定题目名（见 --list）")
    p.add_argument("--variant", help="只看/只跑某个变体，如 polybench、chstone、machsuite")
    p.add_argument("--all", action="store_true", help="跑选中的全部题目")
    p.add_argument("--max", type=int, default=0, help="配合 --all，限制题目数量")
    p.add_argument("--list", action="store_true", help="列出数据集题目")

    # 流程控制
    p.add_argument("--attempts", type=int, default=3, help="失败重试上限（默认 3）")
    p.add_argument("--synth", action="store_true", help="额外跑 csynth，评估「可综合」")
    p.add_argument("--baseline", action="store_true", help="基线模式：单次生成、不重试")
    p.add_argument("--dry-run", action="store_true", help="只生成代码，不调用 Vitis")

    # 环境
    p.add_argument("--workspace", help="Vitis 工作区根目录，必须是纯 ASCII 路径")
    p.add_argument("--vitis", help="vitis-run.bat 路径（默认自动查找）")
    p.add_argument("--part", default=DEFAULT_PART, help=f"目标器件（默认 {DEFAULT_PART}）")
    p.add_argument("--clock", type=float, default=DEFAULT_CLOCK_NS, help="时钟周期 ns（默认 5）")
    p.add_argument("--csim-timeout", type=int, default=600, help="csim 超时秒数（默认 600）")
    p.add_argument("--synth-timeout", type=int, default=1800, help="csynth 超时秒数（默认 1800）")
    p.add_argument("--quiet", action="store_true", help="精简输出")

    # 离线流程
    p.add_argument(
        "--offline",
        nargs="?",
        const="",
        metavar="题目文本",
        help="用内置题库模板生成（不调模型、不跑 Vitis）",
    )
    p.add_argument("-f", "--file", help="离线流程：从文件读取题目")
    p.add_argument("--batch", action="store_true", help="离线流程：把 -f 的文件按空行切成多道题")
    p.add_argument("--kb-list", action="store_true", help="列出内置题库")
    p.add_argument("-o", "--outdir", default="hls_output", help="离线流程的输出目录")
    p.add_argument("--dtype", help="离线流程手动指定数据类型")

    return p


def main(argv: Optional[List[str]] = None) -> int:
    _setup_console()
    args = build_parser().parse_args(argv)

    if args.kb_list:
        return cmd_kb_list()
    if args.offline is not None or args.file:
        return cmd_offline(args)
    if args.list:
        return cmd_list_tasks(args)

    try:
        return cmd_run_tasks(args)
    except WorkspaceError as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
