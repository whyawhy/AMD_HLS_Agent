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
import re
import sys
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

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
                 temperature: float = 0.2, timeout_s: int = 300,
                 thinking: str = "off"):
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout_s = timeout_s
        # 思考控制：off / budget:N。推理模型的思考 token 是生成时间的主要来源，
        # 实测关闭思考后输出 token 减半以上。
        self.thinking = thinking
        # auto 模式下的补充说明（如「自动改用了某个可用模型」），供上层展示
        self.note = ""
        # 上一次调用的耗时指标（token 数、各阶段耗时），供上层诊断"慢在哪"
        self.last_stats: Dict[str, Any] = {}

    def _thinking_payload(self, override: Optional[str] = None) -> dict:
        """Anthropic 风格端点的 thinking 参数；override 优先于实例配置。"""
        t = (override if override is not None else self.thinking).strip().lower()
        if t in ("off", "disabled", "none", "0"):
            return {"thinking": {"type": "disabled"}}
        if t.startswith("budget:"):
            n = t.split(":", 1)[1].strip()
            if n.isdigit() and int(n) > 0:
                return {"thinking": {"type": "enabled", "budget_tokens": int(n)}}
        return {}

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
        note = f"  ({self.note})" if getattr(self, "note", "") else ""
        return f"{self.name}: {self.model} @ {self.endpoint()}{note}"

    # ------------------------------------------------------------------
    def resolve_model(self) -> Tuple[Optional[str], str]:
        """auto 模式下挑一个**服务上真实存在**的模型。

        返回 (模型名 或 None, 说明)。默认实现不做改动——只有本地后端会
        覆写它，因为本地服务的可用模型是能枚举的。

        为什么需要：配置里的模型名可能来自别的机器（如开发机的默认值），
        到了新机器上服务在线但模型不在。此时与其报错让人手动改，不如自动
        挑一个可用的并说明清楚。
        """
        return self.model, ""

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

    def list_models(self) -> List[str]:
        """列出服务上已有的模型 id（连不上则返回空表）。"""
        try:
            r = requests.get(f"{self.base_url}/v1/models", timeout=5)
            if r.status_code != 200:
                return []
            return [m.get("id", "") for m in r.json().get("data", []) if m.get("id")]
        except requests.RequestException:
            return []

    def available(self) -> Tuple[bool, str]:
        names = self.list_models()
        if not names:
            return False, "连不上: 服务未启动或端口不对"
        return True, f"服务在线，{len(names)} 个模型"

    def resolve_model(self) -> Tuple[Optional[str], str]:
        """配置的模型不在时自动挑一个（多数服务只挂一个模型，直接用它）。"""
        names = self.list_models()
        if not names or self.model in names:
            return self.model, ""
        best = names[0]
        return best, f"配置的模型 {self.model} 不在服务上，自动改用 {best}"

    def complete(self, system, messages, max_tokens=None, temperature=None,
                 thinking: Optional[str] = None) -> str:
        # OpenAI 兼容接口没有统一的思考控制参数，这里接受但忽略——
        # 调用方（runner）会对所有后端传同一个签名，必须保持一致
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

    def __init__(self, host: str = "http://127.0.0.1:11434",
                 num_ctx: int = 16384, keep_alive: str = "1h", **kw):
        super().__init__(**kw)
        self.host = host.rstrip("/")
        # 必须显式设置：Ollama 默认上下文只有 2048/4096，而完整提示词
        # 实测可到 5000+ tokens，不设会被静默截断（模型看不到完整测试台）
        self.num_ctx = num_ctx
        # 模型在显存里的驻留时长。本地大模型重新加载一次要 100~200 秒，
        # 批量跑题时必须让它常驻，否则每题都重付一次加载成本。
        self.keep_alive = keep_alive

    def endpoint(self) -> str:
        return f"{self.host}/api/chat"

    def list_models(self) -> List[str]:
        """列出服务上已有的模型名（连不上或没有则返回空表）。"""
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=5)
            if r.status_code != 200:
                return []
            return [m.get("name", "") for m in r.json().get("models", []) if m.get("name")]
        except requests.RequestException:
            return []

    def _has_model(self, names: List[str]) -> bool:
        base = self.model.split(":")[0]
        return any(n == self.model or n.split(":")[0] == base for n in names)

    def available(self) -> Tuple[bool, str]:
        names = self.list_models()
        if not names:
            return False, "连不上或服务上没有任何模型（先 ollama pull <模型>）"
        if not self._has_model(names):
            return False, (f"服务在线，但没有模型 {self.model}。"
                           f"已有: {', '.join(sorted(names)[:6])}")
        return True, "服务在线，模型已就绪"

    def resolve_model(self) -> Tuple[Optional[str], str]:
        """配置的模型不在时，自动挑一个可用的（优先代码模型，其次参数大的）。"""
        names = self.list_models()
        if not names or self._has_model(names):
            return self.model, ""

        def score(n: str) -> tuple:
            low = n.lower()
            coder = 0 if "coder" in low else 1
            nums = re.findall(r"(\d+)\s*b", low)
            size = -max((int(x) for x in nums), default=0)
            return (coder, size)

        best = sorted(names, key=score)[0]
        return best, f"配置的模型 {self.model} 不在服务上，自动改用 {best}"

    def complete(self, system, messages, max_tokens=None, temperature=None,
                 thinking: Optional[str] = None) -> str:
        msgs = ([{"role": "system", "content": system}] if system else []) + list(messages)
        payload = {
            "model": self.model,
            "messages": msgs,
            "stream": False,
            # 让模型在显存里常驻（默认 5 分钟就卸载，重加载一次要 100~200s）
            "keep_alive": self.keep_alive,
            "options": {
                "num_predict": max_tokens or self.max_tokens,
                "temperature": self.temperature if temperature is None else temperature,
                # 显式指定上下文窗口，否则 Ollama 用默认值（2048/4096）
                # 把长提示词截断，模型会看不到完整测试台
                "num_ctx": self.num_ctx,
            },
        }

        # Ollama 用 `think` 控制推理模型的思考过程（qwen3 等）。非思考模型
        # 或旧版本可能不认这个参数，所以失败时去掉重试一次。
        t = (thinking if thinking is not None else self.thinking or "").strip().lower()
        use_think = t in ("off", "disabled", "none", "0")
        if use_think:
            payload["think"] = False

        headers = {"content-type": "application/json"}

        # Ollama 在提示词超出 num_ctx 时会静默截断——模型看不到完整测试台，
        # 生成的代码会离谱且难排查。这里粗估 token 数并明确预警。
        approx_tokens = sum(len(m.get("content", "")) for m in msgs) // 3
        if approx_tokens > self.num_ctx * 0.9:
            print(
                f"  [警告] 提示词约 {approx_tokens} tokens，接近或超过 Ollama "
                f"上下文窗口 {self.num_ctx}，可能被截断。"
                f"请调大环境变量 HLS_AGENT_OLLAMA_NUM_CTX。",
                file=sys.stderr,
            )

        try:
            data = self._post(self.endpoint(), payload, headers)
        except BackendError:
            if not use_think:
                raise
            payload.pop("think", None)
            data = self._post(self.endpoint(), payload, headers)

        msg = data.get("message", {}) or {}
        content = msg.get("content", "")
        # 思考型模型（qwen3 等）可能把内容放进 thinking 字段
        if not content and msg.get("thinking"):
            content = msg["thinking"]
        if not content:
            raise BackendError(f"Ollama 返回了空内容: {json.dumps(data)[:300]}")

        # 记录耗时指标——定位"生成慢"到底慢在读提示词还是写代码
        ns = 1e9
        stats: Dict[str, Any] = {
            "prompt_tokens": data.get("prompt_eval_count"),
            "output_tokens": data.get("eval_count"),
            "prefill_s": (data.get("prompt_eval_duration") or 0) / ns,
            "decode_s": (data.get("eval_duration") or 0) / ns,
            "load_s": (data.get("load_duration") or 0) / ns,
            "total_s": (data.get("total_duration") or 0) / ns,
        }
        oc = stats["output_tokens"] or 0
        if stats["decode_s"] > 0 and oc:
            stats["tok_per_s"] = oc / stats["decode_s"]
        self.last_stats = stats
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

    def complete(self, system, messages, max_tokens=None, temperature=None,
                 thinking: Optional[str] = None) -> str:
        payload = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": self.temperature if temperature is None else temperature,
            "messages": list(messages),
        }
        payload.update(self._thinking_payload(thinking))
        if system:
            payload["system"] = system
        headers = {
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": self.api_key,
            "authorization": f"Bearer {self.api_key}",
        }
        return _extract_anthropic_text(self._post(self.endpoint(), payload, headers))
