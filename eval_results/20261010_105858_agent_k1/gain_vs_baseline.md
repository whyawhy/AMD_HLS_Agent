# 智能体 vs 基线 对比（增益）

- 智能体：`20261010_105858_agent_k1`（claude-fable-5，重试上限 2，技能包+工具反馈）
- 基线　：`20261010_105653_agent_k1`（同一模型，单次生成、不重试、不带技能包）
- 判定口径：严格（数值一致才算通过）

## 总览

| 指标 | 基线 | 智能体 | 增益 |
| --- | --- | --- | --- |
| 通过题目数 | 10/17 | 2/2 | -8 |
| pass@1 | 58.8% | 100.0% | **+41.2%** |
| 相对提升 | — | — | +70% |

- 总墙钟：基线 37196s，智能体 31s

## 分变体对比

| 变体 | 基线 | 智能体 | 增益 |
| --- | --- | --- | --- |
| machsuite | 10/17 (59%) | 2/2 (100%) | -8 |

## 智能体比基线多做对的题

共 1 道：

- `viterbi_viterbi`（machsuite，尝试 1 次）

## 基线比智能体多做对的题（回归，需分析）

- `bfs_bulk`（machsuite）
- `bfs_queue`（machsuite）
- `gemm_blocked`（machsuite）
- `gemm_ncubed`（machsuite）
- `kmp_kmp`（machsuite）
- `sort_merge`（machsuite）
- `spmv_crs`（machsuite）
- `spmv_ellpack`（machsuite）
- `stencil_stencil2d`（machsuite）

