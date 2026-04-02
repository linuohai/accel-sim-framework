# SOTA Baseline 复现工作

> 本目录集中管理 GRASP 论文 evaluation 所需的 SOTA baseline 实现文档。

## 阅读顺序

1. `sota_impl_spec.md` — baseline 实现规格（INTRA/INTER/Snake/Spare Register 的机制、参数、hook 位置）
2. `sota_resume_design.md` — 从旧会话恢复的关键事实与设计决策
3. `sota_resume_plan.md` — 分步实现计划（worktree 隔离、文件清单、验证步骤）
4. `sota_stride_progress_2026-03-24.md` — 当前 stride baseline 的实验进展与阶段性结论

## 当前状态

- **`baseline-intra` + IMA data PC blacklist gating**：完整可用的 SOTA 对照基线
  - BFS +3.92%, SSSP +4.07%, CC +0.18%, SpMV -0.08%
  - 500k geomean **+2.00%**（从无 gating 的 +1.46% 提升）
  - accuracy: BFS/SSSP 99.6%, CC/SpMV ~20%（非 IMA load）
- **`baseline-inter`**：在 IMA workload 上完全无效（BFS/SSSP prefetch_issued=0），作为 negative result 有 evaluation 价值
- **实现位置**：worktree `worktrees/sota_stride`, 分支 `exp/sota_stride`
- **`baseline-snake`（已修复）**：已实现并修复 training/prediction 边界 bug
  - BFS +3.13%, SSSP +3.82%, CC -3.40%, SpMV -3.10%
  - 在所有 IMA workload 上不如 stride-INTRA，作为 negative result 有 evaluation 价值
- **`baseline-spare-reg`（已实现）**：两步预取近似（stride index + pair table data）
  - SSSP **+7.63%**（accuracy 39%，所有 baseline 中最高）
  - BFS 0%（pair table 匹配率低），CC 0%（无 chain CSV）
  - SpMV 待完成
- **`baseline-caps`（已实现）**：CTA-Aware Prefetcher (Koo et al. IPDPS'18) — CAP + PAS + DIST persistence
  - **源码**: `baseline_caps.{h,cc}`, PAS 在 `shader.cc`/`shader.h`
  - Fermi-like 验证 (hotspot): **+1.6% IPC**（baseline 613.58 → 623.65）
  - A100 结果见下方 §Snake/CAPS 图负载评估表

### Snake / CAPS 图负载评估结果（ima_small, A100 108SM, v3 probe-fix）

> 日志：`worktrees/sota_stride/result/log/{bfs,sssp,spmv,bc}_{np,snake,caps}_v3.log`

#### IPC Speedup

| Workload | NP IPC | Snake IPC | Snake % | CAPS IPC | CAPS % |
|----------|--------|-----------|---------|----------|--------|
| BFS | 23.5588 | 23.6000 | **+0.17%** | 23.5689 | +0.04% |
| SSSP | 28.8141 | 28.9289 | **+0.40%** | 28.7802 | -0.12% |
| SpMV | 129.6846 | 131.5913 | **+1.47%** | 148.2326 | **+14.30%** |
| BC | 37.6489 | 38.7625 | **+2.96%** | 37.6802 | +0.08% |

#### Prefetcher Accuracy (useful/issued)

| Workload | Snake | CAPS |
|----------|-------|------|
| BFS | 95.0% | 0.1% |
| SSSP | 94.2% | 0.0% |
| SpMV | 70.3% | 21.3% |
| BC | 52.0% | 0.0% |

#### IMA Data Timeliness (`data_hits/(data_hits+data_hit_reserved)`)

| Workload | NP | Snake | CAPS |
|----------|-----|-------|------|
| BFS | 17.50% | 17.71% | 16.06% |
| SSSP | 40.75% | 40.84% | 39.99% |
| SpMV | 85.45% | 85.34% | 82.77% |
| BC | 83.39% | 83.18% | 83.13% |

#### IMA Data Coverage (`(NP_data_misses - PF_data_misses) / NP_data_misses`)

| Workload | Snake | CAPS |
|----------|-------|------|
| BFS | -0.002% | -0.016% |
| SSSP | -0.003% | -0.050% |
| SpMV | +0.032% | -0.307% |
| BC | -0.010% | -0.093% |

> **结论**: Snake/CAPS 主要作用于 index load（stride prefetch），对 IMA data load 几乎无影响（coverage ≈ 0%）。IPC 提升来自 index load pipeline 效率改善，而非 data miss 消除。Data timeliness 在 NP/Snake/CAPS 间差异 <2%，说明这些 prefetcher 不改变 data load 的 cache 状态。

### 关键改动（blacklist gating）

1. `trace_driven.cc`: baseline 模式加载 chain CSV（`build_ima_pair_tables` 条件扩展）
2. `shader.h` + `trace_driven.{h,cc}`: 新增 `is_ima_data_pc()` 接口
3. `shader.cc`: baseline hook 中跳过 IMA data PC 的训练和预取
