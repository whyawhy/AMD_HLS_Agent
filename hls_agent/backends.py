"""可插拔的大模型后端。

赛道要求模型可本地部署，但开发期我们会换不同的模型/服务，所以把"模型接入"
抽象成后端接口。上层只调用 ``backend.complete()``，不关心背后是 Ollama、
vLLM 还是别的兼容端点。

后端类型：
  ollama     本地 Ollama（默认 http://127.0.0.1:11434）
  openai     任意 OpenAI 兼容服务（vLLM / LM Studio / llama.cpp server 等）
  anthropic  Anthropic Messages 兼容端点（Claude Desktop 本地网关 / DeepSeek）

接入一个新模型 = 启动 serve/ 里对应的服务 + 设一个环境变量，不用改代码。
"""

from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

import requests

# --------------------------------------------------------------------------
# 通用
# --------------------------------------------------------------------------


class BackendError(RuntimeError):
    """后端调用失败。"""


def _extract_openai_text(data: dict) -> str:
    """从 OpenAI 风格响应里取正文。"""
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message", {}) or {}
        content = msg.get("content")
        if content:
            return content
        # 推理模型可能把内容放在 reasoning_content
        rc = msg.get("reasoning_content")
        if rc:
            return rc
    raise BackendError(f"无法从响应中提取文本: {json.dumps(data)[:400]}")


def _extract_anthropic_text(data: dict) -> str:
    """从 Anthropic Messages 响应里取正文（跳过 thinking 块）。"""
    blocks = data.get("content")
    if isinstance(blocks, list):
        parts, thinking = [], []
        for b in blocks:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text" and b.get("text"):
                parts.append(b["text"])
            elif b.get("type") in ("thinking", "reasoning") and b.get("thinking"):
                thinking.append(b["thinking"])
        if parts:
            return "".join(parts)
        # 被 max_tokens 截断时正文可能为空，但思考里带代码，仍然可用
        joined = "\n".join(thinking)
        if "OUTPUT_CODE" in joined or "```" in joined:
            return joined
        if thinking:
            raise BackendError(
                "模型只返回了思考内容，没有正文（多半是 max_tokens 太小被截断）。"
                f" stop_reason={data.get('stop_reason')!r}"
            )
    return _extract_openai_text(data)


# --------------------------------------------------------------------------
# 后端基类
# --------------------------------------------------------------------------


class LLMBackend(ABC):
    name: str = "base"

    def __init__(self, model: str, max_tokens: int = 16384,
                 temperature: float = 0.2, timeout_s: int = 300):
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout_s = timeout_s

    @abstractmethod
    def endpoint(self) -> str:
        """用于展示与探测的地址。"""

    @abstractmethod
    def available(self) -> Tuple[bool, str]:
        """服务是否可达，返回 (可用, 说明)。"""

    @abstractmethod
    def complete(self, system: str, messages: List[Dict[str, str]],
                 max_tokens: Optional[int] = None,
                 temperature: Optional[float] = None) -> str:
        """一次对话补全，返回正文文本。"""

    def describe(self) -> str:
        return f"{self.name}: {self.model} @ {self.endpoint()}"

    # 供子类复用：带重试的 POST
    def _post(self, url: str, payload: dict, headers: dict, retries: int = 3) -> dict:
        retryable = {429, 500, 502, 503, 504}
        last = ""
        for attempt in range(1, retries + 1):
            try:
                r = requests.post(url, headers=headers,
                                  data=json.dumps(payload).encode("utf-8"),
                                  timeout=self.timeout_s)
            except requests.RequestException as e:
                last = f"网络错误: {e}"
                if attempt < retries:
                    time.sleep(2 * attempt)
                    continue
                raise BackendError(last) from e

            if r.status_code in retryable and attempt < retries:
                last = f"HTTP {r.status_code}: {r.text[:200]}"
                time.sleep(2 * attempt)
                continue
            if r.status_code != 200:
                raise BackendError(f"HTTP {r.status_code}: {r.text[:600]}")
            try:
                return r.json()
            except ValueError as e:
                raise BackendError(f"响应不是合法 JSON: {r.text[:300]}") from e
        raise BackendError(last or "调用失败")


# --------------------------------------------------------------------------
# OpenAI 兼容（vLLM / LM Studio / llama.cpp server / Ollama 兼容层）
# --------------------------------------------------------------------------


class OpenAIBackend(LLMBackend):
    """任意 OpenAI 兼容的 /v1/chat/completions 服务（vLLM / LM Studio / llama.cpp）。"""

    name = "openai"

    def __init__(self, base_url: str = "http://127.0.0.1:8000", api_key: str = "not-needed", **kw):
        super().__init__(**kw)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def endpoint(self) -> str:
        return f"{self.base_url}/v1/chat/completions"

    def available(self) -> Tuple[bool, str]:
        try:
            r = requests.get(f"{self.base_url}/v1/models", timeout=5)
            if r.status_code == 200:
                return True, "服务在线"
            return False, f"HTTP {r.status_code}"
        except requests.RequestException as e:
            return False, f"连不上: {e.__class__.__name__}"

    def complete(self, system, messages, max_tokens=None, temperature=None) -> str:
        msgs = ([{"role": "system", "content": system}] if system else []) + list(messages)
        payload = {
            "model": self.model,
            "messages": msgs,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": self.temperature if temperature is None else temperature,
        }
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {self.api_key}",
        }
        return _extract_openai_text(self._post(self.endpoint(), payload, headers))


# --------------------------------------------------------------------------
# Ollama
# --------------------------------------------------------------------------


class OllamaBackend(LLMBackend):
    """本地 Ollama，走原生 /api/chat 接口。"""

    name = "ollama"

    def __init__(self, host: str = "http://127.0.0.1:11434", **kw):
        super().__init__(**kw)
        self.host = host.rstrip("/")

    def endpoint(self) -> str:
        return f"{self.host}/api/chat"

    def available(self) -> Tuple[bool, str]:
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=5)
            if r.status_code != 200:
                return False, f"HTTP {r.status_code}"
            tags = r.json().get("models", [])
            names = {m.get("name", "") for m in tags}
            if not names:
                return False, "服务在线但没有任何模型，先执行 ollama pull <模型>"
            base = self.model.split(":")[0]
            if not any(n == self.model or n.split(":")[0] == base for n in names):
                return False, (f"服务在线，但没有模型 {self.model}。"
                               f"已有: {', '.join(sorted(names)[:5])}")
            return True, "服务在线，模型已就绪"
        except requests.RequestException as e:
            return False, f"连不上: {e.__class__.__name__}"

    def complete(self, system, messages, max_tokens=None, temperature=None) -> str:
        msgs = ([{"role": "system", "content": system}] if system else []) + list(messages)
        payload = {
            "model": self.model,
            "messages": msgs,
            "stream": False,
            "options": {
                "num_predict": max_tokens or self.max_tokens,
                "temperature": self.temperature if temperature is None else temperature,
            },
        }
        data = self._post(self.endpoint(), payload, {"content-type": "application/json"})
        msg = data.get("message", {}) or {}
        content = msg.get("content", "")
        if not content:
            raise BackendError(f"Ollama 返回了空内容: {json.dumps(data)[:300]}")
        return content


# --------------------------------------------------------------------------
# Anthropic Messages 兼容
# --------------------------------------------------------------------------


class AnthropicBackend(LLMBackend):
    """Anthropic Messages 兼容端点（Claude Desktop 网关 / DeepSeek 等）。"""

    name = "anthropic"

    def __init__(self, base_url: str = "https://api.anthropic.com", api_key: str = "", **kw):
        super().__init__(**kw)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def endpoint(self) -> str:
        return f"{self.base_url}/v1/messages"

    def available(self) -> Tuple[bool, str]:
        if not self.api_key:
            return False, "缺少 API Key"
        return True, "已配置凭证"

    def complete(self, system, messages, max_tokens=None, temperature=None) -> str:
        payload = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": self.temperature if temperature is None else temperature,
            "messages": list(messages),
        }
        if system:
            payload["system"] = system
        headers = {
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": self.api_key,
            "authorization": f"Bearer {self.api_key}",
        }
        return _extract_anthropic_text(self._post(self.endpoint(), payload, headers))
