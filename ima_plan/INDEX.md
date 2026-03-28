# IMA Prefetch 研究索引

> 自动生成: 2026-03-25 06:30 | 由 /update-ima-index 生成

## 研究总体状态

当前处于 **Phase 3/4/5 并行推进**，取得关键进展。GRASP 核心组件已实现（8 个源文件），消融实验首次证明 GRASP 有效：**SSSP +42.2%**, **IMA tiny +53.6%**（SpMV 因 ×16 展开 + MSHR 饱和暂为 -2%）。SOTA baseline 复现同步推进：stride-INTRA（+2.0% geomean）、INTER（无效）、Snake（不如 stride）、Spare Register（SSSP +7.63%）均已实现或验证。论文绘图基础设施（academic.mplstyle + plot_util）已就绪。仿真加速研究确认：1SM 与 108SM 耗时相当，编译优化 +15% 已落地，论文评估采用 108SM 全量并行方案。最终目标：投稿体系结构顶会论文。

## 各阶段状态

| Phase | 名称 | 状态 | 关键产出 | 最近更新 |
|-------|------|------|----------|----------|
| 01 | IMA 特征化与分类 | 🔄 进行中 | SASS 依赖链分析 + L1 miss breakdown (51-84%) + 4 类 IMA pattern | 2026-03-22 |
| 02 | 相关工作调研 | 🔄 进行中 | CPU 8 篇 + GPU 9 篇 + `gpu_prefetcher_impl_provenance.md` | 2026-03-22 |
| 03 | 性能天花板 | 🔄 部分完成 | ima_high ideal L1D: 1.75×–3.04× speedup | 2026-03-14 |
| 04 | GRASP Prefetcher 设计 | 🔄 进行中 | GRASP 设计框架 + `small_1sm_cta5` 时序证据 | 2026-03-24 |
| 05 | GPGPU-Sim 实现 | 🔄 **消融实验完成 + SOTA baseline 复现中** | SSSP +42.2% / SpMV -2% 消融 + 4 种 SOTA baseline | 2026-03-25 |
| 06 | 评估方案 | 🔄 **进行中** | benchmark suite (7算法×3级) + 仿真加速研究 | 2026-03-25 |
| 07 | 论文大纲 | 🔄 进行中 | 大纲 + 10 insight + academic 绘图基础设施 | 2026-03-24 |

## 关键发现

1. **GRASP 在 SSSP 上 +42.2%** — d=4, 108SM, 50 CTA; MSHR 压力低 + 跨 kernel 持久化生效 → `05_implementation/grasp_ablation/README.md` §4
2. **GRASP 在 IMA tiny 上 +53.6%** — 专用 IMA 测例，MSHR 无压力 → `05_implementation/grasp_ablation/README.md` §5
3. **GRASP 在 SpMV 上 -2%** — ×16 展开导致 4/5 chain 学不到 stride + MSHR 饱和 (3M RFAIL) → `05_implementation/grasp_ablation/README.md` §3
4. **IMA 占 L1 miss 的 51%–84%** — 5 个核心 workload 的主 kernel LDG miss 归因 → `01_ima_characterization/l1_miss_breakdown/analysis.md`
5. **Ideal L1D 天花板 1.75×–3.04×** — bfs 1.75×, sssp 2.46×, bc 3.04×, cc 2.22×, spmv 2.31× → `03_performance_ceiling.md`
6. **L1/L2 命中率不对称** — L1 miss 70-77% 但 L2 miss 仅 22-34%，prefetch 聚焦 L2→L1 → `07_paper_outline/insight.md` Insight 2
7. **IMAD.WIDE 链覆盖率 88-99%** — 56 个实现的 1188 条 IMA 链中 88.4% 为 IMAD.WIDE → `07_paper_outline/insight.md` Insight 7
8. **SOTA stride-INTRA (+ IMA gating) geomean +2.00%** — BFS +3.92%, SSSP +4.07%, CC +0.18%, SpMV -0.08% → `05_implementation/sota_baseline/README.md`
9. **SOTA Spare Register: SSSP +7.63%** — 两步预取（stride index + pair table data），所有 baseline 中最高 → `05_implementation/sota_baseline/README.md`
10. **仿真加速：1SM ≈ 108SM 耗时** — 1SM 每 cycle 快 77x 但总 cycle 多 68x，相消 → `06_evaluation_plan/simulation_acceleration_study.md`
11. **编译优化 +15%** — `-march=native` + LTO，IPC 完全不变 → `06_evaluation_plan/simulation_acceleration_study.md`
12. **四类 IMA pattern 的 prefetchability 层级** — Pattern I/II 可覆盖，III 部分，IV 不覆盖 → `01_ima_characterization.md` §Level 1

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

## SOTA Baseline 状态

| Baseline | 状态 | 最佳结果 | 评估价值 |
|----------|------|---------|---------|
| **stride-INTRA** (+ IMA gating) | ✅ 完成 | geomean +2.00% | 主对照基线 |
| **stride-INTER** | ✅ 完成 | 0% (BFS/SSSP prefetch_issued=0) | Negative result |
| **Snake** | ✅ 完成 | 不如 stride-INTRA | Negative result |
| **Spare Register** | 🔄 部分完成 | SSSP +7.63% | 最强 baseline |

## 目录详情

### 01_ima_characterization/ (383 files)
- **状态**: 核心分析完成
- **关键文件**: `sass_analysis/README.md`, `l1_miss_breakdown/analysis.md`
- **数据/脚本**: 18 csv, 3 py, 3 svg
- **最近修改**: 2026-03-22

### 02_related_work/ (18 files)
- **状态**: 论文收集完成，分析进行中；新增 GPU prefetcher 实现公开性梳理
- **关键文件**: `gpu_prefetcher_impl_provenance.md`
- **最近修改**: 2026-03-22

### 04_prefetcher_design/ (239 files)
- **状态**: 设计框架已定，时序证据持续回填
- **关键文件**: `流程说明.md`, `extra_pattern/small_1sm_cta5/prefetch_design_summary_lrr.md`
- **数据/脚本**: 158 csv, 6 py, 6 sh, 31 svg
- **最近修改**: 2026-03-25

### 05_implementation/ (53 files)
- **状态**: GRASP Phase A/B 完成 + 消融实验 + SOTA baseline 复现中
- **子目录**: `ima_pair_table/`（设计/正确性）, `spmv_deep_dive/`（迭代级分析）, `grasp_ablation/`（消融实验报告）, `sota_baseline/`（4 种 SOTA 实现+进展）
- **关键文件**: `experiment_progress.md`, `grasp_ablation/README.md`, `sota_baseline/README.md`
- **数据/脚本**: 17 md, 4 py, 13 csv, 4 svg
- **最近修改**: 2026-03-25

### 06_evaluation_plan/ (2 files)
- **状态**: Benchmark suite 定义完成（7 算法 × 3 IMA 级 = 19 trace keys）+ 仿真加速研究完成
- **关键文件**: `benchmark_suite.md`, `simulation_acceleration_study.md`
- **最近修改**: 2026-03-25

### 07_paper_outline/ (39 files)
- **状态**: 大纲 + insight 清单 + academic 绘图基础设施已就绪
- **关键文件**: `insight.md`, `introduction.md`, `plot_style/academic.mplstyle`, `plot_style/plot_util.py`
- **数据/脚本**: 2 md, 4 py, 6 svg, 6 demo figures (pdf/png/svg)
- **最近修改**: 2026-03-24

### weekly_report/ (8 files)
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
11. **P1 已收敛为 pair-table 方案** — trace-driven 的 runtime payload 缺口由预构建映射补齐

## GRASP 逐 Iteration 分析工具

对任何 IMA workload 的 GRASP 行为进行逐 iteration 粒度分析，定位加速/未加速原因。

| 文件 | 用途 |
|------|------|
| `04_prefetcher_design/tiny_case/grasp_verify/analyze_grasp_iterations.py` | 分析脚本（3 种输出格式） |
| `04_prefetcher_design/tiny_case/grasp_verify/README.md` | 完整使用流程与诊断指南 |

**输出格式**：
- `--format summary` (a): 单配置摘要表
- `--format timeline` (b): 逐 iteration 详细事件流（L1 demand + GRASP 内部事件按 cycle 交错）
- `--format compare` (c): Baseline vs GRASP 对比表（含 per-iteration speedup）

**典型用法**：
```bash
python3 analyze_grasp_iterations.py \
    --grasp-dir <grasp_output> --baseline-dir <baseline_output> \
    --warps 1 --format all --output-dir <output>
```

**何时使用**：分析 GRASP 在某个 workload 上加速不理想时，先看 compare 定位问题 iteration，再用 timeline 检查 CD/CT/IST/PRB 时序。详见 README.md §7。

## 待解决问题

- `05_implementation/grasp_ablation/`: SpMV ×16 展开使 stride 学习失效，需设计层面解决
- `05_implementation/grasp_ablation/`: Throttle 80% 阈值在 MSHR 饱和场景未触发，需调整策略
- `05_implementation/sota_baseline/`: Spare Register SpMV 实验待完成
- `06_evaluation_plan/`: 1SM 全量运行中（bfs/bc/cc），结果将作为 GRASP 多算法评估 ground truth
- `02_related_work.md`: 论文详细笔记与 gap analysis 待完成
- `03_performance_ceiling.md`: ima_med / ima_small 的 ideal L1D 数据待补全
