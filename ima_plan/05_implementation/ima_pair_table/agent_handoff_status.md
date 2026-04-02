# Agent Handoff Status

## 1. 这份文档的目的

这份文档用于向其他 agent 说明 `ima_pair_table` 这项工作的当前状态，避免后续对话重复踩同一批坑。

当前最重要的结论是：

- 这轮工作**只**在验证 `pair table mapping correctness`
- 目前已经把 IMA chain 的输入纠正为严格遵守 `04_prefetcher_design.md`
- 在严格 `exact_chain` 输入下，`spmv / bfs / sssp / bc forward / bc reverse` 的 runtime validation 结果均为：
  - `verify_mismatch = 0`
  - `verify_no_prediction = 0`
  - `verify_missing_idx = 0`

这意味着：在当前验证范围内，没有发现 `ima_pair_table` 把 `(idx_addr -> data_addr)` 映射错的反例。

## 2. 这轮工作验证什么，不验证什么

### 2.1 当前验证目标

当前验证目标非常明确：

- 给定一个真实 demand `idx_pc`
- 使用该次动态执行中每个 active lane 的真实 `idx_addr`
- 在 runtime 直接查 `ima_pair_table`
- 记录 `predicted_data_addr`
- 等未来真实 demand `data_pc` 执行时，读取真实 `actual_data_addr`
- 比较两者是否一致

也就是验证：

```text
(chain_id, idx_addr) -> data_addr
```

这张映射表本身是否正确。

### 2.2 当前不验证的内容

这轮**不**验证：

- stride/IPT prefetch policy 是否最优
- 最终 timing/pipeline 设计是否已完全定型
- `chain_with_preamble` 或更宽松依赖是否应该支持
- 所有 workload 是否都已覆盖

所以不要把这轮结果误读成：

- “整个 prefetcher 已经验证完毕”

当前最准确的说法是：

- `ima_pair_table` 的 mapping correctness，在 strict `exact_chain` 范围内已通过代表性 case 验证

## 3. 核心设计口径

### 3.1 `ima_pair_table` 的定义

当前实现里，`ima_pair_table` 的逻辑定义是：

```text
(chain_id, idx_addr) -> data_addr
```

并且：

- 每个 warp 在 `init_traces()` 后预构建自己的 pair table
- 不是 runtime 在线学习

### 3.2 validation mode 的口径

为了只验证表项正确性，而不受 stride/IPT coverage 干扰，新增了：

```text
-gpgpu_ima_validate_all_idx_pc 1
```

这个模式下：

- 不依赖 stride/IPT 去“学会” index prefetch
- 对所有真实 demand `idx_pc`，直接做 exact lookup
- 使用每个 active lane 的真实 `idx_addr`
- 只验证表是不是对的

这一步很关键，因为在此之前大量 `no_prediction` 主要是 prefetch coverage 问题，不是表项错误。

## 4. 本次修正了什么

### 4.1 旧的 IMA chain 提取算法为什么有问题

旧的离线提取脚本是：

- [analyze_family_variants.py](/workspace/prefetch/ima_plan/01_ima_characterization/family_variant_sass_analysis/analyze_family_variants.py)

旧逻辑的问题：

- 通过“反向回溯 writer + gap 分类”来找链
- 没有严格模拟 `04_prefetcher_design.md` 里的 FIFO issue-time detector
- 没有实现 invalidation 语义

因此会把宽松依赖误收成 IMA chain。

已确认的错误例子：

- `spmv` 中错误把 `00a0 -> 0200/0230` 当成 IMA chain
- `bfs` 中错误把 `00f0 -> 01d0` 当成 IMA chain

这两个例子都已经被清理掉。

### 4.2 新的 strict 提取算法

现在离线提取改为严格遵守 [04_prefetcher_design.md](/workspace/prefetch/ima_plan/04_prefetcher_design.md) 的流程：

- 按函数内 SASS issue 顺序扫描
- 维护 offline FIFO
- 只记录两类 entry：
  - `LOAD_RESULT`
  - `IMA_ADDR_COMPUTE`
- 只接受严格链：

```text
LDG Rd
  -> IMAD.WIDE Rx, Rd, scale, c[base]
  -> LDG ..., [Rx]
```

- 同时实现 invalidation：
  - 非 `IMAD.WIDE` 读取 `LOAD_RESULT` 时失效
  - 任意写回覆写 FIFO entry 时失效

这一步的本质是：

- 不再相信“宽松 producer 关系”
- 只相信严格寄存器链

### 4.3 runtime loader 的输入过滤

旧 loader 只看：

- `index_pc`
- `data_pc`
- 可选 `kernel`
- 可选 `sm`

这不够，因为会把同 `function` 的不同实现混在一起。

现在 loader 已改为支持并使用：

- `function`
- `impl`
- `sm`
- `classification`

并且 runtime 只消费：

- `classification == exact_chain`

## 5. 这次改动到哪些文件

### 5.1 严格链提取

- [analyze_family_variants.py](/workspace/prefetch/ima_plan/01_ima_characterization/family_variant_sass_analysis/analyze_family_variants.py)

关键变化：

- 新增 strict FIFO entry 结构
- 新增严格的 `read invalidation / write invalidation`
- `analyze_sass_file()` 改成顺序扫描，而不是反向 writer 回溯

### 5.2 runtime loader / trace metadata

- [trace_driven.cc](/workspace/prefetch/gpu-simulator/trace-driven/trace_driven.cc)
- [trace_parser.h](/workspace/prefetch/gpu-simulator/trace-parser/trace_parser.h)
- [trace_parser.cc](/workspace/prefetch/gpu-simulator/trace-parser/trace_parser.cc)
- [gpu-sim.cc](/workspace/prefetch/gpu-simulator/gpgpu-sim/src/gpgpu-sim/gpu-sim.cc)

关键变化：

- `kernel_trace_t` 增加 `trace_path`
- loader 从 trace 路径里推导 `impl`
- CSV 读取支持 `function / impl / classification / addr_pc`
- runtime 只消费 `exact_chain`

### 5.3 临时目录规范

用户要求不要再用系统 `/tmp`。

因此新增：

- [tmp/.gitignore](/workspace/prefetch/tmp/.gitignore)

当前所有中间产物统一写到：

- [tmp](/workspace/prefetch/tmp)

## 6. 当前 strict chain 产物

### 6.1 代表性 workload 的 strict CSV

位于：

- [strict_selected_chain_instances.csv](/workspace/prefetch/ima_plan/05_implementation/ima_pair_table/golden/strict_selected_chain_instances.csv)
- [spmv_base_strict.csv](/workspace/prefetch/ima_plan/05_implementation/ima_pair_table/golden/spmv_base_strict.csv)
- [bfs_linear_base_strict.csv](/workspace/prefetch/ima_plan/05_implementation/ima_pair_table/golden/bfs_linear_base_strict.csv)
- [sssp_linear_base_strict.csv](/workspace/prefetch/ima_plan/05_implementation/ima_pair_table/golden/sssp_linear_base_strict.csv)
- [bc_linear_base_strict.csv](/workspace/prefetch/ima_plan/05_implementation/ima_pair_table/golden/bc_linear_base_strict.csv)

### 6.2 当前 strict CSV 中的链数量

- `spmv/base`: 29
- `bfs/linear_base`: 7
- `sssp/linear_base`: 7
- `bc/linear_base`: 19

### 6.3 已确认的纠正结果

现在：

- `spmv_base_strict.csv` 中不再包含 `00a0 -> 0200/0230`
- `bfs_linear_base_strict.csv` 中不再包含错误的 `00f0 -> 01d0`

## 7. runtime validation 的运行方式

### 7.1 验证输入

当前使用的 strict chain 总表：

- [strict_selected_chain_instances.csv](/workspace/prefetch/ima_plan/05_implementation/ima_pair_table/golden/strict_selected_chain_instances.csv)

### 7.2 最小 kernelslist

为了避免完整 trace 中前置辅助 kernel 干扰，代表性 case 使用最小 kernelslist：

- [tmp/ima_validate/spmv1/kernelslist.g](/workspace/prefetch/tmp/ima_validate/spmv1/kernelslist.g)
- [tmp/ima_validate/bfs4/kernelslist.g](/workspace/prefetch/tmp/ima_validate/bfs4/kernelslist.g)
- [tmp/ima_validate/sssp4/kernelslist.g](/workspace/prefetch/tmp/ima_validate/sssp4/kernelslist.g)
- [tmp/ima_validate/bcf4/kernelslist.g](/workspace/prefetch/tmp/ima_validate/bcf4/kernelslist.g)
- [tmp/ima_validate/bcr40/kernelslist.g](/workspace/prefetch/tmp/ima_validate/bcr40/kernelslist.g)

### 7.3 验证命令口径

等价命令：

```bash
source /workspace/prefetch/gpu-simulator/setup_environment.sh release
/workspace/prefetch/gpu-simulator/bin/release/accel-sim.out \
  -trace <tmp/ima_validate/.../kernelslist.g> \
  -config /workspace/prefetch/gpu-simulator/gpgpu-sim/configs/tested-cfgs/SM80_A100_1SM_NOSUBCORE/gpgpusim.config \
  -config /workspace/prefetch/gpu-simulator/configs/tested-cfgs/SM80_A100_1SM_NOSUBCORE/trace.config \
  -gpgpu_max_completed_cta 1 \
  -gpgpu_ima_prefetch_enable 1 \
  -gpgpu_ima_validate_all_idx_pc 1 \
  -gpgpu_ima_prefetch_chain_csv /workspace/prefetch/ima_plan/05_implementation/ima_pair_table/golden/strict_selected_chain_instances.csv \
  -gpgpu_ima_prefetch_debug 1
```

## 8. 指标解释

### 8.1 `pairs_sum`

- 统计所有 `IMA pair table build` 日志中的 `pairs=...`
- 表示总共建出来多少个 `(idx_addr -> data_addr)` 表项

### 8.2 `validate_lookup`

- validation mode 下，真实 demand `idx_pc` 触发 exact lookup 的次数

### 8.3 `verify_enqueue`

- 原始 pending verify record 数
- 这是 raw event 计数，不是最终唯一消费数
- 通常会显著大于 `verify_match`

### 8.4 `verify_match`

- 未来真实 demand `data_pc` 到来时，对拍成功的条数

### 8.5 `verify_mismatch`

- 真正的 correctness failure
- 意味着 `predicted_data_addr != actual_data_addr`

### 8.6 `verify_no_prediction`

- 真实 data access 到来时，没有对应 prediction
- 在 validation mode 下理论上应当为 0

### 8.7 `verify_missing_idx`

- runtime pairing 时，连前置 idx occurrence 都找不到
- 在 strict `exact_chain` 输入下理论上应当为 0

## 9. 当前验证结果

日志位置：

- [spmv1.log](/workspace/prefetch/tmp/ima_validate/spmv1.log)
- [bfs4.log](/workspace/prefetch/tmp/ima_validate/bfs4.log)
- [sssp4.log](/workspace/prefetch/tmp/ima_validate/sssp4.log)
- [bcf4.log](/workspace/prefetch/tmp/ima_validate/bcf4.log)
- [bcr40.log](/workspace/prefetch/tmp/ima_validate/bcr40.log)

结果表：

| case | pairs_sum | validate_lookup | verify_enqueue | verify_match | verify_mismatch | verify_no_prediction | verify_missing_idx |
|---|---:|---:|---:|---:|---:|---:|---:|
| `spmv1` | 20975 | 42946 | 447056 | 16287 | 0 | 0 | 0 |
| `bfs4` | 8137 | 26720 | 671179 | 7198 | 0 | 0 | 0 |
| `sssp4` | 49325 | 167080 | 3218977 | 34970 | 0 | 0 | 0 |
| `bcf4` | 926 | 463 | 926 | 926 | 0 | 0 | 0 |
| `bcr40` | 12702 | 33930 | 874076 | 11148 | 0 | 0 | 0 |

### 9.1 如何解读

当前最关键的不是 `verify_enqueue` 和 `verify_match` 的比例，而是：

- `verify_mismatch = 0`
- `verify_no_prediction = 0`
- `verify_missing_idx = 0`

这三个量同时为 0，说明：

- 没有发现表项映射错误
- 没有因为验证模式本身漏掉本该验证的访问
- strict 输入和 runtime pairing 是一致的

## 10. 当前可以下的结论

当前最准确的结论是：

- 在 strict `exact_chain` 范围内
- 对 `spmv / bfs / sssp / bc forward / bc reverse`
- `ima_pair_table` 的 mapping correctness 没有发现反例

不要把这个结论扩大成：

- “整个 prefetcher 已验证完毕”

当前被证明的是：

- `pair table mapping correctness`

还没有被这轮证明的是：

- 完整 prefetch policy 是否最优
- 完整 timing 设计是否最终定型

## 11. 已知边界

### 11.1 BC 完整 kernelslist

完整 `bc_linear_base` trace 前面包含：

- `kernel-2 insert`

当前 trace loader 对这个小 kernel 的空 warp trace 不够健壮，会在 loader 断言处提前失败。  
因此 BC correctness 验证目前使用最小 kernelslist，只保留：

- 初始化 memcpy
- 目标 IMA kernel

### 11.2 仍未覆盖的 workload

本轮已经验证：

- `spmv`
- `bfs`
- `sssp`
- `bc forward`
- `bc reverse`

尚未扩展到：

- `cc`
- `pr`
- `vc`

### 11.3 语义层过滤尚未加严

现在已经确保：

- strict register-chain 正确

但如果后续研究口径还想进一步只保留“真正值得 prefetch 的 data-side chain”，可以再叠加一层更强的语义过滤。当前这层还没做。

## 12. 其他窗口接手时建议的顺序

1. 先看 [validation_status.md](/workspace/prefetch/ima_plan/05_implementation/ima_pair_table/validation_status.md)
2. 再看这份 [agent_handoff_status.md](/workspace/prefetch/ima_plan/05_implementation/ima_pair_table/agent_handoff_status.md)
3. 再看 strict CSV：
   - [strict_selected_chain_instances.csv](/workspace/prefetch/ima_plan/05_implementation/ima_pair_table/golden/strict_selected_chain_instances.csv)
4. 若要继续扩 workload，优先复用：
   - [analyze_family_variants.py](/workspace/prefetch/ima_plan/01_ima_characterization/family_variant_sass_analysis/analyze_family_variants.py)
5. 若要继续 runtime 验证，优先复用：
   - [tmp/ima_validate](/workspace/prefetch/tmp/ima_validate)

## 13. 建议的下一步

1. 用同样的 strict 提取流程扩展到：
   - `cc`
   - `pr`
   - `vc`

2. 决定是否要在 strict register-chain 之上，再叠加一层“语义目标链”过滤

3. 若准备从 correctness 进入 prefetch policy 评估，再重新开启 stride/IPT 路径，单独评估 coverage / timeliness / traffic 开销
