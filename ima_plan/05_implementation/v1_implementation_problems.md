# 实现问题分析

> 本文对照 `04_prefetcher_design.md`，从 GPGPU-Sim 源码结构出发，
> 逐条分析将设计落地时会遭遇的障碍。每个问题下预留"我的思路和解决办法"
> 供讨论和记录，后续的实现决策应在此文档中更新。
>
> 最后更新：2026-03-18

---

## 问题速览

| 编号 | 问题 | 严重度 | 涉及组件 |
|------|------|--------|---------|
| [P1](#p1-component-3-在-trace-driven-模式下无运行时数据值) | DPU 在 trace-driven 模式下无运行时数据值 | **阻塞** | DPU (Data Prefetch Unit) |
| [P2](#p2-per-warp-fifo-深度对-spmv-16-展开不足) | per-warp FIFO 深度对 SpMV ×16 展开不足 | ~~高~~ → **中**（不需要 per-warp，深度需求可控） | CD (Chain Detector) |
| [P3](#p3-imadwide-的-c0x00x178-基地址解析路径缺失) | IMAD.WIDE 的 `c[0x0][0x178]` 基地址解析路径缺失 | ~~高~~ → **已简化**（由 P1 方案连带解决） | CD (Chain Detector) |
| [P4](#p4-imadwide-无专用-op_type只能字符串匹配识别) | IMAD.WIDE 无专用 `op_type`，只能字符串匹配 | **中** | CD (Chain Detector) |
| [P5](#p5-fill-路径中-index-prefetch-无法识别pending-buffer-匹配需新机制) | fill 路径中 index prefetch 无法识别，pending buffer 匹配需新机制 | ~~中~~ → **已简化**（由 P1 方案连带解决） | DPU (Data Prefetch Unit) |
| [P6](#p6-data-prefetch-的多-lane-地址生成无法走正常-coalescing-路径) | data prefetch 多 lane 地址生成无法走正常 coalescing 路径 | **中** | DPU (Data Prefetch Unit) |
| [P7](#p7-pending-buffer-容量被严重低估) | Pending Buffer 容量被严重低估 | ~~中~~ → **已消除**（由 P1 方案连带解决） | DPU (Data Prefetch Unit) |
| [P8](#p8-kernel-launch--warp-exit-清表的-hook-位置) | Kernel launch / Warp EXIT 清表的 hook 位置 | **低** | 生命周期管理 |

---

## P1: DPU 在 trace-driven 模式下无运行时数据值

### 问题描述

Index-Data Pipeline 的 Step 2 公式：`data_addr = base + value × scale`

其中 `value` 是 index prefetch 从 L2 返回时 cache line 中的实际数据（如 `column_indices[offset+3]` 的运行时内容）。

**GPGPU-Sim 的 fill 路径只提供时序通知，没有数据 payload：**

```cpp
// shader.cc::ldst_unit::fill()
void ldst_unit::fill(mem_fetch *mf) {
  mf->set_status(IN_SHADER_LDST_RESPONSE_FIFO, cycle);
  m_response_fifo.push_back(mf);   // 只有时序，无数据
}
```

`gpu-cache.cc::baseline_cache::fill()` 调用 `m_tag_array->fill()` 标记 cache line 为 VALID，
调用 `m_mshrs.mark_ready()` 唤醒 demand 请求，**但不向外部提供 cache line 数据内容**。

Trace-driven GPGPU-Sim 本质上只模拟时序，不维护功能性数据状态：无 functional register file，无 cache line data store。

**相关文件：** `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc`（`ldst_unit::fill()`），`gpu-cache.cc`（`baseline_cache::fill()`）

### 可能的出路

| 方案 | 说明 | 代价 |
|------|------|------|
| **只做 Step 1** | 跳过 DPU，只做 index array prefetch | 放弃 data miss 缓解（设计 novelty 损失大） |
| **从 demand data load 地址反推** | 当 demand `LDG dists[v]` 在 L1_latency_queue 执行时，地址已知 = `dists_base + v*4`，反推 `v`，用于下一迭代的 data prefetch | 触发点后移（demand 执行时而非 index prefetch 返回时）；时效性需验证 |
| **扩展 NVBit tracer 记录 load 返回值** | tracer 记录每个 load 的数据值，trace-driven 重放时提供 | tracer 改动大，trace 文件大幅膨胀 |

### 我的思路和解决办法

> 这个问题的核心是拿不到返回值，计算不出来要预取的地址，那我们的解决方式肯定是想办法可以得到想要预取的地址。目前你提的这几个方案我觉得都不是很好，我的方案在下面说明，**需要注意的是**因为我现在对整个仿真系统还不是很了解，所以提出的建议可能不是最优的，你需要根据你对系统的了解想办法优化我的方案
> 首先明确一个点，寄存器值是肯定不知道的，所以我们要跳过对移位加法算地址的模拟，用正常的 cycle 倒数来模拟占用的时间，应该就是 1 个 cycle。而想要预取的地址实际上我们是知道的，因为 trace 中带有地址，但是问题是怎么让这个地址提前发出？
> 1. 假设现在执行 A[B[i]]，我要对地址 A[B[i+3]] 进行预取。首先预取器会先发一个 B[i+3] 的预取，这很容易，不需要寄存器值。而对于后者的预取，我的想法是，给每个 warp 额外设置一个buffer，存储当前指令后的 trace 指令流,地址信息此时已经包含进去了，当发起 B[i+3] 的预取时，已经能够索引到对应的 A[B[i+3]] 地址，但是此时不能发起预取因为从硬件的角度仍然是未知的，直到 Pending Buffer 返回后，再 delay 一个计算的 cycle，才能发起这次预取
> 2. 第二个方法和第一个类似，建立起每个 index 和 预取地址的映射关系表，每次发起哪个 index，就知道要预取哪些地址了。但是我不知道这个会不会导致模拟变得很慢

### 可行性分析与推荐实现（基于真实 trace）

#### 真实 trace 中的 IMA 结构（BFS kernel-11, warp 0）

```
PC    mask      opcode           地址/字段
──────────────────────────────────────────────────────────────
00a0  ffffffff  IMAD.MOV.U32 R24 imm=4    → R24 = 4 (scale)
00b0  ffffffff  IMAD.WIDE R2, R0, R24     → R2 = row_ptr_byte_offset
00c0  ffffffff  LDG.E R2  [R2]  0x7f1244600000, stride=4  → row_ptr[tid]
00d0  ffffffff  IMAD.MOV.U32 R5  imm=8   → R5 = 8
00e0  ffffffff  IMAD.WIDE R4, R2, R5     → R4 = col_idx_addr
00f0  ffffffff  LDG.E R17 [R4]  base=0x7f125c9c86c0,
                                deltas=[-4993568, +592696, ...]  ← INDEX LOAD
0100  ffffffff  LDG.E R22 [R4+8] (same deltas)
...（约 13 条指令）
01b0  f6f9475b  IMAD.WIDE R24, R17, R24, 0  → 计算 data 地址
01d0  f6f9475b  LDG.E R0  [R24] base=0x7f125dc204d8,
                                deltas=[-13919396, +2112732, ...]  ← DATA LOAD
```

**可行性确认**：
- INDEX LOAD（`00f0`）和 DATA LOAD（`01d0`）都在 trace 中，相距 **~13 条指令**（同一外层迭代内）
- 两者均包含 per-lane 地址（addrcompress=2：base + 31 个 delta）
- 配对方式：按出现顺序（第 k 次 `PC_idx` 记录对应第 k 次 `PC_data` 记录），不需要按地址查找

#### 确定方案：per-CTA 地址映射表 + 真实返回时序

> **方案演进说明**：早期讨论中曾提出"滑动窗口 + 立即发出 data prefetch"方案，
> 后经审视认为**立即发出在硬件上不可实现**（真实 prefetcher 无法在 index 返回前知道 data_addr），
> 会导致评估结果过度乐观。修订为以下方案，在时序上忠实于真实硬件行为。

**核心思路**：利用 Accel-Sim 的 traceg 按 CTA 存储、`warp_traces` 全量加载的特性，
在 `init_traces()` 后预扫描 trace 构建 `idx_addr → data_addr` 映射表。
运行时仅用映射表替代"从 index 返回值计算 data_addr"这一步（trace-driven 做不到），
**但时序上仍等 index prefetch 真正返回后才发 data prefetch**。

**关键代码基础**（`trace_driven.h:142-164`）：

```cpp
class trace_shd_warp_t : public shd_warp_t {
  std::vector<inst_trace_t> warp_traces;  // 全量加载，init_traces() 后即可遍历
  unsigned trace_pc;                       // 执行指针，可自由前后索引
};
```

**映射表数据结构**（新增到 `trace_shd_warp_t`）：

```cpp
struct ima_chain_map {
  unsigned pc_idx;     // index load 的 PC
  unsigned pc_data;    // data load 的 PC
  std::unordered_map<uint64_t, uint64_t> addr_map;  // idx_addr → data_addr
};
std::vector<ima_chain_map> ima_maps;  // 每条 IMA chain 一张映射表

// 统计计数器
unsigned long long stat_mapping_hit = 0;
unsigned long long stat_mapping_miss = 0;
```

**构建流程**：

```
init_traces() 完成后:
  for each warp:
    for each IMA chain (pc_idx, pc_data):
      idx_occurrence = 0, data_occurrence = 0
      scan warp_traces 顺序遍历:
        if inst.m_pc == pc_idx && inst.memadd_info:
          记录 per-lane idx_addrs[idx_occurrence]
          idx_occurrence++
        if inst.m_pc == pc_data && inst.memadd_info:
          for lane in active_lanes:
            addr_map[idx_addrs[data_occurrence][lane]] = inst.memadd_info->addrs[lane]
          data_occurrence++
```

**运行时流程**：

```
on_index_prefetch_fill(warp_id, chain_id, idx_addr):
  data_addr = ima_maps[chain_id].addr_map.lookup(idx_addr)
  if found:
    stat_mapping_hit++
    delay 1 cycle (模拟 IMAD.WIDE 计算)
    issue data prefetch for data_addr
  else:
    stat_mapping_miss++  // 保守处理：跳过 data prefetch
```

**仿真中的"诚实"与"作弊"分界**：

| 仿真中"作弊"的部分 | 仿真中"诚实"的部分 |
|---|---|
| data_addr 从映射表查到（真实硬件从 index 返回值计算） | 时序忠实：等 index prefetch 真正返回后才发 data prefetch |
| | 带宽消耗忠实：prefetch 占用相同的 MSHR/NoC/L2 资源 |

**映射唯一性保证**：对于 read-only index array（BFS/SSSP/CC/SpMV/BC 的 `col_indices[]`、`row_offsets[]` 均满足），同一 `idx_addr` 在任何迭代中读到的值相同，因此 `idx_addr → data_addr` 映射无冲突。若未来扩展到写 index array 的 workload，需重新评估。

**正确性验证**：在 demand data load 执行时做 runtime assertion：

```
当 trace_pc 到达 PC_data 时:
  actual_data_addr = warp_traces[trace_pc].memadd_info->addrs[lane]
  predicted_data_addr = mapping[对应的 idx_addr]
  assert(actual_data_addr == predicted_data_addr)  // debug 模式开启
```

**前置依赖**：
- 需要已知 `(PC_idx, PC_data)` 对（来自 CD 依赖链检测 / CT / SASS 分析）
- 需要在 `init_traces()` 后增加映射表构建步骤
- 需要给 `mem_fetch` 添加 prefetch 类型字段（P5 简化方案）

---

## 补充讨论（P1 相关扩展）

### 讨论 A：多层嵌套 `a[b[c[i]]]`

多层嵌套应拆为**独立的 IMA chain**，每层一张映射表：

```
Chain 1: PC_idx = load c[i],       PC_data = load b[c[i]]
  → mapping_1: addr_of_c[i] → addr_of_b[c[i]]

Chain 2: PC_idx = load b[c[i]],    PC_data = load a[b[c[i]]]
  → mapping_2: addr_of_b[c[i]] → addr_of_a[b[c[i]]]
```

从 SASS 依赖链检测角度，两条 chain 各有独立的 `(PC_idx, IMAD.WIDE, PC_data)` 三元组，FIFO 中的寄存器依赖链会分别匹配。

Prefetch 行为：Chain 1 的 data prefetch 返回后，若命中 Chain 2 的 index load 检测，会**自动触发 Chain 2 的 data prefetch**，形成 pipeline。

**当前状态**：目标 workload（BFS/SSSP/CC/SpMV/BC）均为单层 IMA（`data[col_indices[offset]]`），暂不需要实现多层支持。设计上每条 chain 独立映射表即天然支持。

### 讨论 B：多目标（同一 index 对应多个 data 数组）

如 BC 算法中：

```
sigma[col_indices[offset]]    → IMA chain 0
delta[col_indices[offset]]    → IMA chain 1
```

同一个 `idx_addr`（`col_indices[offset]` 的地址）在不同 chain 中映射到不同的 `data_addr`（sigma vs delta）。

**单一映射表会冲突**。解决方案：**每条 IMA chain 独立映射表**。

- 映射 key 含 chain 身份：`chain_map[chain_id][idx_addr] → data_addr`
- fill 回调时 `mem_fetch` 携带 `chain_id`，直接定位到对应 table，O(1) 查找
- 这与数据结构设计自然一致：`std::vector<ima_chain_map> ima_maps`

### 讨论 C：Lane mask 不匹配（prefetch 预测地址在映射表中缺失）

**问题**：Prefetcher 基于当前 active mask 发出 index prefetch。但下一迭代中某些 lane 可能不再活跃（如 BFS frontier 变化），导致：

1. 预测的 `idx_addr` 对应的 lane 在下一迭代不执行 `PC_data`
2. Trace 中无该 lane 的 `PC_data` 记录
3. 映射表中无此 `idx_addr → data_addr` 条目

**分层处理**：

| 层面 | 处理方式 |
|------|---------|
| **Index prefetch** | 始终发出——预测的 idx_addr 是 index array 中的合法地址，即使该 lane 未来不活跃 |
| **Data prefetch** | 查映射表；若 miss 则跳过该 lane 的 data prefetch |

**为什么 miss 时可以跳过**：

- 映射表覆盖 warp **全生命周期**（所有迭代、所有 lane），多数"幻影地址"仍可命中（因为 read-only index array 的唯一性：不同迭代中相同 `idx_addr` 产生相同 `data_addr`）
- 真正 miss 的情况：stride 预测越界到 warp 从未访问过的 index array 区域（stride 本身可能不准确）
- 这些 data prefetch 在真实硬件中也是 **useless** 的（无对应 demand load），少发一些反而让评估更保守

**量化误差**：

```
stat_mapping_miss / (stat_mapping_hit + stat_mapping_miss)
```

- **< 5%**：可忽略
- **5–20%**：考虑 cross-warp 共享映射表（同一 CTA 内所有 warp 合建，覆盖更多 idx_addr）
- **> 20%**：需审视 stride 预测策略本身

---

## P2: per-warp FIFO 深度对 SpMV ×16 展开不足

### 问题描述

设计文档 §4.1 说"8-entry FIFO 足以覆盖 BFS unroll×4（4条LDG + 4条IMAD.WIDE = 8条相关指令）"。
但对 SpMV ×16 展开，FIFO 只记录"相关指令"（LDG、IMAD.WIDE、IMAD.MOV），实际序列为：

```
IMAD.MOV R_scale                        → FIFO[0]
LDG R0,  [index_0]                      → FIFO[1]
LDG R2,  [index_1]                      → FIFO[2]
...
LDG R30, [index_15]                     → FIFO[16]  ← 超出 8-entry！
--- FIFO 满，FIFO[0]（IMAD.MOV）被淘汰 ---
IMAD.WIDE R_, R0, R_scale, c[..]        → 查找 R0 ✓，查找 R_scale → None（已被淘汰）
                                         → scale 不可知 → 依赖链断裂
```

LDG R0 和 IMAD.WIDE [uses R0] 之间还有 15 个其他 LDG，FIFO 深度 8 无法同时保留 R_scale 和所有 16 个 LDG 的 LOAD_RESULT 条目。

设计文档 §7.1 将 SpMV 30+ PC 列为 CT 的 sizing bottleneck，但 §4.1 的 FIFO 深度论证仅针对 BFS ×4，**未覆盖 SpMV ×16 的实际情况**。

**相关文件：** `04_prefetcher_design.md` §4.1（Per-Warp FIFO 设计说明）

### 我的思路和解决办法

> 这个 fifo 每个 entry 是否可以是记录一个依赖链，而非一个指令 PC，然后对于 spmv 这种 16 unrollling 对情况，我们对应扩充 fifo 大小应该就可以吧，比如我们设置为 20 或 32 个 entry，同时要考虑物理开销

### 讨论结论

#### 问题描述修正：IMAD.MOV 不参与检测链

原问题描述将 IMAD.MOV 纳入 FIFO 必须保留的指令，但 Chain Detector (CD) 的检测目标是：

```
LDG(dst=Rx) → IMAD.WIDE(src=Rx, dst=Ry) → LDG(addr=Ry)
```

检测器只追踪 LDG 和 IMAD.WIDE 之间的寄存器**生产-消费关系**：
- IMAD.WIDE 发射时，回溯 FIFO 找到写了 `Rx` 的 LDG → 确认为 index load
- 后续 LDG 发射时，回溯 FIFO 找到写了 `Ry` 的 IMAD.WIDE → 确认为 data load

IMAD.MOV 提供的 `R_scale` 只是 IMAD.WIDE 的另一个操作数，**不影响 IMA chain 的结构识别**。检测器不需要知道 scale 的来源——它只需确认"一个 LDG 的结果经过 IMAD.WIDE 变成了另一个 LDG 的地址"。因此 FIFO 中不需要保留 IMAD.MOV，FIFO 深度需求相应降低。

#### FIFO 不需要 per-warp

检测结果是 `(PC_idx, PC_data)` 对——这是 **PC 级别**的信息，与具体 warp 无关。所有执行同一 kernel 的 warp 共享同一套 PC 序列，因此一个 warp 的检测结果对所有 warp 有效。

FIFO 只需在 SM 级别维护**一份**，选定某个 warp 追踪其指令流即可。面积开销从 `64 warps × N entries` 降至 `1 × N entries`。

以 SpMV ×16 为例（N=32），硬件开销对比：

| 方案 | 条目总数 | 每条目 ~60 bits | 总面积/SM |
|------|---------|----------------|----------|
| per-warp FIFO | 64 × 32 = 2048 | 60b | ~15 KB |
| **共享 FIFO** | 1 × 32 = 32 | 60b | **~240 B** |

#### FIFO 深度分析（无 IMAD.MOV）

对 SpMV ×16（最坏情况），FIFO 中只有 LDG 和 IMAD.WIDE：

```
当 IMAD.WIDE[0] issue 时：
  FIFO 已有 16×LDG → 需要找到 LDG[0]（距离=16）→ 深度 ≥ 16

当 IMAD.WIDE[k] issue 时：
  FIFO 已有 16×LDG + k×IMAD.WIDE → 需要找到 LDG[k]（距离=16+k-k=16）
  但同时也需要 IMAD.WIDE[k] 被后续 LDG_data[k] 回溯到
  → LDG_data[k] 与 IMAD.WIDE[k] 之间距离取决于指令排列
```

**关键观察**：如果 SpMV ×16 的 16 次展开使用**不同的 PC**（全展开场景），则需要 16 次独立链检测。如果使用**相同的 PC**（循环体），CT 一次学习即可。这决定了 FIFO 深度的实际需求——需要查看具体 SpMV trace 确认。

#### Pending Question

- **追踪 warp 选择策略**：如何在 warp 交错调度下保证 FIFO 内容的连续性？候选方案：(a) 固定追踪 warp 0；(b) 追踪第一个到达目标 PC 的 warp；(c) per-scheduler 各追踪一个 warp。
- **需确认**：SpMV ×16 展开在 SASS 层面是全展开（16 个不同 PC）还是循环体（1 个 PC 重复执行 16 次），这决定 FIFO 深度需求。

**严重度修正**：**高** → **中**（不需要 per-warp，深度需求可控）

---

## P3: IMAD.WIDE 的 `c[0x0][0x178]` 基地址解析路径缺失

### 问题描述

Chain Detector (CD) 需要从 IMAD.WIDE 提取 `data_base`（如 `dists[]` 数组的 64-bit 指针）。

`IMAD.WIDE R2, R0, R11, c[0x0][0x178]` 中：

- **静态偏移**（`0x178`）：在指令编码中。`inst_trace_t` 有 `uint64_t imm` 字段可能捕获该偏移，但 `trace_driven.cc` 的解析路径（lines 193–249）**未显式将其传递到 `warp_inst_t`**。

```cpp
// trace_parser.h
struct inst_trace_t {
  ...
  uint64_t imm;   // 有 imm 字段
  ...
};

// trace_driven.cc (lines 193-249 中没有 this->imm = trace.imm 这样的赋值)
```

- **运行时指针值**（`c[0x0][0x178]` 的实际内容）：= kernel parameter memory 第 `0x178` 字节处的 8-byte 值。需要在 kernel launch 时通过 `kernel_info_t` 提取。GPGPU-Sim 有 `param_space_kernel` 内存空间，但没有现成的"constant memory offset → runtime pointer"查找 API。

**双重挑战：** 静态偏移的传递路径缺失 + 运行时指针的解析路径缺失，两者缺一则无法拿到 `data_base`。

**相关文件：** `trace-parser/trace_parser.h`（`inst_trace_t::imm`），`trace-driven/trace_driven.cc`（解析路径），`abstract_hardware_model.h`（`param_space_kernel`）

### 我的思路和解决办法

> 这个值我们不需要拿到，因为这个值是用来计算地址的，而我们已经在 P1 解决了地址的问题，所以获得不到值其实没有关系。但在仿真过程中只仍要模拟拿到这个值的过程，即在 TT 时记录这次的得到的 baseaddr 和 stride，因为我们实际上是模拟这个预取器在硬件上的行为

### 讨论结论

#### P1 映射表完全消解此问题

`c[0x0][0x178]` 的运行时值（data array 基地址指针）在 Prefetcher 三个组件中的需求分析：

| 组件 | 是否需要 `c[0x0][0x178]` 值 | 原因 |
|------|---------------------------|------|
| CD（依赖链检测） | **否** | 检测基于寄存器依赖模式匹配（LDG→IMAD.WIDE→LDG），不需要操作数的运行时值 |
| IPU（Stride 预测） | **否** | Stride 预测作用于 index load 地址的 delta（连续迭代的 `&col_indices[offset]` 之差），与 data array 基地址无关 |
| DPU（Data prefetch 地址） | **否** | P1 映射表提供 `idx_addr → data_addr` 直接查找，替代了 `base + value × scale` 计算 |

因此 `c[0x0][0x178]` 的运行时值在 trace-driven 实现中**完全不需要获取**。原问题描述中"双重挑战（静态偏移传递 + 运行时指针解析）"均不再构成障碍。

#### TT 保留为训练状态机

虽然 `base_addr` 和 `stride` 的实际值不再需要（用占位符替代），但 TT 的 **valid bit** 仍有意义——它代表硬件 prefetcher 的训练状态：

```
TT entry 状态机：
  INVALID → 首次检测到 chain（CD 写入 CT 触发）→ TRAINING
  TRAINING → 确认 stride 稳定（连续 N 次 delta 一致）→ VALID

  只有 VALID 状态下，映射表中预备好的 data_addr 才允许发出 prefetch
```

这保证了仿真时序的忠实性：真实硬件 prefetcher 在训练完成前不会发出 data prefetch，模拟器也应如此。若跳过此约束（检测到 chain 立刻发），会导致评估结果过度乐观（首次迭代就有 data prefetch，真实硬件做不到）。

TT 中 `base_addr`、`stride` 字段改为占位符：仿真器记录它们仅用于调试输出，不参与地址计算（地址来源已切换为 P1 映射表）。

**严重度修正**：**高** → **已简化**（由 P1 方案连带解决，仅需 valid bit 状态机）

---

## P4: IMAD.WIDE 无专用 `op_type`，只能字符串匹配识别

### 问题描述

`trace_driven.cc` 解析 IMAD 系列指令时，通过字符串前缀统一处理：

```cpp
// trace_driven.cc:220
if (opcode1 == "IMAD") {
  if ((opcode == "IMAD.MOV") || (opcode == "IMAD.IADD")) sp_op = INT__OP;
  // IMAD.WIDE 无特殊分支 → op_type/sp_op 与普通 IMAD 相同
}
```

`warp_inst_t::op`（`op_type` enum）**不区分 IMAD.WIDE、IMAD.MOV.U32、普通 IMAD**。

Chain Detector (CD) 在 `issue_warp()` 中只能访问 `warp_inst_t`，
无法用 `inst->op == IMAD_WIDE_OP` 筛选——必须调用 `opcode_from_inst()` 重建字符串（每次 issue 有字符串操作开销），或修改 ISA 定义文件为 IMAD.WIDE 添加专用枚举值。

**相关文件：** `trace-driven/trace_driven.cc`（line 220），`ISA_Def/ampere_opcode.h`（ISA 枚举定义），`shader.cc::issue_warp()`（line 1661：`opcode_from_inst()`）

### 我的思路和解决办法

> **由于我对整个 Accel-sim 的构造不够深入，所以需要你判断我的方法是否可行。如果不可行，能否借鉴我的思路想到别的解决办法**我认为是否可以在 trace_warp_inst_t 里新增一个字段，直接保存原始 trace.opcode，这样就可以直接识别 IMAD.WIDE 了

### 讨论结论

#### `opcode_from_inst()` 在 trace-driven 模式下不可用（已验证）

完整调用链分析：

```
opcode_from_inst(inst, config)                    // shader.cc:324
  → opcode_token(config, inst->pc)                // shader.cc:311
    → func_sim->ptx_get_insn_str(pc)              // cuda-sim.cc:563
      → g_pc_to_finfo.find(pc)                    // 查找 PC → function_info 映射
```

**根因**：`g_pc_to_finfo` 仅在 `function_info::ptx_decode_inst()`（PTX 功能仿真路径，`cuda-sim.cc:314`）中填充。trace-driven 模式使用 `trace_function_info`，不执行 PTX decode，该 map **始终为空**。

运行时行为：
1. `ptx_get_insn_str(pc)` 查 `g_pc_to_finfo` → miss → 返回 `"<no instruction at address 0x...>"`
2. `opcode_token()` 检测到 `token[0] == '<'` → 返回空字符串
3. `opcode_from_inst()` 走 fallback → 返回 `op_type_str(inst->op)`，即泛化名称（`"INTP_OP"`、`"LOAD_OP"` 等）

这解释了 issue trace 输出中只有泛化 op_type 而非 SASS 助记符。

#### 确认方案：在 `trace_warp_inst_t` 中新增 SASS 助记符字段

两种实现选择：

| 方案 | 实现 | 开销 | 适用场景 |
|------|------|------|---------|
| **bool flag** | `bool m_is_imad_wide`，`parse_from_trace_struct()` 中判断设置 | 1 bit/指令 | 仅需区分 IMAD.WIDE |
| **完整字符串** | `std::string m_sass_opcode`，保存原始助记符 | ~40B/指令（堆分配） | 需区分多种 SASS 子类型 |

**推荐：存完整字符串**。理由：
1. Prefetcher 未来可能需要识别更多指令子类型（如 LDG.E vs LDG.E.64、IMAD.MOV.U32 等）
2. 顺带修复 issue trace 的 opcode 显示问题——`opcode_from_inst()` 可改为优先读取此字段
3. 字符串开销在仿真器总内存中占比极小（每条 trace 指令已有多个字段，多一个 string 可忽略）

**实现位置**：`trace_driven.cc` 的 `parse_from_trace_struct()` 函数中，在解析 `OpcodeMap` 之后增加：
```cpp
m_sass_opcode = trace.opcode;  // 保存原始 SASS 助记符
```

同时在 `trace_warp_inst_t`（`trace_driven.h`）中添加：
```cpp
public:
  std::string m_sass_opcode;  // 原始 SASS 助记符，如 "IMAD.WIDE"、"LDG.E.64"
```

---

## P5: fill 路径中 index prefetch 无法识别，pending buffer 匹配需新机制

### 问题描述

设计 DPU 的触发：当 index prefetch fill 从 L1 返回时，查 pending buffer，用返回值计算 data_addr。

当前 `ldst_unit::fill()` 接收所有 `mem_fetch`（demand + prefetch），无区分机制。即使不考虑 P1（数据值问题），还需要：

1. 区分 prefetch fill 和 demand fill：`mem_fetch` 无 `is_prefetch` 标志
2. 进一步区分 index prefetch fill 和 data prefetch fill
3. 按地址匹配 pending buffer 条目（prefetch 用 byte addr 发出，fill 用 block-aligned addr 返回，需对齐）

目前 `mem_fetch` 类没有任何 prefetch 类型字段，`fill()` 也没有 pending buffer 的查找路径。

**相关文件：** `shader.cc::ldst_unit::fill()`（line 3396），`mem_fetch.h`（`mem_fetch` 类定义），`gpu-cache.cc::baseline_cache::fill()`

### 我的思路和解决办法

> 从 prefetcher 发出的 idx ld 需要追踪，所以肯定要给 mem_fetch 对象里加入对应的标志（具体标注需要根据实际的 prefetcher 设计方案确定），等接收到对应信息，就可以发出对应地址的 prefetch 请求

---

## P6: data prefetch 的多 lane 地址生成无法走正常 coalescing 路径

### 问题描述

设计 §3.3.1 说："Prefetch 走正常 coalescing 路径——per-lane 独立计算 `data_addr`，然后经过 SM 现有的 coalescing unit 合并为 cache line 级请求。"

实现的障碍：`warp_inst_t::generate_mem_accesses()` 是针对真实 warp 指令的，
读取的是 `m_per_scalar_thread[k].memreqaddr[0]`（trace 中预录的地址），
prefetcher 生成的"人工请求"没有对应的 `warp_inst_t`，**无法直接走这条路径**。

两种实现选择及其代价：

| 实现方式 | 说明 | 问题 |
|---------|------|------|
| **每 lane 独立 `mem_fetch`** | 每个 active lane 发一个 sector-sized `mem_fetch` | 最坏 32×K 个 `mem_fetch`，MSHR 压力远高于设计预期 |
| **手动模拟 coalescing** | 按 128B cache line 对齐分组，每组发一个 `mem_fetch`，设置 byte_mask/sector_mask | 需要实现额外的 coalescing 逻辑，但结果更接近设计 |

**相关文件：** `abstract_hardware_model.h::warp_inst_t::generate_mem_accesses()`，`shader.cc::ldst_unit::process_memory_access_queue_l1cache()`

### 我的思路和解决办法

> 我希望从 prefetcher 发出的预取请求，和正常从 LSU 中发出的预取没有区别，那应该直接实现一个 coalescer 应该没有大的问题吧？

---

## P7: Pending Buffer 容量被严重低估

### 问题描述

设计 §4.3 估算 Pending Buffer "16–32 条目/SM，覆盖并发 index prefetch 数量"。

实际并发量计算：
- 每 SM 最多 64 warp
- 每 warp 每次外循环迭代，向每个 active index PC 发 1 次 index prefetch
- `small_1sm_cta5 / lrr` 代表窗口中，`index_issue_to_refill_p50` 已经落在 `536-853` cycles，`p90` 落在 `834-2152` cycles；因此 index prefetch 的在途生命周期不能再用固定 `200 cycles` 近似
- BFS 有 ~5 个 index PC，SpMV 有 30+ 个 index PC

**最坏情况（SpMV，30 个 index PC，64 warp 密集执行）：**
`64 warp × 30 PC = 1920` 给出了一个上界级别的触发规模；结合上面的实测在途时间范围，pending buffer 只有 16–32 条目的假设就更缺乏支撑。

即便是 BFS：`64 × 5 = 320` 个潜在触发点也足以说明 32 条目非常紧张；这里应把 `200 cycles` 视为 config knob，而不是 capacity sizing 的实测依据。

**后果：** 大量 index prefetch fill 因找不到 pending buffer 条目而丢失触发机会，DPU 的实际触发率远低于预期。

**相关文件：** `04_prefetcher_design.md` §4.3（Pending Buffer 设计表格）

### 我的思路和解决办法



---

## P8: Kernel launch / Warp EXIT 清表的 hook 位置

### 问题描述

设计 §4.6 要求：

| 事件 | 操作 |
|------|------|
| Kernel launch | 清空 CT/TT + 所有 warp FIFO + Pending Buffer |
| Warp EXIT | 清该 warp 的 FIFO + Pending Buffer 中匹配条目 |

GPGPU-Sim 中存在对应 hook 点（可能），但 trace-driven 模式下的调用时机需确认：

- **Kernel launch hook**：`gpu-sim.cc` 中 `gpgpu_sim::launch()` 或 `shader_core_ctx::init_warps()`
- **Warp EXIT hook**：`shader.cc` 中 warp done 检测路径（warp barrier / warp finish）

未实现此逻辑的风险：跨 kernel 的陈旧 CT/TT 条目导致错误 pattern 激活，或悬挂的 Pending Buffer 条目占用空间。

**相关文件：** `gpu-sim.cc`（kernel launch 路径），`shader.cc`（warp exit/done 处理）

### 我的思路和解决办法

> 之前我考虑的不对，不能按照 warp exit 去清，因为 预取器最后训练的结果是基于 PC 的，所以应该是 kernel 执行完再切换，CTA 执行完都不用切换，因为下一个 CTA 还是这套 PC，可以服用，所以应该是等到 kernel 切换时才清空（这点可以作为核心的 insight 说明 GPU 做 IMA 预取相比 CPU 优势的点）

---
