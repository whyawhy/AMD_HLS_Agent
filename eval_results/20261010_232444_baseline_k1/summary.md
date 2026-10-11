# HLS Agent 评测结果

- 时间：2026-10-10 22:45:50
- 模式：**baseline**（单次生成、不重试、不看工具反馈）
- 采样轮数 k：1
- 是否评估综合：否
- 判定口径：严格（数值与参考 dump 一致才算通过）
- 模型：`claude-fable-5`（backend=auto）
- 器件：`xczu3eg-sbva484-1-e`，时钟 5 ns
- 题目数：122

## 核心指标

| 指标 | 数值 |
| --- | --- |
| pass@1 | **68.0%** |
| 总墙钟 | 2333.9 s |
| 单次平均墙钟 | 19.1 s |
| 单次最长墙钟 | 265.5 s |

## 分级判定分布

| 最高级别 | 题目数 |
| --- | --- |
| 可运行 | 98 |
| 可编译 | 24 |

## 分组通过率

| 变体 | 题目数 | pass@1 |
| --- | --- | --- |
| c2hlsc | 12 | 12/12 (100.0%) |
| chstone | 20 | 11/20 (55.0%) |
| flowgnn | 3 | 3/3 (100.0%) |
| gnnbuilder | 3 | 3/3 (100.0%) |
| hls_polybench__fixed__small | 28 | 18/28 (64.3%) |
| machsuite | 17 | 10/17 (58.8%) |
| polybench | 28 | 19/28 (67.9%) |
| pp4fpga | 3 | 0/3 (0.0%) |
| rosetta | 8 | 7/8 (87.5%) |

## 逐题明细

| 题目 | 变体 | 第1轮 | 最好级别 | 平均墙钟 |
| --- | --- | --- | --- | --- |
| 2mm | hls_polybench__fixed__small | 通过 | 可运行 | 27.0s |
| 3mm | hls_polybench__fixed__small | 通过 | 可运行 | 25.6s |
| add_round_key | c2hlsc | 通过 | 可运行 | 18.3s |
| aes | c2hlsc | 通过 | 可运行 | 20.0s |
| aes_aes | machsuite | 失败 | 可编译 | 265.5s |
| atax | hls_polybench__fixed__small | 通过 | 可运行 | 23.7s |
| bfs_bulk | machsuite | 通过 | 可运行 | 14.4s |
| bfs_queue | machsuite | 通过 | 可运行 | 13.6s |
| bicg | hls_polybench__fixed__small | 通过 | 可运行 | 24.4s |
| block | c2hlsc | 通过 | 可运行 | 10.6s |
| block_mm | pp4fpga | 失败 | 可编译 | 15.4s |
| cholesky | hls_polybench__fixed__small | 通过 | 可运行 | 30.6s |
| compute_neighbor_tables | gnnbuilder | 通过 | 可运行 | 14.2s |
| correlation | hls_polybench__fixed__small | 失败 | 可运行 | 32.6s |
| covariance | hls_polybench__fixed__small | 失败 | 可运行 | 26.3s |
| cusums | c2hlsc | 通过 | 可运行 | 11.9s |
| des | c2hlsc | 通过 | 可运行 | 28.6s |
| df_add128 | chstone | 通过 | 可运行 | 12.0s |
| df_countLeadingZeros32 | chstone | 通过 | 可运行 | 18.0s |
| df_countLeadingZeros64 | chstone | 失败 | 可编译 | 17.5s |
| df_extractFloat64Exp | chstone | 通过 | 可运行 | 12.1s |
| df_extractFloat64Frac | chstone | 通过 | 可运行 | 12.1s |
| df_extractFloat64Sign | chstone | 通过 | 可运行 | 11.4s |
| df_float64_abs | chstone | 通过 | 可运行 | 11.1s |
| df_float64_ge | chstone | 失败 | 可编译 | 16.2s |
| df_float64_is_nan | chstone | 通过 | 可运行 | 13.4s |
| df_float64_is_signaling_nan | chstone | 通过 | 可运行 | 13.3s |
| df_float64_le | chstone | 失败 | 可编译 | 13.2s |
| df_float64_neg | chstone | 通过 | 可运行 | 11.4s |
| df_mul64To128 | chstone | 失败 | 可编译 | 13.7s |
| df_packFloat64 | chstone | 通过 | 可运行 | 12.0s |
| df_propagateFloat64NaN | chstone | 失败 | 可编译 | 13.6s |
| df_shift64RightJamming | chstone | 通过 | 可运行 | 12.0s |
| dfadd | chstone | 失败 | 可编译 | 32.6s |
| dfdiv | chstone | 失败 | 可编译 | 28.7s |
| dfmul | chstone | 失败 | 可编译 | 25.6s |
| dfsin | chstone | 失败 | 可编译 | 32.0s |
| digit_recognition__popcount | rosetta | 通过 | 可运行 | 12.4s |
| doitgen | hls_polybench__fixed__small | 通过 | 可运行 | 25.3s |
| durbin | hls_polybench__fixed__small | 失败 | 可运行 | 24.3s |
| fdtd-2d | hls_polybench__fixed__small | 失败 | 可运行 | 27.7s |
| fft_strided | machsuite | 失败 | 可编译 | 13.8s |
| fgnn_linear | flowgnn | 通过 | 可运行 | 16.0s |
| fgnn_linear_input_stationary | flowgnn | 通过 | 可运行 | 16.8s |
| fgnn_linear_output_stationary | flowgnn | 通过 | 可运行 | 15.2s |
| floyd-warshall | hls_polybench__fixed__small | 通过 | 可运行 | 22.6s |
| gather_node_neighbors | gnnbuilder | 通过 | 可运行 | 12.1s |
| gemm | hls_polybench__fixed__small | 通过 | 可运行 | 25.8s |
| gemm_blocked | machsuite | 失败 | 可编译 | 12.4s |
| gemm_ncubed | machsuite | 通过 | 可运行 | 11.9s |
| gemver | hls_polybench__fixed__small | 失败 | 可运行 | 27.2s |
| gesummv | hls_polybench__fixed__small | 通过 | 可运行 | 24.1s |
| global_add_pool | gnnbuilder | 通过 | 可运行 | 12.3s |
| gramschmidt | hls_polybench__fixed__small | 失败 | 可编译 | 31.6s |
| heat-3d | hls_polybench__fixed__small | 通过 | 可运行 | 27.1s |
| jacobi-1d | hls_polybench__fixed__small | 通过 | 可运行 | 25.8s |
| jacobi-2d | hls_polybench__fixed__small | 通过 | 可运行 | 27.9s |
| kmp_kmp | machsuite | 通过 | 可运行 | 12.0s |
| lu | hls_polybench__fixed__small | 失败 | 可运行 | 25.9s |
| ludcmp | hls_polybench__fixed__small | 通过 | 可运行 | 27.9s |
| md_grid | machsuite | 失败 | 可编译 | 16.3s |
| md_knn | machsuite | 失败 | 可编译 | 16.4s |
| mix_columns | c2hlsc | 通过 | 可运行 | 11.8s |
| monobit | c2hlsc | 通过 | 可运行 | 11.0s |
| mvt | hls_polybench__fixed__small | 通过 | 可运行 | 23.9s |
| nussinov | hls_polybench__fixed__small | 失败 | 可运行 | 24.8s |
| nw_nw | machsuite | 失败 | 可编译 | 16.7s |
| optical_flow__outer_product | rosetta | 通过 | 可运行 | 15.4s |
| overlapping | c2hlsc | 通过 | 可运行 | 16.6s |
| parallel_merge_sort | pp4fpga | 失败 | 可编译 | 12.6s |
| polybench__2mm | polybench | 通过 | 可运行 | 11.6s |
| polybench__3mm | polybench | 通过 | 可运行 | 12.5s |
| polybench__atax | polybench | 通过 | 可运行 | 11.1s |
| polybench__bicg | polybench | 通过 | 可运行 | 13.2s |
| polybench__cholesky | polybench | 失败 | 可编译 | 11.6s |
| polybench__correlation | polybench | 失败 | 可编译 | 15.6s |
| polybench__covariance | polybench | 通过 | 可运行 | 11.8s |
| polybench__doitgen | polybench | 通过 | 可运行 | 12.6s |
| polybench__durbin | polybench | 失败 | 可运行 | 11.8s |
| polybench__fdtd-2d | polybench | 失败 | 可运行 | 14.0s |
| polybench__floyd-warshall | polybench | 通过 | 可运行 | 11.9s |
| polybench__gemm | polybench | 通过 | 可运行 | 11.8s |
| polybench__gemver | polybench | 通过 | 可运行 | 11.8s |
| polybench__gesummv | polybench | 通过 | 可运行 | 11.7s |
| polybench__gramschmidt | polybench | 失败 | 可编译 | 12.9s |
| polybench__heat-3d | polybench | 通过 | 可运行 | 14.5s |
| polybench__jacobi-1d | polybench | 失败 | 可运行 | 13.5s |
| polybench__jacobi-2d | polybench | 通过 | 可运行 | 14.5s |
| polybench__lu | polybench | 通过 | 可运行 | 13.0s |
| polybench__ludcmp | polybench | 通过 | 可运行 | 12.2s |
| polybench__mvt | polybench | 通过 | 可运行 | 14.1s |
| polybench__nussinov | polybench | 失败 | 可运行 | 13.6s |
| polybench__seidel-2d | polybench | 通过 | 可运行 | 12.7s |
| polybench__symm | polybench | 失败 | 可运行 | 12.6s |
| polybench__syr2k | polybench | 通过 | 可运行 | 12.0s |
| polybench__syrk | polybench | 通过 | 可运行 | 12.0s |
| polybench__trisolv | polybench | 通过 | 可运行 | 11.1s |
| polybench__trmm | polybench | 失败 | 可运行 | 13.1s |
| pp4fpga_cordic | pp4fpga | 失败 | 可编译 | 15.8s |
| present | c2hlsc | 通过 | 可运行 | 24.1s |
| rendering_3d__check_clockwise | rosetta | 通过 | 可运行 | 13.1s |
| rendering_3d__clockwise_vertices | rosetta | 通过 | 可运行 | 12.7s |
| rendering_3d__pixel_in_triangle | rosetta | 通过 | 可运行 | 15.3s |
| rendering_3d__projection | rosetta | 失败 | 可编译 | 15.3s |
| runs | c2hlsc | 通过 | 可运行 | 12.1s |
| seidel-2d | hls_polybench__fixed__small | 通过 | 可运行 | 26.3s |
| shift_rows | c2hlsc | 通过 | 可运行 | 11.3s |
| sort_merge | machsuite | 通过 | 可运行 | 14.1s |
| sort_radix | machsuite | 失败 | 可编译 | 18.7s |
| spam_filter__computeGradient | rosetta | 通过 | 可运行 | 14.5s |
| spam_filter__dotProduct | rosetta | 通过 | 可运行 | 14.4s |
| spmv_crs | machsuite | 通过 | 可运行 | 11.3s |
| spmv_ellpack | machsuite | 通过 | 可运行 | 11.5s |
| stencil_stencil2d | machsuite | 通过 | 可运行 | 13.0s |
| stencil_stencil3d | machsuite | 通过 | 可运行 | 12.6s |
| sub_bytes | c2hlsc | 通过 | 可运行 | 10.7s |
| symm | hls_polybench__fixed__small | 失败 | 可运行 | 25.3s |
| syr2k | hls_polybench__fixed__small | 通过 | 可运行 | 26.3s |
| syrk | hls_polybench__fixed__small | 通过 | 可运行 | 23.6s |
| trisolv | hls_polybench__fixed__small | 通过 | 可运行 | 22.4s |
| trmm | hls_polybench__fixed__small | 失败 | 可运行 | 22.2s |
| viterbi_viterbi | machsuite | 通过 | 可运行 | 14.6s |

## 失败分析

| 题目 | 轮次 | 卡在哪一级 | 原因摘要 |
| --- | --- | --- | --- |
| df_countLeadingZeros64 | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| df_float64_ge | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| df_float64_le | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| df_mul64To128 | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| df_propagateFloat64NaN | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| dfadd | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| dfdiv | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| dfmul | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| dfsin | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| correlation | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| covariance | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| durbin | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| fdtd-2d | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| gemver | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| gramschmidt | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| lu | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| nussinov | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| symm | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| trmm | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| aes_aes | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| fft_strided | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| gemm_blocked | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| md_grid | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| md_knn | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| nw_nw | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| sort_radix | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| polybench__cholesky | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| polybench__correlation | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| polybench__durbin | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| polybench__fdtd-2d | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| polybench__gramschmidt | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| polybench__jacobi-1d | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| polybench__nussinov | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| polybench__symm | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| polybench__trmm | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| block_mm | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| parallel_merge_sort | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| pp4fpga_cordic | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| rendering_3d__projection | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
