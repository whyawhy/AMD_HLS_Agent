"""Vitis HLS 调用与四级判定。

对齐 HLS-Eval 官方 hls_eval/tools.py：

  VitisHLSCSimTool   add_files -tb（所有文件都算 testbench 侧）-> csim_design -setup
                     （只编译，不运行）-> 手工执行 csim.exe
                     官方以「编译 return_code==0」判可编译，
                         「运行 csim.exe return_code==0」判可运行

  VitisHLSSynthTool  add_files（内核侧）-> open_solution -flow_target vivado
                     -> config_compile -unsafe_math_optimizations -> csynth_design
                     以 return_code==0 判可综合

本机适配：Vitis 2026.1 没有 `vitis_hls` 命令，改用 `vitis-run --mode hls --tcl`；
且工作目录必须是纯 ASCII（含中文时 Vitis 打不开 tcl 脚本）。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

# --------------------------------------------------------------------------
# 结果模型
# --------------------------------------------------------------------------


@dataclass
class Grade:
    """四级判定：可解析 -> 可编译 -> 可运行 -> 可综合。None 表示未评估。"""

    parse: Optional[bool] = None
    compile: Optional[bool] = None
    run: Optional[bool] = None
    synth: Optional[bool] = None

    _LEVELS = (("parse", "可解析"), ("compile", "可编译"), ("run", "可运行"), ("synth", "可综合"))

    def as_row(self) -> str:
        def mark(v: Optional[bool]) -> str:
            return "略过" if v is None else ("通过" if v else "失败")

        return " -> ".join(mark(v) for v in (self.parse, self.compile, self.run, self.synth))

    @property
    def highest(self) -> str:
        reached = "未开始"
        for attr, label in self._LEVELS:
            if getattr(self, attr) is True:
                reached = label
            else:
                break
        return reached


@dataclass
class ExecResult:
    return_code: int
    stdout: str = ""
    stderr: str = ""
    elapsed_s: float = 0.0
    timeout: bool = False

    @property
    def ok(self) -> bool:
        return self.return_code == 0 and not self.timeout


@dataclass
class HlsResult:
    """一次完整评估的结果。"""

    project_dir: Path
    compile: Optional[ExecResult] = None
    run: Optional[ExecResult] = None
    synth: Optional[ExecResult] = None
    log: str = ""
    synth_log: str = ""
    dumps: Dict[str, List[float]] = field(default_factory=dict)
    grade: Grade = field(default_factory=Grade)
    synth_report: Optional[Path] = None
    elapsed_s: float = 0.0

    def summary(self) -> str:
        return f"{self.grade.highest}  ({self.grade.as_row()})  [{self.elapsed_s:.1f}s]"


@dataclass
class TaskPaths:
    """一道题在工作目录里的文件布局。"""

    workdir: Path
    build_name: str
    source_name: str  # 生成的内核 .cpp
    other_sources: List[str] = field(default_factory=list)  # 数据集带来的头文件/tb

    @property
    def project_name(self) -> str:
        return f"{self.build_name}__proj"

    @property
    def csim_exe(self) -> Path:
        return (
            self.workdir
            / self.project_name
            / "solution__synth"
            / "csim"
            / "build"
            / "csim.exe"
        )


# --------------------------------------------------------------------------
# 日志解析
# --------------------------------------------------------------------------

_CSIM_DONE = re.compile(r"CSim done with (\d+) errors")
_CLANG_ERROR = re.compile(r"^.*?:\d+:\d+:\s*(?:fatal\s+)?error:\s*(.+)$", re.MULTILINE)
_HLS_ERROR = re.compile(r"^(ERROR|CRITICAL WARNING):\s*\[([A-Z]+ \d+-\d+)\]\s*(.*)$", re.MULTILINE)
_DUMP_BLOCK = re.compile(r"==BEGIN DUMP_ARRAYS==(.*?)==END\s+DUMP_ARRAYS==", re.DOTALL)
_DUMP_NAME = re.compile(r"begin dump:\s*(\S+)")
_NUMBER = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")

_MAX_ERRORS = 12


def parse_dumps(text: str) -> Dict[str, List[float]]:
    """抽取 PolyBench 风格的 dump 数组。

    testbench 的 print_array() 会往 stderr 打：
        ==BEGIN DUMP_ARRAYS==
        begin dump: D
        6.740234 6.197266 ...
        end   dump: D
        ==END   DUMP_ARRAYS==
    """
    out: Dict[str, List[float]] = {}
    for block in _DUMP_BLOCK.findall(text):
        name_m = _DUMP_NAME.search(block)
        if not name_m:
            continue
        body = block[name_m.end():].split("end   dump:")[0]
        vals: List[float] = []
        for tok in _NUMBER.findall(body):
            try:
                vals.append(float(tok))
            except ValueError:
                pass
        if vals:
            out[name_m.group(1)] = vals
    return out


def extract_errors(log: str) -> tuple[List[str], List[str]]:
    """返回 (编译错误, Vitis 错误)。"""
    compile_errors = list(dict.fromkeys(_CLANG_ERROR.findall(log)))[:_MAX_ERRORS]
    hls_errors = [f"[{code}] {msg.strip()}" for _, code, msg in _HLS_ERROR.findall(log)][:_MAX_ERRORS]
    return compile_errors, hls_errors


def error_excerpt(res: HlsResult, limit: int = 8) -> str:
    """汇总失败原因，喂给重试环节。"""
    lines: List[str] = []

    if res.compile is not None and not res.compile.ok:
        c_errs, h_errs = extract_errors(res.log)
        for e in c_errs[:limit]:
            lines.append(f"编译错误: {e}")
        for e in h_errs[:limit]:
            lines.append(f"Vitis: {e}")
        if not c_errs and not h_errs:
            lines.append(_tail(res.log, 1500))

    if res.run is not None and not res.run.ok:
        if res.run.timeout:
            lines.append("运行 testbench 超时")
        else:
            lines.append(f"testbench 运行返回码 {res.run.return_code}，输出如下：")
            lines.append(_tail((res.run.stdout or "") + (res.run.stderr or ""), 1500))
        if "CSim done with" in res.log:
            m = _CSIM_DONE.search(res.log)
            if m and int(m.group(1)) != 0:
                lines.append(f"C 仿真报告 {m.group(1)} 处错误")

    if res.synth is not None and not res.synth.ok:
        _, h_errs = extract_errors(res.synth_log)
        for e in h_errs[:limit]:
            lines.append(f"综合错误: {e}")
        if not h_errs:
            lines.append(_tail(res.synth_log, 1500))

    if not lines:
        lines.append(_tail(res.log, 1500))
    return "\n".join(lines)


def _tail(s: str, n: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else "..." + s[-n:]


# --------------------------------------------------------------------------
# Tcl 构造
# --------------------------------------------------------------------------


def build_csim_tcl(paths: TaskPaths, part: str, clock_ns: float, flow_target: str = "vivado") -> str:
    """官方 VitisHLSCSimTool 的 tcl：所有文件都按 testbench 侧加入，只做 setup。"""
    lines = [f"open_project {paths.project_name}"]
    for name in [paths.source_name] + paths.other_sources:
        lines.append(f"add_files -tb {name}")
    lines.append(f"open_solution solution__synth -flow_target {flow_target}")
    lines.append(f"set_top {paths.build_name}")
    lines.append(f"set_part {part}")
    lines.append(f"create_clock -period {clock_ns:g} -name clk_default")
    lines.append("csim_design -setup")
    lines.append("exit")
    return "\n".join(lines) + "\n"


def build_synth_tcl(
    paths: TaskPaths,
    part: str,
    clock_ns: float,
    flow_target: str = "vivado",
    unsafe_math: bool = True,
) -> str:
    """官方 VitisHLSSynthTool 的 tcl。"""
    lines = [f"open_project {paths.project_name}"]
    for name in [paths.source_name] + paths.other_sources:
        lines.append(f"add_files {name}")
    lines.append(f"open_solution solution__synth -flow_target {flow_target}")
    lines.append(f"set_top {paths.build_name}")
    lines.append(f"set_part {part}")
    lines.append(f"create_clock -period {clock_ns:g} -name clk_default")
    if unsafe_math:
        lines.append("config_compile -unsafe_math_optimizations")
    lines.append("csynth_design")
    lines.append("exit")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# 执行
# --------------------------------------------------------------------------


def _run(cmd: List[str], cwd: Path, timeout: int, env: Optional[dict] = None) -> ExecResult:
    t0 = time.time()
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
        return ExecResult(
            return_code=p.returncode,
            stdout=p.stdout or "",
            stderr=p.stderr or "",
            elapsed_s=time.time() - t0,
        )
    except subprocess.TimeoutExpired as e:
        def dec(x):
            if isinstance(x, bytes):
                return x.decode("utf-8", errors="replace")
            return x or ""

        return ExecResult(
            return_code=-1,
            stdout=dec(e.stdout),
            stderr=dec(e.stderr),
            elapsed_s=time.time() - t0,
            timeout=True,
        )


def csim_env(build_dir: Path, vitis_run: Path) -> dict:
    """构造运行 csim.exe 所需的环境变量。

    Vitis 生成的 csim.exe 依赖浮点算子模型与 MinGW 运行时的 DLL，
    不设置 PATH 时会「静默退出」（0.1 秒、无任何输出）。这些路径由 Vitis
    自己写在 build 目录的 env.json 里，直接读来用。
    """
    env = os.environ.copy()
    extra: List[str] = []

    env_fp = build_dir / "env.json"
    if env_fp.is_file():
        try:
            data = json.loads(env_fp.read_text(encoding="utf-8"))
            extra = [str(p) for p in data.get("PATH", [])]
        except (OSError, ValueError):
            extra = []

    if not extra:
        # env.json 缺失时按 Vitis 安装布局推断
        root = vitis_run.resolve().parent.parent
        for sub in (
            "win64/tools/fpo_v7_1",
            "win64/tools/fft_v9_1",
            "win64/tools/fir_v7_0",
            "win64/tools/dds_v6_0",
            "tps/mingw/10.0.0/win64.o/nt/bin",
        ):
            p = root / sub
            if p.is_dir():
                extra.append(str(p))

    existing = [p for p in extra if Path(p).is_dir()]
    if existing:
        env["PATH"] = os.pathsep.join(existing + [env.get("PATH", "")])
    return env


def _vitis_cmd(vitis_run: Path, tcl_name: str) -> List[str]:
    if str(vitis_run).lower().endswith(".bat"):
        return ["cmd", "/c", str(vitis_run), "--mode", "hls", "--tcl", tcl_name]
    return [str(vitis_run), "--mode", "hls", "--tcl", tcl_name]


def clean_build(paths: TaskPaths) -> None:
    """清掉上一次的 Vitis 工程，避免增量状态干扰。"""
    proj = paths.workdir / paths.project_name
    if proj.exists():
        shutil.rmtree(proj, ignore_errors=True)


def run_csim(
    paths: TaskPaths,
    vitis_run: Path,
    part: str,
    clock_ns: float,
    timeout_s: int = 600,
) -> HlsResult:
    """编译 + 运行 testbench。对应用户要的「读文件、编译、仿真」。"""
    paths.workdir.mkdir(parents=True, exist_ok=True)
    tcl_name = "run_csim.tcl"
    (paths.workdir / tcl_name).write_text(
        build_csim_tcl(paths, part, clock_ns), encoding="utf-8", newline="\n"
    )

    t0 = time.time()
    compile_res = _run(_vitis_cmd(vitis_run, tcl_name), paths.workdir, timeout_s)

    res = HlsResult(project_dir=paths.workdir, compile=compile_res, log=compile_res.stdout + compile_res.stderr)

    # 编译失败就不必跑
    if not compile_res.ok:
        res.elapsed_s = time.time() - t0
        return res

    exe = paths.csim_exe
    if not exe.is_file():
        # setup 成功但没生成可执行文件，视为编译失败
        res.compile = ExecResult(
            return_code=1,
            stdout=compile_res.stdout,
            stderr=compile_res.stderr + f"\n找不到 csim 可执行文件: {exe}",
            elapsed_s=compile_res.elapsed_s,
        )
        res.elapsed_s = time.time() - t0
        return res

    run_res = _run(
        [str(exe)],
        exe.parent,
        timeout_s,
        env=csim_env(exe.parent, vitis_run),
    )
    res.run = run_res
    res.log += "\n" + run_res.stdout + run_res.stderr
    res.dumps = parse_dumps(run_res.stdout + run_res.stderr + res.log)
    res.elapsed_s = time.time() - t0
    return res


def run_synth(
    paths: TaskPaths,
    vitis_run: Path,
    part: str,
    clock_ns: float,
    timeout_s: int = 1800,
    unsafe_math: bool = True,
) -> ExecResult:
    """跑 csynth，对应「可综合」。"""
    tcl_name = "run_synth.tcl"
    (paths.workdir / tcl_name).write_text(
        build_synth_tcl(paths, part, clock_ns, unsafe_math=unsafe_math),
        encoding="utf-8", newline="\n",
    )
    # 综合要重新建工程，先清掉 csim 那边的状态
    clean_build(paths)
    return _run(_vitis_cmd(vitis_run, tcl_name), paths.workdir, timeout_s)


def get_synth_log(paths: TaskPaths) -> str:
    log_fp = paths.workdir / paths.project_name / "solution__synth" / "solution1.log"
    if not log_fp.is_file():
        log_fp = paths.workdir / paths.project_name / "solution__synth" / "csynth.log"
    try:
        return log_fp.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def find_synth_report(paths: TaskPaths) -> Optional[Path]:
    rpt = paths.workdir / paths.project_name / "solution__synth" / "syn" / "report" / "csynth.rpt"
    return rpt if rpt.is_file() else None
