# HLS Agent —— 提交用容器
#
# 赛道要求「提交物为一个基于官方基础镜像构建的容器，在断网沙箱中运行」。
# 官方基础镜像含 Vivado / Vitis 工具链，镜像名以赛事方公布的为准。
#
# 构建：
#     docker build --build-arg BASE_IMAGE=<官方基础镜像> -t hls-agent .
#
# 运行（评测方挂载题集，容器内断网）：
#     docker run --rm -v /path/to/hls_eval_data:/workspace/hls_eval_data \
#         hls-agent bash run.sh 2mm

ARG BASE_IMAGE
FROM ${BASE_IMAGE}

# ---------------------------------------------------------------------------
# Python 依赖
# ---------------------------------------------------------------------------
# 只依赖 requests，**锁定版本**以保证不同时间构建出的镜像行为一致（可复现要求）。
# 若基础镜像已经带了同版本 requests，pip 会直接跳过，无需联网。
#
# ⚠️ 断网构建：若基础镜像里没有 requests，下面的 pip 需要能访问 PyPI。
#    要真正离线构建，先把 wheel 放进构建上下文再改成本地安装：
#        COPY wheels/ /wheels/
#        RUN python3 -m pip install --no-index --find-links=/wheels -r requirements.txt
#    默认走联网路径；正式提交前必须在赛事方规定的基础镜像上实测一次。
ARG REQUESTS_VERSION=2.32.3
RUN python3 -m pip install --no-cache-dir "requests==${REQUESTS_VERSION}" \
    || pip install --no-cache-dir "requests==${REQUESTS_VERSION}"

# ---------------------------------------------------------------------------
# 代码
# ---------------------------------------------------------------------------
WORKDIR /workspace/hls_agent_project
COPY hls_agent.py eval.py validate.py requirements.txt ./
COPY hls_agent/ ./hls_agent/
COPY skill/ ./skill/
COPY serve/ ./serve/
COPY model/ ./model/
COPY run.sh run_baseline.sh ./
RUN chmod +x run.sh run_baseline.sh serve/*.sh

# ---------------------------------------------------------------------------
# 运行环境
# ---------------------------------------------------------------------------
# Vitis 工作区必须是纯 ASCII 路径（Vitis 打不开含中文的路径）
ENV HLS_AGENT_WORKSPACE=/workspace/hls_work

# 题目集挂载点（评测方注入）
ENV HLS_AGENT_DATASET=/workspace/hls_eval_data

# 模型接入：指向容器内/本地网段的推理服务。
# 正式环境请在构建或运行时按实际部署覆盖，并同步更新 model/MODEL.md。
ENV HLS_AGENT_BACKEND=auto

# 单次输出上限：推理模型会先输出思考内容，太小会导致正文被截断
ENV HLS_AGENT_MAX_TOKENS=16384

# ---------------------------------------------------------------------------
# 默认入口：跑一道题并产出代码
# ---------------------------------------------------------------------------
# 评测方也可直接覆盖为 run_baseline.sh 以复现基线对照
ENTRYPOINT ["bash", "run.sh"]
