# Warp Load Tables 说明

这份说明只针对 `extra_pattern` 目录下的两张表：

- `warp_load_events_<scheduler>.csv`
- `warp_load_sectors_<scheduler>.csv`

它们的目标不是给出“整个 BFS 的总览统计”，而是把 **IMA region 内的 `index_load` / `data_load`** 逐次拆出来，直接回答下面这些问题：

- 某个 warp 在什么 cycle 发出了一次 IMA load
- 这次 load 访问了哪些地址、哪些 cacheline
- 这次 load 在 L1 上最先看到的状态是什么
- 如果 miss 了，refill 最晚什么时候回来
- 一次 warp load 内部，不同 sector 的命中/回填是否一致

## 1. 两张表分别看什么

### `warp_load_events_<scheduler>.csv`

这是 **按“每次 warp 发出一条 IMA load”聚合** 的表。

一行代表一次 `index_load` 或 `data_load` 指令 issue。适合回答：

- 这个 warp 在什么时候发出了这次 IMA load
- 这次 load 总共触达了多少 sector
- 整体上这次 load 是 hit、hit_reserved 还是 miss
- 如果需要等 refill，最晚要等到什么时候

这张表适合做 **prefetch timeliness** 判断。

### `warp_load_sectors_<scheduler>.csv`

这是把上面一条聚合 issue **按 sector 展开** 的表。

一行代表这次 issue 里的一个 sector 地址。适合回答：

- 这次 issue 里具体是哪些地址在 miss
- 是不是只有少数 sector miss，其他 sector 已经 hit
- refill 是不是集中在某几个地址

这张表适合做 **prefetch accuracy / coverage / granularity** 判断。

## 2. 怎么读每一列

### `warp_load_events`

- `role`: `index_load` 或 `data_load`
- `warp_id`: warp 编号
- `issue_seq`: 同一个 `(warp_id, role)` 下的第几次 issue。注意它是 **全 trace 顺序号**，不是进入当前 window 后重新从 0 计数
- `issue_cycle`: 这次 issue 的 cycle
- `scheduler`: 发出该指令的 scheduler 编号
- `pc`: 对应 load 指令的 PC
- `issue_mask_hex`: 这次 issue 的活跃线程 mask，十六进制表示
- `sector_addr_count`: 这次 issue 触达的唯一 sector 地址数量
- `sector_addrs`: 这次 issue 的 sector 地址列表，用 `;` 拼接
- `cacheline_ids`: 对应 cacheline 编号列表，用 `;` 拼接
- `first_status`: 这次 issue 的聚合 L1 初始状态
- `refill_cycle`: 如果这次 issue 有 miss-like sector，这里记录相关 sector 中 **最后一个** refill 到达的 cycle
- `issue_to_refill`: `refill_cycle - issue_cycle`

### `warp_load_sectors`

- 前 7 列与 `warp_load_events` 含义一致，用来和聚合表对齐
- `sector_idx`: 这次 issue 内部的 sector 序号
- `sector_addr`: 该 sector 地址
- `cacheline_id`: 该地址所在 cacheline
- `initial_l1_status`: 该 sector 在 L1 上最先观察到的状态
- `initial_cycle`: 观察到该初始状态的 cycle
- `fill_cycle`: 如果该 sector 需要 refill，这里记录对应的 fill cycle

## 3. 这两张表是怎么生成的

实现代码在 [plot_ima_timeline.py](/workspace/prefetch/ima_plan/04_prefetcher_design/extra_pattern/plot_ima_timeline.py)。

核心逻辑如下：

1. 从 issue trace 中只保留 `ISSUE` 事件。
2. 通过 `pc_classification.csv` 把 PC 映射成 `index_load` / `data_load`。
3. 进一步过滤，只保留：
   - `op == LOAD_OP`
   - `space in {GLOBAL, LOCAL}`
   - `mask != 0`
4. 从 issue trace 的 `Issue_Sector_Addresses` 取出这次 issue 实际访问到的 sector 地址。
5. 对每个 `(warp_id, sector_addr)`，去 L1 trace 里找从 `issue_cycle` 开始、`3000` cycle 窗口内的最早初始状态。
6. 如果该 sector 是 miss-like，再去找对应的 `FILL` cycle。
7. 最后把同一条 issue 下所有 sector 聚合成 `warp_load_events`，并把每个 sector 的明细写入 `warp_load_sectors`。

当前聚合优先级是：

`MISS > HIT_RESERVED > HIT > RESFAIL > UNKNOWN`

因此 `warp_load_events.first_status` 的含义是：

- 只要这次 issue 里有任意一个 sector 是 miss-like，整条 issue 就会被记成 `MISS`
- 否则如果有 `HIT_RESERVED`，就记成 `HIT_RESERVED`
- 否则如果全是正常 hit，就记成 `HIT`

## 4. 读表时最重要的几个点

### 先看 `events`，再下钻到 `sectors`

推荐顺序是：

1. 在 `warp_load_events` 里找出 `data_load` 的高 miss 区段
2. 再到 `warp_load_sectors` 看这些 issue 到底是“全体 sector 都 miss”还是“只有少量 sector miss”

如果只看 `events`，你知道这次 issue 很差，但不知道差在几个地址上。

### `HIT_RESERVED` 不能当作真正 hit

对 prefetcher 而言，`HIT_RESERVED` 更接近“这条线正在回来，但 demand 还是要等”。它说明：

- 地址可能已经被更早的请求触发
- 但本次 demand 并没有做到“到达即命中”

所以设计 prefetcher 时，`HIT_RESERVED` 更应该被当成 **timeliness 不够** 的信号，而不是成功 hit。

### `issue_to_refill` 主要看 data side

如果你想判断 prefetch 是否来得及，最有用的列通常是：

- `role`
- `issue_cycle`
- `first_status`
- `refill_cycle`
- `issue_to_refill`

经验上：

- `index_load` 更像链的前半段
- `data_load` 更像真正拖慢 warp 的后半段

因此设计 prefetcher 时，通常先盯 `data_load`。

### `sector_addr_count` 和 `sector_idx` 用来判断粒度问题

如果一条 `data_load` 一次触达很多 sector，但只有其中少数 miss，说明：

- 直接按整条 warp 指令粗粒度预取，可能会过度预取
- 更适合按 cacheline / sector 粒度做选择

如果大多数 sector 都 miss，而且 refill 也集中偏晚，那么更像是工作集或随机性本身太强。

## 5. 对 prefetcher 设计最有价值的信息

用这两张表时，建议重点回答下面四个问题：

### 1. 该不该预取 `index_load` 还是 `data_load`

看 `warp_load_events` 里两种 `role` 的 `first_status` 和 `issue_to_refill`。

- 如果 `index_load` 大多已经 hit，而 `data_load` 经常 miss/hit_reserved，目标应优先放在 `data_load`
- 如果 `index_load` 自身就很差，链头都没拉起来，先救 `index_load` 更合理

### 2. 预取要提前多少

看 `data_load.issue_to_refill` 的分布。

- 如果 refill 经常比后续依赖晚很多，说明触发太晚
- 如果多数已经变成 `HIT_RESERVED`，说明方向对了，但还需要再提前

### 3. 预取粒度会不会太粗

看 `warp_load_sectors`。

- 如果一条 issue 内只有少数 sector 真正 miss，整 warp 全量预取可能浪费很多带宽
- 如果 miss sector 很分散，说明地址确实 scatter，prefetch 准确度会更难

### 4. 哪些 warp 更值得优先分析

优先挑下面这类 warp：

- `data_load` 的 `MISS/HIT_RESERVED` 多
- `issue_to_refill` 长
- 同一 `warp_id` 下连续几次 `data_load` 都很差

这类 warp 最能体现 prefetcher 是否真的缓解了 IMA 链。

## 6. 使用边界

- 这两张表只覆盖 **当前选中的 dense IMA window**，不是全程序全量导出
- `warp_load_events` 是聚合视角；如果要看地址级分裂，必须回到 `warp_load_sectors`
- `issue_mask_hex` 只保留原始 mask，不会展开到具体 lane
- `first_status` 是聚合状态，不等于“每个 sector 都是这个状态”

## 7. 一个最简阅读例子

如果在 `warp_load_events` 里看到：

- `role=data_load`
- `first_status=MISS`
- `issue_to_refill` 很长

再到 `warp_load_sectors` 里发现：

- 这次 issue 只有 2 个 sector miss，其余都 hit

那它对 prefetcher 的含义通常是：

- 不是整条 warp load 都坏
- 而是少数关键地址拖住了整个 issue
- 这时更应该想“如何更早抓到真正 miss 的 line”，而不是无差别扩大预取范围
