# HLS Agent 评测结果

- 时间：2026-10-12 12:51:18
- 模式：**agent**（带工具反馈，失败重试至多 3 次）
- 采样轮数 k：1
- 是否评估综合：否
- 判定口径：严格（数值与参考 dump 一致才算通过）
- 模型：`claude-fable-5`（backend=auto）
- 器件：`xczu3eg-sbva484-1-e`，时钟 5 ns
- 题目数：17

## 核心指标

| 指标 | 数值 |
| --- | --- |
| pass@1 | **17.6%** |
| 总墙钟 | 1009.3 s |
| 单次平均墙钟 | 191.2 s |
| 单次最长墙钟 | 388.6 s |

## 分级判定分布

| 最高级别 | 题目数 |
| --- | --- |
| 可运行 | 3 |
| 可编译 | 9 |
| 可解析 | 2 |
| 未开始 | 3 |

## 分组通过率

| 变体 | 题目数 | pass@1 |
| --- | --- | --- |
| chstone | 4 | 0/4 (0.0%) |
| hls_polybench__fixed__small | 2 | 0/2 (0.0%) |
| machsuite | 6 | 2/6 (33.3%) |
| polybench | 4 | 1/4 (25.0%) |
| pp4fpga | 1 | 0/1 (0.0%) |

## 逐题明细

| 题目 | 变体 | 第1轮 | 最好级别 | 平均墙钟 |
| --- | --- | --- | --- | --- |
| aes_aes | machsuite | 通过 | 可运行 | 152.2s |
| dfadd | chstone | 失败 | 可解析 | 342.8s |
| dfdiv | chstone | 失败 | 未开始 | 327.2s |
| dfmul | chstone | 失败 | 可解析 | 320.2s |
| dfsin | chstone | 失败 | 可编译 | 309.4s |
| fft_strided | machsuite | 失败 | 可编译 | 339.0s |
| gemver | hls_polybench__fixed__small | 失败 | 未开始 | 388.6s |
| gramschmidt | hls_polybench__fixed__small | 失败 | 未开始 | 379.0s |
| md_grid | machsuite | 失败 | 可编译 | 155.8s |
| md_knn | machsuite | 失败 | 可编译 | 74.4s |
| nw_nw | machsuite | 失败 | 可编译 | 281.8s |
| polybench__cholesky | polybench | 失败 | 可编译 | 11.8s |
| polybench__correlation | polybench | 失败 | 可编译 | 12.3s |
| polybench__gramschmidt | polybench | 失败 | 可编译 | 13.4s |
| polybench__trmm | polybench | 通过 | 可运行 | 110.5s |
| pp4fpga_cordic | pp4fpga | 失败 | 可编译 | 16.6s |
| sort_radix | machsuite | 通过 | 可运行 | 15.9s |

## 失败分析

| 题目 | 轮次 | 卡在哪一级 | 原因摘要 |
| --- | --- | --- | --- |
| polybench__cholesky | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| polybench__correlation | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| polybench__gramschmidt | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| pp4fpga_cordic | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| dfadd | 1 | 可解析 | 编译/仿真未通过，详见 results.json |
| dfdiv | 1 | 未开始 | 编译/仿真未通过，详见 results.json |
| dfmul | 1 | 可解析 | 编译/仿真未通过，详见 results.json |
| dfsin | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| gemver | 1 | 未开始 | 编译/仿真未通过，详见 results.json |
| gramschmidt | 1 | 未开始 | 编译/仿真未通过，详见 results.json |
| fft_strided | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| md_grid | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| md_knn | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| nw_nw | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
