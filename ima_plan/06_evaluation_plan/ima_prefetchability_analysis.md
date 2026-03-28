# IMA 可预取性分析框架

> 创建日期：2026-03-25
> 数据来源：chain CSV + Spare Register 运行时诊断 + baseline 实验日志

---

## 1. 四层分析方法

### 层次 1：静态 IMA Chain 分析
**问题**：代码中有多少 IMA pattern？

从 `tmp/strict_chains/strict_selected_chain_instances.csv` 统计 chain 数量和 PC。
Chain pattern: `LDG.E (index) → IMAD.WIDE → LDG.E (data)`。
chain count 反映种类数而非运行时频率（循环展开产生多条 chain）。

### 层次 2：运行时 IMA 密度
**问题**：IMA 活动占总 demand load 多大比重？

**核心指标**：`IMA_seed_ratio = seed_hits / total_loads`

关键发现：IMA seed ratio **高度依赖执行阶段**。
BFS: 500k→1.2%, 2M→62%。SSSP: 稳定在 24.6%。

### 层次 3：Pair Table 可利用度
**问题**：IMA pattern 能否被 prefetcher 利用？

**指标**：`pair_table_hit_rate = cand_hits / cand_lookups`

BFS/SSSP 均 100%——chain CSV 准确覆盖运行时 IMA pattern。

### 层次 4：预取有效性（瓶颈分析）

| 瓶颈类型 | 特征 | 示例 |
|---------|------|------|
| 检测不足 | seed_ratio 低 | CC (0%), BFS 短窗口 (1.2%) |
| 预测不准 | accuracy 低 | SpMV (accuracy 0.001%) |
| cache 容量不足 | accuracy 中等, rfail 高 | BFS 2M (accuracy 0.89%, rfail 86%) |
| 带宽争用 | rfail 高, IPC 反降 | SpMV Spare Reg (-1.82%) |

---

## 2. 各 Workload 实测数据

| Workload | Chains | IMA Seed Ratio | Pair Hit% | Best Prefetcher | 主要瓶颈 |
|----------|:---:|:---:|:---:|------|------|
| SSSP | 7 | 24.6% | 100% | Spare Reg (+7.63%) | 无明显瓶颈 |
| BFS | 7 | 1.2%→62% | 100% | Stride-INTRA (+3.92%) | MSHR 争用 (86% rfail) |
| SpMV | 29 | 高 | — | 无 (均 negative) | 预测不准 + 带宽争用 |
| CC | 0 | 0% | — | 无 | 检测不足（非 CSR-IMA） |
| BC | 19 | 待测 | 待测 | 待测 | 待测 |

### BFS 2M 聚合统计 (108 SM)

| 指标 | 值 |
|------|-----|
| Total loads | 9,279,139 |
| Seed hits | 5,775,211 (62.2%) |
| Data PF queued | 5,780,124 |
| PF issued | 1,210,430 |
| PF rfail | 1,044,724 (86.3%) |
| PF useful | 10,790 (accuracy 0.89%) |
| NP IPC / SR IPC | 16.81 / 16.79 (-0.17%) |

### 各 Prefetcher 对比（500k cycle）

| Workload | Stride-INTRA | Snake | Spare Register |
|----------|:---:|:---:|:---:|
| BFS | **+3.92%** | +3.13% | 0% |
| SSSP | +4.07% | +3.82% | **+7.63%** |
| CC | **+0.18%** | -3.40% | 0% |
| SpMV | **-0.08%** | -3.10% | -1.82% |

---

## 3. 新 Workload 评估流程

1. **提取 chain CSV** → chain count=0 则无 IMA pattern
2. **跑 Spare Reg 诊断** → `seed_hits/total_loads` 得 IMA seed ratio
   - <5%: stride-based 可能更好
   - 5-20%: Spare Register 可能有效
   - >20%: GRASP 有较大空间
3. **检查 pair table 命中率** → <80% 需补充 chain 提取
4. **评估瓶颈** → accuracy/rfail/coverage 定位限制因素

---

## 4. 对 GRASP 的启示

1. Stride-based 方法无法预测 IMA data load 地址（data-dependent）
2. Pair table 检测有效（100% hit），但 L1D 容量和 MSHR 是实际瓶颈
3. IMA 密度阶段依赖（BFS 1.2%→62%）— prefetcher 需适应动态变化
4. SpMV data 地址完全不可预测 — 需 value-based 预测
5. BFS 的 MSHR 已被 demand load 饱和（rfail 86%）— prefetcher 需要更智能的注入时机控制
