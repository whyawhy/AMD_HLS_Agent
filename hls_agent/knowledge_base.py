"""HLS 标准测试题库。

每个 Problem 描述一道可识别的标准测试题：
  - 关键词 / 强关键词：用于从自然语言题目中识别题目类型
  - params：从题目文本中正则抽取的可变参数（N、位宽、行列数、抽头数……）
  - consts / proto / source / testbench：C++ 模板，用 string.Template 的 $VAR 占位

模板中一律使用 typedef 出来的 ``dtype_t`` 作为数值类型，生成器负责按题目要求
把它解析成 int / float / ap_int<W> / ap_fixed<W,I>。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

# --------------------------------------------------------------------------
# 数据模型
# --------------------------------------------------------------------------


@dataclass
class ParamSpec:
    """单个可抽取参数的规则。

    优先使用 ``resolver``（用于需要跨字段解析的场景，如 "3x4" 里的两个维度），
    解析失败返回 None 时再依次尝试 ``patterns``，最后回落到 ``default``。
    """

    name: str
    default: Any
    patterns: List[str] = field(default_factory=list)  # 正则，第 1 个捕获组为值
    cast: Callable[[str], Any] = int
    lo: Optional[Any] = None
    hi: Optional[Any] = None
    resolver: Optional[Callable[[str], Any]] = None

    def _accept(self, val: Any) -> bool:
        if val is None:
            return False
        if self.lo is not None and val < self.lo:
            return False
        if self.hi is not None and val > self.hi:
            return False
        return True

    def extract(self, text: str) -> Any:
        if self.resolver is not None:
            try:
                val = self.resolver(text)
            except Exception:
                val = None
            if self._accept(val):
                return val

        for pat in self.patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if not m:
                continue
            try:
                val = self.cast(m.group(1))
            except (ValueError, TypeError, IndexError):
                continue
            if self._accept(val):
                return val

        return self.default


def _dim_pair(text: str, idx: int) -> Optional[int]:
    """从 "3x4" / "3×4" / "8*8" 这类写法中取第 idx 个维度（0 起）。"""
    m = re.search(r"(\d+)\s*[x×*]\s*(\d+)", text)
    if m:
        return int(m.group(idx + 1))
    return None


def _eq_val(text: str, name: str) -> Optional[int]:
    """解析 "M=3" / "N = 4" 这类显式赋值。"""
    m = re.search(rf"\b{re.escape(name)}\s*=\s*(\d+)", text, re.IGNORECASE)
    return int(m.group(1)) if m else None


@dataclass
class Problem:
    """一道标准测试题的完整定义。"""

    pid: str  # 英文标识，用作函数名和文件名
    name: str  # 中文题名
    category: str  # 分类
    strong_keywords: List[str]  # 命中 +3 分
    keywords: List[str]  # 命中 +1 分
    params: List[ParamSpec]
    consts: str  # 头文件里的常量定义
    proto: str  # 函数原型
    source: str  # 函数实现
    testbench: str  # testbench（须含 int main）
    default_dtype: str = "int"
    includes: List[str] = field(default_factory=list)  # 额外 include
    pragmas: str = ""  # HLS 优化指令建议
    notes: str = ""  # 验收要点
    derive: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None

    # -- 便捷属性 ---------------------------------------------------------
    @property
    def guard(self) -> str:
        return self.pid.upper() + "_H"

    def defaults(self) -> Dict[str, Any]:
        return {p.name: p.default for p in self.params}

    def extract_params(self, text: str) -> Dict[str, Any]:
        vals = {p.name: p.extract(text) for p in self.params}
        if self.derive:
            vals.update(self.derive(vals))
        return vals


# --------------------------------------------------------------------------
# 通用正则片段
# --------------------------------------------------------------------------

_N = r"(\d+)\s*(?:个)?\s*[点元阶维]"  # "8点" / "16元"
_NUM = r"(\d+)"  # 裸数字
_BW = r"(\d+)\s*(?:位|bit|比特)"  # 位宽


# --------------------------------------------------------------------------
# 题库
# --------------------------------------------------------------------------

PROBLEMS: List[Problem] = []


def _register(p: Problem) -> Problem:
    PROBLEMS.append(p)
    return p


# --- 1. 向量加法 ----------------------------------------------------------
_register(
    Problem(
        pid="vecadd",
        name="向量加法",
        category="算术运算",
        strong_keywords=["向量加法", "矢量加法", "vector add", "vecadd", "逐元素相加"],
        keywords=["加法", "相加", "向量", "数组", "两个数组"],
        params=[
            ParamSpec("N", 16, [rf"长度\s*(?:为|=|:)?\s*{_NUM}", rf"(?:N|LEN)\s*=\s*{_NUM}", _N], lo=1, hi=65536),
        ],
        consts="#define VEC_N $N",
        proto="""void vecadd(const dtype_t a[VEC_N],
            const dtype_t b[VEC_N],
            dtype_t       c[VEC_N]);""",
        source="""void vecadd(const dtype_t a[VEC_N],
            const dtype_t b[VEC_N],
            dtype_t       c[VEC_N]) {
    for (int i = 0; i < VEC_N; ++i) {
        c[i] = a[i] + b[i];
    }
}""",
        testbench="""int main() {
    dtype_t a[VEC_N], b[VEC_N], c[VEC_N];

    for (int i = 0; i < VEC_N; ++i) {
        a[i] = (dtype_t)((i * 3) % 19 - 9);
        b[i] = (dtype_t)((i * 7) % 13 - 6);
    }

    vecadd(a, b, c);

    for (int i = 0; i < VEC_N; ++i) {
        char tag[32];
        sprintf(tag, "c[%d]", i);
        tb_check(tag, (double)c[i], (double)a[i] + (double)b[i]);
    }

    if (g_err) { printf("TEST FAILED: %d mismatch(es)\\n", g_err); return 1; }
    printf("TEST PASSED\\n");
    return 0;
}""",
        pragmas="""#pragma HLS INTERFACE m_axi     port=a  depth=VEC_N offset=slave
#pragma HLS INTERFACE m_axi     port=b  depth=VEC_N offset=slave
#pragma HLS INTERFACE m_axi     port=c  depth=VEC_N offset=slave
#pragma HLS INTERFACE s_axilite port=return""",
        notes="结果逐元素精确相等；整数类型则无容差。",
    )
)


# --- 2. 向量点积 ----------------------------------------------------------
_register(
    Problem(
        pid="dotprod",
        name="向量点积",
        category="算术运算",
        strong_keywords=["点积", "内积", "dot product", "dotprod", "点乘"],
        keywords=["向量", "数组", "乘累加", "乘积累加"],
        params=[
            ParamSpec("N", 16, [rf"长度\s*(?:为|=|:)?\s*{_NUM}", rf"(?:N|LEN)\s*=\s*{_NUM}", _N], lo=1, hi=65536),
        ],
        consts="#define DOT_N $N",
        proto="dtype_t dotprod(const dtype_t a[DOT_N], const dtype_t b[DOT_N]);",
        source="""dtype_t dotprod(const dtype_t a[DOT_N], const dtype_t b[DOT_N]) {
    dtype_t acc = 0;
    for (int i = 0; i < DOT_N; ++i) {
        acc += a[i] * b[i];
    }
    return acc;
}""",
        testbench="""int main() {
    dtype_t a[DOT_N], b[DOT_N];
    double  ref = 0.0;

    for (int i = 0; i < DOT_N; ++i) {
        a[i] = (dtype_t)((i * 3) % 11 - 5);
        b[i] = (dtype_t)((i * 5) % 9 - 4);
        ref += (double)a[i] * (double)b[i];
    }

    dtype_t got = dotprod(a, b);
    tb_check("dotprod", (double)got, ref);

    if (g_err) { printf("TEST FAILED: %d mismatch(es)\\n", g_err); return 1; }
    printf("TEST PASSED\\n");
    return 0;
}""",
        pragmas="""#pragma HLS INTERFACE s_axilite port=return
#pragma HLS INTERFACE m_axi     port=a depth=DOT_N offset=slave
#pragma HLS INTERFACE m_axi     port=b depth=DOT_N offset=slave""",
        notes="累加位宽需足够，避免整数溢出；如需高吞吐可对循环做 PARTITION + PIPELINE。",
    )
)


# --- 3. 矩阵乘法 ----------------------------------------------------------
_register(
    Problem(
        pid="matmul",
        name="矩阵乘法",
        category="矩阵运算",
        strong_keywords=["矩阵乘法", "矩阵相乘", "matrix multiply", "matmul", "矩阵乘"],
        keywords=["矩阵", "乘法", "二维数组", "行列"],
        params=[
            ParamSpec("M", 4, [rf"(?:M|行数?)\s*=\s*{_NUM}"], lo=1, hi=512,
                      resolver=lambda t: _dim_pair(t, 0) or _eq_val(t, "M")),
            ParamSpec("N", 4, [rf"(?:N|列数?)\s*=\s*{_NUM}"], lo=1, hi=512,
                      resolver=lambda t: _dim_pair(t, 1) or _eq_val(t, "N")),
            ParamSpec("K", None, [rf"K\s*=\s*{_NUM}"], lo=1, hi=512),
        ],
        derive=lambda p: {"M": p["M"], "N": p["N"], "K": p["K"] or p["M"]},
        consts="""#define MM_M $M
#define MM_N $N
#define MM_K $K""",
        proto="""void matmul(const dtype_t A[MM_M][MM_K],
            const dtype_t B[MM_K][MM_N],
            dtype_t       C[MM_M][MM_N]);""",
        source="""void matmul(const dtype_t A[MM_M][MM_K],
            const dtype_t B[MM_K][MM_N],
            dtype_t       C[MM_M][MM_N]) {
    for (int i = 0; i < MM_M; ++i) {
        for (int j = 0; j < MM_N; ++j) {
            dtype_t acc = 0;
            for (int k = 0; k < MM_K; ++k) {
                acc += A[i][k] * B[k][j];
            }
            C[i][j] = acc;
        }
    }
}""",
        testbench="""int main() {
    dtype_t A[MM_M][MM_K], B[MM_K][MM_N], C[MM_M][MM_N];

    for (int i = 0; i < MM_M; ++i)
        for (int k = 0; k < MM_K; ++k)
            A[i][k] = (dtype_t)((i * 7 + k * 3) % 13 - 6);

    for (int k = 0; k < MM_K; ++k)
        for (int j = 0; j < MM_N; ++j)
            B[k][j] = (dtype_t)((k * 5 + j * 2) % 11 - 5);

    matmul(A, B, C);

    for (int i = 0; i < MM_M; ++i) {
        for (int j = 0; j < MM_N; ++j) {
            double ref = 0.0;
            for (int k = 0; k < MM_K; ++k)
                ref += (double)A[i][k] * (double)B[k][j];
            char tag[32];
            sprintf(tag, "C[%d][%d]", i, j);
            tb_check(tag, (double)C[i][j], ref);
        }
    }

    if (g_err) { printf("TEST FAILED: %d mismatch(es)\\n", g_err); return 1; }
    printf("TEST PASSED\\n");
    return 0;
}""",
        pragmas="""// 内层 k 循环展开 + 流水，是矩阵乘的经典优化点
#pragma HLS ARRAY_PARTITION variable=A complete dim=2
#pragma HLS ARRAY_PARTITION variable=B complete dim=1
#pragma HLS PIPELINE II=1""",
        notes="标准三重循环实现；重点考察对空间并行（循环展开/数组分割）的理解。",
    )
)


# --- 4. 矩阵转置 ----------------------------------------------------------
_register(
    Problem(
        pid="mat_transpose",
        name="矩阵转置",
        category="矩阵运算",
        strong_keywords=["矩阵转置", "转置", "transpose", "行列互换"],
        keywords=["矩阵", "二维数组", "交换"],
        params=[
            ParamSpec("R", 4, [rf"(?:R|行数?)\s*=\s*{_NUM}"], lo=1, hi=512,
                      resolver=lambda t: _dim_pair(t, 0) or _eq_val(t, "R")),
            ParamSpec("C", 4, [rf"(?:C|列数?)\s*=\s*{_NUM}"], lo=1, hi=512,
                      resolver=lambda t: _dim_pair(t, 1) or _eq_val(t, "C")),
        ],
        consts="""#define TR_R $R
#define TR_C $C""",
        proto="""void mat_transpose(const dtype_t in[TR_R][TR_C],
                   dtype_t       out[TR_C][TR_R]);""",
        source="""void mat_transpose(const dtype_t in[TR_R][TR_C],
                   dtype_t       out[TR_C][TR_R]) {
    for (int r = 0; r < TR_R; ++r) {
        for (int c = 0; c < TR_C; ++c) {
            out[c][r] = in[r][c];
        }
    }
}""",
        testbench="""int main() {
    dtype_t in[TR_R][TR_C], out[TR_C][TR_R];

    for (int r = 0; r < TR_R; ++r)
        for (int c = 0; c < TR_C; ++c)
            in[r][c] = (dtype_t)(r * TR_C + c);

    mat_transpose(in, out);

    for (int r = 0; r < TR_R; ++r) {
        for (int c = 0; c < TR_C; ++c) {
            char tag[32];
            sprintf(tag, "out[%d][%d]", c, r);
            tb_check(tag, (double)out[c][r], (double)in[r][c]);
        }
    }

    if (g_err) { printf("TEST FAILED: %d mismatch(es)\\n", g_err); return 1; }
    printf("TEST PASSED\\n");
    return 0;
}""",
        pragmas="""#pragma HLS ARRAY_PARTITION variable=in  complete dim=2
#pragma HLS ARRAY_PARTITION variable=out complete dim=1""",
        notes="非方阵也须正确；常见的综合陷阱是行缓冲导致的高延迟。",
    )
)


# --- 5. FIR 滤波器 --------------------------------------------------------
_register(
    Problem(
        pid="fir",
        name="FIR 滤波器",
        category="信号处理",
        strong_keywords=["fir", "有限冲激响应", "抽头", "滤波器"],
        keywords=["滤波", "系数", "低通", "高通", "卷积", "信号"],
        params=[
            ParamSpec("TAPS", 8, [rf"{_NUM}\s*(?:阶|抽头|点|tap)", rf"(?:抽头|tap|阶数)\s*(?:为|=|:)?\s*{_NUM}"], lo=1, hi=256),
            ParamSpec("LEN", 64, [rf"(?:样本|长度|len|length)\s*(?:为|=|:)?\s*{_NUM}", rf"LEN\s*=\s*{_NUM}"], lo=1, hi=65536),
        ],
        consts="""#define FIR_TAPS $TAPS
#define FIR_LEN  $LEN""",
        proto="""void fir(const dtype_t  x[FIR_LEN],
         dtype_t        y[FIR_LEN],
         const dtype_t  h[FIR_TAPS]);""",
        source="""void fir(const dtype_t  x[FIR_LEN],
         dtype_t        y[FIR_LEN],
         const dtype_t  h[FIR_TAPS]) {
    dtype_t shift[FIR_TAPS];

    for (int i = 0; i < FIR_TAPS; ++i) {
        shift[i] = 0;              // 移位寄存器清零
    }

    for (int n = 0; n < FIR_LEN; ++n) {
        for (int i = FIR_TAPS - 1; i > 0; --i) {
            shift[i] = shift[i - 1];
        }
        shift[0] = x[n];

        dtype_t acc = 0;
        for (int i = 0; i < FIR_TAPS; ++i) {
            acc += shift[i] * h[i];
        }
        y[n] = acc;
    }
}""",
        testbench="""int main() {
    dtype_t x[FIR_LEN], y[FIR_LEN], h[FIR_TAPS];

    /* 一组简单的低通系数，和比任意值；统一用 double 做参考计算 */
    for (int i = 0; i < FIR_TAPS; ++i)
        h[i] = (dtype_t)((i % 3) + 1);

    for (int n = 0; n < FIR_LEN; ++n)
        x[n] = (dtype_t)((n * 7) % 21 - 10);

    fir(x, y, h);

    for (int n = 0; n < FIR_LEN; ++n) {
        double ref = 0.0;
        for (int i = 0; i < FIR_TAPS; ++i) {
            int idx = n - i;
            double xn = (idx >= 0) ? (double)x[idx] : 0.0;
            ref += xn * (double)h[i];
        }
        char tag[32];
        sprintf(tag, "y[%d]", n);
        tb_check(tag, (double)y[n], ref);
    }

    if (g_err) { printf("TEST FAILED: %d mismatch(es)\\n", g_err); return 1; }
    printf("TEST PASSED\\n");
    return 0;
}""",
        pragmas="""#pragma HLS INTERFACE m_axi     port=x depth=FIR_LEN  offset=slave
#pragma HLS INTERFACE m_axi     port=y depth=FIR_LEN  offset=slave
#pragma HLS INTERFACE m_axi     port=h depth=FIR_TAPS offset=slave
#pragma HLS INTERFACE s_axilite port=return
#pragma HLS ARRAY_PARTITION variable=shift complete
#pragma HLS PIPELINE II=1""",
        notes="初值全零、前 TAPS-1 个输出为部分和，务必与参考模型一致。",
    )
)


# --- 6. 二维卷积 ----------------------------------------------------------
_register(
    Problem(
        pid="conv2d",
        name="二维卷积 (3x3 卷积核)",
        category="图像处理",
        strong_keywords=["二维卷积", "2d卷积", "conv2d", "空间卷积"],
        keywords=["卷积", "图像", "卷积核", "滤波", "3x3"],
        params=[
            ParamSpec("H", 8, [rf"(?:高度|H|行数)\s*(?:为|=|:)?\s*{_NUM}", rf"(\d+)\s*[x×]\s*\d+\s*(?:的)?(?:图像|矩阵)"], lo=1, hi=1024),
            ParamSpec("W", 8, [rf"(?:宽度|W|列数)\s*(?:为|=|:)?\s*{_NUM}", rf"{_NUM}\s*[x×]\s*(\d+)\s*(?:的)?(?:图像|矩阵)"], lo=1, hi=1024),
        ],
        consts="""#define IMG_H $H
#define IMG_W $W
#define KER   3""",
        proto="""void conv2d(const dtype_t in[IMG_H][IMG_W],
            const dtype_t k[KER][KER],
            dtype_t       out[IMG_H][IMG_W]);""",
        source="""void conv2d(const dtype_t in[IMG_H][IMG_W],
            const dtype_t k[KER][KER],
            dtype_t       out[IMG_H][IMG_W]) {
    for (int r = 0; r < IMG_H; ++r) {
        for (int c = 0; c < IMG_W; ++c) {
            dtype_t acc = 0;
            for (int kr = 0; kr < KER; ++kr) {
                for (int kc = 0; kc < KER; ++kc) {
                    int rr = r + kr - 1;
                    int cc = c + kc - 1;
                    if (rr >= 0 && rr < IMG_H && cc >= 0 && cc < IMG_W) {
                        acc += in[rr][cc] * k[kr][kc];
                    }
                }
            }
            out[r][c] = acc;
        }
    }
}""",
        testbench="""int main() {
    dtype_t in[IMG_H][IMG_W], k[KER][KER], out[IMG_H][IMG_W];

    for (int r = 0; r < IMG_H; ++r)
        for (int c = 0; c < IMG_W; ++c)
            in[r][c] = (dtype_t)((r * IMG_W + c) % 17 - 8);

    for (int i = 0; i < KER; ++i)
        for (int j = 0; j < KER; ++j)
            k[i][j] = (dtype_t)((i * KER + j) % 3 - 1);

    conv2d(in, k, out);

    for (int r = 0; r < IMG_H; ++r) {
        for (int c = 0; c < IMG_W; ++c) {
            double ref = 0.0;
            for (int kr = 0; kr < KER; ++kr) {
                for (int kc = 0; kc < KER; ++kc) {
                    int rr = r + kr - 1, cc = c + kc - 1;
                    if (rr >= 0 && rr < IMG_H && cc >= 0 && cc < IMG_W)
                        ref += (double)in[rr][cc] * (double)k[kr][kc];
                }
            }
            char tag[48];
            sprintf(tag, "out[%d][%d]", r, c);
            tb_check(tag, (double)out[r][c], ref);
        }
    }

    if (g_err) { printf("TEST FAILED: %d mismatch(es)\\n", g_err); return 1; }
    printf("TEST PASSED\\n");
    return 0;
}""",
        pragmas="""// 行缓冲 (line buffer) 是本问题的核心优化点
#pragma HLS ARRAY_PARTITION variable=k complete dim=0
#pragma HLS PIPELINE II=1""",
        notes="边界采用零填充 (即越界不参与累加)。若题目要求其他边界策略需相应修改。",
    )
)


# --- 7. 3x3 均值滤波 ------------------------------------------------------
_register(
    Problem(
        pid="mean_filter",
        name="3x3 均值滤波",
        category="图像处理",
        strong_keywords=["均值滤波", "中值滤波", "mean filter", "平滑滤波", "图像平滑"],
        keywords=["滤波", "均值", "平滑", "图像", "3x3", "去噪"],
        params=[
            ParamSpec("H", 8, [rf"(?:高度|H|行数)\s*(?:为|=|:)?\s*{_NUM}", rf"(\d+)\s*[x×]\s*\d+\s*(?:的)?(?:图像|矩阵)"], lo=1, hi=1024),
            ParamSpec("W", 8, [rf"(?:宽度|W|列数)\s*(?:为|=|:)?\s*{_NUM}", rf"{_NUM}\s*[x×]\s*(\d+)\s*(?:的)?(?:图像|矩阵)"], lo=1, hi=1024),
        ],
        consts="""#define MF_H $H
#define MF_W $W
#define MF_K 3
#define MF_DIV 9""",
        proto="""void mean_filter(const dtype_t in[MF_H][MF_W],
                 dtype_t       out[MF_H][MF_W]);""",
        source="""void mean_filter(const dtype_t in[MF_H][MF_W],
                 dtype_t       out[MF_H][MF_W]) {
    for (int r = 0; r < MF_H; ++r) {
        for (int c = 0; c < MF_W; ++c) {
            dtype_t acc = 0;
            for (int dr = -1; dr <= 1; ++dr) {
                for (int dc = -1; dc <= 1; ++dc) {
                    int rr = r + dr;
                    int cc = c + dc;
                    if (rr >= 0 && rr < MF_H && cc >= 0 && cc < MF_W) {
                        acc += in[rr][cc];
                    }
                }
            }
            out[r][c] = (dtype_t)(acc / MF_DIV);
        }
    }
}""",
        testbench="""int main() {
    dtype_t in[MF_H][MF_W], out[MF_H][MF_W];

    for (int r = 0; r < MF_H; ++r)
        for (int c = 0; c < MF_W; ++c)
            in[r][c] = (dtype_t)((r * 13 + c * 7) % 41 + 10);

    mean_filter(in, out);

    for (int r = 0; r < MF_H; ++r) {
        for (int c = 0; c < MF_W; ++c) {
            long long acc = 0;
            for (int dr = -1; dr <= 1; ++dr) {
                for (int dc = -1; dc <= 1; ++dc) {
                    int rr = r + dr, cc = c + dc;
                    if (rr >= 0 && rr < MF_H && cc >= 0 && cc < MF_W)
                        acc += (long long)in[rr][cc];
                }
            }
            char tag[48];
            sprintf(tag, "out[%d][%d]", r, c);
            tb_check(tag, (double)out[r][c], (double)(acc / MF_DIV));
        }
    }

    if (g_err) { printf("TEST FAILED: %d mismatch(es)\\n", g_err); return 1; }
    printf("TEST PASSED\\n");
    return 0;
}""",
        pragmas="""#pragma HLS PIPELINE II=1
// 优化提示：用行缓冲替代整体二维数组访问可大幅节省 BRAM""",
        notes="边界零填充；整数除法为向下取整，参考模型必须与之一致。",
    )
)


# --- 8. 冒泡排序 ----------------------------------------------------------
_register(
    Problem(
        pid="sort_bubble",
        name="冒泡排序",
        category="算法",
        strong_keywords=["冒泡排序", "bubble sort", "排序", "sort"],
        keywords=["排序", "升序", "降序", "交换", "数组"],
        params=[
            ParamSpec("N", 16, [rf"长度\s*(?:为|=|:)?\s*{_NUM}", rf"(?:N|LEN)\s*=\s*{_NUM}", _N], lo=1, hi=4096),
            ParamSpec("order", "asc", [r"(降序|从大到小|递减)"], cast=lambda s: "desc"),
        ],
        derive=lambda p: {"SORT_DESC": 1 if p.get("order") == "desc" else 0},
        consts="""#define SORT_N    $N
#define SORT_DESC $SORT_DESC""",
        proto="void sort_bubble(dtype_t a[SORT_N]);",
        source="""void sort_bubble(dtype_t a[SORT_N]) {
    for (int i = 0; i < SORT_N - 1; ++i) {
        for (int j = 0; j < SORT_N - 1 - i; ++j) {
#if SORT_DESC
            int need_swap = (a[j] < a[j + 1]);
#else
            int need_swap = (a[j] > a[j + 1]);
#endif
            if (need_swap) {
                dtype_t t = a[j];
                a[j]     = a[j + 1];
                a[j + 1] = t;
            }
        }
    }
}""",
        testbench="""int main() {
    dtype_t a[SORT_N];
    double  ref[SORT_N];

    for (int i = 0; i < SORT_N; ++i) {
        /* 固定的伪随机序列，保证可复现 */
        int v = (i * 37 + 11) % 101 - 50;
        a[i]   = (dtype_t)v;
        ref[i] = (double)v;
    }

    sort_bubble(a);

    for (int i = 0; i < SORT_N; ++i) {
        for (int j = i + 1; j < SORT_N; ++j) {
            double x = ref[i], y = ref[j];
#if SORT_DESC
            if (x < y) { double t = ref[i]; ref[i] = ref[j]; ref[j] = t; }
#else
            if (x > y) { double t = ref[i]; ref[i] = ref[j]; ref[j] = t; }
#endif
        }
    }

    for (int i = 0; i < SORT_N; ++i) {
        char tag[32];
        sprintf(tag, "a[%d]", i);
        tb_check(tag, (double)a[i], ref[i]);
    }

    if (g_err) { printf("TEST FAILED: %d mismatch(es)\\n", g_err); return 1; }
    printf("TEST PASSED\\n");
    return 0;
}""",
        pragmas="""#pragma HLS PIPELINE II=1
// 优化提示：内层循环加 PIPELINE，或改用奇偶转置排序以获得更好并行度""",
        notes="升序/降序由题目文本决定；比较与交换的稳定性不影响整数结果。",
    )
)


# --- 9. 数组求和 ----------------------------------------------------------
_register(
    Problem(
        pid="array_sum",
        name="数组求和 / 累加",
        category="算术运算",
        strong_keywords=["数组求和", "求和", "累加和", "总和", "之和", "所有元素相加", "sum of array", "array_sum"],
        keywords=["累加", "求和", "数组", "统计", "元素"],
        params=[
            ParamSpec("N", 32, [rf"长度\s*(?:为|=|:)?\s*{_NUM}", rf"(?:N|LEN)\s*=\s*{_NUM}", _N], lo=1, hi=65536),
        ],
        consts="#define SUM_N $N",
        proto="dtype_t array_sum(const dtype_t a[SUM_N]);",
        source="""dtype_t array_sum(const dtype_t a[SUM_N]) {
    dtype_t acc = 0;
    for (int i = 0; i < SUM_N; ++i) {
        acc += a[i];
    }
    return acc;
}""",
        testbench="""int main() {
    dtype_t a[SUM_N];
    double  ref = 0.0;

    for (int i = 0; i < SUM_N; ++i) {
        a[i] = (dtype_t)((i * 13) % 23 - 11);
        ref += (double)a[i];
    }

    tb_check("array_sum", (double)array_sum(a), ref);

    if (g_err) { printf("TEST FAILED: %d mismatch(es)\\n", g_err); return 1; }
    printf("TEST PASSED\\n");
    return 0;
}""",
        pragmas="""#pragma HLS PIPELINE II=1
// 高吞吐版本：树形归约 (tree reduction)
// 例：每周期读 4 个数，两级加法树，II=1""",
        notes="考察定点/整数累加的位宽增长问题。",
    )
)


# --- 10. 最大值 / 最小值 --------------------------------------------------
_register(
    Problem(
        pid="minmax",
        name="数组最大值最小值",
        category="算术运算",
        strong_keywords=["最大值最小值", "最大最小值", "极值", "minmax", "求最大", "求最小"],
        keywords=["最大值", "最小值", "数组", "比较", "峰值"],
        params=[
            ParamSpec("N", 32, [rf"长度\s*(?:为|=|:)?\s*{_NUM}", rf"(?:N|LEN)\s*=\s*{_NUM}", _N], lo=1, hi=65536),
        ],
        consts="#define MX_N $N",
        proto="""void minmax(const dtype_t a[MX_N],
            dtype_t*      minv,
            dtype_t*      maxv);""",
        source="""void minmax(const dtype_t a[MX_N],
            dtype_t*      minv,
            dtype_t*      maxv) {
    dtype_t lo = a[0];
    dtype_t hi = a[0];

    for (int i = 1; i < MX_N; ++i) {
        if (a[i] < lo) lo = a[i];
        if (a[i] > hi) hi = a[i];
    }

    *minv = lo;
    *maxv = hi;
}""",
        testbench="""int main() {
    dtype_t a[MX_N], lo = 0, hi = 0;

    for (int i = 0; i < MX_N; ++i)
        a[i] = (dtype_t)((i * 29 + 5) % 97 - 48);

    minmax(a, &lo, &hi);

    double ref_lo = (double)a[0], ref_hi = (double)a[0];
    for (int i = 1; i < MX_N; ++i) {
        if ((double)a[i] < ref_lo) ref_lo = (double)a[i];
        if ((double)a[i] > ref_hi) ref_hi = (double)a[i];
    }

    tb_check("min", (double)lo, ref_lo);
    tb_check("max", (double)hi, ref_hi);

    if (g_err) { printf("TEST FAILED: %d mismatch(es)\\n", g_err); return 1; }
    printf("TEST PASSED\\n");
    return 0;
}""",
        pragmas="""#pragma HLS INTERFACE s_axilite port=minv
#pragma HLS INTERFACE s_axilite port=maxv
#pragma HLS INTERFACE s_axilite port=return
#pragma HLS INTERFACE m_axi     port=a depth=MX_N offset=slave""",
        notes="指针参数在 HLS 中映射为寄存器接口（s_axilite），不是存储器。",
    )
)


# --- 11. RGB 转灰度 -------------------------------------------------------
_register(
    Problem(
        pid="rgb2gray",
        name="RGB 转灰度",
        category="图像处理",
        strong_keywords=["rgb转灰度", "灰度转换", "rgb2gray", "转灰度", "灰度化", "灰度图", "灰度图像"],
        keywords=["rgb", "灰度", "图像", "像素", "亮度", "ycbcr", "彩色"],
        params=[
            ParamSpec("N", 64, [rf"(?:像素数?|长度)\s*(?:为|=|:)?\s*{_NUM}", rf"{_NUM}\s*个?\s*像素", rf"(?:N|LEN)\s*=\s*{_NUM}"], lo=1, hi=1 << 22),
        ],
        default_dtype="unsigned char",
        consts="#define PIX_N $N",
        proto="""void rgb2gray(const unsigned char r[PIX_N],
             const unsigned char g[PIX_N],
             const unsigned char b[PIX_N],
             unsigned char       y[PIX_N]);""",
        source="""void rgb2gray(const unsigned char r[PIX_N],
             const unsigned char g[PIX_N],
             const unsigned char b[PIX_N],
             unsigned char       y[PIX_N]) {
    /* ITU-R BT.601 亮度公式的定点近似:
       Y = 0.299R + 0.587G + 0.114B
         ~= (77*R + 150*G + 29*B) >> 8
       系数和 77+150+29 = 256，移位不会产生增益误差 */
    for (int i = 0; i < PIX_N; ++i) {
        int acc = 77 * (int)r[i] + 150 * (int)g[i] + 29 * (int)b[i];
        y[i] = (unsigned char)(acc >> 8);
    }
}""",
        testbench="""int main() {
    static unsigned char r[PIX_N], g[PIX_N], b[PIX_N], y[PIX_N];

    for (int i = 0; i < PIX_N; ++i) {
        r[i] = (unsigned char)((i * 7) % 256);
        g[i] = (unsigned char)((i * 13) % 256);
        b[i] = (unsigned char)((i * 29) % 256);
    }

    rgb2gray(r, g, b, y);

    for (int i = 0; i < PIX_N; ++i) {
        int acc = 77 * (int)r[i] + 150 * (int)g[i] + 29 * (int)b[i];
        char tag[32];
        sprintf(tag, "y[%d]", i);
        tb_check(tag, (double)y[i], (double)(acc >> 8));
    }

    if (g_err) { printf("TEST FAILED: %d mismatch(es)\\n", g_err); return 1; }
    printf("TEST PASSED\\n");
    return 0;
}""",
        pragmas="""#pragma HLS INTERFACE m_axi     port=r depth=PIX_N offset=slave
#pragma HLS INTERFACE m_axi     port=g depth=PIX_N offset=slave
#pragma HLS INTERFACE m_axi     port=b depth=PIX_N offset=slave
#pragma HLS INTERFACE m_axi     port=y depth=PIX_N offset=slave
#pragma HLS INTERFACE s_axilite port=return
#pragma HLS PIPELINE II=1""",
        notes="采用 BT.601 定点近似，系数和恰为 256；若题目指定浮点公式请改回 0.299/0.587/0.114。",
    )
)


# --- 12. 校验和 -----------------------------------------------------------
_register(
    Problem(
        pid="checksum",
        name="累加校验和",
        category="数据通路",
        strong_keywords=["校验和", "checksum", "累加校验", "checksum8"],
        keywords=["校验", "字节", "和", "数据包"],
        params=[
            ParamSpec("N", 64, [rf"(?:长度|字节数|len)\s*(?:为|=|:)?\s*{_NUM}", rf"{_NUM}\s*字节", rf"(?:N|LEN)\s*=\s*{_NUM}"], lo=1, hi=1 << 22),
        ],
        default_dtype="unsigned char",
        consts="#define CS_N $N",
        proto="unsigned int checksum(const unsigned char data[CS_N]);",
        source="""unsigned int checksum(const unsigned char data[CS_N]) {
    unsigned int sum = 0;
    for (int i = 0; i < CS_N; ++i) {
        sum += (unsigned int)data[i];
    }
    return sum & 0xFFFFu;   /* 16 位截断校验和 */
}""",
        testbench="""int main() {
    static unsigned char data[CS_N];

    for (int i = 0; i < CS_N; ++i)
        data[i] = (unsigned char)((i * 31 + 7) % 256);

    unsigned long long ref = 0;
    for (int i = 0; i < CS_N; ++i)
        ref += (unsigned long long)data[i];
    ref &= 0xFFFFu;

    tb_check("checksum", (double)checksum(data), (double)ref);

    if (g_err) { printf("TEST FAILED: %d mismatch(es)\\n", g_err); return 1; }
    printf("TEST PASSED\\n");
    return 0;
}""",
        pragmas="""#pragma HLS INTERFACE m_axi     port=data depth=CS_N offset=slave
#pragma HLS INTERFACE s_axilite port=return
#pragma HLS PIPELINE II=1""",
        notes="按字节累加后取低 16 位；累加器位宽决定是否可能溢出。",
    )
)


# --------------------------------------------------------------------------
# 主频 / 器件默认配置（run.tcl 使用）
# --------------------------------------------------------------------------

DEFAULT_PART = "xc7z020clg400-1"
DEFAULT_CLOCK_NS = 10.0


def get_problem(pid: str) -> Optional[Problem]:
    """按 pid 精确查找；支持大小写不敏感。"""
    key = pid.strip().lower()
    for p in PROBLEMS:
        if p.pid.lower() == key:
            return p
    return None


def list_problems() -> List[Problem]:
    return list(PROBLEMS)
