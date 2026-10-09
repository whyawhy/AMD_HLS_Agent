#!/usr/bin/env bash
# 基线入口：同一推理服务、同一上下文配置，但**绕过智能体与技能包**。
#
# 赛道要求（3.1.5.2）：提示词仅含题目本身，单次生成、不重试、不调用工具。
# 它的结果作为「增益」项的对照基线，须与 run.sh 在同一次运行中产出。
#
# 用法：
#     bash run_baseline.sh <题目名> [输出目录]
#     bash run_baseline.sh 2mm
#
# 环境变量与 run.sh 一致（共用同一推理服务配置）。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
TASK="${1:?用法: bash run_baseline.sh <题目名> [输出目录]}"
OUT="${2:-${HLS_AGENT_OUT:-$ROOT/output_baseline}}"
WS="${HLS_AGENT_WORKSPACE:-/workspace/hls_work}"

cd "$ROOT"
mkdir -p "$OUT" "$WS"

echo "=== run_baseline.sh  题目=${TASK}  基线模式（单次生成、不重试、不看工具反馈） ==="

python hls_agent.py \
    --task "$TASK" \
    --workspace "$WS" \
    --baseline

SRC="$WS/$TASK"
if [ -d "$SRC" ]; then
    DEST="$OUT/$TASK"
    mkdir -p "$DEST"
    for f in "$SRC"/*.cpp; do
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
