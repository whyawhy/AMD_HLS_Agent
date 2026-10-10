# HLS Agent 评测结果

- 时间：2026-10-09 20:33:53
- 模式：**agent**（带工具反馈，失败重试至多 2 次）
- 采样轮数 k：1
- 是否评估综合：否
- 模型：`claude-fable-5`（backend=auto）
- 器件：`xczu3eg-sbva484-1-e`，时钟 5 ns
- 题目数：8

## 核心指标

| 指标 | 数值 |
| --- | --- |
| pass@1 | **100.0%** |
| 总墙钟 | 278.9 s |
| 单次平均墙钟 | 34.9 s |
| 单次最长墙钟 | 58.9 s |

## 分级判定分布

| 最高级别 | 题目数 |
| --- | --- |
| 可运行 | 8 |

## 分组通过率

| 变体 | 题目数 | pass@1 |
| --- | --- | --- |
| hls_polybench__fixed__small | 8 | 8/8 (100.0%) |

## 逐题明细

| 题目 | 变体 | 第1轮 | 最好级别 | 平均墙钟 |
| --- | --- | --- | --- | --- |
| 2mm | hls_polybench__fixed__small | 通过 | 可运行 | 27.8s |
| 3mm | hls_polybench__fixed__small | 通过 | 可运行 | 27.8s |
| atax | hls_polybench__fixed__small | 通过 | 可运行 | 25.2s |
| bicg | hls_polybench__fixed__small | 通过 | 可运行 | 26.2s |
| cholesky | hls_polybench__fixed__small | 通过 | 可运行 | 30.9s |
| correlation | hls_polybench__fixed__small | 通过 | 可运行 | 58.9s |
| covariance | hls_polybench__fixed__small | 通过 | 可运行 | 54.4s |
| doitgen | hls_polybench__fixed__small | 通过 | 可运行 | 27.6s |
