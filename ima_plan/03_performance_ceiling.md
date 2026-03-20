# 03 — 性能天花板与动机背景（Ideal L1D + L1/L2 不对称）

> 对应文件夹：`03_performance_ceiling/`（存放 ideal L1D 上界、背景图表、动机分析等）
>
> 状态：**部分完成**（ima_high 的 ideal L1D 动机数据已具备；baseline L1 miss 分类统计见 `01_ima_characterization/l1_miss_breakdown/`）

---

## 目标

本页用于回答两个 motivation 问题：

1. **为什么这件事值得做？** —— ideal L1D 的上界有多高
2. **为什么优先盯 L1 而不是 L2/HBM？** —— L1/L2 hit-rate 的不对称意味着主要瓶颈在 L1→L2

对所有 IMA workload 运行 **baseline vs ideal L1D** 对比实验，量化 prefetcher 的理论最大收益。这一步的核心价值：

1. **筛选高价值 workload**：如果 ideal L1D 提升不足 5%，则该 workload 不适合作为 prefetch 动机
2. **为论文 Motivation 提供数据**：展示"IMA 造成的性能损失有多大"
3. **为 Phase 4 评估提供 upper bound**：prefetcher 的实际收益应在 0% 到 ideal 提升之间

## 与 baseline L1 miss 分类统计的分工

本页负责 **动机与背景**，回答“值不值得做”和“该把火力放在哪一级 cache”。

与之配套的 **baseline miss 归因结果** 放在：

- `ima_plan/01_ima_characterization/l1_miss_breakdown/analysis.md`
- `ima_plan/01_ima_characterization/l1_miss_breakdown/data/per_workload_class_summary.csv`
- `ima_plan/01_ima_characterization/l1_miss_breakdown/figures/ima_high_baseline_l1_miss_share.svg`

该分析现在只统计 **主 kernel 的真实 load 指令**，并把其中“地址依赖前序 load 返回值”的访问统一归为 `ima`。对应的 covered miss_share 为：

| Workload | IMA miss_share | covered miss ratio |
|----------|----------------|--------------------|
| bfs_ima_high | **99.1%** | 53.6% |
| sssp_ima_high | **51.1%** | 100.0% |
| bc_ima_high | **70.5%** | 92.2% |
| cc_ima_high | **83.6%** | 100.0% |
| spmv_ima_high | **66.9%** | 100.0% |

因此，本页的 ideal L1D 上界和下文的 L1/L2 hit-rate 差异，不再只是“整体 cache 很差”的背景，而是和 **主 kernel 中哪些真实 load 在制造 miss** 对应起来了。

---

## 实验矩阵

### Workload 列表

| # | trace_key | 算法 | 图规模 | IMA 强度 |
|---|-----------|------|-------|---------|
| 1 | `bfs_ima_high` | BFS | cit-Patents | High |
| 2 | `bfs_ima_med` | BFS | web-Google (src=1) | Medium |
| 3 | `bfs_ima_small` | BFS | web-Google (src=0) | Small |
| 4 | `spmv_ima_high` | SpMV | — | High |
| 5 | `spmv_ima_small` | SpMV | — | Small |
| 6 | `sssp_ima_high` | SSSP | — | High |
| 7 | `sssp_ima_med` | SSSP | — | Medium |
| 8 | `sssp_ima_small` | SSSP | — | Small |
| 9 | `bc_ima_high` | BC | — | High |
| 10 | `bc_ima_med` | BC | — | Medium |
| 11 | `cc_ima_high` | CC | — | High |
| 12 | `cc_ima_med` | CC | — | Medium |
| 13 | `tc_ima_high` | TC | — | High |
| 14 | `tc_ima_low` | TC | — | Low |

### 每个 workload 需跑两组

| 配置 | 命令示例 |
|------|---------|
| Baseline | `./traceL1 bfs_ima_high bfs_ima_high_base` |
| Ideal L1D | `./traceL1 --ideal-l1d bfs_ima_high bfs_ima_high_ideal` |

### 收集指标

| 指标 | 来源 | 说明 |
|------|------|------|
| IPC | `result/log/*.log` | 主要性能指标 |
| L1 miss rate | L1 trace 或 gpgpusim stats | IMA 导致的 miss 占比 |
| L2 miss rate | L2 trace 或 gpgpusim stats | 是否溢出到 HBM |
| Stall breakdown | issue trace | MEM_WAIT / WAIT_LDGSTS 等占比变化 |
| Cycle count | log | 绝对执行时间 |

---

## 实验步骤

### Step 1：Baseline 全量实验
```bash
# 建议并行跑，每个指定唯一 log_name
./traceL1 bfs_ima_high    bfs_ima_high_base
./traceL1 spmv_ima_high   spmv_ima_high_base
# ... 其余同理
```

### Step 2：Ideal L1D 全量实验
```bash
./traceL1 --ideal-l1d bfs_ima_high    bfs_ima_high_ideal
./traceL1 --ideal-l1d spmv_ima_high   spmv_ima_high_ideal
# ... 其余同理
```

### Step 3：数据提取与汇总
- [ ] 编写脚本从 log 中提取 IPC / cycle / miss rate
- [ ] 汇总到一张对比表
- [ ] 绘制 bar chart：baseline IPC vs ideal IPC（grouped by workload）

### Step 4：分析与筛选
- [ ] 标记 IPC 提升 > 10% 的 workload（重点关注）
- [ ] 标记 IPC 提升 < 5% 的 workload（可能不适合 prefetch 动机）
- [ ] 对重点 workload 进一步分析 stall breakdown 变化

---

## 已有经验参考

从 `analyze/attention_degradation/findings.md` 已知：
- Compute-bound workload（如 flash attention）从 ideal L1D 获益极小甚至为负
- 读写不对称（write-through）可能导致 barrier 堆积
- **Graph workload 预期与 attention 不同**：它们通常是 memory-bound，ideal L1D 应有显著提升

---

## 预期产出

1. **全 workload Baseline vs Ideal L1D 对比表**
2. **"高价值 workload" 列表**（IPC 提升显著的）
3. **Stall 变化分析**（对重点 workload）
4. 论文 Motivation section 的核心数据

---

## 文件夹内容规划

```
03_performance_ceiling/
├── scripts/                # 批量实验脚本、数据提取脚本
├── data/                   # 汇总数据（CSV / JSON）
├── figures/                # 对比图表
├── logs/                   # 关键实验的 log 摘要（非完整 log，完整 log 在 result/log/）
└── analysis.md             # 结果分析笔记
```

---

## 已有实验结果（ima_high 工作负载）

> 以下数据来自已完成的 baseline vs ideal L1D 实验，配置为 SM80_A100。

### IPC 对比（Baseline vs Ideal L1D）

| Workload | Baseline IPC | Ideal L1D IPC | Speedup | 提升百分比 |
|----------|-------------|---------------|---------|-----------|
| bfs_ima_high | 102.34 | 178.80 | **1.75×** | +74.7% |
| sssp_ima_high | 90.43 | 222.78 | **2.46×** | +146.3% |
| bc_ima_high | 104.04 | 315.89 | **3.04×** | +203.6% |
| cc_ima_high | 426.72 | 948.09 | **2.22×** | +122.2% |
| spmv_ima_high | 373.98 | 865.07 | **2.31×** | +131.3% |

**结论**：所有 ima_high 工作负载 IPC 提升均超过 70%，加速比 1.75×–3.04×，远超 10% 的筛选阈值。IMA 导致的 L1 cache miss 是这些图负载的首要性能瓶颈。

数据来源：`result/log/{workload}.log` 和 `result/log/{workload}_ideal_l1d.log` 中的 `gpu_tot_ipc` 统计。

### L1 / L2 命中率对比

| Workload | L1 Miss Rate | L1 Hit Rate | L2 Miss Rate | L2 Hit Rate |
|----------|-------------|-------------|-------------|-------------|
| bfs_ima_high | 77.22% | 22.78% | 21.89% | **78.11%** |
| sssp_ima_high | 76.66% | 23.34% | 25.87% | **74.13%** |
| bc_ima_high | 70.25% | 29.75% | 33.84% | **66.16%** |

**关键发现**：

1. **L1 命中率极低（22–30%）**：IMA 的地址分散度远超 L1D 容量（32–128 KB），导致大量 capacity/conflict miss。
2. **L2 命中率较高（66–78%）**：从更大的地址空间看，IMA 访问的数据（如 `dists[]`、`dist[]`、`comp[]`）仍有宏观空间局部性，L2 cache（通常数 MB）能承载绝大部分工作集。
3. **推论——Prefetcher 应聚焦 L1**：瓶颈在 L1→L2 的 miss，而非 L2→HBM 的 miss。Prefetcher 的目标应是将数据从 L2 提前填充到 L1，而非从 HBM 预取到 L2。
4. **对问题 1 的初步回答**：因为 L2 hit rate 已经很高，ideal L2 实验的额外收益预期很小——L1 miss 是主要瓶颈。

数据来源：`result/log/{workload}.log` 中的 `L1D_total_cache_miss_rate` 和 `L2_total_cache_miss_rate`；可视化参考 `result/L1cache_trace/plot/` 和 `result/L2cache_trace/plot/`。

---

## 关键问题（待讨论）

1. ~~是否需要同时测 **ideal L2**（perfect L2 → 0 HBM latency）？~~ → 初步判断：L2 hit rate 已较高（66–78%），ideal L2 的增量收益有限。但仍可作为补充实验以量化 L2 miss 的影响。
2. 是否需要测 **不同 GPU 配置**（如 QV100 vs A100）来展示通用性？
3. 对于 IPC 提升为负的 workload（如 attention 那样），是否需要在论文中解释？
