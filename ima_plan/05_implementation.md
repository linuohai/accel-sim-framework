# 05 — GRASP Prefetcher 实现文档

> 状态：**Phase A/B 完成**（核心组件已实现，编译通过，smoke test 通过）
>
> 前置：`04_prefetcher_design.md`（设计方案）、`01_ima_characterization.md`（IMA 特征化）
>
> 代码位置：`gpu-simulator/gpgpu-sim/src/gpgpu-sim/grasp_*.{h,cc}`

---

## 0. 设计原则

本实现采用 **防御式编程** 风格，贯穿所有组件：

| 原则 | 体现 |
|------|------|
| **Fail-fast** | 所有关键假设用 `assert()` 守护（PRB bounds、CT invariant、stride!=0） |
| **前置/后置条件** | 函数入口检查参数有效性，出口断言结果一致性 |
| **诊断日志** | `m_cfg.debug` 开关控制详细日志（chain detection、stride convergence、PRB lifecycle） |
| **状态隔离** | kernel launch 时全量清空所有组件，`on_kernel_launch()` 后断言 occupancy == 0 |
| **容量监测** | 每个有限容量组件（FIFO、CT、PRB、prefetch queue）跟踪 peak occupancy 和 stall 计数 |
| **约束编号** | 关键约束在代码注释中标注 `C1`–`C8`，便于代码审查与回溯 |

---

## 1. 架构总览

GRASP (GPU Register-chain Aware Sector Prefetcher) 是一个 per-SM 的硬件 IMA prefetcher。每个 SM 拥有一个 `grasp_prefetcher_t` 实例，统一管理以下子组件：

```
                          ┌─────────────────────────────────────────────┐
  issue_warp()            │              grasp_prefetcher_t              │
  ────────────────►       │                                             │
  on_instruction_issue()  │  CD ──chain──► CT ◄──stride──┐              │
                          │  (FIFO)      (32 entries)    │              │
                          │       TT                     │              │
                          │      (8 entries)             │              │
  L1_latency_queue_cycle()│                              │              │
  ────────────────►       │  on_demand_load() ──► CT stride check       │
  on_demand_load()        │        │                                    │
                          │        ▼                                    │
                          │  prefetch_queue ──► inject_prefetch()        │
                          │                       │                     │
                          │              INDEX_PF │ DATA_PF             │
                          │                ▼      ▼                     │
                          │              L1D access                     │
                          │                │                            │
                          │          ┌─────┼─────┐                      │
                          │        HIT   MISS  RFAIL                    │
                          │          │     │     │                      │
                          │     release  wait  discard                  │
                          │     PRB     fill                            │
                          │     targets   │                             │
                          │          │    ▼                             │
                          │          │  on_fill() → release PRB targets │
                          │          │    │                             │
                          │          ▼    ▼                             │
                          │  DATA_PF enqueue (coalesced by cache line)  │
                          │        │                                    │
                          │        ▼                                    │
                          │  inject_prefetch() → L1D (fire-and-forget)  │
                          │                                             │
                          │  PRB (1024 entries, Phase 1 large capacity) │
                          └─────────────────────────────────────────────┘
```

### 关键设计决策

1. **CT stride 即 confidence**：不使用独立的 IST/IPT 置信度机制。CD 识别 IMA 链后，CT 直接学习 stride；`stride_valid` 标志（需连续 2 次 delta 匹配）等价于"置信度达标"。这避免了退化为无 CD 上下文的裸 stride prefetcher。

2. **无 warp 接替**：tracked warp 退出后，训练永久冻结。理由：如果 tracked warp 在执行期间未能让某些 CT entry 学到 stride，说明那些 PC 的 IMA 访问是低频/一次性的，其他 warp 也不会有新信息。

3. **INDEX_PF HIT 立即释放**：当 index prefetch 命中 L1D（数据已在缓存中），立即从 PRB 释放 targets 并生成 DATA_PF，无需等待 MSHR/fill。

4. **Data PF coalescing**：PRB release 时，多个 candidate 指向同一 128B cache line 的 DATA_PF 合并为单次请求。INDEX_PF（有 successor）不合并——每个需独立做 pair table lookup。

5. **Data PF fire-and-forget**：DATA_PF 发往 L1D 后不跟踪结果。RESERVATION_FAIL 时丢弃（L1 MSHR 拥塞天然节流）。

---

## 2. 文件结构

### 2.1 新增文件（6 个）

| 文件 | 职责 | 行数 |
|------|------|------|
| `grasp_prefetcher.h` | 顶层头文件：`grasp_config_t`, `grasp_prefetch_request_t`, `grasp_prb_entry_t/t`, `grasp_ist_t`, `grasp_stats_t`, `grasp_prefetcher_t` | ~300 |
| `grasp_prefetcher.cc` | 顶层实现 + PRB + IST（保留但不用于主路径） | ~600 |
| `grasp_chain_detector.h` | CD：FIFO + tracked warp + freeze 状态机 | ~105 |
| `grasp_chain_detector.cc` | CD 实现：LDG→IMAD.WIDE→LDG 检测、Read/Write Invalidation | ~235 |
| `grasp_tables.h` | CT (`ct_entry_t`) + TT (`tt_entry_t`) 声明 | ~120 |
| `grasp_tables.cc` | CT/TT 的查找/插入/淘汰/stride 学习 | ~220 |

### 2.2 修改文件（7 个）

| 文件 | 变更内容 |
|------|---------|
| `shader.h` | `ldst_unit` 新增 `grasp_prefetcher_t *m_grasp` + 访问器；`shader_core_config` 新增 10 个 GRASP 配置字段 |
| `shader.cc` | 8 个集成 Hook（§4 详述）|
| `gpu-sim.cc` | 12 个 GRASP 配置选项注册 |
| `trace_driven.h` | `trace_warp_inst_t` 新增 `m_sass_opcode` + `get_sass_opcode()` override |
| `trace_driven.cc` | `parse_from_trace_struct()` 保存 `m_sass_opcode = trace.opcode` |
| `abstract_hardware_model.h` | `warp_inst_t` 新增 virtual `get_sass_opcode()` 基类方法 |
| `CMakeLists.txt` | 新增 3 个 `.cc` 源文件 |

### 2.3 复用文件（不修改）

| 文件 | 复用内容 |
|------|---------|
| `mem_fetch.h` | `ima_prefetch_kind_t` (INDEX/DATA) + `m_ima_prb_entry_id` — GRASP 直接使用 |
| `trace_driven.h/cc` | `ima_pair_chain_table_t` — pair table 建表 + lookup 逻辑不变 |
| `shader.h` | `ima_prefetch_candidate_t` — 预取候选结构不变 |

---

## 3. 组件详细设计

### 3.1 CD (Chain Detector)

**职责**：在 issue 阶段检测 `LDG → IMAD.WIDE → LDG` 寄存器依赖链。

**核心结构**：Circular buffer FIFO，每个 entry 记录 `{valid, dst_reg, type, pc, index_pc, scale, base}`。

**检测逻辑**：
1. **LDG 指令**：检查地址寄存器是否由 FIFO 中的 `IMA_ADDR_COMPUTE` entry 生产 → 若是，检测到完整链 `(index_PC, data_PC)`
2. **IMAD.WIDE 指令**：检查源寄存器是否由 FIFO 中的 `LOAD_RESULT` entry 生产 → 若是，push `IMA_ADDR_COMPUTE` entry
3. **其他指令**：Read Detection（源寄存器消费了 FIFO entry → 失效）+ Write Invalidation（目标寄存器覆盖 FIFO entry → 失效）

**Tracked Warp 机制**：
- 每个 SM 仅追踪 **一个 warp**（first-LDG 自动选择）
- 只有 tracked warp 的指令进入 FIFO
- **Tracked warp 退出 → 训练永久冻结**（无 warp 接替，`m_training_frozen = true`）
- 下一次 kernel launch 时 `reset()` 解冻

**容量**：默认 20 entries（可配置 `-grasp_cd_fifo_depth`），SpMV ×16 的 17 条指令链需 17+。监测 `fifo_peak_occupancy` 和 `fifo_drop_count` 确认是否需要加大。

**约束**：
- C7: `m_training_frozen == true` 时 FIFO 不再写入
- FIFO 满时覆盖最旧 entry（记 `fifo_drop_count`）

### 3.2 CT (Chain Table) + TT (Target Table)

**CT 职责**：存储 CD 检测到的 IMA 链信息 + stride 学习结果。

**CT Entry 结构**（`ct_entry_t`）：
```
index_pc      — key：索引 load 的 PC
data_pc       — 数据 load 的 PC
tt_idx[3]     — 指向 TT 的索引（K=3，one-to-many target）
num_targets   — 有效 target 数（0..3）
last_addr     — 最近一次 demand load 地址（用于 stride 计算）
iter_stride   — 迭代间 stride（字节）
stride_valid  — stride 已学到（需 2 次 delta 匹配确认）
last_access_time — LRU 时间戳
```

**Stride 学习**（`update_stride()`）：
- 仅 tracked warp 贡献 stride 训练，且同一 warp 必须使用同一 lane 保证地址序列一致
- 第 1 次访问：记录 `last_addr`（无 delta）
- 第 2 次访问：计算 `delta = current_addr - last_addr`；若 `delta != 0` 且 `stride_valid == false`，直接设 `iter_stride = delta, stride_valid = true`（单次收敛，无需确认）
- 后续访问：若 `delta != iter_stride`，覆盖 `iter_stride = delta`，但 **不重置 `stride_valid`**
- `delta == 0` 被跳过（不影响 stride 状态，但 `last_addr` 仍更新）
- 同 cycle 的重复 mem_fetch 被去重（`last_cycle == cycle → skip`）

**CT 淘汰策略**（`find_victim()`）：
1. Invalid entry（优先）
2. `stride_valid == false` 的 LRU entry（低价值淘汰）
3. 全部 `stride_valid` 时 LRU 淘汰

**容量**：默认 32 entries（`-grasp_ct_size`），BFS/SpMV 30+ IMA PC 的 sizing 瓶颈。

**TT**：存储 `(base_addr, scale)` 占位符（trace-driven 模式下由 pair table 替代地址计算）。默认 8 entries。

**约束**：
- C5: `num_targets ≤ 3`（K=3 硬件限制）
- C6: `stride_valid == true` 时 `iter_stride != 0`

### 3.3 PRB (Prefetch Request Buffer)

**职责**：暂存 INDEX_PF 发出后、fill 返回前的预取上下文（pair table lookup 结果、warp_id）。

**PRB Entry 结构**（`grasp_prb_entry_t`）：
```
valid             — 是否有效
warp_id           — 发起 warp
candidates[]      — pair table lookup 结果（data_addr + successor_chain_ids）
remaining_sectors — sector 跟踪
alloc_cycle       — 分配时间（用于 lifetime 统计）
```

**生命周期**：
1. `allocate()` — INDEX_PF 发射时分配，保存 pair table lookup 结果
2. `free_entry()` — INDEX_PF 结束时释放（HIT/MISS-fill/MSHR/RFAIL）

**INDEX_PF 结果处理**（关键决策）：

| L1 Access Result | PRB 操作 | 说明 |
|-----------------|----------|------|
| **HIT** | 立即 release targets → free PRB | 数据已在 L1D，直接转发 DATA_PF |
| **MISS** | 等待 fill | fill 回调时 release targets → free PRB |
| **MSHR_HIT / HIT_RESERVED** | free PRB（不等待） | 已有 in-flight 请求，保守放弃 |
| **RESERVATION_FAIL** | free PRB | MSHR 满，丢弃 |

**容量**：Phase 1 默认 1024 entries（`-grasp_prb_capacity`），大容量探测 peak occupancy。

**约束**：
- C2: `free_entry()` 前 entry 必须 valid
- C3: `prb_entry_id < capacity`（bounds check）

### 3.4 Prefetch Queue + Coalescing

**Prefetch Queue**：`std::deque<grasp_prefetch_request_t>`，存储待发射的预取请求。

**请求类型判定**：
- `seed_chain_ids` 非空 → INDEX_PF（需 pair table lookup + PRB 分配）
- `seed_chain_ids` 为空 → DATA_PF（fire-and-forget）

**Coalescing**（PRB release 时）：
- PRB targets 释放时，多个 candidate 的 `data_addr` 可能落在同一 128B cache line
- **DATA_PF（terminal，无 successor）**：按 cache line 地址去重，只入队一次
- **INDEX_PF（有 successor）**：不去重——每个需要独立做下一级 pair table lookup
- L1D 的 MSHR merge 提供第二层去重保障

**时序约束**：
- T2: data PF 的 `ready_cycle = fill_cycle + 1`（模拟 1 cycle ACU 计算延迟）
- T5: prefetch 不阻塞 demand load（使用独立注入路径）

### 3.5 IST (Iteration Stride Tracker) — 保留但不在主路径使用

IST 是从 `ima_prefetcher_t` 迁移的独立 stride tracker（IPT 表 + 2-bit saturating confidence）。

**当前状态**：类实现已保留（编译、可选初始化），但 **不在 `on_demand_load()` 主路径中调用**。原因：CT 的 stride 学习已内置收敛判定（单次非零 delta 即 `stride_valid = true`），且 CT 通过 CD 链检测限定了哪些 PC 是 IMA load——比 IST 的盲目 stride tracking 更精准。IST 的独立运行会退化为无 CD 上下文的裸 stride prefetcher。

可选：后续若需对比"裸 stride vs GRASP"，可通过配置开关重新启用 IST 路径。

---

## 4. 集成 Hook（8 个）

### Hook 1: CD 训练 — `issue_warp()`

**位置**: `shader.cc` → `shader_core_ctx::issue_warp()` → `func_exec_inst()` 之后

```cpp
if (m_ldst_unit->grasp_enabled()) {
  const warp_inst_t &inst = **pipe_reg;
  const std::string &sass_opcode = next_inst->get_sass_opcode();
  m_ldst_unit->grasp()->on_instruction_issue(
      warp_id, inst, sass_opcode,
      m_gpu->gpu_tot_sim_cycle + m_gpu->gpu_sim_cycle);
}
```

通过 virtual dispatch (`get_sass_opcode()`) 获取 SASS 助记符，避免 `trace_driven.h` 的循环 include。

### Hook 2: Demand Load — `L1_latency_queue_cycle()`

**位置**: `shader.cc` → `ldst_unit::L1_latency_queue_cycle()` → global read 路径

```cpp
if (m_grasp && m_grasp->enabled()) {
  shd_warp_t *warp = m_core->get_warp_ptr(mf_next->get_wid());
  m_grasp->on_demand_load(mf_next->get_wid(), mf_next->get_pc(),
                          mf_next->get_addr(), cycle, warp);
}
```

GRASP hook 优先于 legacy IMA hook 执行。

### Hook 3: Prefetch 发射 — `ldst_unit::cycle()`

**位置**: `shader.cc` → `ldst_unit::cycle()` → 现有 `inject_ima_prefetches` 位置

每 cycle 从 prefetch queue 取 ready 请求，构造 `mem_fetch`，发往 L1D，处理返回结果。

### Hook 4: Fill 回调 — `ldst_unit::cycle()`

**位置**: `shader.cc` → `ldst_unit::cycle()` → response_fifo 处理后

```cpp
if (m_grasp && m_grasp->enabled()) {
  m_grasp->on_fill(mf, gpu_sim_cycle + gpu_tot_sim_cycle);
}
```

INDEX_PF fill → release PRB targets → 入队 DATA_PF（coalesced）。

### Hook 5: 构造 — `ldst_unit::init()`

GRASP 和 legacy IMA prefetcher 共存：通过 `-grasp_enable 1` 和 `-gpgpu_ima_prefetch_enable 1` 独立控制。

### Hook 6: Kernel Launch — `init_warps()`

```cpp
if (ctaid == 0 && m_ldst_unit->grasp_enabled()) {
  m_ldst_unit->grasp()->on_kernel_launch();
}
```

C8: 清空所有组件状态（CD/CT/TT/PRB/queue），解冻训练。

### Hook 7: Warp Exit — `set_done_exit()`

```cpp
if (m_ldst_unit->grasp_enabled()) {
  m_ldst_unit->grasp()->on_warp_exit(warp_id);
}
```

Tracked warp exit → CD 永久冻结训练（无 warp 接替）。

### Hook 8: SASS Opcode 保存 — `trace_driven.cc`

```cpp
m_sass_opcode = trace.opcode;  // 保存完整 SASS 助记符
```

在 `parse_from_trace_struct()` 中保存，供 CD 识别 `IMAD.WIDE`。

---

## 5. 事件流

### 5.1 训练流 (CD → CT/TT 填充)

```
[1] issue_warp() 调用 on_instruction_issue()
    → 若 training_frozen → 跳过
    → 若 tracked_warp_id == UNSET 且指令是 LDG → 选为 tracked warp
    → 非 tracked warp → 跳过

[2] CD 处理指令：
    [2a] LDG: 查 FIFO 中是否有 IMA_ADDR_COMPUTE producer
         → 有 → 完整链 (index_PC, data_PC) → CT/TT 插入
         → 无 → push LOAD_RESULT entry

    [2b] IMAD.WIDE: 查 FIFO 中是否有 LOAD_RESULT producer
         → 有 → push IMA_ADDR_COMPUTE entry

    [2c] 其他: Read Detection + Write Invalidation

[3] Stride Learning (在 on_demand_load 中):
    → demand load 的 PC 在 CT 中 → update_stride()
    → 仅 tracked warp 贡献 delta
    → 第 3 次同 PC 同 stride → stride_valid = true

[4] 训练冻结:
    → tracked warp EXIT → m_training_frozen = true
    → CD 停止所有 FIFO 操作（C7）
    → 下一次 kernel launch 解冻
```

### 5.2 Index Prefetch 流

```
[1] demand load → on_demand_load(PC, addr)
    → CT.find(PC) → 若不在 CT → 不是 IMA load，跳过
    → CT.update_stride() → stride 学习

[2] 若 stride_valid:
    → 生成 addr + n * iter_stride (n = 1..distance)
    → 获取 seed_chain_ids → 入队 prefetch_queue

[3] inject_prefetch() 取 ready 请求:
    → seed_chain_ids 非空 → INDEX_PF:
      → pair table lookup → candidates[]
      → PRB allocate → mem_fetch → L1D access

[4] on_l1_access_result():
    → HIT → 立即 release PRB targets → free PRB
    → MISS → cache took ownership → 等 fill
    → MSHR_HIT → free PRB（保守放弃）
    → RFAIL → free PRB（MSHR 满）
```

### 5.3 Data Prefetch 流

```
[1] INDEX_PF fill 返回 → on_fill()
    → release_prb_targets():
      → 遍历 candidates
      → DATA_PF (无 successor): 按 128B cache line 去重
      → INDEX_PF (有 successor): 不去重，独立入队
      → ready_cycle = fill_cycle + 1 (T2: ACU 延迟)
    → free PRB entry

[2] inject_prefetch() 取 DATA_PF:
    → seed_chain_ids 为空 → 直接构造 mem_fetch → L1D access
    → fire-and-forget: RFAIL 时丢弃，不重试
```

### 5.4 INDEX_PF HIT 快速路径

```
当 INDEX_PF 命中 L1D (on_l1_access_result, HIT):
  → 数据已在缓存，无需等 MSHR/fill
  → 立即 release_prb_targets() → DATA_PF 入队
  → free PRB entry
  → delete mem_fetch (不需进 miss queue)

这是最理想的情况：index 数据局部性好时，INDEX_PF 零延迟转 DATA_PF。
```

---

## 6. 约束清单

### 6.1 正确性约束

| ID | 约束 | 断言位置 | 说明 |
|----|------|---------|------|
| C1 | pair table build: `dup_conflict == 0` | `build_ima_pair_tables()` | 冲突 → read-only index 假设失效 |
| C2 | PRB free 前 entry 必须 valid | `free_entry()` | 防止重复释放 |
| C3 | `prb_entry_id < capacity` | `on_fill()`, `get()` | 防止越界 |
| C4 | INDEX_PF 的 `seed_chain_ids` 非空 | `inject_prefetch()` | 空 seed → DATA_PF |
| C5 | CT `num_targets ≤ 3` | `append_target()` | K=3 硬件限制 |
| C6 | `stride_valid` 时 `iter_stride != 0` | `update_stride()` 后 | stride=0 → 训练逻辑错误 |
| C7 | frozen 后 FIFO 不写入 | `on_instruction_issue()` 入口 | 冻结后 CD 休眠 |
| C8 | kernel launch 后全部 invalid | `on_kernel_launch()` | 防止跨 kernel 残留 |

### 6.2 时序约束

| ID | 约束 | 说明 |
|----|------|------|
| T1 | stride 学习需 tracked warp 同一 PC ≥ 3 次 | 第 1 次记录，第 2 次算 delta，第 3 次确认 |
| T2 | DATA_PF `ready_cycle = fill_cycle + 1` | 模拟 ACU 1 cycle 计算延迟 |
| T3 | INDEX_PF HIT → 立即 release | 不走 MSHR/fill 路径 |
| T4 | DATA_PF RFAIL → 丢弃 | fire-and-forget，隐式节流 |
| T5 | prefetch 不阻塞 demand load | 使用独立注入路径 |
| T6 | frozen 后 CD 休眠 | 省去 FIFO 写入/查找开销 |

---

## 7. 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-grasp_enable` | 0 | 总开关 |
| `-grasp_debug` | 0 | 诊断日志开关 |
| `-grasp_cd_fifo_depth` | 20 | CD FIFO 深度（SpMV ×16 需 17+） |
| `-grasp_ct_size` | 32 | CT 条目数（SpMV 30+ IMA PC） |
| `-grasp_tt_size` | 8 | TT 条目数 |
| `-grasp_ist_ipt_size` | 64 | IST IPT 表大小（保留，主路径不用） |
| `-grasp_ist_distance` | 1 | prefetch 步长（lookahead distance） |
| `-grasp_ist_confidence` | 2 | IST confidence 阈值（保留，主路径不用） |
| `-grasp_prb_capacity` | 1024 | PRB 容量（Phase 1 大容量探测） |
| `-grasp_tc_mshr_threshold` | 80 | TC MSHR 占用率阈值（%），超过则抑制 DATA_PF |

与 legacy IMA prefetcher 独立控制：`-grasp_enable 1` 和 `-gpgpu_ima_prefetch_enable 1` 可同时启用也可独立启用。

---

## 8. 监测统计

`print_stats()` 输出以下指标：

### 8.1 全局

| 指标 | 说明 |
|------|------|
| `kernel_launches` | kernel 切换次数 |
| `warp_exits` | tracked warp 退出次数 |
| `queue_peak_depth` | prefetch queue 最大深度 |

### 8.2 CD

| 指标 | 说明 | 关注阈值 |
|------|------|---------|
| `chains_detected` | 检测到的 IMA 链数 | 应 > 0 |
| `fifo_peak_occupancy` | FIFO 最大占用 | 接近 depth → 需增大 |
| `fifo_drop_count` | FIFO 满溢丢弃数 | 应为 0 |
| `fifo_read_invalidations` | Read Detection 失效数 | 正常行为 |
| `fifo_write_invalidations` | Write Invalidation 数 | 正常行为 |
| `frozen` | 是否已冻结 | tracked warp 退出后应为 yes |

### 8.3 CT

| 指标 | 说明 | 关注阈值 |
|------|------|---------|
| `peak_occupancy` | 最大占用 | 接近 ct_size → 需增大 |
| `eviction_count` | 淘汰次数 | 应为 0（SpMV 30 < 32） |
| `evict_stride_valid_count` | 淘汰已学到 stride 的 entry | 应为 0（严重损失） |
| `all_stride_valid` | 所有 entry 是否 stride_valid | yes → 训练完成 |

### 8.4 PRB

| 指标 | 说明 | 关注阈值 |
|------|------|---------|
| `peak_occupancy` | 最大占用 | Phase 1 应远小于 1024 |
| `total_allocations` | 总分配数 | |
| `full_stall_cycles` | PRB 满导致的 stall cycle | 应为 0 |

### 8.5 Prefetch

| 指标 | 说明 |
|------|------|
| `index_pf_issued` / `hit` / `miss` / `mshr` / `rfail` | INDEX_PF 各结果计数 |
| `data_pf_issued` / `hit` / `miss` / `mshr` / `rfail` | DATA_PF 各结果计数 |
| `pair_table_lookup_hit` / `miss` | Pair table 查询结果 |
| `throttle_suppressed` | TC 抑制的 DATA_PF 数 |

---

## 9. 实验进度与待完成项

> **详细实验记录见**: `05_implementation/experiment_progress.md`
>
> 该文件记录每次实验的配置、结果、根因分析和下一步行动，作为跨 Agent 窗口的交接文档。

### 首轮实验结论 (2026-03-24)

GRASP 管线功能正确，但首轮 IPC 无提升。三个根因：

1. **distance=1 太小**：预取和 demand load 竞速同一地址（SpMV: 37,829 次 PF fetch 仅产生 643 次 demand HIT）→ 需增大到 3-5
2. **per-kernel reset**：BFS/SSSP 多 kernel 迭代，每次 launch 清空训练 → 需跨 kernel 持久化 CT stride
3. **无 Throttle Control**：MSHR 已饱和，PF MISS 进一步挤压 demand → 需实现 `TODO(human)`

### Phase C: 全组件监测 + 容量标定

- [x] 跑全部目标 workload (spmv/bfs/sssp/bc × ima_high)
- [x] 收集 peak occupancy 数据
- [x] 验证 CD/CT/PRB 功能正确
- [ ] 基于 peak occupancy 数据确定 Phase 2 的正式容量参数

### Phase D: 性能优化 + 评估

- [ ] **增大 `ist_distance` 到 3-5**（高优先级，预期直接提升 demand HIT 覆盖率）
- [ ] **CT stride 跨 kernel 持久化**（高优先级，使 BFS/SSSP 可用）
- [ ] **实现 Throttle Control**（中优先级，减少 MSHR 拥塞）
- [ ] 正式性能评估：baseline vs GRASP vs ideal L1D
- [ ] 验证 GRASP IPC 在 baseline 和 ideal L1D 之间

### 验证方法

| 类型 | 方法 | 状态 |
|------|------|:----:|
| 单元 | CD: chains_detected > 0 且 fifo_peak 合理 | ✓ |
| 单元 | CT: eviction_count == 0（SpMV 7 < 32 entry） | ✓ |
| 单元 | PRB: full_stall_cycles == 0（Phase 1） | ✓ |
| 集成 | pair table: lookup_hit > 0 | ✓ |
| 集成 | INDEX_PF → fill → DATA_PF 管线完整运行 | ✓ |
| 性能 | demand HIT 覆盖率（目标 > 30%） | ✗ (1.7%) |
| 性能 | IPC speedup（目标 > 5%） | ✗ (-0.47%) |
