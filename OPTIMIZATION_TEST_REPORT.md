# OPTIMIZATION_TEST_REPORT.md — 测试命令、环境与结果

- 日期：2026-10-13
- 代码基线：`87b1a9f`（优化前）
- 环境：Windows 11 家用中文版；Vitis HLS **2026.1**（`E:\AMDdesign\2026.1\Vitis`）
  ；数据集 `E:\HLS-Eval\hls-eval-main\hls_eval_data`（122 题）；工作区 `D:\hls_work`
- 模型：`claude-fable-5`（backend=auto，走本机 Claude Desktop 网关；**开发期口径**，
  正式评测机需换成 `model/MODEL.md` 里声明的本地开源权重）
- 器件/时钟：`xczu3eg-sbva484-1-e` @ 5 ns

> 说明：本机是**开发机**（AMD Radeon 780M 核显），不是赛事方提供的 GPU 机器，
> 也没有 Docker。因此容器相关的验证无法在此完成，见「§5 未执行的测试」。

---

## 1. 阶段 A：静态与单元测试

### 1.1 回归自测

```bash
py selftest.py
```

**结果：29 项全部通过**（优化前 14 项，本次新增 15 项）。

新增用例与它们针对的真实缺陷一一对应：

| 新增用例 | 防的是哪个已发生的问题 |
| --- | --- |
| `test_extract_rejects_truncated_output` | dfadd 输出被 `max_tokens` 截断，抽取器把讲解片段当实现（审计 P1） |
| `test_extract_accepts_real_code_after_truncation_fix` | 防止上面的校验误伤正常输出 |
| `test_retry_prompt_forbids_prose` | 重试提示未禁止写分析文字（P5） |
| `test_static_check_blocks_macro_typedef_hijack` | gemver 的 `#define ap_fixed MY_AP_FIXED`（P7） |
| `test_static_check_blocks_skeleton_ellipsis` | 含整行 `...` 的骨架被放行到 Vitis（P1/P7） |
| `test_csim_launch_retries_transient_dll_miss` | 缺 DLL「零输出秒退」被当成永久失败（P2） |
| `test_mathlib_hint_distinguishes_tb_from_kernel` | 把测试台的数学库依赖误判成模型可修复（P2） |
| `test_error_classification_core_cases` | 失败只有自由文本、无法分类（P3） |
| `test_output_truncated_classified_as_extraction_error` | 截断未被单独归类（P1/P3） |
| `test_dump_tolerance_is_type_aware` | 整数题被 1e-2 浮点容差漏判（P4） |
| `test_compare_dumps_honours_tolerance` | **容差被读出却从未参与判定**（P4） |
| `test_reference_error_is_not_a_tolerance` | `tb_data_hls_error.json` 语义被误用（P4） |
| `test_best_attempt_beats_last_attempt` | 报告与交付产物取了最差的一次尝试（测试中新发现） |
| `test_run_kills_whole_process_tree_on_timeout` | 超时只杀直接子进程，clang 等孙子进程残留继续占 CPU |

### 1.2 `validate.py`

```bash
py validate.py output
```

**结论：不适用于当前评测流程，未作为通过依据。**

它校验的是**离线题库**产出的工程形态（要求 `{pid}/run.tcl`、`README.md`、
`question.txt`、`{pid}_H` 宏保护），而数据集评测流程产出的是
`output/<题目>/<题目>.cpp` + `raw_llm_output_*.txt`。对真实产物跑它一定全 FAIL。
本轮未改它的逻辑（避免超范围重构），已在 `README.md` 与 `skill/README.md` 里
注明适用范围。**真实流程的静态校验由 `selftest.py` 的用例与
`skill/check_generated.py` 覆盖。**

### 1.3 静态预检脚本

```bash
py skill/check_generated.py <生成的.cpp> --header <题目的.h> --top <函数名>
```

对已知正确的产物输出「参数个数一致」且无阻断项；对漏 include、参数个数不符、
宏改写类型名、`...` 骨架的样本分别报出对应阻断项（见 §1.1 用例）。

---

## 2. 阶段 B：固定题目回归（同日 A/B）

**题目集**：`polybench__cholesky`、`polybench__correlation`、`polybench__gramschmidt`、
`pp4fpga_cordic`（覆盖"内核用数学库""测试台用数学库""直接通过"三种情况）

**命令**（三次运行题目集、模型、器件、参数完全一致）：

```bash
py eval.py --tasks polybench__cholesky,polybench__correlation,polybench__gramschmidt,pp4fpga_cordic \
    --k 1 --mode agent --jobs 3 --outdir <目录>
```

**结果**：

| 题目 | 旧代码（18:21） | 中间态（18:34） | 新代码（18:44） |
| --- | --- | --- | --- |
| `polybench__cholesky` | 通过 | 通过 | **通过** |
| `polybench__correlation` | 通过 | 通过 | **通过** |
| `polybench__gramschmidt` | 失败·可编译·19.2s·1 次 | 失败·**可解析**·274.1s·3 次 | 失败·**可运行**·271.0s·3 次 |
| `pp4fpga_cordic` | 失败·可编译·22.7s·1 次 | 失败·**未开始**·325.7s·3 次 | 失败·可编译·**21.5s·1 次** |

**读法**：

1. 通过率在这 4 题上没有变化（2/4）——本轮改动**不是靠放宽标准提分**。
2. `gramschmidt` 的真实水平从「可编译」变成「**可运行**」：它现在能跑起来，
   失败原因是数值不一致（`TEST_MISMATCH`），而不是崩溃。中间态之所以掉到
   「可解析」，是**第 3 次尝试把代码改坏了**（漏 include、参数个数 3≠5）——
   这正是新加的「报告取最优尝试」修正的对象。
3. `cordic` 的墙钟从中间态的 325.7s 降回 **21.5s**：识别出数学库调用发生在
   **测试台**（数据集提供、不可修改）后，直接停止无效重试。
   中间态的 325.7s 就是没有这个区分时白付的代价。
4. 交付产物已修正：`D:\hls_work\polybench__gramschmidt\gramschmidt.cpp`
   现在与最优的 `attempt_2_gramschmidt.cpp` **逐字节相同**（55 行、含 `include`、
   含手写 `my_sqrt`），而改坏了的 `attempt_3` 仅留档。

### 2.1 硬限制的范围量化

```bash
py -c "... _tb_needs_mathlib(t) for t in dataset"
```

**测试台调用数学库（Windows 硬限制、模型无法修复）的题目：1 / 122**（仅
`pp4fpga/pp4fpga_cordic`）。其余 121 题的 DLL 问题都出现在内核侧，
属于模型可修复范围——这也是把「一次失败就终止」改成「定向重试」的依据。

---

## 3. 阶段 C：代表性题集批量评测

**命令**：

```bash
# 11 题代表性题集（覆盖 fixed__small / polybench 的浮点与定点 / chstone / machsuite / pp4fpga）
py eval.py --tasks 2mm,3mm,atax,correlation,covariance,cholesky,fft_strided,aes_aes,dfadd,dfmul,pp4fpga_cordic \
    --k 1 --mode agent --jobs 3 --outdir eval_results/_stageC_11tasks

# 最慢三题的定向复跑（验证截断退让）
py eval.py --tasks dfadd,dfmul,fft_strided --k 1 --mode agent --jobs 3 --outdir eval_results/_stageC2_confirm
```

**结果（11 题）**：通过 **6/11**，总墙钟 883s。逐题明细与前后对照见
`OPTIMIZATION_BENCHMARK.md`。

**同子集的历史基准也是 6/11**（`eval_results/20261011_003719_agent_k1`）——
即**本轮通过的题数没有变化**。本轮的实际收益是：

1. 报告与交付产物取最优尝试（`gramschmidt` 的级别从「可解析」回到「可运行」，
   交付的 `.cpp` 从坏代码换成好代码）；
2. 失败原因从"没有信息"变成可分类、可统计、可推导修复方向；
3. 消除了无效重试的等待（`cordic` 325.7s → 21.5s）；
4. 慢题三连合计墙钟 **1239.8s → 1063.3s（−14%）**。

**P50 / P95 单题墙钟**（11 题样本，样本量小，仅作参考）：
P50 = 31.2s，P95 = 491.9s。

**未做的**：全 122 题批量、`pass@5`、综合（第四级）、智能体 vs 基线的增益对照。
见 §5。

---

## 4. 从未修改的评测输入（可核查）

以下均**未被修改**（本轮改动只碰 `hls_agent/`、`skill/`、入口脚本、文档）：

```bash
git status --porcelain          # 应先确认数据集与工作区不在仓库内
```

- 数据集目录 `E:\HLS-Eval\hls-eval-main\hls_eval_data`：**不在本仓库内**，
  本轮未写入任何文件（工作区副本在 `D:\hls_work`，由 `copy_task_into` 生成）。
- 题目头文件、测试台、参考 dump：`copy_task_into` 是**只读复制**，
  runner 只覆盖 `<source_name>.cpp` 这一个文件。
- 没有跳过任何失败用例，没有把失败改判成成功，没有硬编码参考答案。

---

## 5. 未执行 / 受限的测试（如实列出）

| 项目 | 状态 | 原因 | 需要的验证方案 |
| --- | --- | --- | --- |
| 容器构建与断网运行 | **未执行** | 本机无 Docker、无赛事方官方基础镜像，且开发机非 GPU 机器 | 在赛事方基础镜像上 `docker build` 后，断网 `docker run ... bash run.sh 2mm`；确认 `requests` 已存在或 wheel 已随包 |
| vLLM + 本地开源权重 | **未执行** | 开发机为 Radeon 780M 核显，不支持 ROCm/vLLM | 在 GPU 机器上按 `model/MODEL.md` 启动后跑 `serve/check.py` 与 §3 的题集 |
| 综合（csynth，第四级） | **未执行** | 本轮 `--synth` 未开启；单题 csynth 约 1~3 分钟，先用「可运行」级回归定位正确性 | GPU 机器上跑 `py eval.py --tasks <代表题集> --synth` |
| 全 122 题批量 | **未执行** | 单轮全量在开发机上约 1 小时（历史记录 3270s，且未含重试开销） | 迁移到评测机后跑一次全量，产出 pass@1 / pass@5 |
| `validate.py` 对真实产物 | **不适用** | 见 §1.2 | 若需要，另写面向数据集流程的工程校验 |
| 模型声明准确性 | **待填** | 正式权重尚未在目标机器上部署 | 按 `model/MODEL.md` 的 A 段逐项实测填写（显存、上下文、校验和） |

**以上未被验证的项目，本报告不做任何"已通过"的声明。**
