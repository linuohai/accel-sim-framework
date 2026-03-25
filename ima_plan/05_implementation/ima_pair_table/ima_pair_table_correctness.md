# ima_pair_table 正确性与验收

## 1. 目标

本文件回答两个问题：

1. 如何定义 `ima_pair_table` 的正确性
2. 当前实现应该怎么检验，才能尽快定位错误

这里的“正确”不是只看 IPC 或 prefetch 命中率，而是看：

- 表项来源是否真实
- 映射是否唯一
- issue 和 fill 的时序是否诚实
- 预测地址是否与未来真实 demand 地址一致

## 2. 正确性的四层定义

### 2.1 来源正确

每个表项都必须能追溯到 trace 中的一次真实 `pc_idx` 与对应的 `pc_data`。

当前实现依赖：

- occurrence 配对
- build 阶段统计和 debug 摘要

需要检查：

- 每条 chain `pairs > 0`
- 不存在“表完全没建出来却继续运行”的情况

### 2.2 唯一性正确

对 read-only index array workload：

```text
(chain_id, idx_addr) -> data_addr
```

必须唯一。

当前实现已经内建：

- `stat_duplicate_same_value`
- `stat_duplicate_conflict_value`
- `duplicate_conflict_value > 0` 时直接 `assert`

这意味着当前可以直接证明：

- 构建出来的映射没有发生一 key 多值冲突

### 2.3 时序正确

当前实现的时序约束是：

- lookup 发生在 issue 时
- `DATA_PF` 不能在 `INDEX_PF issue` 当拍直接发出
- `INDEX_PF HIT` 时，最早下一拍发 `DATA_PF`
- `INDEX_PF fill` 时，最早下一拍发 `DATA_PF`

当前实现已经显式满足：

- `HIT` 路径：`cycle + 1`
- `fill` 路径：`fill_cycle + 1`

### 2.4 runtime 语义正确

这是 strongest proof：

```text
predicted_data_addr == future actual demand data_addr
```

当前实现还没有自动完成这一层，因为还缺 verify 队列。

所以现在必须把“当前能验证到哪一层”和“还差哪一层”分开说。

## 3. 当前实现已经能检查什么

### 3.1 build 正确性

现在就可以检查：

- chain CSV 是否被正确加载
- kernel / SM 过滤是否命中
- 每条 chain 是否建出了 pair
- 是否出现冲突

依赖日志：

```text
IMA pair table build: warp=... chain=... pc_idx=... pc_data=...
pairs=... dup_same=... dup_conflict=... succ=...
```

### 3.2 issue lookup 正确性

现在就可以检查：

- demand PC 是否能找到 `seed_chain_ids`
- 某个 index prefetch 地址所在 sector 是否命中了 pair table
- 命中的 candidate 是否被存入 PRB

依赖日志：

```text
IMA issue lookup: sid=... warp=... addr=... chains=... hits=... prb=...
```

### 3.3 fill dispatch 正确性

现在就可以检查：

- `INDEX_PF HIT` 是否立即走 `reason=hit`
- `INDEX_PF fill` 是否走 `reason=fill`
- target 地址是否被下一拍重新压回 queue
- successor chain 是否随 target 一起继续传播

依赖日志：

```text
IMA fill dispatch: sid=... prb=... reason=... warp=... targets=... ready=...
target chain=... idx=... data=... succ=...
```

### 3.4 长链传播正确性

现在就可以检查：

- 上一层释放出来的 `data_addr`
- 是否在下一轮作为新的 `addr` 再次出现于 `IMA issue lookup`
- `chains` 是否等于上一层 target 的 `succ` 数量

## 4. 当前实现还不能自动证明什么

当前还不能自动证明：

```text
predicted_data_addr == future actual_data_addr
```

因为还没有以下机制：

- lookup 命中时，把待验证项放进 verify 队列
- 未来 demand `pc_data` 真正执行时，拿 trace 真实地址做对拍
- 统计 `runtime_verify_pass / fail`

所以必须明确：

- 现在可以做强静态检查和强时序检查
- 但最强的 runtime 语义证明还需要再补一个 verify hook

## 5. 实操检验步骤

### 5.1 先确认构建入口没问题

构建必须从顶层走：

```bash
cd /workspace/prefetch/gpu-simulator/gpgpu-sim
source ./setup_environment
make -j2
```

不要直接在 `src/` 子目录下裸跑 `make`，否则 `SIM_OBJ_FILES_DIR` 不会被正确设置。

### 5.2 运行时至少加这两个参数

在你现有的 trace-driven 运行命令上额外加：

```text
-gpgpu_ima_prefetch_enable 1
-gpgpu_ima_prefetch_chain_csv <你的 chain csv>
-gpgpu_ima_prefetch_debug 1
```

其中：

- `gpgpu_ima_prefetch_enable`
  打开现有 stride IPT 和 prefetch 注入路径
- `gpgpu_ima_prefetch_chain_csv`
  提供 primitive chain 列表
- `gpgpu_ima_prefetch_debug`
  打开摘要和关键样例日志

### 5.3 第一轮只看 build

先跑一个最小 workload，例如 BFS。

只关注 build 日志，检查：

1. 每条 chain `pairs > 0`
2. `dup_conflict == 0`
3. `succ` 数量符合预期

如果这一步不对，后面都不需要看。

### 5.4 第二轮看 issue lookup

检查：

1. `chains > 0`
2. 部分请求 `hits > 0`
3. `prb >= 0` 的请求数量与 `hits > 0` 基本对应

若 `chains = 0`，问题通常在：

- demand PC 不在 `m_chain_ids_by_pc`
- CSV 过滤后没留下这条 chain

若 `hits = 0`，问题通常在：

- stride IPT 预测到的 index sector 不对
- pair table 没建到对应 sector
- 4B 元素假设与真实 workload 不一致

### 5.5 第三轮看 fill dispatch

检查：

1. `reason=fill` 或 `reason=hit` 是否符合预期
2. `ready` 是否总是等于当前事件周期 `+1`
3. `targets` 数量是否与该 PRB entry 的 candidate 数量一致
4. 打印出来的 `data` 地址是否明显落在合理目标数组区间

### 5.6 第四轮看长链传播

若是多级链，例如 `a[b[c[i]]]`，继续检查：

1. 上一层 `target data=... succ=N`
2. 下一轮 `IMA issue lookup` 的 `addr` 是否等于这个 `data`
3. 下一轮的 `chains` 是否与上一轮的 `succ` 对得上

## 6. 推荐 workload 顺序

### 6.1 BFS

用途：

- 先验证单链闭环
- 最容易发现 build / issue / fill 哪一步断了

### 6.2 SpMV

用途：

- 验证 occurrence 配对的稳定性

### 6.3 BC reverse

用途：

- 验证 one-to-many 映射必须依赖 `chain_id`

### 6.4 两级链样例

用途：

- 验证 successor 传播

## 7. 必须保留的 assert 和 print

### 7.1 必须保留的 assert

#### build 阶段

- `data_occurrence <= idx_occurrence`
- `duplicate_conflict_value == 0`

#### issue 阶段

- `warp != NULL`
- `prb_entry_id` 下标合法

#### fill 阶段

- `prb_entry_id < m_ima_prb.size()`
- `m_ima_prb[prb_entry_id].valid`

这些 assert 不是多余的，它们是 bring-up 时最快的错误定位点。

### 7.2 必须观察的 print

按优先级排序：

1. `IMA pair table build`
2. `IMA issue lookup`
3. `IMA fill dispatch`
4. `target chain=... idx=... data=... succ=...`
5. `IMA prefetch dropped on in-flight line`

## 8. 推荐验收标准

在当前实现还没有 verify hook 的前提下，最低验收标准是：

1. 能正常编译并进入 trace-driven 运行
2. BFS 上 build 日志显示 `pairs > 0`
3. 所有 workload 上 `dup_conflict == 0`
4. issue 日志中存在实际 lookup hit
5. fill 日志中 `ready = current_event_cycle + 1`
6. 多级链样例中 successor 传播可见

## 9. strongest proof 该怎么补

若你要真正证明“这张表没有错”，下一步必须补 runtime verify：

1. lookup 命中时记录待验证项
   - `chain_id`
   - `idx_addr`
   - `predicted_data_addr`
   - 期望的 `pc_data occurrence`
2. 当真实 demand `pc_data` 执行时
   - 从 trace 读出 `actual_data_addr`
3. 比较：
   - `predicted_data_addr == actual_data_addr`
4. 统计：
   - `runtime_verify_pass`
   - `runtime_verify_fail`

最终 strongest proof 的验收标准是：

```text
runtime_verify_fail == 0
```
