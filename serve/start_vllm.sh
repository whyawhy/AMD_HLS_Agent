#!/usr/bin/env bash
# 在带 GPU 的机器上启动 vLLM 推理服务。
#
# 这是赛道正式环境（赛事方配了显卡的那台）的推荐方式：vLLM 吞吐高、
# 支持并发，且模型权重完全本地、可断网运行。
#
# 用法：
#   bash serve/start_vllm.sh                 # 用默认模型
#   MODEL=Qwen/Qwen2.5-Coder-14B-Instruct bash serve/start_vllm.sh
#
# 启动后另开终端验证：
#   python serve/check.py
#
# 显存预算参考（赛道要求单卡 32GB 内）：
#   7B  FP16  约 15 GB   ← 最稳，留足 KV cache
#   14B FP16  约 28 GB   ← 接近上限
#   32B 4-bit 约 18 GB   ← 需 AWQ/GPTQ 量化权重
set -euo pipefail

MODEL="${MODEL:-Qwen/Qwen2.5-Coder-7B-Instruct}"
PORT="${PORT:-8000}"
GPU_UTIL="${GPU_UTIL:-0.92}"
MAX_LEN="${MAX_LEN:-32768}"

echo "启动 vLLM: model=${MODEL} port=${PORT} gpu_util=${GPU_UTIL} max_len=${MAX_LEN}"

if ! python -c "import vllm" 2>/dev/null; then
    echo "未检测到 vllm，正在安装（需要 CUDA/ROCm 环境）..."
    pip install vllm
fi

exec python -m vllm.entrypoints.openai.api_server \
    --model "${MODEL}" \
    --served-model-name "${MODEL}" \
    --host 0.0.0.0 \
    --port "${PORT}" \
    --gpu-memory-utilization "${GPU_UTIL}" \
    --max-model-len "${MAX_LEN}" \
    --dtype auto
