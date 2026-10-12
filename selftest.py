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


# ---------------------------------------------------------------------------
# 6. Ollama 上下文窗口与耗时诊断
# ---------------------------------------------------------------------------

def test_ollama_sends_num_ctx() -> None:
    """必须显式传 num_ctx，否则 Ollama 用默认值截断长提示词。"""
    from hls_agent.backends import OllamaBackend

    b = OllamaBackend(model="m", num_ctx=8192, max_tokens=64, timeout_s=5)
    captured: dict = {}

    def fake_post(url, payload, headers, retries=3):
        captured.update(payload)
        return {"message": {"content": "x"}}

    b._post = fake_post  # type: ignore[method-assign]
    b.complete("", [{"role": "user", "content": "hi"}])
    assert captured.get("options", {}).get("num_ctx") == 8192, captured.get("options")


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

    print("\n[3] 定点饱和检测")
    check("±32768 指纹识别", test_saturation_detection)

    print("\n[4] 静态预检")
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        check("拦截漏 include", lambda: test_static_check_catches_missing_include(tmp))
        check("对 std:: 数学函数告警", lambda: test_static_check_warns_std_math(tmp))
        check("手写 sqrt 不告警", lambda: test_static_check_accepts_handwritten_sqrt(tmp))

    print("\n[5] Vitis 命令行构造")
    check("两种入口参数正确", test_vitis_cmd_dispatch)
    check("综合脚本分离测试台", test_synth_tcl_separates_testbench)

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
