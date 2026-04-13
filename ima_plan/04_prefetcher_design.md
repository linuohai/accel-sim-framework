# 04 — GRASP: GPU IMA Prefetcher 设计方案

> **GRASP** — GPU Register-chain Aware Sector Prefetcher
>
> 论文标题：*GRASP: Grasping GPU Indirect Memory Patterns via ISA-Exposed Register-Chain Prefetching*
>
> 对应文件夹：`04_prefetcher_design/`（存放设计草图、算法伪代码、硬件预算估算等）
>
> 状态：**设计框架已定**（依赖 Phase 1 IMA 特征化 & Phase 2 调研完成）
>
> 前置文档：`01_ima_characterization.md`（IMA 模式分类与 SASS 分析）、`02_related_work.md`（CPU/GPU prefetcher 调研）、`03_performance_ceiling.md`（Ideal L1D 上界）

---

## 1. 设计定位

### 1.1 目标

设计 **GRASP**（GPU Register-chain Aware Sector Prefetcher），一个 GPU 硬件 IMA prefetcher，将间接访存（`A[B[i]]`）的数据从 L2 提前填充到 L1，在不显著增加硬件开销和带宽浪费的前提下，缩小与 ideal L1D 之间的性能差距。

### 1.2 量化目标

| 指标 | 目标 | 数据来源 |
|------|------|---------|
| 性能下界 | Baseline（无 prefetch） | `03_performance_ceiling.md` |
| 性能上界 | Ideal L1D（1.75×–3.04× speedup） | `03_performance_ceiling.md` |
| 预期收益 | 捕获上界的 30%–60% | 初步估计，需实验验证 |

### 1.3 预取层级

**L2 → L1**（而非 HBM → L2）。

依据：ima_high 工作负载 L1 miss rate 70–77%，但 L2 hit rate 66–78%。瓶颈在 L1→L2 的 miss，L2 已能承载绝大部分 IMA 工作集。这里的 `-gpgpu_l2_rop_latency 200` 与 `-dram_latency 190` 仅是 simulator config；真正用于预取器时序推导的参考值，以 §2.5 中 `small_1sm_cta5 / lrr` 代表窗口恢复出的 `issue→refill` 分布为准，而不是把 `200 cycles` 直接当成 demand MISS 的实际返回时间。

### 1.4 覆盖范围

| IMA Pattern | 覆盖 | 理由 |
|-------------|------|------|
| **Pattern I: Linear Gather**（SpMV `x[Aj[k]]`） | ✅ 覆盖 | 核心目标，index 地址 stride 可预测 |
| **Pattern II: Frontier-Driven Gather**（BFS `dists[col_idx[j]]`） | ✅ 覆盖 | 核心目标，同 Pattern I 的 Index-Data Pipeline 结构 |
| **Pattern III: Data-Dependent Indirection**（CC hook `comp[max(...)]`） | ⚠️ 部分覆盖 | 第一层 `comp[dst]` 可预取（同 Pattern I）；第二层 `comp[high_comp]` 地址在第一层 load 返回前物理不可知，timeliness ≈ 0，标注为 limitation |
| **Pattern IV: Pointer Chasing**（CC shortcut） | ❌ 不覆盖 | 每一跳地址完全依赖上一跳返回值，MLP ≈ 0，无法提前预取 |

---

## 2. GPU 微架构约束

| 约束 | 说明 | 设计影响 |
|------|------|---------|
| **海量并发 warp** | A100 每 SM 最多 64 warp，108 SM | 不使用大型 per-warp 状态表，改用 address-triggered 即时方案 |
| **L1D 容量小** | 通常 32–128 KB（含 shared memory） | prefetch 污染风险高，需节流控制 |
| **Coalescing** | LD/ST coalescing unit 与 warp 指令结构性绑定 | Prefetcher 自带轻量 coalescer（32B sector 粒度），不复用 LD/ST 流水线 |
| **NoC 带宽有限** | L1→L2→HBM 带宽被所有 SM 共享 | 无用 prefetch 直接抢占有效带宽 |
| **Warp 切换隐藏延迟** | 多 warp 交替执行 | prefetch 的增量收益可能受限，但 ideal L1D 的 1.75×–3.04× 说明仍有大量空间 |
| **Loop Unrolling → PC 膨胀** | BFS 1 条源码 load → 5 个 SASS PC；SpMV → 30+ PC | 不能以 PC 作为 pattern 唯一标识，需要 (base, scale) 归组 |

---

## 2.5 Window 级设计证据（fresh small, 1SM + CTA5）

为避免只用大 workload 的平均值推导设计，本阶段对 `bfs_ima_small`、`sssp_ima_small`、`spmv_ima_small`、`cc_ima_small`、`bc_ima_small_forward`、`bc_ima_small_reverse` 重新生成了 fresh issue/L1 trace，并从最密集 IMA window 中恢复链级时延。结果目录：`04_prefetcher_design/extra_pattern/small_1sm_cta5/`。本节所有数字均来自 `1SM + CTA5 + lrr` 的代表窗口，只作为设计参考值；它们不等价于 pure DRAM return time，也不直接外推到 full-scale workload。按 workload 类别看是 5 类 IMA 负载，但当前统计条目为 6 个，因为 BC 分为 forward / reverse 两个测例。

### 2.5.1 跨 workload 的链时延总览

![Prefetch Latency Overview](04_prefetcher_design/extra_pattern/small_1sm_cta5/figures/prefetch_latency_overview.svg)

结论：
- BFS / SSSP / BC-forward / CC 的形态非常接近：`index_issue_to_refill_p50` 约 `536-585` cycles，而 `refill_to_data_issue_p50`（Intra-chain Gap）只有 `9` cycles，说明数据消费者几乎贴着 index refill 发射。
- BC-reverse 进一步拉长了链头和链尾等待：`index_issue_to_refill_p50=753`，`data_issue_to_refill_p50=1055`，但 intra-chain gap 仍只有 `9` cycles。
- SpMV 是唯一明显不同的 workload：`index_issue_to_refill_p50=853`，`data_issue_to_refill_p50=998`，`refill_to_data_issue_p50=35`，说明它需要更长 lookahead，也更依赖维持足够深的 outstanding prefetch。
- **注意**：Intra-chain Gap 度量的是同一条链内 index refill 到 data issue 的间隔，反映的是"反应式预取"的可用窗口。我们的预取器采用跨迭代提前预取（在 demand index issue 时即触发 index prefetch），因此实际领先量远大于此值。

### 2.5.2 可用窗口与收益空间

![Prefetch Window vs Cost](04_prefetcher_design/extra_pattern/small_1sm_cta5/figures/prefetch_window_vs_cost.svg)

结论：
- 大多数图 workload 落在”**intra-chain gap 很小，但 data miss 代价很高**”的区域；这意味着反应式预取（等 demand index 返回后再启动）几乎没有窗口，而必须依靠跨迭代提前预取来争取足够的领先量。
- SpMV 的 intra-chain gap 更宽，但 data miss 代价也更高；它不是”不需要 prefetch”，而是要求预取器支持更长的 in-flight 生命周期和更强的节流。
- 这张图直接支持“L2→L1、以 data 侧为主目标”的设计定位。

### 2.5.3 Index vs Data 压力分离

![Index vs Data Pressure](04_prefetcher_design/extra_pattern/small_1sm_cta5/figures/index_vs_data_pressure.svg)

结论：
- 所有 workload 都表现出 `data_load` 明显比 `index_load` 更差。BFS / SSSP / BC-forward 的 `data miss rate` 约 `0.72`；CC 达到 `0.98`；SpMV 达到 `0.99`。
- `index_load` 不是完全不重要，但更像链头触发器；真正决定收益上限的是 `data_load` 是否能从 MISS 转成 HIT。
- 右轴同时展示 `index_hit_reserved` 和 `data_hit_reserved`。SpMV 的 `index_hit_reserved` 高达 `41.5%`，说明它的链头请求已经有明显的在途重合（多 warp 共享 index array）；而 `data_hit_reserved` 在所有 workload 中均接近零（≤1.4%），说明 data 侧的 demand 访问几乎没有自然重合。这一对比进一步支持"预取器主目标应放在 data 侧"的结论。

### 2.5.4 链恢复可靠性

![Chain Completeness Overview](04_prefetcher_design/extra_pattern/small_1sm_cta5/figures/chain_completeness_overview.svg)

结论：
- 这批 fresh small 结果的 `complete_ratio` 都在 `95%` 以上，且 `bad_order_count=0`，说明当前链级结论可以直接作为设计输入。
- SpMV 的完整率最低（约 `95.4%`），但仍在可接受范围内；其不完整链更多反映 window 截断和更碎的展开形态，而不是链配对错误。

### 2.5.5 代表窗口细图

每个 workload/phase 都生成了一张代表窗口的链时延剖面图，路径位于 `04_prefetcher_design/extra_pattern/small_1sm_cta5/figures/`：

- `window_chain_profile_bfs_ima_small.svg`
- `window_chain_profile_sssp_ima_small.svg`
- `window_chain_profile_spmv_ima_small.svg`
- `window_chain_profile_cc_ima_small.svg`
- `window_chain_profile_bc_ima_small_forward.svg`
- `window_chain_profile_bc_ima_small_reverse.svg`

这些细图用于支撑上面的总览判断。它们的共同含义是：
- 上半图展示 `idx->refill`、`refill->data`、`data->refill` 的窗口内分布；
- 下半图展示 `data_load` 的 `MISS / HIT_RESERVED / HIT` 组成；
- 因此可以直接判断某 workload 是“窗口太小”问题，还是“data miss 太重”问题，或两者同时存在。

这些证据共同指向两个设计要求：
- Prefetch 的主目标应当是 **data_load**，而不是只优化 index_load。
- 预取触发必须足够早，不能等 demand index 返回后再做地址计算；这正是后文 Index-Data Pipeline 设计的必要性。

### 2.5.6 L2 路径与带宽上下文

![L1 Miss Path Breakdown](04_prefetcher_design/extra_pattern/small_1sm_cta5/figures/l1_miss_path_breakdown.svg)

结论：
- 这批 fresh small 结果表明，`data_load` 的 L1 miss 并不主要停留在 “L2 hit 即可救回” 这一层。BFS / SSSP 的 `data L2 miss-path rate` 已经在 `0.76-0.78`，SpMV 达到 `0.98`，CC 达到 `0.97`。
- `index_load` 普遍比 `data_load` 更容易在 L2 被截住，例如 CC 的 `index L2 hit-path rate` 约 `0.31`，而 `data` 只有 `0.03`。这再次说明 index 更像链头触发器，真正的收益核心仍然在 data 侧。
- BC 的 L2 数据来自 forward / reverse kernel snapshot，与当前 issue/L1 分析窗口保持同一 phase 口径，但匹配完整度低于 BFS / SSSP / SpMV / CC，因此更适合作为方向性参考，不宜过度解读绝对比例。

![L2 Context vs Chain Cost](04_prefetcher_design/extra_pattern/small_1sm_cta5/figures/l2_context_vs_chain_cost.svg)

结论：
- SpMV 与 CC 落在“`data L2 miss-path` 很高，同时 `data_issue_to_refill` 仍然很长”的区域，说明它们不是单纯的 L1 层时效问题，而是已经下沉到 L2/HBM 路径；这类 workload 上，prefetcher 需要更强的过滤和节流，避免把带宽进一步打满。
- BFS / SSSP 虽然同样以 `data` 侧 L2 miss 为主，但 HBM occupancy 低于 SpMV / BC-reverse，说明它们更适合作为首批验证对象：既有明显收益空间，又不至于一开始就把问题变成纯带宽竞争。
- 从设计上看，这组图支持一个更具体的定位：prefetcher 的主职责不是“把所有 L1 miss 都转成 L2 hit”，而是优先压低 **data_load 的长尾 miss latency**；当 workload 已经表现出较高 `L2 miss-path` 和 HBM occupancy 时，必须配合 throttle/filter，不能只追求覆盖率。

---

## 3. 核心架构：GRASP Index-Data Pipeline

### 3.1 架构总览

```
                          ┌─────────────────────────────────┐
                          │    Chain Detector (CD)           │
    指令流 ───────────────→│    (decode/issue 阶段)          │
    (PC, opcode,          │    2 tracked warps, FIFO=20     │
     registers)           │  追踪 LDG→IMAD.WIDE→LDG 依赖   │
                          └──────┬───────────┬──────────────┘
                                 │           │
                           更新 CT       更新 TT
                                 │           │
                    ┌────────────▼──┐  ┌─────▼──────────────┐
                    │  Chain Table  │  │  Target Table      │
                    │  (CT)         │  │  (TT)              │
                    │               │  │                    │
                    │  key: index   │  │  key: (data_base,  │
                    │    load PC    │  │        scale)      │
                    │  val: data_PC,│  │  val: base_addr,   │
                    │    tt_idx[]   │  │       scale        │
                    │               │  │                    │
                    └───────┬───────┘  └────────┬───────────┘
                            │                   │
                            └────────┬──────────┘
                                     │
               ┌─────────────────────▼─────────────────────┐
               │    Index Prefetch Unit (IPU)               │
               │                                           │
               │  当 warp 发出 index load 时:               │
               │  ① 查 CT 确认是 IMA index load            │
               │  ② 检查 stride_valid 确认可预取           │
               │  ③ 发出 index prefetch (sector 粒度):      │
               │     addrs = current_addr + iter_stride    │
               │  ④ 分配 PRB entry (等待值返回)            │
               └─────────────────────┬─────────────────────┘
                                     │ index prefetch 值返回
               ┌─────────────────────▼─────────────────────┐
               │    Data Prefetch Unit (DPU)                │
               │                                           │
               │  Response FIFO → ACU (32-wide,4sect/cyc): │
               │  对每个 target array k ∈ [0, K):          │
               │    data_addr = target[k].base             │
               │               + value × target[k].scale   │
               │  发出 data prefetch 请求 → L1             │
               └─────────────────────┬─────────────────────┘
                                     │ accuracy feedback
               ┌─────────────────────▼─────────────────────┐
               │    Throttle Controller (TC)                │
               │                                           │
               │  stride_valid 门控激活                    │
               │  (后期: misprediction counter / 带宽监控) │
               └───────────────────────────────────────────┘
```

### 3.1.1 模块缩写速查

下表用于快速对照后文各模块名称，避免在 `CD / CT / TT / IPU / DPU / PRB / ACU` 等缩写之间来回切换。

| 缩写 / 名称 | 全称 | 在 GRASP 中的作用 |
|-------------|------|-------------------|
| `GRASP` | GPU Register-chain Aware Sector Prefetcher | 本工作的 GPU IMA 预取器总名，通过寄存器依赖链和两阶段 pipeline 实现 L2→L1 的 IMA 预取 |
| `CD` | Chain Detector | 在 issue/decode 阶段用 **2 tracked warps** 的 FIFO（depth=20）检测 `LDG→IMAD.WIDE→LDG` 依赖链，识别哪些 load 是 IMA index load |
| `CT` | Chain Table | 以 `index_load_PC` 为 key 记录 IMA 链信息，包括 `data_load_PC`、`tt_idx[]`、`iter_stride` 等 |
| `TT` | Target Table | 存储 target array 的 `(base_addr, scale)`，供 data 地址计算与 one-to-many target 映射使用 |
| `IPU` | Index Prefetch Unit | 在 index load 发出时，根据 `iter_stride` 发出下一轮 index prefetch，并分配 PRB 条目 |
| `DPU` | Data Prefetch Unit | 在 index prefetch 返回后，读取 target 参数并发出 data prefetch 请求 |
| `TC` | Throttle Controller | 对预取发出进行节流与门控；当前核心门控条件是 `stride_valid`，后续可扩展 accuracy / 带宽监控 |
| `IST` | Iteration Stride Tracker | CT 扩展功能：任意 warp 的 demand load 均可参与 per-PC stride 学习，首个 warp 第 2 次访问时确定 `iter_stride` |
| `PRB` | Prefetch Request Buffer | 跟踪在途 index prefetch。软件仿真存 `tt_idx[]` 快照；硬件仅存 `ct_idx`（见 §7.1） |
| `ACU` | Address Computation Unit | 将返回的 index 值转换为 `base + value × scale` 的 data 地址，驱动 data-side 预取 |
| `FIFO` | Register FIFO | CD 使用的小型寄存器依赖追踪队列，用于暂存最近的 `LDG` / `IMAD.WIDE` 关系 |
| `Response FIFO` | Response FIFO | 缓冲 L1 返回的 index prefetch sector 响应，避免返回带宽高于 ACU 吞吐时出现拥堵 |
| `Index Coalescer` | Index Coalescer | 将 32 lane 的 index prefetch 地址按 32B sector 合并为较少的 L1 请求 |
| `Data Coalescer` | Data Coalescer | 将 ACU 生成的 data 地址按 32B sector 合并后发往 L1，降低请求数与 MSHR 压力 |

### 3.2 双表设计 (CT + TT)

#### Chain Table (CT)（原 Table A: PC Dependency Table）

用于将 PC 分类为"IMA index load"或"普通 load"。

| 字段 | 大小 | 硬件持久化 | 说明 |
|------|------|:---------:|------|
| **key** | 24 bit (tag) | ✅ | `index_load_PC`，CT 唯一 key，demand load 匹配用 |
| **data_load_PC** | 32 bit | ❌ | CD 检测阶段使用，不存入 CT（data prefetch 通过 TT 完成） |
| **IMAD_PC** | 32 bit | ❌ | CD 检测阶段提取 (base, scale) 写入 TT 后即完成使命，不存入 CT |
| **tt_idx[K]** | ceil(log₂TT)×K bit | ✅ | 指向 TT 的索引（最多 K=3 个 target array），建表时从 IMAD.WIDE 操作数实时获取 |
| **num_targets** | 2 bit | ✅ | 当前已发现的 target 数量（0..K），用于 one-to-many 累积检测 |
| **tracked_warp_id** | — | SM 全局 | SM 级共享的 tracked warp（6 bit），不占用 per-entry 空间 |
| **stride_obs[2]** | 2×38 bit | ✅ | 2 个 observation slot：{warp_id(6b), first_addr(32b)}，任意 warp 首次访问记录地址 |
| **iter_stride** | 16 bit | ✅ | 学到的 iteration stride，单位 bytes |
| **stride_valid** | 1 bit | ✅ | stride 是否已学到 |

**淘汰策略**：当 CT 满且需插入新 entry 时，优先驱逐 `stride_valid == false` 的 entry。理由：`stride_valid == false` 意味着该 PC 要么是前序代码（只执行一次，stride 永不收敛），要么是刚写入尚未完成学习的 entry。前者永远不产生 prefetch，是 CT 的"死 entry"；后者重新写入后会重新学习，代价仅为延迟一个 iteration。若所有 entry 均 `stride_valid == true`，回退到标准 LRU 淘汰。

**建表方式**：在 decode/issue 阶段追踪寄存器依赖链。当观测到 `LDG Rd → IMAD.WIDE Rx, Rd, scale, c[base] → LDG [Rx]` 时，确认 (index_PC, data_PC) 为 IMA 对，写入 CT。

**归并效果**：Loop unrolling 产生的多个 index load PC 拥有不同的 CT entry，但它们的 IMAD.WIDE 操作数具有相同的 `(data_base, scale)`，因此建表时映射到同一个 TT entry，`tt_idx[0]` 指向同一条目。

#### Target Table (TT)（原 Table B: Pattern Table）

每个 entry 存储**单一** data array 的预取参数。One-to-many（如 BC reverse: 1 index → 3 data array）由 CT 的多个 `tt_idx` 槽指向不同的 TT entry 实现，而非在单个 TT entry 内嵌套数组。IMA 依赖链的结构性模式匹配（`LDG→IMAD.WIDE→LDG` 寄存器依赖）已具备足够的选择性（BFS 全 SASS 验证：14 条 IMAD.WIDE 零误检），无需 confidence 门控——首次检测到完整依赖链即可写入。实际预取发出由 `stride_valid` 门控（stride 未学到时不发 prefetch）。

| 字段 | 大小 | 说明 |
|------|------|------|
| **key** | 72 bit | `(data_base, scale)` — 来自 IMAD.WIDE constant operand，用于建表时 CAM 去重 |
| **base_addr** | 64 bit | data array 基地址 |
| **scale** | 8 bit | 元素大小（`sizeof(element)`，通常 4 或 8） |
| **valid** | 1 bit | 有效位 |

**单 entry 单 target 的理由**：原设计在 TT 内嵌 `targets[K=3]` 数组，导致每个 entry 按最大 K 分配空间（即使 BFS/SpMV 等 K=1 的 workload 也浪费 2/3 空间）。拆分后，TT entry 大小统一（~10B），one-to-many 通过 CT 的 `tt_idx[0..K-1]` 指向多个 TT entry 实现，结构更清晰且总存储更小。

**归并效果（以 SpMV 为例）**：
- 源码中 1 条 `x[Aj[k]]` 的 load
- SASS 中展开为 30+ 个不同 PC 的 LDG（×16, ×8, ×4, ×1 版本）
- 所有 30+ 个 CT entry 的 `tt_idx[0]` → 同一个 `(x_base, 8)` 的 TT entry

**One-to-many 效果（以 BC reverse 为例）**：
- 1 个 `index_PC` 的返回值被 3 条 IMAD.WIDE 消费，生成 3 个不同 data array 的地址
- Detector 发现 3 条链后，CT entry: `num_targets=3`, `tt_idx = [idx_depths, idx_pathcounts, idx_deltas]`
- 3 个 TT entry 各存一个 target: `(depths_base, 4)`, `(path_counts_base, 4)`, `(deltas_base, 8)`

### 3.3 Index-Data Pipeline（两阶段预取管道）

IMA 预取分为 Index Phase 和 Data Phase 两步，形成 pipeline：

```
时间线（以 BFS ×4 展开为例，distance=1 outer iteration，iter_stride=16B=4 elements）:

迭代 i:
  warp 发出 index load: LDG column_indices[offset_i]     ← 正常执行
  prefetcher 同时发出: PREFETCH column_indices[offset_i + iter_stride]
                       = column_indices[offset_i + 16]   ← Step 1: index prefetch (i+1 的窗口)

  ... (其他 warp 执行) ...

  column_indices[offset_i + 16] 的值 v 在 prefetch refill 时返回
  prefetcher 计算: data_addr = dists_base + v × 4        ← Step 2: data prefetch
  prefetcher 发出: PREFETCH dists[v]

  ... (数百 cycles later；具体取决于 workload 与窗口拥塞) ...

迭代 i+1 (outer iteration):
  warp 发出 data load: LDG dists[column_indices[offset_i+4]]
  → L1 HIT (已被 prefetch 填充)                          ← 预取命中！
```

**Prefetch distance**：初始默认 distance=1（提前 1 个 outer iteration），即 `current_addr + iter_stride`。后续可通过实验探索 distance=2/4，但 distance=1 已提供 ~500-800 cycles 的领先量（`index_issue_to_refill_p50`），足够覆盖 L2 miss 服务时间。

**关键时序**（配置项与代表窗口观测值分开写）：
- L1 hit 延迟（config）：34 cycles
- L2 ROP latency（config）：**200 cycles**
- DRAM latency（config）：190 cycles
- `small_1sm_cta5 / lrr` 代表窗口中，`index_issue_to_refill_p50` 约为 `536-853` cycles，`p90` 约为 `834-2152` cycles
- `small_1sm_cta5 / lrr` 代表窗口中，`data_issue_to_refill_p50` 约为 `512-1055` cycles，`p90` 约为 `790-2365` cycles
- `small_1sm_cta5 / lrr` 代表窗口中，`refill_to_data_issue_p50` 对 BFS / SSSP / BC-forward / BC-reverse / CC 为 `9` cycles，SpMV 为 `35` cycles

上面后三项是代表窗口中观测到的 MISS-like `issue→refill` / `refill→consumer` 参考值，不应解读为“纯 DRAM 返回时间”。

**时效性分析**：当前 fresh small 结果表明，不能再用 `index≈200`、`data≈200`、总计 `≈400 cycles` 的固定链长来判断可行性。真正影响Index-Data Pipeline 的，是“data 消费者几乎贴着 index refill 发射”这一事实：对于大多数图 workload，`refill_to_data_issue_p50=9` cycles，说明 prefetch 不能等 demand index 返回后再启动，而必须依赖更早发出的 index prefetch 来提前拿到 value，并用 per-PC 的 outer-iteration 窗口吸收 `index` 与 `data` 两段数百-cycle 的 MISS-like 服务时间。

对于 ×4 展开（BFS/SSSP/BC/CC）：设计可行性的依据不再写成“每轮约 400-500 cycles”，而是写成“代表窗口里 `index_issue_to_refill_p50` 约 `536-753`、`data_issue_to_refill_p50` 约 `512-1055`，且 `refill_to_data_issue_p50=9`，因此 lookahead 必须由 outer-iteration 间隔来提供，而不能依赖 demand 链自身的 slack”。
对于 ×16 展开（SpMV）：`index_issue_to_refill_p50=853`、`data_issue_to_refill_p50=998`、`refill_to_data_issue_p50=35`，说明它需要更长 lookahead，也更依赖维持足够深的 in-flight prefetch。

#### 3.3.1 Coalescing 与 Sector 粒度

**Prefetcher 自带轻量 coalescing 逻辑**：硬件上，LD/ST 流水线的 coalescing unit 与 warp 指令（`warp_inst_t`）结构性绑定——它消费的是指令 issue 阶段产生的 32 个 per-lane 地址。Prefetcher 是一块独立硬件，不经过 warp scheduler，不 issue 指令，因此**无法复用** LD/ST 流水线的 coalescing 路径。Prefetcher 需要自带等价的 coalescing 逻辑，但由于 prefetcher 只处理已知形式的地址（`base + value × scale` 或线性 stride），其 coalescer 比 LD/ST 流水线的更简单（仅需按对齐地址分组 + 去重）。

**对齐 A100 L1 Sector 架构**：A100 L1 以 **32B sector**（而非 128B cache line）为操作单位。cache line = 128B = 4 sectors。LSU 将 warp 的访存请求 coalesce 为 sector 级别，每 cycle 可发送 bank 个 sector（无 bank conflict 时）。Prefetcher 的 coalescer 同样以 32B sector 为粒度，产出 sector 级请求。

Prefetcher 内部有两处 coalescer：

| Coalescer | 位置 | 输入 | 输出 | 特点 |
|-----------|------|------|------|------|
| **Index Coalescer** | Component 2 → L1 | 32 per-lane index prefetch 地址 | 1~32 sector 请求 | 取决于 workload：SpMV 线性访问 → ~4 sectors；BFS/SSSP 等 frontier-driven → 平均 ~3-4 但分布双峰（见下文） |
| **Data Coalescer** | Component 3 → L1 | ACU 输出的 8×K data prefetch 地址 | M sector 请求 | IMA data 地址高度分散，合并率低 |

**Index Coalescer 输出的 sector 数取决于 workload 的 inter-lane 访问模式**：

| Workload 类型 | 典型 sector 数 | 原因 |
|--------------|---------------|------|
| SpMV（同行连续列索引） | ~4 | 32 lanes 访问 `Aj[k..k+31]`，连续地址 → 128B = 4 sectors |
| BFS/SSSP/BC/CC（frontier-driven） | 平均 ~3-4，tail 可达 20+ | 32 lanes 处理不同 frontier 顶点，`row_offsets[src_L]` 在 lane 间差异大 |

BFS 实测数据（`bfs_ima_small`, 1SM+CTA5）：44.5% 的 index load coalesce 为 1 sector，74.1% ≤ 4 sectors，但 11.1% scatter 到 9+ sectors。这个双峰分布意味着 PRB 的平均消耗不高，但 burst 峰值时可能需要较多 PRB entry。

**Index Coalescer 多 warp 压力分析**：SM80_A100 配置为 `gpgpu_sub_core_model 1` + `gpgpu_num_sched_per_core 4`，但只有 **1 个 ldst_unit**（`shader.cc` 中仅实例化一次）。因此 SM 级每 cycle 最多发射 1 条 memory 指令——4 个 scheduler 竞争共享 LSU。这意味着 Index Coalescer 每 cycle 最多接收 1 个 index load 的 32 lane 地址，输入速率不会因多 warp 而倍增。但若 coalescer 处理延迟 > 1 cycle（32 地址排序分组），则需要 2–4 entry 输入缓冲应对连续 cycle 到达的 index load。实际中连续两个 cycle 都是 index load 的概率较低（BFS 约 5% 的指令是 index load），压力可控。实现时添加 `idx_coalescer_stall_cycles` 计数器验证。

**Active Mask 策略**：prefetch 使用**当前 warp 的 active_mask**，不预测未来 mask。

| 方面 | 策略 | 理由 |
|------|------|------|
| 使用哪些 lane 的地址 | 当前 active_mask 中的 active lane | 简单且正确——predicated-off lane 的 index 值无意义 |
| 未来 mask 是否预测 | 不预测 | 条件分支（如 BFS `if dists[dst] == INF`）使未来 mask 不可知 |
| 浪费如何处理 | 由 throttle 消化 | 少数 lane 的 prefetch 可能无用，但代价可控 |

**Deduplication**：A100 L1 以 32B sector 为操作单位，一条 warp 的 demand load 可能触发多个 sector 请求（如 128B cache line = 4 sectors）。Prefetcher 必须对同一 warp 指令的多个 sector 去重——否则同一 index load 的每个 sector 都会重复触发 stride learning 和 prefetch generation。实现中通过 per-warp 的 `(ct_idx, inst_uid)` 去重，确保每条 warp 指令仅触发一次 prefetch generation。此外，per-lane 地址去重（多个 lane 预测相同 byte address）和 sector 级合并（多 lane → 同一 data sector）进一步减少冗余请求。

**Prefetcher 作为 L1 Client**：Prefetcher 是 L1 cache 的一个独立 client，与 warp demand load 平级。请求通过独立端口发送，不与 demand load 竞争发射带宽。L1 对 prefetcher 请求和 demand 请求使用相同的 tag check → MSHR → fill 流程，但响应路径不同：index prefetch 的响应需要携带数据返回给 prefetcher（用于 Step 2 地址计算），而 data prefetch 是 fire-and-forget。

**Prefetch 与 L1 Cache 的交互流程**（区分 index prefetch 和 data prefetch）：

| L1 状态 | Index Prefetch 行为 | Data Prefetch 行为 |
|---------|--------------------|--------------------|
| **HIT** | L1 返回 {prb_entry_id, sector_data[32B], element_mask[8bit]} 给 prefetcher | 丢弃（数据已在 L1），仅更新 LRU |
| **MISS, MSHR 有匹配** | 合并到现有 MSHR entry（携带 prb_entry_id） | 合并到现有 MSHR entry |
| **MISS, MSHR 无匹配** | 分配新 MSHR entry（携带 prb_entry_id），向 L2 发出 fill request；fill 后数据返回给 prefetcher | 分配新 MSHR entry，向 L2 发出 fill request |
| **MISS, MSHR 满** (RESERVATION_FAIL) | **放弃该 sector**，标记 RFAIL；对应的 PRB sector 不生成 data prefetch | **丢弃**（fire-and-forget） |

**Index Prefetch 在 MSHR 满时放弃而非阻塞**：初始设计考虑过阻塞等待（保证 Index-Data Pipeline 不断裂），但实现中发现**放弃更优**——阻塞会 stall 整个 prefetch queue（包括后续其他 warp 的请求），导致 prefetch 堆积和时效性下降。放弃仅损失该 sector 对应的 data prefetch 机会；同一 index load 的其他 sector（如果 MSHR 有空位）仍可正常完成。PRB 通过 `remaining_sectors` 计数器跟踪，RFAIL 的 sector 计入已完成但不触发 data prefetch。Data prefetch 在 MSHR 满时同样丢弃——它是最终步骤，丢弃的代价仅为一次预取机会损失。

**MSHR 合并（merge）场景**：当 prefetch 请求的 sector 已有一个 in-flight demand load（另一个 warp 已发出请求），prefetch 不产生额外的 L2 流量——它合并到现有 MSHR entry 中。SM80_A100 的 L1 MSHR 配置为 512 entries（max_merge=64），合并容量充裕。

**设计含义**：
- L1 HIT 和 MSHR merge 两种情况下，prefetch **不产生额外 L2 带宽消耗**
- 真正消耗带宽的是 L1 MISS + MSHR 无匹配的情况——即 prefetch 确实提前请求了尚未被任何 warp 请求的 sector
- Prefetcher 的独立端口确保 prefetch 永远不阻塞 demand load

---

## 4. 组件详细设计

### 4.1 Chain Detector (CD)

**位置**：SM 的 issue/decode 阶段（可观测 PC、opcode、源/目标寄存器编号操作数）。

**检测算法伪代码**：

```python
# SM 级共享 FIFO（20 entries），追踪 2 个"tracked warps"的寄存器依赖
# 每条 entry: {dst_reg, type, PC, ima_info?}
# 查找方式: 在 FIFO 中反向搜索匹配 src_reg 的最新 entry
#
# SM 全局状态:
#   tracked_warp_ids[2]: 2×6 bit (当前被追踪的 2 个 warp，UNSET = 无)
#   tracked_warp_priority: 1 bit (调度器 tie-breaking hint)
#
# FIFO entry 结构（~6 bytes）:
#   dst_reg:  8 bit  (寄存器编号 0-255)
#   type:     1 bit  (LOAD_RESULT / IMA_ADDR_COMPUTE)
#   PC:      32 bit  (用于回填 CT 的 index_PC)
#   ima_info: 可选，仅 IMA_ADDR_COMPUTE 类型携带 (index_PC, scale, base)
#
# 注意：不追踪 IMAD.MOV 等常量加载指令。scale 和 base 在 IMAD.WIDE issue 时
# 直接从寄存器文件/指令操作数读取，无需通过 FIFO 间接获取。
#
# 设计理由：去除 confidence 后，单次完整链观测即可写入 CT/TT。
# 无需 64 个 per-warp FIFO 并行检测——2 个 tracked warp 的共享 FIFO 即可
# 完成所有 IMA 链检测，硬件开销从 3 KB 降至 ~120 B。
# 使用 2 个而非 1 个 tracked warp 的原因：单个 warp 可能在首次 outer loop
# iteration 后即 EXIT（例如 frontier-driven 算法中处理完自己的邻居），
# 导致 stride 永远学不到。2 个 tracked warp 大幅缓解此问题。

def fifo_lookup(reg):
    """在 tracked warp 的 FIFO 中反向查找最近写入 reg 的 entry"""
    for entry in reversed(reg_fifo):
        if entry.dst_reg == reg:
            return entry
    return None  # 未追踪到 → 视为普通寄存器

def on_instruction_issue(warp_id, PC, opcode, dst_reg, src_regs, operands):

    # === 训练冻结检查 ===
    if training_frozen:
        return  # 所有 stride 已学到，CD 休眠（省功耗）

    # === 仅追踪 2 个 tracked warp 的指令 ===
    if not is_tracked_warp(warp_id):
        if opcode == LDG:
            if tracked_warp_ids[0] == UNSET:
                tracked_warp_ids[0] = warp_id  # 首个发出 LDG 的 warp
            elif tracked_warp_ids[1] == UNSET and warp_id != tracked_warp_ids[0]:
                tracked_warp_ids[1] = warp_id  # 第二个（不同 warp）
            else:
                return  # 已有 2 个 tracked warp，忽略其他 warp
        else:
            return
    # 非 tracked warp 的指令对 FIFO 不可见

    # === FIFO Invalidation（两种可选机制，见 §4.1.1）===
    # 默认使用 Read Detection:
    # FIFO 的不变量：entry {Rd, LOAD_RESULT} 意味着"Rd 当前持有该 LDG 的返回值且尚未被非 IMA 消费"
    # 当非 IMAD.WIDE 指令的 src_reg 匹配 FIFO 中某 LOAD_RESULT entry 时 → invalidate
    if opcode not in {IMAD_WIDE}:
        for src in src_regs:
            fifo_invalidate_by_src(src)  # 匹配 FIFO 中 dst_reg == src 的 LOAD_RESULT entry

    if opcode == LDG:
        addr_reg = src_regs[0]  # LDG 的地址寄存器

        # 检查：这条 LDG 的地址是否由一个 IMA 地址计算产生？
        producer = fifo_lookup(addr_reg)
        if producer and producer.type == IMA_ADDR_COMPUTE:
            # 确认 IMA 依赖链完成: LDG → IMAD.WIDE → LDG
            ima = producer.ima_info

            # 查找或创建 TT entry（CAM lookup by (base, scale)）
            tb_idx = TT.cam_lookup(ima.base, ima.scale)
            if tb_idx is None:
                tb_idx = TT.allocate(base_addr=ima.base, scale=ima.scale)

            if ima.index_PC in CT:
                # 同一 index_PC 的新 target（one-to-many，如 BC reverse）
                # → 将新 TT index 追加到 CT 的 tt_idx[] 数组
                existing = CT[ima.index_PC]
                if tb_idx not in existing.tt_idx[:existing.num_targets]:
                    existing.tt_idx[existing.num_targets] = tb_idx
                    existing.num_targets += 1
            else:
                # 首次发现 → 立即写入 CT（无需 confidence 门控）
                CT[ima.index_PC] = {
                    data_PC:      PC,
                    tt_idx:  [tb_idx, INVALID, INVALID],
                    num_targets:  1
                }

        # 记录这条 LDG 到 FIFO（可能作为下一个 IMA 的 index load）
        reg_fifo.push({dst_reg: dst_reg, type: LOAD_RESULT, PC: PC})

    elif opcode == IMAD_WIDE:
        src_val_reg = src_regs[0]   # 被乘数（可能是 load 返回值）
        # scale 和 base 直接从 IMAD.WIDE 指令的操作数/寄存器文件读取：
        scale       = RF[src_regs[1]]   # 乘数（scale = sizeof(element)），issue 时从 RF 读取
        base_addr   = operands.third     # 第三操作数（data array base，通常来自 constant memory c[bank][offset]）

        producer = fifo_lookup(src_val_reg)
        if producer and producer.type == LOAD_RESULT:
            # 这个 IMAD.WIDE 消费了一个 load 的返回值 → 可能是 IMA 地址计算
            reg_fifo.push({
                dst_reg: dst_reg,
                type: IMA_ADDR_COMPUTE,
                ima_info: {
                    index_PC: producer.PC,
                    scale:    scale,      # 直接从 RF 获取，无需 FIFO 追踪 IMAD.MOV
                    base:     base_addr
                }
            })
        # 非 IMA 相关的 IMAD.WIDE 不入 FIFO（节省空间）
        # 注意：不追踪 IMAD.MOV。scale 值在 IMAD.WIDE issue 时已可从 RF 读取。

```

**SM 级单一 FIFO 设计说明**：

| 设计要点 | 说明 |
|---------|------|
| **为什么共享 FIFO 而非 per-warp** | 去除 confidence 后，单次完整链观测即可写入 CT/TT。无需 64 个 warp 并行检测——2 个 tracked warp 的共享 FIFO 即可完成所有 IMA 链发现。硬件从 3 KB 降至 **~120 B**（1 × 20 × 6B）。 |
| **为什么用 FIFO 而非全量表** | IMA 依赖链 `LDG→IMAD.WIDE→LDG` 通常跨 3-5 条指令。20-entry FIFO 足以覆盖 SpMV ×16 展开体（峰值 17 entries，见 FIFO 深度分析）。全量 `[reg]` 表需要追踪 256 个寄存器，绝大部分 entry 永远不会被查到。 |
| **为什么 2 个 tracked warp** | 单个 tracked warp 可能在首次 outer loop iteration 后即 EXIT（frontier-driven 算法中 warp 处理完邻居即退出），导致 stride 永远学不到。2 个 tracked warp 确保至少有一个完成 stride 学习。FIFO 共享，只处理这 2 个 warp 的指令。 |
| **Tracked warp 选择** | 前两个发出 LDG 的不同 warp 自动成为 tracked warp。所有非 tracked warp 的指令对 FIFO 不可见。 |
| **查找方式** | 反向线性搜索 FIFO（20 entries，硬件实现为 20 个并行比较器 + 优先编码器），与 CPU store buffer 的 CAM 查找类似 |
| **淘汰策略** | 两层淘汰：① 无效化（write-invalidation 或 read-detection，见 §4.1.1）及时清除失效 entry；② FIFO 满时自然淘汰最旧 entry |
| **存储开销** | 1 × 20 entries × 6B/entry + tracked_warp_ids[2](12b) + priority(1b) ≈ **~122 B/SM**（对比原 per-warp 方案 3 KB，节省 96%） |
| **只记录相关指令** | 仅 LDG、IMA 相关的 IMAD.WIDE 入 FIFO（IMAD.MOV 不追踪——scale 在 IMAD.WIDE issue 时从 RF 直接读取）；其他指令仅触发无效化检查，不写入 FIFO |
| **调度器优先 hint** | Tracked warp 标记 1-bit priority hint，调度器在多个 ready warp 间 tie-breaking 时优先选择 tracked warp。不阻塞其他 warp——仅影响 tie-breaking 顺序（参考 CAPS [Koo 2018] 的 PAS 机制） |

**FIFO 深度分析（基于 SASS 逐指令仿真）**：

FIFO 深度 8 是基于 BFS unroll×4 的初始估计。为验证其在所有目标 workload 下的充分性，我们对所有 Gardenia 核心 kernel 的 SASS 进行了逐指令仿真，精确模拟 CD 的工作流程：

- **PUSH**：每条 LDG 的 dst_reg 入队
- **DETECT**：IMAD.WIDE 的 src_reg 匹配 FIFO entry 时检测到 IMA 链，**但不弹出**（IMAD.WIDE 是目标检测指令，其读操作不触发读失效）
- **READ_INVAL**：非 IMAD.WIDE 指令读取了 FIFO 中的 reg → 弹出（证明该值不参与 IMA）
- **WRITE_INVAL**：任何指令覆写了 FIFO 中的 reg → 弹出（包括 IMAD.WIDE 的 Rd:Rd+1 目标寄存器对）
- **DROP**：FIFO 满时新 LDG 无法入队 → 后续 IMAD.WIDE 匹配失败，IMA 链丢失

仿真脚本：`ima_plan/04_prefetcher_design/extra_pattern/small_1sm_cta5/fifo_sim_spmv_x16.py`

**正常场景——BFS ×1（`.L_x_6`）**：

```
LDG R0, [R24]           → PUSH R0             FIFO: {R0}       = 1
IMAD.WIDE R4, R0, R3, c → DETECT R0 (链检测)  FIFO: {R0}       = 1  (不弹出)
LDG R2, [R4]            → PUSH R2             FIFO: {R0, R2}   = 2  ← 峰值
ISETP ..., R2, ...       → READ_INVAL R2       FIFO: {R0}       = 1
  ... (循环体: CAS, worklist) ...
LDG R0, [R24+4] (下轮)  → WRITE_INVAL R0      FIFO: {}         = 0
                          → PUSH R0             FIFO: {R0}       = 1
```

峰值 FIFO = **2 entries**。IMA 链紧密排列（LDG → 1 条指令 → IMAD.WIDE），非 IMA load 被后续指令迅速读失效。**FIFO=8 有 4× 冗余。**

**最大压力场景——SpMV ×16（`.L_x_7`）**：

编译器将 16 次迭代的 48 条 LDG（16 col_idx + 16 val + 16 x[]）交错调度以最大化 MLP。仿真结果：

| FIFO 深度 | 检测到的链 | 丢失 | 丢失率 | 说明 |
|-----------|-----------|------|--------|------|
| 4 | 4/16 | 12 | 75% | |
| 8 | 8/16 | 8 | **50%** | 当前设计值 |
| 12 | 14/16 | 2 | 12.5% | |
| 16 | 15/16 | 1 | 6.2% | |
| **17** | **16/16** | **0** | **0%** | 零丢失最小值 |

FIFO=8 时 col_idx[6-10] 和 col_idx[13-15] 因两波溢出被 DROP（val/x[] data load 挤占 FIFO 空间），50% 的 IMA 链无法检测。根因是 nvcc 的 ×16 展开将三类 load 深度交错——11 条连续 LDG 在首个 IMAD.WIDE 之前发射，FFMA 消费（读失效）回收空间又来得太晚。

**全 workload 峰值汇总**：

| Workload | 展开 | 峰值 FIFO | FIFO=8 检测率 | 说明 |
|----------|------|-----------|-------------|------|
| BFS | ×1/×4 | 2 | 100% | 无展开交错 |
| SSSP | ×1/×4 | ~3 | 100% | weight/edge_weight 非 IMA load，间距短 |
| CC | ×1 | ~2 | 100% | 循环体简单 |
| BC | ×1 | ~4 | 100% | 条件路径多，每迭代独立 |
| **SpMV** | **×16** | **17** | **50%** (FIFO=8) / **100%** (FIFO=20) | 48 条 LDG 交错，FIFO=20 零丢失 |

**实现结果——FIFO=20 + 运行时统计**：

FIFO 深度的最优值取决于编译器的展开策略和寄存器分配。实现中采用 FIFO=20 作为默认值（`-cd_fifo_depth 20`），在所有目标 workload 上实现 0% 丢失率，包括 SpMV ×16 的极端场景（峰值=17）。具体策略：

1. **可配置深度的 FIFO**：通过参数 `-cd_fifo_depth N` 控制深度，默认值 20（SpMV ×16 峰值 17 + 安全裕量 3）
2. **添加运行时峰值监测**：记录每个 workload 运行期间 FIFO 的 `peak_occupancy` 和 `drop_count`（因 FIFO 满导致的丢弃次数）
3. **参数扫描确定最优值**：在所有目标 workload 上扫描 FIFO 深度（4/8/12/16/20），结合 `drop_count=0` 的最小值和硬件面积约束，确定最终深度
4. **硬件设计预留**：最终硬件深度按扫描结果 + 安全余量确定（如 peak=17 → 硬件取 20），SASS 仿真的 17 entries 作为下界参考

这种"先跑通再优化"的策略避免了过早锁定参数——编译器版本、优化选项、新 workload 都可能改变最优深度。

**One-to-Many 累积检测**：

BC reverse 中，一条 index load（`column_indices[offset]`，单一 PC）的返回值被三条独立的 IMAD.WIDE 消费，生成 `depths[dst]`、`path_counts[dst]`、`deltas[dst]` 三个 data load。SASS 证据：

```asm
IMAD.WIDE R8, R9, R6, c[0x0][0x178]   // depths[dst]      ← base_1, 共享 index R9
IMAD.WIDE R8, R9, R6, c[0x0][0x170]   // path_counts[dst] ← base_2, 共享 index R9
IMAD.WIDE R8, R9, R6, c[0x0][0x188]   // deltas[dst]      ← base_3, 共享 index R9
```

FIFO 会自然发现三条独立的 `LDG→IMAD.WIDE→LDG` 链，但它们共享同一个 `index_PC`。伪代码中通过 `index_PC in CT` 判断区分：
- **首次发现**：创建 TT entry（CAM by (base,scale)），写入 CT（`tt_idx[0] = tb_idx, num_targets = 1`）
- **后续发现**：创建/查找新的 TT entry，追加到 CT 的 `tt_idx[num_targets++]`

One-to-many 的复杂性由 CT 的 K 个 `tt_idx` 槽吸收，每个 TT entry 保持单一 target 的简单结构。

**IMAD.MOV 无需 FIFO 追踪**：在 BFS 的 SASS 中，scale 值并非 IMAD.WIDE 的立即数，而是先由 `IMAD.MOV.U32 R11, RZ, RZ, 0x4` 加载到寄存器。但 IMAD.WIDE issue 时 R11 的值已在寄存器文件中可读——Detector 直接执行 `RF[R11]` 获取 scale，无需通过 FIFO 间接追踪 IMAD.MOV。这简化了 FIFO 的 type 字段（仅需 LOAD_RESULT / IMA_ADDR_COMPUTE 两种），减少入 FIFO 的指令种类。

```asm
/*0660*/  IMAD.MOV.U32 R11, RZ, RZ, 0x4         // R11 = 4 (sizeof(int))  ← 不入 FIFO
/*0670*/  IMAD.WIDE R2, R0, R11, c[0x0][0x178]  // Detector 读 RF[R11]=4 获取 scale
```

**设计假设与边界**：

IMAD.WIDE 参数直接提取的可行性并非经验性观察（"看了 5 个 workload 碰巧都这样"），而是由 GPU 编译器的代码生成逻辑和 CUDA 内存模型**结构性保证**的。

**编译器视角：为什么 IMAD.WIDE 是必然选择**

源码中 `data[index_val]` 的地址计算为 `base_ptr + index_val × sizeof(element)`，即 32-bit × 32-bit + 64-bit → 64-bit。NVIDIA SASS ISA 中：

- `IMAD.WIDE Rd, Ra, Rb, Rc` 单条指令完成 `Ra × Rb + Rc`（32×32+64→64），**这是唯一能单指令完成此运算的 SASS 指令**
- 替代方案需要至少 3 条指令：`SHL Rtmp, Rindex, log2(scale)` + `IADD3 Rlo, Rtmp, Rbase_lo` + `IADD3.X Rhi, RZ, Rbase_hi, carry`
- NVIDIA 的 SASS 编译器（ptxas）以 IPC 和指令数为核心优化目标，**不会在有单指令方案时选择 3 指令方案**——这是代码生成器的优化不变量，而非启发式行为

因此，只要源码是 `array[computed_index]` 形式，编译器**必然**生成 IMAD.WIDE。

**Scale 为什么总是编译期常量**

`sizeof(element)` 由 C++ 类型系统在编译期确定：`int`→4, `float`→4, `double`→8。编译器将其编码为：
- 立即数直接嵌入 IMAD.WIDE（当 ISA encoding 允许时），或
- 通过 `IMAD.MOV.U32 Rscale, RZ, RZ, imm` 预加载到寄存器并在整个循环中复用（`.reuse` 标记）

SpMV SASS 中 R16 被所有 30+ 个 unrolled IMAD.WIDE 共享（`R16.reuse`），证实编译器认为 scale 是循环不变量。

**Base 为什么总在 constant memory**

这是 CUDA 编译模型的结构性保证：
1. 源码：`__global__ void kernel(int* column_indices, int* dists, ...)` — 数组指针是 kernel 参数
2. PTX 编译：kernel 参数进入 `.param` 地址空间
3. SASS 代码生成：`.param` 映射到 constant memory bank 0 → `c[0x0][0x1XX]`

这个链条中没有任何"选择"——只要数组指针作为 kernel 参数传入，base 就**一定**在 `c[0x0]` 中。图算法的 CSR 数组（`column_indices`、`row_offsets`、`dists`、`comp` 等）全部通过 `cudaMalloc` + kernel 参数传递，100% 落入此保证。

| 假设 | 结构性依据 | 失效场景 |
|------|-----------|---------|
| Scale 是编译期常量 | C++ 类型系统 + SASS 编译器优化（单指令优于多指令） | 非标准 element size（struct packing）——图算法中不存在 |
| Base 来自 constant memory | CUDA param → .param → c[0x0] 映射链 | 设备端动态分配指针（`new`/`malloc`）——标准图算法不使用 |
| IMAD.WIDE 用于所有间接地址计算 | 唯一的单指令 32×32+64→64 方案 | 未来 ISA 引入替代指令——可扩展检测器覆盖 |

5 个 workload 的全部 SASS 验证（BFS/SSSP/SpMV/BC/CC）：scale 100% 为 IMAD.MOV 常量加载，base 100% 为 c[0x0] 直接编码，零反例。这不是"碰巧一致"而是上述编译器保证的直接结果。

**与 CPU 方案的关键区别**：CPU 上 IMP 需要从地址差分反推 shift（试探有限候选集 2/3/4/-3），DMP 需要差分序列比例匹配。这些方法本质是"推断"——因为 x86 的 `lea`/`mov` 不像 IMAD.WIDE 那样结构化暴露计算参数。GPU 的 IMAD.WIDE 将 scale 和 base 直接暴露为指令操作数，是**零推断、零试探**的直接提取。这不是设计上的"简化"，而是 GPU ISA 结构性提供的优势，也是本方案相比 CPU 工作的核心差异化之一。

**训练模型**：

| 层面 | 粒度 | 说明 |
|------|------|------|
| **寄存器追踪（FIFO）** | SM 级共享 | 整个 SM 共享一个 20-entry FIFO，追踪 2 个 tracked warp 的寄存器依赖链 |
| **知识存储（CT/TT）** | SM 级共享 | 所有 warp 共享同一份 CT 和 TT |
| **Stride 学习** | Per-PC（CT） | 任意 warp 的 demand load 均可参与；每 warp 追踪首个 active lane 的地址，第 2 次访问时确定 iter_stride |

**单次检测，全 SM 复用**：IMA 依赖链的结构性模式匹配（`LDG→IMAD.WIDE→LDG` 寄存器依赖 + IMAD.WIDE 参数直接提取）已具备足够选择性（BFS 全 SASS 验证零误检），无需多次观测积累 confidence。Tracked warp 的单次完整链观测即可写入 CT/TT，之后所有 64 个 warp 共享该知识。

训练包含两个阶段，分工不同：

1. **IMA 依赖链检测**（填充 CT/TT，由 2 个 tracked warp 完成）：tracked warp 在 issue 阶段观察到 `LDG→IMAD.WIDE→LDG` 的寄存器依赖链时立即写入 CT/TT。由于无需 confidence 积累，首次观测即完成训练。调度器 tie-breaking hint 确保 tracked warp 获得优先发射，加速链检测。

2. **Stride 学习**（CT 的 `iter_stride`，由任意 warp 完成）：每个 CT entry 维护 2 个 observation slot（硬件仅需 2×38 bit = 76 bit），记录最近 2 个 warp 的首次 active lane 地址。任意 warp 发出 demand index load 时，若该 warp 已有记录，计算地址差即为 iter_stride。**首个完成两次观测的 warp 确定 stride，之后所有 warp 共享**。IMA stride 是固定值（由数据结构 element size 决定），2 个 slot 足以快速收敛。这比仅依赖 tracked warp 更鲁棒——任意 warp 完成一次 outer iteration 即可学到 stride。

与 CPU 的本质差异：CPU 的 IMP/DMP 是 per-core 检测器，每个 core 为自己的线程独立学习（复用率 1:1）。GPU 的独特之处在于大量执行相同代码的 warp **共享同一份 pattern 知识**（复用率 1:64）——这是 SIMT 执行模型的天然产物。2 个 tracked warp 的训练开销被 64 倍分摊。

#### 4.1.1 FIFO 无效化机制

FIFO 的核心不变量：entry `{Rd, LOAD_RESULT}` 意味着"Rd 当前仍持有该 LDG 的返回值"。当此不变量被破坏时（Rd 被后续指令覆写或消费），必须及时 invalidate 对应 entry，否则会产生 false positive。

本设计提供两种等价的无效化机制，均可保证目标 workload 上的零误检：

**机制 A: Write Invalidation（写无效化）**

当任何非追踪指令（opcode ∉ {LDG, IMAD_WIDE}）的 `dst_reg` 匹配 FIFO 中某 entry 的 `dst_reg` 时，立即 invalidate 该 entry。

- 触发条件：`dst_reg` 被非追踪指令覆写
- 硬件：8 个 8-bit 并行比较器（与 FIFO 查找逻辑复用）+ invalidation 使能信号
- 优点：语义直接——"寄存器被覆写 → 值已变 → entry 无效"
- 特性：entry 的存活时间取决于该寄存器被覆写的时机。若中间有大量不涉及该寄存器的指令，entry 可能长期滞留——但这不影响正确性（FIFO 自然淘汰最旧 entry 作为兜底）

**机制 B: Read Detection（读检测）**

当任何非 IMAD.WIDE 指令的 `src_reg` 匹配 FIFO 中某 LOAD_RESULT entry 的 `dst_reg` 时，invalidate 该 entry。逻辑：如果一个 LDG 的结果被非 IMAD.WIDE 指令消费了，它就不可能再形成 `LDG→IMAD.WIDE→LDG` 依赖链。

- 触发条件：`dst_reg` 被非 IMAD.WIDE 指令作为 src 读取
- 硬件：8 个 8-bit 并行比较器 × src_reg 数量（通常 2-3 个 src）
- 优点：entry 在被消费时立即清理，FIFO 周转更快
- 特性：对 FIFO 压力的缓解效果更好（entry 在首次被非 IMA 消费时即回收）

**两种机制的等价性与选型**：

| 维度 | Write Invalidation | Read Detection |
|------|-------------------|----------------|
| 触发条件 | dst_reg 被覆写 | dst_reg 被非 IMAD.WIDE 读取 |
| 正确性 | ✅ 零误检（BFS/SSSP 全 SASS 验证） | ✅ 零误检（同上） |
| 硬件复杂度 | 低（复用查找比较器） | 中（需比较多个 src_reg） |
| FIFO 压力 | 中（entry 存活到被覆写） | 低（entry 在首次消费时回收） |
| 适用场景 | 通用，尤其适合 FIFO 较大时 | FIFO 较小时周转更快 |

**实现建议**：两种机制在目标 workload 上完全等价（因为所有 workload 的 IMAD.WIDE 都是 index load 结果的首个结构性消费者——中间不会被非 IMAD 指令先读取）。初始实现选择 **Read Detection**（默认）。理由：8-entry 的小 FIFO 对周转效率敏感——Read Detection 在 entry 被非 IMA 指令消费时立即回收，在 BFS ×4 展开体（copy 间 ~54 条指令间隔）中能更快腾出空间供后续 IMA 链检测。额外硬件开销（8 × 2-3 个 src_reg 比较器）在 FIFO 仅 8 entries 的规模下完全可接受。

**BFS SASS 实证**：

对 `bfs_linear_base.sm80.sass` 全部 14 条 IMAD.WIDE 逐条追踪，验证 FIFO 的检测准确性：

| 分类 | 数量 | 说明 |
|------|------|------|
| 正确检测为 IMA | 7 | 前序 2 条 + remainder 1 条 + ×4 展开 4 条 |
| 正确排除（src 不在 FIFO） | 6 | 线程 ID / 循环计数器 / warp 前缀和 |
| **无效化生效** | **1** | PC 0x0530: 若无无效化，R2 的旧 LDG entry 会导致误分类 |

**无效化生效的具体案例（PC 0x0530）**：

```
PC 0x0270: LDG.E R2, [R18.64]           // dists[src] → FIFO: {R2, LOAD_RESULT}
PC 0x02a0: ATOMG.E.CAS PT, R2, [R2]...  // Write-inv: R2 被 CAS 覆写 → invalidate
                                          // Read-det: R2 被 CAS 作为 src 读取 → invalidate
PC 0x03c0: IMAD.IADD R2, R2, 0x1, R11   // R2 被前缀和覆写 → 再次确认 R2 不在 FIFO 中
PC 0x0530: IMAD.WIDE R2, R2, R3, c[...]  // FIFO 查 R2 → 无命中 → 正确排除（不是 IMA）
```

两种机制在 PC 0x02a0 处均将旧 entry 清除——Write Invalidation 因 CAS 的 `dst_reg=R2` 覆写而触发；Read Detection 因 CAS 的 `src_reg=R2` 读取而触发。结果一致。

**结论**：无效化机制在 BFS 中将检测准确率从 7/8（87.5%）提升到 **7/7（100%）**。这验证了它作为 FIFO 基础语义的必要性——不是为罕见 corner case 打补丁，而是保证依赖追踪的正确性不变量。

### 4.2 Index Prefetch Unit (IPU)

**设计核心**：不维护 per-warp 状态表。当 warp 发出 index load 时，当前地址即时已知（来自 issue 阶段的地址寄存器），直接在当前地址基础上 + n×stride 发出 index prefetch。

**伪代码**：

Index prefetch 的核心逻辑已整合 per-PC stride learning，完整伪代码见 **§4.5.3**（`on_index_load_issue` 函数）。关键行为：

- 若 `stride_valid`：使用学到的 `iter_stride`（精确跨 1 个 outer iteration）
- 若 stride 尚未学到：**不发 prefetch**（前序 PC stride 永不收敛 → 自然过滤）

```python
# 简化版（完整版见 §4.5.3）
def on_index_load_issue(warp_id, PC, current_addr):
    if PC not in CT:
        return

    entry_a = CT[PC]

    # 预取门控：stride_valid 是唯一的激活条件
    # （IMA 链检测本身已具备足够选择性，无需额外 confidence/active 门控）
    if not entry_a.stride_valid:
        return  # stride 未学到 → 不发 prefetch

    # Per-lane 地址生成（对应 32 个 SIMT lane）
    prefetch_addrs = [current_addr[lane] + entry_a.iter_stride for lane in active_lanes]

    # 经 Index Coalescer 合并为 sector 请求（32B 粒度）
    sector_reqs = index_coalescer.coalesce_to_sectors(prefetch_addrs, active_mask)

    # 从 CT 快照 tt_idx[] 和 num_targets（PRB 直接存储，解耦 CT 生命周期）
    prb_id = PRB.allocate(
        tt_idx=entry_a.tt_idx,
        num_targets=entry_a.num_targets,
        remaining_sectors=len(sector_reqs)
    )
    if prb_id is None:
        stall()  # PRB 满，等待释放

    # 同一 index load 的所有 sector 请求共享同一个 PRB entry
    for req in sector_reqs:
        issue_l1_request(req.sector_addr, req.element_mask, prb_entry_id=prb_id, type=INDEX_PF)
        # 若 MSHR 满 → RESERVATION_FAIL: 放弃该 sector，PRB.remaining_sectors--，不生成 data PF
```

**为什么不需要 per-warp 状态表**：

传统 CPU prefetcher 需要记住每个 context 的 index 当前位置，因为在下一次 load 发出前它需要自主发出 prefetch。但 GPU 的情况不同：

- GPU 上 warp 数量极多（64/SM），且每次 warp 发出 index load 时地址都是已知的
- 在 load 发出的瞬间做 `current_addr + n×stride` 即可，无需"记住"之前的地址
- 唯一需要"跨时间"保留的状态是 PRB 中等待 index 值返回的条目

### 4.3 Data Prefetch Unit (DPU)（Sector-Based Architecture）

**完整数据流**：

```
                              Component 3: Data Prefetch Unit (DPU)
                              ════════════════════════════════════
                                    (Sector-Based Architecture)

  Index Prefetch        ┌─────────┐      ┌──────────────────┐      ┌─────────┐
  per-lane addrs ──────→│  Index   │─────→│      L1 Cache    │─────→│Response │
  (32 addrs)            │Coalescer │ ~4   │  (32B sectors)   │ resp │  FIFO   │
                        │(→sectors)│sector│                  │      │(depth=8)│
                        └─────────┘ reqs │  HIT: 直接返回   │      │         │
                         ↑ PRB alloc     │  MISS: MSHR→L2   │      │ 满→反压 │
                         │               │  MSHR满:阻塞等待 │      └────┬────┘
                    ┌────┴────┐          └──────────────────┘           │
                    │  PRB    │←── remaining_sectors==0   ─────────────│
                    │(32×18b) │                                         │
                    └─────────┘                                         ↓
                                                                 ┌───────────┐
                         TT ─── base,scale ───────────────→│   ACU     │
                                                                 │  32-wide  │
                                                                 │ 4sect/cyc │
                                                                 └─────┬─────┘
                                                                       │ 32×K addr
                                                                 ┌─────▼─────┐
                                                                 │   Data    │
                                                                 │ Coalescer │
                                                                 │ (buf=32)  │
                                                                 └─────┬─────┘
                                                                       │ M sector
                                                                       │ reqs
                                                                       ↓
                                                                  L1 Cache
                                                               (type=DATA_PF)
                                                              MSHR满→丢弃
```

#### 4.3.1 Prefetcher 作为 L1 Client（Sector 粒度）

Prefetcher 是 L1 cache 的一个独立 client（与 warp demand load 平级），请求/响应均以 **32B sector** 为粒度（对齐 A100 L1 架构）：

- **请求接口**：`{sector_addr, element_mask[8bit], prb_entry_id, type(INDEX_PF/DATA_PF)}`
  - 同一个 index load 的所有 sector 请求共享同一个 `prb_entry_id`（per-index-load PRB 设计）
- **响应接口**（仅 INDEX_PF）：`{prb_entry_id, sector_data[32B], element_mask[8bit]}`
  - L1 逐 sector 返回；每次返回触发 PRB `remaining_sectors--`

**L1 对两种 prefetch 类型的差异化处理**：

| 属性 | INDEX_PF | DATA_PF |
|------|----------|---------|
| **填充 L1 cache** | ✅ 是 | ✅ 是 |
| **返回数据给 prefetcher** | ✅ 是（sector_data + element_mask） | ❌ 否（fire-and-forget） |
| **MSHR 满时行为** | 放弃该 sector（RFAIL），PRB 标记 failed | 丢弃（隐式节流） |
| **L1 实现要求** | MSHR subentry 需携带 `prb_entry_id`；sector refill 时向 prefetcher 响应端口发送数据 | 仅常规 prefetch fill，无额外响应路径 |

INDEX_PF 是Index-Data Pipeline 的 Step 1（index refill → ACU → data prefetch），丢弃会导致整条 pipeline 断裂。DATA_PF 是终端操作（fill L1 即完成），丢弃仅损失一次 prefetch 机会。

#### 4.3.2 Prefetch Request Buffer (PRB)

PRB 跟踪在途 index prefetch，**每个 index load（而非每个 sector）占用 1 个 entry**。一次 index load 经 Index Coalescer 后产生 1~32 个 sector 请求，这些 sector 共享同一个 PRB entry，由 `remaining_sectors` 计数器跟踪完成进度。

**软件仿真 vs 硬件实现**：软件仿真中 PRB 存 `tt_idx[]` 快照以解耦 CT 生命周期（防止 CT 驱逐导致 ct_idx 失效）。**硬件实现**中 PRB 仅存 `ct_idx`（4-7 bit，见 §7.1），因为实测表明 CT 驱逐极少发生（BFS/SSSP/CC 用 5-6 entries，远小于 CT=32 容量）。SpMV（25/32）是唯一接近满的情况，但其 stride 收敛后 CT entry 不会被驱逐。若需要额外保护，可在 CT 中增加引用计数（1 bit per entry），防止有 pending PRB 引用的 entry 被驱逐。

| 字段 | 大小 | 说明 |
|------|------|------|
| valid | 1 bit | 有效位 |
| remaining_sectors | 6 bit | 剩余未返回 sector 数（0..32），由 Index Coalescer 初始化；每次 L1 返回 sector 时 -1；归零时释放 entry |
| tt_idx[K=3] | 9 bit | TT 索引快照（3 bit × 3 slot，TT 8 entries），分配时从 CT 拷贝 |
| num_targets | 2 bit | 活跃 target 数（1..3），分配时从 CT 拷贝 |
| **总计/条** | **18 bit** | |
| **条目数** | **32/SM** | 每个 index load 占用 1 个 entry |
| **总大小** | **72 bytes/SM** | |

- Per-index-load 设计大幅提升 entry 利用率：SpMV ×16 → 16 个并发 prefetch 仅占 16 entries（旧 per-sector 设计需 16×4=64 entries）
- BFS scatter burst（单次 index load 产生 20+ sectors）仅占 1 entry（旧设计占 20+ entries）
- PRB 满 → Index Coalescer stall（不丢弃）

**多 warp 并发压力分析**：

上述 per-index-load 优化解决了单次 index load 内部的 sector 膨胀问题，但 **多 warp 并发触发** 导致的 entry 累积是更严重的 sizing 挑战。CT/TT 是 SM 级共享的——任何 warp 的 index load 命中 CT 且 `stride_valid=true` 即触发 prefetch、占用 PRB entry。因此所有 64 warp 都会持续消耗 PRB。

**稳态占用推导**（基于第一性原理 + `small_1sm_cta5` 实测时序）：

- **输入速率**：SM 级单 LSU（`gpgpu_sub_core_model 1`，4 scheduler 竞争 1 个 ldst_unit）→ 最多 1 条 memory 指令/cycle。BFS 约 5 个 index PC / ~100 条 kernel 指令，index load 占 LSU 吞吐约 10–20%，即平均 ~0.1–0.2 条 index load 命中 CT/cycle。
- **entry 生命周期**：= `index_issue_to_refill` 时延。BFS/SSSP/BC-fwd/CC 的 p50 = 536–585 cycles，SpMV 的 p50 = 853 cycles（见 §2.5.1）。L1 miss → L2/HBM 路径下 entry 存活数百 cycle。
- **稳态占用** ≈ 输入速率 × 平均 lifetime。BFS: 0.15 × 560 ≈ **84 entries**；SpMV（16 个 index PC，LSU 中 index load 占比更高）: 稳态可达 **200+ entries**。

即便考虑缓解因素——多 warp 预取同一 index array 相邻区域时部分 prefetch 命中 L1（SpMV `index_hit_reserved = 41.5%`），使部分 PRB entry 快速释放（lifetime 降至 ~34 cycles）——稳态占用仍远超 32。

**实现方案：两阶段容量确定**：

原始 32 entry 是基于单 warp 场景的 SASS 静态分析估算值，多 warp 并发场景下严重不足。实现时采用两阶段方法：

1. **Phase 1（容量探测）**：PRB 使用大定长数组（如 1024 entries）+ free list，不设人为上限，确保所有目标 workload 都能无阻塞跑完。全部 workload 跑完后，统计 `prb_peak_occupancy` 确定真实需求上界。
2. **Phase 2（正式评估）**：基于 Phase 1 数据确定固定容量（取 peak occupancy 的 110–120% 作为安全裕量），用固定容量跑正式性能评估（此时有真实的 stall 反压行为）。

Phase 1 中 PRB 无限大意味着 prefetcher 永不因 PRB 满而 stall，prefetch 流量最大化，memory 子系统承受最大压力。因此 Phase 1 测到的 peak occupancy 是真实需求的**上界**——有背压时实际需求更低。但上界正是容量确定所需要的。

PRB 每 entry 仅需 ct_idx（4-7 bit），即使扩到 2048 entries 也只有 ~2 KB/SM，对比 register file 256 KB，硬件开销仍极小。

#### 4.3.3 Response FIFO 与反压

| 组件 | 深度 | 每条大小 | 总大小 |
|------|------|---------|--------|
| Response FIFO | 8 | prb_entry_id(5b) + sector_data(32B) + element_mask(8b) ≈ 34B | **~272 B** |

- 多个 sector 响应可能同时到达（L1 每 cycle 可返回 4 个 sector，对应 4 bank）
- FIFO 满 → 反压 L1 prefetcher 响应端口（不影响 demand load 响应路径）
- FIFO front 每次弹出最多 4 条 → 送入 ACU（匹配 32-wide ACU 吞吐，见 §4.3.4）
- 每次弹出时 ACU 读取 PRB entry 的 `tt_idx[]` 和 `num_targets`，并执行 `remaining_sectors--`；当 `remaining_sectors == 0` 时 invalidate PRB entry

**多 warp 并发压力分析**：

Response FIFO 的输入来自 L1 对 index prefetch 的 sector 级响应（最多 4 sectors/cycle），输出到 ACU（K=1 时 4 sectors/cycle，K=3 时 1.33 sectors/cycle）。

- **K=1**（BFS/SSSP/SpMV/CC）：输入输出速率匹配（4:4），FIFO 仅作 pipeline buffer，8 entry 足够。
- **K=3**（BC reverse）：ACU 消费速率降至 1.33 sectors/cycle，若 L1 以 4 sectors/cycle 持续返回，FIFO 约 3 cycles 打满（8/(4−1.33) ≈ 3 cycles）后反压 L1。
- **PRB 扩容的间接影响**：若 PRB 从 32 扩容到 128+（见 §4.3.2 多 warp 压力分析），更多 PRB entry 的 sector 响应可能在相近时间完成，形成 burst。此时 8 entry 可能不足以缓冲峰值到达速率。

实现时同样采用两阶段方法：Phase 1 用大 FIFO（如 128 entries）测 `rsp_fifo_peak_depth`，Phase 2 确定固定深度。

#### 4.3.4 Address Computation Unit (ACU) — 32-wide 并行（4 sectors/cycle）

A100 L1 每 cycle 可返回最多 4 个 sector（4 bank 并行）。为匹配 L1 返回带宽，ACU 采用 **32-wide** 设计，每 cycle 并行处理 **4 个 sector × 8 elements = 32 个元素**：

```python
# 每次从 Response FIFO 弹出最多 4 条 {prb_entry_id, sector_data[32B], element_mask[8bit]}
# 以下为单条处理逻辑（32-wide ACU 可并行处理 4 条，见下方硬件描述）

prb = PRB[prb_entry_id]
# 直接从 PRB 读取 tt_idx 快照（无需回查 CT，避免 CT 驱逐风险）
tt_idxs = prb.tt_idx[0:prb.num_targets]

prb.remaining_sectors -= 1
if prb.remaining_sectors == 0:
    prb.valid = False  # 所有 sector 已返回，释放 PRB entry

for k in range(prb.num_targets):  # K=1 大多数 workload, K=3 BC reverse
    tb = TT[tt_idxs[k]]
    for each element position i (0..7):
        if element_mask[i] == 1:
            value = sector_data[i*4 .. i*4+3]  # 32-bit int
            data_addr[i][k] = tb.base_addr + (value << log2(tb.scale))
```

**地址计算硬件**：

Data prefetch 的地址公式为 `data_addr = base + value × scale`。关键观察：**scale 永远是 2 的幂**（`sizeof(int)=4=2²`，`sizeof(double)=8=2³`），因此乘法可替换为位移：`data_addr = base + (value << log2(scale))`。

| 组件 | 位宽 | 数量 | 面积（相对） |
|------|------|------|-------------|
| Barrel shifter | 32-bit input, 3-bit shift | **32** | 极小 × 32 |
| 加法器 | 64-bit | **32** | 小 × 32 |
| 乘法器 | — | **0** | — |

**不需要乘法器**。shift amount 直接从 TT 的 scale 字段取 `log2(scale)`，零试探。32 组 shifter+adder 分为 4 组（每组 8 lane），由 element_mask 门控无效 lane。

- K=1（BFS/SSSP/SpMV/CC）：**4 sectors/cycle**（32 elements 并行）
- K=3（BC reverse）：**4 sectors per 3 cycles**（每 cycle 处理 4 sectors × 1 target，切换 3 次）

注意：如果后续扩展到 non-power-of-2 的 scale（如 struct packing 中 sizeof(struct)=12），则需要 8 个 32×32 乘法器。但图算法中所有 element 类型均为 int/float/double，scale ∈ {4, 8}，当前无此需求。

#### 4.3.5 Data Coalescer

接收 ACU 输出的 up to 32×K 个 data addresses（4 sectors × 8 elements × K targets），合并为 M 个 sector 请求：

| 组件 | 条目数 | 每条大小 | 总大小 |
|------|--------|---------|--------|
| Data Coalescer Buffer | 32 | sector_addr(~40b) + valid(1b) ≈ 6B | **~192 B** |

- IMA data 地址高度分散，coalescing 合并率低，M 接近有效元素数（≤ 32×K）
- 每 cycle dispatch **4 个** sector 请求到 L1（type=DATA_PF），匹配 LSU 端口带宽；MSHR 满时丢弃
- **一批 dispatch 完成后 invalidate 内部缓冲**，准备接收下一批
- ACU 可与 Data Coalescer dispatch 并行工作（双缓冲或 pipeline 设计），减少 Response FIFO stall

**One-to-Many 支持**：

| Workload | index array | target arrays | K |
|----------|------------|---------------|---|
| BFS | `column_indices[]` | `dists[]` | 1 |
| SSSP | `column_indices[]` | `dist[]` | 1 |
| SpMV | `Aj[]` | `x[]` | 1 |
| BC forward | `column_indices[]` | `depths[]`, `path_counts[]` | 2 |
| BC reverse | `column_indices[]` | `depths[]`, `path_counts[]`, `deltas[]` | 3 |
| CC hook | `column_indices[]` | `comp[]` | 1 |

设计 K=3 即可覆盖所有目标 workload。

**Data Prefetch 带宽风险**：

Data prefetch 的地址由 index 值决定，通常高度分散（IMA 的本质特征）。最坏情况下的带宽放大：

| 参数 | 值 | 说明 |
|------|---|------|
| ACU 每批处理的 sector 数 | 4 | 32-wide ACU 匹配 L1 4-bank 返回带宽 |
| 每批有效 prefetch 请求 | 最多 32 | 4 sectors × 8 elements，由 element_mask 门控 |
| Coalescing 后 sector 请求 | ~24-32 | IMA 地址分散，coalescing 合并率低 |
| Target array 数（K） | 1-3 | BFS K=1, BC reverse K=3 |
| 每批 ACU 输出产生的 data prefetch | ~24-96 sectors | 24-32 × K |

**风险评估**：32-wide ACU 每批处理 4 个 sector 响应，最坏情况（K=3、地址高度分散）可产生 ~96 条 data prefetch sector 请求。但 4 sectors/cycle dispatch + MSHR 隐式节流提供了天然背压。

**缓解措施**（当前版本）：
1. MSHR 满时 data prefetch 自动丢弃（隐式节流）
2. `stride_valid` 门控：stride 未学到时不发 prefetch，避免训练期产生无用请求
3. 实际影响需在第一轮实验中量化——如果带宽成为瓶颈，在 Throttle Controller 中增加带宽感知机制（见 §4.4）

### 4.4 Throttle Controller (TC)

**当前版本**：IMA 链检测的结构性模式匹配（`LDG→IMAD.WIDE→LDG` 寄存器依赖 + IMAD.WIDE 参数直接提取）已具备足够选择性，**不需要 confidence 门控**。预取激活由 `stride_valid` 自然门控——stride 未学到时不发 prefetch，前序链（仅执行一次的 PC）stride 永不收敛，自动过滤。

**隐式节流**：Data prefetch 在 MSHR 满时丢弃（fire-and-forget），这提供了天然的背压机制——当 L1→L2 带宽紧张时，data prefetch 自动降级。

**后期扩展方向**：

| 机制 | 说明 | 参考 |
|------|------|------|
| **Misprediction Counter** | 统计 prefetch 发出但从未被 demand load 命中的比例；超阈值则暂停对应 pattern 的 prefetch | IMP / CAPS [Koo 2018] |
| Early Eviction Rate | 跟踪 prefetch 带入的 cache line 被使用前就被驱逐的比例；超阈值则降低 prefetch 频率 | MT-Prefetch / WASP |
| 动态 Prefetch Depth | 根据 accuracy 自适应调整 prefetch distance（1→4 个 outer iteration） | DMP |
| **带宽感知节流** | 监控 NoC/L2 interconnect 利用率或 MSHR 占用率；高负载时暂停 prefetch；低负载时恢复 | 新增（应对 §4.3 中 data prefetch 带宽风险） |

### 4.5 Loop Unrolling、MLP 与 Iteration Stride Tracker (IST)

#### 4.5.1 GPU 的 Non-Blocking Load 与 MLP

GPGPU-Sim 源码验证（`shader.cc` scoreboard 机制）：LDG 是 **non-blocking** 的——warp 发出 `LDG Rd, [addr]` 后，scoreboard 将 Rd 标记为 pending，但 warp 可继续发射不依赖 Rd 的后续指令。仅当下一条指令的源寄存器与 pending 寄存器冲突（RAW hazard）时，warp 才 stall。

关键代码路径：`scheduler_unit::cycle()` → `scoreboard->checkCollision(next_inst)` → 检查 `next_inst` 的源寄存器是否在 `reg_table` 中 → 若无冲突则 `issue_warp()`。

这意味着 compiler 的 loop unrolling **确实创造了 Memory-Level Parallelism (MLP)**：

```
// SpMV ×16 unrolling 的实际发射序列
LDG R0,  [index_addr_0]    → R0 pending, 继续
LDG R2,  [index_addr_1]    → R2 pending, 继续
...
LDG R30, [index_addr_15]   → R30 pending, 16 个 index load 全部 in-flight!
IMAD.WIDE R32, R0, ...     → R0 是 pending → STALL（等待 refill 返回）
```

#### 4.5.2 固定 n 的冗余分析

**关键前提：BFS 的 ×4 展开与 SpMV 的 ×16 展开本质不同**

表面上两者都叫"unrolling"，但其结构差异决定了 MLP 行为和 prefetch 策略的根本不同：

| 特性 | BFS/SSSP/BC/CC ×4 | SpMV ×16 |
|------|-------------------|----------|
| 展开方式 | **功能性展开**（functional expansion） | **内存级展开**（memory-level unrolling） |
| 相邻 INDEX LOAD 间隔 | ~864 bytes / ~54 条指令（含 CAS + worklist 代码） | ~16 bytes / ~1 条指令（纯连续 LDG） |
| in-flight index loads | ≤ 1（间隔过大，前一个 load 已返回） | 16 个同时 in-flight（MLP=16） |
| 展开的实质 | 4 份独立的"CAS + 写邻居队列"代码块 | 16 条 LDG 紧密排列，单次外层迭代消费 16 个元素 |

**BFS 的 SASS 结构**（摘自 `bfs_linear_base.sm80.sass`，`.L_x_20` 展开循环）：

```
PC 0x0640: INDEX LOAD (copy 1)
  ...~54 条指令：CAS + worklist update + branch...
PC 0x09a0: INDEX LOAD (copy 2)    ← 距 copy 1 约 0x360 bytes = 864 bytes
  ...~54 条指令：CAS + worklist update + branch...
PC 0x0d00: INDEX LOAD (copy 3)
  ...~54 条指令...
PC 0x1060: INDEX LOAD (copy 4)
```

由于每个 copy 之间有 54 条指令的 CAS + worklist 代码，当 copy 2 的 INDEX LOAD 发出时，copy 1 的 load 在代表窗口中通常已完成 refill——这 4 个 INDEX LOAD **不会同时 in-flight**，不创造 MLP。展开的目的是减少循环开销（branch + counter），而非创造并行度。

**SpMV 的 SASS 结构**（摘自 `spmv_base.sm80.sass`，`.L_x_7` ×16 展开循环）：

```
PC 0x03d0: INDEX LOAD [0]     ←┐
PC 0x03e0: INDEX LOAD [1]      │
PC 0x03f0: INDEX LOAD [2]      │ 16 条 LDG 在 ~12 条指令内连续发出
PC 0x0400: INDEX LOAD [3]      │ 全部 in-flight，MLP = 16
...                            │
PC ~0x04xx: INDEX LOAD [15]   ←┘
... (然后才是 IMAD.WIDE + DATA LOAD 序列)
```

16 个 INDEX LOAD 几乎没有间隔，warp 在发出第 1 个 LDG 后遇到 RAW hazard 前，会连续发出所有 16 个——这是真正的**内存级并行**。

**n=3 固定深度的实际含义**：

对于 BFS ×4，当 warp 执行第 j 个 copy（j=0,1,2,3）时，n=3 的 prefetch 目标是第 j+3 个元素。由于相邻 copy 之间有 54 条指令的间隔，demand load 不会通过 MLP 提前发出；j+3 的目标几乎必然落在"下一个 outer iteration 的窗口内"——有效。

对于 SpMV ×16，n=3 时只有第 j=13,14,15 个 load 的 prefetch 目标落在下一个窗口；前 13 个的目标仍在当前窗口内，而这 13 个 demand load 已经通过 MLP 同时 in-flight——冗余。

如果使用固定 prefetch depth n=3，当 warp 执行 unroll 窗口 [0..U-1] 中第 j 个元素时，prefetch 目标为第 j+3 个元素：

- 若 `j+3 < U`（窗口内）：demand load 已通过 MLP 发出 → **index prefetch 冗余**（MSHR merge，不产生额外流量）
- 若 `j+3 ≥ U`（跨窗口）：目标在下一个 unroll 窗口 → **prefetch 有效**

| Workload | Unroll factor U | 展开类型 | 窗口内冗余 | 跨窗口有效 | 有效比例 |
|----------|----------------|---------|-----------|-----------|---------|
| BFS      | 4              | 功能性展开（间隔 864B） | 1/4 | 3/4 | **75%** |
| SSSP     | 4              | 功能性展开（间隔 ~864B） | 1/4 | 3/4 | **75%** |
| SpMV     | 16             | 内存级展开（间隔 ~16B） | 13/16 | 3/16 | **19%** |
| BC       | 4              | 功能性展开（间隔 ~864B） | 1/4 | 3/4 | **75%** |
| CC       | 4              | 功能性展开（间隔 ~864B） | 1/4 | 3/4 | **75%** |

SpMV 的 19% 有效率不可接受——81% 的 prefetch 仅产生 MSHR merge（虽无害但浪费检测和发射资源）。

**结论：per-PC stride learning 的核心动机来自 SpMV，而非 BFS/SSSP/BC/CC。** 对于 BFS 等功能性展开 workload，固定 n=3 已经达到 75% 有效率，基本可接受；对于 SpMV ×16 真正的内存级展开，必须通过 per-PC stride learning 将 prefetch depth 对齐到整个 outer iteration（stride = 16 × 4B = 64B），才能将有效率从 19% 提升到 100%。

**附带效果：前序链自然过滤**。前序代码（如 BFS 的 `worklist→row_offsets`、`row_offsets→column_indices` 初始偏移）中的 IMA PC 每个 warp 仅执行一次，stride learning 需要同一 warp 命中同一 PC 两次才能收敛 → `stride_valid` 永远为 false → 不发出 prefetch。这消除了前序链的无效 prefetch，无需任何额外机制。

#### 4.5.3 Iteration Stride Tracker (IST) — Per-PC Stride Learning

**核心思路**：不用固定 n，而是让每个 CT entry 学习自己的 **iteration stride**——即同一 PC 在同一 warp 连续两次触发之间的地址差。这个差值恰好等于 `U × element_stride`（U 为该 PC 所属展开版本的 unroll factor）。

**CT 扩展字段**：

| 新增字段 | 大小 | 说明 |
|---------|------|------|
| `stride_obs[2]` | 2×(6+32) = 76 bit | 2 个 observation slot：{warp_id(6b), first_addr(32b, sector-aligned)}。任意 warp 首次访问记录地址，同 warp 第 2 次确定 stride。IMA stride 为固定值，2 slot 足以快速收敛 |
| `iter_stride` | 16 bit | 学到的 iteration stride（bytes）（per-entry），±32KB 覆盖所有 IMA stride |
| `stride_valid` | 1 bit | stride 是否已学到（per-entry） |
| `stride_speculative` | 1 bit | stride 是否为 speculative（通过 element size 推断，尚未经真实观测确认） |
| **额外存储** | **~12 B/entry** | 32 entries × 12B = **~384 B**（含 stride obs） |

注：`tracked_warp_ids[2]` 已提升为 SM 级全局状态（与 Chain Detector (CD) FIFO 共享），不占用 per-entry 空间。Stride 学习与 chain 检测的分工不同——chain 检测仅由 tracked warp 驱动，但 stride 学习由**任意 warp** 的 demand load 触发。

**学习算法**：

```python
def on_index_load_issue(warp_id, PC, current_addr, lane_id, cycle):
    if PC not in CT:
        return

    entry_a = CT[PC]

    # === Stride Learning (任意 warp 参与) ===
    obs = find_obs_for_warp(entry_a, warp_id)

    if obs is None:
        # 首次访问：记录该 warp 的 first-lane 地址（硬件仅 2 个 slot）
        if entry_a.num_stride_obs < 2:  # W=2 observation slots
            entry_a.stride_obs[entry_a.num_stride_obs++] = {
                warp_id, lane_id, current_addr, cycle
            }
        # Speculative stride: 可从 element size 推断（见 §4.5.4）
        if not entry_a.stride_valid and speculative_hint != 0:
            entry_a.iter_stride = speculative_hint
            entry_a.stride_valid = True
            entry_a.stride_speculative = True
        return

    # Dedup: 同 cycle 的多个 sector 不重复计算
    if obs.last_cycle == cycle: return
    obs.last_cycle = cycle

    # Lane 一致性: 同一 warp 必须用同一 lane 保证地址序列可比
    if obs.lane_id != lane_id: return

    delta = current_addr - obs.last_addr
    obs.last_addr = current_addr
    if delta == 0: return

    if not entry_a.stride_valid:
        # 首个 warp 的第 2 次观测 → stride 确定
        entry_a.iter_stride = delta
        entry_a.stride_valid = True
        entry_a.stride_speculative = False
    elif entry_a.stride_speculative:
        # Speculative → 用真实观测确认或修正
        entry_a.iter_stride = delta
        entry_a.stride_speculative = False
    # 已确认的 stride 不再更新（防止跨 CTA warp 复用导致的抖动）

    # === Prefetch ===
    if not entry_a.stride_valid:
        return  # stride 未学到 → 不发 prefetch（前序 PC stride 永不收敛 → 自然过滤）

    # Per-lane 地址生成（对应 32 个 SIMT lane）
    prefetch_addrs = [current_addr[lane] + entry_a.iter_stride for lane in active_lanes]

    # 经 Index Coalescer 合并为 sector 请求（32B 粒度，见 §4.3）
    sector_reqs = index_coalescer.coalesce_to_sectors(prefetch_addrs, active_mask)

    # 从 CT 快照 tt_idx[] 和 num_targets 到 PRB（解耦 CT 生命周期）
    prb_id = PRB.allocate(
        tt_idx=entry_a.tt_idx,
        num_targets=entry_a.num_targets,
        remaining_sectors=len(sector_reqs)
    )
    if prb_id is None:
        stall()  # PRB 满，等待释放

    # 同一 index load 的所有 sector 请求共享同一个 PRB entry
    for req in sector_reqs:
        issue_l1_request(req.sector_addr, req.element_mask, prb_entry_id=prb_id, type=INDEX_PF)
```

**Per-PC stride 精确区分不同展开版本**：

SpMV 的 Duff's device 包含 ×16/×8/×4/×1 四个版本，共 30+ 个 CT entry。但每个 entry 学到的 stride 精确反映其所属版本：

| PC 所属版本 | 学到的 iter_stride | 含义 |
|------------|-------------------|------|
| ×16 中的 PC | 16 × 4 = 64 bytes | 跨 1 个 ×16 窗口 |
| ×8 中的 PC  | 8 × 4 = 32 bytes  | 跨 1 个 ×8 窗口 |
| ×4 中的 PC  | 4 × 4 = 16 bytes  | 跨 1 个 ×4 窗口 |
| ×1 中的 PC  | 1 × 4 = 4 bytes   | 跨 1 个 ×1 迭代 |

每个版本的 prefetch 都恰好跨过自己的 unroll 窗口边界 → **100% 有效**，零冗余。

**训练速度**：stride learning 需要任意 warp 的同一 PC demand load 触发两次（同一 warp、同一 lane），即该 warp 经历 1 个完整的 outer loop iteration。由于所有 64 个 warp 都可以贡献观测，实际上首个完成 outer iteration 的 warp 即可确定 stride。对于 BFS 内循环（邻居遍历），这通常在 kernel 启动后数百 cycles 内完成。

**任意 warp stride 的合法性**：所有 warp 执行相同的 kernel 代码，unroll 结构完全相同，只是数据地址不同。因此一个 warp 学到的 stride 对所有 warp 有效——`iter_stride` 是代码结构属性，不是数据属性。

#### 4.5.4 Speculative Stride — 跳过学习延迟

在正常 stride learning 中，prefetcher 需要等待至少一次 outer loop iteration 才能确定 stride。��于短循环或 warp 快速退出的场景，这一延迟可能导致 prefetcher 在 kernel 的大部分运行时间内���于静默状态。

**Speculative stride** 允许在**首次 demand load** 时即设置 `stride_valid=true`，跳过学习延迟：

- **推断来源**：index LDG 的 `sizeof(element)` 可在 chain detection 阶段从 IMAD.WIDE 的 `scale` 操作数推断。例如，`scale=4`（32-bit index）意味�� `iter_stride = 4 bytes`（×1 版本）或 `4 × U bytes`（×U 展开版本）。对于 ×1 版本，speculative stride = `scale` 即可。
- **确认/修��**：后续任意 warp 的真实观测会自动替换 speculative 值（`stride_speculative → false`）。
- **风险极低**：对 ×1 展开，speculative 值精确；对 ×U 展开，speculative 值偏小（产生 in-window 冗余 prefetch，合并到 MSHR 不产生额外带宽），真实观测修正后恢复 100% 有效。

**Tracked Warp 调度器优先 Hint**：

Tracked warp 承担 IMA 链检测任务，其执行进度直接决定 CT/TT 何时填充完成。为加速训练收敛，调度器对 tracked warp 施加**轻量级 tie-breaking 优先**：

| 属性 | 说明 |
|------|------|
| **机制** | Tracked warp 标记 1-bit `priority` 位。调度器在选择下一个发射的 warp 时，若多个 warp 同时 ready，优先选择 `priority=1` 的 warp |
| **不阻塞其他 warp** | 这不是排他性调度——只影响 ready warp 之间的 tie-breaking 顺序。若仅有一个 warp ready，无论是否为 tracked warp 都立即发射 |
| **参考** | CAPS [Koo et al. 2018] 的 Prefetch-Aware Scheduler (PAS)：leading warp 获得 1-bit priority hint，调度器 tie-breaking 时优先选择。本设计复用相同思路，但 tracked warp 的选择逻辑不同（前两个发出 LDG 的 warp，而非 CAPS 的 per-CTA 进度最快 warp） |
| **效果** | Tracked warp 更快完成 chain detection → CT/TT 更快填充 → 结合 speculative stride 或其他 warp 的 stride 学习，prefetch 更早启动 |
| **硬件开销** | 1 bit/SM（存储在 tracked_warp_ids 旁边）+ 调度器比较逻辑中增加一个 OR 门 |

### 4.6 表生命周期管理

Prefetcher 的各状态表在不同事件下需要清理或重置，以避免跨 kernel 的陈旧数据或 warp 退出后的悬挂状态。

| 事件 | 清理范围 | 理由 |
|------|---------|------|
| **Kernel Launch** | 清空 CT + TT + Register FIFO + PRB + Response FIFO + Data Coalescer Buffer + tracked_warp_ids[2] + training_frozen=false | 新 kernel 的 PC 空间、base address、scale 全部不同，旧数据完全无效；冻结标志复位以重新启动训练 |
| **训练冻结（两个触发条件）** | 设置 `training_frozen = true`：(1) 不选择新 tracked warp，(2) CD FIFO 停止追踪指令，(3) 调度器 priority hint 关闭 | **触发条件 1**：Stride 收敛后 `check_freeze()` 检查 CT 中所有有效 entry 均 `stride_valid=true`——正常完成路径，通常在第 1-2 次 outer iteration 后触发。**触发条件 2**：任一 tracked warp EXIT——warp 生命周期结束。两条路径均可触发冻结。 |
| **Tracked Warp EXIT** | 清空该 warp 在 Register FIFO 中的 entries + 永久冻结（见上） | 对 iterative graph algorithms，tracked warp EXIT 通常发生在条件 1 已触发之后 |
| **非 Tracked Warp EXIT** | 无额外操作 | 非 tracked warp 的指令不影响 FIFO，无需清理 |
| **CTA 完成** | 无额外操作 | CTA 完成时其所有 warp 已 EXIT（已触发上述清理）；CT/TT 为 SM 级共享，不受 CTA 生命周期影响 |

**实现要点**：

1. **Kernel Launch 清表**：可通过 `memset` 一次性清零所有表（CT ~544B + TT ~80B + CD FIFO ~300B + PRB ~1.0KB），单 cycle 内可完成。

2. **训练冻结**：两条路径——(a) 每次 stride 收敛时 `check_freeze(ct)` 检查 `all_stride_valid()`；(b) tracked warp EXIT 时永久冻结。冻结后 prefetcher 仍正常工作（CT/TT 已填充完成，仅依赖 stride_valid 门控的 address-triggered prefetch），但 FIFO 写入/查找的动态功耗降为零。PRB 无 warp_id 字段——条目由 L1 sector 响应触发 `remaining_sectors--`，归零时自动回收。

---

## 5. 具体执行流示例

### 5.1 BFS：column_indices[offset] → dists[dst]

```
=== 训练阶段（前 3 次观测）===

Warp 0, 迭代 0:
  ISSUE: LDG.E R0, [R16.64]                    PC=0x0650  (column_indices[offset])
    → register_producer[warp0][R0] = {LOAD_RESULT, PC=0x0650}

  ISSUE: IMAD.MOV.U32 R11, RZ, RZ, 0x4         PC=0x0660
    （常量加载，不入 FIFO——scale 在 IMAD.WIDE issue 时从 RF 直接读取）

  ISSUE: IMAD.WIDE R2, R0, R11, c[0x0][0x178]  PC=0x0670
    → R0 由 LOAD 产生 → 确认 IMA 地址计算
    → scale=RF[R11]=4, base=c[0x0][0x178]=dists_base（直接从操作数获取）
    → register_producer[warp0][R2] = {IMA_ADDR_COMPUTE, index_PC=0x0650, scale=4, base=dists_base}

  ISSUE: LDG.E R4, [R2.64]                     PC=0x0680  (dists[dst])
    → R2 由 IMA_ADDR_COMPUTE 产生 → 确认完整依赖链!
    → TT CAM lookup (dists_base, 4) → miss → 分配 tb_idx=0
    → CT[0x0650] = {data_PC=0x0680, tt_idx=[0], num_targets=1}
    → TT[0] = {base_addr=dists_base, scale=4}  ← 首次检测即写入，无需 confidence

  （tracked warp 继续执行，stride learning 记录 last_addr...）

  Tracked Warp 0, 迭代 1:（同一 PC 第二次触发）
    → entry_a.iter_stride = current_addr - last_addr → stride_valid = True!
    → 此后所有 warp 对 PC=0x0650 的 prefetch 均生效

=== 展开副本自动归并 ===

Tracked Warp 0, 展开版第 2 份:
  ISSUE: LDG.E R0, [R16.64+0x4]                PC=0x09c0  (column_indices[offset+1])
  ISSUE: IMAD.WIDE R2, R0, R11, c[0x0][0x178]  PC=0x09e0
  ISSUE: LDG.E R4, [R2.64]                     PC=0x09f0  (dists[dst_1])
    → TT CAM lookup (dists_base, 4) → hit → tb_idx=0（已存在）
    → CT[0x09c0] = {data_PC=0x09f0, tt_idx=[0], num_targets=1}
    → 同一个 TT[0] entry（归并）

=== 预取阶段 ===

Warp 10, 迭代 i:
  ISSUE: LDG.E R0, [R16.64]                    PC=0x0650, addr=0xA000
    → CT lookup: PC=0x0650 → stride_valid=True, iter_stride=16
    → Step 1: issue index prefetch at 0xA000 + 16 = 0xA010  (stride = 4 elements × 4B)
    → PRB ← {tt_idx=[0], num_targets=1, remaining_sectors=N}（N 个 sector 请求共享同一 prb_entry_id）

  ... (index prefetch refill 返回；在代表窗口中通常是数百 cycles later，而不是固定 200 cycles) ...

  Index prefetch 返回: addr=0xA010, value=42857 (= column_indices[offset+4])
    → Step 2: data_addr = dists_base + 42857 × 4 = dists_base + 0x29FA4
    → issue data prefetch at dists_base + 0x29FA4

  ... (data prefetch refill 到达；在代表窗口中同样通常是数百 cycles later，具体取决于 workload 与窗口拥塞) ...

Warp 10, 迭代 i+1 outer iteration:
  ISSUE: LDG.E R0, [R16.64]                    PC=0x0650, addr=0xA010
    → 该 warp 访问 dists[column_indices[offset+4]]
  ISSUE: LDG.E R4, [R2.64]                     PC=0x0680, addr=dists_base + 0x29FA4
    → L1 HIT ✓ (已被 prefetch 填充)
```

### 5.2 BC reverse：1 index → 3 data prefetch

```
CT entry (index_PC = column_indices 的 PC):
  tt_idx = [0, 1, 2]
  num_targets = 3

TT[0] = {base_addr: depths_base,      scale: 4}   # depths[dst]
TT[1] = {base_addr: path_counts_base, scale: 4}   # path_counts[dst]
TT[2] = {base_addr: deltas_base,      scale: 8}   # deltas[dst] (double)

PRB entry: {tt_idx=[0,1,2], num_targets=3, remaining_sectors=N}

Index prefetch 返回 value=1234:
  ACU 读 PRB → num_targets=3, tt_idx=[0,1,2]（快照，无需回查 CT）
  → 对 k=0: TT[0] → data prefetch #1: depths_base + 1234 × 4
  → 对 k=1: TT[1] → data prefetch #2: path_counts_base + 1234 × 4
  → 对 k=2: TT[2] → data prefetch #3: deltas_base + 1234 × 8
  → PRB.remaining_sectors--; if 0 → invalidate
```

---

## 6. 设计决策记录

| 决策 | 选择 | 理由 | 备选方案 |
|------|------|------|---------|
| **检测标准** | 寄存器依赖链（LDG→ALU→LDG） | 泛化能力强，不假设特定指令 | 纯 IMAD.WIDE 匹配（更简单但泛化差） |
| **Pattern 唯一标识** | `(data_base, scale)` 来自 IMAD.WIDE 常量操作数 | 自动归并 loop unrolling（SpMV 30+ PC → 1 entry）；直接提取计算参数 | Per-PC 独立追踪（表项膨胀严重） |
| **Index Tracker 粒度** | Address-triggered 即时方案 + PRB（L1 client 模式） | 无需 per-warp 状态表（64 warp × N pattern 开销大）；GPU load 发出时地址即时已知 | Per-warp 全量状态表（3.2 KB/SM） |
| **预取层级** | L2 → L1 | L2 hit rate 66–78%，瓶颈在 L1 miss | L2 → HBM prefetch（已有较高 hit rate，增量小） |
| **覆盖 Pattern** | I + II（Linear & Frontier Gather） | 覆盖 BFS/SSSP/BC/SpMV 的核心 IMA 链 | 扩展到 III（timeliness 几乎为零）；IV（物理不可预取） |
| **ISA 扩展** | 不需要（纯 hardware detection） | 保持通用性，无需重编译；对比 COMPASS 等 software hint 方案 | 编译器标注 IMA 组（更精确但破坏通用性） |
| **节流方式** | `stride_valid` 门控 + MSHR 隐式节流 | IMA 链检测选择性已足够，无需 confidence；stride 未学到时不发 prefetch 自然过滤前序链 | Confidence counter（增加复杂度但无收益）；Misprediction counter（后期扩展） |
| **Prefetch depth** | Per-PC iter_stride（自适应学习 + speculative stride 快启动） | lookahead 必须绑定到 per-PC 的 outer-iteration 窗口。固定 n 在 SpMV ×16 下 81% 冗余，per-PC stride 100% 有效。Speculative stride 通过 element size 推断，可在首次 demand load 即启动 prefetch（§4.5.4）。前序链（stride 不收敛）自然过滤 | 固定 n=max(U)（需预知 U）；TT distinct_pc_count（简单但对 Duff's device 高估） |
| **Max target arrays K** | K=3 | 覆盖 BC reverse（最大 case：3 个数组） | K=1（更简单但不覆盖 BC） |
| **Index prefetch 返回数据路由** | L1 client 模式（PRB entry ID 随请求穿过 L1/MSHR） | PRB 18 bit/entry（72B/SM）；per-index-load 设计，直接存 tt_idx[] 快照避免 CT 驱逐风险 | MSHR 标记（不覆盖 L1 HIT）；独立 Pending Buffer + CAM |
| **Prefetch coalescing** | Prefetcher 自带 Index/Data Coalescer（32B sector 粒度） | 对齐 A100 L1 sector 架构；LD/ST 流水线 coalescing unit 与指令结构性绑定 | 复用 LD/ST coalescer（不可行）；per-lane 独立请求（MSHR 压力过高） |
| **MSHR 满时行为** | Index prefetch: 放弃该 sector（RFAIL）；Data prefetch: 丢弃 | 阻塞会 stall 整个 prefetch queue 导致时效性下降；放弃仅损失该 sector 的 data PF 机会，其他 sector 不受影响 | 阻塞等待（初始设计，但 stall 副作用过大） |
| **Register FIFO 范围** | SM 级共享 FIFO（2 tracked warps, depth=20） | 去除 confidence 后单次链观测即可训练；2 tracked warp 用于链检测，stride 学习由任意 warp 完成；硬件从 3 KB 降至 ~120 B | Per-warp FIFO（64×8×6B=3KB，96% 浪费）；单一 tracked warp（容易在首次 iteration 后 EXIT） |
| **FIFO 无效化** | Read Detection（默认），Write Invalidation（备选） | 两种机制在目标 workload 上等价（零误检）；Read Detection 对 8-entry 小 FIFO 周转更快 | 无无效化（87.5% 准确率，存在 false positive 风险） |
| **调度器辅助** | Tracked warp 1-bit tie-breaking priority hint | 加速 stride 收敛和链检测，不阻塞其他 warp | 无调度器辅助（训练慢但简单）；CAPS 式强优先调度（影响其他 warp 延迟） |
| **地址计算并行度** | 32-wide 并行 ACU（4 sectors/cycle，匹配 L1 4-bank 返回带宽） | 避免 ACU 成为瓶颈；32 shifter+adder 面积极小 | 8-wide（1 sector/cycle，L1 高带宽时积压 Response FIFO）；串行（太慢） |
| **多响应并发** | Response FIFO（depth=8）+ 反压 L1 | 多个 sector 响应可能同时到达；反压不影响 demand load 路径 | 丢弃溢出响应 |

---

## 7. 硬件预算估算

### 7.1 Per-SM 存储开销

| 组件 | 条目数 | 每条大小 | 总大小 | 说明 |
|------|--------|---------|--------|------|
| **CT** (Chain Table) | 32 | index_pc_tag(24b) + tt_idx[3](ceil(log₂TT)×3) + num_targets(2b) + valid(1b) + iter_stride(16b) + stride_valid(1b) + stride_speculative(1b) + stride_obs[2](2×38b=76b) + LRU(5b) ≈ **17 B** | **~544 B** | 仅存 index_pc 作为 key；data_pc/imad_pc 在 CD 检测阶段完成使命后不存入 CT。stride_obs 精简为 2 slot（IMA stride 固定，2 个 warp 观测即可收敛）。覆盖 SpMV 30+ unrolled PC |
| **TT** (Target Table) | 8 | base_addr_tag(32b) + scale(3b) + valid(1b) ≈ **5 B** | **~40 B** | 每 entry 存单一 target 的 (base, scale)；one-to-many 由 CT 的 tt_idx[] 指向多个 entry |
| **PRB** (Prefetch Request Buffer) | 1024 | valid(1b) + ct_idx(ceil(log₂CT)) ≈ **4–7 bit** | **~1.0 KB** | 仅存 CT 表项索引。L1 fill 返回时携带 PRB entry ID + index 数据，通过 ct_idx 查 TT 即可计算 data address，无需冗余存储 tt_idx 快照或 warp_id |
| **Register FIFO** (CD) | 1 × 20 entries | dst_reg(8b) + type(2b) + PC(24b) + ima_info(可选) ≈ **15 B** | **~300 B** | SM 级共享 FIFO，追踪 2 个 tracked warps。深度 20（SpMV ×16 峰值 17 + 安全裕量） |
| **SM 全局状态** | 1 | tracked_warp_ids[2](12b) + priority(1b) + training_frozen(1b) | **~2 B** | 2 个 tracked warp 标识 + 调度器 hint + 训练冻结标志 |
| **总计（默认配置）** | | | **~1.9 KB/SM** | 占 L1D (128 KB) 的 1.5% |

**Storage Budget Sensitivity 四档位**（用于论文 sensitivity 实验）：

| 档位 | CT | TT | PRB | CD FIFO (固定) | 总计/SM | 占 L1D |
|------|---:|---:|----:|:--------------:|-----------:|:------:|
| **S1 (不够)** | 8×17B=136B | 4×5B=20B | 256×1B=256B | 300B | **712 B** | **0.54%** |
| **S2 (勉强)** | 16×17B=272B | 8×5B=40B | 512×1B=512B | 300B | **1.1 KB** | **0.86%** |
| **S3 (充裕/默认)** | 32×17B=544B | 16×5B=80B | 1024×1B=1.0KB | 300B | **1.9 KB** | **1.5%** |
| **S4 (过剩)** | 64×17B=1.1KB | 32×5B=160B | 2048×1B=2.0KB | 300B | **3.6 KB** | **2.7%** |

**CT 容量设计依据**：

CT 的 32 entry 由 loop unrolling 分析确定——compiler 的循环展开直接决定了同一逻辑 load 对应多少不同的 SASS PC：

| Workload | Unrolled index PCs | 展开方式 | 说明 |
|----------|-------------------|---------|------|
| BFS | ~5 | ×4 + remainder | 4 份展开体 + 1 份尾部 |
| SSSP | ~5 | ×4 + remainder | 同 BFS |
| SpMV | **30+** | ×16 + ×8 + ×4 + ×1 | 多级 Duff's device 风格展开，sizing bottleneck |
| BC reverse | ~5 | ×4 + remainder | one-to-many 不增加 CT 占用（共享 index_PC） |
| CC hook | ~5 | ×4 + remainder | 同 BFS |

SpMV 的 30+ PC 是 sizing bottleneck。32 entry 覆盖所有已分析 workload，但余量有限（~2 空闲 entry）。如目标扩展到更激进展开的 kernel，可扩展至 48 或 64 entry（每 entry ~17B，增量 ~0.27-0.54 KB）。

BC reverse 的 one-to-many（3 个 target array）**不增加 CT entry 数**——所有 target 共享同一个 `index_PC` 的 CT entry，差异由 `tt_idx[K=3]` 指向不同的 TT entry 吸收。

**模拟器容量监测要求（全组件）**：

所有存储组件的容量均为基于静态分析或单 warp 场景的初始估算值。多 warp 并发场景下的实际需求需通过仿真验证。实现时采用 **两阶段容量确定法**：

**Phase 1（容量探测）**：所有组件使用远大于预期的定长数组（大数组 + free list，非链表——PRB 需 O(1) 按 `prb_entry_id` 查找，链表做不到），确保所有 workload 无阻塞跑完，同时记录以下监测计数器：

| 组件 | 计数器 | 说明 | 用途 |
|------|--------|------|------|
| **CT** | `ct_peak_occupancy` | 运行期间最高有效 entry 数 | 确认 32 是否足够 |
| | `ct_eviction_count` | 淘汰触发次数 | 非零说明容量不足 |
| | `ct_eviction_stride_valid` | 被淘汰 entry 中 `stride_valid=true` 的比例 | 高比例说明有效 entry 被驱逐 |
| **PRB** | `prb_peak_occupancy` | 运行期间最高有效 entry 数 | 确定 PRB 固定容量的关键指标 |
| | `prb_full_stall_cycles` | PRB 满导致 Index Coalescer stall 的总 cycle 数 | Phase 1 中应为 0（容量充裕）；Phase 2 中验证 |
| | `prb_avg_lifetime` | 平均 entry 生存时间（cycles） | 结合 peak 分析稳态行为 |
| | `prb_allocations` | 成功分配次数 | 与 stall 次数对比得出阻塞率 |
| **Response FIFO** | `rsp_fifo_peak_depth` | 运行期间最高水位 | 确定 FIFO 固定深度 |
| | `rsp_fifo_full_cycles` | 满导致反压 L1 的 cycle 数 | Phase 1 中应为 0 |
| **Index Coalescer** | `idx_coalescer_stall_cycles` | 因下游（PRB 满/MSHR 满）stall 的 cycle 数 | 定位 pipeline 瓶颈 |
| **Data Coalescer** | `data_coalescer_full_cycles` | 满导致 ACU stall 的 cycle 数 | 验证 Data Coalescer buffer 深度 |

**Phase 2（正式评估）**：基于 Phase 1 的 peak 数据确定固定容量（取 peak occupancy 的 110–120% 作为安全裕量），用固定容量跑正式性能评估。此时 stall/反压行为真实反映硬件约束。

**Phase 1 数据是上界的原因**：无限容量下 prefetcher 永不 stall → prefetch 流量最大化 → memory 子系统更拥塞 → PRB entry lifetime 可能更长 → peak occupancy 更高。有限容量时 stall 会降低 prefetch 速率，从而降低实际需求。因此 Phase 1 的 peak 是保守的 sizing 目标。

理想情况：CT 的 `ct_eviction_count = 0`（静态分析已覆盖所有 PC）；PRB/Response FIFO 的 Phase 2 `stall/full_cycles` 占总 cycle 数 < 1%。

### 7.2 对比参考

| Prefetcher | 存储开销/SM | 来源 |
|------------|-----------|------|
| IMP | 0.7 KB | Indirect Memory Prefetcher (2015) |
| Tyche | 0.57 KB | Tyche (2024) |
| Spare Register | 1.365 KB | Spare Register Aware Prefetching (2014) |
| **本方案（默认 S3）** | **~1.9 KB** | CT(544B) + TT(80B) + PRB(1.0KB) + CD FIFO(300B) |
| **本方案（最小 S1）** | **~712 B** | CT=8, TT=4, PRB=256 — 覆盖图遍历类 workload |

### 7.3 存储开销分析

**三项关键精简**使存储开销大幅降低：

1. **CT 去掉 data_pc / imad_pc**：CD 检测到 `LDG→IMAD.WIDE→LDG` 链时，IMAD 的 (base, scale) 在插入阶段直接写入 TT。CT 只需存 `index_pc` 作为 key（24b tag），后续 demand load 匹配和 prefetch 触发均通过 index_pc 完成，data_pc 和 imad_pc 不参与任何后续查找。每 entry 省 48 bit。

2. **stride_obs 从 16 slot → 2 slot**：IMA stride 是由数据结构 element size 决定的固定值（如 4B/8B/64B），极易学习。硬件只需 2 个 observation slot（2×38bit = 76bit），记录 2 个 warp 的首次访问地址。首个完成两次观测的 warp 即确定 stride，之后所有 64 个 warp 共享。每 entry 省 ~2100 bit（从 16×140b 降至 76b）。

3. **PRB 只存 ct_idx**：L1 fill 返回时携带 PRB entry ID + 实际 index 数据。PRB 通过 ct_idx 查到 CT entry 的 tt_idx[] → TT 的 (base, scale) → 计算 data address。无需冗余存储 tt_idx 快照或 warp_id，每 entry 仅 4-7 bit。

关键设计要点：
- Register FIFO（CD）从主要存储瓶颈（原 per-warp 方案 3 KB）降为 ~300 B（SM 级共享 FIFO）
- CT 的 2-slot stride obs 允许任意 warp 贡献 stride 学习，比仅 tracked warp 更鲁棒
- 训练冻结机制（§4.6）在所有 stride 收敛后关闭 CD FIFO 追踪 + 调度器 hint，动态功耗降为零
- 单个 CT entry 复用率极高（实测平均每 entry 触发数万次 prefetch），因此小表即可支撑大量 IMA 访存

**相对参考**：A100 每 SM 的 register file 为 256 KB，L1D/shared memory 为 192 KB。默认配置 1.9 KB 约占 L1D 的 1.5%，即使最大配置（S4, 3.6 KB）也仅占 2.7%，开销极小。

**硬件逻辑开销**（非存储）：
- 32 × barrel shifter + 32 × 64-bit adder（ACU，32-wide 并行地址计算，4 sectors/cycle）
- Index Coalescer + Data Coalescer（按 32B sector 分组 + 去重）

---

## 8. 与已有工作的差异化

| 维度 | CPU IMP (2015) | CPU Tyche (2024) | GPU Spare Reg (2014) | **本方案** |
|------|---------------|-----------------|---------------------|-----------|
| 目标平台 | CPU | CPU | GPU | **GPU** |
| 检测信号 | PC + stride | PC + propagation | Compiler annotation | **Register dependency chain** |
| 地址推断 | 观测 addr diff → 推 shift/base | 依赖链传播 | 编译器注入 prefetch 指令 | **IMAD.WIDE 操作数直接提取 scale/base** |
| Loop unrolling | N/A (CPU 少展开) | N/A | N/A | **(base, scale) 归组，自动归并** |
| 硬件辅助 | Hardware table | Hardware propagation table | Spare register file | **Two-table + PRB + 32-wide ACU** |
| ISA 扩展 | 不需要 | 不需要 | 需要（profiling + code gen） | **不需要** |
| IMA 覆盖 | Gather/Scatter | 多级依赖链 | 单级 gather | **Pattern I+II (Gather)，部分覆盖 III** |

**核心 novelty**：
1. **GPU 专属的 IMAD.WIDE 参数直接提取**：CPU prefetcher 需要从地址序列推断 shift 和 base（如 IMP 通过地址差分，DMP 通过 value differential），本方案利用 GPU SASS 的 IMAD.WIDE 指令直接暴露 scale 和 base，零推断开销
2. **自动归并 loop unrolling**：以 (base, scale) 而非 PC 作为 pattern key，天然解决 GPU 编译器激进展开导致的 PC 膨胀问题
3. **Address-triggered 即时预取**：利用 GPU 大量 warp 并发的特性，在 load 发出时即时计算预取地址，无需维护大型 per-warp 状态表

---

## 9. 待定事项与后续步骤

### 已回答的问题

| 问题 | 结论 | 所在章节 |
|------|------|---------|
| ~~L1 prefetch 还是 L2 prefetch？~~ | L2→L1 预取（L2 hit rate 66–78%，瓶颈在 L1） | §1.3 |
| ~~需要 software hint / ISA 扩展？~~ | 不需要，纯 hardware detection | §6 决策表 |
| ~~Unified 还是 hybrid 方案？~~ | Unified Index-Data Pipeline，覆盖 Pattern I+II | §3 |
| ~~Coalescing 交互~~ | Prefetcher 自带 Index/Data Coalescer（32B sector 粒度），不复用 LD/ST 流水线 | §3.3.1 |
| ~~MSHR 竞争~~ | 共享 MSHR；Index prefetch MSHR 满时放弃该 sector（RFAIL），Data prefetch MSHR 满时丢弃 | §3.3.1 |
| ~~Register Producer Table 精简~~ | 已改为 SM 级共享 FIFO（20 entry/2 tracked warps），~120 B/SM（原 per-warp 3 KB 降 96%） | §4.1 / §7 |
| ~~Active Mask 处理~~ | 使用当前 active_mask，不预测未来 mask | §3.3.1 |
| ~~表清理策略~~ | Kernel launch 清全表（含 PRB + Response FIFO + Data Coalescer）；tracked warp EXIT 清 Register FIFO + 重置 tracked_warp_id | §4.6 |
| ~~训练模型~~ | SM 级共享 FIFO（2 tracked warps）用于 chain detection + shared CT/TT；stride 学习由任意 warp 完成；speculative stride 可跳过学习延迟 | §4.1 / §4.5.3 / §4.5.4 |
| ~~Data prefetch 带宽~~ | 已知风险（32 scattered × K），先实验再节流 | §4.3 |
| ~~地址计算硬件~~ | 32-wide 并行 ACU（32 × barrel shifter + 32 × 64-bit adder），4 sectors/cycle，不需要乘法器 | §4.3.4 |
| ~~Cache hit 处理~~ | L1 tag check + MSHR merge，标准流程；HIT/merge 时不消耗额外 L2 带宽 | §3.3.1 |
| ~~Pending Buffer 设计~~ | PRB per-index-load，直接存 tt_idx[] 快照（解耦 CT 生命周期）；容量由两阶段法确定（Phase 1 大数组探测 peak，Phase 2 固定） | §4.3.2, §7.1 |
| ~~Sector 粒度~~ | 对齐 A100 L1 sector（32B）架构，prefetcher 以 sector 为操作单位（请求/响应/coalescing 均为 32B 粒度） | §3.3.1, §4.3 |
| ~~多响应并发~~ | Response FIFO 缓冲 L1 返回的 sector 响应，满时反压 L1（不影响 demand load）；深度由两阶段法确定 | §4.3.3, §7.1 |
| ~~Prefetch distance~~ | Per-PC iter_stride 自适应学习 + speculative stride 快启动（仅 stride_valid 时发出），精确区分不同展开版本 | §4.5 / §4.5.4 |
| ~~Unrolling 与 MLP 交互~~ | LDG 是 non-blocking（scoreboard-based），unrolling 创造 MLP；固定 n=3 在 SpMV ×16 下 81% 冗余，per-PC stride 解决 | §4.5 |
| ~~False positive 风险~~ | 两种无效化机制（write-invalidation / read-detection）均保证 FIFO 不变量，BFS 实证 14 条 IMAD.WIDE 零误检 | §4.1.1 |
| ~~前序链无效 prefetch~~ | Gate on stride_valid + CT 淘汰优先驱逐 stride_valid=false entry | §4.5, §3.2 |

### 待深化

| 问题 | 优先级 | 说明 |
|------|--------|------|
| **PRB/FIFO 多 warp 容量确定** | **高** | PRB 原始 32 entry、Response FIFO 原始 8 entry 均为单 warp 场景估算，多 warp 并发下严重不足（§4.3.2 分析 BFS 稳态 ~84 entries，SpMV 200+）。实现时 Phase 1 用大数组（PRB 1024, FIFO 128）+ 全组件监测计数器跑完目标 workload，Phase 2 基于 peak 数据定容量。详见 §7.1 模拟器容量监测要求 |
| Stride 自动检测 vs 固定值 | 中 | 当前假设 stride=4（int32），double 类型的 index array 需要 stride=8；可从 CT 的 scale 推断 |
| Throttle 精细化 | 中 | 当前仅 stride_valid 门控 + MSHR 隐式节流，后续需评估 misprediction counter 和带宽感知节流 |
| FIFO 深度优化 | 中 | SASS 仿真表明 BFS/SSSP/CC/BC 峰值 ≤ 4，但 SpMV ×16 峰值 = 17（见 §4.1 FIFO 深度分析）。实现时用可配置参数 + 运行时 `fifo_peak_occupancy`/`fifo_drop_count` 计数器扫描确定最优值 |
| ~~训练-冻结机制~~ | ~~低~~ | 已纳入 §4.6 生命周期管理：tracked warp EXIT 时检查 CT 是否全部 stride_valid，若是则冻结 CD |
| BC/CC 的 SASS 逐指令验证 | 低 | BFS 已验证无效化机制的有效性；BC/CC SASS 更复杂，实现时做同样的逐指令验证 |
| Write-inv vs Read-det 实验对比 | 低 | 当前默认 Read Detection；两种机制理论等价，实现时可做 A/B 对比验证 |

### 下一步

1. **Phase 4: 实现**：在 GPGPU-Sim 中实现上述设计，代码修改集中在 `gpu-cache.cc`、`shader.cc` 等文件
2. **Phase 4a: 容量探测（两阶段法 Phase 1）**：所有存储组件（PRB/Response FIFO/Coalescer 等）使用大定长数组（非链表），不设人为上限。全部目标 workload 跑完后，收集 peak occupancy / stall cycles 等监测计数器，确定各组件的真实容量需求（见 §7.1 全组件监测矩阵）
3. **Phase 4b: 正式评估（两阶段法 Phase 2）**：基于容量探测数据确定固定容量，用真实 stall/反压行为跑正式性能评估
4. **第一轮实验**：在 ima_high workload 上验证 prefetch 正确性和基本效果
5. **参数扫描**：验证 per-PC stride learning 的 convergence 和效果
6. **精化**：根据实验结果调整 throttle 策略等
