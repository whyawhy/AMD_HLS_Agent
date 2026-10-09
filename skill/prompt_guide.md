# 提示词模板设计说明

> 权威实现见 `hls_agent/prompts.py`。本文件只说明**为什么这样写**，
> 避免同一份正文在两处维护导致漂移。

## 生成提示词（zero-shot）

对齐 HLS-Eval 官方 `hls_eval/prompts.py::build_prompt_gen_zero_shot`，由三部分组成：

| 部分 | 作用 |
| --- | --- |
| `Overview` | 角色设定：面向 Vitis HLS 的硬件工程师 |
| `Task Description` | 任务定义：给定自然语言描述 + 头文件 + 测试台，生成实现 |
| `Output Format` | 输出格式：`<OUTPUT_CODE name="x.cpp">`，且只输出这一段 |

其后拼接 `## Task Inputs`，把三个输入文件按官方 XML 包法塞进去：

```
<INPUT_CODE name="kernel_description.md">...</INPUT_CODE name="kernel_description.md">
<INPUT_CODE name="xxx_tb.cpp">...</INPUT_CODE name="xxx_tb.cpp">
<INPUT_CODE name="xxx.h">...</INPUT_CODE name="xxx.h">
```

## 关键约束（踩坑得来，不是照抄）

### 1. 只生成一个 `.cpp`，不动头文件和测试台

官方评测流程（`hls_eval/eval.py::HLSGenerationZeroShotEvaluator`）断言生成的代码块
**恰好一个且以 `.cpp` 结尾**；头文件与测试台由题集提供并复制进构建目录。
若模型顺手改了头文件，评测时会被题集的原始头文件覆盖，改动作废。

### 2. 签名必须逐字匹配

测试台按一个**精确的签名**调用内核，参数个数、类型、数组维度、顺序都不能变
（参数名可以不同）。这是最常见的一类失败。

### 3. 输出格式约束要写死

模型经常返回带叙述的回答、markdown 围栏，甚至裸代码。提示词里明确要求
`<OUTPUT_CODE>` 格式，同时在 `hls_agent/llm.py::extract_source` 里做了五级回退，
两端一起兜底。

### 4. 数值类型沿用题集给定的 typedef

`hls_polybench__fixed__small` 变体的头文件里已有 `typedef ap_fixed<32,16> t_ap_fixed;`，
实现直接用它即可，**不要**自行改成 `float` / `double`——否则定点语义变化，
数值会比参考输出差出量级。

## 重试提示词

失败后在同一份基础提示词后追加 `## Previous Attempt Failed`，内容包括：

1. Vitis 的错误摘要（编译错误 / 仿真错误 / 综合错误，由 `vitis.error_excerpt` 提炼）
2. 上一次生成的完整代码
3. 再次强调必须匹配的签名

并要求「输出完整文件，不要只给 diff」——只给 diff 会导致抽取失败。

## 基线提示词

赛道要求 `run_baseline.sh` 「绕过智能体与技能包，提示词仅含题目本身，单次生成、
不重试、不调用工具」。

当前实现中，基线与智能体使用**同一份生成提示词**（即官方 zero-shot 口径），
差异只在「是否重试、是否使用工具反馈」。这样定义的好处是与 HLS-Eval 官方
zero-shot 基线口径一致、增益可解释。

> 若按赛道字面口径（基线提示词更"裸"）重定义，需同步修改
> `hls_agent/prompts.py` 与设计报告中的说明，并重跑基线数据。
