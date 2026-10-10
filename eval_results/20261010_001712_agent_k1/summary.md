# HLS Agent 评测结果

- 时间：2026-10-09 23:31:14
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
| pass@1 | **63.1%** |
| 总墙钟 | 2758.6 s |
| 单次平均墙钟 | 22.6 s |
| 单次最长墙钟 | 95.7 s |

## 分级判定分布

| 最高级别 | 题目数 |
| --- | --- |
| 可运行 | 93 |
| 可编译 | 28 |
| 可解析 | 1 |

## 分组通过率

| 变体 | 题目数 | pass@1 |
| --- | --- | --- |
| c2hlsc | 12 | 12/12 (100.0%) |
| chstone | 20 | 13/20 (65.0%) |
| flowgnn | 3 | 3/3 (100.0%) |
| gnnbuilder | 3 | 3/3 (100.0%) |
| hls_polybench__fixed__small | 28 | 19/28 (67.9%) |
| machsuite | 17 | 0/17 (0.0%) |
| polybench | 28 | 18/28 (64.3%) |
| pp4fpga | 3 | 2/3 (66.7%) |
| rosetta | 8 | 7/8 (87.5%) |

## 逐题明细

| 题目 | 变体 | 第1轮 | 最好级别 | 平均墙钟 |
| --- | --- | --- | --- | --- |
| 2mm | hls_polybench__fixed__small | 通过 | 可运行 | 24.4s |
| 3mm | hls_polybench__fixed__small | 通过 | 可运行 | 23.8s |
| add_round_key | c2hlsc | 通过 | 可运行 | 17.6s |
| aes | c2hlsc | 通过 | 可运行 | 37.9s |
| aes_aes | machsuite | 失败 | 可编译 | 44.7s |
| atax | hls_polybench__fixed__small | 通过 | 可运行 | 19.9s |
| bfs_bulk | machsuite | 失败 | 可编译 | 23.6s |
| bfs_queue | machsuite | 失败 | 可编译 | 38.0s |
| bicg | hls_polybench__fixed__small | 通过 | 可运行 | 21.5s |
| block | c2hlsc | 通过 | 可运行 | 10.8s |
| block_mm | pp4fpga | 通过 | 可运行 | 13.5s |
| cholesky | hls_polybench__fixed__small | 通过 | 可运行 | 25.4s |
| compute_neighbor_tables | gnnbuilder | 通过 | 可运行 | 13.8s |
| correlation | hls_polybench__fixed__small | 通过 | 可运行 | 26.3s |
| covariance | hls_polybench__fixed__small | 通过 | 可运行 | 22.8s |
| cusums | c2hlsc | 通过 | 可运行 | 11.4s |
| des | c2hlsc | 通过 | 可运行 | 29.3s |
| df_add128 | chstone | 通过 | 可运行 | 11.5s |
| df_countLeadingZeros32 | chstone | 通过 | 可运行 | 16.7s |
| df_countLeadingZeros64 | chstone | 失败 | 可编译 | 31.8s |
| df_extractFloat64Exp | chstone | 通过 | 可运行 | 11.3s |
| df_extractFloat64Frac | chstone | 通过 | 可运行 | 11.0s |
| df_extractFloat64Sign | chstone | 通过 | 可运行 | 10.4s |
| df_float64_abs | chstone | 通过 | 可运行 | 10.7s |
| df_float64_ge | chstone | 失败 | 可编译 | 25.9s |
| df_float64_is_nan | chstone | 通过 | 可运行 | 12.1s |
| df_float64_is_signaling_nan | chstone | 通过 | 可运行 | 11.0s |
| df_float64_le | chstone | 通过 | 可运行 | 13.6s |
| df_float64_neg | chstone | 通过 | 可运行 | 10.2s |
| df_mul64To128 | chstone | 失败 | 可编译 | 23.5s |
| df_packFloat64 | chstone | 通过 | 可运行 | 12.3s |
| df_propagateFloat64NaN | chstone | 通过 | 可运行 | 14.2s |
| df_shift64RightJamming | chstone | 通过 | 可运行 | 12.7s |
| dfadd | chstone | 失败 | 可编译 | 48.7s |
| dfdiv | chstone | 失败 | 可编译 | 95.7s |
| dfmul | chstone | 失败 | 可编译 | 51.7s |
| dfsin | chstone | 失败 | 可编译 | 28.4s |
| digit_recognition__popcount | rosetta | 通过 | 可运行 | 12.2s |
| doitgen | hls_polybench__fixed__small | 通过 | 可运行 | 23.5s |
| durbin | hls_polybench__fixed__small | 失败 | 可运行 | 40.6s |
| fdtd-2d | hls_polybench__fixed__small | 失败 | 可运行 | 46.1s |
| fft_strided | machsuite | 失败 | 可编译 | 19.0s |
| fgnn_linear | flowgnn | 通过 | 可运行 | 13.6s |
| fgnn_linear_input_stationary | flowgnn | 通过 | 可运行 | 15.4s |
| fgnn_linear_output_stationary | flowgnn | 通过 | 可运行 | 12.8s |
| floyd-warshall | hls_polybench__fixed__small | 通过 | 可运行 | 19.7s |
| gather_node_neighbors | gnnbuilder | 通过 | 可运行 | 11.9s |
| gemm | hls_polybench__fixed__small | 通过 | 可运行 | 21.8s |
| gemm_blocked | machsuite | 失败 | 可编译 | 19.9s |
| gemm_ncubed | machsuite | 失败 | 可编译 | 18.1s |
| gemver | hls_polybench__fixed__small | 失败 | 可运行 | 42.8s |
| gesummv | hls_polybench__fixed__small | 通过 | 可运行 | 21.2s |
| global_add_pool | gnnbuilder | 通过 | 可运行 | 10.9s |
| gramschmidt | hls_polybench__fixed__small | 失败 | 可运行 | 48.8s |
| heat-3d | hls_polybench__fixed__small | 通过 | 可运行 | 25.2s |
| jacobi-1d | hls_polybench__fixed__small | 失败 | 可运行 | 40.2s |
| jacobi-2d | hls_polybench__fixed__small | 失败 | 可运行 | 44.4s |
| kmp_kmp | machsuite | 失败 | 可编译 | 67.1s |
| lu | hls_polybench__fixed__small | 失败 | 可运行 | 41.2s |
| ludcmp | hls_polybench__fixed__small | 通过 | 可运行 | 23.3s |
| md_grid | machsuite | 失败 | 可解析 | 32.9s |
| md_knn | machsuite | 失败 | 可编译 | 57.3s |
| mix_columns | c2hlsc | 通过 | 可运行 | 12.3s |
| monobit | c2hlsc | 通过 | 可运行 | 11.2s |
| mvt | hls_polybench__fixed__small | 通过 | 可运行 | 21.3s |
| nussinov | hls_polybench__fixed__small | 失败 | 可运行 | 37.5s |
| nw_nw | machsuite | 失败 | 可编译 | 53.7s |
| optical_flow__outer_product | rosetta | 通过 | 可运行 | 17.0s |
| overlapping | c2hlsc | 通过 | 可运行 | 19.1s |
| parallel_merge_sort | pp4fpga | 通过 | 可运行 | 14.9s |
| polybench__2mm | polybench | 通过 | 可运行 | 12.3s |
| polybench__3mm | polybench | 通过 | 可运行 | 12.6s |
| polybench__atax | polybench | 通过 | 可运行 | 11.4s |
| polybench__bicg | polybench | 通过 | 可运行 | 11.7s |
| polybench__cholesky | polybench | 失败 | 可编译 | 11.3s |
| polybench__correlation | polybench | 失败 | 可编译 | 13.0s |
| polybench__covariance | polybench | 通过 | 可运行 | 11.3s |
| polybench__doitgen | polybench | 通过 | 可运行 | 13.7s |
| polybench__durbin | polybench | 通过 | 可运行 | 11.8s |
| polybench__fdtd-2d | polybench | 失败 | 可运行 | 27.7s |
| polybench__floyd-warshall | polybench | 通过 | 可运行 | 11.7s |
| polybench__gemm | polybench | 通过 | 可运行 | 12.1s |
| polybench__gemver | polybench | 通过 | 可运行 | 12.5s |
| polybench__gesummv | polybench | 通过 | 可运行 | 13.7s |
| polybench__gramschmidt | polybench | 失败 | 可编译 | 14.1s |
| polybench__heat-3d | polybench | 通过 | 可运行 | 17.9s |
| polybench__jacobi-1d | polybench | 失败 | 可运行 | 21.7s |
| polybench__jacobi-2d | polybench | 失败 | 可运行 | 22.6s |
| polybench__lu | polybench | 失败 | 可运行 | 22.5s |
| polybench__ludcmp | polybench | 通过 | 可运行 | 12.3s |
| polybench__mvt | polybench | 通过 | 可运行 | 11.6s |
| polybench__nussinov | polybench | 失败 | 可运行 | 23.1s |
| polybench__seidel-2d | polybench | 通过 | 可运行 | 12.8s |
| polybench__symm | polybench | 失败 | 可运行 | 20.0s |
| polybench__syr2k | polybench | 通过 | 可运行 | 13.3s |
| polybench__syrk | polybench | 通过 | 可运行 | 12.3s |
| polybench__trisolv | polybench | 通过 | 可运行 | 10.9s |
| polybench__trmm | polybench | 失败 | 可运行 | 20.9s |
| pp4fpga_cordic | pp4fpga | 失败 | 可编译 | 16.8s |
| present | c2hlsc | 通过 | 可运行 | 26.6s |
| rendering_3d__check_clockwise | rosetta | 通过 | 可运行 | 14.0s |
| rendering_3d__clockwise_vertices | rosetta | 通过 | 可运行 | 13.2s |
| rendering_3d__pixel_in_triangle | rosetta | 通过 | 可运行 | 14.6s |
| rendering_3d__projection | rosetta | 失败 | 可编译 | 28.0s |
| runs | c2hlsc | 通过 | 可运行 | 12.1s |
| seidel-2d | hls_polybench__fixed__small | 通过 | 可运行 | 25.8s |
| shift_rows | c2hlsc | 通过 | 可运行 | 12.3s |
| sort_merge | machsuite | 失败 | 可编译 | 28.2s |
| sort_radix | machsuite | 失败 | 可编译 | 75.6s |
| spam_filter__computeGradient | rosetta | 通过 | 可运行 | 14.6s |
| spam_filter__dotProduct | rosetta | 通过 | 可运行 | 14.0s |
| spmv_crs | machsuite | 失败 | 可编译 | 20.7s |
| spmv_ellpack | machsuite | 失败 | 可编译 | 19.3s |
| stencil_stencil2d | machsuite | 失败 | 可编译 | 20.6s |
| stencil_stencil3d | machsuite | 失败 | 可编译 | 24.7s |
| sub_bytes | c2hlsc | 通过 | 可运行 | 10.5s |
| symm | hls_polybench__fixed__small | 通过 | 可运行 | 23.8s |
| syr2k | hls_polybench__fixed__small | 通过 | 可运行 | 23.7s |
| syrk | hls_polybench__fixed__small | 通过 | 可运行 | 22.2s |
| trisolv | hls_polybench__fixed__small | 通过 | 可运行 | 19.8s |
| trmm | hls_polybench__fixed__small | 失败 | 可运行 | 38.0s |
| viterbi_viterbi | machsuite | 失败 | 可编译 | 31.6s |

## 失败分析

| 题目 | 轮次 | 卡在哪一级 | 原因摘要 |
| --- | --- | --- | --- |
| df_countLeadingZeros64 | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| df_float64_ge | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
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
| jacobi-2d | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| lu | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| nussinov | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| trmm | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| aes_aes | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| bfs_bulk | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| bfs_queue | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| fft_strided | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| gemm_blocked | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| gemm_ncubed | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| kmp_kmp | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| md_grid | 1 | 可解析 | 编译/仿真未通过，详见 results.json |
| md_knn | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| nw_nw | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| sort_merge | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| sort_radix | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| spmv_crs | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| spmv_ellpack | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| stencil_stencil2d | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| stencil_stencil3d | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| viterbi_viterbi | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| polybench__cholesky | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| polybench__correlation | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
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
