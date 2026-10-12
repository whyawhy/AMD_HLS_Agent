# HLS Agent 评测结果

- 时间：2026-10-11 23:08:17
- 模式：**agent**（带工具反馈，失败重试至多 3 次）
- 采样轮数 k：1
- 是否评估综合：否
- 判定口径：严格（数值与参考 dump 一致才算通过）
- 模型：`claude-fable-5`（backend=auto）
- 器件：`xczu3eg-sbva484-1-e`，时钟 5 ns
- 题目数：27

## 核心指标

| 指标 | 数值 |
| --- | --- |
| pass@1 | **11.1%** |
| 总墙钟 | 1881.2 s |
| 单次平均墙钟 | 69.7 s |
| 单次最长墙钟 | 534.6 s |

## 分级判定分布

| 最高级别 | 题目数 |
| --- | --- |
| 可运行 | 13 |
| 可编译 | 14 |

## 分组通过率

| 变体 | 题目数 | pass@1 |
| --- | --- | --- |
| chstone | 5 | 1/5 (20.0%) |
| hls_polybench__fixed__small | 7 | 1/7 (14.3%) |
| machsuite | 6 | 0/6 (0.0%) |
| polybench | 7 | 0/7 (0.0%) |
| pp4fpga | 1 | 0/1 (0.0%) |
| rosetta | 1 | 1/1 (100.0%) |

## 逐题明细

| 题目 | 变体 | 第1轮 | 最好级别 | 平均墙钟 |
| --- | --- | --- | --- | --- |
| aes_aes | machsuite | 失败 | 可编译 | 534.6s |
| df_mul64To128 | chstone | 通过 | 可运行 | 37.5s |
| dfadd | chstone | 失败 | 可编译 | 73.2s |
| dfdiv | chstone | 失败 | 可编译 | 67.7s |
| dfmul | chstone | 失败 | 可编译 | 50.7s |
| dfsin | chstone | 失败 | 可编译 | 100.0s |
| fdtd-2d | hls_polybench__fixed__small | 失败 | 可运行 | 79.0s |
| fft_strided | machsuite | 失败 | 可编译 | 152.3s |
| gemver | hls_polybench__fixed__small | 失败 | 可运行 | 65.6s |
| gramschmidt | hls_polybench__fixed__small | 失败 | 可运行 | 80.1s |
| jacobi-1d | hls_polybench__fixed__small | 通过 | 可运行 | 25.6s |
| lu | hls_polybench__fixed__small | 失败 | 可运行 | 126.7s |
| md_grid | machsuite | 失败 | 可编译 | 37.4s |
| md_knn | machsuite | 失败 | 可编译 | 31.1s |
| nussinov | hls_polybench__fixed__small | 失败 | 可运行 | 101.9s |
| nw_nw | machsuite | 失败 | 可编译 | 35.5s |
| polybench__cholesky | polybench | 失败 | 可编译 | 10.9s |
| polybench__correlation | polybench | 失败 | 可编译 | 12.2s |
| polybench__fdtd-2d | polybench | 失败 | 可运行 | 32.3s |
| polybench__gramschmidt | polybench | 失败 | 可编译 | 12.8s |
| polybench__jacobi-1d | polybench | 失败 | 可运行 | 26.7s |
| polybench__symm | polybench | 失败 | 可运行 | 26.7s |
| polybench__trmm | polybench | 失败 | 可运行 | 30.6s |
| pp4fpga_cordic | pp4fpga | 失败 | 可编译 | 16.5s |
| rendering_3d__projection | rosetta | 通过 | 可运行 | 15.4s |
| sort_radix | machsuite | 失败 | 可编译 | 38.5s |
| trmm | hls_polybench__fixed__small | 失败 | 可运行 | 59.7s |

## 失败分析

| 题目 | 轮次 | 卡在哪一级 | 原因摘要 |
| --- | --- | --- | --- |
| dfadd | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| dfdiv | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| dfmul | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| dfsin | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| fdtd-2d | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| gemver | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| gramschmidt | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| lu | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| nussinov | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| trmm | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| aes_aes | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| fft_strided | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| md_grid | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| md_knn | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| nw_nw | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| sort_radix | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| polybench__cholesky | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| polybench__correlation | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| polybench__fdtd-2d | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| polybench__gramschmidt | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| polybench__jacobi-1d | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| polybench__symm | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| polybench__trmm | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| pp4fpga_cordic | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
