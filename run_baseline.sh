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
#     HLS_AGENT_PYTHON  手动指定解释器
#
# 基线公平性（赛道 3.1.5.2，代码里的对应保证）：
#   - 同一模型权重、同一推理后端、同一上下文配置：两者都从 LLMConfig.from_env()
#     构造，没有任何基线专属的模型或参数；
#   - 只给题目本身：不加技能包 system prompt（runner 里 use_skill = mode != "baseline"）；
#   - 单次生成、不重试、不看工具反馈：max_attempts 被强制为 1，
#     且生成后不进入重试循环（cli.py::cmd_run_tasks 里显式传 1）。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
TASK="${1:?用法: bash run_baseline.sh <题目名> [输出目录]}"
OUT="${2:-${HLS_AGENT_OUT:-$ROOT/output_baseline}}"
WS="${HLS_AGENT_WORKSPACE:-/workspace/hls_work}"

# 与 run.sh 同样的解释器探测，且**必须真的跑一下**：Windows 上
# `python3` / `python` 常常是应用商店的占位程序（command -v 找得到，
# 但执行即退出码 49 静默失败，表现为"窗口一闪就关"）
pick_python() {
    for cand in python3 py python; do
        command -v "$cand" >/dev/null 2>&1 || continue
        if "$cand" -c 'import sys' >/dev/null 2>&1; then
            printf '%s' "$cand"
            return 0
        fi
    done
    return 1
}

if [ -n "${HLS_AGENT_PYTHON:-}" ]; then
    PY="$HLS_AGENT_PYTHON"
elif ! PY="$(pick_python)"; then
    echo "[错误] 找不到可用的 Python（python3 / py / python 都不可用或都是应用商店占位程序）" >&2
    echo "       请用 HLS_AGENT_PYTHON 指定解释器绝对路径" >&2
    exit 2
fi

cd "$ROOT"
mkdir -p "$OUT" "$WS"

echo "=== run_baseline.sh  题目=${TASK}  基线模式（单次生成、不重试、不看工具反馈） ==="
echo "    Python=${PY}"

"$PY" hls_agent.py \
    --task "$TASK" \
    --workspace "$WS" \
    --baseline

SRC="$WS/$TASK"
if [ -d "$SRC" ]; then
    DEST="$OUT/$TASK"
    mkdir -p "$DEST"
    # 与 run.sh 一致：只要内核实现，不带测试台与各次尝试的中间产物
    for f in "$SRC"/*.cpp; do
        case "$(basename "$f")" in
            attempt_*|*_tb.cpp) ;;
            *) cp -f "$f" "$DEST/" 2>/dev/null || true ;;
        esac
    done
    cp -f "$SRC"/raw_llm_output_*.txt "$DEST/" 2>/dev/null || true
    echo "已产出: $DEST"
else
    echo "[警告] 未找到工作目录 $SRC" >&2
fi
