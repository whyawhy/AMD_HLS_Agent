"""失败分类：把"失败了"变成程序能处理的**结构化原因**。

为什么需要：原来只有一句自由文本（`error` 字段只在抛异常时才非空），
评测报告里 24 行失败全写成"编译/仿真未通过，详见 results.json"，
而 results.json 里连返回码都没有。结果就是无法回答"哪些题卡在哪一步、
是不是同一个根因、该不该重试"。工作区又会被下一次评测覆盖，
证据转瞬即逝。

这里把原因收敛成有限几类，每类都给出：是否值得重试、以及对应的修复方向。
分类只依据**真实工具证据**（返回码、有无输出、日志里的具体字样），
不做关键词式的机械替换。
"""

from __future__ import annotations

from typing import List, Optional, Tuple

# --------------------------------------------------------------------------
# 类别
# --------------------------------------------------------------------------

OUTPUT_FORMAT_ERROR = "OUTPUT_FORMAT_ERROR"          # 模型输出格式不对，取不到代码
SOURCE_EXTRACTION_ERROR = "SOURCE_EXTRACTION_ERROR"  # 取到了但不是完整实现（截断/骨架）
SIGNATURE_ERROR = "SIGNATURE_ERROR"                  # 顶层函数签名与头文件不符
STATIC_CHECK_ERROR = "STATIC_CHECK_ERROR"            # 静态预检的高置信阻断
CXX_COMPILE_ERROR = "CXX_COMPILE_ERROR"              # C++ 编译失败
CSIM_BUILD_ERROR = "CSIM_BUILD_ERROR"                # 仿真工程构建失败（无 csim.exe）
CSIM_RUNTIME_ERROR = "CSIM_RUNTIME_ERROR"            # 仿真程序崩溃
TEST_MISMATCH = "TEST_MISMATCH"                      # 测试台/参考输出判定不一致
INPUT_DATA_ERROR = "INPUT_DATA_ERROR"                # 测试输入数据缺失或读不到
TOOL_TIMEOUT = "TOOL_TIMEOUT"                        # Vitis 调用超时
MODEL_TIMEOUT = "MODEL_TIMEOUT"                      # 模型调用超时
MODEL_SERVICE_ERROR = "MODEL_SERVICE_ERROR"          # 模型服务异常
SYNTHESIS_ERROR = "SYNTHESIS_ERROR"                  # 综合失败
RESOURCE_OR_TIMING_ERROR = "RESOURCE_OR_TIMING_ERROR"  # 综合报告里的资源/时序问题
ENVIRONMENT_ERROR = "ENVIRONMENT_ERROR"              # 工具链/动态库/路径/容器问题
UNKNOWN_ERROR = "UNKNOWN_ERROR"

ALL_KINDS: Tuple[str, ...] = (
    OUTPUT_FORMAT_ERROR, SOURCE_EXTRACTION_ERROR, SIGNATURE_ERROR, STATIC_CHECK_ERROR,
    CXX_COMPILE_ERROR, CSIM_BUILD_ERROR, CSIM_RUNTIME_ERROR, TEST_MISMATCH,
    INPUT_DATA_ERROR, TOOL_TIMEOUT, MODEL_TIMEOUT, MODEL_SERVICE_ERROR,
    SYNTHESIS_ERROR, RESOURCE_OR_TIMING_ERROR, ENVIRONMENT_ERROR, UNKNOWN_ERROR,
)

# 值得再试一次的类别。环境类问题重试没有意义——重试前必须先确认工具链是好的，
# 否则会让模型反复重写本来正确的算法（见 OPTIMIZATION_AUDIT.md P2）。
RETRYABLE = frozenset({
    OUTPUT_FORMAT_ERROR, SOURCE_EXTRACTION_ERROR, SIGNATURE_ERROR, STATIC_CHECK_ERROR,
    CXX_COMPILE_ERROR, CSIM_RUNTIME_ERROR, TEST_MISMATCH, SYNTHESIS_ERROR,
    RESOURCE_OR_TIMING_ERROR, CSIM_BUILD_ERROR,
})

# 每一类对应的修复方向（写进评测报告，也用于决定给模型看什么）
REPAIR_HINT = {
    OUTPUT_FORMAT_ERROR: "只要求模型按 <OUTPUT_CODE> 格式重新输出，不重新做算法设计",
    SOURCE_EXTRACTION_ERROR: "输出被截断/只给了骨架；要求只输出完整代码块、不要写分析",
    SIGNATURE_ERROR: "把头文件里的真实顶层函数声明原样贴给模型",
    STATIC_CHECK_ERROR: "把静态预检命中的具体阻断项告诉模型",
    CXX_COMPILE_ERROR: "只给第一条有效编译错误 + 相关代码行",
    CSIM_BUILD_ERROR: "仿真工程没生成可执行文件，检查工程准备阶段",
    CSIM_RUNTIME_ERROR: "给出返回码与崩溃前输出；区分「程序崩了」和「测试台报了不一致」",
    TEST_MISMATCH: "给出参考值/实际值、最大误差位置与饱和迹象",
    INPUT_DATA_ERROR: "输入数据文件缺失或被改坏，属评测设施问题，先修设施",
    TOOL_TIMEOUT: "放宽该阶段超时或先确认工具链可用，不要让模型反复重写算法",
    MODEL_TIMEOUT: "按配置做有限次服务重试",
    MODEL_SERVICE_ERROR: "确认推理服务在线；不得静默切到远程模型",
    SYNTHESIS_ERROR: "按真实综合日志改不可综合构造，不改算法语义",
    RESOURCE_OR_TIMING_ERROR: "按综合报告处理资源/时序，不改算法语义",
    ENVIRONMENT_ERROR: "先诊断工具链（动态库/路径/权限），不要重写算法代码",
    UNKNOWN_ERROR: "保留原始日志交人工复核",
}


def is_retryable(kind: str) -> bool:
    return kind in RETRYABLE


def hint(kind: str) -> str:
    return REPAIR_HINT.get(kind, REPAIR_HINT[UNKNOWN_ERROR])


# --------------------------------------------------------------------------
# 分类器
# --------------------------------------------------------------------------

# Windows: STATUS_DLL_NOT_FOUND。csim.exe 依赖的浮点算子/数学库运行时不在了，
# 进程会在执行任何用户代码之前就退出，表现为"0.1 秒、零输出"。
_DLL_NOT_FOUND = 3221225781
_INPUT_DATA_MARKERS = (
    "Couldn't open input data file",
    "could not open file",
    "No such file or directory",
    "cannot open input",
)


def classify_generation_error(exc: BaseException) -> str:
    """模型调用 / 代码抽取阶段的失败。"""
    name = type(exc).__name__
    text = str(exc)
    if name == "OutputTruncated":
        return SOURCE_EXTRACTION_ERROR
    if name == "LLMError":
        low = text.lower()
        if "timeout" in low or "超时" in low:
            return MODEL_TIMEOUT
        return MODEL_SERVICE_ERROR
    if "timeout" in text.lower() or "timed out" in text.lower():
        return MODEL_TIMEOUT
    if name in ("ValueError", "KeyError") or "没能从模型输出里取到" in text:
        return OUTPUT_FORMAT_ERROR
    return UNKNOWN_ERROR


def classify_compile(return_code: int, log: str, timeout: bool = False,
                     exe_missing: bool = False) -> str:
    """编译 / 仿真工程准备阶段的失败。"""
    if timeout:
        return TOOL_TIMEOUT
    if exe_missing:
        return CSIM_BUILD_ERROR
    if any(m.lower() in log.lower() for m in _INPUT_DATA_MARKERS):
        return INPUT_DATA_ERROR
    if "error:" in log or "ERROR:" in log:
        return CXX_COMPILE_ERROR
    return CXX_COMPILE_ERROR if return_code != 0 else UNKNOWN_ERROR


def _is_windows_exception(rc: int) -> bool:
    """返回码是否是一个 Windows 异常码（而不是程序自己返回的退出码）。

    Windows 的异常码落在 0xC0000000~0xC000FFFF（如 0xC0000005 访问违例、
    0xC0000374 堆损坏、0xC0000135 缺 DLL）。这个区间之外的大数通常是程序
    `return -1` 之类的正常退出——例如测试台把 `exit(-1)` 变成 4294967295。
    不区分这两者，就会把"测试台报不一致"误判成"程序崩溃"。
    """
    return 0xC0000000 <= rc <= 0xC000FFFF


def classify_run(return_code: int, stdout: str, stderr: str, timeout: bool = False) -> str:
    """运行 csim.exe 阶段的失败。"""
    if timeout:
        return TOOL_TIMEOUT
    out = (stdout or "") + (stderr or "")
    if return_code == _DLL_NOT_FOUND and not out.strip():
        # 进程在任何用户代码执行前就因缺 DLL 退出
        return ENVIRONMENT_ERROR
    if any(m.lower() in out.lower() for m in _INPUT_DATA_MARKERS):
        return INPUT_DATA_ERROR
    if _is_windows_exception(return_code):
        # 真崩溃：访问违例 / 堆损坏 / 缺依赖
        return CSIM_RUNTIME_ERROR
    if return_code != 0 and out.strip():
        # 程序完整跑完了（有输出）却返回非零：那是测试台自己判定的不一致。
        # 例：fft_strided 打印 "ERROR: 1010 ..." 后 exit(-1)；
        #     CHStone 把"不匹配用例数"当 main 返回值。
        return TEST_MISMATCH
    if return_code != 0:
        return CSIM_RUNTIME_ERROR
    return UNKNOWN_ERROR


def classify_synth(return_code: int, log: str, timeout: bool = False) -> str:
    if timeout:
        return TOOL_TIMEOUT
    low = log.lower()
    if "timing" in low or "slack" in low:
        return RESOURCE_OR_TIMING_ERROR
    return SYNTHESIS_ERROR


def describe(kind: str) -> str:
    """给报告用的一行中文说明。"""
    return {
        OUTPUT_FORMAT_ERROR: "输出格式错误",
        SOURCE_EXTRACTION_ERROR: "输出被截断 / 只给了骨架",
        SIGNATURE_ERROR: "函数签名不符",
        STATIC_CHECK_ERROR: "静态预检阻断",
        CXX_COMPILE_ERROR: "C++ 编译失败",
        CSIM_BUILD_ERROR: "仿真工程构建失败",
        CSIM_RUNTIME_ERROR: "仿真程序崩溃",
        TEST_MISMATCH: "测试结果不一致",
        INPUT_DATA_ERROR: "测试输入数据问题",
        TOOL_TIMEOUT: "工具调用超时",
        MODEL_TIMEOUT: "模型调用超时",
        MODEL_SERVICE_ERROR: "模型服务异常",
        SYNTHESIS_ERROR: "综合失败",
        RESOURCE_OR_TIMING_ERROR: "综合资源/时序问题",
        ENVIRONMENT_ERROR: "工具链/环境问题",
        UNKNOWN_ERROR: "未分类",
    }.get(kind, "未分类")
