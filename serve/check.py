#!/usr/bin/env python3
"""推理服务连通性自检。

在跑智能体之前先执行这个，确认"接哪个模型、能不能连上"：

    python serve/check.py

它会依次探测本地 Ollama、本地 OpenAI 兼容服务（vLLM 等）、远程 Anthropic
兼容端点，并说明程序会自动选中哪一个。如果哪个都不可用，会给出对应的启动命令。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hls_agent.config import LLMConfig  # noqa: E402
from hls_agent.llm import LLMClient, probe_backends  # noqa: E402

SEP = "=" * 70


def main() -> int:
    cfg = LLMConfig.from_env()

    print(SEP)
    print("  推理服务自检")
    print(SEP)
    print(f"  后端设置   : {cfg.backend}   (auto = 自动探测)")
    print(f"  模型       : {cfg.model}")
    print(f"  Ollama 地址: {cfg.ollama_host}")
    print(f"  vLLM 地址  : {cfg.openai_base_url}")
    print(f"  远程端点   : {cfg.base_url}")
    print()

    results = probe_backends(cfg)
    print("  ---- 探测结果 ----")
    for name, ok, why in results:
        print(f"  [{'可用' if ok else '不可用'}] {name:10} {why}")
    print()

    if cfg.backend == "auto":
        client = LLMClient(cfg)
        print(f"  自动选中   : {client.backend.describe()}")
    else:
        print(f"  指定后端   : {cfg.backend}")

    any_ok = any(ok for _n, ok, _w in results)
    if not any_ok:
        print()
        print("  没有可用的推理服务。任选一种启动方式：")
        print("    Ollama (Linux/macOS): bash serve/start_ollama.sh")
        print("    Ollama (Windows)    : serve\\start_ollama.bat")
        print("    vLLM   (带显卡机器)  : bash serve/start_vllm.sh")
        print("    或设置 HLS_AGENT_BASE_URL / HLS_AGENT_API_KEY 指向远程兼容端点")
        print(SEP)
        return 1

    # 真的发一次最小请求，确认端到端可用
    print()
    print("  ---- 端到端测试 ----")
    try:
        client = LLMClient(cfg)
        out = client.complete(
            "你是测试助手。",
            [{"role": "user", "content": "只回复两个字：可用"}],
            max_tokens=64,
        )
        print(f"  调用成功，模型回复: {out.strip()[:40]}")
        print(SEP)
        return 0
    except Exception as e:
        print(f"  调用失败: {type(e).__name__}: {str(e)[:300]}")
        print(SEP)
        return 1


if __name__ == "__main__":
    sys.exit(main())
