"""大模型调用门面 + 模型输出解析。

``LLMClient`` 是对 :mod:`hls_agent.backends` 的薄封装，上层（runner）只依赖它，
所以切换后端不需要改动调用方。配置见 :class:`hls_agent.config.LLMConfig`。

本模块另一半是"从模型输出里把代码抠出来"——模型不一定老实按格式输出，所以按
可靠性从高到低有多条回退路径。
"""

from __future__ import annotations

import html
import re
from typing import Dict, List, Optional

from .backends import (
    AnthropicBackend,
    BackendError,
    LLMBackend,
    OllamaBackend,
    OpenAIBackend,
)
from .config import LLMConfig

__all__ = [
    "LLMClient",
    "LLMError",
    "BackendError",
    "extract_output_code_xml",
    "extract_fenced_by_name",
    "extract_code_blocks",
    "extract_source",
    "unescape_xml_entities",
]


class LLMError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# 门面
# --------------------------------------------------------------------------


class LLMClient:
    """把 LLMConfig 变成具体后端。上层只用 ``complete()``。"""

    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg
        self.backend: LLMBackend = _make_backend(cfg)

    def complete(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        try:
            return self.backend.complete(system, messages, max_tokens, temperature)
        except BackendError as e:
            raise LLMError(str(e)) from e

    def describe(self) -> str:
        return self.backend.describe()


def _make_backend(cfg: LLMConfig) -> LLMBackend:
    """按 cfg.backend 构造后端；auto 时按可用性依次尝试。"""
    common = dict(model=cfg.model, max_tokens=cfg.max_tokens,
                  temperature=cfg.temperature, timeout_s=cfg.timeout_s)

    kind = (cfg.backend or "auto").lower()

    if kind == "ollama":
        return OllamaBackend(host=cfg.ollama_host, **common)
    if kind in ("openai", "vllm"):
        return OpenAIBackend(base_url=cfg.openai_base_url, api_key=cfg.api_key or "not-needed", **common)
    if kind == "anthropic":
        return AnthropicBackend(base_url=cfg.base_url, api_key=cfg.api_key, **common)

    # auto：本地优先（赛道要求本地开源权重），再退回远程兼容端点
    candidates: List[LLMBackend] = [
        OllamaBackend(host=cfg.ollama_host, **common),
        OpenAIBackend(base_url=cfg.openai_base_url, api_key="not-needed", **common),
        AnthropicBackend(base_url=cfg.base_url, api_key=cfg.api_key, **common),
    ]
    for b in candidates:
        ok, _why = b.available()
        if ok:
            return b

    # 都不在线时，按"哪个配了凭证用哪个"兜底，让报错更有指向性
    for b in candidates:
        if isinstance(b, AnthropicBackend) and b.api_key:
            return b
    return candidates[0]


def probe_backends(cfg: LLMConfig) -> List[tuple[str, bool, str]]:
    """探测各后端可用性，返回 [(名称, 可用, 说明)]。供 CLI 诊断用。"""
    common = dict(model=cfg.model, max_tokens=cfg.max_tokens,
                  temperature=cfg.temperature, timeout_s=cfg.timeout_s)
    out = []
    for b in (
        OllamaBackend(host=cfg.ollama_host, **common),
        OpenAIBackend(base_url=cfg.openai_base_url, api_key="not-needed", **common),
        AnthropicBackend(base_url=cfg.base_url, api_key=cfg.api_key, **common),
    ):
        ok, why = b.available()
        out.append((b.name, ok, why))
    return out


# --------------------------------------------------------------------------
# 代码块抽取（对齐官方 hls_eval/prompting.py）
# --------------------------------------------------------------------------

_FENCE = re.compile(r"```(?:[a-zA-Z0-9_+#.]*)\s*\n(.*?)```", re.DOTALL)


def unescape_xml_entities(code: str) -> str:
    """还原被 XML 转义的尖括号。

    模型按要求把代码放进 ``<OUTPUT_CODE>`` 标签时，会**正确地**做 XML 转义：

        typedef ap_fixed&lt;64, 32&gt; t_accum;      // 实际想要 ap_fixed<64, 32>

    正则抽取不做反转义的话，代码会以 ``&lt;`` 形式落盘，编译必然失败
    （``ap_fixed&lt;64,32&gt;`` 会被解析成没有模板参数的 ``ap_fixed``）。
    真正的 C++ 代码里几乎不会出现字面的 ``&lt;`` / ``&gt;``，所以这里可以放心还原。
    """
    if "&lt;" in code or "&gt;" in code or "&amp;" in code or "&quot;" in code:
        return html.unescape(code)
    return code


def extract_output_code_xml(text: str) -> Dict[str, str]:
    """解析官方的 <OUTPUT_CODE name="x.cpp"> ... </OUTPUT_CODE> 格式。

    与 hls_eval/prompting.py::extract_code_xml_from_llm_output 行为一致：
    按出现顺序把开标签和闭标签两两配对。额外做一次 XML 反转义。
    """
    matches = list(re.finditer(r'<OUTPUT_CODE name="(.+?)">', text))
    if not matches:
        return {}
    closes = [m.start() for m in re.finditer(r"</OUTPUT_CODE(?:\s+name=\"(?:\S+)\")?>", text)]
    if len(closes) < len(matches):
        raise ValueError(
            f"OUTPUT_CODE 标签不成对：{len(matches)} 个开标签，{len(closes)} 个闭标签"
        )
    out: Dict[str, str] = {}
    for i, m in enumerate(matches):
        out[m.group(1)] = unescape_xml_entities(text[m.end() : closes[i]].strip())
    return out


def extract_fenced_by_name(text: str) -> Dict[str, str]:
    """兜底：```2mm.cpp ... ``` 这种把文件名当语言标签的写法。"""
    out: Dict[str, str] = {}
    pattern = re.compile(r"```([A-Za-z0-9_.\-]+\.(?:cpp|h|hpp|cc|c))\s*\n(.*?)```", re.DOTALL)
    for m in pattern.finditer(text):
        out[m.group(1)] = m.group(2).strip()
    return out


def extract_code_blocks(text: str) -> List[str]:
    """取出所有围栏代码块；没有围栏就整段返回。"""
    blocks = [b.strip() for b in _FENCE.findall(text)]
    return [b for b in blocks if b] or [text.strip()]


def _looks_like_cpp(body: str) -> bool:
    """粗糙判断一段文本是不是 C++ 源码。"""
    if "#include" in body:
        return True
    has_brace = "{" in body and "}" in body
    has_semi = body.count(";") >= 3
    return has_brace and has_semi


def extract_source(text: str, want: str, top: str = "") -> str:
    """从模型输出里取出内核 .cpp 的内容。

    模型不一定老实按官方 XML 格式输出，所以按可靠性从高到低依次尝试：
      1. 官方 <OUTPUT_CODE name=".."> 格式
      2. ```xxx.cpp 这种把文件名当语言标签的围栏
      3. 任意围栏代码块里包含顶层函数名的那个
      4. 任意像 C++ 的围栏代码块
      5. 整段文本本身就是 C++ 的情况

    无论走哪条路径，最后都做一次 XML 反转义（模型写 XML 时会把尖括号转义）。
    """
    return unescape_xml_entities(_extract_source_raw(text, want, top))


def _extract_source_raw(text: str, want: str, top: str = "") -> str:
    # 1. 官方 XML
    try:
        named = extract_output_code_xml(text)
    except ValueError:
        named = {}
    if want in named:
        return named[want]
    for k, v in named.items():
        if k.endswith((".cpp", ".cc", ".c")):
            return v

    # 2. 文件名围栏
    fenced = extract_fenced_by_name(text)
    if want in fenced:
        return fenced[want]
    for k, v in fenced.items():
        if k.endswith((".cpp", ".cc", ".c")):
            return v

    blocks = extract_code_blocks(text)

    # 3. 含顶层函数名的代码块
    if top:
        for b in blocks:
            if re.search(rf"\b{re.escape(top)}\s*\(", b):
                return b

    # 4. 像 C++ 的代码块（取最长的那个）
    cpp_blocks = [b for b in blocks if _looks_like_cpp(b)]
    if cpp_blocks:
        return max(cpp_blocks, key=len)

    # 5. 整段就是代码
    stripped = text.strip()
    if _looks_like_cpp(stripped):
        return stripped

    raise ValueError(
        f"没能从模型输出里取到 {want}（也不像 C++ 源码）。输出前 400 字：\n{text[:400]}"
    )
