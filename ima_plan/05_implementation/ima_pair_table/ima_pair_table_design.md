# ima_pair_table 设计规格

## 1. 目标

P1 要解决的问题不是“如何预测 index prefetch 地址”，而是：

```text
在 trace-driven 模式没有 runtime payload 的前提下，
如何在不作弊的情况下得到未来 data load 的地址
```

当前规格固定为：

- `ima_pair_table` 从 trace 预构建
- `index prefetch issue` 时 lookup
- lookup 命中的 target 缓存在在途状态里
- `index prefetch` 命中或 fill 返回后，下一拍发出 target `data prefetch`

## 2. 核心术语

### 2.1 primitive chain

每条 primitive chain 由三元组定义：

- `chain_id`
- `pc_idx`
- `pc_data`

它表示一条固定依赖：

```text
load index -> load data
```

### 2.2 chain graph

多条 primitive chain 可以构成长依赖图。

例如：

```text
a[b[c[i]]]
```

拆成：

```text
chain 0: c[i]    -> b[c[i]]
chain 1: b[c[i]] -> a[b[c[i]]]
```

于是有：

```text
chain 0 -> chain 1
```

### 2.3 pair table

pair table 的逻辑定义是：

```text
(chain_id, idx_addr) -> data_addr
```

其中：

- `idx_addr` 来自 trace 中 `pc_idx` 的真实地址
- `data_addr` 来自 trace 中对应 `pc_data` 的真实地址

## 3. 输入与输出

### 3.1 输入

当前实现依赖三类输入：

1. `warp_traces`
   - 由 trace-driven warp 持有
2. chain CSV
   - 必需列：`index_pc`, `data_pc`
   - 可选列：`kernel`, `sm`
3. chain graph
   - 当前实现不是显式输入
   - 通过 `pc_data == child.pc_idx` 自动推导 successor

### 3.2 输出

输出分两层：

1. 静态 pair table
   - per-warp `addr_map`
2. runtime 在途状态
   - prefetch queue 中的请求
   - PRB 中缓存的 candidate 列表

## 4. 为什么 key 必须是 `(chain_id, idx_addr)`

单目标场景例如 BFS：

```cpp
dst = column_indices[offset];
d = dist[dst];
```

通常只有一条 chain。

但 BC reverse 中：

```cpp
dst = column_indices[offset];
a = depths[dst];
b = path_counts[dst];
c = deltas[dst];
```

同一个 `idx_addr` 可以映射到多个不同目标数组，所以不能只用 `idx_addr`。

规范要求 key 为：

```text
(chain_id, idx_addr)
```

## 5. 数据结构要求

### 5.1 trace warp 侧

pair table 挂在 `trace_shd_warp_t` 上：

- `m_ima_pair_tables`
- `m_chain_ids_by_pc`

其中每个 chain table 至少要有：

- chain 描述
- `idx_addr -> data_addr`
- build 统计
- issue lookup 统计

### 5.2 runtime 侧

runtime 最少需要两类状态：

1. pending prefetch request
   - `addr`
   - `warp_id`
   - `seed_chain_ids`
   - `ready_cycle`

2. PRB entry
   - 是否有效
   - 属于哪个 warp
   - 本次 index request 命中的全部 candidate

这里的关键不是字段名，而是语义：

- issue 时查出来的 `data_addr` 必须保存起来
- fill 时不再回表查第二次

## 6. 构建时机和构建算法

### 6.1 构建时机

构建发生在：

- `trace_shader_core_ctx::init_traces()`
- `get_next_threadblock_traces()` 之后
- warp 正式执行之前

因此它是：

- 由 trace 驱动
- 但不是 online learning

### 6.2 CSV 选择规则

当前实现先按以下条件过滤 CSV：

- `kernel` 列若存在，则必须匹配当前 kernel
- `sm` 列若存在，则必须匹配当前 SM 名称

过滤后会对 `(pc_idx, pc_data)` 去重，并按顺序重新编号 `chain_id`。

### 6.3 successor 推导

当前 successor 关系不是外部显式提供，而是自动推导：

```text
if chain[i].pc_data == chain[j].pc_idx
  then chain[i] -> chain[j]
```

这足够支持简单的两级或多级链，但不是通用的显式 graph 输入方案。

### 6.4 occurrence 配对规则

pair table 的每个表项必须来自真实 trace 配对：

- 第 `k` 次出现的 `pc_idx`
- 对应第 `k` 次出现的 `pc_data`

按 active lane 写入：

```text
(chain_id, idx_addr[lane]) -> data_addr[lane]
```

冲突规则：

- 同 key 同 value
  - 允许
- 同 key 不同 value
  - 记冲突并 `assert`

## 7. runtime 流程规范

### 7.1 demand load 训练 index prefetch

当前实现沿用已有 stride IPT：

- demand load 访问触发 `ima_prefetcher_t::on_load_access()`
- 输出一组预测的 index prefetch 地址

### 7.2 用 demand PC 决定 seed chain

同一个 demand load 还会用它的 PC 查询：

```text
pc -> seed_chain_ids
```

这些 seed chain 会附着在本次 index prefetch request 上。

### 7.3 issue-time lookup

当请求被从 prefetch queue 取出时：

- 若 `seed_chain_ids` 非空
  - 视为 `INDEX_PF`
  - 对该请求地址所在 sector 做 pair-table lookup
  - 命中的 candidate 放进 PRB
- 若 `seed_chain_ids` 为空
  - 视为 `DATA_PF`
  - 不做 pair-table lookup

### 7.4 fill-time dispatch

当 `INDEX_PF`：

- 在 `HIT` 时
  - 下一拍释放 PRB 中全部 target
- 在 `MISS/SECTOR_MISS` fill 返回时
  - 下一拍释放 PRB 中全部 target

释放出来的 target 重新进入 prefetch queue，地址为 `data_addr`。

### 7.5 successor 传播

每个 candidate 还带着 `successor_chain_ids`。

因此释放 target 时：

- 当前 `data_addr`
  会成为下一层请求的 `addr`
- 当前 `successor_chain_ids`
  会成为下一层请求的 `seed_chain_ids`

这就是当前实现支持 `a[b[c[i]]]` 这类长链的方式。

## 8. 当前实现映射

### 8.1 `trace_driven.cc`

负责：

- 读取并缓存 CSV
- 过滤当前 kernel / SM 的 chain row
- 构建 per-warp pair table
- 提供 `get_ima_seed_chain_ids()`
- 提供 `lookup_ima_prefetch_candidates()`

### 8.2 `shader.cc`

负责：

- demand load 训练 stride IPT
- 把 demand PC 转成 `seed_chain_ids`
- queue prefetch request
- issue-time lookup
- PRB 分配与释放
- `INDEX_PF` hit/fill 后转发 `DATA_PF`
- successor 传播

### 8.3 `mem_fetch.h`

负责：

- 给 prefetch 请求附加 `IMA_PREFETCH_INDEX` / `IMA_PREFETCH_DATA`
- 保存 `prb_entry_id`

### 8.4 `gpu-sim.cc`

负责：

- 注册 `-gpgpu_ima_prefetch_chain_csv`
- 注册 `-gpgpu_ima_prefetch_debug`

## 9. 当前实现的显式限制

当前实现不是最终形态，至少有这些限制：

1. lookup 默认按 `SECTOR_SIZE / 4` 扫 sector
   - 隐含 4B index 元素假设
2. chain graph 只支持自动推导 successor
   - 还不支持显式 graph 输入
3. `MSHR_HIT/HIT_RESERVED` 当前直接丢弃 prefetch
4. 还没有 runtime verify 队列
   - 无法自动证明 `predicted_data_addr == future actual_data_addr`

## 10. 实现要求

后续如果继续扩展这套实现，以下要求不能破坏：

- pair table 必须继续保持 prebuild
- lookup 必须继续保持在 issue 时完成
- fill 路径不能重新回表查第二次
- 长链传播必须通过显式 chain 信息完成，不能靠临时猜测
- debug print 和 assert 必须优先于性能优化
