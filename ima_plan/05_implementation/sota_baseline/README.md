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

### 关键改动（blacklist gating）

1. `trace_driven.cc`: baseline 模式加载 chain CSV（`build_ima_pair_tables` 条件扩展）
2. `shader.h` + `trace_driven.{h,cc}`: 新增 `is_ima_data_pc()` 接口
3. `shader.cc`: baseline hook 中跳过 IMA data PC 的训练和预取
