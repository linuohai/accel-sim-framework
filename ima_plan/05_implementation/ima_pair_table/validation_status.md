# Validation Status

## 当前结论

截至当前版本，`ima_pair_table` 的验证结论可以收敛为：

- 本轮验证对象是 **pair table mapping correctness**
- IMA chain 输入已经改为严格遵守 `04_prefetcher_design.md` 的 `LDG -> IMAD.WIDE -> LDG` 寄存器链检测
- runtime loader 已经按 `function + impl + sm + classification` 过滤输入，只消费 `exact_chain`
- 在下列代表性 case 上，validation mode 结果均为：
  - `verify_mismatch = 0`
  - `verify_no_prediction = 0`
  - `verify_missing_idx = 0`

这说明在当前验证范围内，没有发现 `ima_pair_table` 把 `(idx_addr -> data_addr)` 映射错的反例。

## 这次修正了什么

### 1. 严格链提取算法

旧算法的问题是：

- 使用“反向找 writer + gap 分类”的启发式
- 没有按 `04_prefetcher_design.md` 的 FIFO / invalidation 语义做严格检测
- 会把宽松依赖误收成 IMA chain

这次改成：

- 按 SASS issue 顺序扫描
- 维护一个 offline FIFO
- 只接受严格链：

```text
LDG Rd
  -> IMAD.WIDE Rx, Rd, scale, c[base]
  -> LDG ..., [Rx]
```

- 加入两类失效语义：
  - 非 `IMAD.WIDE` 读取 `LOAD_RESULT` 时失效
  - 任意指令覆写 FIFO 中寄存器时失效

对应脚本：

- [analyze_family_variants.py](/workspace/prefetch/ima_plan/01_ima_characterization/family_variant_sass_analysis/analyze_family_variants.py)

### 2. runtime loader 输入过滤

旧 loader 只看：

- `index_pc`
- `data_pc`
- 可选 `kernel`
- 可选 `sm`

这不够，因为会把同一 `function` 的不同实现混在一起。

现在 loader 额外支持并使用：

- `function`
- `impl`
- `classification`

并在 runtime 只消费：

- `classification == exact_chain`

对应代码：

- [trace_driven.cc](/workspace/prefetch/gpu-simulator/trace-driven/trace_driven.cc)
- [trace_parser.h](/workspace/prefetch/gpu-simulator/trace-parser/trace_parser.h)
- [trace_parser.cc](/workspace/prefetch/gpu-simulator/trace-parser/trace_parser.cc)

### 3. 仓库内临时目录

不再使用系统 `/tmp`。

当前所有临时验证产物统一放在：

- [tmp](/workspace/prefetch/tmp)

并由：

- [tmp/.gitignore](/workspace/prefetch/tmp/.gitignore)

做忽略。

## 关键验证口径

这轮验证不是在验证完整 prefetcher policy，而是在验证：

- 给定一个真实 demand `idx_pc`
- 取它的真实 lane 地址 `idx_addr`
- 用 `(chain_id, idx_addr)` 去查 `ima_pair_table`
- 得到的 `predicted_data_addr`
- 是否等于未来真实 demand `data_pc` 的 `actual_data_addr`

对应运行开关：

```text
-gpgpu_ima_prefetch_enable 1
-gpgpu_ima_validate_all_idx_pc 1
```

含义：

- 绕过 stride/IPT coverage 问题
- 对所有真实 demand `idx_pc` 直接做 exact lookup
- 只验证 pair table 映射是否正确

## 这次使用的 strict chain 产物

生成位置：

- [strict_selected_chain_instances.csv](/workspace/prefetch/ima_plan/05_implementation/ima_pair_table/golden/strict_selected_chain_instances.csv)
- [spmv_base_strict.csv](/workspace/prefetch/ima_plan/05_implementation/ima_pair_table/golden/spmv_base_strict.csv)
- [bfs_linear_base_strict.csv](/workspace/prefetch/ima_plan/05_implementation/ima_pair_table/golden/bfs_linear_base_strict.csv)
- [sssp_linear_base_strict.csv](/workspace/prefetch/ima_plan/05_implementation/ima_pair_table/golden/sssp_linear_base_strict.csv)
- [bc_linear_base_strict.csv](/workspace/prefetch/ima_plan/05_implementation/ima_pair_table/golden/bc_linear_base_strict.csv)

最关键的两个人工纠错点已经得到修正：

- `spmv` strict CSV 中不再出现 `00a0 -> 0200/0230`
- `bfs` strict CSV 中不再出现错误的 `00f0 -> 01d0`

## 最小 kernelslist 与日志位置

最小验证入口：

- [tmp/ima_validate/spmv1/kernelslist.g](/workspace/prefetch/tmp/ima_validate/spmv1/kernelslist.g)
- [tmp/ima_validate/bfs4/kernelslist.g](/workspace/prefetch/tmp/ima_validate/bfs4/kernelslist.g)
- [tmp/ima_validate/sssp4/kernelslist.g](/workspace/prefetch/tmp/ima_validate/sssp4/kernelslist.g)
- [tmp/ima_validate/bcf4/kernelslist.g](/workspace/prefetch/tmp/ima_validate/bcf4/kernelslist.g)
- [tmp/ima_validate/bcr40/kernelslist.g](/workspace/prefetch/tmp/ima_validate/bcr40/kernelslist.g)

日志：

- [spmv1.log](/workspace/prefetch/tmp/ima_validate/spmv1.log)
- [bfs4.log](/workspace/prefetch/tmp/ima_validate/bfs4.log)
- [sssp4.log](/workspace/prefetch/tmp/ima_validate/sssp4.log)
- [bcf4.log](/workspace/prefetch/tmp/ima_validate/bcf4.log)
- [bcr40.log](/workspace/prefetch/tmp/ima_validate/bcr40.log)

说明：

- `bc_linear_base` 的完整 `kernelslist` 前面包含 `kernel-2 insert`
- 当前 trace loader 会在该小 kernel 的空 warp trace 上触发断言
- 因此 BC correctness 验证仍采用最小 kernelslist，直接跳到目标 IMA kernel

## 结果汇总

| case | pairs_sum | validate_lookup | verify_enqueue | verify_match | verify_mismatch | verify_no_prediction | verify_missing_idx |
|---|---:|---:|---:|---:|---:|---:|---:|
| `spmv1` | 20975 | 42946 | 447056 | 16287 | 0 | 0 | 0 |
| `bfs4` | 8137 | 26720 | 671179 | 7198 | 0 | 0 | 0 |
| `sssp4` | 49325 | 167080 | 3218977 | 34970 | 0 | 0 | 0 |
| `bcf4` | 926 | 463 | 926 | 926 | 0 | 0 | 0 |
| `bcr40` | 12702 | 33930 | 874076 | 11148 | 0 | 0 | 0 |

### 指标解释

- `pairs_sum`
  - 所有 `IMA pair table build` 日志中 `pairs=` 的总和
  - 表示实际建出的 `(idx_addr -> data_addr)` 表项数
- `validate_lookup`
  - validation mode 下，真实 demand `idx_pc` 触发 exact lookup 的次数
- `verify_enqueue`
  - 原始 pending verify record 数
  - 它是 raw event 数，不是最终消费数，所以通常会远大于 `verify_match`
- `verify_match`
  - 未来真实 demand `data_pc` 到来时，对拍成功的记录数
- `verify_mismatch`
  - 真正的 correctness failure
- `verify_no_prediction`
  - 真实 data access 到来时没有对应 prediction
  - 在 validation mode 下应当为 0
- `verify_missing_idx`
  - runtime pairing 时连前置 idx occurrence 都找不到
  - 在 strict exact-chain 输入下应当为 0

## 如何解读当前结果

当前结果最重要的是这三点：

1. `verify_mismatch = 0`
   - 没有发现 pair table 把地址映射错

2. `verify_no_prediction = 0`
   - validation mode 已经消除了旧的 stride/IPT coverage 干扰
   - 不会再出现“真实应该对拍但因为 prefetcher 没触发而无法验证”的情况

3. `verify_missing_idx = 0`
   - strict chain 输入和 runtime pairing 现在是一致的
   - 旧的宽松链污染已经被清掉

## 当前仍然不证明什么

这轮验证**不**证明：

- 完整 prefetch policy 已经最优
- 完整 timing 设计已经最终无误
- 当前硬件化 FIFO 深度已经定型

这轮验证**只证明**：

- 对 strict `exact_chain`
- `ima_pair_table` 的 `(chain_id, idx_addr) -> data_addr`
- 与未来真实 demand 地址一致

## 后续建议

1. 用同一套 strict 提取流程扩展到更多 workload
   - `cc`
   - `pr`
   - `vc`

2. 把 strict chain 生成流程正式固化
   - 不再依赖人工 review 某几个 case
   - 直接从 SASS 生成 runtime 可用 CSV

3. 在文档和代码里明确区分两条线
   - `pair table correctness validation`
   - `prefetch policy / timing evaluation`
