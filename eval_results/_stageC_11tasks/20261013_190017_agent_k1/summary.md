# HLS Agent 评测结果

- 时间：2026-10-13 18:45:34
- 模式：**agent**（带工具反馈，失败重试至多 3 次）
- 采样轮数 k：1
- 是否评估综合：否（未跑综合的题在分级里显示「略过」，不会被当成「综合通过」）
- 判定口径：严格（数值与参考 dump 一致才算通过）
- 模型：`claude-fable-5`（backend=auto）
- 器件：`xczu3eg-sbva484-1-e`，时钟 5 ns
- 题目数：11

## 核心指标

| 指标 | 数值 |
| --- | --- |
| pass@1 | **54.5%** |
| 总墙钟 | 883.2 s |
| 单次平均墙钟 | 167.3 s |
| 单次最长墙钟 | 491.9 s |

## 分级判定分布

| 最高级别 | 题目数 |
| --- | --- |
| 可运行 | 6 |
| 可编译 | 4 |
| 未开始 | 1 |

## 分组通过率

| 变体 | 题目数 | pass@1 |
| --- | --- | --- |
| chstone | 2 | 0/2 (0.0%) |
| hls_polybench__fixed__small | 6 | 6/6 (100.0%) |
| machsuite | 2 | 0/2 (0.0%) |
| pp4fpga | 1 | 0/1 (0.0%) |

## 逐题明细

| 题目 | 变体 | 第1轮 | 最好级别 | 平均墙钟 |
| --- | --- | --- | --- | --- |
| 2mm | hls_polybench__fixed__small | 通过 | 可运行 | 28.4s |
| 3mm | hls_polybench__fixed__small | 通过 | 可运行 | 30.2s |
| aes_aes | machsuite | 失败 | 可编译 | 401.2s |
| atax | hls_polybench__fixed__small | 通过 | 可运行 | 26.4s |
| cholesky | hls_polybench__fixed__small | 通过 | 可运行 | 31.2s |
| correlation | hls_polybench__fixed__small | 通过 | 可运行 | 31.7s |
| covariance | hls_polybench__fixed__small | 通过 | 可运行 | 27.7s |
| dfadd | chstone | 失败 | 可编译 | 412.7s |
| dfmul | chstone | 失败 | 未开始 | 491.9s |
| fft_strided | machsuite | 失败 | 可编译 | 335.2s |
| pp4fpga_cordic | pp4fpga | 失败 | 可编译 | 23.5s |

## 失败分析

### 失败类别分布

| 失败类别 | 题数 | 是否值得重试 | 修复方向 |
| --- | --- | --- | --- |
| `CSIM_RUNTIME_ERROR`（仿真程序崩溃） | 2 | 是 | 给出返回码与崩溃前输出；区分「程序崩了」和「测试台报了不一致」 |
| `TEST_MISMATCH`（测试结果不一致） | 1 | 是 | 给出参考值/实际值、最大误差位置与饱和迹象 |
| `UNKNOWN_ERROR`（未分类） | 1 | 否 | 保留原始日志交人工复核 |
| `ENVIRONMENT_ERROR`（工具链/环境问题） | 1 | 否 | 先诊断工具链（动态库/路径/权限），不要重写算法代码 |

### 逐题明细

| 题目 | 轮次 | 卡在哪一级 | 失败类别 | 尝试 | 每次尝试卡在哪 | 原因摘要 |
| --- | --- | --- | --- | --- | --- | --- |
| dfadd | 1 | 可编译 | `TEST_MISMATCH` | 3 | TEST_MISMATCH → STATIC_CHECK_ERROR → STATIC_CHECK_ERROR | testbench 运行返回码 2，输出如下： ...0 b_input=bff0000000000000 expected=7ff0000000000000 output=7ff0000000000000 (inf) a_input=3ff0000000000000 b_input=8000000000000000  |
| dfmul | 1 | 未开始 | `UNKNOWN_ERROR` | 3 | SOURCE_EXTRACTION_ERROR → SOURCE_EXTRACTION_ERROR | - |
| aes_aes | 1 | 可编译 | `CSIM_RUNTIME_ERROR` | 3 | CSIM_RUNTIME_ERROR → SOURCE_EXTRACTION_ERROR → STATIC_CHECK_ERROR | testbench 运行返回码 3221226356，输出如下：  |
| fft_strided | 1 | 可编译 | `CSIM_RUNTIME_ERROR` | 3 | CSIM_RUNTIME_ERROR → STATIC_CHECK_ERROR → CSIM_RUNTIME_ERROR | testbench 运行返回码 4294967295，输出如下： ...751360220.842621 (0.000001) ERROR: 1010 (real): -182526263876.193237 (0.000001) ERROR: 1010 (img): -133948559158.660446 (0.0 |
| pp4fpga_cordic | 1 | 可编译 | `ENVIRONMENT_ERROR` | 1 | ENVIRONMENT_ERROR | csim.exe 缺少数学库运行时 DLL（0xC0000135），零输出退出；触发点在测试台，非模型可修复 |
