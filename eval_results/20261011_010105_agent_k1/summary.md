# HLS Agent 评测结果

- 时间：2026-10-11 00:39:20
- 模式：**agent**（带工具反馈，失败重试至多 2 次）
- 采样轮数 k：1
- 是否评估综合：否
- 判定口径：严格（数值与参考 dump 一致才算通过）
- 模型：`claude-fable-5`（backend=auto）
- 器件：`xczu3eg-sbva484-1-e`，时钟 5 ns
- 题目数：56

## 核心指标

| 指标 | 数值 |
| --- | --- |
| pass@1 | **75.0%** |
| 总墙钟 | 1304.7 s |
| 单次平均墙钟 | 23.3 s |
| 单次最长墙钟 | 78.2 s |

## 分级判定分布

| 最高级别 | 题目数 |
| --- | --- |
| 可运行 | 53 |
| 可编译 | 3 |

## 分组通过率

| 变体 | 题目数 | pass@1 |
| --- | --- | --- |
| hls_polybench__fixed__small | 28 | 21/28 (75.0%) |
| polybench | 28 | 21/28 (75.0%) |

## 逐题明细

| 题目 | 变体 | 第1轮 | 最好级别 | 平均墙钟 |
| --- | --- | --- | --- | --- |
| 2mm | hls_polybench__fixed__small | 通过 | 可运行 | 22.7s |
| 3mm | hls_polybench__fixed__small | 通过 | 可运行 | 23.6s |
| atax | hls_polybench__fixed__small | 通过 | 可运行 | 24.6s |
| bicg | hls_polybench__fixed__small | 通过 | 可运行 | 23.5s |
| cholesky | hls_polybench__fixed__small | 通过 | 可运行 | 31.7s |
| correlation | hls_polybench__fixed__small | 通过 | 可运行 | 29.8s |
| covariance | hls_polybench__fixed__small | 通过 | 可运行 | 26.6s |
| doitgen | hls_polybench__fixed__small | 通过 | 可运行 | 25.9s |
| durbin | hls_polybench__fixed__small | 通过 | 可运行 | 28.6s |
| fdtd-2d | hls_polybench__fixed__small | 失败 | 可运行 | 52.8s |
| floyd-warshall | hls_polybench__fixed__small | 通过 | 可运行 | 20.9s |
| gemm | hls_polybench__fixed__small | 通过 | 可运行 | 25.4s |
| gemver | hls_polybench__fixed__small | 失败 | 可运行 | 53.7s |
| gesummv | hls_polybench__fixed__small | 通过 | 可运行 | 25.1s |
| gramschmidt | hls_polybench__fixed__small | 失败 | 可运行 | 59.8s |
| heat-3d | hls_polybench__fixed__small | 通过 | 可运行 | 30.2s |
| jacobi-1d | hls_polybench__fixed__small | 失败 | 可运行 | 43.5s |
| jacobi-2d | hls_polybench__fixed__small | 通过 | 可运行 | 26.0s |
| lu | hls_polybench__fixed__small | 失败 | 可运行 | 49.1s |
| ludcmp | hls_polybench__fixed__small | 通过 | 可运行 | 29.0s |
| mvt | hls_polybench__fixed__small | 通过 | 可运行 | 24.7s |
| nussinov | hls_polybench__fixed__small | 失败 | 可运行 | 43.6s |
| polybench__2mm | polybench | 通过 | 可运行 | 11.2s |
| polybench__3mm | polybench | 通过 | 可运行 | 12.3s |
| polybench__atax | polybench | 通过 | 可运行 | 11.3s |
| polybench__bicg | polybench | 通过 | 可运行 | 10.8s |
| polybench__cholesky | polybench | 失败 | 可编译 | 11.0s |
| polybench__correlation | polybench | 失败 | 可编译 | 11.9s |
| polybench__covariance | polybench | 通过 | 可运行 | 11.5s |
| polybench__doitgen | polybench | 通过 | 可运行 | 12.7s |
| polybench__durbin | polybench | 通过 | 可运行 | 11.6s |
| polybench__fdtd-2d | polybench | 失败 | 可运行 | 22.1s |
| polybench__floyd-warshall | polybench | 通过 | 可运行 | 10.7s |
| polybench__gemm | polybench | 通过 | 可运行 | 11.0s |
| polybench__gemver | polybench | 通过 | 可运行 | 11.6s |
| polybench__gesummv | polybench | 通过 | 可运行 | 11.1s |
| polybench__gramschmidt | polybench | 失败 | 可编译 | 11.7s |
| polybench__heat-3d | polybench | 通过 | 可运行 | 14.0s |
| polybench__jacobi-1d | polybench | 失败 | 可运行 | 20.7s |
| polybench__jacobi-2d | polybench | 通过 | 可运行 | 11.6s |
| polybench__lu | polybench | 通过 | 可运行 | 11.7s |
| polybench__ludcmp | polybench | 通过 | 可运行 | 12.0s |
| polybench__mvt | polybench | 通过 | 可运行 | 11.2s |
| polybench__nussinov | polybench | 通过 | 可运行 | 78.2s |
| polybench__seidel-2d | polybench | 通过 | 可运行 | 11.9s |
| polybench__symm | polybench | 失败 | 可运行 | 19.1s |
| polybench__syr2k | polybench | 通过 | 可运行 | 11.9s |
| polybench__syrk | polybench | 通过 | 可运行 | 11.1s |
| polybench__trisolv | polybench | 通过 | 可运行 | 10.4s |
| polybench__trmm | polybench | 失败 | 可运行 | 20.0s |
| seidel-2d | hls_polybench__fixed__small | 通过 | 可运行 | 27.7s |
| symm | hls_polybench__fixed__small | 通过 | 可运行 | 26.9s |
| syr2k | hls_polybench__fixed__small | 通过 | 可运行 | 26.3s |
| syrk | hls_polybench__fixed__small | 通过 | 可运行 | 20.9s |
| trisolv | hls_polybench__fixed__small | 通过 | 可运行 | 19.1s |
| trmm | hls_polybench__fixed__small | 失败 | 可运行 | 36.9s |

## 失败分析

| 题目 | 轮次 | 卡在哪一级 | 原因摘要 |
| --- | --- | --- | --- |
| fdtd-2d | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| gemver | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| gramschmidt | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| jacobi-1d | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| lu | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| nussinov | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| trmm | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| polybench__cholesky | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| polybench__correlation | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| polybench__fdtd-2d | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| polybench__gramschmidt | 1 | 可编译 | 编译/仿真未通过，详见 results.json |
| polybench__jacobi-1d | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| polybench__symm | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
| polybench__trmm | 1 | 可运行 | 编译/仿真未通过，详见 results.json |
