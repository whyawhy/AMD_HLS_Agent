# HLS Agent 评测结果

- 时间：2026-10-11 23:43:37
- 模式：**agent**（带工具反馈，失败重试至多 3 次）
- 采样轮数 k：1
- 是否评估综合：否
- 判定口径：严格（数值与参考 dump 一致才算通过）
- 模型：`claude-fable-5`（backend=auto）
- 器件：`xczu3eg-sbva484-1-e`，时钟 5 ns
- 题目数：24

## 核心指标

| 指标 | 数值 |
| --- | --- |
| pass@1 | **29.2%** |
| 总墙钟 | 5420.2 s |
| 单次平均墙钟 | 225.8 s |
| 单次最长墙钟 | 604.6 s |

## 分级判定分布

| 最高级别 | 题目数 |
| --- | --- |
| 可运行 | 8 |
| 可编译 | 2 |
| 可解析 | 8 |
| 未开始 | 6 |

## 分组通过率

| 变体 | 题目数 | pass@1 |
| --- | --- | --- |
| chstone | 4 | 0/4 (0.0%) |
| hls_polybench__fixed__small | 6 | 4/6 (66.7%) |
| machsuite | 6 | 0/6 (0.0%) |
| polybench | 7 | 3/7 (42.9%) |
| pp4fpga | 1 | 0/1 (0.0%) |

## 逐题明细

| 题目 | 变体 | 第1轮 | 最好级别 | 平均墙钟 |
| --- | --- | --- | --- | --- |
| aes_aes | machsuite | 失败 | 可解析 | 493.2s |
| dfadd | chstone | 失败 | 可解析 | 604.6s |
| dfdiv | chstone | 失败 | 可解析 | 338.4s |
| dfmul | chstone | 失败 | 可解析 | 326.6s |
| dfsin | chstone | 失败 | 可编译 | 98.5s |
| fdtd-2d | hls_polybench__fixed__small | 通过 | 可运行 | 302.7s |
| fft_strided | machsuite | 失败 | 可解析 | 188.6s |
| gemver | hls_polybench__fixed__small | 失败 | 未开始 | 429.0s |
| gramschmidt | hls_polybench__fixed__small | 失败 | 可运行 | 364.6s |
| lu | hls_polybench__fixed__small | 通过 | 可运行 | 208.9s |
| md_grid | machsuite | 失败 | 可编译 | 74.0s |
| md_knn | machsuite | 失败 | 可解析 | 282.7s |
| nussinov | hls_polybench__fixed__small | 通过 | 可运行 | 130.5s |
| nw_nw | machsuite | 失败 | 可解析 | 233.7s |
| polybench__cholesky | polybench | 失败 | 未开始 | 0.0s |
| polybench__correlation | polybench | 失败 | 未开始 | 0.0s |
| polybench__fdtd-2d | polybench | 通过 | 可运行 | 267.5s |
| polybench__gramschmidt | polybench | 失败 | 未开始 | 0.0s |
| polybench__jacobi-1d | polybench | 通过 | 可运行 | 241.1s |
| polybench__symm | polybench | 通过 | 可运行 | 133.6s |
| polybench__trmm | polybench | 失败 | 未开始 | 0.0s |
| pp4fpga_cordic | pp4fpga | 失败 | 未开始 | 0.0s |
| sort_radix | machsuite | 失败 | 可解析 | 347.0s |
| trmm | hls_polybench__fixed__small | 通过 | 可运行 | 355.1s |

## 失败分析

| 题目 | 轮次 | 卡在哪一级 | 原因摘要 |
| --- | --- | --- | --- |
| dfadd | 1 | 可解析 | 编译/仿真未通过，详见 results.json |
| dfdiv | 1 | 可解析 | 编译/仿真未通过，详见 results.json |
| dfmul | 1 | 可解析 | 编译/仿真未通过，详见 results.json |
| dfsin | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| gemver | 1 | 未开始 | 编译/仿真未通过，详见 results.json |
| gramschmidt | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| aes_aes | 1 | 可解析 | 编译/仿真未通过，详见 results.json |
| fft_strided | 1 | 可解析 | 编译/仿真未通过，详见 results.json |
| md_grid | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| md_knn | 1 | 可解析 | 编译/仿真未通过，详见 results.json |
| nw_nw | 1 | 可解析 | 编译/仿真未通过，详见 results.json |
| sort_radix | 1 | 可解析 | 编译/仿真未通过，详见 results.json |
| polybench__trmm | 1 | 未开始 | 跳过（超出总时间预算 5400s） |
| polybench__cholesky | 1 | 未开始 | 跳过（超出总时间预算 5400s） |
| polybench__correlation | 1 | 未开始 | 跳过（超出总时间预算 5400s） |
| polybench__gramschmidt | 1 | 未开始 | 跳过（超出总时间预算 5400s） |
| pp4fpga_cordic | 1 | 未开始 | 跳过（超出总时间预算 5400s） |
