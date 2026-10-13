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
#     HLS_AGENT_SYNTH       设为 1 则额外跑 csynth（补上第四级「可综合」）
#     HLS_AGENT_OUT         默认输出目录
#     HLS_AGENT_PYTHON      手动指定解释器
#
# 关于是否跑综合：赛题对 run.sh 的定义是「读题 → 产出代码」，所以默认只跑到
# 「可运行」这一级；要覆盖完整四级判定（可解析/可编译/可运行/可综合）就设
# HLS_AGENT_SYNTH=1。注意 csynth 很慢（本地每题约 1~3 分钟），批量评测时开着
# 会让总墙钟显著变长。**未跑综合时报告里一律显示「略过」，绝不会被当成
# 「综合通过」**——这一点在 eval.py 的 summary 与 report.headline() 里都有保证。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
TASK="${1:?用法: bash run.sh <题目名> [输出目录]}"
OUT="${2:-${HLS_AGENT_OUT:-$ROOT/output}}"
WS="${HLS_AGENT_WORKSPACE:-/workspace/hls_work}"
ATTEMPTS="${HLS_AGENT_ATTEMPTS:-3}"

# 解释器探测。**必须真的跑一下**，不能只看 `command -v`：
# Windows 上 `python3` / `python` 常常解析到应用商店的占位程序
# （C:\Users\<你>\AppData\Local\Microsoft\WindowsApps\python3），
# 它存在、能被 command -v 找到，但一执行就以退出码 49 静默失败——
# 表现为"脚本一闪就退出，什么都没输出"。
# `py` 是 Windows 官方启动器，容器里则有真正的 python3。
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

EXTRA=()
if [ "${HLS_AGENT_SYNTH:-0}" = "1" ]; then
    EXTRA+=(--synth)
fi

echo "=== run.sh  题目=${TASK}  智能体模式（带工具反馈与重试） ==="
echo "    Python=${PY}   综合（第四级判定）=${HLS_AGENT_SYNTH:-0}"

"$PY" hls_agent.py \
    --task "$TASK" \
    --workspace "$WS" \
    --attempts "$ATTEMPTS" \
    "${EXTRA[@]+"${EXTRA[@]}"}"

# 把该题最终产出的代码收集到输出目录，方便评测方取用
SRC="$WS/$TASK"
if [ -d "$SRC" ]; then
    DEST="$OUT/$TASK"
    mkdir -p "$DEST"
    # 只取内核实现与模型原始输出。测试台和头文件由数据集提供（不可修改，
    # 提交时也不需要重复带上），各次尝试的中间产物 attempt_N_*.cpp 另行留档。
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
