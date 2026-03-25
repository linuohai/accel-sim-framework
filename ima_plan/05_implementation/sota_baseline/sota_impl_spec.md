# GRASP Evaluation Baseline 复现规格文档

> 状态：**待实现**
>
> 目的：为 GRASP 论文 evaluation 章节提供完整 baseline 实现规格，供实现 agent 独立执行
>
> 前置知识：`05_implementation.md`（GRASP 本身的实现与 hook 位置）、`02_related_work.md`（论文细节）

---

## ⚠️ 实现原则（最高优先级）

**忠实复现，不额外调优。**

1. **严格按照论文原文描述的机制实现**，不遗漏核心组件，保证实现的正确性和可复现性。
2. **使用论文给出的默认参数**（table size、confidence threshold、training iterations 等）。如果论文给出了参数范围，取其默认值或中间值，不做针对本项目 workload 的专门调优。
3. **不添加论文未描述的增强**。例如：论文没提到的自适应节流、额外的 filter 机制、或针对特定 workload 的 pattern heuristic，一律不加。
4. **不投入精力做 baseline-specific 的性能调优**。实现通过 smoke test、stats 输出正常、开关隔离验证通过即视为完成。不需要反复调参数让 baseline 跑出最优结果。
5. **简化实现优先**。在论文描述存在模糊地带时（如 Snake 的 decoupled storage 细节、Spare Register 的空闲寄存器精确管理），优先选择文档中标注的"简化方案"，不追求完美还原论文每一个实现细节。

**理由**：这些 baseline 的价值在于提供对比参照点，证明 stride-based 方案在 IMA 上的局限性。实现精力应集中在 GRASP 本身，而非为竞争方案做深度优化。

---

## 0. 模拟器环境与约束

### 0.1 代码库

| 项目 | 路径 |
|------|------|
| 模拟器根目录 | `/workspace/prefetch/gpu-simulator/` |
| GPGPU-Sim 核心代码 | `gpu-simulator/gpgpu-sim/src/gpgpu-sim/` |
| GRASP 实现（参考） | `gpu-simulator/gpgpu-sim/src/gpgpu-sim/grasp_*.{h,cc}` |
| 配置注册 | `gpu-simulator/gpgpu-sim/src/gpgpu-sim/gpu-sim.cc` |
| SM / ldst_unit | `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.{h,cc}` |
| L1D cache | `gpu-simulator/gpgpu-sim/src/gpgpu-sim/gpu-cache.{h,cc}` |
| mem_fetch 定义 | `gpu-simulator/gpgpu-sim/src/gpgpu-sim/mem_fetch.{h,cc}` |
| trace 解析 | `gpu-simulator/trace-driven/trace_driven.{h,cc}` |
| 默认 GPU 配置 | `gpu-simulator/gpgpu-sim/configs/tested-cfgs/SM80_A100/gpgpusim.config` |
| CMake 构建 | `gpu-simulator/CMakeLists.txt` |

### 0.2 构建方式

```bash
source ./gpu-simulator/setup_environment.sh
make -j -C ./gpu-simulator/
# 产物: ./gpu-simulator/bin/release/accel-sim.out
```

### 0.3 实验入口

```bash
# 运行单个 workload
./traceL1 <trace_key> [log_name]

# 常用 trace_key（IMA workload）
bfs_ima_high  sssp_ima_high  bc_ima_high  spmv_ima_high  cc_ima_high
```

### 0.4 GRASP 已有 Hook 位置（baseline 可复用）

GRASP 在 `shader.cc` 中有 8 个集成 hook（见 `05_implementation.md` §4）。Baseline 实现应尽量挂载在**相同或相邻位置**，以保证时序公平：

| Hook 位置 | 函数 | 时机 | Baseline 用途 |
|-----------|------|------|--------------|
| **H1** | `shader_core_ctx::issue_warp()` | 指令 issue 后 | INTRA/INTER: 记录 PC + addr；Snake: chain 训练；Spare Register: load-pair 检测 |
| **H2** | `ldst_unit::L1_latency_queue_cycle()` | demand load 送入 L1D 时 | 所有 baseline: stride 查表 + 发 prefetch |
| **H3** | `ldst_unit::cycle()` | 每 cycle 执行 | 所有 baseline: inject prefetch requests |
| **H4** | `ldst_unit::cycle()` response_fifo 后 | L1D fill 返回时 | Spare Register: value tag 更新；Snake: decoupled buffer fill |
| **H5** | `ldst_unit::init()` | 构造时 | 所有 baseline: 创建 prefetcher 实例 |
| **H6** | `init_warps()` ctaid==0 | kernel launch | 所有 baseline: 清表 |
| **H7** | `set_done_exit()` | warp 退出 | Spare Register / Snake: tracked warp 状态 |

### 0.5 开关设计原则

每个 baseline 用独立的 config flag 控制，互不影响，互斥检查可选：

```
-baseline_intra_enable 1
-baseline_inter_enable 1
-baseline_snake_enable 1
-baseline_spare_reg_enable 1
-grasp_enable 1
```

同一时刻只应启用一个 prefetcher（或 no-prefetch），以保证实验对比公平。

### 0.6 输出与评估指标

所有 baseline 应在仿真结束时 `print_stats()` 输出以下指标：

| 指标 | 说明 |
|------|------|
| `prefetch_issued` | 发射的 prefetch 请求总数 |
| `prefetch_hit` | L1D HIT 的 prefetch 数（数据已在） |
| `prefetch_useful` | 后续被 demand load 使用的 prefetch 数 |
| `prefetch_useless` | 未被使用就被 evict 的 prefetch 数 |
| `prefetch_rfail` | RESERVATION_FAIL 被丢弃的数 |
| `coverage` | `prefetch_useful / total_demand_miss` |
| `accuracy` | `prefetch_useful / prefetch_issued` |

这些指标可以通过在 `gpu-cache.cc` 中标记 prefetch 请求的 `mem_fetch` 来跟踪（参考 GRASP 的 `grasp_stats_t`）。

### 0.7 工作区隔离与交接方式

本实现阶段必须使用 `git worktree` 做隔离，不要在当前脏工作区里直接混写多个 baseline。

1. **当前工作区保留不动**：`/workspace/prefetch` 继续作为主仓库元数据与参考区，允许存在未提交修改。
2. **一个 baseline 一个 worktree**：每个实现分支单独放到独立目录，避免编译产物、日志和代码修改互相污染。
3. **实验结果单独落盘**：所有运行日志和对比结果统一放到 `/workspace/prefetch/runs/<baseline_name>/`。
4. **后续 agent 直接接手**：新 agent 只需要读取本文件和对应 worktree 中的代码，不需要回到当前对话上下文。

推荐的目录与命令如下：

```bash
cd /workspace/prefetch
git worktree add /workspace/prefetch/worktrees/sota_stride -b exp/sota_stride
git worktree add /workspace/prefetch/worktrees/sota_snake -b exp/sota_snake
git worktree add /workspace/prefetch/worktrees/sota_spare_reg -b exp/sota_spare_reg

mkdir -p /workspace/prefetch/runs/sota_stride
mkdir -p /workspace/prefetch/runs/sota_snake
mkdir -p /workspace/prefetch/runs/sota_spare_reg
```

执行约束：

- **先做 `INTRA/INTER`**，因为它最容易把 hook、配置、stats 和 smoke test 跑通。
- **再做 `Snake`**，复用前一阶段已经验证过的配置与统计框架。
- **最后做 `Spare Register`**，因为它对 trace-driven 模式依赖最大，排错成本最高。
- **不要同时启用多个 baseline**，同一 binary 里只允许一个 prefetcher 生效，保证对比公平。

---

## 1. Baseline 总览

| # | 名称 | 论文 | 类型 | 实现优先级 | 文件命名建议 |
|---|------|------|------|-----------|-------------|
| 0 | No-prefetch | — | — | 已有 | — |
| 1 | INTRA | Snake §III-A / CAPS §III | Intra-warp stride | P0（最先） | `baseline_stride.{h,cc}` |
| 2 | INTER | Snake §III-A / MT-Prefetch | Inter-warp stride | P0（与 INTRA 合并） | 同上（共用类，配置区分） |
| 3 | Snake | MICRO 2023 | Stride chain | P1 | `baseline_snake.{h,cc}` |
| 4 | Spare Register | HPCA 2014 | IMA load-pair | P2 | `baseline_spare_reg.{h,cc}` |
| 5 | Ideal L1D | 本项目 | — | 已有 | `-gpgpu_perfect_l1d 1` |

**INTRA 和 INTER 建议合并为一个类 `baseline_stride_prefetcher_t`**，通过 mode 参数切换行为。两者的数据结构和 hook 点完全相同，只是 stride 的计算维度不同（intra = 同 warp 跨时间，inter = 同 PC 跨 warp）。

---

## 2. Baseline 1 & 2: INTRA / INTER Stride Prefetcher

### 2.1 来源定义

- **INTRA**：Snake (MICRO'23) §III-A 定义的 intra-warp stride。同一 warp、同一 PC 的相邻两次 issue 之间计算地址差（stride）。
- **INTER**：Snake (MICRO'23) §III-A 定义的 inter-warp stride。同一 PC，不同 warp 之间计算地址差。

### 2.2 数据结构

```cpp
struct stride_entry_t {
    bool valid;
    // INTRA mode key:
    unsigned warp_id;   // 仅 INTRA 使用
    address_type pc;
    // 共用字段:
    new_addr_type last_addr;    // 最近一次地址（coalesced 后的 per-warp base addr）
    int64_t stride;             // 当前 stride
    unsigned confidence;        // 0..2, 达到 2 则 prefetch
    unsigned last_warp_id;      // 仅 INTER 使用：上一次访问的 warp_id
    unsigned long long last_access_cycle;  // LRU
};

class baseline_stride_prefetcher_t {
    enum mode_t { INTRA_WARP, INTER_WARP };
    mode_t m_mode;
    std::vector<stride_entry_t> m_table;  // set-associative
    unsigned m_table_size;       // 默认 64
    unsigned m_assoc;            // 默认 4
    unsigned m_conf_threshold;   // 默认 2
    unsigned m_prefetch_degree;  // 默认 1
    // stats
    unsigned m_stat_issued;
    unsigned m_stat_useful;
    // ...
};
```

### 2.3 核心算法

#### INTRA 模式

```
on_demand_load(warp_id, pc, addr, cycle):
  key = hash(warp_id, pc)
  entry = table.lookup(key)
  if entry.valid AND entry.warp_id == warp_id AND entry.pc == pc:
    delta = addr - entry.last_addr
    if delta == entry.stride AND delta != 0:
      entry.confidence = min(entry.confidence + 1, 2)
    else:
      entry.stride = delta
      entry.confidence = 1
    entry.last_addr = addr

    if entry.confidence >= conf_threshold:
      for d in 1..prefetch_degree:
        pf_addr = addr + d * entry.stride
        enqueue_prefetch(pf_addr)
  else:
    // 新建或替换
    entry = {valid=true, warp_id, pc, last_addr=addr, stride=0, confidence=0}
    table.insert_or_replace(key, entry)
```

#### INTER 模式

```
on_demand_load(warp_id, pc, addr, cycle):
  key = hash(pc)   // 注意：不含 warp_id
  entry = table.lookup(key)
  if entry.valid AND entry.pc == pc:
    if entry.last_warp_id != warp_id:  // 必须是不同 warp
      delta = addr - entry.last_addr
      if delta == entry.stride AND delta != 0:
        entry.confidence = min(entry.confidence + 1, 2)
      else:
        entry.stride = delta
        entry.confidence = 1
    entry.last_addr = addr
    entry.last_warp_id = warp_id

    if entry.confidence >= conf_threshold:
      for d in 1..prefetch_degree:
        pf_addr = addr + d * entry.stride
        enqueue_prefetch(pf_addr)
  else:
    entry = {valid=true, pc, last_addr=addr, stride=0, confidence=0,
             last_warp_id=warp_id}
    table.insert_or_replace(key, entry)
```

### 2.4 Prefetch 发射

- 构造 `mem_fetch` 请求，标记为 prefetch（设置 `mf->set_prefetch(true)` 或自定义标记）
- 发往 L1D：调用 `m_L1D->access()` 或通过 GRASP 相同的注入路径
- `RESERVATION_FAIL` 时丢弃，不重试
- prefetch 目标：L1D sector 粒度（32B）

### 2.5 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-baseline_intra_enable` | 0 | INTRA 开关 |
| `-baseline_inter_enable` | 0 | INTER 开关 |
| `-baseline_stride_table_size` | 64 | stride table entries |
| `-baseline_stride_assoc` | 4 | set associativity |
| `-baseline_stride_conf_threshold` | 2 | confidence 阈值 |
| `-baseline_stride_degree` | 1 | prefetch degree |

### 2.6 实现估计

- 代码量：~200–300 行（含头文件）
- 修改文件：`shader.h`（声明成员）、`shader.cc`（hook）、`gpu-sim.cc`（配置注册）、`CMakeLists.txt`
- 工期：1–2 天

---

## 3. Baseline 3: Snake (Variable-length Chain-based Prefetching)

### 3.1 论文引用

Mostofi et al., "Snake: A Variable-length Chain-based Prefetching for GPUs", **MICRO 2023**.

论文 PDF 位置：`ima_plan/02_related_work/gpu/Mostofi 等 - 2023 - Snake A Variable-length Chain-based Prefetching for GPUs.pdf`

原始评估平台：**Accel-Sim v1.2.0 + AccelWattch v1.0**（与本项目同系列）。

### 3.2 机制概要

Snake 将传统单步 stride 扩展为**可变长度 stride chain**。核心观察：连续 PC 的 load 指令之间存在固定 stride 关系（inter-thread stride），多个这样的 stride 组成 chain。

三种 stride 维度：
1. **Inter-thread (IT)**：连续 PC 之间的 stride（如 PC_1 和 PC_2 的地址差固定）
2. **Intra-warp (IaW)**：同一 warp 同一 PC 的前后两次 issue 间 stride
3. **Inter-warp (IeW)**：同一 PC 不同 warp 间 stride

Snake 的创新在于将 IT stride 串联成 chain，一次 demand miss 可以触发整条 chain 的 prefetch。

### 3.3 数据结构

```cpp
// Head Table (HT): 记录 chain 起始 PC
struct ht_entry_t {
    bool valid;
    address_type pc;           // chain 起始 PC
    unsigned chain_length;     // chain 长度（跳数）
    unsigned tt_head_idx;      // 指向 Tail Table 的第一跳
    new_addr_type base_addr;   // 最近一次 demand addr
    int64_t iaw_stride;        // intra-warp stride
    int64_t iew_stride;        // inter-warp stride
    bool iaw_valid;
    bool iew_valid;
    unsigned training_count;   // 已训练的 warp 数
    unsigned long long last_access;
};

// Tail Table (TT): 记录 chain 中每一跳的 IT stride
struct tt_entry_t {
    bool valid;
    int64_t it_stride;         // inter-thread stride (PC_n → PC_{n+1} 的地址差)
    unsigned next_tt_idx;      // 链表指针：下一跳的 TT index（0xFFFF = end）
};

class baseline_snake_prefetcher_t {
    std::vector<ht_entry_t> m_ht;    // Head Table, 默认 128 entries
    std::vector<tt_entry_t> m_tt;    // Tail Table, 默认 256 entries
    unsigned m_training_warps;        // 训练所需 warp 数, 默认 3
    unsigned m_max_chain_length;      // 最大 chain 长度, 默认 8
    // Decoupled storage (简化版):
    // 可用独立小 buffer 或直接 prefetch 到 L1D（论文用 unified shared memory）
};
```

### 3.4 核心算法

#### 训练阶段（前 3 个 warp）

```
on_demand_load(warp_id, pc, addr, cycle):
  ht_entry = HT.lookup(pc)

  if ht_entry == NULL:
    // 新 PC，创建 HT entry
    HT.insert(pc, {base_addr=addr, training_count=1})
    return

  if ht_entry.training_count < training_warps:
    // 正在训练
    // 1. IaW stride: 同 warp 连续两次同 PC → 学 stride
    // 2. IeW stride: 不同 warp 同 PC → 学 stride
    // 3. IT chain: 观察连续 PC 序列，计算 stride chain
    ht_entry.training_count++
    update_strides(ht_entry, warp_id, addr)
    if ht_entry.training_count == training_warps:
      finalize_chain(ht_entry)  // 锁定 chain 结构
    return
```

#### Chain Detection（IT stride 学习）

```
IT chain 的学习依赖于观察连续 PC 的 demand load 地址:

假设 warp W 在 cycle T 访问了 PC_A → addr_A
     warp W 在 cycle T+k 访问了 PC_B → addr_B
     PC_A 和 PC_B 是连续 load 指令

则 IT_stride(A→B) = addr_B - addr_A

如果多个 warp 观察到相同的 IT_stride → confident → 建立 chain link

Chain: PC_A --[IT_stride_1]--> PC_B --[IT_stride_2]--> PC_C
```

#### Prefetch 阶段（训练完成后）

```
on_demand_load(warp_id, pc, addr, cycle):
  ht_entry = HT.lookup(pc)
  if ht_entry == NULL OR ht_entry.training_count < training_warps:
    return  // 未训练完

  // 1. Intra-warp prefetch: addr + iaw_stride
  if ht_entry.iaw_valid:
    enqueue_prefetch(addr + ht_entry.iaw_stride)

  // 2. Inter-warp prefetch: addr + iew_stride
  if ht_entry.iew_valid:
    enqueue_prefetch(addr + ht_entry.iew_stride)

  // 3. Chain prefetch: 沿 TT chain 逐跳生成 prefetch 地址
  pf_addr = addr
  tt_idx = ht_entry.tt_head_idx
  for hop in 1..chain_length:
    tt = TT[tt_idx]
    pf_addr = pf_addr + tt.it_stride
    enqueue_prefetch(pf_addr)
    tt_idx = tt.next_tt_idx
    if tt_idx == END: break
```

### 3.5 Decoupled Storage

论文的创新之一是将 prefetch 数据存入 **unified shared memory 的专用区域**而非 L1D，避免 L1 pollution。

**简化实现建议**：

- **方案 A（推荐）**：prefetch 直接到 L1D，不实现 decoupled storage。理由：(1) 实现代价显著降低；(2) 若 Snake 在 IMA 上效果差（预期如此），decoupled storage 不会改变结论；(3) 可以在论文中注明 "our Snake implementation omits decoupled storage, which may slightly overstate pollution effects but does not change the fundamental conclusion that stride-based methods fail on IMA"。
- **方案 B（完整）**：在 `ldst_unit` 中加一个小的 `snake_buffer_t`（类似 victim cache），prefetch 数据先存这里，demand miss 时先查此 buffer。

### 3.6 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-baseline_snake_enable` | 0 | 总开关 |
| `-baseline_snake_ht_size` | 128 | Head Table entries |
| `-baseline_snake_tt_size` | 256 | Tail Table entries |
| `-baseline_snake_training_warps` | 3 | 训练所需 warp 数 |
| `-baseline_snake_max_chain` | 8 | 最大 chain 长度 |
| `-baseline_snake_decoupled` | 0 | 是否启用 decoupled storage |
| `-baseline_snake_decoupled_size` | 4096 | decoupled buffer 大小（bytes） |

### 3.7 实现注意事项

1. **连续 PC 识别**：Snake 需要知道哪些 PC 是"连续 load"。在 trace-driven 模式下，可以通过 issue 阶段观察 warp 的指令流获取 PC 序列。
2. **训练冻结**：训练完成后（3 个 warp 都观察过），chain 结构锁定。新 kernel launch 时重置。
3. **PC 粒度**：Snake 以 PC 为 key（不含 warp_id），因为 SIMT 模型下所有 warp 执行相同指令。
4. **IMA workload 上的预期行为**：Snake 在 IMA workload 上应表现差——data load 的地址是数据依赖的，不存在跨 warp/跨 iteration 的 stride，因此 confidence 无法达标或 prefetch 准确率极低。

### 3.8 实现估计

- 代码量：~500–700 行
- 修改文件：同 INTRA/INTER + 新增 `baseline_snake.{h,cc}`
- 工期：1–2 周

---

## 4. Baseline 4: Spare Register Aware Prefetching

### 4.1 论文引用

Lakshminarayana & Kim, "Spare Register Aware Prefetching for Graph Algorithms on GPUs", **HPCA 2014**.

论文 PDF 位置：`ima_plan/02_related_work/gpu/Lakshminarayana和Kim - 2014 - Spare register aware prefetching for graph algorithms on GPUs.pdf`

原始评估平台：**MacSim** timing simulator（需移植到 Accel-Sim）。

### 4.2 机制概要

检测 **load-pair** 模式：

```
head-load:  R1 = LDG [base + i * stride]    // index load, strided
tail-load:  R2 = LDG [base2 + R1 * scale]   // data load, 依赖 head-load 的值
```

即 `A[B[i]]` 中的 `B[i]`（head）和 `A[B[i]]`（tail）。

关键创新：预取数据存入**空闲寄存器**而非 L1D cache，避免 GPU 小 L1D 的 early eviction 问题。

### 4.3 数据结构

```cpp
// Value Tag: 记录 load 返回值的 hash，用于检测 "值被用作地址" 关系
struct value_tag_entry_t {
    bool valid;
    address_type load_pc;       // 产生该值的 load PC
    unsigned warp_id;
    uint32_t value_hash;        // load 返回值的低 bits hash
    unsigned long long cycle;
};

// Load-ID Tag: 记录确认的 (head_pc, tail_pc) pair
struct load_pair_entry_t {
    bool valid;
    address_type head_pc;       // index load PC
    address_type tail_pc;       // data load PC
    unsigned training_iter;     // 已训练迭代数 (0..3)
    bool confirmed;             // 训练完成标志
    // stride 相关（head load 的 stride）:
    new_addr_type last_head_addr;
    int64_t head_stride;
    bool head_stride_valid;
};

// Shadow Iteration Counter: per-warp 循环迭代计数
struct shadow_iter_t {
    unsigned warp_id;
    unsigned iteration_count;   // 当前迭代数（用于计算 prefetch distance）
};

// Spare Register Tracker: 空闲寄存器分配
struct spare_reg_tracker_t {
    // per-warp: 分配的寄存器数 vs 实际使用的寄存器数
    unsigned allocated_regs;    // 编译器分配
    unsigned used_regs;         // 运行时最大使用
    // 可用空闲寄存器列表
    std::vector<unsigned> spare_regs;
};

class baseline_spare_reg_prefetcher_t {
    std::vector<value_tag_entry_t> m_value_tags;     // 默认 16 entries
    std::vector<load_pair_entry_t> m_load_pairs;     // 默认 8 entries
    std::map<unsigned, shadow_iter_t> m_shadow_iter;  // per-warp
    // Note: 空闲寄存器管理详见 §4.6
};
```

### 4.4 核心算法

#### Phase 1: Load-Pair 检测（训练）

```
on_load_return(warp_id, load_pc, addr, return_value, cycle):
  // 记录 value tag
  vt = value_tags.insert({load_pc, warp_id, hash(return_value)})

on_demand_load(warp_id, pc, addr, cycle):
  // 检查 addr 是否匹配某个 value tag
  for vt in value_tags:
    if vt.valid AND vt.warp_id == warp_id:
      if addr_matches_value(addr, vt.value_hash):
        // 发现 load-pair: vt.load_pc (head) → pc (tail)
        pair = load_pairs.find_or_create(vt.load_pc, pc)
        pair.training_iter++
        if pair.training_iter >= 3:
          pair.confirmed = true
```

#### Phase 2: Head Load Stride 学习

```
on_demand_load(warp_id, pc, addr, cycle):
  // 若 pc 是某个 confirmed pair 的 head_pc
  pair = load_pairs.find_by_head(pc)
  if pair AND pair.confirmed:
    delta = addr - pair.last_head_addr
    if delta == pair.head_stride AND delta != 0:
      pair.head_stride_valid = true
    else:
      pair.head_stride = delta
    pair.last_head_addr = addr
```

#### Phase 3: Prefetch 生成

```
on_demand_load(warp_id, pc, addr, cycle):
  pair = load_pairs.find_by_head(pc)
  if pair AND pair.confirmed AND pair.head_stride_valid:
    // 计算未来 head load 地址
    distance = compute_distance(warp_id)  // 基于 shadow iteration counter
    future_head_addr = addr + distance * pair.head_stride

    // Step 1: prefetch index (head)
    enqueue_index_prefetch(future_head_addr)

    // Step 2: 当 index prefetch 返回值后, 计算 data (tail) 地址
    //         在 fill 回调中: tail_addr = base2 + index_value * scale
    //         enqueue_data_prefetch(tail_addr)
```

### 4.5 Value-Address 匹配

这是 Spare Register 论文的核心检测机制。判断一个 load 返回值是否被用作后续 load 的地址组成部分：

```
addr_matches_value(load_addr, value_hash):
  // 论文的方案: 对 load 返回值做多种 shift 后与 address 比较
  // GPU 简化版本: 检查 addr 的低 N bits 是否包含 value_hash
  // 具体实现取决于 IMA pattern:
  //   对 A[B[i]]: tail_addr = base_A + B[i] * element_size
  //   所以 (tail_addr - base_A) / element_size == B[i]
  //   hash(tail_addr) 与 hash(B[i]) 应有相关性
  return (hash(load_addr) & mask) == (value_hash & mask)
```

### 4.6 空闲寄存器管理

**这是 Spare Register 论文区别于所有其他 prefetcher 的核心特征。**

论文方案：预取数据存入 warp 的空闲寄存器（`allocated - used` 的 gap），避免 L1 pollution。

**简化实现建议**：

在 Accel-Sim trace-driven 模式下，精确模拟空闲寄存器分配较为复杂（需与 operand collector 交互）。建议分两步：

1. **第一步（简化）**：prefetch 数据直接存入 L1D（与 INTRA/INTER 相同），但保留 load-pair detection + stride learning 的完整逻辑。在论文中标注 "we use L1D storage instead of spare registers for implementation simplicity; this may slightly understate Spare Register's performance due to L1 pollution, but the comparison remains meaningful as both GRASP and Spare Register would experience similar L1 capacity constraints"。

2. **第二步（完整，可选）**：在 `shader_core_ctx` 中维护 per-warp spare register count，prefetch 数据存入模拟的 register buffer（bypass L1D），demand load 时先查此 buffer。

### 4.7 Trace-Driven 模式下的特殊挑战

**⚠️ 关键问题：load 返回值不可用**

与 GRASP 的 `ima_pair_table` 面临的 P1 问题（见 `v1_implementation_problems.md`）相同：Accel-Sim trace-driven 模式下，`mem_fetch` 不携带 load 返回的数据值，只有地址和时序。

**解决方案**（与 GRASP 的 `ima_pair_table` 同源）：

- **方案 A（推荐）**：复用 GRASP 已有的 `ima_pair_chain_table_t`。该表已经预构建了 `(chain_id, idx_addr) → data_addr` 的映射。Spare Register 的 load-pair detection 可以改为：在 SASS 分析阶段离线识别 head-tail pair（与 GRASP CD 的 `LDG→IMAD.WIDE→LDG` 检测等价），然后在 demand load 时通过 pair table lookup 获取 data 地址。
- **方案 B**：从 trace 文件中额外提取 load 值。需要修改 tracer，侵入性大，不推荐。

### 4.8 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `-baseline_spare_reg_enable` | 0 | 总开关 |
| `-baseline_spare_reg_value_tags` | 16 | value tag table entries |
| `-baseline_spare_reg_load_pairs` | 8 | load pair table entries |
| `-baseline_spare_reg_training_iter` | 3 | 训练迭代数 |
| `-baseline_spare_reg_use_l1d` | 1 | 1=存 L1D（简化），0=存 spare register（完整） |

### 4.9 实现注意事项

1. **与 GRASP 的关键差异**：Spare Register 仅做 intra-warp 级别的 load-pair 检测，不利用 inter-warp 或 inter-CTA 信息。GRASP 的 CT/TT 是 per-SM shared（一个 warp 训练 → 所有 warp 受益）。
2. **Prefetch Distance**：论文用 shadow iteration counter 估算循环迭代数，动态调整 distance。简化实现可用固定 distance = 2-4。
3. **Tail Load 地址计算**：需要知道 `base_addr` 和 `element_size`。在 trace-driven 下，这些可以从 pair table 中获取，或从 SASS 分析中提取。

### 4.10 实现估计

- 代码量：~600–900 行
- 修改文件：同上 + 新增 `baseline_spare_reg.{h,cc}` + 可能修改 `mem_fetch.h`
- 工期：2–3 周

---

## 5. 评估工作负载

所有 baseline 使用相同的 workload 集合：

### 5.1 主要工作负载（IMA-heavy）

| trace_key | 算法 | IMA Pattern | IMA 占 L1 miss |
|-----------|------|-------------|----------------|
| `bfs_ima_high` | BFS | Pattern II: Frontier-Driven Gather | ~65% |
| `sssp_ima_high` | SSSP | Pattern II + weight | ~70% |
| `bc_ima_high` | BC | Pattern II: 双向遍历 | ~84% |
| `spmv_ima_high` | SpMV | Pattern I: Linear Gather | ~51% |
| `cc_ima_high` | CC | Pattern III: Data-Dependent | ~60% |

### 5.2 性能上下界（已有数据）

| Workload | No-prefetch (baseline) | Ideal L1D speedup |
|----------|----------------------|-------------------|
| BFS | 1.00× | 1.75× |
| SSSP | 1.00× | 2.46× |
| BC | 1.00× | 3.04× |
| CC | 1.00× | 2.22× |
| SpMV | 1.00× | 2.31× |

### 5.3 运行命令模板

```bash
# No-prefetch baseline（参考）
./traceL1 bfs_ima_high bfs_nopf

# INTRA stride
./traceL1 bfs_ima_high bfs_intra  # 需要在 config 中加 -baseline_intra_enable 1

# INTER stride
./traceL1 bfs_ima_high bfs_inter  # -baseline_inter_enable 1

# Snake
./traceL1 bfs_ima_high bfs_snake  # -baseline_snake_enable 1

# Spare Register
./traceL1 bfs_ima_high bfs_spare  # -baseline_spare_reg_enable 1

# GRASP
./traceL1 bfs_ima_high bfs_grasp  # -grasp_enable 1

# Ideal L1D（已有）
./traceL1 --ideal-l1d bfs_ima_high bfs_ideal
```

配置参数通过修改 `gpgpusim.config` 或在 `traceL1` 中新增 flag 传入。

---

## 6. 实现顺序与依赖

```
Phase 0 (已完成):
  ✓ No-prefetch baseline
  ✓ Ideal L1D
  ✓ GRASP

Phase 1 (P0, 第一批):
  → INTRA + INTER (合并为 baseline_stride_prefetcher_t)
  → 预计产物: baseline_stride.{h,cc}
  → 无外部依赖

Phase 2 (P1, 第二批):
  → Snake
  → 预计产物: baseline_snake.{h,cc}
  → 无外部依赖（与 Phase 1 可并行）

Phase 3 (P2, 第三批):
  → Spare Register
  → 预计产物: baseline_spare_reg.{h,cc}
  → 依赖: 需确认是否复用 ima_pair_chain_table_t（推荐复用）
```

---

## 7. 论文 PDF 位置（供实现 agent 查阅原文细节）

| Baseline | PDF 路径 |
|----------|---------|
| Snake | `ima_plan/02_related_work/gpu/Mostofi 等 - 2023 - Snake A Variable-length Chain-based Prefetching for GPUs.pdf` |
| Spare Register | `ima_plan/02_related_work/gpu/Lakshminarayana和Kim - 2014 - Spare register aware prefetching for graph algorithms on GPUs.pdf` |
| MT-Prefetch (INTRA/INTER 思想来源) | `ima_plan/02_related_work/gpu/Lee 等 - 2010 - Many-Thread Aware Prefetching Mechanisms for GPGPU Applications.pdf` |
| CAPS (INTRA/INTER 定义来源) | `ima_plan/02_related_work/gpu/Koo 等 - 2018 - CTA-Aware Prefetching and Scheduling for GPU.pdf` |

---

## 8. 验收标准

每个 baseline 实现完成后，需满足：

1. **编译通过**：`make -j -C ./gpu-simulator/` 无错误
2. **Smoke test**：`./traceL1 bfs_ima_high test_baseline_X` 能正常完成仿真
3. **Stats 输出**：仿真结束时打印 §0.6 中定义的 7 个指标
4. **开关隔离**：enable=0 时对仿真结果零影响（IPC 与 no-prefetch 完全一致）
5. **互斥检查**：同时启用多个 prefetcher 时打印 warning 或 assert
