"""提示词构造 —— 严格照搬 HLS-Eval 官方 hls_eval/prompts.py 的 zero-shot 生成提示。

官方流程（hls_eval/eval.py::HLSGenerationZeroShotEvaluator）：
    输入 = 题面(kernel_description.md) + 头文件(.h) + testbench(_tb.cpp)
    输出 = **只生成一个 .cpp**，格式为
        <OUTPUT_CODE name="kernel_name.cpp">
        ...
        </OUTPUT_CODE name="kernel_name.cpp">
    断言：提取出的代码块恰好 1 个，且以 .cpp 结尾。

因此本模块保持官方原文不做改动，保证与官方评测可比；重试时在其后追加编译反馈。
"""

from __future__ import annotations

from textwrap import dedent
from typing import Dict

# --------------------------------------------------------------------------
# 官方原文（hls_eval/prompts.py）
# --------------------------------------------------------------------------

PROMPT_PRE = dedent(
    """
## Overview
You are a helpful export hardware engineer and software developer who will assist the user with hardware design tasks for high-level synthesis.
The task will center around high-level synthesis (HLS) code written in C++ for a hardware design. The HLS design is written to target the latest Vitis HLS tool from Xilinx, which maps C++ code to a Verilog implementation for FPGAs.
"""
).strip()

PROMPT_GEN = dedent(
    """
## Task Description
Given a natural language description of an HLS design, a pre-written C++ design header, and a pre-written C++ testbench, generate the C++ implementation of the HLS design that aligns with the natural language description.

It should be functionally equivalent to the natural language description, be consistent with the provided header file, and pass the testbench. The design should also be synthesizable by the HLS tool.

Only generate the code for the design; do not modify the header file or the testbench. Make sure to import the header file as well.

Provide the complete design code in the single output; do not omit anything or leave placeholders.

Hierarchical design, sub-functions, template functions, structs, typedefs, and define statements are allowed but should be used only if appropriate.
"""
).strip()

PROMPT_OUTPUT_FORMAT_XML = dedent(
    text="""
## Output Format
The generated HLS output code should be provided in the following format:
```
<OUTPUT_CODE name="kernel_name.cpp">
    ...
</OUTPUT_CODE>
```
Please use this XML format and do not use other formats like markdown code blocks or plain text.
Only output the generated HLS code in the XML format and nothing else.
"""
).strip()


def build_input_code_prompt_xml(code: Dict[str, str]) -> str:
    """官方 build_input_code_prompt_xml：把输入文件包成 <INPUT_CODE> 块。"""
    p = "\n"
    for name, content in code.items():
        p += f'<INPUT_CODE name="{name}">\n'
        p += f"{content}\n"
        p += f'</INPUT_CODE name="{name}">\n'
    p += "\n"
    return p


def build_prompt_gen_zero_shot(
    description_name: str,
    description: str,
    tb_name: str,
    tb_src: str,
    h_name: str,
    h_src: str,
) -> str:
    """官方 build_prompt_gen_zero_shot 的等价实现（改传内容而非路径）。"""
    p = PROMPT_PRE
    p += "\n\n"
    p += PROMPT_GEN
    p += "\n\n"
    p += PROMPT_OUTPUT_FORMAT_XML
    p += "\n\n"

    p += "## Task Inputs\n"
    p += "\n"
    p += build_input_code_prompt_xml(
        {
            description_name: description,
            tb_name: tb_src,
            h_name: h_src,
        }
    )
    p += "\n\n"

    p += "## Task Output\n"
    p += "\n"
    return p


# --------------------------------------------------------------------------
# 重试：在官方提示后追加编译/仿真反馈
# --------------------------------------------------------------------------

RETRY_SUFFIX = dedent(
    """
## Previous Attempt Failed

Your previous implementation was compiled and simulated with Vitis HLS and did not pass.
The tool output below shows what went wrong.

```
{errors}
```

Here is the code you generated last time:

```
{prev_code}
```

Fix the problem and output the complete `{source_name}` again, following the same
`<OUTPUT_CODE name="{source_name}">` XML format as before. Output the whole file, not a diff.
Do not modify the header file or the testbench — only the kernel implementation.
"""
).strip()


def build_retry_prompt(
    base_prompt: str,
    errors: str,
    prev_code: str,
    source_name: str,
) -> str:
    return base_prompt + "\n\n" + RETRY_SUFFIX.format(
        errors=errors.strip(), prev_code=prev_code.strip(), source_name=source_name
    ) + "\n"


FORMAT_RETRY_SUFFIX = dedent(
    """
## Output Format Violation

Your previous response could not be used: {reason}

You must output **exactly one** code block in this exact format, with nothing before or after it:

<OUTPUT_CODE name="{source_name}">
...the complete C++ implementation...
</OUTPUT_CODE name="{source_name}">

Do not write any explanation, reasoning, or markdown fences. Output only the XML block.
"""
).strip()


def build_format_retry_prompt(base_prompt: str, reason: str, source_name: str) -> str:
    """模型没按格式输出时的重试提示（还没轮到编译，纯格式问题）。"""
    return base_prompt + "\n\n" + FORMAT_RETRY_SUFFIX.format(
        reason=reason.strip(), source_name=source_name
    ) + "\n"


# --------------------------------------------------------------------------
# 基线：官方 zero-shot 就是基线口径（单次生成、不重试、无工具反馈），
# 所以基线直接用上面的 build_prompt_gen_zero_shot，不做任何裁剪。
# --------------------------------------------------------------------------
