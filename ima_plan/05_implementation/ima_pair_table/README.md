# ima_pair_table

## 目的

本目录用于把 `05_implementation/v1_implementation_problems.md` 中 P1 的想法，
落成可交接、可实现、可调试的文档集合。

当前口径已经固定为：

- `ima_pair_table` 在 `init_traces()` 后预构建，不是 runtime 在线学习
- `index prefetch issue` 时就查表，不在 fill 时二次 lookup
- lookup 结果保存在在途状态里
- `index prefetch` 命中或 fill 返回后，下一拍发出对应的 `data prefetch`
- 长依赖链通过 `primitive chain + successor chain` 传播，不把 `a[b[c[i]]]`
  当成一条大链直接处理

## 推荐阅读顺序

1. `implementation_walkthrough.md`
   - 这是主交接文档
   - 按真实代码路径解释“表怎么建、请求怎么流、fill 怎么发、日志怎么看”
2. `ima_pair_table_design.md`
   - 看规范和接口约束
3. `ima_pair_table_correctness.md`
   - 看正确性定义、验收标准、调试策略
4. `validation_status.md`
   - 看当前严格链提取后的实际验证状态
   - 包括修正过的输入口径、最小 kernelslist、日志位置、结果表

## 当前代码入口

- `trace_driven.cc`
  - 负责加载 chain CSV、按 warp 预构建 pair table、提供 lookup 接口
- `shader.cc`
  - 负责 issue-time lookup、PRB 管理、fill 后释放 target
- `mem_fetch.h`
  - 负责给 IMA prefetch 请求附加 metadata
- `gpu-sim.cc`
  - 负责注册 `-gpgpu_ima_prefetch_chain_csv` 和 `-gpgpu_ima_prefetch_debug`

## 文档内容

- `implementation_walkthrough.md`
  - 当前实现的完整走读
  - 包括输入格式、核心状态、真实控制流、调试入口、已知限制
- `ima_pair_table_design.md`
  - 设计规格、数据结构、时序约束、长链处理原则
- `ima_pair_table_correctness.md`
  - 如何检验“表项正确”
  - 当前实现已经能检查什么
  - 要做到 strongest proof 还缺什么
- `validation_status.md`
  - 当前严格 `exact_chain` 输入下的验证结论
  - 这轮到底证明了什么，没证明什么
  - 结果复现入口和临时产物位置

## 一句话定义

`ima_pair_table` 是一张按 warp 预构建的地址映射表：

```text
(chain_id, idx_addr) -> data_addr
```

当前实现把它接在如下流水上：

```text
demand load
  -> stride prefetcher 产生 index PF 地址
  -> 根据 demand PC 取 seed chain
  -> issue index PF 时查 pair table
  -> 命中的 data_addr 存入 PRB
  -> index PF 命中或 fill 返回后，下一拍发 data PF
  -> 若存在 successor chain，则 data PF 地址继续作为下一层 chain 的 index 输入
```

## 快速正确性检查

如果只想快速判断当前实现有没有明显跑偏，先看这 4 件事：

1. build 日志里每条 chain 的 `pairs > 0`
2. build 日志里 `dup_conflict == 0`
3. issue 日志里能看到 `chains > 0` 且部分请求 `hits > 0`
4. fill 日志里 `ready = fill_cycle + 1`

更完整的检查步骤见 `ima_pair_table_correctness.md`。
