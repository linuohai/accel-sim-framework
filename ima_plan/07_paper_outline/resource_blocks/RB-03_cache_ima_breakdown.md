# RB-03: L1/L2 Cache Miss 与 IMA Miss 分析

> 创建: 2026-04-05
> 最近更新: 2026-04-05

## 核心想法

L1 cache miss rate 远高于 L2 miss rate，说明数据在 L2 中但不在 L1 → L1 prefetching 有机会。进一步分析表明 IMA 指令贡献了 L1 misses 的绝大部分（60-94%），且 data load misses 远多于 index load misses。

## 要素

### 1. L1 vs L2 Miss Rate 对比

跨 6 个算法 × 多数据集（37 个组合），L1 miss rate 中位数在 39-66%，而 L2 miss rate 中位数在 10-21%。

关键对比：
- L1 miss rate **高** → warp stall 的主要原因
- L2 hit rate **高** (79-90%) → 数据确实在 L2 中
- 差距 = L1 prefetching 的**机会窗口**

### 2. L1 Miss 中的 IMA 占比

在总 L1 misses 中：
- **IMA Data Miss** 占比最大（40-78%），是主要性能瓶颈
- **IMA Index Miss** 次之（15-29%）
- **Other Miss** 最小（6-40%）

### 3. 跨数据集一致性

每个算法的数据为多个图数据集的中位数（BFS/SSSP/BC 各 8-10 个数据集，CC 4 个，SpMV 5 个，VC 2 个；总计 37 组实验）。各数据集包括 cit-Patents、web-Google、flickr、roadNet-CA、soc-LiveJournal 的 dir/sym 变体。上述结论在不同数据集上一致成立：L1 miss rate 中位数 39-58%，L2 hit rate 中位数 70-89%。

## 已完成的图

| 图 | 文件 | 脚本 |
|----|------|------|
| Fig A: L1/L2 Cache Miss + IMA Breakdown | `figures/rb03/rb03_cache_ima_breakdown.svg` | `scripts/plot_cache_ima_breakdown.py` |

## 候选位置

| 论文章节 | 使用方式 |
|---------|---------|
| **§2 Motivation**（主选） | 完整图表，论证 L1 prefetching 的必要性 |
| **§1 Introduction**（辅选） | 引用数字：L1 miss 48-66%, L2 hit 79-92%, IMA 占 L1 miss 的 60-94% |

---

## 绘图数据接口说明

### Fig A: Cache Miss + IMA Breakdown (`plot_cache_ima_breakdown.py`)

**数据方式**：读取 CSV 文件。

**数据位置**：`resource_blocks/data/cache_ima_breakdown.csv`

**CSV 格式**：
```csv
algorithm,dataset,l1_miss_rate,l2_miss_rate,l1_total_misses,ima_index_misses,ima_data_misses,log_file
bfs,web_sym,0.6559,0.1053,13856104,3953038,8982421,bfs_web_sym_baseline.log
```

**字段含义**：
- `algorithm`: 算法名 (bfs, sssp, bc, cc, spmv, vc)
- `dataset`: 数据集 (web_sym, cit_sym, flickr_dir, etc.)
- `l1_miss_rate`: L1D 总体 miss rate (0-1)
- `l2_miss_rate`: L2 总体 miss rate (0-1)
- `l1_total_misses`: L1D total miss 次数
- `ima_index_misses`: IMA index load 的 miss 次数
- `ima_data_misses`: IMA data load 的 miss 次数
- `log_file`: 数据来源日志

**如何新增数据**：
1. 跑 baseline 实验（`./traceL1 {trace_key} {log_name}`），确保日志含 `IMA_DEMAND:` 输出
2. 运行 `python3 extract_cache_ima_data.py`（自动扫描新日志）
3. 运行 `python3 plot_cache_ima_breakdown.py`

---

### 数据生成流水线

```bash
# 1. 提取数据 (扫描 result/log/ 中所有 baseline 日志)
python3 ima_plan/07_paper_outline/resource_blocks/scripts/extract_cache_ima_data.py

# 2. 绘图
python3 ima_plan/07_paper_outline/resource_blocks/scripts/plot_cache_ima_breakdown.py
```

## 通用规范

与 RB-01/02 相同（`plot_util.apply_style()`、SVG 输出、`save_fig()`）。

## 依赖与约束

| 项目 | 状态 |
|------|------|
| Baseline 日志 (6 算法 × 多数据集) | **已有** (37 组合) |
| IMA_DEMAND 输出 | **已有** (含在 baseline 日志中) |
| VC road_sym 日志 | **缺失**（仅 2 个数据集） |
