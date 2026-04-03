# IMA Prefetch 研究索引

> 自动生成: 2026-04-03 23:30 | 由 /update-ima-index 生成

## 研究总体状态

当前处于 **Phase 5 优化迭代 + Phase 6 大规模评估 + Phase 7 论文撰写**。**Throttle Control DSE 已完成**：tc_mode=4 Cooldown Timer 框架实现并经 9-workload 验证，推荐配置 T40C200（thr=40, cd=200），SpMV +3.47%, BFS/SSSP +0.37%, 0/9 退化。核心发现：IPC 提升来自 MSHR 拥塞缓解 + cache pollution 减少，而非 miss 数量减少。4 类图数据集 + 6 算法（PR 已移除）的评估 95% 完成。**论文大纲已定稿**：§1-§7 完整大纲 + 17 figures + 4 tables（`paper_structure.md`）。SOTA baseline 5 种已完成。最终目标：投稿 MICRO 2026。

## 各阶段状态

| Phase | 名称 | 状态 | 关键产出 | 最近更新 |
|-------|------|------|----------|----------|
| 01 | IMA 特征化与分类 | 🔄 进行中 | SASS 依赖链分析 + L1 miss breakdown (51-84%) + 4 类 IMA pattern | 2026-03-29 |
| 02 | 相关工作调研 | 🔄 进行中 | CPU 8 篇 + GPU 9 篇 + 论文重组为 6 个子目录 | 2026-03-30 |
| 03 | 性能天花板 | 🔄 部分完成 | ima_high ideal L1D: 1.75x-3.04x speedup | 2026-03-14 |
| 04 | GRASP Prefetcher 设计 | 🔄 设计框架已定 | GRASP 设计框架 + `small_1sm_cta5` 时序证据 | 2026-03-28 |
| 05 | GPGPU-Sim 实现 | 🔄 **Throttle DSE 完成** | CT/CD fix + Throttle T40C200 + 5 SOTA baseline | 2026-04-03 |
| 06 | 评估方案 | 🔄 **4 类图 x 6 算法大规模评估** | benchmark suite + experiment_results.md + 28 NVBit traces + ~140 仿真 | 2026-04-03 |
| 07 | 论文大纲 | 🔄 **权威大纲已定稿** | `paper_structure.md`（§1-§7 + 17fig + 4tab）+ 11 insight + LaTeX 模板 | 2026-04-03 |

## 关键发现

1. **Throttle T40C200 Cooldown Timer: 0/9 退化, SpMV +3.47%** -- tc_mode=4, thr=40, cd=200; useless PFs 减少 25-61%; IPC 提升来自 MSHR 拥塞缓解而非 miss 减少 -> `05_implementation/dse_throttle_control/README.md` §7
2. **GRASP ima_med geomean +35.5%** -- BFS +49.8%, SSSP +44.0%, SpMV +26.6%, BC +23.3%（108SM 全量运行）-> `05_implementation/experiment_progress.md` S5b
3. **L1 MQ/MSHR 不是瓶颈（7h 实验）** -- 消除全部 RFAIL 后 data_misses 仅减 0.3%，IPC 反降 4.7%。74% 原 RFAIL 预取变 useless（cache 污染），accuracy 从 44% 降到 23% -> `experiment_progress.md` S7h
4. **CT kernel reset + CD FIFO bug fix** -- CT 用指针比较（trace-driven 永远不同）+ CD FIFO invalidate 不回收 m_count。修复后 BFS +3.6%, SSSP +3.2%, SpMV +6.8% -> `experiment_progress.md` S7g
5. **IMA 占 L1 miss 的 51%-84%** -- 5 个核心 workload 的主 kernel LDG miss 归因 -> `01_ima_characterization/l1_miss_breakdown/analysis.md`
6. **Ideal L1D 天花板 1.75x-3.04x** -- bfs 1.75x, sssp 2.46x, bc 3.04x, cc 2.22x, spmv 2.31x -> `03_performance_ceiling.md`
7. **L1/L2 命中率不对称** -- L1 miss 70-77% 但 L2 miss 仅 22-34%，prefetch 聚焦 L2->L1 -> `07_paper_outline/insight.md` Insight 2
8. **IMAD.WIDE 链覆盖率 88-99%** -- 56 个实现的 1188 条 IMA 链中 88.4% 为 IMAD.WIDE -> `insight.md` Insight 7
9. **SOTA stride-INTRA (+ IMA gating) geomean +2.00%** -- BFS +3.92%, SSSP +4.07%, CC +0.18%, SpMV -0.08% -> `sota_baseline/README.md`
10. **CAPS (CTA-Aware Prefetcher) SpMV +14.30%** -- stride prefetcher 中 SpMV 最优，但 IMA data coverage = 0% -> `sota_baseline/README.md`
11. **Stride 学习跨 CTA 污染修复** -- PT hit rate 29%->60%，accuracy +3pp -> `experiment_progress.md` S7f
12. **四类 IMA pattern 的 prefetchability 层级** -- Pattern I/II 可覆盖，III 部分，IV 不覆盖 -> `01_ima_characterization.md`
13. **节流收益与 baseline accuracy 负相关** -- acc < 55% 时 +0.37%~+3.47%，acc > 99% 时 ~0% -> `dse_throttle_control/README.md` §6.6

## GRASP ima_med 全量结果（108SM，完整运行）

| Workload | Baseline IPC | GRASP IPC | Speedup |
|----------|-------------|-----------|---------|
| BFS | 7.35 | 11.02 | **+49.8%** |
| SSSP | 9.56 | 13.76 | **+44.0%** |
| SpMV | 129.68 | 164.12 | **+26.6%** |
| BC | 10.83 | 13.36 | **+23.3%** |
| **Geomean** | | | **+35.5%** |

> 数据来源：`05_implementation/experiment_progress.md` S5b (2026-03-28)

## 4 类图 x 6 算法大规模评估（2026-04-03，sym=1 变体亮点）

| 数据集 | BFS | SSSP | BC | CC | SpMV | VC |
|--------|:---:|:----:|:--:|:--:|:----:|:--:|
| **cit-Patents** | +6.2% | +2.5% | +1.7% | -7.0% | 0.0% | +1.9% |
| **web-Google** | **+56.1%** | **+46.6%** | +10.9% | **+93.6%** | **+40.1%** | +0.8% |
| **flickr** | **+27.0%** | +19.9% | +21.8% | **+138.6%** | **+38.0%** | crash |
| **roadNet-CA** | +3.4% | +2.0% | +1.7% | -0.0% | -1.0% | crash |
| **soc-LJ1** | **+31.1%** | -- | -- | -- | +17.8% | -- |

> 完整数据（含 dir 变体、Timeliness、Coverage、Accuracy、source log）-> `06_evaluation_plan/experiment_results.md`
> PR 已移除（全场 -0.5%~0%，单次仿真 12-38h）。VC/flickr crash 因 MAXCOLOR=128。Ideal L1D 仅对 load 生效。

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
| `grasp_prefetcher.{h,cc}` | 顶层：config, PRB, IST, TC (tc_mode dispatch), stats, 主逻辑 |
| `grasp_chain_detector.{h,cc}` | CD：FIFO + tracked warp + LDG->IMAD.WIDE->LDG |
| `grasp_tables.{h,cc}` | CT + TT 查找/插入/淘汰/stride 学习 |
| `grasp_tracer.{h,cc}` | GRASP 事件追踪器（CSV 输出，含 DEMAND_CT_MISS/EVICT 事件） |
| `trace_driven.cc` | trace-driven warp exit 的 GRASP hook（与 shader.cc 对齐） |

Golden chain CSV：`05_implementation/ima_pair_table/golden/strict_selected_chain_instances.csv`

GRASP 仿真输出行：
- `GRASP_CONFIG:` -- 一次性参数 dump（仅 SM0）
- `GRASP_DEMAND SM*:` -- global reads/misses, throttle_suppressed
- `GRASP_IMA_DEMAND SM*:` -- IMA index/data 分项：reads/hits/hit_reserved/misses
- `GRASP_TIMELINESS SM*:` -- index/data timeliness%（= hits/(hits+hit_reserved)）
- `GRASP_EFFECT SM*:` -- legacy pf_useful/pf_useless/pf_late/accuracy%（仅供 debug）
- `GRASP_STORAGE SM*:` / `GRASP_RFAIL SM*:` -- 存储利用率 / reservation fail 分布
- `GRASP_L1MQ SM*:` -- miss_queue_peak / mshr_peak 跟踪
- `IMA_DEMAND:` / `IMA_TIMELINESS:` -- 全局汇总（baseline 和 GRASP 都有）

## Legacy 声明（新 session 请忽略）

| Legacy 项 | 被什么替代 | 说明 |
|-----------|-----------|------|
| `GRASP_EFFECT` 指标 | `GRASP_IMA_DEMAND` + `GRASP_TIMELINESS` | 不区分 IMA PC，粒度粗，仅供 debug |
| `-gpgpu_ima_prefetch_*` 参数 | `-grasp_enable` + `grasp_*` 参数 | 旧版 IMA prefetcher，已禁用 |
| `distance=1` 配置 | `distance=4` | distance=1 已证明无效 |
| experiment_progress S1-S4 | S5b（ima_med 全量） | 早期实验配置不可比 |
| `SM80_A100_*_infmq` 系列 GPU config | 仅限 7h 实验用 | MQ/MSHR 放大验证，**非生产配置** |
| `tc_mode=0` (thr=80) | `tc_mode=4` T40C200 | 旧 binary threshold 已被 cooldown timer 替代 |

## 源码导航（task -> required reading）

| 你要做什么 | 必须先读 |
|-----------|---------|
| 调 GRASP 整体行为/参数 | `grasp_prefetcher.{h,cc}` + `experiment_progress.md` 最新 section |
| 调 stride learning / distance | `grasp_tables.cc`（`update_stride()`）+ `grasp_ablation/README.md` |
| 调 chain detection / pattern | `grasp_chain_detector.cc`（`on_issue()`、`check_chain()`）|
| 调 throttle / cooldown 策略 | `grasp_prefetcher.cc`（`inject_prefetch()` tc_mode dispatch）+ `dse_throttle_control/README.md` |
| 分析 accuracy / coverage 问题 | `experiment_progress.md` S7h + S7g + `debug/README.md` |
| 改 IMA chain 定义 | `ima_pair_table/golden/*.csv`（改后必须重跑回归测试） |
| 改 SOTA baseline | `sota_baseline/README.md` + 对应 `baseline_*.cc` |
| 改实验基础设施 | `traceL1` 脚本 + `CLAUDE.md` "运行仿真" section |
| 写论文图表 | `07_paper_outline/plot_style/plot_util.py` + `CLAUDE.md` "绘图规范" |
| Debug GRASP miss root cause | `debug/README.md`（5 阶段 + structural miss 分类） |

## SOTA Baseline 状态

| Baseline | 状态 | 最佳结果 | 评估价值 |
|----------|------|---------|---------|
| **stride-INTRA** (+ IMA gating) | 完成 | geomean +2.00% | 主对照基线 |
| **stride-INTER** | 完成 | 0% (BFS/SSSP prefetch_issued=0) | Negative result |
| **Snake** | 完成 | BC +2.96%, SpMV +1.47% | Negative result |
| **Spare Register** | 部分完成 | SSSP +7.63% | IMA-aware 最强 baseline |
| **CAPS** | 完成 | **SpMV +14.30%**, 其余 <0.1% | CTA-aware stride |

## 实验基础设施

| 功能 | 说明 |
|------|------|
| **EXPERIMENT SUMMARY** | `traceL1` 仿真后自动写入 log 末尾，含 status/kernels/IPC |
| **Baseline Registry** | `06_evaluation_plan/baseline_registry.csv`，baseline 不重跑 |
| **回归测试** | `grasp_regression.sh check`（默认 --quick ~34min，--full ~44min） |
| **Golden Chain CSV** | `ima_pair_table/golden/strict_selected_chain_instances.csv`（105 chains, PR 删除后） |
| **输出规范** | `06_evaluation_plan/output_specification.md` |
| **实验结果** | `06_evaluation_plan/experiment_results.md`（唯一集中数据源） |
| **批量实验** | `run_batch_experiments.sh` / `run_ideal_l1d.sh` |
| **Debug 方法学** | `05_implementation/debug/README.md`（5 阶段 + structural miss 分类） |
| **DSE 参数** | `05_implementation/dse_ct_reset_policy.md`（speculative stride + throttle control） |
| **Throttle DSE** | `05_implementation/dse_throttle_control/`（README.md + extract_metrics.sh + 6 CSV） |
| **traceL1 --sim-args** | 直接传递额外仿真参数到 accel-sim（如 `-grasp_tc_mode 4`） |
| **L1 eviction trace** | `emit_evict` 追踪 eviction 事件 + `analyze_grasp_iterations_v2.py` 处理 EVICT |

## 目录详情

### 01_ima_characterization/
- **状态**: 核心分析完成
- **关键文件**: `sass_analysis/README.md`, `l1_miss_breakdown/analysis.md`
- **最近修改**: 2026-03-29

### 02_related_work/
- **状态**: 论文收集完成（CPU 8 + GPU 9），重组为 6 个子目录
- **关键文件**: `gpu_prefetcher_impl_provenance.md`
- **最近修改**: 2026-03-30

### 04_prefetcher_design/
- **状态**: 设计框架已定，时序证据持续回填
- **关键文件**: `analyze_grasp_iterations_v2.py`（新增 EVICT 事件处理）
- **最近修改**: 2026-03-28

### 05_implementation/
- **状态**: GRASP +35.5% + Throttle T40C200 + CT/CD bug fix + 5 SOTA baseline + debug 方法学
- **子目录**: `regression/`, `grasp_ablation/`, `sota_baseline/`, `ima_pair_table/`（含 `golden/`）, `grasp_real_diag/`, `chain_extraction/`, `debug/`, `grasp_metrics/`, **`dse_throttle_control/`**（完成: T40C200 推荐 + 6 CSV + extract_metrics.sh）
- **新增（2026-04-03）**: Throttle DSE 完成。tc_mode=4 Cooldown Timer 9-workload 验证通过。
- **最近修改**: 2026-04-03

### 06_evaluation_plan/
- **状态**: **4 类图 x 6 算法大规模评估** (PR 已移除, 38 workloads)
- **关键文件**: `benchmark_suite.md`, `experiment_results.md`（唯一集中数据源）, `experiment_timing.md`, `output_specification.md`
- **批量脚本**: `run_batch_experiments.sh`, `run_ideal_l1d.sh`
- **最近修改**: 2026-04-03

### 07_paper_outline/
- **状态**: **权威大纲已定稿** + abstract + insight 清单 + academic 绘图 + LaTeX 模板
- **关键文件**: **`paper_structure.md`**（§1-§7 完整大纲，基于 9 篇 CCF-A 论文结构分析）, `insight.md`（11 insights）, `introduction.md`, `abstract.md`
- **最近修改**: 2026-04-03

## 实现阻塞项

### 原始设计问题

| 编号 | 问题 | 状态 |
|------|------|------|
| P1 | trace-driven 模式无运行时数据值 | 已解决：`ima_pair_table` 方案 |
| P2 | per-warp FIFO 深度不足 | 已解决：共享 FIFO |
| P3-P5 | IMAD.WIDE 基地址/op_type/fill 路径 | 已解决：由 P1 消解或保存 SASS |
| P6 | data prefetch 多 lane coalescing | 需实现 |
| P7-P8 | Pending Buffer / Kernel launch hook | 已解决 |

### 首轮实验暴露的问题

| 编号 | 问题 | 状态 |
|------|------|------|
| E1 | distance=1 预取不及时 | 已修复：distance=4 |
| E2 | per-kernel reset 破坏多 kernel 训练 | 已修复：跨 kernel 持久化 |
| E3 | Throttle 80% 阈值过于粗暴 | **已修复：tc_mode=4 T40C200** |
| E4 | Stride 学习跨 CTA 污染 | 已修复：stride freeze + warp exit cleanup |
| E5 | CT kernel reset 指针比较 bug | 已修复：改用 kernel name 比较 |
| E6 | CD FIFO invalidation 不回收 m_count | 已修复：push 时扫描 invalid slot |
| **E7** | **L1 MQ/MSHR 容量不足？** | **已排除**：放大后无收益，不是瓶颈 |

### SpMV 特殊问题

| 问题 | 状态 |
|------|------|
| x16 展开使 4/5 chain 学不到 stride | 设计瓶颈 |
| MSHR 极度饱和 (3M RFAIL) | **T40C200 缓解**: useless -60.7%, IPC +3.47% |

## Insight 清单

从 `07_paper_outline/insight.md` 提取：

1. **IMAD.WIDE 零推断检测** -- GPU ISA 将 IMA 结构显式暴露
2. **L1/L2 命中率不对称** -- prefetch 聚焦 L2->L1
3. **IMA 占 L1 Miss 主体** -- 51%-84%
4. **PC 膨胀可归并** -- (base, scale) key 解决 30x 展开
5. **One-to-Many 索引复用** -- BC reverse 1->3
6. **训练一次全 SM 复用** -- CT/TT per-SM shared，64 倍分摊
7. **固定指令检测覆盖率** -- 88-99% IMAD.WIDE 链
8. **四类 Pattern Prefetchability** -- I/II 高, III 有限, IV 不覆盖
9. **Ideal L1D 天花板** -- 1.75x-3.04x
10. **写无效化保证正确性** -- false positive 清除
11. **Stride 学习跨 CTA 污染修复** -- PT hit rate 29%->60%

## GRASP 逐 Iteration 分析工具

| 文件 | 用途 |
|------|------|
| `04_prefetcher_design/tiny_case/grasp_verify/analyze_grasp_iterations.py` | 分析脚本（3 种输出格式） |
| `04_prefetcher_design/analyze_grasp_iterations_v2.py` | v2 增强版（BFS iteration 检测 + EVICT pc=NA 处理） |

## 待解决问题

- **Accuracy 过低（22.8% in inf-all）**: 资源放大无效，需算法层面减少无效预取
- **PT miss (~33K 不变)**: addr_map 覆盖不完整，MQ/MSHR 放大无法改善
- **SpMV x16 展开使 stride 学习失效**: 需设计层面解决
- **论文撰写（active）**: 大纲已定稿，下一步按 §3 Design -> §2 Background -> §5 Evaluation 优先级填充内容
- **Spare Register SpMV 实验待完成**
- **Speculative stride BC 退化 -8.6% 根因待查**
- **回归测试待跑**: Throttle DSE 代码改动未提交
