## 失败分析

- 失败总数：45 / 122
- 按阶段：仿真失败 28，数值不符 16，编译失败 1

| 变体 | 失败数 |
| --- | --- |
| machsuite | 17 |
| polybench | 10 |
| hls_polybench__fixed__small | 9 |
| chstone | 7 |
| pp4fpga | 1 |
| rosetta | 1 |

| 题目 | 变体 | 失败阶段 | 尝试 | 墙钟 | 错误归类 | 错误摘要 |
| --- | --- | --- | --- | --- | --- | --- |
| df_countLeadingZeros64 | chstone | 仿真失败 | 2 | 32s | - | - |
| df_float64_ge | chstone | 仿真失败 | 2 | 26s | - | - |
| df_mul64To128 | chstone | 仿真失败 | 2 | 23s | - | - |
| dfadd | chstone | 仿真失败 | 2 | 49s | - | - |
| dfdiv | chstone | 仿真失败 | 2 | 96s | 重定义/冲突、其他 | redefinition of 'rem0' |
| dfmul | chstone | 仿真失败 | 2 | 52s | - | - |
| dfsin | chstone | 仿真失败 | 2 | 28s | - | - |
| durbin | hls_polybench__fixed__small | 数值不符 | 2 | 41s | - | 数值与参考输出不符（相对容差 0.001）。逐数组对比：
- y: 最大误差在索引 0，实际 -121 vs 参考 0. |
| fdtd-2d | hls_polybench__fixed__small | 数值不符 | 2 | 46s | - | 数值与参考输出不符（相对容差 0.001）。逐数组对比：
- ex: 最大误差在索引 4643，实际 -32707.5  |
| gemver | hls_polybench__fixed__small | 数值不符 | 2 | 43s | - | 数值与参考输出不符（相对容差 0.001）。逐数组对比：
- w: 最大误差在索引 119，实际 17047.8 vs  |
| gramschmidt | hls_polybench__fixed__small | 数值不符 | 2 | 49s | - | 数值与参考输出不符（相对容差 0.001）。逐数组对比：
- R: 最大误差在索引 3005，实际 -0.146362  |
| jacobi-1d | hls_polybench__fixed__small | 数值不符 | 2 | 40s | - | 数值与参考输出不符（相对容差 0.001）。逐数组对比：
- A: 最大误差在索引 119，实际 0.97789 vs  |
| jacobi-2d | hls_polybench__fixed__small | 数值不符 | 2 | 44s | - | 数值与参考输出不符（相对容差 0.001）。逐数组对比：
- A: 最大误差在索引 8099，实际 3.13306 vs |
| lu | hls_polybench__fixed__small | 数值不符 | 2 | 41s | - | 数值与参考输出不符（相对容差 0.001）。逐数组对比：
- A: 最大误差在索引 6413，实际 -32738.3 v |
| nussinov | hls_polybench__fixed__small | 数值不符 | 2 | 38s | - | 数值与参考输出不符（相对容差 0.001）。逐数组对比：
- table: 最大误差在索引 177，实际 0 vs 参考 |
| trmm | hls_polybench__fixed__small | 数值不符 | 2 | 38s | - | 数值与参考输出不符（相对容差 0.001）。逐数组对比：
- B: 最大误差在索引 4122，实际 -32754.6 v |
| aes_aes | machsuite | 仿真失败 | 2 | 45s | - | - |
| bfs_bulk | machsuite | 仿真失败 | 2 | 24s | - | - |
| bfs_queue | machsuite | 仿真失败 | 2 | 38s | - | - |
| fft_strided | machsuite | 仿真失败 | 2 | 19s | - | - |
| gemm_blocked | machsuite | 仿真失败 | 2 | 20s | - | - |
| gemm_ncubed | machsuite | 仿真失败 | 2 | 18s | - | - |
| kmp_kmp | machsuite | 仿真失败 | 2 | 67s | - | - |
| md_grid | machsuite | 编译失败 | 2 | 33s | 漏 include / 未声明、其他 | use of undeclared identifier 'sqrt' |
| md_knn | machsuite | 仿真失败 | 2 | 57s | 漏 include / 未声明、其他 | use of undeclared identifier 'sqrt' |
| nw_nw | machsuite | 仿真失败 | 2 | 54s | - | - |
| sort_merge | machsuite | 仿真失败 | 2 | 28s | - | - |
| sort_radix | machsuite | 仿真失败 | 2 | 76s | - | - |
| spmv_crs | machsuite | 仿真失败 | 2 | 21s | - | - |
| spmv_ellpack | machsuite | 仿真失败 | 2 | 19s | - | - |
| stencil_stencil2d | machsuite | 仿真失败 | 2 | 21s | - | - |
| stencil_stencil3d | machsuite | 仿真失败 | 2 | 25s | - | - |
| viterbi_viterbi | machsuite | 仿真失败 | 2 | 32s | - | - |
| polybench__cholesky | polybench | 仿真失败 | 1 | 11s | - | - |
| polybench__correlation | polybench | 仿真失败 | 1 | 13s | - | - |
| polybench__fdtd-2d | polybench | 数值不符 | 2 | 28s | - | 数值与参考输出不符（相对容差 0）。逐数组对比：
- ex: 最大误差在索引 524，实际 7.61037e+06 vs |
| polybench__gramschmidt | polybench | 仿真失败 | 1 | 14s | - | - |
| polybench__jacobi-1d | polybench | 数值不符 | 2 | 22s | - | 数值与参考输出不符（相对容差 0）。逐数组对比：
- A: 最大误差在索引 1，实际 0.1 vs 参考 0.11855 |
| polybench__jacobi-2d | polybench | 数值不符 | 2 | 23s | - | 数值与参考输出不符（相对容差 0）。逐数组对比：
- A: 最大误差在索引 841，实际 2.86667 vs 参考 3 |
| polybench__lu | polybench | 数值不符 | 2 | 23s | - | 数值与参考输出不符（相对容差 0）。逐数组对比：
- A: 最大误差在索引 1599，实际 14.8369 vs 参考  |
| polybench__nussinov | polybench | 数值不符 | 2 | 23s | - | 数值与参考输出不符（相对容差 0）。逐数组对比：
- table: 最大误差在索引 57，实际 0 vs 参考 28
  |
| polybench__symm | polybench | 数值不符 | 2 | 20s | - | 数值与参考输出不符（相对容差 0）。逐数组对比：
- C: 最大误差在索引 210，实际 11.13 vs 参考 51. |
| polybench__trmm | polybench | 数值不符 | 2 | 21s | - | 数值与参考输出不符（相对容差 0）。逐数组对比：
- B: 最大误差在索引 20，实际 0.5 vs 参考 11.425 |
| pp4fpga_cordic | pp4fpga | 仿真失败 | 1 | 17s | - | - |
| rendering_3d__projection | rosetta | 仿真失败 | 2 | 28s | - | - |

### 编译错误模式分布

- 其他：3
- 重定义/冲突：2
- 漏 include / 未声明：2

### 技能包提炼建议

- 「漏 include / 未声明」高发：检查静态预检是否覆盖了对应的 include 模式；
  考虑在提示词里补充「头文件必须 #include」的强调。

