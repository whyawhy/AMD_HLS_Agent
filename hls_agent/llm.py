"""大模型客户端（Anthropic Messages API 兼容端点）。

本机默认走 DeepSeek 的 Anthropic 兼容接口，配置从环境变量读取：
    ANTHROPIC_BASE_URL   https://api.deepseek.com/anthropic
    ANTHROPIC_AUTH_TOKEN <api key>
    ANTHROPIC_MODEL      deepseek-v4-pro

只依赖 requests，不引入额外 SDK。
"""

from __future__ import annotations

import json
import re
import time
from typing import Dict, List, Optional

import requests

from .config import LLMConfig

_RETRYABLE = {429, 500, 502, 503, 504}


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, cfg: LLMConfig):
        if not cfg.api_key:
            raise LLMError(
                "没有找到 API Key。请设置环境变量 ANTHROPIC_AUTH_TOKEN，"
                "或用 --api-key 指定。"
            )
        self.cfg = cfg
        self.endpoint = cfg.base_url.rstrip("/") + "/v1/messages"

    # ------------------------------------------------------------------
    def complete(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        retries: int = 3,
    ) -> str:
        """调用一次对话补全，返回拼接后的文本。"""
        payload = {
            "model": self.cfg.model,
            "max_tokens": max_tokens or self.cfg.max_tokens,
            "temperature": self.cfg.temperature if temperature is None else temperature,
            "system": system,
            "messages": messages,
        }
        headers = {
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": self.cfg.api_key,
            "authorization": f"Bearer {self.cfg.api_key}",
        }

        last_err = ""
        for attempt in range(1, retries + 1):
            try:
                r = requests.post(
                    self.endpoint,
                    headers=headers,
                    data=json.dumps(payload).encode("utf-8"),
                    timeout=self.cfg.timeout_s,
                )
            except requests.RequestException as e:
                last_err = f"网络错误: {e}"
                if attempt < retries:
                    time.sleep(2 * attempt)
                    continue
                raise LLMError(last_err) from e

            if r.status_code in _RETRYABLE and attempt < retries:
                last_err = f"HTTP {r.status_code}: {r.text[:200]}"
                time.sleep(2 * attempt)
                continue

            if r.status_code != 200:
                raise LLMError(f"HTTP {r.status_code}: {r.text[:800]}")

            try:
                data = r.json()
            except ValueError as e:
                raise LLMError(f"响应不是合法 JSON: {r.text[:400]}") from e

            return self._extract_text(data)

        raise LLMError(last_err or "调用失败")

    # ------------------------------------------------------------------
    @staticmethod
    def _extract_text(data: dict) -> str:
        blocks = data.get("content")

        if isinstance(blocks, list):
            parts: List[str] = []
            thinking: List[str] = []
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and b.get("text"):
                    parts.append(b["text"])
                elif b.get("type") in ("thinking", "reasoning") and b.get("thinking"):
                    thinking.append(b["thinking"])
            if parts:
                return "".join(parts)
            # 推理模型有时把内容全写进 thinking 块（尤其是被 max_tokens 截断时）。
            # 如果思考内容里带代码块，仍然有救，直接用它。
            joined = "\n".join(thinking)
            if "OUTPUT_CODE" in joined or "```" in joined:
                return joined
            if thinking:
                raise LLMError(
                    f"模型只返回了思考内容，没有正文（stop_reason={data.get('stop_reason')!r}，"
                    f"output_tokens={data.get('usage', {}).get('output_tokens')!r}）。"
                    f"多半是 max_tokens 太小被截断，请调大 HLS_AGENT_MAX_TOKENS。"
                )

        # 有些兼容端点直接返回 OpenAI 风格
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            return choices[0].get("message", {}).get("content", "")

        raise LLMError(f"无法从响应中提取文本: {json.dumps(data)[:400]}")


# --------------------------------------------------------------------------
# 代码块抽取（对齐官方 hls_eval/prompting.py）
# --------------------------------------------------------------------------

_FENCE = re.compile(r"```(?:[a-zA-Z0-9_+#.]*)\s*\n(.*?)```", re.DOTALL)


def extract_output_code_xml(text: str) -> Dict[str, str]:
    """解析官方的 <OUTPUT_CODE name="x.cpp"> ... </OUTPUT_CODE> 格式。

    与 hls_eval/prompting.py::extract_code_xml_from_llm_output 行为一致：
    按出现顺序把开标签和闭标签两两配对。
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
        out[m.group(1)] = text[m.end() : closes[i]].strip()
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
    """
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
