# HLS Agent 评测结果

- 时间：2026-10-10 23:42:48
- 模式：**agent**（带工具反馈，失败重试至多 2 次）
- 采样轮数 k：1
- 是否评估综合：否
- 判定口径：严格（数值与参考 dump 一致才算通过）
- 模型：`claude-fable-5`（backend=auto）
- 器件：`xczu3eg-sbva484-1-e`，时钟 5 ns
- 题目数：122

## 核心指标

| 指标 | 数值 |
| --- | --- |
| pass@1 | **72.1%** |
| 总墙钟 | 3270.2 s |
| 单次平均墙钟 | 26.8 s |
| 单次最长墙钟 | 516.0 s |

## 分级判定分布

| 最高级别 | 题目数 |
| --- | --- |
| 可运行 | 106 |
| 可编译 | 16 |

## 分组通过率

| 变体 | 题目数 | pass@1 |
| --- | --- | --- |
| c2hlsc | 12 | 12/12 (100.0%) |
| chstone | 20 | 15/20 (75.0%) |
| flowgnn | 3 | 3/3 (100.0%) |
| gnnbuilder | 3 | 3/3 (100.0%) |
| hls_polybench__fixed__small | 28 | 18/28 (64.3%) |
| machsuite | 17 | 11/17 (64.7%) |
| polybench | 28 | 17/28 (60.7%) |
| pp4fpga | 3 | 2/3 (66.7%) |
| rosetta | 8 | 7/8 (87.5%) |

## 逐题明细

| 题目 | 变体 | 第1轮 | 最好级别 | 平均墙钟 |
| --- | --- | --- | --- | --- |
| 2mm | hls_polybench__fixed__small | 通过 | 可运行 | 25.8s |
| 3mm | hls_polybench__fixed__small | 通过 | 可运行 | 25.4s |
| add_round_key | c2hlsc | 通过 | 可运行 | 11.7s |
| aes | c2hlsc | 通过 | 可运行 | 19.4s |
| aes_aes | machsuite | 失败 | 可编译 | 516.0s |
| atax | hls_polybench__fixed__small | 通过 | 可运行 | 21.9s |
| bfs_bulk | machsuite | 通过 | 可运行 | 12.9s |
| bfs_queue | machsuite | 通过 | 可运行 | 15.4s |
| bicg | hls_polybench__fixed__small | 通过 | 可运行 | 20.9s |
| block | c2hlsc | 通过 | 可运行 | 10.5s |
| block_mm | pp4fpga | 通过 | 可运行 | 14.2s |
| cholesky | hls_polybench__fixed__small | 通过 | 可运行 | 28.0s |
| compute_neighbor_tables | gnnbuilder | 通过 | 可运行 | 14.2s |
| correlation | hls_polybench__fixed__small | 通过 | 可运行 | 27.2s |
| covariance | hls_polybench__fixed__small | 通过 | 可运行 | 23.0s |
| cusums | c2hlsc | 通过 | 可运行 | 11.4s |
| des | c2hlsc | 通过 | 可运行 | 27.6s |
| df_add128 | chstone | 通过 | 可运行 | 10.7s |
| df_countLeadingZeros32 | chstone | 通过 | 可运行 | 16.9s |
| df_countLeadingZeros64 | chstone | 通过 | 可运行 | 16.9s |
| df_extractFloat64Exp | chstone | 通过 | 可运行 | 10.4s |
| df_extractFloat64Frac | chstone | 通过 | 可运行 | 10.7s |
| df_extractFloat64Sign | chstone | 通过 | 可运行 | 10.9s |
| df_float64_abs | chstone | 通过 | 可运行 | 10.6s |
| df_float64_ge | chstone | 通过 | 可运行 | 15.6s |
| df_float64_is_nan | chstone | 通过 | 可运行 | 11.1s |
| df_float64_is_signaling_nan | chstone | 通过 | 可运行 | 11.6s |
| df_float64_le | chstone | 通过 | 可运行 | 13.4s |
| df_float64_neg | chstone | 通过 | 可运行 | 10.1s |
| df_mul64To128 | chstone | 失败 | 可编译 | 20.9s |
| df_packFloat64 | chstone | 通过 | 可运行 | 13.2s |
| df_propagateFloat64NaN | chstone | 通过 | 可运行 | 14.4s |
| df_shift64RightJamming | chstone | 通过 | 可运行 | 11.0s |
| dfadd | chstone | 失败 | 可编译 | 52.3s |
| dfdiv | chstone | 失败 | 可编译 | 58.6s |
| dfmul | chstone | 失败 | 可编译 | 37.7s |
| dfsin | chstone | 失败 | 可编译 | 53.2s |
| digit_recognition__popcount | rosetta | 通过 | 可运行 | 12.7s |
| doitgen | hls_polybench__fixed__small | 通过 | 可运行 | 23.5s |
| durbin | hls_polybench__fixed__small | 失败 | 可运行 | 69.6s |
| fdtd-2d | hls_polybench__fixed__small | 失败 | 可运行 | 43.5s |
| fft_strided | machsuite | 失败 | 可编译 | 21.5s |
| fgnn_linear | flowgnn | 通过 | 可运行 | 15.0s |
| fgnn_linear_input_stationary | flowgnn | 通过 | 可运行 | 16.9s |
| fgnn_linear_output_stationary | flowgnn | 通过 | 可运行 | 15.6s |
| floyd-warshall | hls_polybench__fixed__small | 通过 | 可运行 | 18.8s |
| gather_node_neighbors | gnnbuilder | 通过 | 可运行 | 12.2s |
| gemm | hls_polybench__fixed__small | 通过 | 可运行 | 21.0s |
| gemm_blocked | machsuite | 通过 | 可运行 | 13.1s |
| gemm_ncubed | machsuite | 通过 | 可运行 | 11.5s |
| gemver | hls_polybench__fixed__small | 失败 | 可运行 | 122.0s |
| gesummv | hls_polybench__fixed__small | 通过 | 可运行 | 23.1s |
| global_add_pool | gnnbuilder | 通过 | 可运行 | 12.2s |
| gramschmidt | hls_polybench__fixed__small | 失败 | 可运行 | 53.4s |
| heat-3d | hls_polybench__fixed__small | 通过 | 可运行 | 34.0s |
| jacobi-1d | hls_polybench__fixed__small | 失败 | 可运行 | 50.4s |
| jacobi-2d | hls_polybench__fixed__small | 通过 | 可运行 | 26.9s |
| kmp_kmp | machsuite | 通过 | 可运行 | 15.6s |
| lu | hls_polybench__fixed__small | 失败 | 可运行 | 52.2s |
| ludcmp | hls_polybench__fixed__small | 通过 | 可运行 | 30.7s |
| md_grid | machsuite | 失败 | 可编译 | 121.1s |
| md_knn | machsuite | 失败 | 可编译 | 26.6s |
| mix_columns | c2hlsc | 通过 | 可运行 | 11.8s |
| monobit | c2hlsc | 通过 | 可运行 | 10.1s |
| mvt | hls_polybench__fixed__small | 通过 | 可运行 | 26.2s |
| nussinov | hls_polybench__fixed__small | 失败 | 可运行 | 46.2s |
| nw_nw | machsuite | 失败 | 可编译 | 26.7s |
| optical_flow__outer_product | rosetta | 通过 | 可运行 | 14.9s |
| overlapping | c2hlsc | 通过 | 可运行 | 13.1s |
| parallel_merge_sort | pp4fpga | 通过 | 可运行 | 13.2s |
| polybench__2mm | polybench | 通过 | 可运行 | 13.0s |
| polybench__3mm | polybench | 通过 | 可运行 | 13.2s |
| polybench__atax | polybench | 通过 | 可运行 | 12.3s |
| polybench__bicg | polybench | 通过 | 可运行 | 12.2s |
| polybench__cholesky | polybench | 失败 | 可编译 | 12.2s |
| polybench__correlation | polybench | 失败 | 可编译 | 13.5s |
| polybench__covariance | polybench | 通过 | 可运行 | 13.0s |
| polybench__doitgen | polybench | 通过 | 可运行 | 16.0s |
| polybench__durbin | polybench | 失败 | 可运行 | 22.6s |
| polybench__fdtd-2d | polybench | 失败 | 可运行 | 28.1s |
| polybench__floyd-warshall | polybench | 通过 | 可运行 | 13.3s |
| polybench__gemm | polybench | 通过 | 可运行 | 12.2s |
| polybench__gemver | polybench | 通过 | 可运行 | 13.6s |
| polybench__gesummv | polybench | 通过 | 可运行 | 12.6s |
| polybench__gramschmidt | polybench | 失败 | 可编译 | 14.9s |
| polybench__heat-3d | polybench | 通过 | 可运行 | 20.4s |
| polybench__jacobi-1d | polybench | 失败 | 可运行 | 22.5s |
| polybench__jacobi-2d | polybench | 失败 | 可运行 | 24.0s |
| polybench__lu | polybench | 失败 | 可运行 | 19.5s |
| polybench__ludcmp | polybench | 通过 | 可运行 | 12.1s |
| polybench__mvt | polybench | 通过 | 可运行 | 10.9s |
| polybench__nussinov | polybench | 失败 | 可运行 | 23.6s |
| polybench__seidel-2d | polybench | 通过 | 可运行 | 35.0s |
| polybench__symm | polybench | 失败 | 可运行 | 19.8s |
| polybench__syr2k | polybench | 通过 | 可运行 | 11.5s |
| polybench__syrk | polybench | 通过 | 可运行 | 12.2s |
| polybench__trisolv | polybench | 通过 | 可运行 | 11.2s |
| polybench__trmm | polybench | 失败 | 可运行 | 19.7s |
| pp4fpga_cordic | pp4fpga | 失败 | 可编译 | 15.9s |
| present | c2hlsc | 通过 | 可运行 | 25.1s |
| rendering_3d__check_clockwise | rosetta | 通过 | 可运行 | 13.6s |
| rendering_3d__clockwise_vertices | rosetta | 通过 | 可运行 | 13.0s |
| rendering_3d__pixel_in_triangle | rosetta | 通过 | 可运行 | 45.5s |
| rendering_3d__projection | rosetta | 失败 | 可编译 | 32.3s |
| runs | c2hlsc | 通过 | 可运行 | 11.4s |
| seidel-2d | hls_polybench__fixed__small | 通过 | 可运行 | 33.6s |
| shift_rows | c2hlsc | 通过 | 可运行 | 11.4s |
| sort_merge | machsuite | 通过 | 可运行 | 13.2s |
| sort_radix | machsuite | 失败 | 可编译 | 29.1s |
| spam_filter__computeGradient | rosetta | 通过 | 可运行 | 15.4s |
| spam_filter__dotProduct | rosetta | 通过 | 可运行 | 15.8s |
| spmv_crs | machsuite | 通过 | 可运行 | 14.7s |
| spmv_ellpack | machsuite | 通过 | 可运行 | 13.2s |
| stencil_stencil2d | machsuite | 通过 | 可运行 | 19.8s |
| stencil_stencil3d | machsuite | 通过 | 可运行 | 17.0s |
| sub_bytes | c2hlsc | 通过 | 可运行 | 10.4s |
| symm | hls_polybench__fixed__small | 失败 | 可运行 | 47.1s |
| syr2k | hls_polybench__fixed__small | 失败 | 可运行 | 47.7s |
| syrk | hls_polybench__fixed__small | 通过 | 可运行 | 22.2s |
| trisolv | hls_polybench__fixed__small | 通过 | 可运行 | 20.6s |
| trmm | hls_polybench__fixed__small | 失败 | 可运行 | 41.0s |
| viterbi_viterbi | machsuite | 通过 | 可运行 | 15.1s |

## 失败分析

| 题目 | 轮次 | 卡在哪一级 | 原因摘要 |
| --- | --- | --- | --- |
| df_mul64To128 | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| dfadd | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| dfdiv | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| dfmul | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| dfsin | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| durbin | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| fdtd-2d | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| gemver | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| gramschmidt | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| jacobi-1d | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| lu | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| nussinov | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| symm | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| syr2k | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| trmm | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| aes_aes | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| fft_strided | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
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
| polybench__jacobi-2d | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| polybench__lu | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| polybench__nussinov | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| polybench__symm | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| polybench__trmm | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| pp4fpga_cordic | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| rendering_3d__projection | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
