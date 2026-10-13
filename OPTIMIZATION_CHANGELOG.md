# OPTIMIZATION_CHANGELOG.md — 逐项修改记录

审计见 `OPTIMIZATION_AUDIT.md`，测试证据见 `OPTIMIZATION_TEST_REPORT.md`。

改动纪律：只做有证据支持的修改；**未放大任何数值容差**；未修改题目、头文件、
测试台或参考数据；未增加重试次数上限来掩盖问题。

---

## M1 输出截断不再被当成"实现"（对应 P1）

| 项目 | 内容 |
| --- | --- |
| 改动文件 | `hls_agent/llm.py`、`hls_agent/runner.py`、`hls_agent/prompts.py` |
| 为什么 | 模型回复被 `max_tokens` 截断时，抽取器回退到「任意含顶层函数名的围栏块」，把模型讲解用的骨架片段当成实现写盘（实测 `dfadd`：59055 字符回复里 0 个 `<OUTPUT_CODE>` 标签，取出 774 字符含字面 `...` 的残片） |
| 行为变化 | ① 新增 `OutputTruncated` 异常；`extract_source` 在「有开标签无闭标签」或「抽到的代码含整行 `...`」时抛它，不再返回残片。② `runner` 单独识别该异常，走纯格式重试并**完全跳过 Vitis**。③ `RETRY_SUFFIX` 增加硬性要求：回复必须以 `<OUTPUT_CODE ...>` 开头、以 `</OUTPUT_CODE ...>` 结尾，不得写分析文字 |
| 风险 | 极小。真实 HLS 内核不会出现孤立 `...` 行；`printf(const char*, ...)` 之类的 stripped 内容不是孤立省略号，有专门回归用例覆盖 |
| 回归用例 | `test_extract_rejects_truncated_output`、`test_extract_accepts_real_code_after_truncation_fix`、`test_retry_prompt_forbids_prose` |

## M2 环境类失败区分「可修复」与「硬限制」（对应 P2）

| 项目 | 内容 |
| --- | --- |
| 改动文件 | `hls_agent/vitis.py`、`hls_agent/runner.py` |
| 为什么 | 原逻辑：`csim.exe` 返回 `0xC0000135` 且零输出 → 立刻 `break`。但 2026-10-13 复现证明这是**模型可修复**的：同一台机器上 `polybench__cholesky`（手写 `my_sqrt`）、`polybench__correlation` 通过，而 `polybench__gramschmidt`（裸 `sqrt()`）稳定崩溃 |
| 行为变化 | ① `_run_exe_retrying()`：对"零输出 DLL 缺失"重试 3 次（每次约 0.1s），排除偶发启动失败；有输出的正常失败**不重试**。② runner 把该情况改成**定向重试**，错误信息明确要求把数学库调用改写成手写内联实现。③ 新增 `_tb_needs_mathlib()`：若数学库调用发生在**测试台**（数据集提供、不可修改，如 `pp4fpga_cordic`），直接停止重试并如实标注为 Windows 硬限制 |
| 风险 | 低。硬限制题只多付最多一次重试；已有 `eval_results` 中的 `attempts` 字段可监控是否异常增长 |
| 回归用例 | `test_csim_launch_retries_transient_dll_miss`、`test_mathlib_hint_distinguishes_tb_from_kernel` |

## M3 失败证据结构化并落盘（对应 P3）

| 项目 | 内容 |
| --- | --- |
| 改动文件 | 新增 `hls_agent/errors.py`；`hls_agent/runner.py`、`eval.py` |
| 为什么 | 失败表 24 行全是"详见 results.json"，而 results.json 里没有原因；`RunRecord.level` 是 `@property`，`asdict()` 根本不落盘；工作区会被下一次评测 `rmtree` 覆盖 |
| 行为变化 | ① 新增 16 类失败枚举 + `classify_generate/compile/run/synth` + `is_retryable()` + 中文说明与修复方向。② `Attempt`/`TaskReport` 增加 `failure_kind` / `failure_detail` / `return_code` / `code_hash`。③ `RunRecord` 增加 `level`（改为落盘字段）、`failure_kind`、`failure_detail`、`failure_sequence`（每次尝试分别卡在哪）、`return_code`、`code_hash`。④ `summary.md` 的失败分析改为「失败类别分布表 + 逐题明细表」 |
| 关键判定 | CHStone 风格测试台把"不匹配用例数"当 `main` 返回值 → 归为 `TEST_MISMATCH` 而不是崩溃；`0xC0000135` 零输出 → `ENVIRONMENT_ERROR`；两者都不与"编译错误"混为一谈 |
| 回归用例 | `test_error_classification_core_cases`、`test_output_truncated_classified_as_extraction_error` |

## M4 数值容差真正参与判定，并修正语义（对应 P4）

| 项目 | 内容 |
| --- | --- |
| 改动文件 | `hls_agent/runner.py` |
| 为什么 | `tol` 被读出来、被写进给模型看的字符串（于是出现"相对容差 0"这种自相矛盾的话），却从未进入 `compare_dumps`（那里硬编码 `1e-2`）。而 `tb_data_hls_error.json` 记录的是**参考实现自身的偏差**，不是容差（122 题中仅 28 题有此文件，官方评测器从不读它） |
| 行为变化 | ① `load_error_tolerance` → `load_reference_error`，只作诊断，不再当容差、不进模型反馈。② `compare_dumps(got, ref, tol)` 显式接收容差。③ 新增 `dump_tolerance(task)`：纯整数题 **tol=0（精确比较）**，浮点/定点题 1e-2，可用 `HLS_AGENT_DUMP_TOL` 覆盖 |
| 口径变化 | **整体更严**：整数题（CHStone 软浮点、MachSuite AES）原来被 1e-2 的浮点容差放过去，属于漏判 |
| 风险 | 可能让个别原本"通过"的整数题转为失败——这是纠正漏判，不是退步；已用同样题目集复跑确认 |
| 回归用例 | `test_dump_tolerance_is_type_aware`、`test_compare_dumps_honours_tolerance`、`test_reference_error_is_not_a_tolerance` |

## M5 无效重试拦截：代码一字未改就不再付 Vitis（对应 P6）

| 项目 | 内容 |
| --- | --- |
| 改动文件 | `hls_agent/runner.py`、`hls_agent/prompts.py` |
| 为什么 | `prev_code` 只用于拼提示词，从不比较。实测 `dfadd` 第 2、3 次尝试产出完全相同的残片，每次都白付一遍编译+仿真 |
| 行为变化 | 对抽出的代码取 SHA1；与上一次相同则**跳过 Vitis**，改用 `build_no_progress_prompt()`（"你上一版代码一个字没改，必须真的改"),并明确要求修改点 |
| 回归用例 | 由 `test_extract_*` 与 M1 的用例间接覆盖；行为可在 `summary.md` 的 `failure_sequence` 与 `attempts` 上观察 |

## M6 静态预检补两类高置信阻断（对应 P7）

| 项目 | 内容 |
| --- | --- |
| 改动文件 | `hls_agent/static_check.py` |
| 为什么 | ① 实测某次生成的 `gemver.cpp` 第 1 行是 `#define ap_fixed MY_AP_FIXED`，第 2 行才 `#include`，会把 Vitis 自己的头一起改坏；② `...` 骨架片段此前能直接放行到 Vitis |
| 行为变化 | 新增两条 BLOCKER：用 `#define` 改写题目头文件里的类型名（类型名从真实头文件的 `typedef` 中提取，兜底含 `ap_fixed/ap_ufixed/ap_int/ap_uint/ap_float`）；源码含整行 `...` |
| 风险 | 低。`#define` 重定义头文件类型名没有任何正当用法 |
| 回归用例 | `test_static_check_blocks_macro_typedef_hijack`、`test_static_check_blocks_skeleton_ellipsis` |

## M7 报告与交付产物取「最优尝试」，而非最后一次（回归测试中新发现）

| 项目 | 内容 |
| --- | --- |
| 改动文件 | `hls_agent/runner.py`、`eval.py` |
| 为什么 | 原来 `report.grade = 最后一次尝试的 grade`。但重试未必越改越好：实测 `polybench__gramschmidt` 第 1、2 次尝试都生成了带 `#include` 的完整实现（第 2 次已能跑通，只是数值不符），**第 3 次模型反而把代码改坏了**（漏 include、参数个数 3≠5）。按最后一次判定，这道题会被记成「可解析」——比真实水平低两级；更糟的是 `run.sh` 拷出去的交付产物就是那份坏代码 |
| 行为变化 | 新增 `_attempt_rank()`（级别优先，同级优先数值也对的那次）；收尾时用最优尝试的 grade / dump / failure_kind 出报告；若最优不是最后一次，**把最优代码写回最终文件名**（各次 `attempt_N_*.cpp` 原样留档），并在日志里说明 |
| 验证 | 同题复跑：`gramschmidt` 的级别从「可解析」变为「**可运行**」，`gramschmidt.cpp` 与 `attempt_2_gramschmidt.cpp` 逐字节相同 |
| 回归用例 | `test_best_attempt_beats_last_attempt` |

## M8 超时后回收整棵进程树 + 各阶段超时可配（对应 §3.3.6/3.3.7）

| 项目 | 内容 |
| --- | --- |
| 改动文件 | `hls_agent/vitis.py`、`hls_agent/config.py`、`hls_agent/runner.py`、`eval.py` |
| 为什么 | ① `subprocess.run(timeout=…)` 只杀直接子进程，而 `vitis-run` 会再拉起 clang / 综合器，超时后这些孙子进程会继续占 CPU 拖慢整批评测；② 编译与运行共用一个超时数字，而两者量级完全不同；③ 超时只在 eval.py 的 CLI 参数里能改，不符合「配置集中、不散落在多个模块」的要求 |
| 行为变化 | `_run()` 改用 `Popen` + `_kill_tree()`（Windows `taskkill /F /T`、POSIX 杀进程组）；`AgentConfig` 拆出 `compile_timeout_s`（默认 600）/ `csim_timeout_s`（240）/ `csynth_timeout_s`（1800），分别可由 `HLS_AGENT_COMPILE_TIMEOUT` / `HLS_AGENT_CSIM_TIMEOUT` / `HLS_AGENT_SYNTH_TIMEOUT` 覆盖，CLI 参数默认值改为 `None` 以便让环境变量生效 |
| 注意 | **没有调大任何超时来掩盖问题**：默认值保持原有量级，只是把「编译」和「运行」拆开并允许配置 |
| 回归用例 | `test_run_kills_whole_process_tree_on_timeout` |

## M9 入口脚本的解释器探测（容器兼容）

| 项目 | 内容 |
| --- | --- |
| 改动文件 | `run.sh`、`run_baseline.sh` |
| 为什么 | 两个入口都写死 `python`。官方基础镜像里往往只有 `python3`，会直接 `command not found`；开发机（本机）反而只有 `py`/`python` |
| 行为变化 | 按 `HLS_AGENT_PYTHON` → `python3` → `python` 顺序探测，找不到就以退出码 2 明确报错；启动时打印实际用的解释器与是否启用综合 |
| 回归风险 | 无（纯增强，保留 `python` 作为最后的候选） |

## M10 依赖锁定 + 断网构建说明

| 项目 | 内容 |
| --- | --- |
| 改动文件 | `Dockerfile`、`requirements.txt` |
| 为什么 | 原来写 `requests>=2.28`，构建结果随时间漂移，不满足「可复现」；且断网沙箱下 `pip install` 会失败，而原文件没有说明 |
| 行为变化 | 锁定 `requests==2.32.3`（`REQUESTS_VERSION` 可用 `--build-arg` 覆盖）；Dockerfile 里写明离线构建的 `--no-index --find-links` 做法，并标注**必须在赛事方基础镜像上实测一次** |
| 诚实说明 | **本机无 Docker、无官方基础镜像，容器相关改动只经过静态检查，未实际构建验证**。见 `OPTIMIZATION_TEST_REPORT.md` §5 |

## M11 上一轮被截断时，重试退让思考预算（阶段 C 暴露）

| 项目 | 内容 |
| --- | --- |
| 改动文件 | `hls_agent/runner.py`（新增 `_retry_thinking()`） |
| 为什么 | 阶段 C 显示失败题的墙钟反而变长：`dfadd` 412.7s、`dfmul` 491.9s。逐项拆开看，重试的 `thinking="budget:2048"` 让输出涨到 50KB 量级，在写到一半时被 `max_tokens` 截断——思考 token 和正文抢同一份预算，一轮约 130 秒基本白花（审计 P1 的同一根因） |
| 行为变化 | 首轮不给思考（求快）；重试且上一轮**未**被截断时给 2048 token 预算；重试且上一轮**被**截断时显式关闭思考，先把代码写完 |
| 验证 | `dfadd` 412.7s → **250.1s（−39%）**；三题合计 1239.8s → **1063.3s（−14%）**。单题仍受模型随机性影响（`fft_strided` 反而变慢），结论强度有限 |
| 回归用例 | `test_retry_thinking_backs_off_after_truncation` |

## M12 失败分类的精度修正（阶段 C 暴露）

| 项目 | 内容 |
| --- | --- |
| 改动文件 | `hls_agent/errors.py`、`hls_agent/runner.py` |
| 为什么 | ① `fft_strided` 打印 `ERROR: 1010 ...` 后 `exit(-1)`（Windows 上是 4294967295），旧逻辑把任何非零返回码都归为「仿真程序崩溃」——**把"数值算错了"误报成"程序崩了"**，给出的修复方向完全不同；② 代码抽出来了但不含顶层函数（`not parse_ok`）这条路径没有设置失败类别，报告里落成 `UNKNOWN_ERROR`（`dfmul` 就是这样） |
| 行为变化 | ① 新增 `_is_windows_exception()`：只有 0xC0000000~0xC000FFFF 才算真崩溃（`0xC0000005` 访问违例、`0xC0000374` 堆损坏、`0xC0000135` 缺 DLL）；其余"有输出的非零返回码"归为 `TEST_MISMATCH`——程序完整跑完了，是测试台判定的不一致。② `not parse_ok` 路径标注 `SIGNATURE_ERROR` |
| 验证 | `fft_strided` 由 `CSIM_RUNTIME_ERROR` 纠正为 **`TEST_MISMATCH`**；`dfmul` 由 `UNKNOWN_ERROR` 纠正为 **`TEST_MISMATCH`（返回码 8 = 8 个用例不符）**；`aes_aes`（`0xC0000374` 堆损坏）仍正确判为 `CSIM_RUNTIME_ERROR` |
| 回归用例 | `test_error_classification_core_cases`、`test_best_attempt_beats_last_attempt` |

## 未改动（明确说明）

| 项 | 原因 |
| --- | --- |
| `validate.py` | 它校验的是**离线题库**工程形态（要求 `run.tcl`/`README.md`/`question.txt`/宏保护），与当前评测流程产出的 `output/<题>/<题>.cpp` 形态不匹配。本轮不超范围重写，已在 README 与测试报告里记录该限制 |
| `run.sh` 是否默认跑综合 | **保持默认不跑**。赛题对 `run.sh` 的定义是「读题 → 产出代码」，四级判定由评测方执行；而且主用户明确抱怨过开启综合后墙钟从 250s 涨到 660s。改法是在脚本头部与 README 里写清 `HLS_AGENT_SYNTH=1` 才覆盖第四级，并确认**未跑综合时一律显示「略过」、不会被当成「综合通过」** |
| `_warmup_model` 里的冗余 import | 无害，改动无收益 |
| 重试次数上限、容差数值本身 | **未增加重试次数、未放大容差**（整数题反而收紧为精确比较） |
| `knowledge_base.py` / `matcher.py` / `codegen.py` | 属离线题库路径，不参与数据集评测流程；本轮无证据表明它们影响通过率，不做无依据改动 |
