#!/usr/bin/env bash
# 启动本地 Ollama 并确保模型已下载。
#
# Ollama 适合开发期与无独显的机器（走 CPU 或 Vulkan）。正式评测请在
# 带显卡的机器上用 serve/start_vllm.sh。
#
# 用法：
#   bash serve/start_ollama.sh
#   MODEL=qwen2.5-coder:14b bash serve/start_ollama.sh
set -euo pipefail

MODEL="${MODEL:-qwen2.5-coder:7b}"

if ! command -v ollama >/dev/null 2>&1; then
    echo "未找到 ollama。安装方式见 https://ollama.com/download"
    exit 1
fi

# 后台拉起服务（已在跑则忽略）
if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    echo "启动 ollama serve ..."
    nohup ollama serve >/tmp/ollama.log 2>&1 &
    for _ in $(seq 1 30); do
        curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
        sleep 1
    done
fi

echo "拉取模型 ${MODEL}（已存在会跳过）..."
ollama pull "${MODEL}"

echo
echo "就绪。设置环境变量后即可运行智能体："
echo "  export HLS_AGENT_BACKEND=ollama"
echo "  export HLS_AGENT_MODEL=${MODEL}"
echo "  python hls_agent.py --task 2mm"
