# 模型声明 (MODEL.md)

> 赛道要求：模型须为**可本地部署的开源权重**，须声明来源与版本；须能在**单张 32GB 卡**
> 上完整容纳，不允许跨卡；上下文长度自定但须如实声明。
>
> 本文件分两部分：**A. 正式提交配置**（在带显卡的机器上填写）和
> **B. 开发期配置**（当前开发机的临时设置，不用于提交）。

---

## A. 正式提交配置

### A.1 模型来源

| 项目 | 内容 |
| --- | --- |
| 模型名称 | `待填写`（例如 Qwen2.5-Coder-7B-Instruct） |
| 来源仓库 | `待填写`（HuggingFace / ModelScope 完整地址） |
| 版本 / 修订号 | `待填写`（commit hash 或 release tag） |
| 权重校验和 | `待填写`（SHA256，`sha256sum *.safetensors`） |
| 是否微调 | `否` / `是（若是，填写 A.4）` |

### A.2 量化方式

| 项目 | 内容 |
| --- | --- |
| 精度 | `待填写`（FP16 / BF16 / AWQ 4-bit / GPTQ 4-bit / GGUF Q4_K_M） |
| 量化工具 | `待填写`（如 autoawq / GPTQModel / llama.cpp quantize） |
| 量化校准数据 | `待填写`（若为训练后量化） |

### A.3 资源占用与上下文（实测）

| 项目 | 内容 |
| --- | --- |
| 实测显存占用 | `待填写` GB（用 `nvidia-smi` / `rocm-smi` 读取稳态值） |
| 单卡是否容纳 | `是`（赛道要求 ≤ 32 GB） |
| 上下文长度 | `待填写` tokens（max_model_len） |
| 单次输出上限 | `待填写` tokens（对应 `HLS_AGENT_MAX_TOKENS`） |
| 推理后端 | `待填写`（vLLM 版本号 / Ollama 版本号） |
| 并发数 | `待填写` |

**显存预算参考（单卡 32GB）：**

| 模型规模 | 精度 | 权重占用 | 评价 |
| --- | --- | --- | --- |
| 7B | FP16 | ~15 GB | 余量充足，推荐 |
| 14B | FP16 | ~28 GB | 接近上限，KV cache 需压缩 |
| 32B | 4-bit | ~18 GB | 需 AWQ/GPTQ 量化权重 |

### A.4 微调信息（若 A.1 选择"是"）

| 项目 | 内容 |
| --- | --- |
| 基座模型 | `待填写` |
| 微调方式 | `待填写`（LoRA / QLoRA / 全参数） |
| 训练数据来源 | `待填写` |
| 微调权重地址 | `待填写`（须开源） |

### A.5 启动方式

在本仓库根目录执行：

```bash
bash serve/start_vllm.sh
```

环境变量（详见 `serve/env.example`）：

```bash
export HLS_AGENT_BACKEND=openai
export HLS_AGENT_OPENAI_BASE_URL=http://127.0.0.1:8000
export HLS_AGENT_MODEL=<A.1 中的模型名称>
```

自检：

```bash
python serve/check.py
```

---

## B. 开发期配置（当前开发机，**不用于提交**）

开发机为 **AMD Radeon 780M 核显**（无独立显存，共享 31 GB 系统内存），
不在 ROCm 官方支持列表内，因此**无法运行 vLLM**，开发期使用以下两种方式之一：

| 方式 | 命令 | 说明 |
| --- | --- | --- |
| 本地 Ollama（Windows） | `serve\start_ollama.bat` | CPU / Vulkan 推理，约 3~8 token/s |
| 远程兼容端点 | 设置 `HLS_AGENT_BASE_URL` / `HLS_AGENT_API_KEY` | 仅开发期便利，评测环境断网不可用 |

代码通过 `hls_agent/backends.py` 做了后端抽象，按
「本地 Ollama → 本地 OpenAI 兼容服务 → 远程端点」顺序自动探测，
**切换到正式 GPU 机器只需改环境变量，无需改动任何代码**。

---

## 附：本文件与提交物的对应关系

| 赛道要求 | 本文件对应部分 |
| --- | --- |
| 模型来源（仓库地址与版本号，或权重校验和） | A.1 |
| 量化方式 | A.2 |
| 实测显存占用 | A.3 |
| 上下文配置 | A.3 |
| 微调信息（若适用） | A.4 |
