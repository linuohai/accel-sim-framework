# 04 — GPU IMA Prefetcher 设计方案

> 对应文件夹：`04_prefetcher_design/`（存放设计草图、算法伪代码、硬件预算估算等）
>
> 状态：**设计框架已定**（依赖 Phase 1 IMA 特征化 & Phase 2 调研完成）
>
> 前置文档：`01_ima_characterization.md`（IMA 模式分类与 SASS 分析）、`02_related_work.md`（CPU/GPU prefetcher 调研）、`03_performance_ceiling.md`（Ideal L1D 上界）

---

## 1. 设计定位

### 1.1 目标

设计一个 GPU 硬件 IMA prefetcher，将间接访存（`A[B[i]]`）的数据从 L2 提前填充到 L1，在不显著增加硬件开销和带宽浪费的前提下，缩小与 ideal L1D 之间的性能差距。

### 1.2 量化目标

| 指标 | 目标 | 数据来源 |
|------|------|---------|
| 性能下界 | Baseline（无 prefetch） | `03_performance_ceiling.md` |
| 性能上界 | Ideal L1D（1.75×–3.04× speedup） | `03_performance_ceiling.md` |
| 预期收益 | 捕获上界的 30%–60% | 初步估计，需实验验证 |

### 1.3 预取层级

**L2 → L1**（而非 HBM → L2）。

依据：ima_high 工作负载 L1 miss rate 70–77%，但 L2 hit rate 66–78%。瓶颈在 L1→L2 的 miss，L2 已能承载绝大部分 IMA 工作集。prefetcher 的延迟预算为 L2 访问延迟（~200 cycles，SM80_A100 配置 `-gpgpu_l2_rop_latency 200`），远小于 DRAM 延迟（~190 cycles 另加排队/调度开销）。

### 1.4 覆盖范围

| IMA Pattern | 覆盖 | 理由 |
|-------------|------|------|
| **Pattern I: Linear Gather**（SpMV `x[Aj[k]]`） | ✅ 覆盖 | 核心目标，index 地址 stride 可预测 |
| **Pattern II: Frontier-Driven Gather**（BFS `dists[col_idx[j]]`） | ✅ 覆盖 | 核心目标，同 Pattern I 的两步结构 |
| **Pattern III: Data-Dependent Indirection**（CC hook `comp[max(...)]`） | ⚠️ 部分覆盖 | 第一层 `comp[dst]` 可预取（同 Pattern I）；第二层 `comp[high_comp]` 地址在第一层 load 返回前物理不可知，timeliness ≈ 0，标注为 limitation |
| **Pattern IV: Pointer Chasing**（CC shortcut） | ❌ 不覆盖 | 每一跳地址完全依赖上一跳返回值，MLP ≈ 0，无法提前预取 |

---

## 2. GPU 微架构约束

| 约束 | 说明 | 设计影响 |
|------|------|---------|
| **海量并发 warp** | A100 每 SM 最多 64 warp，108 SM | 不使用大型 per-warp 状态表，改用 address-triggered 即时方案 |
| **L1D 容量小** | 通常 32–128 KB（含 shared memory） | prefetch 污染风险高，需 confidence 控制 |
| **Coalescing** | LD/ST coalescing unit 与 warp 指令结构性绑定 | Prefetcher 自带轻量 coalescer（32B sector 粒度），不复用 LD/ST 流水线 |
| **NoC 带宽有限** | L1→L2→HBM 带宽被所有 SM 共享 | 无用 prefetch 直接抢占有效带宽 |
| **Warp 切换隐藏延迟** | 多 warp 交替执行 | prefetch 的增量收益可能受限，但 ideal L1D 的 1.75×–3.04× 说明仍有大量空间 |
| **Loop Unrolling → PC 膨胀** | BFS 1 条源码 load → 5 个 SASS PC；SpMV → 30+ PC | 不能以 PC 作为 pattern 唯一标识，需要 (base, scale) 归组 |

---

## 3. 核心架构：两表 + 两步 Pipeline

### 3.1 架构总览

```
                          ┌─────────────────────────────────┐
                          │    Component 1:                 │
                          │    Dependency Detector          │
    指令流 ───────────────→│    (decode/issue 阶段)          │
    (PC, opcode,          │                                 │
     registers)           │  追踪 LDG→IMAD.WIDE→LDG 依赖   │
                          └──────┬───────────┬──────────────┘
                                 │           │
                          更新 Table A   更新 Table B
                                 │           │
                    ┌────────────▼──┐  ┌─────▼──────────────┐
                    │  Table A:     │  │  Table B:          │
                    │  PC Dep Table │  │  Pattern Table     │
                    │               │  │                    │
                    │  key: index   │  │  key: (data_base,  │
                    │    load PC    │  │        scale)      │
                    │  val: data_PC,│  │  val: confidence,  │
                    │    scale,base │  │    active,         │
                    │               │  │    targets[K=3]    │
                    └───────┬───────┘  └────────┬───────────┘
                            │                   │
                            └────────┬──────────┘
                                     │
               ┌─────────────────────▼─────────────────────┐
               │    Component 2:                           │
               │    Address-Triggered Index Prefetch       │
               │                                           │
               │  当 warp 发出 index load 时:               │
               │  ① 查 Table A 确认是 IMA index load       │
               │  ② 查 Table B 确认 pattern 已激活         │
               │  ③ 发出 index prefetch (sector 粒度):      │
               │     addrs = current_addr + iter_stride    │
               │  ④ 分配 PRB entry (等待值返回)            │
               └─────────────────────┬─────────────────────┘
                                     │ index prefetch 值返回
               ┌─────────────────────▼─────────────────────┐
               │    Component 3:                           │
               │    Data Prefetch Generator                │
               │                                           │
               │  Response FIFO → ACU (8-wide 并行):      │
               │  对每个 target array k ∈ [0, K):          │
               │    data_addr = target[k].base             │
               │               + value × target[k].scale   │
               │  发出 data prefetch 请求 → L1             │
               └─────────────────────┬─────────────────────┘
                                     │ accuracy feedback
               ┌─────────────────────▼─────────────────────┐
               │    Component 4:                           │
               │    Throttle Controller (简版)              │
               │                                           │
               │  confidence counter 控制激活              │
               │  (后期: early eviction rate 监控)         │
               └───────────────────────────────────────────┘
```

### 3.2 两表设计

#### Table A: PC Dependency Table

用于将 PC 分类为"IMA index load"或"普通 load"。

| 字段 | 说明 |
|------|------|
| **key** | `index_load_PC` |
| **data_load_PC** | 对应的 data load 的 PC |
| **IMAD_PC** | 依赖链中 IMAD.WIDE 的 PC |
| **scale** | 从 IMAD.WIDE 操作数提取的元素大小（通常 4 或 8） |
| **data_base** | 从 IMAD.WIDE 的 constant memory 操作数提取的 data array 基地址 |
| **tracked_warp_id** | 用于学习 iteration stride 的代表 warp（6 bit） |
| **last_addr** | 该代表 warp 上次触发此 PC 的地址（64 bit） |
| **iter_stride** | 学到的 iteration stride，单位 bytes（32 bit） |
| **stride_valid** | stride 是否已学到（1 bit） |

**淘汰策略**：当 Table A 满且需插入新 entry 时，优先驱逐 `stride_valid == false` 的 entry。理由：`stride_valid == false` 意味着该 PC 要么是前序代码（只执行一次，stride 永不收敛），要么是刚写入尚未完成学习的 entry。前者永远不产生 prefetch，是 Table A 的"死 entry"；后者重新写入后会重新学习，代价仅为延迟一个 iteration。若所有 entry 均 `stride_valid == true`，回退到标准 LRU 淘汰。

**建表方式**：在 decode/issue 阶段追踪寄存器依赖链。当观测到 `LDG Rd → IMAD.WIDE Rx, Rd, scale, c[base] → LDG [Rx]` 时，确认 (index_PC, data_PC) 为 IMA 对，写入 Table A。

**归并效果**：Loop unrolling 产生的多个 index load PC 拥有不同的 Table A entry，但它们的 `(data_base, scale)` 相同，因此映射到 Table B 的同一条 pattern entry。

#### Table B: Pattern Table

用于归并展开副本、存储预取参数和激活状态。

| 字段 | 说明 |
|------|------|
| **key** | `(data_base, scale)` — 来自 IMAD.WIDE constant operand |
| **confidence** | 观测到依赖链的次数，≥ 阈值则 active=true |
| **active** | 是否激活预取 |
| **targets[K]** | 最多 K=3 个 `(base_addr, scale)` 对，支持 one-to-many（BC reverse: 1 index → 3 data） |

**归并效果（以 SpMV 为例）**：
- 源码中 1 条 `x[Aj[k]]` 的 load
- SASS 中展开为 30+ 个不同 PC 的 LDG（×16, ×8, ×4, ×1 版本）
- 所有 30+ 个 Table A entry → 同一个 `(x_base, 8)` 的 Table B entry

### 3.3 两步 Prefetch Pipeline

IMA 预取分为两步，形成 pipeline：

```
时间线（以 BFS 为例）:

迭代 i:
  warp 发出 index load: LDG column_indices[offset_i]     ← 正常执行
  prefetcher 同时发出: PREFETCH column_indices[offset_i + 3×4]  ← Step 1: index prefetch (i+3)

  ... (其他 warp 执行) ...

  column_indices[offset_i + 3×4] 的值 v 从 L2 返回
  prefetcher 计算: data_addr = dists_base + v × 4        ← Step 2: data prefetch
  prefetcher 发出: PREFETCH dists[v]

  ... (~200 cycles later) ...

迭代 i+3:
  warp 发出 data load: LDG dists[column_indices[offset_i+3]]
  → L1 HIT (已被 prefetch 填充)                          ← 预取命中！
```

**关键时序**（基于 SM80_A100 gpgpusim.config 实测参数）：
- L1 hit 延迟：34 cycles
- L2 hit 延迟（L2 ROP latency）：**200 cycles**
- DRAM 延迟：190 cycles（另加排队/调度开销）
- Step 1 (index prefetch) 延迟：~200 cycles（L2 hit）
- Step 2 (data prefetch) 延迟：~200 cycles（L2 hit）
- 总 lead time 需求：~400 cycles

**时效性分析**：warp 的每次循环迭代至少经历 index load L2 miss（~200 cycles）+ data load L2 miss（~200 cycles），合计 ~400+ cycles/iteration。Prefetch 使用 per-PC stride（= 1 个 outer iteration 的元素数），lead time = 1 × 400+ cycles ≈ 400+ cycles ≈ pipeline 需求 → 时效刚好满足。

对于 ×4 展开（BFS/SSSP/CC）：stride = 4 elements，每 4 个 demand load 之后才回到同一 PC → lead time ≈ 400-500 cycles > 400 cycles → 可行。
对于 ×16 展开（SpMV）：stride = 16 elements，窗口内 16 个 demand load 通过 MLP 并行处理，一个完整 outer iteration ≈ 400-500 cycles → lead time ≈ 400-500 cycles ≈ 400 cycles → 临界可行。

#### 3.3.1 Coalescing 与 Sector 粒度

**Prefetcher 自带轻量 coalescing 逻辑**：硬件上，LD/ST 流水线的 coalescing unit 与 warp 指令（`warp_inst_t`）结构性绑定——它消费的是指令 issue 阶段产生的 32 个 per-lane 地址。Prefetcher 是一块独立硬件，不经过 warp scheduler，不 issue 指令，因此**无法复用** LD/ST 流水线的 coalescing 路径。Prefetcher 需要自带等价的 coalescing 逻辑，但由于 prefetcher 只处理已知形式的地址（`base + value × scale` 或线性 stride），其 coalescer 比 LD/ST 流水线的更简单（仅需按对齐地址分组 + 去重）。

**对齐 A100 L1 Sector 架构**：A100 L1 以 **32B sector**（而非 128B cache line）为操作单位。cache line = 128B = 4 sectors。LSU 将 warp 的访存请求 coalesce 为 sector 级别，每 cycle 可发送 bank 个 sector（无 bank conflict 时）。Prefetcher 的 coalescer 同样以 32B sector 为粒度，产出 sector 级请求。

Prefetcher 内部有两处 coalescer：

| Coalescer | 位置 | 输入 | 输出 | 特点 |
|-----------|------|------|------|------|
| **Index Coalescer** | Component 2 → L1 | 32 per-lane index prefetch 地址 | ~4 sector 请求 | Index 数组线性访问，32×4B=128B=4 sectors |
| **Data Coalescer** | Component 3 → L1 | ACU 输出的 8×K data prefetch 地址 | M sector 请求 | IMA data 地址高度分散，合并率低 |

**Active Mask 策略**：prefetch 使用**当前 warp 的 active_mask**，不预测未来 mask。

| 方面 | 策略 | 理由 |
|------|------|------|
| 使用哪些 lane 的地址 | 当前 active_mask 中的 active lane | 简单且正确——predicated-off lane 的 index 值无意义 |
| 未来 mask 是否预测 | 不预测 | 条件分支（如 BFS `if dists[dst] == INF`）使未来 mask 不可知 |
| 浪费如何处理 | 由 throttle 消化 | 少数 lane 的 prefetch 可能无用，但代价可控 |

**Prefetcher 作为 L1 Client**：Prefetcher 是 L1 cache 的一个独立 client，与 warp demand load 平级。请求通过独立端口发送，不与 demand load 竞争发射带宽。L1 对 prefetcher 请求和 demand 请求使用相同的 tag check → MSHR → fill 流程，但响应路径不同：index prefetch 的响应需要携带数据返回给 prefetcher（用于 Step 2 地址计算），而 data prefetch 是 fire-and-forget。

**Prefetch 与 L1 Cache 的交互流程**（区分 index prefetch 和 data prefetch）：

| L1 状态 | Index Prefetch 行为 | Data Prefetch 行为 |
|---------|--------------------|--------------------|
| **HIT** | L1 返回 {prb_entry_id, sector_data[32B], element_mask[8bit]} 给 prefetcher | 丢弃（数据已在 L1），仅更新 LRU |
| **MISS, MSHR 有匹配** | 合并到现有 MSHR entry（携带 prb_entry_id） | 合并到现有 MSHR entry |
| **MISS, MSHR 无匹配** | 分配新 MSHR entry（携带 prb_entry_id），向 L2 发出 fill request；fill 后数据返回给 prefetcher | 分配新 MSHR entry，向 L2 发出 fill request |
| **MISS, MSHR 满** | **阻塞等待**，MSHR 有空位后重发 | **丢弃**（fire-and-forget） |

**Index Prefetch 在 MSHR 满时阻塞而非丢弃**：Index prefetch 是两步 pipeline 的 Step 1——如果丢弃，对应的 data prefetch（Step 2）将无法触发，等于浪费了依赖链检测和地址生成的所有工作。反压通过 prefetcher 内部 pipeline stall 实现，不影响 demand load 路径（prefetcher 使用独立的 L1 端口）。Data prefetch 在 MSHR 满时丢弃，因为它是最终步骤，丢弃的代价仅为一次预取机会损失。

**MSHR 合并（merge）场景**：当 prefetch 请求的 sector 已有一个 in-flight demand load（另一个 warp 已发出请求），prefetch 不产生额外的 L2 流量——它合并到现有 MSHR entry 中。SM80_A100 的 L1 MSHR 配置为 512 entries（max_merge=64），合并容量充裕。

**设计含义**：
- L1 HIT 和 MSHR merge 两种情况下，prefetch **不产生额外 L2 带宽消耗**
- 真正消耗带宽的是 L1 MISS + MSHR 无匹配的情况——即 prefetch 确实提前请求了尚未被任何 warp 请求的 sector
- Prefetcher 的独立端口确保 prefetch 永远不阻塞 demand load

---

## 4. 组件详细设计

### 4.1 Component 1: Dependency Detector

**位置**：SM 的 issue/decode 阶段（可观测 PC、opcode、源/目标寄存器编号、立即数/constant memory 操作数）。

**检测算法伪代码**：

```python
# 每个 SM 为每个 warp 维护一个小 FIFO（8 entries），记录最近的 load/IMAD.WIDE 产出
# 每条 entry: {dst_reg, type, PC, ima_info?}
# 查找方式: 在 FIFO 中反向搜索匹配 src_reg 的最新 entry
#
# FIFO entry 结构（~6 bytes）:
#   dst_reg:  8 bit  (寄存器编号 0-255)
#   type:     2 bit  (LOAD_RESULT / IMA_ADDR_COMPUTE / CONST_VALUE)
#   PC:      32 bit  (用于回填 Table A 的 index_PC)
#   ima_info: 可选，仅 IMA_ADDR_COMPUTE 类型携带 (index_PC, scale, base)

def fifo_lookup(warp_id, reg):
    """在 warp 的 FIFO 中反向查找最近写入 reg 的 entry"""
    for entry in reversed(reg_fifo[warp_id]):
        if entry.dst_reg == reg:
            return entry
    return None  # 未追踪到 → 视为普通寄存器

def on_instruction_issue(warp_id, PC, opcode, dst_reg, src_regs, operands):

    # === FIFO Write Invalidation（基础语义）===
    # FIFO 的不变量：entry {Rd, LOAD_RESULT} 意味着"Rd 当前持有该 LDG 的返回值"
    # 当任何非追踪指令覆写 Rd 时，该不变量被破坏 → 必须 invalidate
    # 附带效果：被非 IMA 指令消费的 LDG entry 及时清理，缓解 FIFO 压力
    if dst_reg is not None and opcode not in {LDG, IMAD_WIDE, IMAD_MOV}:
        fifo_invalidate(warp_id, dst_reg)

    if opcode == LDG:
        addr_reg = src_regs[0]  # LDG 的地址寄存器

        # 检查：这条 LDG 的地址是否由一个 IMA 地址计算产生？
        producer = fifo_lookup(warp_id, addr_reg)
        if producer and producer.type == IMA_ADDR_COMPUTE:
            # 确认 IMA 依赖链完成: LDG → IMAD.WIDE → LDG
            ima = producer.ima_info

            if ima.index_PC in Table_A:
                # 同一 index_PC 的新 target（one-to-many，如 BC reverse）
                # → 不覆盖 Table A，将新 target 追加到 Table B
                existing = Table_A[ima.index_PC]
                pattern_key = (existing.data_base, existing.scale)
                new_target = (ima.base, ima.scale)
                if new_target not in Table_B[pattern_key].targets:
                    Table_B[pattern_key].targets.append(new_target)
            else:
                # 首次发现 → 正常写入 Table A 和 Table B
                Table_A[ima.index_PC] = {
                    data_PC:   PC,
                    scale:     ima.scale,
                    data_base: ima.base
                }
                pattern_key = (ima.base, ima.scale)
                if pattern_key not in Table_B:
                    Table_B[pattern_key] = {
                        confidence: 0, active: False,
                        targets: [(ima.base, ima.scale)]
                    }
                Table_B[pattern_key].confidence += 1
                if Table_B[pattern_key].confidence >= CONFIDENCE_THRESHOLD:
                    Table_B[pattern_key].active = True

        # 记录这条 LDG 到 FIFO（可能作为下一个 IMA 的 index load）
        reg_fifo[warp_id].push({dst_reg: dst_reg, type: LOAD_RESULT, PC: PC})

    elif opcode == IMAD_WIDE:
        src_val_reg = src_regs[0]   # 被乘数（可能是 load 返回值）
        scale_reg   = src_regs[1]   # 乘数（scale = sizeof(element)）
        base_const  = operands.const_mem  # constant memory 操作数（data array base）

        producer = fifo_lookup(warp_id, src_val_reg)
        if producer and producer.type == LOAD_RESULT:
            # 这个 IMAD.WIDE 消费了一个 load 的返回值 → 可能是 IMA 地址计算
            reg_fifo[warp_id].push({
                dst_reg: dst_reg,
                type: IMA_ADDR_COMPUTE,
                ima_info: {
                    index_PC: producer.PC,
                    scale:    resolve_scale(scale_reg),
                    base:     base_const
                }
            })
        # 非 IMA 相关的 IMAD.WIDE 不入 FIFO（节省空间）

    elif opcode == IMAD_MOV and is_constant_load(operands):
        # IMAD.MOV.U32 Rd, RZ, RZ, imm → 常量加载（如 scale=4）
        reg_fifo[warp_id].push({
            dst_reg: dst_reg,
            type: CONST_VALUE,
            value: operands.immediate
        })

```

**Per-Warp FIFO 设计说明**：

| 设计要点 | 说明 |
|---------|------|
| **为什么用 FIFO 而非全量表** | IMA 依赖链 `LDG→IMAD.WIDE→LDG` 通常跨 3-5 条指令。8-entry FIFO 足以覆盖 unrolled 循环体（BFS unroll×4 = 4 条 LDG + 4 条 IMAD.WIDE = 8 条相关指令）。全量 `[warp][reg]` 表需要追踪 256 个寄存器，绝大部分 entry 永远不会被查到。 |
| **查找方式** | 反向线性搜索 FIFO（8 entries，硬件实现为 8 个并行比较器 + 优先编码器），与 CPU store buffer 的 CAM 查找类似 |
| **淘汰策略** | 两层淘汰：① 写无效化（见下行）及时清除被覆写的 entry；② FIFO 满时自然淘汰最旧 entry |
| **写无效化** | 每条非追踪指令发射时，若其 dst_reg 在 FIFO 中有 entry，立即 invalidate。这是 FIFO 的**基础语义**——保证 entry 的 `dst_reg` 确实仍持有追踪值。硬件：8 个 8-bit 并行比较器（与现有查找逻辑复用）+ invalidation 使能信号，面积增量接近零。附带效果：被非 IMA 指令消费的 LDG entry 及时回收，缓解高 LDG 密度代码下的 FIFO 压力 |
| **存储开销** | 64 warp × 8 entries × 6B/entry ≈ **3 KB/SM**（对比全量表 12 KB，节省 75%） |
| **只记录相关指令** | 仅 LDG、IMA 相关的 IMAD.WIDE、IMAD.MOV 常量加载入 FIFO；其他指令完全忽略，避免 FIFO 被无关指令快速填满 |

**One-to-Many 累积检测**：

BC reverse 中，一条 index load（`column_indices[offset]`，单一 PC）的返回值被三条独立的 IMAD.WIDE 消费，生成 `depths[dst]`、`path_counts[dst]`、`deltas[dst]` 三个 data load。SASS 证据：

```asm
IMAD.WIDE R8, R9, R6, c[0x0][0x178]   // depths[dst]      ← base_1, 共享 index R9
IMAD.WIDE R8, R9, R6, c[0x0][0x170]   // path_counts[dst] ← base_2, 共享 index R9
IMAD.WIDE R8, R9, R6, c[0x0][0x188]   // deltas[dst]      ← base_3, 共享 index R9
```

FIFO 会自然发现三条独立的 `LDG→IMAD.WIDE→LDG` 链，但它们共享同一个 `index_PC`。伪代码中通过 `index_PC in Table_A` 判断区分：
- **首次发现**：正常写入 Table A + Table B（含第一个 target）
- **后续发现**：识别为同一 index stream 的新 target，追加到 Table B 的 `targets[]` 数组

这样 Table A 不需要多路或膨胀——one-to-many 的复杂性被 Table B 的 `targets[K=3]` 吸收。

**IMAD.MOV 特殊处理**：在 BFS 的 SASS 中，scale 值并非直接作为 IMAD.WIDE 的立即数，而是先通过 `IMAD.MOV.U32 R11, RZ, RZ, 0x4` 加载到寄存器。detector 需要追踪这类"常量加载"指令，确保 scale 值可解析。上方伪代码中已将 `IMAD.MOV` 常量加载纳入 FIFO 追踪。

```asm
/*0660*/  IMAD.MOV.U32 R11, RZ, RZ, 0x4         // R11 = 4 (sizeof(int))
/*0670*/  IMAD.WIDE R2, R0, R11, c[0x0][0x178]  // addr = R0 × R11 + dists_base
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

检测与知识的分离是本设计的关键架构决策：

| 层面 | 粒度 | 说明 |
|------|------|------|
| **寄存器追踪（FIFO）** | Per-warp | 每个 warp 有独立的 8-entry FIFO，追踪各自的寄存器依赖链 |
| **知识存储（Table A/B）** | Per-SM shared | 所有 warp 共享同一份 Table A 和 Table B |

**训练一次，全 SM 复用**：本设计的核心训练优势不是"单个 warp 训练更快"（事实上 per-warp 训练速度比 CPU 单线程更慢），而是**训练产出的知识（Table A/B）被全 SM 共享**，训练开销被 64 倍分摊。

训练包含两个阶段，性质不同：

1. **IMA 依赖链检测**（填充 Table A/B + 累加 confidence）：发生在 instruction issue 阶段，观察到 `LDG→IMAD.WIDE→LDG` 的寄存器依赖链时立即写入，不需要等 load 数据返回。64 个 warp 各自独立检测并给 Table B 的 confidence +1，因此 confidence 在 wall-clock 时间上较快达到阈值——这是"多观察者共同贡献"的结果，不是单个观察者更快。

2. **Stride 学习**（Table A 的 `iter_stride`）：需要同一 PC 的 index load 被同一个 tracked warp 执行两次以计算地址差。这要求该 warp 经历至少 2 次 outer loop iteration。对 BFS（unroll×4）约需 ~3200 cycles，比 CPU 单线程（~800 cycles）更慢。但 stride 一旦学到，即对所有 warp 的后续 prefetch 生效。

与 CPU 的本质差异：CPU 的 IMP/DMP 是 per-core 检测器，每个 core 为自己的线程独立学习（复用率 1:1）。GPU 的独特之处在于大量执行相同代码的 warp **共享同一份 pattern 知识**（复用率 1:64）——这是 SIMT 执行模型的天然产物。

#### 4.1.1 BFS SASS 实证：FIFO 写无效化的必要性

对 `bfs_linear_base.sm80.sass` 全部 14 条 IMAD.WIDE 逐条追踪，验证 FIFO 的检测准确性：

| 分类 | 数量 | 说明 |
|------|------|------|
| 正确检测为 IMA | 7 | 前序 2 条 + remainder 1 条 + ×4 展开 4 条 |
| 正确排除（src 不在 FIFO） | 6 | 线程 ID / 循环计数器 / warp 前缀和 |
| **写无效化生效** | **1** | PC 0x0530: 若无写无效化，R2 的旧 LDG entry 会导致误分类 |

**写无效化生效的具体案例（PC 0x0530）**：

```
PC 0x0270: LDG.E R2, [R18.64]           // dists[src] → FIFO: {R2, LOAD_RESULT}
PC 0x02a0: ATOMG.E.CAS PT, R2, [R2]...  // R2 被 CAS 返回值覆写 → 写无效化清除 FIFO 中 R2 的旧 entry
PC 0x03c0: IMAD.IADD R2, R2, 0x1, R11   // R2 被前缀和覆写 → 再次确认 R2 不在 FIFO 中
PC 0x0530: IMAD.WIDE R2, R2, R3, c[...]  // FIFO 查 R2 → 无命中 → 正确排除（不是 IMA）
```

若无写无效化，PC 0x0530 会误命中 0x0270 的旧 entry，将非 IMA 的 worklist 写入路径误判为 IMA 地址计算。BFS 中此案例恰好后跟 STG（链无法完成），但其他 workload 中类似路径可能后跟 LDG，产生真正的 false positive。

**结论**：写无效化在 BFS 中将检测准确率从 7/8（87.5%）提升到 **7/7（100%）**。这验证了它作为 FIFO 基础语义的必要性——不是为罕见 corner case 打补丁，而是保证依赖追踪的正确性不变量。

### 4.2 Component 2: Address-Triggered Index Prefetch

**设计核心**：不维护 per-warp 状态表。当 warp 发出 index load 时，当前地址即时已知（来自 issue 阶段的地址寄存器），直接在当前地址基础上 + n×stride 发出 index prefetch。

**伪代码**：

Index prefetch 的核心逻辑已整合 per-PC stride learning，完整伪代码见 **§4.5.3**（`on_index_load_issue` 函数）。关键行为：

- 若 `stride_valid`：使用学到的 `iter_stride`（精确跨 1 个 outer iteration）
- 若 stride 尚未学到：**不发 prefetch**（前序 PC stride 永不收敛 → 自然过滤）

```python
# 简化版（完整版见 §4.5.3）
def on_index_load_issue(warp_id, PC, current_addr):
    if PC not in Table_A:
        return

    entry_a = Table_A[PC]
    pattern_key = (entry_a.data_base, entry_a.scale)

    if not Table_B[pattern_key].active:
        return

    # Per-PC stride learning（见 §4.5.3 完整学习逻辑）
    if not entry_a.stride_valid:
        return  # stride 未学到 → 不发 prefetch

    # Per-lane 地址生成（对应 32 个 SIMT lane）
    prefetch_addrs = [current_addr[lane] + entry_a.iter_stride for lane in active_lanes]

    # 经 Index Coalescer 合并为 sector 请求（32B 粒度）
    sector_reqs = index_coalescer.coalesce_to_sectors(prefetch_addrs, active_mask)

    for req in sector_reqs:
        prb_id = PRB.allocate(table_b_idx=pattern_key_idx)
        if prb_id is None:
            stall()  # PRB 满，等待释放
        # 每个 sector 请求独立分配 PRB entry
        issue_l1_request(req.sector_addr, req.element_mask, prb_entry_id=prb_id, type=INDEX_PF)
        # 若 MSHR 满 → stall 等待，不丢弃
```

**为什么不需要 per-warp 状态表**：

传统 CPU prefetcher 需要记住每个 context 的 index 当前位置，因为在下一次 load 发出前它需要自主发出 prefetch。但 GPU 的情况不同：

- GPU 上 warp 数量极多（64/SM），且每次 warp 发出 index load 时地址都是已知的
- 在 load 发出的瞬间做 `current_addr + n×stride` 即可，无需"记住"之前的地址
- 唯一需要"跨时间"保留的状态是 PRB 中等待 index 值返回的条目

### 4.3 Component 3: Data Prefetch Generator（Sector-Based Architecture）

**完整数据流**：

```
                              Component 3: Data Prefetch Generator
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
                    │  PRB    │←── invalidate on FIFO pop ─────────────│
                    │(32×5bit)│                                         │
                    └─────────┘                                         ↓
                                                                 ┌───────────┐
                         Table B ─── base,scale ───────────────→│   ACU     │
                                                                 │  8-wide   │
                                                                 │ 1cyc/sect │
                                                                 └─────┬─────┘
                                                                       │ 8×K addrs
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
- **响应接口**（仅 index prefetch）：`{prb_entry_id, sector_data[32B], element_mask[8bit]}`

#### 4.3.2 Prefetch Request Buffer (PRB)

PRB 是一个极简的在途 index prefetch 跟踪表，每个 sector 请求独立占用 1 个 entry。当 L1 响应返回时，PRB entry ID 随响应一起返回，prefetcher 通过 `table_b_idx` 查找 Table B 获取 data prefetch 参数。

| 字段 | 大小 | 说明 |
|------|------|------|
| valid | 1 bit | 有效位 |
| table_b_idx | 4 bit | Table B 索引（用于查找 base/scale） |
| **总计/条** | **5 bit** | |
| **条目数** | **32/SM** | 每个 sector 请求独立占用 1 个 entry |
| **总大小** | **20 bytes/SM** | |

- 一次 index prefetch（32 lanes × 4B = 128B）coalesce 为 ~4 sector 请求 → 占用 ~4 个 PRB entries
- 32 个 PRB entries 可支持 ~8 个并发 index prefetch（8 warp 同时有 in-flight index prefetch）
- PRB 满 → Index Coalescer stall（不丢弃）

#### 4.3.3 Response FIFO 与反压

| 组件 | 深度 | 每条大小 | 总大小 |
|------|------|---------|--------|
| Response FIFO | 8 | prb_entry_id(5b) + sector_data(32B) + element_mask(8b) ≈ 34B | **~272 B** |

- 多个 sector 响应可能同时到达（L1 每 cycle 可返回 bank 个 sector）
- FIFO 满 → 反压 L1 prefetcher 响应端口（不影响 demand load 响应路径）
- FIFO front 每次弹出一条 → 送入 ACU
- PRB entry 在 Response FIFO 弹出时即 invalidate（table_b_idx 已读取）

#### 4.3.4 Address Computation Unit (ACU) — 8-wide 并行

每个 sector 返回 32B = 8 个 int 元素。ACU 在 **1 cycle** 内并行处理一个 sector 的所有有效元素：

```python
# 每次从 Response FIFO 弹出一条 {prb_entry_id, sector_data[32B], element_mask[8bit]}
table_b_idx = PRB[prb_entry_id].table_b_idx
PRB[prb_entry_id].valid = False  # invalidate PRB entry

for each element position i (0..7):
    if element_mask[i] == 1:
        value = sector_data[i*4 .. i*4+3]  # 32-bit int
        for each target k in Table_B[table_b_idx].targets:
            data_addr[i][k] = target.base + (value << log2(target.scale))
```

**地址计算硬件**：

Data prefetch 的地址公式为 `data_addr = base + value × scale`。关键观察：**scale 永远是 2 的幂**（`sizeof(int)=4=2²`，`sizeof(double)=8=2³`），因此乘法可替换为位移：`data_addr = base + (value << log2(scale))`。

| 组件 | 位宽 | 数量 | 面积（相对） |
|------|------|------|-------------|
| Barrel shifter | 32-bit input, 3-bit shift | **8** | 极小 × 8 |
| 加法器 | 64-bit | **8** | 小 × 8 |
| 乘法器 | — | **0** | — |

**不需要乘法器**。shift amount 直接从 Table B 的 scale 字段取 `log2(scale)`，零试探。8 组 shifter+adder 由 element_mask 门控无效 lane。

- K=1（BFS/SSSP/SpMV/CC）：**1 cycle** 完成
- K=3（BC reverse）：**3 cycles**（复用同一组 8-wide 加法器，每 cycle 切换 target）

注意：如果后续扩展到 non-power-of-2 的 scale（如 struct packing 中 sizeof(struct)=12），则需要 8 个 32×32 乘法器。但图算法中所有 element 类型均为 int/float/double，scale ∈ {4, 8}，当前无此需求。

#### 4.3.5 Data Coalescer

接收 ACU 输出的 up to 8×K 个 data addresses，合并为 M 个 sector 请求：

| 组件 | 条目数 | 每条大小 | 总大小 |
|------|--------|---------|--------|
| Data Coalescer Buffer | 32 | sector_addr(~40b) + valid(1b) ≈ 6B | **~192 B** |

- IMA data 地址高度分散，coalescing 合并率低，M 接近有效元素数（≤ 8×K）
- 逐个 dispatch sector 请求到 L1（type=DATA_PF），MSHR 满时丢弃
- **Dispatch 完成后 invalidate 内部缓冲**，准备接收下一批
- 在 dispatch 期间，Response FIFO 的下一条无法弹出（pipeline stall）

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
| 每 sector 有效 prefetch 请求 | 最多 8 | element_mask 中每个有效位产生一个独立地址 |
| Coalescing 后 sector 请求 | ~6-8 | IMA 地址分散，coalescing 合并率低 |
| Target array 数（K） | 1-3 | BFS K=1, BC reverse K=3 |
| 每 sector 响应产生的 data prefetch | ~6-24 sectors | 6-8 × K |

**风险评估**：当 K=3（BC reverse）且地址高度分散时，每个 sector 响应可能产生 ~24 条 data prefetch sector 请求。这些请求将与 demand load 竞争 L1→L2 带宽和 MSHR。

**缓解措施**（当前版本）：
1. MSHR 满时 data prefetch 自动丢弃（隐式节流）
2. Confidence counter 防止训练期产生无用 prefetch
3. 实际影响需在第一轮实验中量化——如果带宽成为瓶颈，在 Throttle Controller 中增加带宽感知机制（见 4.4）

### 4.4 Component 4: Throttle Controller

**当前版本（简版）**：仅用 confidence counter 控制 pattern 激活。

```python
CONFIDENCE_THRESHOLD = 3  # 观测到 3 次完整依赖链后才激活预取

# 在 Dependency Detector 中已实现:
# Table_B[pattern_key].confidence >= CONFIDENCE_THRESHOLD → active = True
```

**后期扩展方向**：

| 机制 | 说明 | 参考 |
|------|------|------|
| Early Eviction Rate | 跟踪 prefetch 带入的 cache line 被使用前就被驱逐的比例；超阈值则降低 n | MT-Prefetch / WASP |
| Accuracy Counter | 统计 prefetch hit / total prefetch 比率；低于阈值则暂停 | IMP |
| 动态 Prefetch Depth | 根据 accuracy 自适应调整 n（1→4） | DMP |
| **带宽感知节流** | 监控 NoC/L2 interconnect 利用率或 MSHR 占用率；高负载时降低 prefetch depth n 或暂停 prefetch；低负载时恢复 | 新增（应对 4.3 中 data prefetch 带宽风险） |

### 4.5 Loop Unrolling、MLP 与 Per-PC Stride Learning

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
IMAD.WIDE R32, R0, ...     → R0 是 pending → STALL（等待 L2 返回）
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

由于每个 copy 之间有 54 条指令的 CAS + worklist 代码，当 copy 2 的 INDEX LOAD 发出时，copy 1 的 load 早已从 L2 返回——这 4 个 INDEX LOAD **不会同时 in-flight**，不创造 MLP。展开的目的是减少循环开销（branch + counter），而非创造并行度。

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

#### 4.5.3 Per-PC Iteration Stride Learning

**核心思路**：不用固定 n，而是让每个 Table A entry 学习自己的 **iteration stride**——即同一 PC 在同一 warp 连续两次触发之间的地址差。这个差值恰好等于 `U × element_stride`（U 为该 PC 所属展开版本的 unroll factor）。

**Table A 扩展字段**：

| 新增字段 | 大小 | 说明 |
|---------|------|------|
| `tracked_warp_id` | 6 bit | 用于学习 stride 的代表 warp |
| `last_addr` | 64 bit | 该 warp 上次触发此 PC 的地址 |
| `iter_stride` | 32 bit | 学到的 iteration stride（bytes） |
| `stride_valid` | 1 bit | stride 是否已学到 |
| **额外存储** | **~13 B/entry** | 32 entries × 13B = **416 B** |

**学习算法**：

```python
def on_index_load_issue(warp_id, PC, current_addr):
    if PC not in Table_A:
        return

    entry_a = Table_A[PC]

    # === Stride Learning ===
    if not entry_a.stride_valid:
        if entry_a.tracked_warp_id == UNSET:
            # 首次触发：设定 tracked warp
            entry_a.tracked_warp_id = warp_id
            entry_a.last_addr = current_addr
        elif warp_id == entry_a.tracked_warp_id:
            # 同一 warp 再次触发 → 学到 stride
            entry_a.iter_stride = current_addr - entry_a.last_addr
            entry_a.stride_valid = True
            entry_a.last_addr = current_addr

    # === Prefetch ===
    pattern_key = (entry_a.data_base, entry_a.scale)
    if not Table_B[pattern_key].active:
        return

    if not entry_a.stride_valid:
        return  # stride 未学到 → 不发 prefetch（前序 PC stride 永不收敛 → 自然过滤）

    # Per-lane 地址生成（对应 32 个 SIMT lane）
    prefetch_addrs = [current_addr[lane] + entry_a.iter_stride for lane in active_lanes]

    # 经 Index Coalescer 合并为 sector 请求（32B 粒度，见 §4.3）
    sector_reqs = index_coalescer.coalesce_to_sectors(prefetch_addrs, active_mask)

    for req in sector_reqs:
        prb_id = PRB.allocate(table_b_idx=pattern_key_idx)
        if prb_id is None:
            stall()  # PRB 满，等待释放
        issue_l1_request(req.sector_addr, req.element_mask, prb_entry_id=prb_id, type=INDEX_PF)
```

**Per-PC stride 精确区分不同展开版本**：

SpMV 的 Duff's device 包含 ×16/×8/×4/×1 四个版本，共 30+ 个 Table A entry。但每个 entry 学到的 stride 精确反映其所属版本：

| PC 所属版本 | 学到的 iter_stride | 含义 |
|------------|-------------------|------|
| ×16 中的 PC | 16 × 4 = 64 bytes | 跨 1 个 ×16 窗口 |
| ×8 中的 PC  | 8 × 4 = 32 bytes  | 跨 1 个 ×8 窗口 |
| ×4 中的 PC  | 4 × 4 = 16 bytes  | 跨 1 个 ×4 窗口 |
| ×1 中的 PC  | 1 × 4 = 4 bytes   | 跨 1 个 ×1 迭代 |

每个版本的 prefetch 都恰好跨过自己的 unroll 窗口边界 → **100% 有效**，零冗余。

**训练速度**：stride learning 需要同一 warp 触发同一 PC 两次，即经历 1 个完整的 outer loop iteration。对于 BFS 内循环（邻居遍历），这通常在 kernel 启动后数百 cycles 内完成——与 Table B confidence 训练同步。

**代表 warp 的合法性**：所有 warp 执行相同的 kernel 代码，unroll 结构完全相同，只是数据地址不同。因此一个 warp 学到的 stride 对所有 warp 有效——`iter_stride` 是代码结构属性，不是数据属性。

### 4.6 表生命周期管理

Prefetcher 的各状态表在不同事件下需要清理或重置，以避免跨 kernel 的陈旧数据或 warp 退出后的悬挂状态。

| 事件 | 清理范围 | 理由 |
|------|---------|------|
| **Kernel Launch** | 清空 Table A + Table B + 所有 FIFO + PRB + Response FIFO + Data Coalescer Buffer | 新 kernel 的 PC 空间、base address、scale 全部不同，旧数据完全无效 |
| **Warp EXIT** | 清空该 warp 的 Register FIFO | Warp 退出后其寄存器状态无意义；Table A/B 保留供其他 warp 使用；PRB 条目无 warp_id，由 L1 响应自然回收 |
| **CTA 完成** | 无额外操作 | CTA 完成时其所有 warp 已 EXIT（已触发上述清理）；Table A/B 为 SM 级共享，不受 CTA 生命周期影响 |

**实现要点**：

1. **Kernel Launch 清表**：在 GPGPU-Sim 中对应 `gpu_sim_cycle()` 中 kernel launch 的初始化路径。可通过 `memset` 一次性清零所有表（Table A 960B + Table B 296B + Register FIFO 3KB + PRB 20B + Response FIFO 272B + Data Coalescer 192B ≈ 4.7 KB，单 cycle 内可完成）。

2. **Warp EXIT 清 Register FIFO**：将该 warp 的 FIFO head/tail 指针重置为 0 即可（1 cycle）。PRB 无 warp_id 字段，不需要按 warp 清理——其条目由 L1 响应返回时自然回收（Response FIFO 弹出 → PRB invalidate）。

---

## 5. 具体执行流示例

### 5.1 BFS：column_indices[offset] → dists[dst]

```
=== 训练阶段（前 3 次观测）===

Warp 0, 迭代 0:
  ISSUE: LDG.E R0, [R16.64]                    PC=0x0650  (column_indices[offset])
    → register_producer[warp0][R0] = {LOAD_RESULT, PC=0x0650}

  ISSUE: IMAD.MOV.U32 R11, RZ, RZ, 0x4         PC=0x0660
    → register_producer[warp0][R11] = {CONST_4}

  ISSUE: IMAD.WIDE R2, R0, R11, c[0x0][0x178]  PC=0x0670
    → R0 由 LOAD 产生 → 确认 IMA 地址计算
    → register_producer[warp0][R2] = {IMA_ADDR_COMPUTE, index_PC=0x0650, scale=4, base=dists_base}

  ISSUE: LDG.E R4, [R2.64]                     PC=0x0680  (dists[dst])
    → R2 由 IMA_ADDR_COMPUTE 产生 → 确认完整依赖链!
    → Table_A[0x0650] = {data_PC=0x0680, scale=4, data_base=dists_base}
    → Table_B[(dists_base, 4)].confidence++ → 现在 = 1

... 重复 2 次 (不同 warp 或同 warp 不同迭代) ...

  → Table_B[(dists_base, 4)].confidence = 3 → active = True!

=== 展开副本自动归并 ===

Warp 5, 展开版第 2 份:
  ISSUE: LDG.E R0, [R16.64+0x4]                PC=0x09c0  (column_indices[offset+1])
  ISSUE: IMAD.WIDE R2, R0, R11, c[0x0][0x178]  PC=0x09e0
  ISSUE: LDG.E R4, [R2.64]                     PC=0x09f0  (dists[dst_1])
    → Table_A[0x09c0] = {data_PC=0x09f0, scale=4, data_base=dists_base}
    → 同一个 Table_B[(dists_base, 4)] entry，已 active!

=== 预取阶段 ===

Warp 10, 迭代 i:
  ISSUE: LDG.E R0, [R16.64]                    PC=0x0650, addr=0xA000
    → Table_A lookup: PC=0x0650 → pattern_key=(dists_base, 4), active=True
    → Step 1: issue index prefetch at 0xA000 + 3×4 = 0xA00C
    → PRB ← {table_b_idx=pattern(dists_base,4) 的索引}（sector 请求携带 prb_entry_id）

  ... (~200 cycles, L2 返回 index prefetch) ...

  Index prefetch 返回: addr=0xA00C, value=42857 (= column_indices[offset+3])
    → Step 2: data_addr = dists_base + 42857 × 4 = dists_base + 0x29FA4
    → issue data prefetch at dists_base + 0x29FA4

  ... (~200 cycles, data 从 L2 填充到 L1) ...

Warp 10, 迭代 i+3:
  ISSUE: LDG.E R4, [R2.64]                     PC=0x0680, addr=dists_base + 0x29FA4
    → L1 HIT ✓ (已被 prefetch 填充)
```

### 5.2 BC reverse：1 index → 3 data prefetch

```
Pattern Table entry:
  key: (depths_base, 4)
  targets: [
    {base: depths_base,      scale: 4},   # depths[dst]
    {base: path_counts_base, scale: 4},   # path_counts[dst]
    {base: deltas_base,      scale: 8}    # deltas[dst] (double)
  ]

Index prefetch 返回 value=1234:
  → data prefetch #1: depths_base + 1234 × 4
  → data prefetch #2: path_counts_base + 1234 × 4
  → data prefetch #3: deltas_base + 1234 × 8
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
| **节流方式** | Confidence counter（简版） | 先验证核心预取功效，再精化节流 | Early eviction rate + 动态 depth（后期扩展） |
| **Prefetch depth** | Per-PC iter_stride（自适应学习，仅 stride_valid 时发出） | 两步 pipeline 总延迟 ~400 cycles（L2 ROP 200 cycles × 2 步）；per-PC stride learning 自适应，lead time ≈ 1 个 outer iteration ≈ 400+ cycles ≈ pipeline 需求；固定 n 在高展开 workload（SpMV ×16）下 81% 冗余，per-PC stride 精确区分不同展开版本，100% 有效；移除 fallback n=3，仅 stride_valid 时发出 prefetch：前序链（stride 不收敛）自然过滤，保证仅循环内 IMA 触发 prefetch | 固定 n=max(U)（需预知 U）；Table B distinct_pc_count（简单但对 Duff's device 高估） |
| **Max target arrays K** | K=3 | 覆盖 BC reverse（最大 case：3 个数组） | K=1（更简单但不覆盖 BC） |
| **Index prefetch 返回数据路由** | L1 client 模式（PRB entry ID 随请求穿过 L1/MSHR） | PRB 仅需 5 bit/entry（20B/SM）；复用 L1 已有的 multi-requestor 路由 | MSHR 标记（不覆盖 L1 HIT）；独立 Pending Buffer + CAM |
| **Prefetch coalescing** | Prefetcher 自带 Index/Data Coalescer（32B sector 粒度） | 对齐 A100 L1 sector 架构；LD/ST 流水线 coalescing unit 与指令结构性绑定 | 复用 LD/ST coalescer（不可行）；per-lane 独立请求（MSHR 压力过高） |
| **MSHR 满时行为** | Index prefetch: 阻塞等待；Data prefetch: 丢弃 | Index prefetch 是两步 pipeline 的 Step 1，丢弃会导致 Step 2 断裂；Data prefetch 是 fire-and-forget | 统一丢弃（原设计，损失 prefetch 机会） |
| **地址计算并行度** | 8-wide 并行 ACU（1 cycle 处理一个 sector 的所有元素） | 对齐 sector 粒度（32B/4B=8 elements） | 32-wide（按 cache line 处理，与 sector 架构不匹配）；串行（太慢） |
| **多响应并发** | Response FIFO（depth=8）+ 反压 L1 | 多个 sector 响应可能同时到达；反压不影响 demand load 路径 | 丢弃溢出响应 |

---

## 7. 硬件预算估算

### 7.1 Per-SM 存储开销

| 组件 | 条目数 | 每条大小 | 总大小 | 说明 |
|------|--------|---------|--------|------|
| **Table A** (PC Dep Table) | 32 | PC(32b) + data_PC(32b) + scale(8b) + base(64b) + valid(1b) + tracked_warp_id(6b) + last_addr(64b) + iter_stride(32b) + stride_valid(1b) ≈ 30B | **960 B** | 覆盖 SpMV 30+ unrolled PC；含 per-PC stride learning 字段 |
| **Table B** (Pattern Table) | 8 | key(72b) + confidence(4b) + active(1b) + 3×target(72b×3) + valid(1b) ≈ 37B | **296 B** | 8 个 IMA pattern 足够 |
| **PRB** (Prefetch Request Buffer) | 32 | valid(1b) + table_b_idx(4b) = 5 bit | **20 B** | 在途 index prefetch sector 请求（原 Pending Buffer 320B → 20B） |
| **Response FIFO** | 8 | prb_entry_id(5b) + sector_data(32B) + element_mask(8b) ≈ 34B | **~272 B** | 缓冲 L1 返回的 sector 级 index prefetch 响应 |
| **Data Coalescer Buffer** | 32 | sector_addr(~40b) + valid(1b) ≈ 6B | **~192 B** | 缓冲 ACU 输出的 data prefetch sector 请求 |
| **Register FIFO** | 64 warp × 8 entries | dst_reg(8b) + type(2b) + PC(32b) + ima_info(可选) ≈ 6B | **~3 KB** | Per-warp FIFO 用于依赖链检测 |
| **总计** | | | **~4.7 KB/SM** | |
| **总计（不含 Register FIFO）** | | | **~1.7 KB/SM** | 核心预取逻辑 |

**Table A 容量设计依据**：

Table A 的 32 entry 由 loop unrolling 分析确定——compiler 的循环展开直接决定了同一逻辑 load 对应多少不同的 SASS PC：

| Workload | Unrolled index PCs | 展开方式 | 说明 |
|----------|-------------------|---------|------|
| BFS | ~5 | ×4 + remainder | 4 份展开体 + 1 份尾部 |
| SSSP | ~5 | ×4 + remainder | 同 BFS |
| SpMV | **30+** | ×16 + ×8 + ×4 + ×1 | 多级 Duff's device 风格展开，sizing bottleneck |
| BC reverse | ~5 | ×4 + remainder | one-to-many 不增加 Table A 占用（共享 index_PC） |
| CC hook | ~5 | ×4 + remainder | 同 BFS |

SpMV 的 30+ PC 是 sizing bottleneck。32 entry 覆盖所有已分析 workload，但余量有限（~2 空闲 entry）。如目标扩展到更激进展开的 kernel，可扩展至 48 或 64 entry（每 entry 30B，增量 ~0.5-1.0 KB）。

BC reverse 的 one-to-many（3 个 target array）**不增加 Table A 占用**——所有 target 共享同一个 `index_PC` 的 Table A entry，差异由 Table B 的 `targets[K=3]` 吸收。这是 Table A/B 分离设计的一个工程优势。

### 7.2 对比参考

| Prefetcher | 存储开销/SM | 来源 |
|------------|-----------|------|
| IMP | 0.7 KB | Indirect Memory Prefetcher (2015) |
| Tyche | 0.57 KB | Tyche (2024) |
| Spare Register | 1.365 KB | Spare Register Aware Prefetching (2014) |
| **本方案（核心）** | **~1.7 KB** | 不含 Register FIFO |
| **本方案（含 FIFO）** | **~4.7 KB** | 含 64 warp × 8-entry Register FIFO |

### 7.3 Register FIFO 的开销分析

Register FIFO 占总存储的 ~64%（3 KB / 4.7 KB），但这是为 64 个 warp 提供**独立依赖链检测**的必要开销。与原设计（12 KB 全量 register producer table）相比已节省 75%。

**进一步优化空间**（实现阶段验证）：

1. **训练-冻结机制**：当 Table A/B 中所有 pattern 均已 active 时，可关闭 FIFO 追踪。此后 Register FIFO 存储可释放或断电。对于 BFS/SpMV 等稳态 kernel，冻结在第一轮迭代结束后即可触发。
2. **FIFO 深度缩减**：如果实验表明 4-entry FIFO 足以覆盖大部分 IMA 链（BFS unroll×4 的链长 ≤ 4），可将深度从 8 降到 4，存储减半至 ~1.5 KB。
3. **CTA 内共享**：同 CTA 的 warp 执行相同 PC 序列，理论上可共享一个 FIFO（但实现复杂度高，需仲裁）。

**相对参考**：A100 每 SM 的 register file 为 256 KB，L1D/shared memory 为 192 KB。4.7 KB 约占 register file 的 1.8%，开销可接受。

**硬件逻辑开销**（非存储）：
- 8 × barrel shifter + 8 × 64-bit adder（ACU，8-wide 并行地址计算）
- Index Coalescer + Data Coalescer（按 32B sector 分组 + 去重）

---

## 8. 与已有工作的差异化

| 维度 | CPU IMP (2015) | CPU Tyche (2024) | GPU Spare Reg (2014) | **本方案** |
|------|---------------|-----------------|---------------------|-----------|
| 目标平台 | CPU | CPU | GPU | **GPU** |
| 检测信号 | PC + stride | PC + propagation | Compiler annotation | **Register dependency chain** |
| 地址推断 | 观测 addr diff → 推 shift/base | 依赖链传播 | 编译器注入 prefetch 指令 | **IMAD.WIDE 操作数直接提取 scale/base** |
| Loop unrolling | N/A (CPU 少展开) | N/A | N/A | **(base, scale) 归组，自动归并** |
| 硬件辅助 | Hardware table | Hardware propagation table | Spare register file | **Two-table + PRB + 8-wide ACU** |
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
| ~~Unified 还是 hybrid 方案？~~ | Unified 两步 pipeline，覆盖 Pattern I+II | §3 |
| ~~Coalescing 交互~~ | Prefetcher 自带 Index/Data Coalescer（32B sector 粒度），不复用 LD/ST 流水线 | §3.3.1 |
| ~~MSHR 竞争~~ | 共享 MSHR；Index prefetch MSHR 满时阻塞等待（保证 Step 2 触发），Data prefetch MSHR 满时丢弃 | §3.3.1 |
| ~~Register Producer Table 精简~~ | 已改为 per-warp FIFO（8 entry/warp），~3 KB/SM（原 12 KB 降 75%） | §4.1 / §7 |
| ~~Active Mask 处理~~ | 使用当前 active_mask，不预测未来 mask | §3.3.1 |
| ~~表清理策略~~ | Kernel launch 清全表（含 PRB + Response FIFO + Data Coalescer）；warp EXIT 清该 warp Register FIFO | §4.6 |
| ~~训练模型~~ | Per-warp detection + shared Table A/B；64 warp 并行训练，阈值 3 在首轮迭代达标 | §4.1 |
| ~~Data prefetch 带宽~~ | 已知风险（32 scattered × K），先实验再节流 | §4.3 |
| ~~地址计算硬件~~ | 8-wide 并行 ACU（8 × barrel shifter + 8 × 64-bit adder），1 cycle/sector，不需要乘法器 | §4.3.4 |
| ~~Cache hit 处理~~ | L1 tag check + MSHR merge，标准流程；HIT/merge 时不消耗额外 L2 带宽 | §3.3.1 |
| ~~Pending Buffer 设计~~ | PRB（5 bit/entry × 32 = 20B/SM），L1 client 模式：请求携带 prb_entry_id，响应返回 sector data + element_mask | §4.3.2 |
| ~~Sector 粒度~~ | 对齐 A100 L1 sector（32B）架构，prefetcher 以 sector 为操作单位（请求/响应/coalescing 均为 32B 粒度） | §3.3.1, §4.3 |
| ~~多响应并发~~ | Response FIFO（depth=8, ~272B）缓冲 L1 返回的 sector 响应，满时反压 L1（不影响 demand load） | §4.3.3 |
| ~~Prefetch distance~~ | Per-PC iter_stride 自适应学习（仅 stride_valid 时发出，无 fallback），精确区分不同展开版本 | §4.5 |
| ~~Unrolling 与 MLP 交互~~ | LDG 是 non-blocking（scoreboard-based），unrolling 创造 MLP；固定 n=3 在 SpMV ×16 下 81% 冗余，per-PC stride 解决 | §4.5 |
| ~~False positive 风险~~ | 写无效化保证 FIFO 不变量，BFS 实证 14 条 IMAD.WIDE 零误检 | §4.1.1 |
| ~~前序链无效 prefetch~~ | Gate on stride_valid + Table A 淘汰优先驱逐 stride_valid=false entry | §4.5, §3.2 |

### 待深化

| 问题 | 优先级 | 说明 |
|------|--------|------|
| Stride 自动检测 vs 固定值 | 中 | 当前假设 stride=4（int32），double 类型的 index array 需要 stride=8；可从 Table A 的 scale 推断 |
| Throttle 精细化 | 中 | Confidence counter 是最简版，后续需评估 early eviction rate 和带宽感知节流 |
| FIFO 深度优化 | 低 | 8-entry 是保守值，实验可能表明 4-entry 已足够（节省 ~1.5 KB） |
| 训练-冻结机制 | 低 | Table A/B 全部 active 后可关闭 FIFO 追踪，节省动态功耗 |
| BC/CC 的 SASS 逐指令验证 | 低 | BFS 已验证写无效化的有效性；BC/CC SASS 更复杂，实现时做同样的逐指令验证 |

### 下一步

1. **Phase 4: 实现**：在 GPGPU-Sim 中实现上述设计，代码修改集中在 `gpu-cache.cc`、`shader.cc` 等文件
2. **第一轮实验**：在 ima_high workload 上验证 prefetch 正确性和基本效果
3. **参数扫描**：验证 per-PC stride learning 的 convergence 和效果
4. **精化**：根据实验结果调整 table 大小、throttle 策略等
