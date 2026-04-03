# Benchmark Suite IMA 可预取性分析

> 基于 `ima_prefetchability_analysis.md` 的四层框架，对 benchmark_suite.md 定义的 6 个算法逐一分析
>
> 创建日期：2026-03-25
> 最近更新: 2026-04-03

---

## 总览

| 算法 | Chain CSV | 层次 1 | 层次 2 | 层次 3 | 层次 4 | 预测可利用度 |
|------|:---------:|:------:|:------:|:------:|:------:|:----------:|
| BFS | 7 chains | ✅ | ⚠️ 窗口依赖 | ✅ 100% | ❌ MSHR 饱和 | 中（需长窗口） |
| SSSP | 7 chains | ✅ | ✅ 24.6% | ✅ 100% | ✅ 39% acc | **高** |
| BC | 19 chains | ✅ | 🔲 待测 | 🔲 待测 | 🔲 待测 | **预期高** |
| CC | **0 chains** | ❌ | ❌ 0% | — | — | **无** |
| SpMV | 29 chains | ✅ | ✅ 高 | ⚠️ | ❌ acc 0.001% | **极低** |
| VC | **0 chains** | ❌ | 🔲 待测 | — | — | **待确认** |

✅ 有利 / ⚠️ 有条件 / ❌ 不利 / 🔲 待测

---

## 逐算法分析

### 1. BFS (`bfs_ima_high/med/small`)

**层次 1 — 静态 chain**: 7 条 chain, 1 个 kernel (`bfs_kernel`), 6 个 index PC
- 模式: `row_ptr[node]` → IMAD → `col_idx[edge]` / `depths[neighbor]`
- 2 条共享同一 index PC 0xc0（worklist 索引 → 两个不同 data load）
- 5 条来自 CSR 邻居遍历的循环展开

**层次 2 — 运行时密度**: **高度窗口依赖**
- 500k cycle: seed_ratio = 1.2%（frontier 极小，初始 BFS 层）
- 2M cycle: seed_ratio = 62%（frontier 爆发后 IMA 主导）
- **结论**: BFS 的 IMA 密度不是常数，必须用足够长的窗口评估

**层次 3 — Pair table**: 命中率 100%。Chain CSV 完美覆盖。

**层次 4 — 瓶颈**: **MSHR 饱和** (rfail 86.3%)
- BFS 的 demand load 已经把 MSHR 占满
- Prefetch 请求被大量拒绝
- 2M 窗口: accuracy 0.89%, IPC -0.17%

**Prefetcher 建议**:
- Stride-INTRA (+3.92%) 最好——捕获非 IMA 的 frontier/worklist stride
- Spare Register 受限于 MSHR 争用——需要 spare register 存储或更智能的注入时机
- IMA miss share 99.1%——理论上有巨大的 prefetch 空间，但实际受 cache/MSHR 瓶颈

### 2. SSSP (`sssp_ima_high/med/small`)

**层次 1 — 静态 chain**: 7 条 chain, 1 个 kernel (`bellman_ford`), 6 个 index PC
- 与 BFS 结构类似（CSR 遍历），但 SSSP 多一个 weight 数组访问
- 单 kernel 内 relax 循环，不像 BFS 多 kernel 迭代

**层次 2 — 运行时密度**: **稳定** 24.6%
- 单 kernel 设计 → IMA 密度从一开始就稳定
- 不像 BFS 有窗口依赖问题

**层次 3 — Pair table**: 命中率 100%。

**层次 4 — 有效性**: **最佳**
- Spare Register: accuracy 39%, coverage 高, IPC +7.63%
- Stride-INTRA: accuracy 99.7%, IPC +4.07%
- IMA miss share 51.1%——IMA 和非 IMA miss 各占一半

**Prefetcher 建议**:
- Spare Register 效果最好（直接命中 IMA data load）
- SSSP 是展示 IMA prefetcher 价值的**最佳测例**
- 理论上 Spare Register + Stride-INTRA 互补可达更高收益

### 3. BC (`bc_ima_high/med/small`)

**层次 1 — 静态 chain**: **19 条 chain**（仅次于 SpMV），2 个 kernel
- `bc_forward`: 12 chains, 6 个 index PC（与 BFS 类似的 frontier 遍历）
- `bc_reverse`: 7 chains, 7 个 index PC（反向传播依赖值）
- IMA miss share 70.5%，ideal L1D 加速 3.04×（所有算法最高）

**层次 2-4 — 待测**: 无实验数据

**预测**:
- BC 的 `bc_forward` 结构类似 BFS（frontier-driven），预期类似窗口依赖
- BC 的 `bc_reverse` 是全图遍历，IMA 密度可能更稳定
- **19 条 chain + 3.04× ideal 加速 + 70.5% IMA miss share → 预期 Spare Register 有显著收益**
- 优先级：**应当尽早补充实验**

### 4. CC (`cc_ima_high/med/small`)

**层次 1 — 静态 chain**: **0 条 chain**

**根因分析**:
- CC 使用 Shiloach-Vishkin 算法，访问模式是 `component[component[v]]`（指针追踪）
- 这不是标准 CSR-IMA 模式（`A[B[i]]`），而是 `A[A[i]]`（同一数组递归）
- Chain CSV 的 strict exact_chain 检测要求 `LDG → IMAD.WIDE → LDG`，但 CC 的地址计算可能不经过 IMAD.WIDE

**层次 2-4**: IMA seed ratio = 0%。所有 IMA-based prefetcher 无效。
- Stride-INTRA (+0.18%): 微弱正效果，来自 component 数组的部分 stride 可预测性
- Snake (-3.40%): 大量低质量预取，cache pollution
- CC 的 IMA miss share 83.6% 但无法被当前 chain 检测器覆盖

**Prefetcher 建议**:
- 当前所有 baseline 基本无效
- 需要扩展 chain 检测器以识别 `A[A[i]]` 模式（pointer chasing 而非 indirect array access）
- 或者需要完全不同类型的 prefetcher（如 runahead execution）

### 5. SpMV (`spmv_ima_high/med`)

**层次 1 — 静态 chain**: **29 条 chain**（最多），1 个 kernel (`spmv_csr_scalar`)
- 全部来自同一源码行 `base.cu:22`（循环展开产生 29 个 LDG→IMAD→LDG 副本）
- 模式: `row_ptr[row]` → `col_idx[j]` → `x[col_idx[j]]`

**层次 2 — 运行时密度**: 高（每行多个 non-zero 元素 → 密集的 index+data load）

**层次 3 — Pair table**: 命中但**地址预测无效**

**层次 4 — 有效性**: **灾难性**
- Spare Register: 14.7M issued, 211 useful, accuracy 0.001%, IPC -1.82%
- Snake: accuracy 12.5%, IPC -3.10%
- Stride-INTRA: accuracy 18.4%, IPC -0.08%

**根因**: SpMV 的 `x[col_idx[j]]` 访问地址完全取决于稀疏矩阵结构：
- 不同行的 `col_idx` 指向完全不同的 `x[]` 位置
- 同一行内的连续 `col_idx` 也不连续（依赖矩阵非零分布）
- Prefetch 的 data 在被 demand 前就被 evict（cache 太小相对于 x[] 向量大小）

**Prefetcher 建议**:
- **所有 stride/IMA 方法均失败**——SpMV 是最难的测例
- IMA miss share 66.9%，但 data 地址不可预测
- 唯一可能有效的方法：增大 cache 或 reuse-aware scheduling

### 6. VC (`vc_ima_high/med/small`)

**层次 1 — 静态 chain**: **0 条 chain** in current CSV

**分析**:
- VC (Vertex Coloring) 的 chain 符合率 97%（benchmark_suite.md）
- Chain CSV 缺失是数据问题，非算法特性
- VC 的 CSR 遍历模式应产生 IMA chain

**预测**:
- 补充 chain CSV 后预期有 IMA chain
- 效果取决于 VC 的访问 regularity（比 BFS 更规则还是更不规则）
- 优先级：中

---

## 行动计划

### 立即可做（有数据）

| 算法 | 行动 | 优先级 |
|------|------|--------|
| BFS | 使用 2M+ 窗口重新评估所有 prefetcher | 高 |
| SSSP | 结果完整，无需额外工作 | — |
| SpMV | 结果完整（negative result），可用于论文 | — |
| CC | 结果完整（0% 因无 chain），可用于论文 | — |

### 需要补充数据

| 算法 | 缺失 | 行动 | 优先级 |
|------|------|------|--------|
| **BC** | 无实验数据 | 跑 Spare Reg + Stride-INTRA + Snake 500k suite | **最高** |
| **VC** | 无 chain CSV | 补充 SASS chain 分析 → 跑 baseline suite | 中 |
| **CC** | 无 chain CSV（非 CSR-IMA） | 扩展 chain 检测器识别 `A[A[i]]` 模式 | 低（可能不可行） |

### 预测汇总

| 算法 | 预期最佳 Prefetcher | 预期 IPC Uplift | 信心度 |
|------|---------------------|:---:|:---:|
| SSSP | Spare Register | +7.63% (实测) | 实测 |
| BFS | Stride-INTRA | +3.92% (实测) | 实测 |
| BC | Spare Register | +5-10% (预测) | 中（类似 BFS/SSSP 混合） |
| CC | 无 | ~0% | 实测 |
| SpMV | 无 | ~0% | 实测 |
| VC | Spare Register? | 待测 | 低 |
