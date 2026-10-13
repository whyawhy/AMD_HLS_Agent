# HLS Agent 评测结果

- 时间：2026-10-13 19:08:11
- 模式：**agent**（带工具反馈，失败重试至多 3 次）
- 采样轮数 k：1
- 是否评估综合：否（未跑综合的题在分级里显示「略过」，不会被当成「综合通过」）
- 判定口径：严格（数值与参考 dump 一致才算通过）
- 模型：`claude-fable-5`（backend=auto）
- 器件：`xczu3eg-sbva484-1-e`，时钟 5 ns
- 题目数：3

## 核心指标

| 指标 | 数值 |
| --- | --- |
| pass@1 | **0.0%** |
| 总墙钟 | 412.6 s |
| 单次平均墙钟 | 354.4 s |
| 单次最长墙钟 | 412.6 s |

## 分级判定分布

| 最高级别 | 题目数 |
| --- | --- |
| 可编译 | 3 |

## 分组通过率

| 变体 | 题目数 | pass@1 |
| --- | --- | --- |
| chstone | 2 | 0/2 (0.0%) |
| machsuite | 1 | 0/1 (0.0%) |

## 逐题明细

| 题目 | 变体 | 第1轮 | 最好级别 | 平均墙钟 |
| --- | --- | --- | --- | --- |
| dfadd | chstone | 失败 | 可编译 | 250.1s |
| dfmul | chstone | 失败 | 可编译 | 400.6s |
| fft_strided | machsuite | 失败 | 可编译 | 412.6s |

## 失败分析

### 失败类别分布

| 失败类别 | 题数 | 是否值得重试 | 修复方向 |
| --- | --- | --- | --- |
| `TEST_MISMATCH`（测试结果不一致） | 3 | 是 | 给出参考值/实际值、最大误差位置与饱和迹象 |

### 逐题明细

| 题目 | 轮次 | 卡在哪一级 | 失败类别 | 尝试 | 每次尝试卡在哪 | 原因摘要 |
| --- | --- | --- | --- | --- | --- | --- |
| dfadd | 1 | 可编译 | `TEST_MISMATCH` | 3 | TEST_MISMATCH → SOURCE_EXTRACTION_ERROR → TEST_MISMATCH | testbench 运行返回码 13，输出如下： ...b_input=bff0000000000000 expected=7ff0000000000000 output=7ff0000000000000 (inf) a_input=3ff0000000000000 b_input=8000000000000000 e |
| dfmul | 1 | 可编译 | `TEST_MISMATCH` | 3 | TEST_MISMATCH → STATIC_CHECK_ERROR → STATIC_CHECK_ERROR | testbench 运行返回码 8，输出如下： ...ed=7ff0000000000000 output=7ff0000000000000 (inf) a_input=0000000000000000 b_input=3ff0000000000000 expected=0000000000000000 output= |
| fft_strided | 1 | 可编译 | `TEST_MISMATCH` | 3 | TEST_MISMATCH → STATIC_CHECK_ERROR → SOURCE_EXTRACTION_ERROR | testbench 运行返回码 4294967295，输出如下： ...751360220.842621 (0.000001) ERROR: 1010 (real): -182526263876.193237 (0.000001) ERROR: 1010 (img): -133948559158.660446 (0.0 |
