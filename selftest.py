#!/usr/bin/env python3
"""回归自测：覆盖曾经踩过的 bug，改代码后跑一遍防复发。

    python selftest.py

不依赖 pytest，全部用断言 + 打印。任一项失败会以非零码退出。
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

FAILS: list[str] = []


def check(name: str, fn) -> None:
    try:
        fn()
        print(f"  [通过] {name}")
    except AssertionError as e:
        print(f"  [失败] {name}: {e}")
        FAILS.append(name)
    except Exception as e:
        print(f"  [异常] {name}: {type(e).__name__}: {e}")
        FAILS.append(name)


# ---------------------------------------------------------------------------
# 1. 三个后端的接口必须一致
#    （曾经 AnthropicBackend 加了 thinking 参数而 Ollama/OpenAI 没加，
#      开发机上一直走 Anthropic 所以没暴露，到实验室一换 Ollama 就崩）
# ---------------------------------------------------------------------------

def test_backend_signatures_match() -> None:
    from hls_agent.backends import (
        AnthropicBackend, LLMBackend, OllamaBackend, OpenAIBackend,
    )

    base = inspect.signature(LLMBackend.complete)
    base_params = set(base.parameters.keys())
    for cls in (OllamaBackend, OpenAIBackend, AnthropicBackend):
        sig = inspect.signature(cls.complete)
        params = set(sig.parameters.keys())
        missing = base_params - params
        assert not missing, f"{cls.__name__}.complete 缺少参数 {missing}"

    # 构造参数：子类用 **kw 透传给基类，所以检查"能否用基类参数调用"
    common = dict(model="m", max_tokens=64, temperature=0.2, timeout_s=5, thinking="off")
    for cls, kw in (
        (OllamaBackend, {"host": "http://127.0.0.1:11434"}),
        (OpenAIBackend, {"base_url": "http://127.0.0.1:8000"}),
        (AnthropicBackend, {"base_url": "http://x", "api_key": "k"}),
    ):
        cls(**kw, **common)  # 能构造即通过


def test_all_backends_constructible() -> None:
    from hls_agent.backends import AnthropicBackend, OllamaBackend, OpenAIBackend

    common = dict(model="m", max_tokens=64, temperature=0.2, timeout_s=5, thinking="off")
    for cls, kw in (
        (OllamaBackend, {"host": "http://127.0.0.1:11434"}),
        (OpenAIBackend, {"base_url": "http://127.0.0.1:8000"}),
        (AnthropicBackend, {"base_url": "http://x", "api_key": "k"}),
    ):
        b = cls(**kw, **common)
        assert hasattr(b, "note"), f"{cls.__name__} 缺少 note 属性"
        assert callable(b.resolve_model), f"{cls.__name__} 缺少 resolve_model"


def test_ollama_picks_available_model() -> None:
    from hls_agent.backends import OllamaBackend

    lab = ["qwen85b:latest", "qwen2.5-coder-32k:latest",
           "qwen2.5-coder:32b", "qwen2.5-coder:7b"]
    orig = OllamaBackend.list_models
    OllamaBackend.list_models = lambda self: lab  # type: ignore[method-assign]
    try:
        b = OllamaBackend(model="deepseek-v4-pro")
        assert b.available()[0] is False, "模型不在时 available 应为 False"
        picked, note = b.resolve_model()
        assert picked == "qwen2.5-coder:32b", f"应挑 32b，实得 {picked}"
        assert note, "自动换模型时必须给出说明"

        b2 = OllamaBackend(model="qwen2.5-coder:7b")
        assert b2.available()[0] is True
        assert b2.resolve_model() == ("qwen2.5-coder:7b", "")
    finally:
        OllamaBackend.list_models = orig  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# 2. 模型输出的代码抽取（含 XML 转义，曾导致编译失败）
# ---------------------------------------------------------------------------

def test_extract_plain_xml() -> None:
    from hls_agent.llm import extract_source

    text = (
        '<OUTPUT_CODE name="a.cpp">\n'
        "void f() { int x = 1; }\n"
        '</OUTPUT_CODE name="a.cpp">'
    )
    out = extract_source(text, "a.cpp", "f")
    assert "void f()" in out


def test_extract_unescapes_entities() -> None:
    """模型按 XML 语义转义了尖括号，抽取时必须还原（曾致编译失败）。"""
    from hls_agent.llm import extract_source

    text = (
        '<OUTPUT_CODE name="a.cpp">\n'
        "typedef ap_fixed&lt;64, 32&gt; t_acc;\n"
        "void f() { for (int i = 0; i &lt; 8; i++) {} }\n"
        '</OUTPUT_CODE name="a.cpp">'
    )
    out = extract_source(text, "a.cpp", "f")
    assert "&lt;" not in out, "XML 转义未还原"
    assert "ap_fixed<64, 32>" in out


def test_extract_from_markdown_fence() -> None:
    from hls_agent.llm import extract_source

    text = "这是实现：\n```a.cpp\nvoid f() { return; }\n```\n"
    out = extract_source(text, "a.cpp", "f")
    assert "void f()" in out


def test_extract_rejects_truncated_output() -> None:
    """输出被 max_tokens 截断时，绝不能把讲解用的片段当成实现。

    真实案例（dfadd，批次 20261012_130807）：59055 字符的回复里 0 个
    <OUTPUT_CODE> 标签，抽取器回退取到 774 字符、含字面 `...` 的残片，
    这段残片被写进磁盘送去 Vitis，必然失败。
    """
    from hls_agent.llm import OutputTruncated, extract_source

    # (a) 有开标签没闭标签 = 正文写到一半就断了
    partial = '<OUTPUT_CODE name="x.cpp">\nvoid f() { int a = 1;'
    try:
        extract_source(partial, "x.cpp", "f")
        raise AssertionError("截断的输出应当抛 OutputTruncated")
    except OutputTruncated:
        pass

    # (b) 没有 XML 标签、只有含 `...` 的骨架片段
    skeleton = (
        "Let me think about this.\n\n"
        "```cpp\n"
        "float64 float64_add(float64 a, float64 b)\n"
        "{\n"
        "    ...\n"
        "}\n"
        "```\n\n"
        "So the plan is to handle the special cases first."
    )
    try:
        extract_source(skeleton, "x.cpp", "float64_add")
        raise AssertionError("含整行省略号的骨架应当抛 OutputTruncated")
    except OutputTruncated as e:
        assert "省略号" in str(e) or "不完整" in str(e)


def test_extract_accepts_real_code_after_truncation_fix() -> None:
    """修好之后，正常的完整输出必须照常通过（不能误伤）。"""
    from hls_agent.llm import extract_source

    good = (
        '<OUTPUT_CODE name="x.cpp">\n'
        '#include "x.h"\n'
        "static double my_sqrt(double x) { double r = x; return r; }\n"
        "void f(double *a) { a[0] = my_sqrt(a[1]); }\n"
        '</OUTPUT_CODE name="x.cpp">'
    )
    out = extract_source(good, "x.cpp", "f")
    assert "#include" in out and "my_sqrt" in out


def test_retry_prompt_forbids_prose() -> None:
    """重试提示必须要求"只输出代码块"——否则模型又写几千字分析把正文挤没了。"""
    from hls_agent.prompts import build_retry_prompt

    p = build_retry_prompt("BASE", "boom", "void f(){}", "f.cpp")
    assert "Output only the code block" in p, "重试提示没有禁止写分析文字"
    assert "<OUTPUT_CODE" in p


# ---------------------------------------------------------------------------
# 3. 定点饱和检测（±32768 指纹）
# ---------------------------------------------------------------------------

def test_saturation_detection() -> None:
    from hls_agent.runner import _detect_saturation

    assert _detect_saturation([1.0, -32738.3, 2.0]) is not None, "应检出饱和"
    assert _detect_saturation([1.0, 2.0, 3.0]) is None, "正常值不应误报"
    assert _detect_saturation([]) is None


# ---------------------------------------------------------------------------
# 4. 静态预检
# ---------------------------------------------------------------------------

def _tmp_header(dirpath: Path, name: str, body: str) -> Path:
    p = dirpath / name
    p.write_text(body, encoding="utf-8")
    return p


def test_static_check_catches_missing_include(tmp: Path) -> None:
    from hls_agent.static_check import check

    hdr = _tmp_header(tmp, "x.h", "void kernel_x(double a[4]);")
    code = "void kernel_x(double a[4]) { a[0] = 1.0; }"
    res = check(code, hdr, "kernel_x")
    assert not res.ok, "漏 include 应被判为阻断"
    assert any("include" in b for b in res.blockers)


def test_static_check_warns_std_math(tmp: Path) -> None:
    """std:: 数学函数在 Windows 上会链缺失的数学库 DLL。"""
    from hls_agent.static_check import check

    hdr = _tmp_header(tmp, "x.h", "void kernel_x(double*a);")
    code = '#include "x.h"\nvoid kernel_x(double*a){ a[0] = std::sqrt(a[1]); }'
    res = check(code, hdr, "kernel_x")
    assert any("数学函数" in w for w in res.warnings), "未对 std::sqrt 告警"


def test_static_check_accepts_handwritten_sqrt(tmp: Path) -> None:
    from hls_agent.static_check import check

    hdr = _tmp_header(tmp, "x.h", "void kernel_x(double*a);")
    code = (
        '#include "x.h"\n'
        "static double my_sqrt(double x){ double r=x; for(int i=0;i<60;i++) r=0.5*(r+x/r); return r; }\n"
        "void kernel_x(double*a){ a[0] = my_sqrt(a[1]); }"
    )
    res = check(code, hdr, "kernel_x")
    assert not any("数学函数" in w for w in res.warnings), "手写 sqrt 不应告警"


def test_static_check_blocks_macro_typedef_hijack(tmp: Path) -> None:
    """用 #define 改写题目头文件的类型名，必然把 Vitis 自己的头也改坏。

    真实案例：某次生成的 gemver.cpp 第一行就是 `#define ap_fixed MY_AP_FIXED`。
    """
    from hls_agent.static_check import check

    hdr = _tmp_header(tmp, "x.h", '#include "ap_fixed.h"\ntypedef ap_fixed<32,16> t_ap_fixed;\nvoid kernel_x(t_ap_fixed*a);')
    code = '#define t_ap_fixed MY_TYPE\n#include "x.h"\nvoid kernel_x(t_ap_fixed*a){ a[0] = 0; }'
    res = check(code, hdr, "kernel_x")
    assert not res.ok, "宏改写头文件类型名应被判为阻断"
    assert any("t_ap_fixed" in b for b in res.blockers), res.blockers


def test_static_check_blocks_skeleton_ellipsis(tmp: Path) -> None:
    """只写了骨架、用 `...` 略过实现，不能放行到 Vitis。"""
    from hls_agent.static_check import check

    hdr = _tmp_header(tmp, "x.h", "void kernel_x(double*a);")
    code = '#include "x.h"\nvoid kernel_x(double*a){\n    ...\n}\n'
    res = check(code, hdr, "kernel_x")
    assert not res.ok
    assert any("骨架" in b or "省略号" in b for b in res.blockers), res.blockers


# ---------------------------------------------------------------------------
# 5. Vitis 命令行构造（两种入口参数不同）
# ---------------------------------------------------------------------------

def test_vitis_cmd_dispatch() -> None:
    from hls_agent.vitis import _vitis_cmd

    hls = Path("/opt/Xilinx/Vitis/2024.1/bin/vitis_hls")
    old = _vitis_cmd(hls, "r.tcl")
    assert old[0] == str(hls) and old[1] == "-f", f"vitis_hls 参数错: {old}"

    run = Path("/opt/Xilinx/Vitis/2025.2/bin/vitis-run")
    new = _vitis_cmd(run, "r.tcl")
    assert new[0] == str(run) and "--mode" in new and "--tcl" in new, f"vitis-run 参数错: {new}"

    win = Path(r"D:\Xilinx\Vitis\2025.2\bin\vitis-run.bat")
    w = _vitis_cmd(win, "r.tcl")
    assert w[0] == "cmd" and w[1] == "/c", f".bat 未经 cmd 调用: {w}"


def test_synth_tcl_separates_testbench() -> None:
    """综合脚本必须把测试台按 -tb 加入，不能混进设计源文件。"""
    from hls_agent.vitis import TaskPaths, build_synth_tcl

    p = TaskPaths(
        workdir=Path("/w"), build_name="kernel_x", source_name="x.cpp",
        other_sources=["x.h", "x_tb.cpp"], tb_sources=["x_tb.cpp"],
    )
    tcl = build_synth_tcl(p, "part", 5.0)
    assert "add_files x.cpp" in tcl, tcl
    assert "add_files x.h" in tcl, tcl
    assert "add_files -tb x_tb.cpp" in tcl, f"测试台未按 -tb 加入:\n{tcl}"
    assert "\nadd_files x_tb.cpp" not in tcl, f"测试台被当设计文件加入:\n{tcl}"


def test_mathlib_hint_distinguishes_tb_from_kernel() -> None:
    """内核调用数学库 -> 可让模型改写；测试台调用 -> 模型无论如何都修不好。

    pp4fpga_cordic 的 cordic_tb.cpp 直接调用 sin()/cos()，测试台不可修改，
    属于 Windows 硬限制；而 polybench__cholesky 只是内核用了 sqrt，
    手写 my_sqrt 就能通过。两者不能混为一谈。
    """
    from hls_agent import dataset as ds
    from hls_agent.runner import _tb_needs_mathlib

    root = ds.locate_dataset(None)
    if root is None:
        return
    d = ds.HlsEvalDataset(root)

    def find(parent: str, name: str):
        for t in d.tasks():
            if t.root.parent.name == parent and t.root.name == name:
                return t
        return None

    cordic = find("pp4fpga", "pp4fpga_cordic")
    if cordic is not None:
        assert _tb_needs_mathlib(cordic), "cordic 的测试台确实调用了 sin/cos"

    chol = find("polybench", "cholesky")
    if chol is not None:
        assert not _tb_needs_mathlib(chol), "cholesky 的测试台没有数学库调用"


def test_retry_thinking_backs_off_after_truncation() -> None:
    """上一轮被截断时，重试必须关掉思考，先把代码写完。

    实测（dfadd，批次 20261012_130807）：开思考预算后模型输出涨到 51~59KB，
    在写到一半时撞上 max_tokens，两轮重试约 260 秒里连一个 <OUTPUT_CODE>
    标签都没产出。思考 token 和正文抢的是同一份预算。
    """
    from hls_agent.runner import _retry_thinking

    assert _retry_thinking(1, last_truncated=False) is None      # 首轮不给思考
    assert _retry_thinking(1, last_truncated=True) is None       # 首轮同样不给
    assert _retry_thinking(2, last_truncated=False) == "budget:2048"
    assert _retry_thinking(3, last_truncated=False) == "budget:2048"
    assert _retry_thinking(2, last_truncated=True) == "off"      # 退让
    assert _retry_thinking(3, last_truncated=True) == "off"


def test_best_attempt_beats_last_attempt() -> None:
    """重试未必越改越好，报告的应是**最好**的一次，交付产物也用它。

    真实案例：polybench__gramschmidt 第 1、2 次尝试都生成了带 #include 的完整
    实现（第 2 次已能跑通，只是数值不符），第 3 次模型把代码改坏了。按"最后一次"
    判定会把这道题从「可运行」记成「可解析」，并把坏代码当成交付产物。
    """
    from hls_agent.runner import Attempt, _attempt_rank
    from hls_agent.vitis import Grade, HlsResult

    def att(i, grade, dump_ok=True):
        a = Attempt(index=i, code=f"code{i}", dump_ok=dump_ok)
        a.result = HlsResult(project_dir=Path("/w"), grade=grade)
        return a

    gen_fail = Attempt(index=1)  # 连代码都没抽出来
    parse_only = att(2, Grade(parse=True, compile=False, run=False))
    run_ok = att(3, Grade(parse=True, compile=True, run=True))
    run_ok_badnum = att(4, Grade(parse=True, compile=True, run=True), dump_ok=False)

    assert _attempt_rank(gen_fail) < _attempt_rank(parse_only)
    assert _attempt_rank(parse_only) < _attempt_rank(run_ok)
    # 同级别时，数值也对的那次更优
    assert _attempt_rank(run_ok_badnum) < _attempt_rank(run_ok)

    # 第 3 次最差 -> 最优是第 2 次，而不是最后一次
    seq = [att(1, Grade(parse=True, compile=True, run=True), dump_ok=False),
           att(2, Grade(parse=True, compile=False, run=False)),
           att(3, Grade(parse=True, compile=False, run=False))]
    best = max(seq, key=_attempt_rank)
    assert best.index == 1, f"应挑第 1 次，实得第 {best.index} 次"

    # 级别完全相同时取更靠后的那次（它的失败原因更能代表"最终卡在哪"）
    ties = [Attempt(index=1), Attempt(index=2), Attempt(index=3)]
    assert max(ties, key=_attempt_rank).index == 3


def test_run_kills_whole_process_tree_on_timeout(tmp: Path) -> None:
    """超时必须连子孙进程一起收，否则会留下继续吃 CPU 的孤儿进程。

    vitis-run 会再拉起 clang / 综合器；`Popen.kill()` 只杀得掉直接子进程。
    这里起一个会 spawn 孙子进程的父进程，看超时后孙子还会不会写出文件。
    """
    import sys
    import time as _t

    from hls_agent import vitis

    sentinel = tmp / "child_survived.txt"
    if sentinel.exists():
        sentinel.unlink()

    child_code = "import sys,time;time.sleep(3);open(sys.argv[1],'w').write('x')"
    parent_code = (
        "import subprocess,sys,time;"
        "subprocess.Popen([sys.executable,'-c',sys.argv[2],sys.argv[1]]);"
        "time.sleep(30)"
    )

    r = vitis._run(
        [sys.executable, "-c", parent_code, str(sentinel), child_code],
        tmp,
        timeout=1,
    )
    assert r.timeout, "超过 timeout 应判定为超时"
    assert r.elapsed_s < 20, f"超时后应立即返回，实得 {r.elapsed_s:.1f}s"

    _t.sleep(4.5)  # 给孙子进程足够时间去写文件（如果它还活着）
    assert not sentinel.exists(), "进程树未被终止：孙子进程仍活着并写出了文件"


def test_csim_launch_retries_transient_dll_miss() -> None:
    """缺 DLL 的"零输出 0.1 秒退出"要重试后再下结论。

    实测：同一份代码同一台机器，偶尔会在启动阶段就 0xC0000135 退出
    （Windows 杀软扫描刚链接出来的 exe），重试即好。但真正的数学库缺失
    会稳定复现——那种情况重试也不能掩盖，要交给上层判成环境受限。
    """
    from hls_agent import vitis

    calls = {"n": 0}
    real = vitis._run

    def flaky(cmd, cwd, timeout, env=None):
        calls["n"] += 1
        if calls["n"] < 3:
            return vitis.ExecResult(return_code=3221225781)  # 零输出
        return vitis.ExecResult(return_code=0, stdout="ok")

    vitis._run = flaky  # type: ignore[assignment]
    try:
        r = vitis._run_exe_retrying(Path("/x/csim.exe"), Path("/x"), 10, {})
        assert r.ok and calls["n"] == 3, f"应重试到第 3 次成功，实际 {calls}"

        calls["n"] = 0

        def always_dll_miss(cmd, cwd, timeout, env=None):
            calls["n"] += 1
            return vitis.ExecResult(return_code=3221225781)

        vitis._run = always_dll_miss  # type: ignore[assignment]
        r2 = vitis._run_exe_retrying(Path("/x/csim.exe"), Path("/x"), 10, {})
        assert r2.return_code == 3221225781, "稳定复现的 DLL 缺失不应被掩盖"
        assert calls["n"] == 3, f"应恰好重试 3 次，实际 {calls}"

        calls["n"] = 0

        def crashes_with_output(cmd, cwd, timeout, env=None):
            calls["n"] += 1
            return vitis.ExecResult(return_code=1, stdout="assert failed")

        vitis._run = crashes_with_output  # type: ignore[assignment]
        vitis._run_exe_retrying(Path("/x/csim.exe"), Path("/x"), 10, {})
        assert calls["n"] == 1, "有输出的正常失败不该重试（浪费时间）"
    finally:
        vitis._run = real  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# 5b. 失败分类：把"失败了"变成可处理的结构化原因
# ---------------------------------------------------------------------------

def test_error_classification_core_cases() -> None:
    from hls_agent import errors as E

    # (a) Windows 缺 DLL：零输出的 0xC0000135
    assert E.classify_run(3221225781, "", "") == E.ENVIRONMENT_ERROR
    # 有输出就不是"启动失败"，而是程序自己崩了
    assert E.classify_run(3221225781, "some output", "") == E.CSIM_RUNTIME_ERROR

    # (b) CHStone 风格：测试台把"不匹配用例数"作为 main 返回值
    assert E.classify_run(3, "a_input=... \n3\n", "") == E.TEST_MISMATCH
    assert E.classify_run(0, "", "") != E.TEST_MISMATCH  # rc=0 不算失败
    # fft_strided 真实案例：测试台打印 "ERROR: 1010 ..." 后 exit(-1)，
    # Windows 上表现为 4294967295。程序跑完了，是数值不一致，不是崩溃。
    assert E.classify_run(4294967295, "ERROR: 1010 (real): -1.8e11\n", "") == E.TEST_MISMATCH
    # aes_aes 真实案例：3221226356 = 0xC0000374 STATUS_HEAP_CORRUPTION，是真崩溃
    assert E.classify_run(3221226356, "", "") == E.CSIM_RUNTIME_ERROR
    assert E.classify_run(3221225477, "x", "") == E.CSIM_RUNTIME_ERROR  # 0xC0000005 访问违例

    # (c) 超时优先于其他判断
    assert E.classify_run(-1, "x", "y", timeout=True) == E.TOOL_TIMEOUT

    # (d) 编译阶段
    assert E.classify_compile(1, "x.cpp:3:5: error: expected ';'") == E.CXX_COMPILE_ERROR
    assert E.classify_compile(1, "boom", exe_missing=True) == E.CSIM_BUILD_ERROR
    assert E.classify_compile(-1, "x", timeout=True) == E.TOOL_TIMEOUT

    # (e) 输入数据缺失要和编译错误分开
    assert E.classify_compile(1, "Couldn't open input data file") == E.INPUT_DATA_ERROR

    # (f) 模型侧
    assert E.classify_generation_error(ValueError("没能从模型输出里取到 a.cpp")) == E.OUTPUT_FORMAT_ERROR
    assert E.classify_generation_error(TimeoutError("read timeout")) == E.MODEL_TIMEOUT

    # (g) 环境类不应盲目重试——否则会让模型反复重写本来正确的算法
    assert not E.is_retryable(E.ENVIRONMENT_ERROR)
    assert E.is_retryable(E.CXX_COMPILE_ERROR)
    assert E.is_retryable(E.TEST_MISMATCH)
    # 每个类别都要有中文说明和修复方向
    for k in E.ALL_KINDS:
        assert E.describe(k) and E.hint(k)


def test_output_truncated_classified_as_extraction_error() -> None:
    from hls_agent import errors as E
    from hls_agent.llm import OutputTruncated

    assert E.classify_generation_error(OutputTruncated("x")) == E.SOURCE_EXTRACTION_ERROR


# ---------------------------------------------------------------------------
# 5c. 数值比对口径：容差必须真的参与判定
# ---------------------------------------------------------------------------

def test_dump_tolerance_is_type_aware() -> None:
    """整数题精确比较，浮点/定点题用相对容差。

    CHStone 头文件里 `typedef unsigned long long float64;`——名字带 float
    但本质是整数位模式，不能按浮点处理。
    """
    from hls_agent.runner import dump_tolerance

    class T:
        def __init__(self, h):
            self.header_src = h

    assert dump_tolerance(T("void k(double a[4]);")) > 0
    assert dump_tolerance(T("#include \"ap_fixed.h\"\ntypedef ap_fixed<32,16> t;")) > 0
    # 纯整数（CHStone 软浮点）
    assert dump_tolerance(T(
        "typedef int flag;\ntypedef unsigned long long int bits64;\n"
        "typedef unsigned long long float64;\nfloat64 add(float64, float64);"
    )) == 0.0


def test_compare_dumps_honours_tolerance() -> None:
    """原来容差读出来了却从不参与判定（硬编码 1e-2），这里锁死行为。"""
    from hls_agent.runner import compare_dumps

    got = {"D": [10.0]}
    ref = {"D": [10.0]}
    assert compare_dumps(got, ref, 0.0)[0] is True

    got_bad = {"D": [10.5]}
    # 相对误差 0.05：容差 1e-2 时判失败，容差 0.1 时判通过
    assert compare_dumps(got_bad, ref, 0.01)[0] is False
    assert compare_dumps(got_bad, ref, 0.1)[0] is True
    # 容差 0（整数题）时，1 个最低位的差也要抓出来
    assert compare_dumps({"z": [7]}, {"z": [8]}, 0.0)[0] is False

    # 长度不符必须失败
    assert compare_dumps({"D": [1.0]}, {"D": [1.0, 2.0]}, 0.01)[0] is False
    # 没有参考输出时不算失败（明确标为"未比对"而不是"已通过"）
    assert compare_dumps({}, {"D": [1.0]}, 0.01) == (True, "无参考输出，跳过数值比对")


def test_reference_error_is_not_a_tolerance() -> None:
    """tb_data_hls_error.json 记录的是参考实现自身偏差，语义上不是容差。

    对 polybench/2mm 来说这个文件是全 0；此前代码把它当容差，
    于是在给模型看的反馈里写出"相对容差 0"，与真实判定口径自相矛盾。
    """
    from hls_agent import dataset as ds
    from hls_agent.runner import load_reference_error

    root = ds.locate_dataset(None)
    if root is None:
        return  # 没挂数据集时跳过
    d = ds.HlsEvalDataset(root)
    # 同一道 2mm 在 polybench 与 hls_polybench__fixed__small 下各有一份，
    # 裸名会被后者占用，所以按题目目录定位而不是按名字。
    hits = [t for t in d.tasks() if t.root.parent.name == "polybench" and t.root.name == "2mm"]
    if not hits:
        return
    assert load_reference_error(hits[0]) == 0.0



def test_ollama_sends_num_ctx() -> None:
    """必须显式传 num_ctx（否则提示词被截断）和 keep_alive（否则每次重加载模型）。"""
    from hls_agent.backends import OllamaBackend

    b = OllamaBackend(model="m", num_ctx=8192, keep_alive="2h",
                      max_tokens=64, timeout_s=5)
    captured: dict = {}

    def fake_post(url, payload, headers, retries=3):
        captured.update(payload)
        return {"message": {"content": "x"}}

    b._post = fake_post  # type: ignore[method-assign]
    b.complete("", [{"role": "user", "content": "hi"}])
    assert captured.get("options", {}).get("num_ctx") == 8192, captured.get("options")
    assert captured.get("keep_alive") == "2h", captured.get("keep_alive")


def test_ollama_captures_timing_stats() -> None:
    """耗时指标要能落到 last_stats 上，否则无法定位"慢在哪"。"""
    from hls_agent.backends import OllamaBackend

    b = OllamaBackend(model="m", num_ctx=8192, max_tokens=64, timeout_s=5)
    fake = {
        "message": {"content": "code"},
        "prompt_eval_count": 400,
        "prompt_eval_duration": int(1e9),
        "eval_count": 50,
        "eval_duration": int(2e9),
        "total_duration": int(3e9),
        "load_duration": 0,
    }
    b._post = lambda *a, **k: fake  # type: ignore[method-assign]
    out = b.complete("", [{"role": "user", "content": "hi"}])
    assert out == "code"
    assert b.last_stats["prompt_tokens"] == 400
    assert abs(b.last_stats["decode_s"] - 2.0) < 0.01
    assert abs(b.last_stats["tok_per_s"] - 25.0) < 0.1


# ---------------------------------------------------------------------------

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=" * 66)
    print("  HLS Agent 回归自测")
    print("=" * 66)

    print("\n[1] 后端接口一致性")
    check("三个后端 complete() 签名一致", test_backend_signatures_match)
    check("三个后端可正常构造", test_all_backends_constructible)
    check("Ollama 自动挑选可用模型", test_ollama_picks_available_model)

    print("\n[2] 模型输出代码抽取")
    check("标准 XML 格式", test_extract_plain_xml)
    check("XML 转义还原", test_extract_unescapes_entities)
    check("markdown 围栏回退", test_extract_from_markdown_fence)
    check("拒绝被截断的输出（dfadd 真实案例）", test_extract_rejects_truncated_output)
    check("完整输出不受影响", test_extract_accepts_real_code_after_truncation_fix)
    check("重试提示禁止写分析文字", test_retry_prompt_forbids_prose)

    print("\n[3] 定点饱和检测")
    check("±32768 指纹识别", test_saturation_detection)

    print("\n[4] 静态预检")
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        check("拦截漏 include", lambda: test_static_check_catches_missing_include(tmp))
        check("对 std:: 数学函数告警", lambda: test_static_check_warns_std_math(tmp))
        check("手写 sqrt 不告警", lambda: test_static_check_accepts_handwritten_sqrt(tmp))
        check("拦截宏改写头文件类型名", lambda: test_static_check_blocks_macro_typedef_hijack(tmp))
        check("拦截 `...` 骨架片段", lambda: test_static_check_blocks_skeleton_ellipsis(tmp))
        check("超时后回收整棵进程树", lambda: test_run_kills_whole_process_tree_on_timeout(tmp))

    print("\n[5] Vitis 命令行构造")
    check("两种入口参数正确", test_vitis_cmd_dispatch)
    check("综合脚本分离测试台", test_synth_tcl_separates_testbench)
    check("csim 启动失败重试", test_csim_launch_retries_transient_dll_miss)
    check("区分测试台/内核的数学库依赖", test_mathlib_hint_distinguishes_tb_from_kernel)
    check("报告取最优尝试而非最后一次", test_best_attempt_beats_last_attempt)
    check("截断后退让思考预算", test_retry_thinking_backs_off_after_truncation)

    print("\n[5b] 失败分类")
    check("核心分类规则", test_error_classification_core_cases)
    check("截断归为抽取错误", test_output_truncated_classified_as_extraction_error)

    print("\n[5c] 数值比对口径")
    check("容差按数值类型选取", test_dump_tolerance_is_type_aware)
    check("容差真的参与判定", test_compare_dumps_honours_tolerance)
    check("参考自身偏差不是容差", test_reference_error_is_not_a_tolerance)

    print("\n[6] Ollama 上下文与耗时诊断")
    check("显式传 num_ctx", test_ollama_sends_num_ctx)
    check("采集耗时指标", test_ollama_captures_timing_stats)

    print()
    print("=" * 66)
    if FAILS:
        print(f"  {len(FAILS)} 项失败: {', '.join(FAILS)}")
        return 1
    print("  全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
