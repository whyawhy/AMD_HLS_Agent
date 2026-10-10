# HLS Agent 评测结果

- 时间：2026-10-10 00:36:56
- 模式：**agent**（带工具反馈，失败重试至多 2 次）
- 采样轮数 k：1
- 是否评估综合：否
- 判定口径：严格（数值与参考 dump 一致才算通过）
- 模型：`claude-fable-5`（backend=auto）
- 器件：`xczu3eg-sbva484-1-e`，时钟 5 ns
- 题目数：17

## 核心指标

| 指标 | 数值 |
| --- | --- |
| pass@1 | **58.8%** |
| 总墙钟 | 37196.3 s |
| 单次平均墙钟 | 2188.0 s |
| 单次最长墙钟 | 36913.7 s |

## 分级判定分布

| 最高级别 | 题目数 |
| --- | --- |
| 可运行 | 10 |
| 可编译 | 5 |
| 可解析 | 1 |
| 未开始 | 1 |

## 分组通过率

| 变体 | 题目数 | pass@1 |
| --- | --- | --- |
| machsuite | 17 | 10/17 (58.8%) |

## 逐题明细

| 题目 | 变体 | 第1轮 | 最好级别 | 平均墙钟 |
| --- | --- | --- | --- | --- |
| aes_aes | machsuite | 失败 | 可解析 | 43.4s |
| bfs_bulk | machsuite | 通过 | 可运行 | 13.9s |
| bfs_queue | machsuite | 通过 | 可运行 | 14.4s |
| fft_strided | machsuite | 失败 | 可编译 | 19.8s |
| gemm_blocked | machsuite | 通过 | 可运行 | 13.5s |
| gemm_ncubed | machsuite | 通过 | 可运行 | 11.2s |
| kmp_kmp | machsuite | 通过 | 可运行 | 13.3s |
| md_grid | machsuite | 失败 | 可编译 | 28.6s |
| md_knn | machsuite | 失败 | 可编译 | 21.5s |
| nw_nw | machsuite | 失败 | 可编译 | 27.8s |
| sort_merge | machsuite | 通过 | 可运行 | 11.9s |
| sort_radix | machsuite | 失败 | 可编译 | 27.1s |
| spmv_crs | machsuite | 通过 | 可运行 | 10.8s |
| spmv_ellpack | machsuite | 通过 | 可运行 | 11.2s |
| stencil_stencil2d | machsuite | 通过 | 可运行 | 14.1s |
| stencil_stencil3d | machsuite | 通过 | 可运行 | 36913.7s |
| viterbi_viterbi | machsuite | 失败 | 未开始 | 0.0s |

## 失败分析

| 题目 | 轮次 | 卡在哪一级 | 原因摘要 |
| --- | --- | --- | --- |
| aes_aes | 1 | 可解析 | 编译/仿真未通过，详见 results.json |
| fft_strided | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| md_grid | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| md_knn | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| nw_nw | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| sort_radix | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| viterbi_viterbi | 1 | 未开始 | 跳过（超出总时间预算 2400s） |
