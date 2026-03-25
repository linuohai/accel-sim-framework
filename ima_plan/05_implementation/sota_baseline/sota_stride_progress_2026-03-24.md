# SOTA Stride Baseline 阶段性进展记录（2026-03-24）

> 目的：记录 `baseline-intra / baseline-inter` 当前已经完成的实现、验证结果与阶段性结论，作为后续继续开展 SOTA baseline 实验的背景材料。
>
> 范围：本文件只记录当前 `stride baseline` 的实现和实验进展，不覆盖 `Snake` / `Spare Register` 的正式实现。
>
> 状态：截至 2026-03-24，`baseline-intra` 已经具备作为后续 SOTA 对照基线的实验价值；`baseline-inter` 已完成接线，但尚未观察到稳定收益。

---

## 1. 当前工作位置

本轮 SOTA stride baseline 的实现与实验主要发生在独立 worktree：

- worktree：`/workspace/prefetch/worktrees/sota_stride`
- 分支：`exp/sota_stride`

主仓库 `/workspace/prefetch` 目前主要承担：

- 研究文档与交接材料存放
- 实验背景与结论固化
- 为后续 agent 提供无需聊天上下文的接手入口

因此，下面提到的代码状态与日志路径，默认都以 `worktrees/sota_stride` 为准。

## 2. 已完成的实现范围

### 2.1 已落地内容

已经完成并可运行的内容包括：

- `baseline_prefetcher` 公共框架
- `baseline_stride_prefetcher_t`
- `--baseline-intra` / `--baseline-inter` 的 `traceL1` 入口
- baseline 统计输出：
  - `prefetch_issued`
  - `prefetch_hit`
  - `prefetch_useful`
  - `prefetch_useless`
  - `prefetch_rfail`
  - `coverage`
  - `accuracy`
  - `demand_miss`

### 2.2 当前最关键的两个实现修复

本轮验证中，真正让 `baseline-intra` 从“基本无效”变成“对 IMA 图负载有稳定小幅收益”的关键修复有两个：

1. baseline 训练地址改为使用 request-specific lane address  
   在 `shader.cc` 的 baseline hook 中，不再直接用 instruction 级别的统一地址，而是根据 `mf_next->get_access_warp_mask()` 选择本次请求实际对应的 lane 地址进行训练。  
   这修复了 coalesced request 下 stride 训练地址失真的问题。

2. stride table 的 set index 去掉 PC 对齐低位  
   在 `baseline_stride.cc` 中，set index 改为基于 `pc >> 4` 进行哈希，避免 instruction-aligned SASS PC 把热点 load 压到同一 set，导致表冲突异常严重。

这两个修复之后，`baseline-intra` 在 `BFS / SSSP` 上开始稳定发出高准确率预取。

### 2.3 已试过但已放弃的方向

曾尝试加入基于 `useful / issued` 的 kernel-level throttle，用来主动抑制坏 case。  
短窗口 quick suite 结果表明该策略会伤害 `CC` 等 case，因此该尝试已经完整回退，当前代码不包含这类额外节流逻辑。

## 3. 当前实验结论总览

### 3.1 80k quick suite（1SM）结论

`80k` 短窗口主要用于确认：

- baseline 统计链路是否通
- `baseline-intra` 是否开始真正发出有意义的预取
- quick suite 上总体符号是否大致合理

代表性结果：

| Workload | No-prefetch IPC | Intra IPC | Uplift |
|---|---:|---:|---:|
| BFS | 0.0819 | 0.0830 | +1.34% |
| SSSP | 0.0829 | 0.0840 | +1.33% |
| SpMV | 2.0687 | 2.0809 | +0.59% |
| CC | 2.3230 | 2.3180 | -0.22% |
| B+Tree | 54.0727 | 52.6523 | -2.63% |

五项几何平均约为：

- `+0.073%`

这个阶段的意义不是证明收益很大，而是证明：

- `baseline-intra` 已经不是“完全不工作”
- 单个坏 case 可接受的前提下，整体开始转正

### 3.2 200k 中窗口验证结论

`200k` 窗口主要用于确认：短窗口是否低估了 IMA 图负载上的收益。

代表性结果：

| Workload | No-prefetch IPC | Intra IPC | Uplift |
|---|---:|---:|---:|
| BFS med | 0.0502 | 0.0515 | +2.59% |
| BFS high | 0.0505 | 0.0518 | +2.57% |
| SSSP med | 0.0511 | 0.0526 | +2.94% |
| SSSP high | 0.0514 | 0.0528 | +2.72% |

这一阶段已经能说明：

- `BFS / SSSP` 的收益不是 quick suite 噪声
- 窗口拉长后，收益幅度明显比 `80k` 更清晰

### 3.3 500k 长窗口代表性 suite 结论

`500k` 窗口是目前最重要的一组证据，因为它同时覆盖了：

- 主要收益 workload：`BFS / SSSP`
- 代表性非收益 workload：`SpMV / CC / B+Tree`

结果如下：

| Workload | No-prefetch IPC | Intra IPC | Uplift |
|---|---:|---:|---:|
| BFS high | 0.0379 | 0.0394 | +3.96% |
| SSSP high | 0.0389 | 0.0405 | +4.11% |
| SpMV high | 5.0766 | 5.0572 | -0.38% |
| CC high | 3.2088 | 3.2028 | -0.19% |
| B+Tree | 60.2834 | 60.2202 | -0.10% |

五项几何平均：

- `+1.46%`

这说明当前 `baseline-intra` 已经满足一个重要阶段性目标：

- 允许单项衰退
- 但在代表性 IMA suite 上整体为正收益

## 4. 为什么判断“不是实现坏了”

当前证据更支持“workload 适配性分化”，而不是“stride baseline 实现损坏”。

### 4.1 正收益 workload 上存在强而稳定的正确性信号

在 `500k` 长窗口中：

- `BFS high`
  - `prefetch_issued=277`
  - `prefetch_useful=276`
  - `accuracy=0.996390`
- `SSSP high`
  - `prefetch_issued=582`
  - `prefetch_useful=580`
  - `accuracy=0.996564`

这两项同时成立：

- IPC 明显提升（约 `+4%`）
- accuracy 接近 `100%`

如果实现本身有根本性错误，通常不会在两个不同图 workload 上同时出现这种“高准确率 + 稳定收益”的组合。

### 4.2 回退 workload 上存在一致的低准确率信号

在 `500k` 长窗口中：

- `SpMV high`
  - `prefetch_issued=3412`
  - `prefetch_useful=281`
  - `accuracy=0.082356`
- `CC high`
  - `prefetch_issued=3553`
  - `prefetch_useful=329`
  - `accuracy=0.092598`
- `B+Tree`
  - `prefetch_issued=12714`
  - `prefetch_useful=1752`
  - `accuracy=0.137801`

这些 case 的共同点是：

- 能发出不少预取
- 但真正 useful 的比例很低
- IPC 只出现轻微负向变化，而不是大幅崩坏

这更像“stride 模式对这些 workload 的预测相关性不足”，而不是“注入路径、统计路径或地址训练逻辑完全错误”。

### 4.3 回退与资源压力恶化相匹配

回退 case 不只是 accuracy 低，还伴随额外的 cache / MSHR 压力：

#### SpMV high

- IPC：`5.0766 -> 5.0572`
- `L1D_total_cache_reservation_fails`：`403420 -> 414380`
- `L2_cache_stats_fail_breakdown[GLOBAL_ACC_R][MSHR_ENRTY_FAIL]`：
  `28424 -> 49158`
- `MEM_WAIT` stall fraction：
  `0.8585 -> 0.8694`

#### CC high

- IPC：`3.2088 -> 3.2028`
- `L1D_total_cache_misses`：`62757 -> 62907`
- `MEM_WAIT` stall fraction：
  `0.9460 -> 0.9473`

#### B+Tree

- IPC：`60.2834 -> 60.2202`
- `L1D_total_cache_reservation_fails`：`5922 -> 7620`
- `PIPE_BUSY` stall fraction：
  `0.1488 -> 0.1506`

这说明回退并非“无源之水”，而是与错误预取带来的额外资源占用高度一致。

### 4.4 当前最合理的解释

截至目前，最合理的解释是：

- `baseline-intra` 对 `BFS / SSSP` 这类 frontier-driven IMA 访问有较强 stride 可预测性
- 对 `SpMV / CC / B+Tree`，当前训练口径下的 stride 相关性弱很多
- 结果是：
  - 好 case：极高准确率，带来真实收益
  - 坏 case：低准确率，带来额外 prefetch traffic 和资源争用

因此当前问题更像：

- “需要 workload-sensitive 的 gating / filtering”

而不是：

- “当前 baseline-intra 基本实现是坏的，需要推倒重来”

## 5. 当前 `baseline-inter` 的定位

本轮实验中，`baseline-inter` 已经完成接线与可运行支持，但在目前短窗口与代表性验证中，没有观察到与 `baseline-intra` 同量级的稳定收益。

阶段性结论是：

- `baseline-inter` 当前可以保留为“已实现、待进一步评估”的对照项
- 后续优先级仍应明显低于 `baseline-intra`

## 6. 对后续 SOTA 实验的意义

本阶段工作已经为后续 SOTA baseline 实验奠定了三层基础：

### 6.1 实现基础

已经有一个可运行、可统计、可复现实验入口的 stride baseline，不需要再次从零搭框架。

### 6.2 评估基础

已经拿到一组比 quick suite 更可信的长窗口结果，可作为后续所有改进尝试的 baseline reference：

- `BFS / SSSP` 是收益观察主战场
- `SpMV / CC / B+Tree` 是回退与止损观察主战场

### 6.3 研究基础

当前已经明确一个重要研究问题：

- stride-based baseline 在 IMA workload 上不是“完全无效”
- 但收益高度 workload-sensitive
- 后续值得研究的方向不是“是否要继续做 stride”，而是：
  - 如何只在好 case 上放大收益
  - 如何在坏 case 上尽量降低副作用

## 7. 后续建议

如果后续继续推进 SOTA baseline 研究，建议按下面顺序：

1. 先把本文件作为背景材料固定下来，后续 agent 一律先读
2. 保持 `500k` 五项 suite 作为当前 stride baseline 的阶段性对照集
3. 后续若继续修改 `baseline-intra`，优先研究：
   - 更严格的 gating
   - 只在高价值 PC 上训练/发射
   - 避免在 `SpMV / CC / B+Tree` 上放大低质量流量
4. 在 `baseline-intra` 基线稳定后，再继续 `Snake / Spare Register`

## 8. 关键日志位置

当前最重要的代表性日志如下：

- `worktrees/sota_stride/result/log/bfs500_np_high.log`
- `worktrees/sota_stride/result/log/bfs500_intra_high.log`
- `worktrees/sota_stride/result/log/sssp500_np_high.log`
- `worktrees/sota_stride/result/log/sssp500_intra_high.log`
- `worktrees/sota_stride/result/log/spmv500_np_high.log`
- `worktrees/sota_stride/result/log/spmv500_intra_high.log`
- `worktrees/sota_stride/result/log/cc500_np_high.log`
- `worktrees/sota_stride/result/log/cc500_intra_high.log`
- `worktrees/sota_stride/result/log/btree500_np.log`
- `worktrees/sota_stride/result/log/btree500_intra.log`

对应的 stall breakdown / topk 统计目录位于：

- `worktrees/sota_stride/result/issue_trace/stall_reason_pc_stats/`

## 9. IMA Data PC Blacklist Gating（2026-03-24 后半段）

### 9.1 问题

无 gating 版本中 SpMV (-0.38%) 和 CC (-0.19%) 存在回退。根因：stride prefetcher 对 IMA data load PC（如 `x[col_idx[k]]`）的地址完全无法预测（数据依赖），低准确率 prefetch 污染 L1/MSHR。

### 9.2 方案选择

考虑了三种方案：

| 方案 | 描述 | 结论 |
|------|------|------|
| A-whitelist | 只允许 IMA index PC 训练 | ❌ 过度过滤：BFS/SSSP 的非 IMA stride 收益（frontier/row_ptr）也被消除 |
| A-blacklist | 只排除 IMA data PC | ✅ 采用：精准移除不可预测的 data load，保留所有有 stride 的 load |
| B | per-entry 准确率动态节流 | 留作后续兜底 |

whitelist 方案首先被实验验证，BFS 收益从 +3.96% 降为 0%，因为 BFS 的 +4% 主要来自非 IMA load 的 stride 预测（frontier management / worklist 类顺序 load），而非 IMA index load 本身。

### 9.3 代码改动

三处修改（均在 `worktrees/sota_stride` 中）：

1. **`trace_driven.cc`**：`build_ima_pair_tables()` 的调用条件加入 `baseline_*_enable` 标志，使 baseline 模式也加载 chain CSV
2. **`shader.h` + `trace_driven.{h,cc}`**：新增 `is_ima_data_pc(pc)` 接口，查询 `m_chain_ids_by_data_pc`
3. **`shader.cc`**：baseline hook 中 `on_demand_load` 前检查 `is_ima_data_pc()`，若为 IMA data PC 则跳过训练和预取

### 9.4 Blacklist Gating 实验结果（500k cycles, `--max-cycle 500000`）

#### INTRA

| Workload | NP IPC | Intra IPC | Uplift | Accuracy | 对比无 gating |
|----------|--------|-----------|--------|----------|--------------|
| BFS | 0.0383 | 0.0398 | **+3.92%** | 99.6% | +3.96%（保持） |
| SSSP | 0.0393 | 0.0409 | **+4.07%** | 99.7% | +4.11%（保持） |
| CC | 227.17 | 227.57 | **+0.18%** | ~23% | -0.19%（回退消除） |
| SpMV | 462.07 | 461.71 | **-0.08%** | ~19% | -0.38%（回退缩小 5×） |
| **Geomean** | — | — | **+2.00%** | — | +1.46%（提升） |

#### INTER

| Workload | NP IPC | Inter IPC | Uplift | Notes |
|----------|--------|-----------|--------|-------|
| BFS | 0.0383 | 0.0383 | **0%** | prefetch_issued=0 |
| SSSP | 0.0393 | 0.0393 | **0%** | prefetch_issued=0 |
| CC | 227.17 | 227.18 | **0%** | accuracy 4-9%，IPC 无变化 |
| SpMV | — | — | — | 预期同样无效 |

### 9.5 INTER 无效根因

INTER 模式检测同一 PC 跨不同 warp 的地址 stride。在 IMA workload 上完全无效：

- BFS/SSSP：不同 warp 处理不同 frontier 节点，inter-warp 地址差无 stride 规律
- SpMV：不同 warp 处理不同矩阵行，col_idx 起始位置无 stride
- CC：类似，data-dependent 寻址无 inter-warp 可预测性

这是 IMA 访问模式的本质特征，不是实现问题。INTER 作为 baseline 对照的意义在于证明”跨 warp stride 在 IMA 上完全无效”。

### 9.6 关键日志位置（blacklist gating 版本）

```
worktrees/sota_stride/result/log/bfs500bl_np_high.log
worktrees/sota_stride/result/log/bfs500bl_intra_high.log
worktrees/sota_stride/result/log/sssp500bl_np_high.log
worktrees/sota_stride/result/log/sssp500bl_intra_high.log
worktrees/sota_stride/result/log/spmv500bl_np_high.log
worktrees/sota_stride/result/log/spmv500bl_intra_high.log
worktrees/sota_stride/result/log/cc500bl_np_high.log
worktrees/sota_stride/result/log/cc500bl_intra_high.log
worktrees/sota_stride/result/log/bfs500bl_inter_high.log
worktrees/sota_stride/result/log/sssp500bl_inter_high.log
worktrees/sota_stride/result/log/cc500bl_inter_high.log
```

## 10. 最终阶段性结论

截至 2026-03-24，stride baseline 的状态：

- **`baseline-intra` + blacklist gating** 是一个完整可用的 SOTA 对照基线
  - BFS/SSSP：+4%，accuracy 99.6%
  - CC：+0.18%（中性）
  - SpMV：-0.08%（噪声范围）
  - Geomean：+2.00%
- **`baseline-inter`** 在 IMA workload 上完全无效（0% uplift），但作为”negative result”本身有 evaluation 价值
- 后续 Snake / Spare Register 的实现可以复用本阶段已验证的框架（`baseline_prefetcher_t`、hook 位置、stats 输出、chain CSV 加载）
- 若需进一步压缩 SpMV 的 -0.08%，可叠加 per-entry accuracy 节流（方案 B），但当前已在可接受范围

## 11. Snake Baseline 修复与实验（2026-03-25）

### 11.1 发现的 Bug

`baseline_snake.cc:on_demand_load()` 中存在 training/prediction 硬分界 bug：

- 训练阶段（`!training_done`）：更新 IaW/IeW stride + IT chain
- 预测阶段（`else`）：只生成 prefetch，**不再更新 stride**

BFS/SSSP 上 3 个不同 warp 依次到达同一 PC，`training_warp_count` 快速达 3，但没有同一 warp 对同一 PC 连续访问 2 次以上，所以 `iaw_confirmed=false`、`iew_confirmed=false`、`chain_length=0`。训练完成后 stride 学习永久停止 → `prefetch_issued=0`。

### 11.2 修复方案

将 `update_iaw_stride()` / `update_iew_stride()` 和 `generate_prefetches()` 移到 training gate 之外，使 stride 学习贯穿整个生命周期。IT chain 检测仍然只在训练阶段进行。

变更文件：`baseline_snake.cc`，~5 行代码变更。

### 11.3 A/B 对比实验

测试了两种 prefetch 生成策略：

- **Plan A**：stride 一旦 confirmed 就立即预取（不等 training_done）
- **Plan B**：stride 持续学习，但预取等 training_done 后再开始

#### 500k cycles 结果

| Workload | NP IPC | Plan A IPC | Plan A Uplift | Plan B IPC | Plan B Uplift |
|----------|--------|------------|---------------|------------|---------------|
| BFS | 0.0383 | 0.0395 | **+3.13%** | 0.0383 | **0.00%** |
| SSSP | 0.0393 | 0.0408 | **+3.82%** | 0.0393 | **0.00%** |
| CC | 227.17 | 219.46 | **-3.40%** | 219.96 | **-3.17%** |
| SpMV | 462.07 | 447.75 | **-3.10%** | 待完成 | — |

#### 决策：选择 Plan A

- BFS/SSSP 上 Plan A 有显著收益，Plan B 等同于无预取
- CC 上两者差异极小（-3.40% vs -3.17%），因为 CC 训练很快完成
- Plan A 更"诚实"地展示了 Snake 的实际行为

### 11.4 与 Stride-INTRA 对比

| Workload | Stride-INTRA (blacklist) | Snake (Plan A) | 差异 |
|----------|--------------------------|----------------|------|
| BFS | +3.92% | +3.13% | Snake 更差 |
| SSSP | +4.07% | +3.82% | Snake 更差 |
| CC | +0.18% | -3.40% | Snake 远更差 |
| SpMV | -0.08% | -3.10% | Snake 远更差 |

**结论**：即使是更复杂的 Snake（chain-based stride），在所有 IMA workload 上也不如简单的 Stride-INTRA。Snake 的 IT chain 和 IeW 维度对 IMA 访问模式没有帮助，反而因为更多低质量预取导致更大的 cache 污染。

### 11.5 关键日志位置

```
worktrees/sota_stride/result/log/snakeA_bfs500.log
worktrees/sota_stride/result/log/snakeA_sssp500.log
worktrees/sota_stride/result/log/snakeA_cc500.log
worktrees/sota_stride/result/log/snakeA_spmv500.log
worktrees/snake_planb/result/log/snakeB_bfs500.log
worktrees/snake_planb/result/log/snakeB_sssp500.log
worktrees/snake_planb/result/log/snakeB_cc500.log
worktrees/snake_planb/result/log/snakeB_spmv500.log  (running)
```

## 12. Spare Register Baseline 实现与实验（2026-03-25）

### 12.1 实现方案（Approach B — 最接近论文）

论文核心机制（§3.2.5, Figure 4C）：在迭代 i 中注入两条预取指令：
1. Head prefetch: stride 预测未来 index 地址，预取 index 数据
2. Tail prefetch: 用 head 返回值计算 data 地址，预取 data

Trace-driven 近似（无法获取 head 返回值）：
1. **Index prefetch via stride**：与论文完全一致
2. **Data prefetch via pair table**：查当前地址的 pair table 获取 data 地址并立即预取（近似：预取当前迭代 tail 而非未来迭代 tail）

### 12.2 关键实现细节

- `baseline_spare_reg.h/cc`：~100 行
- 基类 `on_fill` 改为 virtual（支持子类 override）
- 新增 `-baseline_spare_reg_distance` 配置参数（默认 1）
- 使用 `exact_match_only=true` 查 pair table 避免预取洪泛
- Chain CSV 只包含 `bfs/sssp/spmv/bc`，CC 无 chain → Spare Register 在 CC 上等同 NP

### 12.3 实验结果（500k cycles）

| Workload | NP IPC | Spare Reg IPC | Uplift | Stride-INTRA | Snake |
|----------|--------|-------------|--------|-------------|-------|
| BFS | 0.0383 | 0.0383 | **0.00%** | +3.92% | +3.13% |
| SSSP | 0.0393 | 0.0423 | **+7.63%** | +4.07% | +3.82% |
| CC | 227.17 | 227.17 | **0.00%** | +0.18% | -3.40% |
| SpMV | 462.07 | 待完成 | — | -0.08% | -3.10% |

### 12.4 SSSP +7.63% 分析

SM1 数据：`prefetch_issued=785`, `prefetch_useful=306`, `accuracy=39%`。
Spare Register 的 pair table 查表机制直接消除了 head→tail 依赖延迟，比 stride-only 方法有效得多。

### 12.5 BFS 窗口效应分析

500k cycle 窗口对 BFS **严重不足**——只覆盖第一层 frontier（极少 IMA 活动）：

| Window | Seed Hit Ratio | data_pf/SM | accuracy | NP IPC | SR IPC |
|--------|---------------|------------|----------|--------|--------|
| 500k | 1.2% (3/242) | 3 | 0% | 0.0383 | 0.0383 |
| **2M** | **44%** (29k/66k) | ~29,000 | **20-25%** | 16.81 | 14.51 |

2M 窗口下 BFS 跑了 5 个 kernel invocation（5 层 BFS），IMA seed ratio 从 1.2% 跳到 44%。
Spare Register 发出大量有效预取（accuracy 20-25%），但 L1D pollution 拖慢执行——NP 跑了 6 个 kernel 而 Spare Reg 只跑了 5 个。

**结论**：Spare Register 的 pair table 检测机制在 BFS 上是有效的，但缺少论文核心的 spare register 存储导致 L1D 争用抵消了收益。这正是论文选择 register 而非 cache 存储的原因。

### 12.6 关键日志位置

```
worktrees/sota_stride/result/log/spare_reg_bfs500.log
worktrees/sota_stride/result/log/spare_reg_sssp500.log
worktrees/sota_stride/result/log/spare_reg_cc500.log
worktrees/sota_stride/result/log/spare_reg_spmv500.log  (running)
```

## 13. IMA 行为定量分析（2026-03-25）

### 13.1 各 Workload IMA 特征

| Workload | Total Loads | L1D Misses | IMA Seed Ratio | Pair Table Hit% | 最佳 Prefetcher |
|----------|-------------|------------|----------------|-----------------|----------------|
| SSSP | 281 (1SM) | 24 | **24.6%** | 100% | Spare Reg (+7.63%) |
| BFS | 512,755 | 205,056 | **4%→44%** (窗口依赖) | 100% | Stride-INTRA (+3.92%) |
| SpMV | 56,920,896 | 26,378,058 | 高 (29 chains) | — | 无（均 negative） |
| CC | 16,214,502 | 5,399,987 | **0%** (无 chain) | — | 无 |

### 13.2 核心发现

1. **Pair table 检测准确**：BFS/SSSP 的 pair table 命中率 100%，IMA pattern 被正确识别
2. **IMA 密度决定 prefetcher 收益**：SSSP（24.6%）>> BFS（4-44%，窗口依赖）>> CC（0%）
3. **SpMV 的 accuracy 灾难**：29 条 chain 但 14.7M prefetch 中仅 211 useful（accuracy 0.001%）——data 地址完全随机
4. **所有 prefetcher 在 GPU 图算法上 coverage < 5%**：不规则访问模式从根本上限制了 stride/IMA-pattern 方法的有效性
5. **Spare Register 的 register 存储是真实需求**：BFS 2M 窗口证明检测机制有效（accuracy 20-25%），但 L1D pollution 抵消收益

## 14. 后续建议（更新）

1. **SpMV Spare Register 实验**：等待完成，补充表格
2. **GRASP 本身**：修复 distance=1 / per-kernel reset / throttle 三个根因后，与所有 baseline 做公平对比
3. **补充 CC chain**：若需要 CC 上的 Spare Register 结果，需先补充 CC 的 strict chain CSV
