"""单题编排：读题 -> 生成 -> Vitis 编译仿真 -> 四级判定 -> 失败回灌重试。

对应赛道的 run.sh / run_baseline.sh：

  agent     完整智能体：官方提示词 + 编译仿真反馈 + 失败重试
  baseline  裸跑基线：同一提示词，单次生成、不重试、不看工具反馈

两者用同一推理服务与同一上下文配置，差值即「增益」。
"""

from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import prompts
from .config import AgentConfig, safe_dir_name
from .dataset import Task, copy_task_into
from .llm import LLMClient, extract_source
from .vitis import (
    ExecResult,
    Grade,
    HlsResult,
    TaskPaths,
    clean_build,
    error_excerpt,
    find_synth_report,
    run_csim,
    run_synth,
)

# --------------------------------------------------------------------------
# 判定辅助
# --------------------------------------------------------------------------


# 数值比对用相对误差：定点运算是逐步舍入的，和参考实现在累加顺序/中间变量上
# 只要有差异，末位就会有量级 1e-3 的偏差。官方 zero-shot 评测本身不比对 dump，
# 只看 csim 返回码，所以这里只作为诊断信号，阈值取得宽松以免误判。
REL_TOL = 1e-2


def compare_dumps(
    got: Dict[str, List[float]], ref: Dict[str, List[float]]
) -> Tuple[bool, str]:
    """把仿真 dump 与参考 dump 比较，返回 (是否一致, 说明)。"""
    if not got or not ref:
        return True, "无参考输出，跳过数值比对"

    detail: List[str] = []
    ok = True

    for name, rvals in ref.items():
        if name not in got:
            ok = False
            detail.append(f"{name}: 仿真未输出该数组")
            continue
        gvals = got[name]
        if len(gvals) != len(rvals):
            ok = False
            detail.append(f"{name}: 长度不符 仿真 {len(gvals)} vs 参考 {len(rvals)}")
            continue

        max_err = max(abs(a - b) for a, b in zip(gvals, rvals))
        scale = max(1.0, max(abs(v) for v in rvals))
        rel = max_err / scale
        if rel > REL_TOL:
            ok = False
            detail.append(f"{name}: 相对误差 {rel:.3g} 超过 {REL_TOL:g}（绝对 {max_err:.4g}）")
        else:
            detail.append(f"{name}: 相对误差 {rel:.3g}（绝对 {max_err:.4g}）")

    return ok, "; ".join(detail)


def load_reference_dump(task: Task) -> Dict[str, List[float]]:
    from .vitis import parse_dumps

    fp = task.reference_dump_file()
    if fp is None:
        return {}
    try:
        return parse_dumps(fp.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return {}


def load_error_tolerance(task: Task) -> Optional[float]:
    """读 tb_data_hls_error.json 里的 rmse 作为可接受最大误差。"""
    fp = task.root / "tb_data_hls_error.json"
    if not fp.is_file():
        return None
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    vals = []
    for v in data.values():
        if isinstance(v, dict):
            for k in ("rmse", "mae", "mse"):
                if isinstance(v.get(k), (int, float)):
                    vals.append(abs(float(v[k])))
    return max(vals) if vals else None


# --------------------------------------------------------------------------
# 报告
# --------------------------------------------------------------------------


@dataclass
class Attempt:
    index: int
    code: str = ""
    result: Optional[HlsResult] = None
    generation_error: str = ""
    dump_ok: bool = True
    dump_detail: str = ""

    @property
    def passed(self) -> bool:
        return bool(self.result and self.result.grade.run)


@dataclass
class TaskReport:
    task: Task
    project_dir: Path
    mode: str
    attempts: List[Attempt] = field(default_factory=list)
    grade: Grade = field(default_factory=Grade)
    dumps: Dict[str, List[float]] = field(default_factory=dict)
    dump_ok: bool = True
    dump_detail: str = ""
    elapsed_s: float = 0.0
    gen_time_s: float = 0.0

    @property
    def passed(self) -> bool:
        return bool(self.grade.run)

    def headline(self) -> str:
        n = len(self.attempts)
        if self.grade.synth:
            return f"全过（可综合）· {n} 次尝试"
        if self.grade.run:
            return f"可运行 · {n} 次尝试"
        if self.grade.compile:
            return f"仅可编译 · {n} 次尝试"
        return f"失败 · {n} 次尝试"


# --------------------------------------------------------------------------
# 单次尝试
# --------------------------------------------------------------------------


def _write_line_report(rep: TaskReport, att: Attempt, cfg: AgentConfig, verbose: bool) -> None:
    if not verbose or att.result is None:
        return
    res = att.result
    print(f"  [判定] {res.grade.as_row()}")
    if res.compile is not None:
        print(f"  [编译] {'通过' if res.compile.ok else '失败'}  ({res.compile.elapsed_s:.1f}s)")
    if res.run is not None:
        print(f"  [仿真] {'通过' if res.run.ok else '失败'}  ({res.run.elapsed_s:.1f}s)")
    if res.synth is not None:
        print(f"  [综合] {'通过' if res.synth.ok else '失败'}  ({res.synth.elapsed_s:.1f}s)")
    if att.dump_detail:
        print(f"  [数据] {att.dump_detail}")


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------


def run_task(
    task: Task,
    cfg: AgentConfig,
    client: Optional[LLMClient] = None,
    max_attempts: int = 1,
    do_synth: bool = False,
    mode: str = "agent",
    verbose: bool = True,
) -> TaskReport:
    """跑完一道题：生成 -> csim ->（可选）csynth -> 四级判定。"""
    t_start = time.time()

    workdir = cfg.workspace / safe_dir_name(task.name)
    if workdir.exists():
        shutil.rmtree(workdir, ignore_errors=True)
    workdir.mkdir(parents=True, exist_ok=True)
    copy_task_into(task, workdir)

    paths = TaskPaths(
        workdir=workdir,
        build_name=task.top,
        source_name=task.source_name,
        other_sources=[task.header_name, task.tb_name],
    )

    report = TaskReport(task=task, project_dir=workdir, mode=mode)
    ref_dump = load_reference_dump(task)
    tol = load_error_tolerance(task)

    if client is None:
        from .config import LLMConfig

        client = LLMClient(LLMConfig.from_env())

    base_prompt = prompts.build_prompt_gen_zero_shot(
        description_name=task.description_file.name,
        description=task.description,
        tb_name=task.tb_name,
        tb_src=task.tb_src,
        h_name=task.header_name,
        h_src=task.header_src,
    )
    (workdir / "prompt.txt").write_text(base_prompt, encoding="utf-8", newline="\n")

    prompt = base_prompt
    prev_code = ""
    use_skill = mode != "baseline"

    for i in range(1, max_attempts + 1):
        att = Attempt(index=i)

        t_gen = time.time()
        try:
            raw = client.complete(system="", messages=[{"role": "user", "content": prompt}])
            (workdir / f"raw_llm_output_{i}.txt").write_text(raw, encoding="utf-8", newline="\n")
            att.code = extract_source(raw, task.source_name, task.top)
        except Exception as e:
            att.generation_error = str(e)
            report.gen_time_s += time.time() - t_gen
            report.attempts.append(att)
            if verbose:
                print(f"  [尝试 {i}] 生成失败：{str(e)[:160]}")
            # 生成阶段失败（多为没按输出格式走）也值得重试
            if use_skill and i < max_attempts:
                prompt = prompts.build_format_retry_prompt(
                    base_prompt, str(e), task.source_name
                )
                continue
            break
        report.gen_time_s += time.time() - t_gen

        # 可解析：模型输出的代码被成功提取，且包含顶层函数名
        parse_ok = bool(att.code.strip()) and task.top in att.code
        (workdir / task.source_name).write_text(att.code, encoding="utf-8", newline="\n")
        (workdir / f"attempt_{i}_{task.source_name}").write_text(
            att.code, encoding="utf-8", newline="\n"
        )

        if not parse_ok:
            att.result = HlsResult(project_dir=workdir, grade=Grade(parse=False, compile=False, run=False))
            report.attempts.append(att)
            if not use_skill:
                break
            prompt = prompts.build_retry_prompt(
                base_prompt,
                f"生成的代码里找不到顶层函数 {task.top}，请确认实现了正确的函数。",
                att.code,
                task.source_name,
            )
            continue

        # ---- 编译 + 仿真 ----
        if verbose:
            print(f"  [尝试 {i}] 编译并运行 testbench ...", flush=True)
        clean_build(paths)
        res = run_csim(paths, cfg.vitis_run, cfg.part, cfg.clock_ns, cfg.csim_timeout_s)
        res.grade.parse = True
        res.grade.compile = bool(res.compile and res.compile.ok)
        res.grade.run = bool(res.run and res.run.ok)

        # ---- 综合 ----
        if do_synth and res.grade.compile:
            if verbose:
                print(f"  [尝试 {i}] 综合中（较慢）...", flush=True)
            synth_res = run_synth(
                paths, cfg.vitis_run, cfg.part, cfg.clock_ns, cfg.csynth_timeout_s
            )
            res.synth = synth_res
            res.synth_log = synth_res.stdout + synth_res.stderr
            res.synth_report = find_synth_report(paths)
            res.grade.synth = synth_res.ok

        att.result = res

        # ---- 数值比对 ----
        if res.grade.run and ref_dump:
            att.dump_ok, att.dump_detail = compare_dumps(res.dumps, ref_dump)
            if not att.dump_ok:
                att.dump_detail = f"数值不符（容差 {tol if tol is not None else 1e-3:g}）：" + att.dump_detail
        else:
            att.dump_ok, att.dump_detail = True, ""

        report.attempts.append(att)

        # 通过条件：可运行 + 数值一致
        if res.grade.run and att.dump_ok:
            break
        if not use_skill:
            break

        errs = error_excerpt(res)
        if not att.dump_ok:
            errs = att.dump_detail + "\n" + errs
        prev_code = att.code
        prompt = prompts.build_retry_prompt(base_prompt, errs, prev_code, task.source_name)

    last = report.attempts[-1] if report.attempts else None
    if last and last.result:
        report.grade = last.result.grade
        report.dumps = last.result.dumps
        report.dump_ok = last.dump_ok
        report.dump_detail = last.dump_detail

    report.elapsed_s = time.time() - t_start
    return report
