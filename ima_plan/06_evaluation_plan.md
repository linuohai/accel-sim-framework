# 06 — 评估方案

> 对应文件夹：`06_evaluation_plan/`（存放评估脚本、结果数据、图表等）
>
> 状态：待开始（依赖 Phase 4 实现完成）

---

## 目标

设计一套完整的评估方案，证明 prefetcher 的有效性、开销合理性、并与已有方案对比。评估结果直接对应论文 Evaluation section。

---

## 评估维度

### 1. 性能提升（Primary Metric）

| 指标 | 定义 | 展示方式 |
|------|------|---------|
| IPC Speedup | `IPC_prefetch / IPC_baseline` | Bar chart, grouped by workload |
| Normalized to Ideal | `(IPC_pref - IPC_base) / (IPC_ideal - IPC_base)` | 展示接近天花板的百分比 |
| Geomean Speedup | 所有 workload 的几何平均 | 汇总指标 |

### 2. Cache 行为改善

| 指标 | 定义 | 展示方式 |
|------|------|---------|
| L1 Miss Rate Reduction | `(miss_base - miss_pref) / miss_base` | Per-workload bar chart |
| L2 Miss Rate Change | 同上 | 监控 prefetch 是否增加 L2 压力 |
| Prefetch Accuracy | `useful_prefetch / total_prefetch` | 衡量预取质量 |
| Prefetch Coverage | `useful_prefetch / total_demand_miss_base` | 覆盖了多少原有 miss |
| Prefetch Timeliness | late prefetch 占比 | 预取是否及时 |

### 3. Stall 缓解

| 指标 | 来源 | 展示方式 |
|------|------|---------|
| MEM_WAIT Stall Reduction | issue trace | 核心指标：内存等待是否减少 |
| Overall Stall Breakdown 变化 | issue trace | Stacked bar chart |
| PC-level Stall 变化 | stall_reason_pc_stats | 验证 IMA 相关 PC 的 stall 改善 |

### 4. 带宽开销

| 指标 | 来源 | 展示方式 |
|------|------|---------|
| L1→L2 带宽增加 | L2 trace / ICNT stats | 监控额外流量 |
| L2→HBM 带宽增加 | HBM bandwidth trace | 关键：是否浪费 HBM 带宽 |
| Bandwidth Overhead | `(BW_pref - BW_base) / BW_base` | 额外带宽占比 |

### 5. 硬件开销

| 指标 | 方法 | 说明 |
|------|------|------|
| 存储开销 | 计算 table/queue 大小 | 对比 L1D 面积 |
| 逻辑复杂度 | 定性描述 | 比较器/加法器数量 |
| 功耗估算 | CACTI 或类似工具（可选） | 面积→功耗换算 |

---

## Workload 矩阵

详见 [`06_evaluation_plan/benchmark_suite.md`](06_evaluation_plan/benchmark_suite.md)，包含完整测例矩阵（7 算法 × 3 IMA 强度级 = 20 trace keys）和各实验类型的覆盖要求。

### 算法一览

| 算法 | 来源 | 入选理由 |
|------|------|---------|
| BFS | Gardenia | 经典图遍历，IMA 模式清晰 |
| SSSP | Gardenia | 加权图遍历，ideal L1D 提升最高（2.46×） |
| BC | Gardenia | 反向传播阶段 1→多表查找，ideal L1D 提升 3.04× |
| CC | Gardenia | 无源点依赖，IMA miss share 83.6% |
| SpMV | Gardenia | CSR 格式间接访存，IMA miss share 66.9% |
| PR (PageRank) | Gardenia | pull 语义补充 push 类算法；SASS chain 100% 符合 |
| VC (Vertex Coloring) | Gardenia | 迭代收敛型；SASS chain 97% 符合，证明通用性 |

---

## 对比方案（Baselines）

| 方案 | 说明 | 在 GPGPU-Sim 中如何实现 |
|------|------|------------------------|
| No Prefetch (Baseline) | 默认配置 | 现有 baseline |
| Ideal L1D | 完美 L1D，性能上界 | 已实现（`--ideal-l1d`） |
| Next-Line Prefetch | 最简单的 prefetch | 需实现（简单 stride=1） |
| Stride Prefetch | 经典 stride detection | 需实现（RPT-based） |
| 本方案（IMA Prefetch） | Phase 3 设计 | Phase 4 实现 |
| 本方案 + 变体 | 消融实验 | 关闭/开启不同子模块 |

---

## 消融实验（Ablation Study）

为了展示设计各组件的贡献，需进行消融实验：

- [ ] 关闭 confidence/throttling → 观察 pollution 影响
- [ ] 缩小 pattern table → 观察 coverage 下降
- [ ] 只做 L1 prefetch vs 只做 L2 prefetch → 比较效果
- [ ] 其他方案特定的消融点（待设计确定）

---

## 敏感性分析（Sensitivity Study）

| 参数 | 扫描范围 | 目的 |
|------|---------|------|
| Prefetch Queue Size | 4, 8, 16, 32 | 最优配置点 |
| Target Table (TT) Size | 16, 32, 64, 128 entries | 面积-性能 trade-off |
| Prefetch Degree | 1, 2, 4 | 激进度 |
| L1D Size | 32KB, 64KB, 128KB | 与 cache size 的交互 |
| Warp Count / CTA | 不同并发度 | 与 latency hiding 的交互 |

---

## 论文图表规划

| Figure | 内容 | 类型 |
|--------|------|------|
| Fig.X | IPC speedup across workloads（本方案 vs baselines） | Grouped bar chart |
| Fig.X | Normalized to ideal L1D | Bar chart |
| Fig.X | L1 miss rate reduction | Bar chart |
| Fig.X | Prefetch accuracy & coverage | Dual-axis chart |
| Fig.X | Stall breakdown 变化 | Stacked bar chart |
| Fig.X | Bandwidth overhead | Bar chart |
| Fig.X | Ablation study | Bar chart |
| Fig.X | Sensitivity to table size / queue size | Line chart |
| Tab.X | Hardware overhead summary | Table |

---

## 预期产出

1. **评估数据全集**（存放在 `06_evaluation_plan/data/`）
2. **论文级图表**（存放在 `06_evaluation_plan/figures/`）
3. **结论摘要**：可直接用于论文 evaluation section 的文字

---

## 文件夹内容规划

```
06_evaluation_plan/
├── scripts/                # 批量实验脚本、数据处理脚本、绘图脚本
├── data/                   # 实验结果数据（CSV/JSON）
├── figures/                # 最终论文图表
├── raw_logs/               # 关键实验的原始日志（或指向 result/log/ 的索引）
└── analysis.md             # 结果分析与解读
```

---

## 关键问题（待讨论）

1. 是否需要测 **多 GPU 配置**（A100 / V100 / RTX3070）展示通用性？
2. 是否需要做 **execution time simulation** 还是 IPC 就够了？
3. 与 **software prefetch**（CUDA __prefetch）的对比是否必要？
4. 投稿目标是 ISCA/MICRO/HPCA 中的哪个？不同会议对评估深度要求不同
