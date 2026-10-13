# 技能包 (skill)

赛道对技能包的要求是「提示词模板、校验脚本、踩坑清单等领域知识的组织」。
本目录就是这三类知识的落点，也是设计报告里「技能包提炼过程」的对应物。

## 目录内容

| 文件 | 类型 | 作用 | 什么时候用 |
| --- | --- | --- | --- |
| [prompt_guide.md](prompt_guide.md) | 提示词模板 | 生成提示词的设计说明与关键约束 | 改提示词前先读 |
| [check_generated.py](check_generated.py) | 校验脚本 | 花 Vitis 时间之前的静态预检 | 生成之后、跑 Vitis 之前 |
| [analyze_failures.py](analyze_failures.py) | 分析脚本 | 把一批评测的失败按**结构化类别**归类 | 每批评测跑完后 |
| [compare_runs.py](compare_runs.py) | 分析脚本 | 智能体 vs 基线的增益对照 | 出增益报告时 |
| [pitfalls.md](pitfalls.md) | 踩坑清单 | 实际踩过并解决的坑，含现象/根因/规避 | 定位新问题时查表 |

## 技能包的知识怎么进来（提炼流程）

**不允许**把单个失败案例直接变成全局规则。每条规则都要走完：

```
失败案例 → 根因分析 → 形成候选规则 → 针对性回归测试 → 记录效果 → 纳入技能包
```

对应到本仓库的落地方式：

| 步骤 | 具体做法 |
| --- | --- |
| 找案例 | `python skill/analyze_failures.py <批次目录>`，看「重复根因」表 |
| 看根因 | 该题在 `results.json` 里的 `failure_kind` / `failure_detail` / `failure_sequence` |
| 写规则 | 追加到 `pitfalls.md`，必须标注**适用范围**（哪类变体、哪种数值类型）与**验证证据** |
| 补测试 | 在 `selftest.py` 里补一条对应用例（改代码后能防复发） |
| 验效果 | 固定题目集重跑，**分变体**比通过率——只看总体会掩盖局部退步 |

一条规则的完整结构（`pitfalls.md` 里每条都按这个写）：

- **适用条件**：哪类题、哪种数值类型下成立
- **问题表现**：工具输出里能看到什么（返回码、日志字样、数值指纹）
- **已验证根因**：怎么确定是它，做了哪些对照实验
- **修复方法**：具体怎么改
- **副作用 / 误用后果**：错误套用会怎样
- **验证案例**：题目名 + 结果

## 三类知识的来源与验证

### 提示词模板

**来源**：对齐 HLS-Eval 官方 `hls_eval/prompts.py` 的 zero-shot 生成提示，
使本方案的生成口径与官方排行榜可比。权威实现见 `hls_agent/prompts.py`，
本目录只记录设计理由与约束（避免两份正文漂移）。

**领域知识按数据类型条件注入**（`prompts.py::build_agent_skill_system`）：

| 分组 | 注入条件 | 内容 |
| --- | --- | --- |
| `AGENT_SKILL_COMMON` | 所有题目 | 精确复刻算法、边界值、禁用 `std::` 数学函数 |
| `AGENT_SKILL_FIXEDPOINT` | 题头含 `ap_fixed` | 合并除法、eps 保护、禁 float 中间量、±32768 饱和 |

无条件注入定点规则会让 `double` 内核被引导去规避 double，**实测反而退步**
（见 `pitfalls.md` 第 19 条）。

### 校验脚本

**来源**：Vitis 单次 csim 约 20~30 秒、csynth 约 1~2 分钟，而有些问题不编译就能
发现。把它们提前到静态检查，可以省下大量等待时间。

**规则分级**（`static_check.py`）：

| 级别 | 何时使用 | 例子 |
| --- | --- | --- |
| BLOCKER | 有明确证据表明代码结构不合法或破坏规定接口 | 漏 `#include`、参数个数不符、`printf`、`malloc`、用 `#define` 改写头文件类型名、整行 `...` 骨架 |
| WARNING | 有风险但必须进一步验证 | 出现 `float`/`double`、裸 `sqrt/pow`、除法无保护 |
| INFO | 诊断信息 | 参数个数一致 |

**只有 BLOCKER 才能直接跳过 Vitis**；WARNING 一律放行到工具链验证，
避免把可能正确的代码拦在门外。

### 踩坑清单

**来源**：`pitfalls.md` 里每一条都来自开发过程中**实际发生并已修复**的问题，
不是预先设想的。

**有效性验证**（每条规避措施都有对应回归用例）：

| 坑 | 固化位置 | 回归用例 |
| --- | --- | --- |
| 中文路径 | `config.py::resolve_workspace` | 传入非 ASCII 路径直接报错 |
| csim.exe 缺浮点算子 DLL | `vitis.py::csim_env` | 2mm 的 csim.exe 能正常跑出 dump |
| 缺 DLL「零输出秒退」偶发 | `vitis.py::_run_exe_retrying` | `test_csim_launch_retries_transient_dll_miss` |
| 缺数学库 DLL（内核调用） | `runner.py` 定向重试 + `_mathlib_dll_hint` | `test_mathlib_hint_distinguishes_tb_from_kernel` |
| 缺数学库 DLL（测试台调用） | `runner.py::_tb_needs_mathlib` 直接停止 | 同上 |
| **输出被 max_tokens 截断** | `llm.py::extract_source` 抛 `OutputTruncated` | `test_extract_rejects_truncated_output` |
| **容差读了但没参与判定** | `runner.py::compare_dumps(tol)` / `dump_tolerance` | `test_compare_dumps_honours_tolerance` |
| 宏改写头文件类型名 | `static_check.py` BLOCKER | `test_static_check_blocks_macro_typedef_hijack` |
| 定点容差 | `runner.py::compare_dumps` | 3mm 相对误差 1.7e-3 判为一致 |
| 输出格式不符 | `llm.py::extract_source` 五级回退 | `test_extract_plain_xml` 等 |
| 编译/运行两级分离 | `vitis.py::run_csim` | `test_vitis_cmd_dispatch` |

## 使用方式

静态预检（生成之后、跑 Vitis 之前）：

```bash
python skill/check_generated.py <生成的.cpp> --header <给定的.h> --top <函数名>
```

退出码 0 表示没有阻断问题，可以进入 Vitis 验证；1 表示有问题，先修再跑，
或把问题摘要作为重试提示回灌给模型。

失败分析（每批评测之后）：

```bash
python skill/analyze_failures.py eval_results/<时间戳>_<模式>_k<k>
```

增益对照（智能体 vs 基线）：

```bash
python skill/compare_runs.py eval_results/<基线批> eval_results/<智能体批>
```

> `compare_runs.py` 会强制校验两次运行的**题目集完全一致**，否则只比较共同
> 题目并给出警告——历史批次题目集不同，直接比通过率是错的。
