# ima_pair_table 实现走读

## 1. 这份文档解决什么问题

这份文档不是再解释一次 P1 背景，而是给后续窗口一个直接可用的交接入口：

- 当前实现到底接到了哪些代码路径
- 每一步的输入是什么
- 每一步的输出流向哪里
- 现在有哪些 debug print / assert 可以依赖
- 当前实现的边界和缺口是什么

如果只打算快速接手调试，请先读本文件，再按需回看设计文档和正确性文档。

## 2. 当前实现的总览

当前实现已经把 `ima_pair_table` 接到了一个最小可运行闭环里：

```text
trace init
  -> 预扫描 warp trace 建表
  -> demand load 训练 stride IPT
  -> stride IPT 生成 index prefetch 地址
  -> demand load 的 PC 提供 seed_chain_ids
  -> index prefetch issue 时查 pair table
  -> lookup 命中的 data_addr 放进 PRB
  -> index prefetch HIT 或 fill 返回
  -> 下一拍把 PRB 里的 data_addr 重新压回 prefetch queue
  -> 这些 data_addr 作为 DATA_PF 发往 L1D
```

长链不是单独一套逻辑，而是通过 `successor_chain_ids` 沿着这条流水继续传播。

## 3. 外部输入和配置

### 3.1 必需配置项

当前实现依赖两个新增配置项：

- `-gpgpu_ima_prefetch_chain_csv`
- `-gpgpu_ima_prefetch_debug`

相关注册点在 `gpu-sim.cc`。

### 3.2 chain CSV 的真实格式

当前实现读取的 CSV 至少要求这两列：

- `index_pc`
- `data_pc`

可选列：

- `kernel`
- `sm`

实际示例：

```csv
kernel,sm,index_pc,data_pc
bfs_kernel,sm80,00f0,01d0
bfs_kernel,sm80,01d0,02a0
bc_reverse,sm80,00f0,01d0
bc_reverse,sm80,00f0,01e0
bc_reverse,sm80,00f0,01f0
```

注意两点：

1. 当前实现不会读取 CSV 中显式提供的 `chain_id`
   - `chain_id` 是按过滤后的行顺序重新编号的
2. `successor_chain_ids` 也不是从 CSV 读入
   - 当前实现通过 `pc_data == child.pc_idx` 自动推导

这意味着当前 CSV 更像“primitive chain 列表”，不是完整的 chain graph 定义文件。

### 3.3 过滤规则

构建 pair table 时，chain row 会按当前 warp 所属 kernel 和 SM 过滤：

- 若 row 有 `kernel`，则必须匹配当前 kernel
- 若 row 有 `sm`，则必须匹配当前 trace 的 binary 对应 SM 名称

如果 CSV 过滤后为空，debug 模式会打印 `found no chain specs`。

## 4. 静态建表阶段

### 4.1 入口

入口在 `trace_shader_core_ctx::init_traces()`。

时序是：

1. `get_next_threadblock_traces()` 先把 warp trace 装进来
2. `m_trace_warp->set_kernel()` 绑定当前 kernel
3. 若开启 IMA prefetch 且配置了 chain CSV，则调用
   `build_ima_pair_tables()`

这意味着：

- pair table 是在 warp 正式 timing 执行前就建好的
- 不是 online learning
- build 阶段不会反过来污染 timing 行为

### 4.2 数据结构

当前建表状态挂在 `trace_shd_warp_t` 上：

- `m_ima_pair_tables`
- `m_chain_ids_by_pc`

每条 chain 表项包含：

- `desc`
  - `chain_id`
  - `pc_idx`
  - `pc_data`
  - `successor_chain_ids`
- `addr_map`
  - `idx_addr -> data_addr`
- build 和 issue lookup 统计项

### 4.3 建表算法

当前实现严格按 trace occurrence 配对：

```text
第 k 次 pc_idx
  对应
第 k 次 pc_data
```

具体过程：

1. 顺序扫描 `warp_traces`
2. 每遇到一次 `pc_idx`
   - 记录当前 active lane 的 `idx_addr`
3. 每遇到一次 `pc_data`
   - 取出同序号的 `idx_addr` 向量
   - 对 active lane 建立 `(chain_id, idx_addr) -> data_addr`

重复 key 的处理：

- 同 key 同 value
  - 记 `stat_duplicate_same_value`
- 同 key 不同 value
  - 记 `stat_duplicate_conflict_value`
  - 立即 `assert`

所以当前实现默认工作负载满足 read-only index array 假设。

### 4.4 build 阶段现有日志

打开 `-gpgpu_ima_prefetch_debug 1` 后，每条 chain 会打印一行摘要：

```text
IMA pair table build: warp=... chain=... pc_idx=... pc_data=...
pairs=... dup_same=... dup_conflict=... succ=...
```

这是当前最先要看的日志。

## 5. runtime 流水走读

### 5.1 demand load 训练 stride IPT

入口在 `ldst_unit::L1_latency_queue_cycle()`。

当满足以下条件时：

- `m_ima_prefetcher != nullptr`
- 当前请求是 `GLOBAL_ACC_R`
- 不是 store

就会调用：

```cpp
m_ima_prefetcher->on_load_access(mf_next->get_pc(), mf_next->get_addr(), cycle)
```

它输出的是一组“预测出来的 index prefetch 地址”，不是 data 地址。

### 5.2 demand PC 提供 seed chain

同一个 demand load 请求还会做一件事：

```cpp
warp->get_ima_seed_chain_ids(mf_next->get_pc())
```

当前逻辑是：

- 用 demand load 的 PC 去 `m_chain_ids_by_pc` 查有哪些 chain 以它作为 `pc_idx`
- 这些 chain id 作为 `seed_chain_ids`
- 后续每个由 stride IPT 产生的 index PF 地址都会带上这组 seed

因此当前实现假设：

- “哪条 chain 该被触发”是由 demand load 的 PC 决定的
- “具体去 prefetch 哪个 index sector”是由 stride IPT 决定的

### 5.3 prefetch queue 里存的是什么

`queue_ima_prefetch_request()` 往 `m_prefetch_queue` 里压的不是裸地址，而是：

- `addr`
- `warp_id`
- `seed_chain_ids`
- `ready_cycle`

这让同一条队列既能承载：

- 第一层 `INDEX_PF`
- fill 后转发出来的 `DATA_PF`
- successor chain 继续向下传播出来的下一层 index 输入

### 5.4 issue 阶段如何区分 INDEX_PF 和 DATA_PF

入口在 `inject_ima_prefetches()`。

判断规则很直接：

- `seed_chain_ids` 非空
  - 视为 `IMA_PREFETCH_INDEX`
- `seed_chain_ids` 为空
  - 视为 `IMA_PREFETCH_DATA`

这就是当前实现里 `INDEX_PF` / `DATA_PF` 的真实区分方法。

### 5.5 issue-time lookup 怎么做

若请求是 `INDEX_PF`，则：

1. 通过 `warp->lookup_ima_prefetch_candidates(req.addr, req.seed_chain_ids)`
   做 lookup
2. 若命中，得到一组 candidate
   - `idx_addr`
   - `data_addr`
   - `source_chain_id`
   - `successor_chain_ids`
3. 调用 `alloc_ima_prb_entry()` 把 candidate 列表存进 PRB

当前 lookup 逻辑的真实做法是：

- 先把请求地址对齐到 sector base
- 再按 `SECTOR_SIZE / 4` 扫描这个 sector 内所有 4-byte slot
- 对每个 slot 的 `idx_addr` 去 `addr_map` 查表

这意味着当前实现隐含了一个假设：

- index element 大小按 4B 处理

如果后续 workload 的 index 元素不是 4B，这里需要改。

### 5.6 PRB 里保存的是什么

当前 `ima_prb_entry_t` 比最初设计更简单，只保存：

- `valid`
- `warp_id`
- `std::vector<ima_prefetch_candidate_t> candidates`

也就是说：

- PRB entry 与一个 index sector 请求绑定
- 该 sector 对应的全部 target 地址都在这个 entry 里
- fill 回来时直接释放整个 entry 的全部 candidates

当前实现没有再额外记录 `sector_idx -> 子集合`，因为一个 PRB entry 已经对应一个具体 sector 请求。

### 5.7 `mem_fetch` metadata 的作用

在真正向 L1D 发出 prefetch 前，会构造 `mem_fetch` 并写入：

- `IMA_PREFETCH_INDEX` / `IMA_PREFETCH_DATA`
- `prb_entry_id`

这让 fill 路径能够判断：

- 这是 demand 还是 prefetch
- 若是 prefetch，是 index 还是 data
- 若是 index，对应应该释放哪个 PRB entry

### 5.8 L1D access 结果如何处理

当前实现按 `m_L1D->access()` 的结果分四类处理。

#### `HIT`

- 若是 `INDEX_PF` 且有 PRB entry
  - 立即 `release_ima_prb_targets(prb, cycle + 1, "hit")`
  - 再释放 PRB
- 这是合理的，因为 index 数据已经在 L1D，不需要等 fill

#### `MSHR_HIT` / `HIT_RESERVED`

- 当前实现直接 free PRB 并丢弃请求
- debug 模式打印 `dropped on in-flight line`

这是当前实现的保守策略，不会去等待已有 miss 完成。

#### `RESERVATION_FAIL`

- 当前实现直接 free PRB 并丢弃请求
- 不让 prefetch 反压 demand traffic

#### `MISS` / `SECTOR_MISS`

- cache 接管 `mem_fetch`
- 后续等 fill 返回

### 5.9 fill 路径如何发出 target

入口在 `ldst_unit::cycle()` 的 response handling 里。

当某个 global read fill 进入 L1D 后，会调用：

```cpp
on_ima_prefetch_fill(mf, fill_cycle)
```

其中仅当：

- `mf->is_ima_prefetch()`
- `mf->get_ima_kind() == IMA_PREFETCH_INDEX`

时才会继续。

然后它做两件事：

1. `release_ima_prb_targets(prb_entry_id, fill_cycle + 1, "fill")`
2. `free_ima_prb_entry(prb_entry_id)`

`release_ima_prb_targets()` 会把每个 candidate 的 `data_addr` 重新压回
`m_prefetch_queue`，并把 `successor_chain_ids` 一并带上。

这就是长链传播的关键点。

### 5.10 successor chain 是怎么接上的

candidate 带着：

- `data_addr`
- `successor_chain_ids`

被重新压回队列之后，这个 `data_addr` 会作为下一轮请求的 `req.addr`。

如果 `successor_chain_ids` 非空，它在下次 `inject_ima_prefetches()` 时又会被当成
一个新的 `INDEX_PF`：

- 当前层 `data_addr`
  - 变成下一层的 `idx_addr`
- 当前层的 successor
  - 变成下一层 lookup 的 seed chain

所以 `a[b[c[i]]]` 的多级传播不是专门硬编码的，而是靠：

- `successor_chain_ids`
- prefetch queue 的统一表示
- PRB 的同一套 fill-release 流程

自然串起来的。

## 6. 当前实现与原始设计相比的真实取舍

### 6.1 已经实现的部分

- pair table 预构建
- chain CSV 过滤与 dedupe
- successor chain 自动推导
- issue-time lookup
- PRB 缓存 lookup 结果
- index PF hit/fill 后下一拍发 data PF
- 多级 chain 的 successor 传播
- 最小 debug print 和 assert
- 正常构建流程下整体编译通过

### 6.2 当前仍然缺的 strongest proof

当前实现还没有自动完成这一步：

```text
predicted_data_addr == future actual demand data_addr
```

也就是还没有 runtime verify 队列。

因此现在能做到的是：

- 证明 build 路径合理
- 证明 issue/fill 时序合理
- 证明日志和内部状态自洽

但最强的 correctness proof 还需要下一步加 verify hook。

### 6.3 当前已知限制

1. lookup 默认按 4B index 元素扫描 sector
2. `chain_id` 来自 CSV 过滤后的顺序，不是外部稳定 ID
3. successor graph 只支持 `pc_data == child.pc_idx` 这种自动推导
4. `MSHR_HIT` / `HIT_RESERVED` 当前直接丢弃，不等待已有请求
5. 没有 runtime verify 队列，不能自动对拍 future demand 地址

## 7. 调试时应该先看哪里

### 7.1 build 是否正常

先看：

```text
IMA pair table build: ...
```

你要确认：

- 每条 chain `pairs > 0`
- `dup_conflict == 0`
- `succ` 数量符合预期

### 7.2 issue 是否命中 pair table

再看：

```text
IMA issue lookup: ...
```

你要确认：

- `chains > 0`
- 至少部分请求 `hits > 0`
- `prb >= 0` 的请求确实被分配了 PRB

### 7.3 fill 是否真的释放 target

然后看：

```text
IMA fill dispatch: ...
target chain=... idx=... data=... succ=...
```

你要确认：

- `reason=fill` 或 `reason=hit`
- `ready = fill_cycle + 1` 或 `cycle + 1`
- target 数量与 issue 阶段 lookup 命中数一致

### 7.4 长链是否继续传播

如果是多级 chain，继续看下一轮 `IMA issue lookup`：

- 它的 `addr` 应该来自上一轮打印出来的 `data_addr`
- `chains` 应该等于上一轮 candidate 的 `succ` 数量

## 8. 推荐 bring-up 顺序

1. 只开 build debug
   - 先确认表建出来
2. 再看 issue lookup
   - 先确认命中，不急着看性能
3. 再看 fill dispatch
   - 确认 `ready_cycle` 和 target 地址
4. 再看 successor chain
   - 确认长链传播
5. 最后再补 runtime verify
   - 这是 correctness 的最终证明

## 9. 后续窗口接手时最先要做的事

如果后续窗口的目标是“证明当前实现正确”，优先级应是：

1. 补 runtime verify 队列
2. 用 BFS 跑最小 trace
3. 用 BC 验证 one-to-many 的 `chain_id`
4. 用两级链样例验证 successor 传播

如果目标是“继续扩展实现”，优先级应是：

1. 把 chain graph 从自动推导升级成显式输入
2. 去掉 4B index 元素假设
3. 决定 `MSHR_HIT/HIT_RESERVED` 是否继续丢弃还是改成等待
