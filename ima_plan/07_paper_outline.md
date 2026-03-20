# 07 — 论文大纲

> 对应文件夹：`07_paper_outline/`（存放论文草稿、图表素材、参考文献列表等）
>
> 状态：待开始（随研究推进逐步完善）

---

## 目标

维护一份持续更新的论文大纲，随着研究推进逐步填充内容。最终目标：投稿体系结构顶会（ISCA / MICRO / HPCA）或顶刊。

---

## 论文标题（暂定）

> *待定* — 在 prefetcher 方案明确后确定
>
> 参考格式：`[方案名]: [核心创新] for [目标问题] on [平台]`
>
> 示例：`"IMA-Fetch: A GPU Hardware Prefetcher for Indirect Memory Access in Graph Workloads"`

---

## 论文结构

### 1. Abstract（~150 words）
- 问题：GPU graph workloads suffer from IMA → cache miss → stall
- 方法：我们提出 XXX prefetcher，利用 YYY 识别 IMA 模式并预取
- 结果：在 N 个 graph workloads 上平均提升 X% IPC，达到 ideal 天花板的 Y%

### 2. Introduction（~1.5 pages）
- Graph 负载在 GPU 上的重要性（AI/ML graph, social network, scientific computing）
- IMA 问题的本质：data-dependent address → 传统 prefetch 失效
- 现有方案的局限（CPU prefetcher 不适配 GPU / GPU prefetch 未关注 IMA）
- **Contribution 列表**：
  1. IMA 特征化与分类体系（Phase 1 成果）
  2. 针对 GPU IMA 的 prefetcher 设计（Phase 3 成果）
  3. 全面评估，展示显著性能提升（Phase 4 成果）

### 3. Background & Motivation（~2 pages）

#### 3.1 GPU Memory Hierarchy
- L1D / L2 / HBM 结构，coalescing，MSHR

#### 3.2 IMA in Graph Workloads
- CSR 格式 + 间接访存模式
- 代码示例（BFS / SpMV / B+Tree 各一）

#### 3.3 Motivation: Quantifying the IMA Problem
- **来自 Phase 2 的数据**：Baseline vs Ideal L1D IPC 对比
- Stall breakdown 分析：MEM_WAIT 占比
- L1/L2 miss rate 数据
- **关键论点**：IMA 导致的性能损失显著，且有很大优化空间（ideal 和 baseline 差距大）

#### 3.4 Why Existing Prefetchers Fail
- Next-line/stride 对 IMA 无效（无固定 stride）
- CPU IMA prefetcher 在 GPU 上的问题（地址流交织、硬件预算）

### 4. IMA Characterization（~1.5 pages）
- **来自 Phase 1 的成果**
- Level 1-3 分类体系
- 各 workload 的 IMA 行为量化
- 关键 observation 总结

### 5. Design（~3 pages）
- **来自 Phase 3 的成果**
- 5.1 Overview：整体架构图
- 5.2 核心机制 1：XXX
- 5.3 核心机制 2：YYY
- 5.4 Prefetch Accuracy Control（throttling / confidence）
- 5.5 Hardware Cost Analysis

### 6. Implementation（~0.5 page）
- 在 GPGPU-Sim 中的实现说明
- 配置参数

### 7. Evaluation（~3 pages）
- **来自 Phase 4 的成果**
- 7.1 Experimental Setup（配置、workloads、baselines）
- 7.2 Performance Results（IPC speedup）
- 7.3 Cache Behavior Analysis（miss rate, prefetch accuracy/coverage）
- 7.4 Stall Reduction Analysis
- 7.5 Bandwidth Overhead
- 7.6 Ablation Study
- 7.7 Sensitivity Analysis
- 7.8 Hardware Overhead Discussion

### 8. Related Work（~1 page）
- **来自 Phase 2 调研成果**
- CPU irregular prefetcher
- GPU cache / prefetch 优化
- Graph workload optimization

### 9. Conclusion（~0.5 page）
- 总结贡献
- Future work 方向

---

## 投稿目标分析（待讨论）

| 会议 | 截稿日期（通常） | 页数限制 | 特点 |
|------|----------------|---------|------|
| ISCA | ~11月 | 11 pages | 最偏硬件/微架构 |
| MICRO | ~4月 | 11 pages | 微架构 + 编译器 |
| HPCA | ~7月 | 12 pages | 高性能计算导向 |
| ASPLOS | ~11月 | 12 pages | 系统+架构交叉 |

---

## 文件夹内容规划

```
07_paper_outline/
├── drafts/                 # 论文各 section 的草稿
├── figures/                # 论文图表源文件
├── references/             # 参考文献 BibTeX
└── submission_log.md       # 投稿记录（目标、截止日期、反馈等）
```

---

## 关键问题（待讨论）

1. 论文的核心 novelty claim 是什么？（待 Phase 2/3 后明确）
2. 目标投稿会议？这决定写作方向和时间安排
3. 是否需要 artifact evaluation？（ISCA/MICRO 鼓励，需要准备可重复实验环境）
