# OPTIMIZATION_AUDIT.md — 优化前的问题审计

- 审计日期：2026-10-13
- 审计对象：`AMD_HLS_Agent`（本目录），赛道 3.1 HLS Track
- 审计方式：读代码 + 复现历史评测中的失败样本（工作区证据在 `D:\hls_work`，
  备份在 `D:\__evidence_20261013`）
- 代码版本：`git rev-parse HEAD` = `87b1a9f`（审计时工作区干净）

本文件只记录**有证据的问题**。每条给出触发条件、证据路径、影响面与修改方案。

---

## 0. 现状基线（先说清楚哪些数字可比）

| 批次 | 模型 | 后端 | 题数 | pass@1（严格） | 总墙钟 |
| --- | --- | --- | --- | --- | --- |
| 20261010_001712 | claude-fable-5 | auto | 122 | 63.1% (77/122) | 2759s |
| 20261011_003719 | claude-fable-5 | auto | 122 | **72.1% (88/122)** | 3270s |
| 20261011_010105 | claude-fable-5 | auto | 56 | 75.0% | 1305s |
| 20261011_233938 | claude-fable-5 | auto | 27 | 11.1% | 1881s |
| 20261012_130807 | claude-fable-5 | auto | 17 | 17.6% | 1009s |

**重要**：后三批评测的题目集是**故意挑选的难题子集**（chstone 软浮点、machsuite、
定点 polybench）。把 11.1% 与 72.1% 直接对比是错的。同一批共同题对比：
`20261011_233938` 的 27 题在基准批次里通过 0 题、本批通过 3 题——
即当前代码在难题上并未退步，但**全题集的当前成绩是未知的**（最后一次全量跑是
`20261011_003719`，之后代码有改动）。

历史批次之间的题目集、模型、后端各不相同，**不能用作优化前后的公平对比**。
本轮优化必须用固定题集重跑，见 `OPTIMIZATION_TEST_REPORT.md`。

---

## 1. 问题清单

### P1（严重）模型输出被截断时，抽取器会静默取到"讲解用代码片段"

- **位置**：`hls_agent/llm.py::extract_source` / `_extract_source_raw`（回退路径 3）
  ，调用点 `hls_agent/runner.py:380`
- **触发**：模型这一轮回复里**没有** `<OUTPUT_CODE>` 标签（因为写到一半就被
  `max_tokens` 截断，还在输出分析文字），抽取器于是回退到"任意包含顶层函数名的
  围栏代码块"，把模型**讲解过程中随手贴的示意片段**当成实现。
- **证据**（`D:\hls_work\dfadd`，来自批次 `20261012_130807`）：

  | 原始输出 | 大小 | `<OUTPUT_CODE>` 开/闭 | 抽取结果 |
  | --- | --- | --- | --- |
  | `raw_llm_output_1.txt` | 11282 字符 | 1 / 1 | 11236 字符，335 行，**含 `#include`，完整** |
  | `raw_llm_output_2.txt` | 59055 字符 | 0 / 0 | **774 字符，28 行，无 include，含字面 `...`** |
  | `raw_llm_output_3.txt` | 51917 字符 | 0 / 0 | **1136 字符，41 行，无 include，含字面 `...`** |

  第 2、3 次尝试写入磁盘的 `dfadd.cpp` 是这样一段**没有 `#include`、用 `...`
  省略了函数体**的残片，必然编译/运行失败。
- **影响**：难题的重试环节**完全失效**——模型明明在认真推理，但产出被丢掉，
  换回来一段垃圾送进 Vitis，白付一次编译+仿真时间，并且把"模型能力不足"的
  错误结论写进评测报告。
- **修改方案**：
  1. `extract_source` 增加完整性校验：原文有 `<OUTPUT_CODE` 开标签却无闭标签
     → 判为**输出被截断**；抽到的代码里存在"整行只有 `...`"→ 判为**残片**。
     两者都抛专有异常 `OutputTruncated`，不再返回代码。
  2. `runner` 单独识别该异常，走**纯格式重试**（禁止写分析文字），并**完全跳过
     Vitis**，不再浪费一次 20~240 秒的工具往返。

### P2（严重）`env_limited` 分支一次失败就终止，放弃可修复的题

- **位置**：`hls_agent/runner.py:450-479`
- **触发**：`csim.exe` 返回 `3221225781`（`0xC0000135 STATUS_DLL_NOT_FOUND`）
  且无任何输出 → 代码立刻 `break`，不再尝试。
- **证据**（2026-10-13 复现，`--jobs 3`）：

  | 题目 | 生成代码里的数学调用 | 结果 |
  | --- | --- | --- |
  | `polybench__gramschmidt` | 裸 `sqrt(norm)` | 复现失败，`attempts=1`，手工运行 csim.exe 得 `rc=3221225781`、零输出 |
  | `pp4fpga_cordic` | 数学库函数 | 复现失败，`attempts=1` |
  | `polybench__cholesky` | 手写 `my_sqrt` | **通过** |
  | `polybench__correlation` | 手写内联 | **通过** |

  即：**同一套代码、同一台机器，写手写开方就过，写裸 `sqrt()` 就崩**。
  这不是环境不可用，而是**模型可修复的错误**，却被 `break` 判了死刑。
- **影响**：`polybench` 变体里凡是用了数学库函数的题全部直接判失败，
  连带 `attempts=1` 让评测报告看不出真实原因（详见 P3）。
- **修改方案**：
  1. `vitis.py::run_csim` 对"零输出的 DLL 缺失"启动失败**重试 2 次**（每次仅 ~0.1 秒），
     排除偶发启动失败。
  2. `runner` 把该情况改为**定向重试**：错误信息明确写出"你用了
     `sqrt()`/`std::sqrt()`，本机 Vitis 缺该运行时 DLL，改成手写内联实现
     （附牛顿迭代示例）"；重试仍失败才停。只有预算耗尽才 break。

### P3（严重）失败证据没有落盘，导致无法做失败分析

- **位置**：`eval.py::RunRecord`（只有 `error` / `dump_detail` 两个自由文本字段）；
  `render_summary` 的失败表（`eval.py:432`）
- **证据**：`eval_results/20261011_003938_agent_k1/summary.md` 的失败表里
  **24 行全部**是"编译/仿真未通过，详见 results.json"，而 `results.json`
  里也没有编译错误、返回码或失败阶段——`error` 字段只在抛异常时才非空。
  另外 `RunRecord.level` 是 `@property`，`asdict()` 不会序列化，落盘记录里
  根本没有"最高级别"字段。
- **影响**：`skill/analyze_failures.py` 只能靠翻 `D:\hls_work` 里的日志猜，
  且工作区会被下一次评测 `shutil.rmtree` 覆盖（`runner.py:272`），
  证据转瞬即逝。**没有这个，任何"从失败中学习"的流程都是空转。**
- **修改方案**：新增结构化字段并落盘：
  `failure_kind`（枚举）、`failure_detail`（一句根因）、`return_code`、
  `attempt_failure_kinds`（每次尝试的分类）、`code_hash`。同时把 `level`
  由 property 改为落盘字段。

### P4（中）数值容差读取了却从未参与判定，且提示词里报出错误的"容差 0"

- **位置**：`runner.py:289`（算 `tol`）、`runner.py:48-78`（`compare_dumps`
  硬编码 `REL_TOL = 1e-2`）、`runner.py:486`（`tol` 只用于拼字符串）
- **证据**：`eval_results/20261011_003719_agent_k1/results.json` 中
  `polybench__lu` 的 `dump_detail` 首行为
  **"数值与参考输出不符（相对容差 0）"**——`load_error_tolerance()` 对
  polybench 读到的 `tb_data_hls_error.json` 全为 0，于是把 **0** 写进了给模型看的
  提示词，而实际判定用的是 1e-2。模型被告知容差是 0，反馈信息自相矛盾。
- **语义澄清**（对数据集做的核查）：`tb_data_hls_error.json` 记录的是
  **参考实现自己相对软件黄金实现的偏差**（`polybench/2mm` 为
  `{"D": {"mae": 0.0, "mse": 0.0, "rmse": 0.0}}`，122 题中只有 28 题有这个文件），
  它**不是**允许误差阈值；官方评测器（`hls_eval/*.py`）根本没读这个文件。
  把它当容差用是双重错误（量纲混用 + 语义错位）。
- **影响**：反馈信息误导模型；判定口径与题目类型无关。
- **修改方案**：
  1. 把 `load_error_tolerance` 改名为 `load_reference_error`，只作**诊断**用途
     （说明参考实现自身的偏差量级），不再当作容差塞进提示词。
  2. `compare_dumps(got, ref, tol)` 显式接收容差；`tol` 按题目数值类型选：
     纯整数/位精确题目用**精确比较**，浮点/定点题目用相对容差（默认 1e-2，
     可用 `HLS_AGENT_DUMP_TOL` 覆盖）。**不放大任何容差。**

### P5（中）P1 的成因之一：重试提示词允许模型写长篇分析

- **位置**：`hls_agent/prompts.py::RETRY_SUFFIX`
- **证据**：`raw_llm_output_2/3.txt` 是 51~59KB 的**分析文字**（尾部停在
  "…(aSign != bSign) {" 这样的推理中途），没有一个 `<OUTPUT_CODE>` 标签。
  重试时又开了 `thinking="budget:2048"`（`runner.py:344`），思考 token 与正文
  抢同一份 `max_tokens`，把正文挤没了。
- **修改方案**：`RETRY_SUFFIX` 明确要求"只输出代码块、不得写任何分析文字"；
  并在截断发生后（P1 检出）走纯格式重试，不再叠加思考预算。

### P6（中）相同代码重复送进 Vitis

- **位置**：`runner.py:325,530`（`prev_code` 只用于拼提示词，从未比较）
- **证据**：`dfadd` 的 `attempt_2` 与 `attempt_3` 都是同一类残片；
  更一般地，`attempts=2 但两次代码完全相同` 的情况没有短路，
  每次都付一遍编译+仿真。
- **修改方案**：对抽出的代码取哈希，与上一次相同则**跳过 Vitis**，
  直接告诉模型"你上一版代码一个字没改"，并计入独立的重试预算。

### P7（低）静态检查漏掉一类必然编译失败的写法

- **位置**：`hls_agent/static_check.py::BLOCKERS`
- **证据**：`D:\hls_work\gemver\gemver.cpp` 第 1 行是
  `#define ap_fixed MY_AP_FIXED`，第 2 行才是 `#include "gemver.h"`——
  用宏改写题目头文件里的类型名，属于必然出错的写法，静态检查目前不拦。
- **修改方案**：新增 BLOCKER：源码中不允许 `#define` 重定义头文件里的类型名
  （`ap_fixed` / `ap_int` / `ap_uint` / `t_ap_fixed` 等，从实际头文件里提取）。
  同时把 P1 的"整行 `...`"也纳入 BLOCKER（双保险）。

### P8（低）`validate.py` 与当前评测流程脱节

- **位置**：`validate.py`
- **证据**：它校验的是离线题库工程的形态（要求 `{pid}/run.tcl`、`README.md`、
  `question.txt`、`{pid}_h` 宏保护），而评测流程产出的是
  `output/<题目>/<题目>.cpp` + `raw_llm_output_*.txt`。直接对 `output/` 跑会全 FAIL。
- **修改方案**：本轮**不改它的逻辑**（避免超范围重构），在 README 与测试报告里
  注明它只适用于离线题库，并新增面向真实流程的校验（已有 `skill/check_generated.py`
  与新增的 `selftest.py` 用例覆盖）。

---

## 2. 修改纪律

1. 先修 P1/P2/P3（明确的正确性/证据问题），再做 P4/P5/P6/P7。
2. 每步都补 `selftest.py` 回归用例；任何不能写成用例的改动不做。
3. **不放大数值容差、不增加重试次数来掩盖问题、不改题目/头文件/测试台。**
4. 全部改动在固定题集上做前后对比（`OPTIMIZATION_BENCHMARK.md`）。
