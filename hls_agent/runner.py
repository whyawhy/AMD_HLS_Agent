"""单题编排：读题 -> 生成 -> Vitis 编译仿真 -> 四级判定 -> 失败回灌重试。

对应赛道的 run.sh / run_baseline.sh：

  agent     完整智能体：官方提示词 + 编译仿真反馈 + 失败重试
  baseline  裸跑基线：同一提示词，单次生成、不重试、不看工具反馈

两者用同一推理服务与同一上下文配置，差值即「增益」。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import errors as err
from . import prompts
from .config import AgentConfig, safe_dir_name
from .dataset import Task, copy_task_into
from .llm import LLMClient, OutputTruncated, extract_source
from .vitis import (
    ExecResult,
    Grade,
    HlsResult,
    TaskPaths,
    clean_build,
    error_excerpt,
    find_synth_report,
    get_synth_log,
    run_csim,
    run_synth,
)
# --------------------------------------------------------------------------
# 判定辅助
# --------------------------------------------------------------------------


# 数值比对用相对误差：定点运算是逐步舍入的，和参考实现在累加顺序/中间变量上
# 只要有差异，末位就会有量级 1e-3 的偏差。官方 zero-shot 评测本身不比对 dump，
# 只看 csim 返回码，所以这里只作为诊断信号，阈值取得宽松以免误判。
#
# 注意判定口径分两类（见 dump_tolerance）：
#   浮点 / 定点题目 -> 相对容差，默认 1e-2（可用 HLS_AGENT_DUMP_TOL 覆盖）
#   纯整数题目     -> 精确比较（CHStone 的测试台本身就是位精确比对）
# 容差只会更严不会更松：整数题原本被 1e-2 的浮点容差放过去，属于漏判。
REL_TOL = 1e-2

# 判断题目是否用了浮点/定点数值：只看**真正的类型关键字**。
# CHStone 的头文件里有 `typedef unsigned long long float64;`——名字带 float
# 但本质是整数位模式，不能按浮点处理，所以这里用 \bfloat\b / \bdouble\b
# （`float64` 的 `float` 后面紧跟字母数字，词边界不成立，不会误命中）。
_FLOAT_TYPE = re.compile(r"\b(?:double|float)\b|ap_(?:u?fixed|float)\s*<")


def dump_tolerance(task: Task) -> float:
    """这道题的 dump 比对容差。整数题返回 0（精确比较）。"""
    env = os.environ.get("HLS_AGENT_DUMP_TOL", "").strip()
    if env:
        try:
            return float(env)
        except ValueError:
            pass
    if _FLOAT_TYPE.search(task.header_src):
        return REL_TOL
    return 0.0


def compare_dumps(
    got: Dict[str, List[float]],
    ref: Dict[str, List[float]],
    tol: float = REL_TOL,
) -> Tuple[bool, str]:
    """把仿真 dump 与参考 dump 比较，返回 (是否一致, 说明)。

    tol = 0 表示精确比较（整数题目）。相对误差以该数组参考值的最大绝对值为
    基准——这是一个全局相对误差口径，不是逐元素相对误差。
    """
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
        if rel > tol:
            ok = False
            detail.append(f"{name}: 相对误差 {rel:.3g} 超过 {tol:g}（绝对 {max_err:.4g}）")
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


def load_reference_error(task: Task) -> Optional[float]:
    """读 `tb_data_hls_error.json` 记录的**参考实现自身偏差**，仅用于诊断。

    这个文件记录的是数据集里的参考实现（HLS 定点版）相对软件黄金实现的
    mae/mse/rmse，例如 `polybench/2mm` 是 `{"D": {"mae": 0, "mse": 0, "rmse": 0}}`。
    它**不是**允许误差阈值，官方评测器（hls_eval/*.py）根本没读它。

    此前把它当容差用，导致给模型看的反馈里写出"相对容差 0"，
    与真实判定口径（1e-2）自相矛盾。现在只用来提示"参考实现本身的偏差量级"。
    """
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


# 旧名字保留，避免外部脚本引用失效
load_error_tolerance = load_reference_error


# ap_fixed<32,16> 的整数位是 16 位（含符号），取值范围 ±2^15 = ±32768。
# 迭代/累加类内核一旦中间结果越界就会**饱和**到边界值，输出里会出现
# ±32768 附近的数——这是溢出的指纹，不是精度问题。
_FIXED_SATURATION = 32768.0


def _detect_saturation(vals: List[float]) -> Optional[float]:
    """返回饱和迹象最强的那个值（接近 ±32768），没有则返回 None。"""
    if not vals:
        return None
    edge = [v for v in vals if abs(abs(v) - _FIXED_SATURATION) < _FIXED_SATURATION * 0.01]
    if not edge:
        return None
    return max(edge, key=abs)


_TB_MATH_CALL = re.compile(
    r"(?<![\w:.])\b(?:sin|cos|tan|asin|acos|atan2?|sqrt|pow|exp|log|log10|fabs|cbrt)\s*\("
)


def _tb_needs_mathlib(task: Task) -> bool:
    """这道题的**测试台**是否调用了数学库函数（而不是内核调用）。

    为什么要区分：测试台由数据集提供、不可修改。
      - 内核用了 `sqrt()`  → 让模型改写成内联实现即可通过（实测 cholesky 就是这样）
      - 测试台用了 `sin()` → 无论模型写什么都跑不起来，本机属于硬限制
    复现证据：`pp4fpga/pp4fpga_cordic/cordic_tb.cpp:36-37` 直接调用
    `sin((double)radian)` / `cos((double)radian)`。
    没有这个区分，就会把一次注定失败的重试和一次白跑的 Vitis 往返
    记到模型头上，报告里也会把"环境硬限制"写成"模型没修好"。
    """
    src = re.sub(r"/\*.*?\*/", " ", task.tb_src, flags=re.DOTALL)
    src = re.sub(r"//[^\n]*", " ", src)
    return bool(_TB_MATH_CALL.search(src))


def _retry_thinking(attempt_index: int, last_truncated: bool) -> Optional[str]:
    """重试时给多少思考预算。

    - 第一次尝试：不给思考，求快（多数题一次就过）。
    - 重试且上一轮**没有被截断**：给 2048 token 思考预算，难题（软浮点、
      复杂算法）靠推理能力修得更准。
    - 重试但上一轮**被截断**：显式关掉思考。

    最后一条来自实测：dfadd 开启思考预算后输出涨到 51~59KB，在写到一半时撞上
    max_tokens，两轮重试（约 260 秒）连一个 `<OUTPUT_CODE>` 标签都没产出——
    思考 token 和正文抢同一份预算，把正文挤没了。这种情况下先把代码写完更重要。
    """
    if attempt_index == 1:
        return None
    return "off" if last_truncated else "budget:2048"


def _mathlib_dll_hint(res: HlsResult) -> str:
    """csim.exe 因缺数学库 DLL 零输出退出时给模型的定向修复指示。

    这条不是"环境不可用"的报错，而是**可执行的修改要求**：把数学库调用换成
    手写内联实现。实测证据（2026-10-13，同机同代码库）：

      polybench__cholesky   手写 my_sqrt   -> 通过
      polybench__correlation 手写内联      -> 通过
      polybench__gramschmidt 裸 sqrt()     -> csim.exe rc=0xC0000135，零输出
      pp4fpga_cordic         数学库函数    -> 同上

    所以直接把"换写法"讲清楚，比笼统说"仿真失败"有效得多。
    """
    return (
        "testbench 可执行文件无法启动：csim.exe 以 0xC0000135 "
        "(STATUS_DLL_NOT_FOUND) 退出，且没有任何输出——说明它在执行你的代码之前就死了。\n"
        "原因确定：你的实现调用了 C 数学库函数（`sqrt()` / `std::sqrt()` / `pow()` / "
        "`exp()` / `log()` / `sin()` / `cos()` 等）。这些调用会让链接器去依赖 Vitis "
        "安装里并不存在的数学库运行时 DLL。\n"
        "**这不是环境问题，改写法即可通过**——同一台机器上，手写内联实现的同类题目都能跑通。\n"
        "请把每一个数学库调用替换成手写内联实现：\n"
        "```cpp\n"
        "static double my_sqrt(double x) {\n"
        "    if (x <= 0.0) return 0.0;\n"
        "    double r = x;\n"
        "    for (int i = 0; i < 60; i++) r = 0.5 * (r + x / r);\n"
        "    return r;\n"
        "}\n"
        "```\n"
        "（若内核用的是 ap_fixed，则改用 `hls::sqrt()`，它是内联展开、不依赖外部库。）\n"
        "其余算法逻辑一律保持不变，不要顺手改动数值类型或循环结构。"
    )


def _dump_mismatch_detail(
    got: Dict[str, List[float]], ref: Dict[str, List[float]], tol: float, sample: int = 6
) -> str:
    """数值不符时的重试反馈：给模型看参考值 vs 实际值的前几个样例。

    只告诉模型「数值不符」没用——它不知道差多少、差在哪。给出具体数值后，
    模型能立刻判断是精度问题（差 1e-3 量级）还是溢出/算法问题（差几个数量级），
    修复成功率明显更高。
    """
    lines = [f"数值与参考输出不符（相对容差 {tol:g}）。逐数组对比："]
    sat_hit: Optional[float] = None

    for name, rv in ref.items():
        gv = got.get(name)
        if not gv or len(gv) != len(rv):
            lines.append(f"- {name}: 长度不符 实际 {len(gv) if gv else 0} vs 参考 {len(rv)}")
            continue
        pairs = list(zip(gv, rv))
        max_idx = max(range(len(pairs)), key=lambda i: abs(pairs[i][0] - pairs[i][1]))
        worst = pairs[max_idx]
        lines.append(
            f"- {name}: 最大误差在索引 {max_idx}，实际 {worst[0]:.6g} vs 参考 {worst[1]:.6g}"
        )
        lines.append(
            f"  参考前 {sample} 个值: " + " ".join(f"{v:.4g}" for _, v in pairs[:sample])
        )
        lines.append(
            f"  实际前 {sample} 个值: " + " ".join(f"{v:.4g}" for v, _ in pairs[:sample])
        )
        s = _detect_saturation(gv)
        if s is not None and (sat_hit is None or abs(s) > abs(sat_hit)):
            sat_hit = s

    if sat_hit is not None:
        lines.append("")
        lines.append(
            f"**检测到定点饱和**：实际输出里出现了 {sat_hit:.6g}，非常接近 "
            f"t_ap_fixed（ap_fixed<32,16>）的取值范围边界 ±32768。"
            f"这说明中间计算结果**溢出饱和**了，不是舍入精度问题。"
        )
        lines.append(
            "修复方向：把中间累加变量换成更宽的类型（例如 "
            "`typedef ap_fixed<64,32> t_acc;` 并用它累积，最后再转回 t_ap_fixed），"
            "或者调整算法避免数值增长（如先归一化、提取公因子）。"
        )
    else:
        lines.append(
            "请检查：算法是否与题目描述一致；定点运算下除法/开方的次数是否过多"
            "（数学等价的公式在定点下误差可能差几个数量级，参考实现通常先归一化再点积）。"
        )
    return "\n".join(lines)


# 尝试优劣排序用的级别序列（与 Grade.highest 返回的字符串一致）
_LEVEL_ORDER = ("未开始", "可解析", "可编译", "可运行", "可综合")


def _attempt_rank(att: Attempt) -> tuple:
    """给一次尝试打分，用来挑出「最好的一次」。

    同级别时优先选数值也对的那次（dump_ok）。

    为什么需要：重试未必越改越好。实测 polybench__gramschmidt 的第 1、2 次
    尝试都生成了带 #include 的完整实现（第 2 次已能跑通，只是数值不符），
    第 3 次模型却把代码改坏了（漏 include、参数个数不对）。若按"最后一次"
    判定，这道题会被记成「可解析」——比它的真实水平低两级，
    而且 run.sh 拷出去的交付产物还是那份坏代码。
    """
    if att.result is None:
        return (0, 0, att.index)
    try:
        lvl = _LEVEL_ORDER.index(att.result.grade.highest)
    except ValueError:
        lvl = 0
    # 第三项用尝试序号兜底：级别完全相同时取更靠后的那次——
    # 它的失败原因更能代表"最终卡在哪"
    return (lvl, 1 if att.dump_ok else 0, att.index)


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
    # 结构化失败类别（见 hls_agent/errors.py）。空串表示本次没有失败。
    failure_kind: str = ""
    failure_detail: str = ""
    return_code: Optional[int] = None
    code_hash: str = ""

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
    # 最终判定用的失败类别，以及「每次尝试分别卡在哪」
    failure_kind: str = ""
    failure_detail: str = ""
    # 最优尝试的代码指纹与返回码（供评测记录使用）
    code_hash: str = ""
    return_code: Optional[int] = None

    @property
    def passed(self) -> bool:
        """严格口径：可运行 且 数值与参考一致。

        官方评测只认 csim 返回码，但 dump 型 testbench 不检查数值，
        功能错误的代码也会「可运行」。作为参赛队要保证功能正确，
        所以把 dump 比对纳入通过条件（config.strict_dump=False 可关闭）。
        """
        return bool(self.grade.run and self.dump_ok)

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
        tb_sources=[task.tb_name],
        # testbench 用相对路径读的数据文件（MachSuite 的 input.data/check.data），
        # 运行时必须先搬进 csim build 目录
        stage_files=[f.name for f in task.tb_data],
    )

    report = TaskReport(task=task, project_dir=workdir, mode=mode)
    ref_dump = load_reference_dump(task)
    # 容差按题目数值类型定：浮点/定点用相对容差，纯整数用精确比较
    tol = dump_tolerance(task)
    # 参考实现自身的偏差量级，只用于诊断提示（不是容差，见 load_reference_error）
    ref_err = load_reference_error(task)

    if client is None:
        from .config import LLMConfig

        client = LLMClient(LLMConfig.from_env())
        # auto 模式可能自动换用了别的模型（配置里的名字在当前服务上不存在），
        # 这属于需要用户知道的变化，显式打出来
        note = getattr(client.backend, "note", "")
        if note:
            print(f"  [模型] {note}", flush=True)

    # 重试可换用更大的模型：首次用小模型求快，失败后换大模型求准。
    # 多数题第一次就过，所以快速路径占主导；难题才付大模型的代价。
    retry_client = None
    if cfg.llm.retry_model and cfg.llm.retry_model != client.backend.model:
        rc = LLMConfig.from_env()
        rc.model = cfg.llm.retry_model
        try:
            retry_client = LLMClient(rc)
            if verbose:
                print(f"  [模型] 重试将换用 {retry_client.backend.model}", flush=True)
        except Exception:
            retry_client = None

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
    prev_hash = ""
    last_truncated = False
    use_skill = mode != "baseline"

    # 技能包知识按题目实际用的数值类型组合：定点规则只在该题确实用 ap_fixed 时注入。
    # 无条件注入会让 double 类型的内核被引导去规避 double，实测反而退步。
    uses_fixed_point = "ap_fixed" in task.header_src
    skill_system = prompts.build_agent_skill_system(uses_fixed_point) if use_skill else ""

    for i in range(1, max_attempts + 1):
        att = Attempt(index=i)

        t_gen = time.time()
        try:
            # 第一次尝试用低温度求稳；重试时提高温度增加多样性，
            # 避免模型在同一个错误上打转
            retry_temp = None if i == 1 else 0.7
            # 思考预算按上一轮是否被截断决定，见 _retry_thinking
            retry_thinking = _retry_thinking(i, last_truncated)

            # 模型调用期间没有任何输出，本地大模型可能要等几分钟，
            # 不提示会被误认为卡死
            if verbose:
                print(
                    f"  [{i}/{max_attempts}] 调用模型生成中……"
                    f"（本地大模型首次要约 1~3 分钟，请勿 Ctrl+C）",
                    flush=True,
                )

            # 重试时换用更大的模型（若配置了 HLS_AGENT_RETRY_MODEL）
            active = retry_client if (i > 1 and retry_client is not None) else client
            raw = active.complete(
                system=skill_system,
                messages=[{"role": "user", "content": prompt}],
                temperature=retry_temp,
                thinking=retry_thinking,
            )
            (workdir / f"raw_llm_output_{i}.txt").write_text(raw, encoding="utf-8", newline="\n")

            # 打印本次生成的耗时构成——定位"慢在读提示词还是写代码"
            st = active.last_stats
            if verbose and st:
                bits = []
                if st.get("load_s", 0) > 2:
                    bits.append(f"模型加载 {st['load_s']:.0f}s")
                if st.get("prompt_tokens"):
                    bits.append(f"提示词 {st['prompt_tokens']} tok/{st.get('prefill_s', 0):.1f}s")
                if st.get("output_tokens"):
                    bits.append(f"输出 {st['output_tokens']} tok/{st.get('decode_s', 0):.1f}s")
                if st.get("tok_per_s"):
                    bits.append(f"{st['tok_per_s']:.1f} tok/s")
                if bits:
                    print(f"           生成明细: {'; '.join(bits)}", flush=True)

            att.code = extract_source(raw, task.source_name, task.top)
        except Exception as e:
            att.generation_error = str(e)
            att.failure_kind = err.classify_generation_error(e)
            att.failure_detail = str(e)[:200]
            # 记下"这一轮是不是被截断了"：下一轮的重试策略要据此调整
            last_truncated = isinstance(e, OutputTruncated)
            report.gen_time_s += time.time() - t_gen
            report.attempts.append(att)
            if verbose:
                tag = err.describe(att.failure_kind)
                print(f"  [尝试 {i}] 生成失败（{tag}）：{str(e)[:160]}")
            # 生成阶段失败也值得重试，但要用对应的话术：
            #   输出被截断 -> 只要求它把代码重新完整输出一遍，别再写分析
            #   其他格式问题 -> 同样走纯格式重试
            if use_skill and i < max_attempts:
                if isinstance(e, OutputTruncated) and verbose:
                    print(
                        "            这次输出被截断（正文写到一半就到 token 上限），"
                        "已跳过 Vitis，直接要求重新输出完整代码",
                        flush=True,
                    )
                prompt = prompts.build_format_retry_prompt(
                    base_prompt, str(e), task.source_name
                )
                continue
            break
        report.gen_time_s += time.time() - t_gen
        last_truncated = False
        att.code_hash = hashlib.sha1(att.code.encode("utf-8")).hexdigest()[:12]

        # 可解析：模型输出的代码被成功提取，且包含顶层函数名
        parse_ok = bool(att.code.strip()) and task.top in att.code
        (workdir / task.source_name).write_text(att.code, encoding="utf-8", newline="\n")
        (workdir / f"attempt_{i}_{task.source_name}").write_text(
            att.code, encoding="utf-8", newline="\n"
        )

        if not parse_ok:
            att.result = HlsResult(project_dir=workdir, grade=Grade(parse=False, compile=False, run=False))
            att.failure_kind = err.SIGNATURE_ERROR
            att.failure_detail = (
                f"抽出的代码里找不到顶层函数 {task.top}（模型实现错了目标函数）"
            )
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

        # ---- 静态预检：毫秒级，阻断项直接回灌重试，省掉一次 Vitis 往返（~20s）----
        from .static_check import check as static_check

        sc = static_check(att.code, workdir / task.header_name, task.top)
        if not sc.ok:
            att.result = HlsResult(project_dir=workdir, grade=Grade(parse=True, compile=False, run=False))
            att.failure_kind = (
                err.SIGNATURE_ERROR
                if any("参数个数" in b or "参数类型" in b for b in sc.blockers)
                else err.STATIC_CHECK_ERROR
            )
            att.failure_detail = "; ".join(sc.blockers)[:300]
            report.attempts.append(att)
            if not use_skill:
                break
            if verbose:
                for line in sc.render().splitlines()[:6]:
                    print(f"    {line}")
            prompt = prompts.build_retry_prompt(
                base_prompt,
                sc.retry_hint(task.top, task.header_name),
                att.code,
                task.source_name,
            )
            continue

        # ---- 编译 + 仿真 ----
        if verbose:
            print(f"  [尝试 {i}] 编译并运行 testbench ...", flush=True)
        clean_build(paths)
        res = run_csim(
            paths, cfg.vitis_run, cfg.part, cfg.clock_ns,
            cfg.csim_timeout_s, cfg.compile_timeout_s,
        )
        res.grade.parse = True
        res.grade.compile = bool(res.compile and res.compile.ok)
        res.grade.run = bool(res.run and res.run.ok)

        att.result = res
        # 注意：综合（csynth）不在这里跑——它很慢（本地约 200s），
        # 若本次尝试注定要重试（数值不符），跑了也是白跑。
        # 挪到数值比对通过之后执行，见下方。

        # ---- 环境受限：Windows 缺数学库运行时 DLL（裸 sqrt / hls::sqrt 触发）----
        # 0xC0000135 (STATUS_DLL_NOT_FOUND) 且无任何输出 = 进程在执行用户代码前
        # 就退出了。**这不代表环境不可用**：实测同一台机器上，同一道题写成
        # 手写内联开方就能跑通（polybench__cholesky / __correlation 通过），
        # 写成裸 `sqrt()` 就必崩（polybench__gramschmidt / pp4fpga_cordic 复现）。
        # 所以这里不能一断了之，而是把"改用内联数学函数"这个可执行的修法
        # 明确告诉模型再试一次；只有额度用尽才停。
        env_limited = (
            res.run is not None
            and res.run.return_code == 3221225781
            and not (res.run.stdout or res.run.stderr)
        )
        if env_limited:
            tb_blocked = _tb_needs_mathlib(task)
            att.failure_kind = err.ENVIRONMENT_ERROR
            att.failure_detail = (
                "csim.exe 缺少数学库运行时 DLL（0xC0000135），零输出退出"
                + ("；触发点在测试台，非模型可修复" if tb_blocked else
                   "；触发点在内核，可改用内联实现")
            )
            att.return_code = res.run.return_code
            att.dump_ok, att.dump_detail = True, ""
            report.attempts.append(att)
            if tb_blocked:
                # 测试台由数据集提供、不可修改，模型再怎么改内核也跑不起来。
                # 这是 Windows 开发机的硬限制，Linux 评测环境没有这个问题——
                # 不要在这种题上浪费重试额度（见 skill/pitfalls.md 第 15 条）。
                if verbose:
                    print(
                        "  [环境] 这道题的**测试台**调用了数学库函数（测试台不可修改），"
                        "本机 Vitis 缺该 DLL，属于 Windows 硬限制；"
                        "Linux 评测环境无此问题。已停止重试。",
                        flush=True,
                    )
                break
            if verbose:
                print(
                    "  [环境] csim.exe 因缺少数学库运行时 DLL 无法启动"
                    "（内核里用了 sqrt()/std::sqrt() 等）。"
                    "这不是环境不可用——改成手写内联实现就能跑通"
                    "（同类题 cholesky/correlation 手写 my_sqrt 时均通过），"
                    "已带着这条指示重试。",
                    flush=True,
                )
            if not use_skill or i >= max_attempts:
                break
            prompt = prompts.build_retry_prompt(
                base_prompt,
                _mathlib_dll_hint(res),
                att.code,
                task.source_name,
            )
            prev_code, prev_hash = att.code, att.code_hash
            continue

        # ---- 数值比对 ----
        if res.grade.run and ref_dump:
            att.dump_ok, att.dump_detail = compare_dumps(res.dumps, ref_dump, tol)
            if not att.dump_ok:
                att.dump_detail = _dump_mismatch_detail(res.dumps, ref_dump, tol)
                if verbose and ref_err:
                    print(
                        f"           （数据集里参考实现自身的偏差量级为 {ref_err:.3g}，"
                        f"仅供参考，不作为判定容差）",
                        flush=True,
                    )
        else:
            att.dump_ok, att.dump_detail = True, ""

        # ---- 归类本次尝试卡在哪一步（按先后顺序，不越级）----
        if not res.grade.compile:
            att.failure_kind = err.classify_compile(
                return_code=res.compile.return_code if res.compile else -1,
                log=res.log,
                timeout=bool(res.compile and res.compile.timeout),
                exe_missing=bool(
                    res.compile and res.compile.ok and not paths.csim_exe.is_file()
                ),
            )
            att.failure_detail = error_excerpt(res)[:300]
            att.return_code = res.compile.return_code if res.compile else None
        elif not res.grade.run:
            att.failure_kind = err.classify_run(
                return_code=res.run.return_code if res.run else -1,
                stdout=res.run.stdout if res.run else "",
                stderr=res.run.stderr if res.run else "",
                timeout=bool(res.run and res.run.timeout),
            )
            att.failure_detail = error_excerpt(res)[:300]
            att.return_code = res.run.return_code if res.run else None
        elif not att.dump_ok:
            att.failure_kind = err.TEST_MISMATCH
            att.failure_detail = att.dump_detail[:300]

        # 通过条件：可运行 +（严格模式）数值一致
        passed = res.grade.run and (att.dump_ok or not cfg.strict_dump)

        # ---- 综合：只在前三级都过了才跑 ----
        # csynth 很慢（本地约 200s），而失败题必然要重试——先跑综合等于白付一次。
        # 放在这里，失败题每次省下约 200s；只有「有可能通过」的那次才付这个代价。
        if do_synth and passed:
            if verbose:
                print(f"  [尝试 {i}] 综合中（较慢，约 1~3 分钟）...", flush=True)
            synth_res = run_synth(
                paths, cfg.vitis_run, cfg.part, cfg.clock_ns, cfg.csynth_timeout_s
            )
            res.synth = synth_res
            res.synth_log = synth_res.stdout + synth_res.stderr + get_synth_log(paths)
            res.synth_report = find_synth_report(paths)
            res.grade.synth = synth_res.ok
            passed = synth_res.ok  # 综合失败同样要重试
            if not synth_res.ok:
                att.failure_kind = err.classify_synth(
                    return_code=synth_res.return_code,
                    log=res.synth_log,
                    timeout=synth_res.timeout,
                )
                att.failure_detail = error_excerpt(res)[:300]
                if verbose:
                    print(f"  [{i}] 综合失败（耗时 {synth_res.elapsed_s:.0f}s），准备重试", flush=True)

        report.attempts.append(att)

        if passed:
            break
        if not use_skill:
            break

        # ---- 无效重试拦截：模型原样返回上一版代码时，不要再付一次 Vitis ----
        # 实测 dfadd 的第 2、3 次尝试产出的是一模一样的残片，
        # 每次都白付一遍编译+仿真。代码没变就不可能有不同的结果。
        if att.code_hash and att.code_hash == prev_hash:
            if verbose:
                print(
                    f"  [{i}/{max_attempts}] 模型返回的代码与上一版完全相同，"
                    f"跳过 Vitis，直接要求它真的做出修改",
                    flush=True,
                )
            errs = error_excerpt(res)
            if not att.dump_ok:
                errs = att.dump_detail + "\n" + errs
            prompt = prompts.build_no_progress_prompt(
                base_prompt, errs, att.code, task.source_name
            )
            prev_code, prev_hash = att.code, att.code_hash
            continue

        # 明确说出为什么重试——否则总墙钟翻倍时看不出原因
        if verbose:
            why = err.describe(att.failure_kind) if att.failure_kind else "未通过"
            print(
                f"  [{i}/{max_attempts}] 未通过（{why}），重试中……",
                flush=True,
            )

        errs = error_excerpt(res)
        if not att.dump_ok:
            errs = att.dump_detail + "\n" + errs
        prev_code = att.code
        prev_hash = att.code_hash
        prompt = prompts.build_retry_prompt(base_prompt, errs, prev_code, task.source_name)

    # ---- 收尾：按「最好的一次尝试」出报告，并把那份代码作为最终交付产物 ----
    # 不能用最后一次：重试未必越改越好，实测 gramschmidt 第 3 次反而把代码改坏了
    # （漏 include、参数个数不对），按最后一次判定会把这道题从「可运行」记成
    # 「可解析」，run.sh 拷出去的交付产物也会是那份坏代码。
    best = max(report.attempts, key=_attempt_rank) if report.attempts else None
    if best is not None and best.result is not None:
        report.grade = best.result.grade
        report.dumps = best.result.dumps
        report.dump_ok = best.dump_ok
        report.dump_detail = best.dump_detail
        report.failure_kind = best.failure_kind
        report.failure_detail = best.failure_detail
        report.code_hash = best.code_hash
        report.return_code = best.return_code
        if best is not report.attempts[-1] and best.code.strip():
            # 把最优尝试的代码写回最终文件名（run.sh / run_baseline.sh 取的就是它），
            # 各次尝试的 attempt_N_*.cpp 原样保留，便于复核
            (workdir / task.source_name).write_text(
                best.code, encoding="utf-8", newline="\n"
            )
            if verbose:
                print(
                    f"  [产物] 最优尝试是第 {best.index} 次（{best.result.grade.highest}），"
                    f"已把它写回 {task.source_name}；第 {report.attempts[-1].index} 次更差，仅留档",
                    flush=True,
                )

    report.elapsed_s = time.time() - t_start
    return report
