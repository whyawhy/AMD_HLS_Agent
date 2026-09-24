"""题目识别、参数抽取与数据类型解析。

识别策略：关键词加权打分。强关键词（如"矩阵乘法"）命中得 3 分，弱关键词
（如"矩阵"）得 1 分。取总分最高者；同分时按题库顺序稳定排序。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .knowledge_base import Problem, list_problems


@dataclass
class MatchResult:
    problem: Problem
    score: int
    hits: List[str]
    params: Dict[str, Any]
    dtype: str
    dtype_note: str

    @property
    def pid(self) -> str:
        return self.problem.pid


# --------------------------------------------------------------------------
# 识别
# --------------------------------------------------------------------------


def score_all(text: str) -> List[Tuple[int, Problem, List[str]]]:
    """对所有题目打分，返回按分数降序、题库顺序稳定的列表。"""
    low = text.lower()
    scored: List[Tuple[int, Problem, List[str]]] = []

    for p in list_problems():
        s = 0
        hits: List[str] = []

        for kw in p.strong_keywords:
            if kw.lower() in low:
                s += 3
                hits.append(kw)

        for kw in p.keywords:
            # 已被强关键词覆盖的子串不重复计分
            if kw.lower() in low and not any(kw.lower() in h.lower() for h in hits):
                s += 1
                hits.append(kw)

        scored.append((s, p, hits))

    scored.sort(key=lambda t: -t[0])
    return scored


def match_best(text: str, min_score: int = 1) -> Optional[Tuple[int, Problem, List[str]]]:
    """返回得分最高的题目；低于 min_score 视为无法识别。"""
    ranked = score_all(text)
    if not ranked or ranked[0][0] < min_score:
        return None
    return ranked[0]


def rank(text: str, top_k: int = 3) -> List[Tuple[int, Problem, List[str]]]:
    """返回前 top_k 个候选项（仅保留有分的）。"""
    return [t for t in score_all(text) if t[0] > 0][:top_k]


# --------------------------------------------------------------------------
# 数据类型解析
# --------------------------------------------------------------------------

_BITWIDTH_RE = re.compile(r"(\d+)\s*(?:位|bit|比特)", re.IGNORECASE)
_FIXED_RE = re.compile(
    r"(?:ap_)?fixed\s*<\s*(\d+)\s*,\s*(\d+)\s*>|定点\s*\(?\s*(\d+)\s*[,，]\s*(\d+)",
    re.IGNORECASE,
)

_FLOAT_HINTS = ("浮点", "float", "单精度", "实数", "小数")
_DOUBLE_HINTS = ("双精度", "double")
_FIXED_HINTS = ("定点", "ap_fixed", "fixed")


def resolve_dtype(
    text: str,
    problem: Problem,
    override: Optional[str] = None,
) -> Tuple[str, List[str], str]:
    """决定生成的 C++ 数值类型。

    返回 (类型字符串, 需要追加的 #include 列表, 说明文字)。
    优先级：命令行 override > 题目文本描述 > 题目默认类型。
    """
    low = text.lower()

    # 1) 命令行显式指定
    if override:
        return _normalize_override(override)

    # 2) 定点
    m = _FIXED_RE.search(text)
    if m:
        w = int(m.group(1) or m.group(3))
        i = int(m.group(2) or m.group(4))
        if 0 < i <= w <= 64:
            return f"ap_fixed<{w},{i}>", ["ap_fixed.h"], f"题目指定定点 {w} 位（整数 {i} 位）"

    if any(h in low for h in _FIXED_HINTS):
        return "ap_fixed<16,8>", ["ap_fixed.h"], "题目提到定点数，默认取 ap_fixed<16,8>"

    # 3) 位宽的 ap_int
    m = _BITWIDTH_RE.search(text)
    if m:
        w = int(m.group(1))
        if 0 < w <= 64:
            if w <= 8:
                # 8 位及以下用 C 原生类型，便于跨平台编译
                return "unsigned char" if "无符号" in text else "char", [], f"题目指定 {w} 位，映射为 C 原生类型"
            return f"ap_int<{w}>", ["ap_int.h"], f"题目指定 {w} 位有符号数，使用 ap_int<{w}>"

    # 4) 浮点
    if any(h in low for h in _DOUBLE_HINTS):
        return "double", [], "题目提到双精度浮点"

    if any(h in low for h in _FLOAT_HINTS):
        return "float", [], "题目提到浮点数"

    # 5) 题目默认
    return problem.default_dtype, [], f"未指定类型，采用该题默认类型 {problem.default_dtype}"


def _normalize_override(override: str) -> Tuple[str, List[str], str]:
    o = override.strip()

    if o in ("int", "float", "double", "char", "unsigned char", "short", "long"):
        return o, [], f"命令行指定类型 {o}"

    m = re.fullmatch(r"ap_int\s*<\s*(\d+)\s*>", o, re.IGNORECASE)
    if m:
        return f"ap_int<{int(m.group(1))}>", ["ap_int.h"], f"命令行指定 {o}"

    m = re.fullmatch(r"ap_fixed\s*<\s*(\d+)\s*,\s*(\d+)\s*>", o, re.IGNORECASE)
    if m:
        return f"ap_fixed<{int(m.group(1))},{int(m.group(2))}>", ["ap_fixed.h"], f"命令行指定 {o}"

    # 纯数字视为位宽
    if o.isdigit():
        w = int(o)
        if w <= 64:
            if w <= 8:
                return "char", [], f"命令行指定位宽 {w}，映射为 char"
            return f"ap_int<{w}>", ["ap_int.h"], f"命令行指定位宽 {w}，使用 ap_int<{w}>"

    raise ValueError(
        f"无法识别的数据类型 '{override}'。可用：int / float / double / short / char / "
        f"ap_int<N> / ap_fixed<W,I> / 或一个位宽数字"
    )


# --------------------------------------------------------------------------
# 组合入口
# --------------------------------------------------------------------------


def analyze(text: str, dtype_override: Optional[str] = None) -> MatchResult:
    """识别题目 + 抽取参数 + 解析类型，一次完成。"""
    hit = match_best(text)
    if hit is None:
        raise LookupError("无法识别题目类型")

    score, problem, hits = hit
    params = problem.extract_params(text)
    dtype, inc, note = resolve_dtype(text, problem, dtype_override)

    return MatchResult(
        problem=problem,
        score=score,
        hits=hits,
        params=params,
        dtype=dtype,
        dtype_note=note,
    )


def describe_params(problem: Problem, params: Dict[str, Any]) -> str:
    """把参数渲染成一行人类可读文本。"""
    items = []
    for spec in problem.params:
        if spec.name in params:
            items.append(f"{spec.name}={params[spec.name]}")
    for k, v in params.items():
        if k not in {s.name for s in problem.params}:
            items.append(f"{k}={v}")
    return ", ".join(items) if items else "(无参数)"


def canonical_question(problem: Problem, params: Dict[str, Any]) -> str:
    """为 README 生成一句标准化的中文题目描述。"""
    p = dict(params)

    if problem.pid == "vecadd":
        return f"实现 {p['N']} 点向量加法，输入两个长度为 {p['N']} 的数组，逐元素相加输出。"
    if problem.pid == "dotprod":
        return f"实现 {p['N']} 点向量点积，计算两个长度为 {p['N']} 的数组的乘积累加和。"
    if problem.pid == "matmul":
        if p["M"] == p["N"] == p["K"]:
            return f"实现 {p['M']}x{p['N']} 方阵乘法（内维 {p['K']}）。"
        return f"实现 {p['M']}x{p['K']} 与 {p['K']}x{p['N']} 的矩阵乘法。"
    if problem.pid == "mat_transpose":
        return f"实现 {p['R']}x{p['C']} 矩阵的转置。"
    if problem.pid == "fir":
        return f"实现 {p['TAPS']} 抽头 FIR 滤波器，对长度为 {p['LEN']} 的输入序列滤波。"
    if problem.pid == "conv2d":
        return f"实现 {p['H']}x{p['W']} 图像与 3x3 卷积核的二维卷积（零填充边界）。"
    if problem.pid == "mean_filter":
        return f"实现 {p['H']}x{p['W']} 图像的 3x3 均值滤波（零填充边界，整数除 9）。"
    if problem.pid == "sort_bubble":
        order = "降序" if p.get("order") == "desc" else "升序"
        return f"实现冒泡排序，对长度为 {p['N']} 的数组进行{order}排列。"
    if problem.pid == "array_sum":
        return f"实现长度为 {p['N']} 的数组求和（累加）。"
    if problem.pid == "minmax":
        return f"求长度为 {p['N']} 的数组中的最大值和最小值。"
    if problem.pid == "rgb2gray":
        return f"把 {p['N']} 个 RGB 像素转换为灰度值（BT.601 定点近似）。"
    if problem.pid == "checksum":
        return f"计算 {p['N']} 字节数据的 16 位累加校验和。"

    return f"{problem.name}（{describe_params(problem, params)}）"
