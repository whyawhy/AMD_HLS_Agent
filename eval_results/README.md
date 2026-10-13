# eval_results — 评测记录索引

每个子目录是一次评测运行，包含：

- `results.json` — 逐次运行的完整记录（含每题的失败类别、每次尝试卡在哪、返回码）
- `summary.md` — 人读汇总表（核心指标、分级判定分布、失败类别分布、逐题明细）
- `failure_analysis.md` — 由 `skill/analyze_failures.py` 生成的失败模式分析（按需生成）
- `gain_vs_baseline.md` — 由 `skill/compare_runs.py` 生成的增益对照（按需生成）

> ⚠️ **不同批次的题目集不一样，不能横向比较通过率。**
> 目录名里带 `_ab_` / `_stageC` 的是 2026-10-13 优化审计专门跑的**受控对照**，
> 每次运行的题目集在 `results.json` 的 `tasks` 字段里可以核对。

## 2026-10-13 优化审计的受控对照

| 目录 | 是什么 | 题目集 | 结果 |
| --- | --- | --- | --- |
| `_ab_before` | A/B 基准：**优化前**的代码 | 4 题（DLL/环境类） | 2/4 |
| `_ab_mid` | 只加了结构化记录、还没加测试台识别的中间态 | 同上 4 题 | 2/4，`cordic` 白付 325.7s |
| `_ab_after` | **优化后**的代码 | 同上 4 题 | 2/4，`gramschmidt` 级别回到「可运行」，`cordic` 21.5s |
| `_stageC_11tasks` | 11 题代表性题集 | 2mm/3mm/atax/correlation/covariance/cholesky/fft_strided/aes_aes/dfadd/dfmul/pp4fpga_cordic | 6/11 |
| `_stageC2_confirm` | 最慢三题，验证"截断后关思考"的效果 | dfadd/dfmul/fft_strided | 合计墙钟 −14% |

分析见 `../OPTIMIZATION_BENCHMARK.md` 与 `../OPTIMIZATION_TEST_REPORT.md`。

## 历史批次（优化前）

`20261009_*` ~ `20261012_*` 是优化审计之前跑的批次。注意：

- 只有 `20261010_001712_agent_k1` 与 `20261011_003719_agent_k1` 是 **122 题全量**；
  其余是**故意挑选的难题子集**（例如 `20261011_233938_agent_k1` 的 27 题在
  全量批次里通过 0 题，属于最难的一档），所以 11.1% 与 72.1% 之间没有可比性。
- 这些批次里的 `results.json` 生成于引入结构化失败分类之前，只有自由文本
  `error` 字段，没有 `failure_kind` / `failure_level`。
  `skill/analyze_failures.py` 对它们会退回按阶段粗分并给出提示。
