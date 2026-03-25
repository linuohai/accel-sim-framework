# GRASP Prefetcher 实验进度记录

> **目的**：本文档作为跨 Agent 窗口的交接文档，记录每次实验的配置、结果和发现。
>
> 最近更新：2026-03-24

---

## 1. 当前状态总结

**Phase A/B**：核心组件实现完成，编译通过。
**Phase C**（验证）：功能验证已完成，性能评估首轮完成。
**Phase D**（优化）：未开始。

### 关键发现

GRASP 管线**功能正确**（CD 检测链、CT 学 stride、INDEX/DATA_PF 生成并发往 L1D），但**首轮实验 IPC 无提升**。根因分析如下。

---

## 2. 实验配置

### 2.1 运行方式

```bash
# 基线
./traceL1 --max-completed-cta <N> <trace_key> <log_name>

# GRASP
./traceL1 --grasp --max-completed-cta <N> <trace_key> <log_name>

# GRASP + debug
./traceL1 --grasp --grasp-debug --max-completed-cta <N> <trace_key> <log_name>
```

### 2.2 默认 GRASP 参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `grasp_cd_fifo_depth` | 20 | CD FIFO 深度 |
| `grasp_ct_size` | 32 | CT 条目数 |
| `grasp_tt_size` | 8 | TT 条目数 |
| `grasp_ist_distance` | 1 | 预取步长 |
| `grasp_prb_capacity` | 1024 | PRB 容量 |
| `grasp_tc_mshr_threshold` | 80 | TC 阈值（未实现） |
| chain CSV | `tmp/strict_chains/strict_selected_chain_instances.csv` | 默认 |

### 2.3 chain CSV 覆盖范围

| 算法 | impl | 有 chain 数据 |
|------|------|:----------:|
| spmv | base | ✓ |
| bfs | linear_base | ✓ |
| sssp | linear_base | ✓ |
| bc | linear_base | ✓ |
| cc | base | ✗ |

---

## 3. 首轮实验结果 (2026-03-24)

### 3.1 IPC 对比

| Workload | CTA限制 | Baseline IPC | GRASP IPC | Delta | GRASP是否激活 | 备注 |
|----------|---------|-------------|-----------|-------|:------------:|------|
| spmv_ima_high | 100 | 557.73 | 555.11 | **-0.47%** | ✓ 活跃 | 单 kernel，充分训练 |
| sssp_ima_high | 100 | 0.0336 | 0.0336 | **0%** | ✗ (k2) / ✓ (k3+) | 多 kernel，k2 无活动 |
| bfs_ima_high | 50 | 0.3313 | 0.3313 | **0%** | ✗ (k1-2) / ✓ (k3) | 多 kernel，k3 有链但无 PF |
| bc_ima_high | 100 | 418.64 | 418.64 | **0%** | ✗ | 两者都在 k1 crash |

### 3.2 SpMV 详细 L1D 分析（唯一 GRASP 活跃的可比工作负载）

#### 3.2.1 GRASP 管线活动（所有 SM 聚合）

| 指标 | 值 |
|------|-----|
| CD 检测链数（总） | 702 |
| 活跃 SM 数 | 58 / 108 |
| INDEX_PF: issued(miss) / hit / rfail | 14,586 / 8,789 / 3,242 |
| DATA_PF: issued(miss) / hit / rfail | 23,243 / 28,388 / 5,096 |
| Pair table: hit / miss | 24,834 / 3,283 |
| Queue peak (max across SMs) | 4,141 |
| PF 总 L1D 访问数 | 83,344 |

#### 3.2.2 分离 demand vs prefetch 对 L1D 的影响

| L1D 结果 | Baseline | GRASP total | PF 部分 | Demand (GRASP) | Demand delta |
|----------|---------|------------|---------|---------------|-------------|
| **HIT** | 142,579 | 180,399 | 37,177 | 143,222 | **+643** |
| **HIT_RESERVED** | 107,143 | 131,326 | 0 | 131,326 | **+24,183** |
| **MISS+SECTOR_MISS** | 619,665 | 634,299 | 37,829 | 596,470 | **-23,195** |
| **RESERVATION_FAIL** | 3,007,127 | 3,034,686 | 8,338 | 3,026,348 | +19,221 |

#### 3.2.3 根因解读

1. **预取有效获取数据**：37,829 次 PF MISS 从 L2 取回了新数据 ✓
2. **但 demand load HIT 仅增加 643 次**：37,829 次 PF fetch 中仅 1.7% 在 demand load 到达前完成 ✗
3. **24,183 次 demand load 变成 HIT_RESERVED**：说明 PF 刚发出请求（MSHR 已分配），demand load 随后到达并合并进同一 MSHR entry。两者在**同一时间竞速**，PF 没有时间优势
4. **23,195 次 demand MISS 减少**：这些前 MISS 变成了 HIT_RESERVED（不是 HIT！），对延迟**无改善**

**结论**：distance=1 导致预取和 demand load 几乎同时竞争同一地址。预取需要更大的 lookahead 才能在 demand load 到达前完成 L2 round trip（~200 cycle）。

---

## 4. 根因分析

### 4.1 根因 A：预取不及时 (distance=1 太小)

**影响**：SpMV IPC -0.47%

当前 `ist_distance=1`，预取 `addr + 1 * stride`（下一次迭代的地址）。但 demand load 在下一次迭代立即发出，仅晚几个 cycle。预取的 L2 round trip 需要 ~200 cycle，来不及在 demand load 之前完成。

**证据**：
- 37,829 次 PF MISS → 只产生 643 次 demand HIT（1.7% 覆盖率）
- 24,183 次 demand 变成 HIT_RESERVED = PF 和 demand 竞速，PF 仅略快（MSHR 刚分配）

**修复方案**：增加 `ist_distance` 到 3-5，使预取在当前迭代就预测 3-5 次迭代后的地址，给预取足够的 L2 latency hiding 时间。

### 4.2 根因 B：per-kernel reset 破坏多 kernel 工作负载的训练

**影响**：BFS、SSSP、BC 完全无效

BFS/SSSP 的每个 BFS level / Bellman-Ford iteration 是独立的 kernel launch。`on_kernel_launch()` 清空所有 GRASP 状态（CD、CT、TT、PRB、queue）。导致：

1. Kernel N 启动 → CD 开始检测链 → CT 插入 → stride 开始训练
2. Kernel N 结束（通常很短，仅几千 cycle）
3. Kernel N+1 启动 → **全部清空** → 从零开始
4. 如此反复，stride 永远无法收敛

**证据**：
- BFS kernel 3：CD 检测 208 链，CT peak_occ=6，但 `all_stride_valid=no`，`idx_pf issued=0`
- SSSP kernel 2（827K cycles）：CD 0 链（第一个 kernel 太早？）
- SSSP kernel 3-4：CD 活跃 + PF 发出（但 IPC 对比的是 kernel 2，故看不到效果）

**修复方案**：对同一 kernel function 的重复 launch，保留 CT stride 信息（跨 kernel 持久化）。至少保留 `stride_valid` 和 `iter_stride`，因为 IMA 的 stride pattern 在不同 kernel launch 间是稳定的。

### 4.3 根因 C：无 Throttle Control

**影响**：MSHR 拥塞环境下 PF 加重负担

SpMV 的 MSHR_ENTRY_FAIL 为 290 万次，说明 MSHR 已完全饱和。此时 PF 的 MISS（37,829 次）占用额外 MSHR entries，挤压 demand load。

**证据**：GRASP 运行后 RFAIL 增加 27,559 次（+0.9%），表明 demand load 获取 MSHR 更难。

**修复方案**：实现 `TODO(human)` 的 MSHR 占用率检查，当 MSHR 占用超过阈值时抑制 DATA_PF。

---

## 5. 下一步行动

### 5.1 高优先级

| # | 行动 | 预期效果 | 复杂度 |
|---|------|---------|--------|
| 1 | **增加 `ist_distance` 到 3-5** | 预取提前 3-5 次迭代，覆盖 L2 latency | 改 1 个配置值 |
| 2 | **CT stride 跨 kernel 持久化** | BFS/SSSP/BC 不再因 kernel 重启丢失训练 | 修改 `on_kernel_launch()` 逻辑 |
| 3 | **实现 Throttle Control** | 减少 MSHR 拥塞时的无效 PF | 实现 `TODO(human)` |

### 5.2 验证计划

1. 修复后重跑 spmv_ima_high (distance=3)，期望 demand HIT 从 643 → 数千以上
2. 修复后重跑 sssp_ima_high（跨 kernel 持久化），期望 kernel 2 也有 PF 活动
3. 对比 IPC 提升与 ideal L1D 的上界

---

## 6. 已知问题

| 问题 | 状态 | 说明 |
|------|------|------|
| `warp_traces.size() > 0` 断言失败 | **Pre-existing** | BFS/BC `--max-completed-cta` 模式下 CTA 回收时触发。非 GRASP bug |
| `miss` 统计字段永远为 0 | Cosmetic | `index_pf_miss` / `data_pf_miss` 未被任何代码路径赋值，可移除 |
| `warp_exits=0` 在所有 SM | Needs investigation | tracked warp 退出事件未被记录，可能 hook 位置不对 |

---

## 7. 日志文件索引

| 日志 | 说明 |
|------|------|
| `result/log/spmv_baseline.log` | SpMV 基线 (100 CTA) |
| `result/log/spmv_grasp.log` | SpMV GRASP (100 CTA) |
| `result/log/sssp_baseline.log` | SSSP 基线 (100 CTA) |
| `result/log/sssp_grasp.log` | SSSP GRASP (100 CTA) |
| `result/log/bfs_baseline.log` | BFS 基线 (50 CTA) |
| `result/log/bfs_grasp.log` | BFS GRASP (50 CTA) |
| `result/log/bc_baseline.log` | BC 基线 (100 CTA, crashed) |
| `result/log/bc_grasp.log` | BC GRASP (100 CTA, crashed) |
| `result/log/grasp_stats_test2.log` | bfs_ima_small GRASP debug (50 CTA) |
