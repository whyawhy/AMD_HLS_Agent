# 智能体 vs 基线 对比（增益）

- 智能体：`20261011_003719_agent_k1`（claude-fable-5，重试上限 2，技能包+工具反馈）
- 基线　：`20261010_232444_baseline_k1`（同一模型，单次生成、不重试、不带技能包）
- 判定口径：严格（数值一致才算通过）

## 总览

| 指标 | 基线 | 智能体 | 增益 |
| --- | --- | --- | --- |
| 通过题目数 | 83/122 | 88/122 | +5 |
| pass@1 | 68.0% | 72.1% | **+4.1%** |
| 相对提升 | — | — | +6% |

- 总墙钟：基线 2334s，智能体 3270s

## 分变体对比

| 变体 | 基线 | 智能体 | 增益 |
| --- | --- | --- | --- |
| c2hlsc | 12/12 (100%) | 12/12 (100%) | +0 |
| chstone | 11/20 (55%) | 15/20 (75%) | +4 |
| flowgnn | 3/3 (100%) | 3/3 (100%) | +0 |
| gnnbuilder | 3/3 (100%) | 3/3 (100%) | +0 |
| hls_polybench__fixed__small | 18/28 (64%) | 18/28 (64%) | +0 |
| machsuite | 10/17 (59%) | 11/17 (65%) | +1 |
| polybench | 19/28 (68%) | 17/28 (61%) | -2 |
| pp4fpga | 0/3 (0%) | 2/3 (67%) | +2 |
| rosetta | 7/8 (88%) | 7/8 (88%) | +0 |

## 智能体比基线多做对的题

共 9 道：

- `block_mm`（pp4fpga，尝试 1 次）
- `correlation`（hls_polybench__fixed__small，尝试 1 次）
- `covariance`（hls_polybench__fixed__small，尝试 1 次）
- `df_countLeadingZeros64`（chstone，尝试 1 次）
- `df_float64_ge`（chstone，尝试 1 次）
- `df_float64_le`（chstone，尝试 1 次）
- `df_propagateFloat64NaN`（chstone，尝试 1 次）
- `gemm_blocked`（machsuite，尝试 1 次）
- `parallel_merge_sort`（pp4fpga，尝试 1 次）

## 基线比智能体多做对的题（回归，需分析）

- `jacobi-1d`（hls_polybench__fixed__small）
- `polybench__jacobi-2d`（polybench）
- `polybench__lu`（polybench）
- `syr2k`（hls_polybench__fixed__small）

