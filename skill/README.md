# 技能包 (skill)

赛道对技能包的要求是「提示词模板、校验脚本、踩坑清单等领域知识的组织」。
本目录就是这三类知识的落点，也是设计报告里「技能包提炼过程」的对应物。

## 目录内容

| 文件 | 类型 | 作用 |
| --- | --- | --- |
| [prompt_guide.md](prompt_guide.md) | 提示词模板 | 生成提示词的设计说明与关键约束 |
| [check_generated.py](check_generated.py) | 校验脚本 | 花 Vitis 时间之前的静态预检 |
| [pitfalls.md](pitfalls.md) | 踩坑清单 | 实际踩过并解决的坑，含现象/根因/规避 |

## 三类知识的来源与验证

### 提示词模板

**来源**：对齐 HLS-Eval 官方 `hls_eval/prompts.py` 的 zero-shot 生成提示，
使本方案的生成口径与官方排行榜可比。权威实现见 `hls_agent/prompts.py`，
本目录只记录设计理由与约束（避免两份正文漂移）。

**有效性验证**：在 `hls_polybench__fixed__small/2mm` 上，按该提示词生成的实现
一次通过全部四级判定（可解析 / 可编译 / 可运行 / 可综合）。

### 校验脚本

**来源**：Vitis 单次 csim 约 20~30 秒、csynth 约 1~2 分钟，而有些问题不编译就能
发现（漏 include、函数签名不符、用了不可综合的写法）。把它们提前到静态检查，
可以省下大量等待时间。

**有效性验证**：对已知正确的生成产物跑检查，应输出「参数个数一致」且无阻断项；
对故意去掉 `#include` 或改错参数个数的样本，应报出对应阻断项。

### 踩坑清单

**来源**：`pitfalls.md` 里的每一条都来自开发过程中**实际发生并已修复**的问题，
不是预先设想的。条目都带「现象 / 根因 / 规避」三段，便于他人直接复用。

**有效性验证**：规避措施都已固化进代码，并有对应的回归验证：

| 坑 | 固化位置 | 验证方式 |
| --- | --- | --- |
| 中文路径 | `config.py::resolve_workspace` | 传入非 ASCII 路径应直接报错 |
| csim.exe 缺 DLL | `vitis.py::csim_env` | 2mm 的 csim.exe 能正常跑出 dump |
| max_tokens 截断 | `backends.py` 响应解析 | 正文为空时有明确报错并带 stop_reason |
| 定点容差 | `runner.py::compare_dumps` | 3mm 相对误差 1.7e-3 判为一致 |
| 输出格式不符 | `llm.py::extract_source` | 五级回退，均能抽出代码 |
| 编译/运行两级分离 | `vitis.py::run_csim` | 分别记录两个阶段的返回码 |

## 使用方式

静态预检（生成之后、跑 Vitis 之前）：

```bash
python skill/check_generated.py <生成的.cpp> --header <给定的.h> --top <函数名>
```

退出码 0 表示没有阻断问题，可以进入 Vitis 验证；1 表示有问题，先修再跑，
或把问题摘要作为重试提示回灌给模型。
