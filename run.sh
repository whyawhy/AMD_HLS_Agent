#!/usr/bin/env bash
# 单题入口：读题 -> 生成 -> 验证 -> 产出代码
#
# 这是赛事方评测时调用的入口（对应赛道要求的 run.sh）。它跑的是**完整智能体**：
# 领域提示词 + 调 Vitis 编译仿真 + 失败时把工具输出回灌重试。
# 对照实验请用 run_baseline.sh（同推理服务，但单次生成、不重试、不看工具反馈）。
#
# 用法：
#     bash run.sh <题目名> [输出目录]
#     bash run.sh 2mm
#     bash run.sh 2mm /tmp/out
#
# 环境变量：
#     HLS_AGENT_WORKSPACE   Vitis 工作区（默认 /workspace/hls_work，必须纯 ASCII）
#     HLS_AGENT_ATTEMPTS    重试上限（默认 3）
#     HLS_AGENT_SYNTH       设为 1 则额外跑 csynth
#     HLS_AGENT_OUT         默认输出目录
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
TASK="${1:?用法: bash run.sh <题目名> [输出目录]}"
OUT="${2:-${HLS_AGENT_OUT:-$ROOT/output}}"
WS="${HLS_AGENT_WORKSPACE:-/workspace/hls_work}"
ATTEMPTS="${HLS_AGENT_ATTEMPTS:-3}"

cd "$ROOT"
mkdir -p "$OUT" "$WS"

EXTRA=()
if [ "${HLS_AGENT_SYNTH:-0}" = "1" ]; then
    EXTRA+=(--synth)
fi

echo "=== run.sh  题目=${TASK}  智能体模式（带工具反馈与重试） ==="

python hls_agent.py \
    --task "$TASK" \
    --workspace "$WS" \
    --attempts "$ATTEMPTS" \
    "${EXTRA[@]+"${EXTRA[@]}"}"

# 把该题最终产出的代码收集到输出目录，方便评测方取用
SRC="$WS/$TASK"
if [ -d "$SRC" ]; then
    DEST="$OUT/$TASK"
    mkdir -p "$DEST"
    # 只取内核实现与模型原始输出，测试台和头文件由题集提供、不需要重复提交
    for f in "$SRC"/*.cpp; do
        # 跳过各次尝试的中间产物（attempt_N_*.cpp）
        case "$(basename "$f")" in
            attempt_*) ;;
            *) cp -f "$f" "$DEST/" 2>/dev/null || true ;;
        esac
    done
    cp -f "$SRC"/raw_llm_output_*.txt "$DEST/" 2>/dev/null || true
    echo "已产出: $DEST"
else
    echo "[警告] 未找到工作目录 $SRC" >&2
fi
