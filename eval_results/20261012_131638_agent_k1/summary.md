# HLS Agent 评测结果

- 时间：2026-10-12 13:12:10
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
| 总墙钟 | 267.9 s |
| 单次平均墙钟 | 78.1 s |
| 单次最长墙钟 | 267.9 s |

## 分级判定分布

| 最高级别 | 题目数 |
| --- | --- |
| 可运行 | 3 |
| 可编译 | 1 |

## 分组通过率

| 变体 | 题目数 | pass@1 |
| --- | --- | --- |
| polybench | 3 | 2/3 (66.7%) |
| pp4fpga | 1 | 0/1 (0.0%) |

## 逐题明细

| 题目 | 变体 | 第1轮 | 最好级别 | 平均墙钟 |
| --- | --- | --- | --- | --- |
| polybench__cholesky | polybench | 通过 | 可运行 | 13.2s |
| polybench__correlation | polybench | 通过 | 可运行 | 14.4s |
| polybench__gramschmidt | polybench | 失败 | 可运行 | 267.9s |
| pp4fpga_cordic | pp4fpga | 失败 | 可编译 | 17.0s |

## 失败分析

| 题目 | 轮次 | 卡在哪一级 | 原因摘要 |
| --- | --- | --- | --- |
| polybench__gramschmidt | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| pp4fpga_cordic | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
