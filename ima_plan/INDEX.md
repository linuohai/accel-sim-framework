# IMA Prefetch 研究索引

> 自动生成: 2026-04-02 20:30 | 由 /update-ima-index 生成

## 研究总体状态

当前处于 **Phase 5 评估深化 + Phase 6 评估基础设施完善**。GRASP 核心组件已实现（8 个源文件），ima_med 全量实验取得 **geomean +35.5%**。**Speculative stride 机制已实现**（默认 OFF）：首次 observation 用 per-chain stride_hint（SASS 分析得出）推测预取，BFS/SSSP/SpMV 提升 +3~7%，BC 退化 -8.6%，记为 DSE 参数。**小 case debug 方法学已建立**（5 阶段 + 7 步归因管线）。BFS 1SM 分析发现 CT 在不同 kernel 切换时全量 reset stride（每轮 BFS level 重训练 7K-29K cycles），也记为 DSE 参数。SOTA baseline 5 种已完成，CAPS 在 SpMV 上 +14.30%。最终目标：投稿体系结构顶会论文。

## 各阶段状态

| Phase | 名称 | 状态 | 关键产出 | 最近更新 |
|-------|------|------|----------|----------|
| 01 | IMA 特征化与分类 | 🔄 进行中 | SASS 依赖链分析 + L1 miss breakdown (51-84%) + 4 类 IMA pattern | 2026-03-29 |
| 02 | 相关工作调研 | 🔄 进行中 | CPU 8 篇 + GPU 9 篇 + 论文重组为 6 个子目录 | 2026-03-30 |
| 03 | 性能天花板 | 🔄 部分完成 | ima_high ideal L1D: 1.75×–3.04× speedup | 2026-03-14 |
| 04 | GRASP Prefetcher 设计 | 🔄 设计框架已定 | GRASP 设计框架 + `small_1sm_cta5` 时序证据 | 2026-03-28 |
| 05 | GPGPU-Sim 实现 | 🔄 **ima_med +35.5% + spec stride + debug 方法学** | speculative stride (DSE) + debug 规范 + CT reset 发现 | 2026-04-02 |
| 06 | 评估方案 | 🔄 **输出规范 + 批量实验** | benchmark suite + output spec + ideal L1D report + batch run | 2026-04-02 |
| 07 | 论文大纲 | 🔄 进行中 | 大纲 + 10 insight + academic 绘图 + LaTeX 模板 + figures + abstract | 2026-04-01 |

## 关键发现

1. **GRASP ima_med geomean +35.5%** — BFS +49.8%, SSSP +44.0%, SpMV +26.6%, BC +23.3%（108SM 全量运行）→ `05_implementation/experiment_progress.md` §5b
2. **GRASP 在 SSSP ima_high 上 +42.2%** — d=4, 108SM, 50 CTA; MSHR 压力低 + 跨 kernel 持久化生效 → `05_implementation/grasp_ablation/README.md` §4
3. **GRASP 在 IMA tiny 上 +53.6%** — 专用 IMA 测例，MSHR 无压力 → `05_implementation/grasp_ablation/README.md` §5
4. **IMA 占 L1 miss 的 51%–84%** — 5 个核心 workload 的主 kernel LDG miss 归因 → `01_ima_characterization/l1_miss_breakdown/analysis.md`
5. **Ideal L1D 天花板 1.75×–3.04×** — bfs 1.75×, sssp 2.46×, bc 3.04×, cc 2.22×, spmv 2.31× → `03_performance_ceiling.md`
6. **L1/L2 命中率不对称** — L1 miss 70-77% 但 L2 miss 仅 22-34%，prefetch 聚焦 L2→L1 → `07_paper_outline/insight.md` Insight 2
7. **IMAD.WIDE 链覆盖率 88-99%** — 56 个实现的 1188 条 IMA 链中 88.4% 为 IMAD.WIDE → `07_paper_outline/insight.md` Insight 7
8. **SOTA stride-INTRA (+ IMA gating) geomean +2.00%** — BFS +3.92%, SSSP +4.07%, CC +0.18%, SpMV -0.08% → `05_implementation/sota_baseline/README.md`
9. **SOTA Spare Register: SSSP +7.63%** — 两步预取（stride index + pair table data），所有 baseline 中最高 → `05_implementation/sota_baseline/README.md`
10. **四类 IMA pattern 的 prefetchability 层级** — Pattern I/II 可覆盖，III 部分，IV 不覆盖 → `01_ima_characterization.md` §Level 1
11. **Stride 学习跨 CTA 污染修复** — PT hit rate 29%→60%，accuracy +3pp → `05_implementation/experiment_progress.md` §7f
12. **CAPS (CTA-Aware Prefetcher) SpMV +14.30%** — stride prefetcher 中 SpMV 最优，但 IMA data coverage ≈ 0% → `05_implementation/sota_baseline/README.md`
13. **Speculative stride geomean +1.09%**（默认 OFF）— BFS +3.6%, SSSP +3.2%, SpMV +6.8%, BC -8.6%。per-chain stride_hint 从 SASS 分析（inner=4, unrolled×4=16, SpMV ×16=64）→ `05_implementation/dse_ct_reset_policy.md`
14. **CT kernel 切换全量 reset** — BFS 每轮 level 重训练 stride（5 轮 × 7K-29K cycles = 65K cycles, 4.1%），根因：insert/bfs_kernel 交替触发 `m_ct.reset()` → `05_implementation/dse_ct_reset_policy.md`

## GRASP ima_med 全量结果（108SM，完整运行）

| Workload | Baseline IPC | GRASP IPC | Speedup |
|----------|-------------|-----------|---------|
| BFS | 7.35 | 11.02 | **+49.8%** |
| SSSP | 9.56 | 13.76 | **+44.0%** |
| SpMV | 129.68 | 164.12 | **+26.6%** |
| BC | 10.83 | 13.36 | **+23.3%** |
| **Geomean** | | | **+35.5%** |

> 数据来源：`05_implementation/experiment_progress.md` §5b (2026-03-28)

## GRASP ima_small Timeliness/Coverage（新指标，108SM 完整运行）

| Workload | Baseline IPC | GRASP IPC | Speedup | Data Timeliness | Data Coverage | Accuracy | Index Coverage |
|----------|-------------|-----------|---------|-----------------|--------------|----------|---------------|
| BFS | 23.56 | 30.34 | **+28.8%** | 67.85% | 14.09% | 55.89% | −5.15% |
| SSSP | 28.81 | 34.59 | **+20.1%** | 64.36% | 11.54% | 49.19% | +8.05% |
| SpMV | 129.68 | 152.04 | **+17.2%** | 93.34% | 5.87% | 28.83% | +5.49% |
| BC | 37.65 | 44.72 | **+18.8%** | 85.83% | 11.05% | 50.92% | +4.21% |

> Timeliness = hits/(hits+hit_reserved); Coverage = (baseline_misses−grasp_misses)/baseline_misses
> BFS distance sweep (d=1~8): d=1 最优，d 增大后 timeliness/coverage 单调下降
> 数据来源：`05_implementation/experiment_progress.md` §7d (2026-03-30)

## GRASP 组件命名映射

| 缩写 | 全称 | 原名 |
|------|------|------|
| CD | Chain Detector | Dependency Detector |
| CT | Chain Table | Table A / PC Dependency Table |
| TT | Target Table | Table B / Pattern Table |
| IPU | Index Prefetch Unit | Address-Triggered Index Prefetch |
| DPU | Data Prefetch Unit | Data Prefetch Generator |
| TC | Throttle Controller | (不变) |
| IST | Iteration Stride Tracker | Per-PC Stride Learning |
| ACU | Address Computation Unit | (不变) |
| PRB | Prefetch Request Buffer | (不变) |

## GRASP 源代码文件

代码位置：`gpu-simulator/gpgpu-sim/src/gpgpu-sim/grasp_*.{h,cc}`

| 文件 | 职责 |
|------|------|
| `grasp_prefetcher.{h,cc}` | 顶层：config, PRB, IST, stats, 主逻辑 |
| `grasp_chain_detector.{h,cc}` | CD：FIFO + tracked warp + LDG→IMAD.WIDE→LDG |
| `grasp_tables.{h,cc}` | CT + TT 查找/插入/淘汰/stride 学习 |
| `grasp_tracer.{h,cc}` | GRASP 事件追踪器（CSV 输出） |
| `trace_driven.cc` | trace-driven warp exit 的 GRASP hook（与 shader.cc 对齐） |

Golden chain CSV：`05_implementation/ima_pair_table/golden/strict_selected_chain_instances.csv`

GRASP 仿真输出行：
- `GRASP_CONFIG:` — 一次性参数 dump（仅 SM0）
- `GRASP_DEMAND SM*:` — global reads/misses, throttle_suppressed
- `GRASP_IMA_DEMAND SM*:` — IMA index/data 分项：reads/hits/hit_reserved/misses
- `GRASP_TIMELINESS SM*:` — index/data timeliness%（= hits/(hits+hit_reserved)）
- `GRASP_EFFECT SM*:` — legacy pf_useful/pf_useless/pf_late/accuracy%（仅供 debug）
- `GRASP_STORAGE SM*:` / `GRASP_RFAIL SM*:` — 存储利用率 / reservation fail 分布
- `IMA_DEMAND:` / `IMA_TIMELINESS:` — 全局汇总（baseline 和 GRASP 都有）

## Legacy 声明（新 session 请忽略）

以下内容是历史遗留产物，**不代表当前设计/配置/数据**。新 session 不要基于这些内容做判断：

| Legacy 项 | 位置 | 被什么替代 | 说明 |
|-----------|------|-----------|------|
| `GRASP_EFFECT` 指标 | 仿真 log 输出 | `GRASP_IMA_DEMAND` + `GRASP_TIMELINESS` | 不区分 IMA PC，粒度粗；已被 IMA PC 分类统计替代，仅供 debug 参考 |
| `-gpgpu_ima_prefetch_*` 参数 | gpgpusim.config | `-grasp_enable` + `grasp_*` 参数 | 旧版 IMA prefetcher，与 GRASP 互斥，已禁用 |
| `distance=1` 配置 | experiment_progress §1-§4 | `distance=4` | distance=1 已证明无效（SpMV -0.47%），当前默认 distance=4 |
| experiment_progress §1-§4 | `05_implementation/experiment_progress.md` | §5b（ima_med 全量） | 早期实验使用 ima_high + 限制 CTA + distance=1，与当前配置不可比 |
| `agent_handoff_status.md` | `05_implementation/ima_pair_table/` | `.claude/BOARD.md` | 旧版串行交接文档，已被并发协调机制替代 |
| `04_prefetcher_design/流程说明.md` | `04_prefetcher_design/` | `04_prefetcher_design.md` 正文 | 文件自标"不应当作 golden"，是早期设计草稿 |
| 旧组件名 (Table A/B 等) | 04 设计文档 | CT/TT/CD 等（见组件命名映射） | 仅在早期文档中出现，代码已统一为新名 |

## 源码导航（task → required reading）

工作前先确认需要读哪些文件，**禁止不读代码就推测原因**：

| 你要做什么 | 必须先读 |
|-----------|---------|
| 调 GRASP 整体行为/参数 | `grasp_prefetcher.{h,cc}`（config/PRB/IST/stats）+ `experiment_progress.md` 最新 section |
| 调 stride learning / distance | `grasp_tables.cc`（`update_stride()`、`ist_distance`）+ `grasp_ablation/README.md` §4 |
| 调 chain detection / pattern | `grasp_chain_detector.cc`（`on_issue()`、`check_chain()`）|
| 调 throttle / MSHR 压力 | `grasp_prefetcher.cc`（`should_throttle()`）+ RFAIL 输出 |
| 分析 SpMV 问题 | `experiment_progress.md` §5b + `grasp_tables.cc`（×16 展开分析）|
| 改 IMA chain 定义 | `05_implementation/ima_pair_table/golden/*.csv`（golden，改后必须重跑回归测试） |
| 改 SOTA baseline | `05_implementation/sota_baseline/README.md` + 对应 `baseline_*.cc` |
| 改实验基础设施 | `traceL1` 脚本 + `CLAUDE.md` "运行仿真" section |
| 写论文图表 | `07_paper_outline/plot_style/plot_util.py` + `CLAUDE.md` "绘图规范" |

## SOTA Baseline 状态

| Baseline | 状态 | 最佳结果 | 评估价值 |
|----------|------|---------|---------|
| **stride-INTRA** (+ IMA gating) | ✅ 完成 | geomean +2.00% | 主对照基线 |
| **stride-INTER** | ✅ 完成 | 0% (BFS/SSSP prefetch_issued=0) | Negative result |
| **Snake** | ✅ 完成 | BC +2.96%, SpMV +1.47% | Index stride 提升，IMA data 无影响 |
| **Spare Register** | 🔄 部分完成 | SSSP +7.63% | IMA-aware 最强 baseline |
| **CAPS** | ✅ 完成 | **SpMV +14.30%**, 其余 <0.1% | CTA-aware stride, IMA data coverage ≈ 0% |

## 实验基础设施

| 功能 | 说明 |
|------|------|
| **EXPERIMENT SUMMARY** | `traceL1` 仿真后自动写入 log 末尾，含 status/kernels/IPC |
| **Baseline Registry** | `06_evaluation_plan/baseline_registry.csv`，baseline 不重跑 |
| **回归测试** | `grasp_regression.sh check`（默认 --quick ~34min，--full 4 workload 并行 ~44min） |
| **Golden Chain CSV** | `ima_pair_table/golden/strict_selected_chain_instances.csv`，所有 GRASP/IMA 仿真的必需输入 |
| **输出规范** | `06_evaluation_plan/output_specification.md`，展示/调试指标分级 + Index/Data/Total 三版本规则 |
| **Debug 方法学** | `05_implementation/debug/README.md`，小 case 5 阶段 debug + 7 步 root cause 归因管线 |
| **DSE 参数** | `05_implementation/dse_ct_reset_policy.md`，speculative stride + CT reset policy 待验证特性 |

## 目录详情

### 01_ima_characterization/
- **状态**: 核心分析完成，新增 cuGraph 分析
- **关键文件**: `sass_analysis/README.md`, `l1_miss_breakdown/analysis.md`
- **数据/脚本**: 19 csv, 4 py, 1 sh, 3 svg
- **最近修改**: 2026-03-29

### 02_related_work/
- **状态**: 论文收集完成（CPU 8 + GPU 9），重组为 6 个子目录
- **子目录**: `gpu_irregular/`, `gpu_stride/`, `gpu_sched/`, `ima_hw/`, `ima_sw/`, `related/`
- **关键文件**: `gpu_prefetcher_impl_provenance.md`
- **最近修改**: 2026-03-30

### 04_prefetcher_design/
- **状态**: 设计框架已定，时序证据持续回填
- **关键文件**: `流程说明.md`, `analyze_grasp_iterations_v2.py`
- **数据/脚本**: 173 csv, 8 py, 6 sh, 31 svg
- **最近修改**: 2026-03-28

### 05_implementation/
- **状态**: GRASP +35.5% + speculative stride (DSE) + debug 方法学 + 5 种 SOTA baseline
- **子目录**: `regression/`, `grasp_ablation/`, `sota_baseline/`, `ima_pair_table/`（含 `golden/`）, `grasp_real_diag/`, `chain_extraction/`, `debug/`（BFS 1SM root cause 分析）, `grasp_metrics/`
- **关键文件**: `experiment_progress.md`, `dse_ct_reset_policy.md`, `debug/README.md`, `sota_baseline/README.md`
- **新增（2026-04-02）**: `dse_ct_reset_policy.md`（DSE 参数：speculative stride + CT reset policy）, `debug/README.md`（5 阶段 debug 规范 + 7 步归因管线）, chain CSV `stride_hint` 列
- **最近修改**: 2026-04-02

### 06_evaluation_plan/
- **状态**: Benchmark suite + baseline registry + **输出规范** + ideal L1D report + batch run
- **关键文件**: `benchmark_suite.md`, `output_specification.md`, `baseline_registry.csv`, `ideal_l1d_report.md`
- **数据**: 9 md, 1 csv
- **最近修改**: 2026-04-02

### 07_paper_outline/
- **状态**: 大纲 + abstract + insight 清单 + academic 绘图 + LaTeX 模板 + figures + 投稿指南
- **子目录**: `plot_style/`, `latex_template/`, `submission_guidelines/`, `figures/`
- **关键文件**: `insight.md`, `introduction.md`, `abstract.md`, `plot_style/plot_util.py`
- **数据/脚本**: 7 md, 5 py, 10 svg, 4 tex, 20 pdf, 18 png
- **最近修改**: 2026-04-01

### weekly_report/
- **状态**: 周报文档与配图
- **关键文件**: `2026-03-21_image_first/README.md`
- **最近修改**: 2026-03-22

## 实现阻塞项

### 原始设计问题

| 编号 | 问题 | 状态 |
|------|------|------|
| P1 | trace-driven 模式无运行时数据值 | ✅ `ima_pair_table` 方案 |
| P2 | per-warp FIFO 深度不足 | ✅ 共享 FIFO |
| P3 | IMAD.WIDE 基地址解析缺失 | ✅ 由 P1 消解 |
| P4 | IMAD.WIDE 无专用 op_type | ✅ 保存原始 SASS 助记符 |
| P5 | fill 路径无法识别 index prefetch | ✅ 由 P1 消解 |
| P6 | data prefetch 多 lane coalescing | 需实现轻量 coalescer |
| P7 | Pending Buffer 容量低估 | ✅ 由 P1 消解 |
| P8 | Kernel launch 清表 hook | ✅ kernel 切换时清空 |

### 首轮实验暴露的问题

| 编号 | 问题 | 状态 |
|------|------|------|
| E1 | distance=1 预取不及时 | ✅ 已修复：distance=4 验证有效 |
| E2 | per-kernel reset 破坏多 kernel 训练 | ✅ 已修复：跨 kernel stride 持久化 |
| E3 | 缺少 Throttle Control | ⚠️ 已实现但 80% 阈值在 SpMV 上未触发 |
| E4 | Stride 学习跨 CTA 污染 | ✅ 已修复：stride freeze + warp exit cleanup + trace-driven hook |

### SpMV 特殊问题

| 问题 | 状态 |
|------|------|
| ×16 展开使 4/5 chain 学不到 stride | 🔴 设计瓶颈 |
| MSHR 极度饱和 (3M RFAIL) | 🔴 需更积极节流 |

## Insight 清单

从 `07_paper_outline/insight.md` 提取：

1. **IMAD.WIDE 零推断检测** — GPU ISA 将 IMA 结构显式暴露
2. **L1/L2 命中率不对称** — prefetch 聚焦 L2→L1
3. **IMA 占 L1 Miss 主体** — 51%–84%
4. **PC 膨胀可归并** — (base, scale) key 解决 30× 展开
5. **One-to-Many 索引复用** — BC reverse 1→3
6. **训练一次全 SM 复用** — CT/TT per-SM shared，64 倍分摊
7. **固定指令检测覆盖率** — 88-99% IMAD.WIDE 链
8. **四类 Pattern Prefetchability** — I/II 高, III 有限, IV 不覆盖
9. **Ideal L1D 天花板** — 1.75×–3.04×
10. **写无效化保证正确性** — false positive 清除
11. **Stride 学习跨 CTA 污染修复** — PT hit rate 29%→60%，accuracy +3pp

## GRASP 逐 Iteration 分析工具

| 文件 | 用途 |
|------|------|
| `04_prefetcher_design/tiny_case/grasp_verify/analyze_grasp_iterations.py` | 分析脚本（3 种输出格式） |
| `04_prefetcher_design/analyze_grasp_iterations_v2.py` | v2 增强版分析脚本 |

**输出格式**：`summary` | `timeline` | `compare`

## 待解决问题

- `05_implementation/`: SpMV ×16 展开使 stride 学习失效，需设计层面解决
- `05_implementation/`: Throttle 80% 阈值在 MSHR 饱和场景未触发，需调整策略
- `05_implementation/sota_baseline/`: Spare Register SpMV 实验待完成
- `05_implementation/`: Speculative stride BC 退化 -8.6% 根因待查（stride 值已正确，可能是推测机制副作用）
- `05_implementation/`: CT kernel 切换 reset policy DSE（full vs tracking_only）待对照实验
- `02_related_work.md`: 论文详细笔记与 gap analysis 待完成
- `03_performance_ceiling.md`: ima_med / ima_small 的 ideal L1D 数据待补全
