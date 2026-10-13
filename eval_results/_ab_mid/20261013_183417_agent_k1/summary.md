# HLS Agent 评测结果

- 时间：2026-10-13 18:28:34
- 模式：**agent**（带工具反馈，失败重试至多 3 次）
- 采样轮数 k：1
- 是否评估综合：否
- 判定口径：严格（数值与参考 dump 一致才算通过）
- 模型：`claude-fable-5`（backend=auto）
- 器件：`xczu3eg-sbva484-1-e`，时钟 5 ns
- 题目数：4

## 核心指标

| 指标 | 数值 |
| --- | --- |
| pass@1 | **50.0%** |
| 总墙钟 | 343.0 s |
| 单次平均墙钟 | 158.9 s |
| 单次最长墙钟 | 325.7 s |

## 分级判定分布

| 最高级别 | 题目数 |
| --- | --- |
| 可运行 | 2 |
| 可解析 | 1 |
| 未开始 | 1 |

## 分组通过率

| 变体 | 题目数 | pass@1 |
| --- | --- | --- |
| polybench | 3 | 2/3 (66.7%) |
| pp4fpga | 1 | 0/1 (0.0%) |

## 逐题明细

| 题目 | 变体 | 第1轮 | 最好级别 | 平均墙钟 |
| --- | --- | --- | --- | --- |
| polybench__cholesky | polybench | 通过 | 可运行 | 17.3s |
| polybench__correlation | polybench | 通过 | 可运行 | 18.3s |
| polybench__gramschmidt | polybench | 失败 | 可解析 | 274.1s |
| pp4fpga_cordic | pp4fpga | 失败 | 未开始 | 325.7s |

## 失败分析

### 失败类别分布

| 失败类别 | 题数 | 是否值得重试 | 修复方向 |
| --- | --- | --- | --- |
| `SIGNATURE_ERROR`（函数签名不符） | 1 | 是 | 把头文件里的真实顶层函数声明原样贴给模型 |
| `SOURCE_EXTRACTION_ERROR`（输出被截断 / 只给了骨架） | 1 | 是 | 输出被截断/只给了骨架；要求只输出完整代码块、不要写分析 |

### 逐题明细

| 题目 | 轮次 | 卡在哪一级 | 失败类别 | 尝试 | 每次尝试卡在哪 | 原因摘要 |
| --- | --- | --- | --- | --- | --- | --- |
| polybench__gramschmidt | 1 | 可解析 | `SIGNATURE_ERROR` | 3 | ENVIRONMENT_ERROR → TEST_MISMATCH → SIGNATURE_ERROR | 没有 #include "gramschmidt.h"，编译会找不到声明; 参数个数不一致：头文件 3 个，实现 5 个 |
| pp4fpga_cordic | 1 | 未开始 | `SOURCE_EXTRACTION_ERROR` | 3 | ENVIRONMENT_ERROR → ENVIRONMENT_ERROR → SOURCE_EXTRACTION_ERROR | 抽取到的 cordic.cpp 不完整：抽取结果为空。（多半是模型把代码写在分析文字里、或输出被 max_tokens 截断） |
