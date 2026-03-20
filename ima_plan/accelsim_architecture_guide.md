# Accel-Sim / GPGPU-Sim 架构上手手册（面向 IMA Prefetch）

> 最后更新：2026-03-18
> 目标：帮你在不通读整个模拟器的前提下，建立一套足够支撑 IMA prefetch 研究与 AI Agent 协作的心智模型。

---

## 0. 先说结论：你到底要掌握什么

如果你的目标是继续做 `IMA -> miss/stall 归因 -> prefetch 设计/实现/评估`，你不需要把 Accel-Sim 全仓库读完。你需要真正吃透的，只有下面这 5 条链：

1. **trace-driven 指令从哪里来**
   - 不是 functional/PTX 路径在动态执行 CUDA C。
   - 当前主路径是 NVBit 采出来的 SASS-like trace，经 `trace-driven/` 解析，再喂给 shader core。

2. **一条 warp 指令如何进入 pipeline**
   - `fetch -> decode -> ibuffer -> scheduler -> issue -> functional unit`
   - 这决定你在 issue trace 里看到的 `ISSUE/STALL` 到底在描述哪一层。

3. **一条 global load 为什么会变成 `MEM_WAIT`**
   - 不是 “load 自己在 issue trace 里持续卡着”。
   - 真正常见的是：load 已经 issue 出去，目的寄存器还在 scoreboard 里占着，后续 consumer 指令因为 RAW hazard 被 scheduler 记成 `MEM_WAIT`。

4. **L1/L2/DRAM 返回路径是什么**
   - `ldst_unit -> L1D/L2 -> memory_sub_partition -> DRAM -> memory_sub_partition -> cluster -> ldst_unit response FIFO -> L1 fill/writeback -> scoreboard release`
   - 不搞清这条返回链，你很容易误判 prefetch 应该挂在哪、什么时候算“命中”、什么时候算“把等待藏起来了”。

5. **trace 各自记录的口径**
   - issue trace：scheduler 每 cycle 是否发射，以及 stall sample
   - L1/L2 trace：访存请求到达 cache 时的状态
   - HBM/L2 BW trace：带宽与占用
   - 它们可以按 cycle 对齐，但不代表“同一行就是同一条指令的同一步”

如果你只能投入很少时间，优先读：

1. `gpu-simulator/gpgpu-sim/src/gpgpu-sim/gpu-sim.cc`
2. `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc`
3. `gpu-simulator/gpgpu-sim/src/gpgpu-sim/gpu-cache.cc`
4. `gpu-simulator/gpgpu-sim/src/gpgpu-sim/l2cache.cc`
5. `gpu-simulator/trace-driven/trace_driven.cc`

---

## 1. 当前仓库的真实执行路径是什么

### 1.1 你现在跑的不是 “CUDA 程序直接在模拟器里执行”

本仓库日常实验主路径是：

1. 真实 GPU 上用 NVBit 采 trace
2. `traceL1` 选定某个 `trace_key`
3. trace-driven Accel-Sim / GPGPU-Sim 读取 `kernelslist.g`
4. 模拟器按 trace 中的 warp 指令、地址、active mask、寄存器信息推进 timing model

`traceL1` 里已经给 BFS 的 IMA workload 配好了 trace key：

- `bfs_ima_high`
- `bfs_ima_med`
- `bfs_ima_small`

对应入口见 `traceL1` 里的 `TRACE_MAP`。

### 1.2 trace-driven 模式下，指令来自哪里

`trace_shd_warp_t::get_next_trace_inst()` 会从 `warp_traces` 里按顺序取下一条 trace instruction，并把它 parse 成 `trace_warp_inst_t`：

- `gpu-simulator/trace-driven/trace_driven.cc:60`
- `gpu-simulator/trace-driven/trace_driven.cc:155`

`trace_shader_core_ctx::get_next_inst()` 覆盖了基类接口，真正从 trace warp 中取指：

- `gpu-simulator/trace-driven/trace_driven.cc:582`

所以你在 timing model 里分析 issue、cache、stall 时，**前端语义已经由 trace 固化**。你关心的是：

- 这条 trace 指令什么时候被 fetch/decode
- 什么时候 issue
- 访存请求什么时候进入 L1/L2/DRAM
- 什么时候返回并解除 scoreboard 依赖

而不是去纠结 functional simulator 如何解释 PTX。

---

## 2. 你应该怎么理解 shader core 的最小流水线

### 2.1 一个 core cycle 的顺序

`shader_core_ctx::cycle()` 的顺序非常关键：

1. `writeback()`
2. `execute()`
3. `read_operands()`
4. `issue()`
5. `decode()`
6. `fetch()`

源码：

- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc:4980`

这意味着：

- 本 cycle 先处理老指令的 writeback
- 再推进功能单元
- 再做本 cycle 的 scheduler issue
- 然后才 decode/fetch 新指令

所以 issue trace 中看到某个 warp stall，不代表“这个 warp 此刻没有更老的访存正在后面返回”。很多时候恰恰相反。

### 2.2 fetch / decode / ibuffer 是怎么衔接的

#### fetch

`shader_core_ctx::fetch()` 做两件事：

1. 如果 `L1I` 已经有指令返回，就把它放进 `m_inst_fetch_buffer`
2. 否则在可取指的 warp 中找一个，访问 `L1I`

关键点：

- `ibuffer_empty()` 的 warp 才会继续取新指令
- 发生 I-cache miss 时，会设置 `imiss_pending`

源码：

- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc:1527`

#### decode

`decode()` 会从 `m_inst_fetch_buffer` 取出 1 到 2 条指令，塞进 warp 的 `ibuffer`：

- `ibuffer_fill(0, pI1)`
- 如果还有下一条，`ibuffer_fill(1, pI2)`

源码：

- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc:1492`

#### ibuffer

warp 自己带 2-entry `ibuffer`，scheduler 不是直接对 trace 流取指，而是对 `ibuffer_next_inst()` 发射。

相关结构：

- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.h:229`
- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.h:295`

所以 issue trace 里的 `IBUFFER_EMPTY` 不是神秘状态，本质上就是：

- warp 当前没有 decode 好的指令可发
- 或者前端还没把下一条装进来

---

## 3. BFS 里哪些访问是 IMA，哪些不是

本文主例用 Gardenia BFS：

- `gpu-app-collection/gardenia/src/bfs/linear_base.cu:9`

核心 kernel：

```cpp
for (int offset = row_begin; offset < row_end; ++ offset) {
  int dst = column_indices[offset];
  if ((dists[dst] == MYINFINITY) &&
      (atomicCAS(&dists[dst], MYINFINITY, dists[src]+1) == MYINFINITY)) {
    assert(out_queue.push(dst));
  }
}
```

### 3.1 三类关键访存

#### A. `column_indices[offset]`

- 这是 CSR edge list 的顺序流
- 常常是 cache-friendly 或至少是 stride/streaming 风格
- 它是图算法必要访存，但**不是**你最关心的 IMA 根因

#### B. `dists[dst]`

- 这是典型 IMA
- `dst` 由上一条 load `column_indices[offset]` 动态产生
- 地址是否局部、是否能被 cache 命中，完全由 graph topology 和 frontier 展开方式决定

#### C. `atomicCAS(&dists[dst], ...)`

- 仍然围绕 `dst` 这个间接索引
- 但它引入了 read-modify-write 和 atomic serialization
- 所以在 issue trace 中，除了 `MEM_WAIT`，你经常还会看到 `WAIT_ATOMIC`

### 3.2 不要把 “所有 global load” 都叫 IMA

对 BFS 来说，真正和 IMA prefetch 最相关的是：

- 先读 `column_indices[offset]` 得到 neighbor id
- 再访问 `dists[dst]`

其中第二步才是 “用数据当索引”的那一步。

如果文档、分析脚本、甚至 AI Agent 把：

- `row_offsets[src]`
- `column_indices[offset]`
- `dists[dst]`
- `atomicCAS(&dists[dst], ...)`

全混成同一种 load，就会直接把 prefetch 设计方向带偏。

---

## 4. 一条 BFS load 从 fetch 到 refill 的完整生命周期

下面这条链是你最该真正搞懂的部分。

### 4.1 阶段 A：trace 指令被 fetch / decode 到 warp ibuffer

在 trace-driven 模式下：

1. `trace_shader_core_ctx::get_next_inst()` 从 trace 中拿到下一条 warp 指令
2. `shader_core_ctx::fetch()` 通过 `L1I` 把取指结果放进 `m_inst_fetch_buffer`
3. `shader_core_ctx::decode()` 把指令塞进 warp 的 `ibuffer`

这一步之后，warp 对 scheduler 来说才“有可发射候选”。

### 4.2 阶段 B：scheduler 选择 warp 并尝试 issue

调度核心在 `scheduler_unit::cycle()`：

- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc:2220`

它会扫描候选 warp，并检查：

- ibuffer 是否有指令
- 控制流是否允许
- scoreboard 是否冲突
- 对应执行管线是否有空位

如果能发射 memory op，会走：

- `m_shader->issue_warp(*m_mem_out, pI, active_mask, warp_id, m_id);`

对应位置：

- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc:2111`

### 4.3 阶段 C：issue 时，scoreboard 先把目标寄存器占住

`shader_core_ctx::issue_warp()` 会在发射后调用：

- `m_scoreboard->reserveRegisters(*pipe_reg);`

源码：

- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc:1639`
- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc:1752`

而 `Scoreboard::reserveRegisters()` 会把 global/local/texture 等 load 的目的寄存器标成 long operation：

- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/scoreboard.cc:88`

这一步是理解 `MEM_WAIT` 的关键。

**一旦 load issue 出去，它自己通常已经不再卡在 scheduler 里；真正后续被卡住的是消费者。**

### 4.4 阶段 D：memory op 进入 ldst_unit

memory 指令进入 `ldst_unit::issue()` 后，会根据 `accessq_count()` 记录 pending writes 数量：

- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc:3749`

直观理解：

- 一条 warp load 可能被 coalesce 成多个 memory accesses
- 只有这些 accesses 都完成，目标寄存器才算真正 ready

### 4.5 阶段 E：ldst_unit 决定走 L1D 还是 bypass

真正的 global/local memory access 由 `ldst_unit::memory_cycle()` 处理：

- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc:3315`

这里会判断：

- `CACHE_GLOBAL` 或 `gmem_skip_L1D` 时是否绕过 L1D
- 否则走 `process_memory_access_queue_l1cache(m_L1D, inst)`

也就是说，后续 trace 行的出现顺序，直接受这里控制。

### 4.6 阶段 F：生成 mem_fetch，并保留 per-lane 原始地址

`shader_core_mem_fetch_allocator::alloc(const warp_inst_t&, ...)` 在生成 `mem_fetch` 时，会把每个 active lane 的原始地址保存进去：

- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.h:2128`

这就是为什么 L1/L2 trace 能输出：

- `lane_id`
- `address`
- `pc`

而不是只有一个合并后的 transaction address。

### 4.7 阶段 G：L1D access，可能出现 `MISS / HIT / HIT_RESERVED`

L1 access 在 `l1_cache::access()`：

- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/gpu-cache.cc:2016`

读 miss 的核心逻辑在 `baseline_cache::send_read_request()`：

- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/gpu-cache.cc:1355`

你需要记住三种常见状态：

#### `HIT`

- 该 line 已经在 L1
- 请求可以很快在 L1 层返回

#### `MISS`

- tag probe 未命中
- 新建 MSHR / miss queue 项，往下层发请求

#### `HIT_RESERVED`

- 这不是普通 hit
- 它通常表示：同一 line 的 miss 已经在飞，新的请求 merge 到已有 MSHR
- 所以它不会立即拿到数据，只是“挂在同一个 outstanding miss 上”

这也是很多人第一次读 L1 trace 时最容易误解的地方。

### 4.8 阶段 H：miss 进入 L2 subpartition，再进 DRAM

全局时钟域推进在 `gpgpu_sim::cycle()` 中完成：

- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/gpu-sim.cc:2240`

在当前实现里，不要把它脑补成一个单纯的 `CORE -> L2 -> DRAM` 直线。更贴近代码的理解是：

1. 如果这一拍包含 `CORE`，先执行 `m_cluster[i]->icnt_cycle()`
   - 把已经回到 cluster 的 response 往具体 core 分发
2. 如果这一拍包含 `ICNT`，尝试把 memory subpartition 的回复推回 interconnect
3. 如果这一拍包含 `DRAM`，执行 `memory_partition_unit::dram_cycle()`
4. 如果这一拍包含 `L2`，执行 `memory_sub_partition::cache_cycle()`
5. 如果这一拍包含 `ICNT`，再做一次 `icnt_transfer()`
6. 如果这一拍包含 `CORE`，最后才执行 `m_cluster[i]->core_cycle()`

所以：

- response 先被 cluster/core 侧“接住”，再在后续 core cycle 里被 `ldst_unit` 消化
- issue trace 看到的 stall，和 L2/DRAM 正在发生的事之间，常常隔着不止一个局部状态机

L2 subpartition 的关键状态机在：

- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/l2cache.cc:479`

其中：

- `m_icnt_L2_queue`：上层请求刚到 subpartition
- `m_L2_dram_queue`：L2 miss 往 DRAM 走
- `m_dram_L2_queue`：DRAM 返回，等待 L2 fill 或直接上送
- `m_L2_icnt_queue`：准备回到 interconnect

DRAM 调度本体在：

- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/dram.cc:292`

注意两层 latency：

1. `memory_partition_unit::dram_cycle()` 里的 `m_dram_latency_queue`
   - 表示从 subpartition 到 DRAM controller 前的人为延迟
2. `dram_t::cycle()`
   - 表示真实 DRAM bank/queue/returnq 行为

### 4.9 阶段 I：数据返回 subpartition，再回 cluster / core

DRAM 返回后：

1. `memory_partition_unit::dram_cycle()` 把请求送入 `dram_L2_queue`
2. `memory_sub_partition::cache_cycle()` 决定：
   - 如果 L2 正在等 fill，就 `m_L2cache->fill()`
   - 否则直接放进 `m_L2_icnt_queue`
3. `gpgpu_sim::cycle()` 的 `ICNT` 域把 response 推回 core cluster
4. `simt_core_cluster::icnt_cycle()` 把 response 放进 cluster response FIFO
5. `ldst_unit::fill()` 把 response 放进该 core 的 `m_response_fifo`

关键源码：

- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/l2cache.cc:507`
- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/gpu-sim.cc:2249`
- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc:6049`
- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc:3396`

### 4.10 阶段 J：L1 fill / writeback / scoreboard release

`ldst_unit::cycle()` 会优先处理 response FIFO：

- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc:3976`

对 global read 来说有两种路径：

#### 路径 1：绕过 L1D

- 直接进 `m_next_global`
- 后续在 `ldst_unit::writeback()` 中变成 `m_next_wb`

#### 路径 2：正常 L1D fill

- `m_L1D->fill(mf, fill_cycle);`
- 之后当 `m_L1D->access_ready()`，`ldst_unit::writeback()` 会从 `m_L1D->next_access()` 取到它

相关代码：

- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc:4030`
- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc:3870`

最终，writeback 时会：

1. 递减 `m_pending_writes`
2. 当最后一个 pending access 完成，`releaseRegister`
3. `warp_inst_complete()`

源码：

- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc:3776`

这一步之后，依赖该寄存器的后续指令才不再被记作 `MEM_WAIT`。

---

## 5. 用真实 BFS trace 把这条链看一遍

这里优先用小样本：

- `result/issue_trace/bfs_ima_small_1sm_cta5_issue.csv`
- `result/L1cache_trace/bfs_ima_small_1sm_cta5_l1.csv`
- `result/L2cache_trace/bfs_ima_small_1sm_cta5_l2.csv`

原因很简单：它没有压缩，适合肉眼核对。

### 5.1 例子 A：`MISS -> FILL -> consumer MEM_WAIT`

L1 trace 片段：

```csv
cycle,sm_id,warp_id,lane_id,op,space,address,l1_status,pc
5540,0,0,0,LD,GLOBAL,0x7fc4b8400000,MISS,0x130
5962,0,0,0,LD,GLOBAL,0x7fc4b8400000,FILL,0x130
```

对应 issue trace 片段：

```csv
5495,0,0,0,NA,0,STALL,0x130,0x1,LOAD_OP,NA,REG_WAIT,...
5502,0,0,0,NA,0,ISSUE,0x130,0x1,LOAD_OP,GLOBAL,NA,...,(0x7fc4b8400000),(0),...
5504,0,0,0,NA,0,STALL,0x150,0x1,INTP_OP,NA,MEM_WAIT,1,0,...
5505,0,0,0,NA,0,STALL,0x150,0x1,INTP_OP,NA,MEM_WAIT,1,0,...
...
```

这组数据非常适合建立正确直觉：

1. `0x130` 这条 `LOAD_OP` 在 cycle `5502` 成功 issue
2. L1 trace 在 cycle `5540` 记录它为 `MISS`
3. 之后 stall 的 sample PC 已经不是 `0x130`，而是 `0x150/0x160/...`
4. 这说明真正卡住 scheduler 的，是后续 consumer 指令在等 `0x130` 产生的寄存器结果
5. 直到 cycle `5962` 出现 `FILL`，这条 outstanding miss 才算在 L1 层返回

这正是 `Scoreboard longop -> MEM_WAIT` 的典型模式。

如果再看同一地址在 L2 trace 里的样子：

```csv
cycle,sm_id,warp_id,lane_id,op,space,address,l2_status,pc
5744,0,0,0,LD,GLOBAL,0x7fc4b8400000,MISS,0x130
```

就能更清楚地把三层信息串起来：

- issue trace：`0x130` 已经发出去，后续 consumer 在 `MEM_WAIT`
- L1 trace：这次访问在 L1 是 `MISS`
- L2 trace：这次访问在 L2 也还是 `MISS`

换句话说，这不是 “L1 没命中但很快被 L2 挡住” 的情况，而是真正一路向下走了。

### 5.2 例子 B：`MISS -> 多个 HIT_RESERVED -> 单次 FILL`

L1 trace 片段：

```csv
11282,0,2,0,LD,GLOBAL,0x7fc4b8400200,MISS,0x40
11283,0,3,0,LD,GLOBAL,0x7fc4b8400200,HIT_RESERVED,0x40
11284,0,1,0,LD,GLOBAL,0x7fc4b8400200,HIT_RESERVED,0x40
11285,0,4,0,LD,GLOBAL,0x7fc4b8400200,HIT_RESERVED,0x40
11286,0,5,0,LD,GLOBAL,0x7fc4b8400200,HIT_RESERVED,0x40
11287,0,6,0,LD,GLOBAL,0x7fc4b8400200,HIT_RESERVED,0x40
11288,0,7,0,LD,GLOBAL,0x7fc4b8400200,HIT_RESERVED,0x40
11289,0,0,0,LD,GLOBAL,0x7fc4b8400200,HIT_RESERVED,0x40
11489,0,2,0,LD,GLOBAL,0x7fc4b8400200,FILL,0x40
```

这说明：

- 第一个 warp/lane 触发了真正 miss
- 同一 cache line 的后续请求没有再发独立 miss，而是 merge 进已有 MSHR
- 所以它们显示为 `HIT_RESERVED`
- 真正数据回来时，只有一次 `FILL`

如果以后你做 prefetch 命中分析，必须把：

- 普通 `HIT`
- `HIT_RESERVED`
- `FILL`

分开看。因为它们对 stall hiding 的意义完全不同。

### 5.3 例子 C：高压 BFS 为什么主要是 `MEM_WAIT`

`bfs_ima_high` 的 stall breakdown：

```csv
reason,stall_warp_events,fraction_of_stall_warp_events
MEM_WAIT,10911556984,0.70091383
WAIT_ATOMIC,3459009730,0.22219265
PIPE_BUSY,1192185367,0.07658112
```

而 `MEM_WAIT` 的热点 PC 分布里，top-5 只覆盖了 43% 左右：

```csv
reason,segment,rank,stall_warp_events,fraction_of_reason,topk_share
MEM_WAIT,0x1f0,1,1161450769,0.10644226,0.43036747
MEM_WAIT,0x690,2,940617649,0.08620380,0.43036747
...
MEM_WAIT,OTHER,0,6215577839,0.56963253,0.43036747
```

这说明两件事：

1. `bfs_ima_high` 的等待不是集中在某一两个“坏 load”上，而是更广泛的 consumer 链条问题
2. 单纯做 PC-local 的 prefetch 很可能不够，需要结合 IMA pattern 本身考虑

这也是为什么后续做 prefetch 设计时，不能只盯一张 top-k 图。

---

## 6. 这些 trace 到底各在记录什么

### 6.1 issue trace

issue trace 记录的是：

- 每个 `cycle`
- 每个 `SM`
- 每个 `scheduler`
- 是 `ISSUE` 还是 `STALL`

它最适合回答：

- warp 为什么没发出去
- `MEM_WAIT / REG_WAIT / PIPE_BUSY / WAIT_ATOMIC` 占比如何
- stall sample 对应的 PC 是什么

但它**不直接告诉你**：

- 这条 load 到了哪一级 cache
- miss 合并了几次
- 什么时候发生了 cache fill

### 6.2 L1 / L2 trace

L1/L2 trace 记录的是：

- 某个访问到达该级 cache 时
- cache 返回了什么状态

它最适合回答：

- 某个 PC 是 `HIT` 还是 `MISS`
- 同一 line 是否出现大量 `HIT_RESERVED`
- fill 回来时延大概多长

但它不直接告诉你：

- scheduler 为什么当下 stall
- 某个 miss 对哪几条后续 consumer 造成了阻塞

### 6.3 HBM / bandwidth trace

它记录的是总线层或 partition 层的吞吐与占用。

它最适合回答：

- 你的优化到底是减少了真正的 DRAM 流量
- 还是只是把 miss 从 `MISS` 变成了 `HIT_RESERVED`
- 或者把等待搬到了别的地方

### 6.4 正确的联合读法

推荐顺序：

1. 先看 issue trace stall breakdown
2. 再看热点 PC 的 L1/L2 状态
3. 然后看 bandwidth / occupancy
4. 最后回源码判断这些 PC 到底对应哪类访问

这也是后续让 AI Agent 协助分析时最稳的流程。

---

## 7. 多 workload 对照：为什么 BFS 不是唯一代表

### 7.1 SpMV：`x[col_idx]` 是最干净的 gather

Gardenia SpMV 标准写法：

- `gpu-app-collection/gardenia/src/spmv/base.cu:13`

核心访问：

```cpp
sum += Ax[offset] * x[Aj[offset]];
```

对 IMA 研究的意义：

- `Aj[offset]` 是顺序 CSR 流
- `x[Aj[offset]]` 是典型 gather
- 没有 BFS 那种 frontier 变化和 atomicCAS 语义干扰

所以如果你想验证：

- 预取器是否真的能抓住 “indirect index -> payload array” 关系

SpMV 通常比 BFS 更干净。

### 7.2 CC：`comp[dst]` 既是 IMA，又是迭代更新

Gardenia CC：

- `gpu-app-collection/gardenia/src/cc/base.cu:8`

核心访问：

```cpp
int dst = column_indices[offset];
int comp_dst = __ldg(comp+dst);
...
if (high_comp == comp[high_comp]) {
  comp[high_comp] = low_comp;
}
```

它和 BFS 的差异：

- 仍然有 `dst` 这个间接索引
- 但读写的是 `comp`，而且算法是多轮迭代收敛
- 所以 cache 中“旧值被反复摸”的行为比 BFS 更明显

从 prefetch 视角看：

- BFS 更像 “frontier 驱动的 bursty IMA + atomic”
- SpMV 更像 “纯 gather”
- CC 更像 “IMA + 读写回写 + 迭代性”

如果一个 prefetcher 只在 SpMV 上好看，不代表它在 BFS/CC 上真的成立。

---

## 8. 做 IMA prefetch 前，你必须知道的边界

### 8.1 你应该盯住哪一层

当前仓库已有 IMA prefetcher 挂点在：

- `ldst_unit::L1_latency_queue_cycle()`

相关代码：

- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc:3179`

这意味着它天然更偏：

- 看到 demand load 后，在 L1D 侧训练并发起预取

这类挂点的优点：

- 离真实 data access 很近
- 容易和 L1 trace 对齐

缺点：

- 训练时机已经比较晚
- 如果真正瓶颈是 `column_indices[offset] -> dists[dst]` 这类跨指令依赖，纯 L1D-side 观察未必够早

### 8.2 ideal L1D / perfect mem 改变的是哪一段路径

`gpgpu_perfect_l1d` 在 `l1_cache::access()` 里把 eligible 访问强制视为 `HIT`：

- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/gpu-cache.cc:2023`

它改变的是：

- L1 miss / lower-level access / refill 这一段

它**不改变**：

- scheduler 数量
- scoreboard 逻辑
- atomic 语义
- barrier / done / issue width

所以如果 ideal L1D 下 IPC 没涨甚至掉了，不能简单说 “memory 不重要”。
更可能是：

- warp 到达同步点更拥挤
- atomic / barrier 重新成为主瓶颈
- 读加速后暴露了别的结构性依赖

### 8.3 预取成效不能只看 miss rate

真正要联动看：

1. `MISS` 是否减少
2. `HIT_RESERVED` 是否上升
3. `MEM_WAIT` 是否下降
4. `WAIT_ATOMIC` / `PIPE_BUSY` 是否被放大
5. HBM 带宽是否明显增加

一个常见坏情况是：

- prefetch 把 demand miss 提前成了 prefetch miss
- miss rate 看起来好了一点
- 但 DRAM 带宽、MSHR 压力、fill port 竞争上去了
- 最终 `MEM_WAIT` 没降多少，甚至让别的 stall 变坏

---

## 9. 如果让 AI Agent 协助你做后续工作，应该怎么分工

### 9.1 可以直接交给 AI Agent 的任务

- 给定热点 PC，回溯它在源码里属于哪类访问
- 联合解析 issue/L1/L2/bandwidth trace
- 做 workload 间的 IMA pattern 对照
- 起草 prefetch 设计文档和实验矩阵

### 9.2 你需要亲自把关的任务

- 一个 PC 到底是不是“真正的 IMA payload access”
- 一个 stall 变化到底是“性能改善”还是“时序重排”
- prefetch 挂点是否真的符合你要解决的问题

### 9.3 最适合给 Agent 的阅读入口

按顺序给它这些文件，效率最高：

1. `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc`
2. `gpu-simulator/gpgpu-sim/src/gpgpu-sim/gpu-cache.cc`
3. `gpu-simulator/gpgpu-sim/src/gpgpu-sim/l2cache.cc`
4. `gpu-simulator/trace-driven/trace_driven.cc`
5. `result/issue_trace/...` 与 `result/L1cache_trace/...`

并明确要求它先回答这三个问题：

1. 该 PC 对应的是 producer load、consumer use，还是 atomic/store？
2. 它的等待主要发生在 scoreboard、L1 miss、L2 miss，还是同步点？
3. 这个 workload 的 IMA 模式更像 BFS、SpMV，还是 CC？

---

## 10. 最后给你的阅读建议

如果你要在最短时间内真的“会用”模拟器，而不是只会说概念，建议按下面顺序读：

1. 先看第 4 节，把一条 load 的生命周期读通
2. 再用第 5 节的小样本 trace 把 `MISS -> MEM_WAIT -> FILL` 对起来
3. 然后看第 8 节，明确 prefetch 设计到底要解决哪一段
4. 最后再去做 workload 间对照，而不是一上来就横向比较一堆 benchmark

一句话总结：

> 对 IMA prefetch 研究来说，你真正要掌握的不是 “GPU cache 的一般原理”，而是 “这个仓库里，哪条 trace 行对应哪一级状态机里的哪一步”。只要这件事你能说清楚，后面的设计、实现、分析都会稳很多。
