> 最近更新: 2026-04-07

# GRASP Bottleneck Analysis — No-Throttle 实验结果

## 0. 实验目标与方法

### 0.1 动机

GRASP 默认配置中存在两类**自愿过滤**机制，掩盖了两级流水线 (IPU → DPU) 的真实性能上限：

1. **Throttle Control (TC)**：`tc_mode=5` 基于滑动窗口 accuracy 反馈动态抑制 DATA_PF
2. **L1 Reservation Fail drop**：当 L1 cache 返回 RESERVATION_FAIL（MSHR 满 / line alloc fail），prefetch 被永久丢弃

这使得我们看到的 "`data_pf_issued` 远小于 `ima_data_reads`" 无法区分两类瓶颈：
- **Generation gap**：GRASP 没有及时生成足够的 prefetch（chain detection / pair table / timing）
- **L1 back-pressure**：生成了但 L1 拒收（MSHR / 线分配资源不足）

### 0.2 No-Throttle 模式

通过 `-grasp_no_throttle 1` 开启，行为：
- 完全跳过 `inject_prefetch()` 的 TC gate（`throttle_suppressed` 恒为 0）
- L1 RESERVATION_FAIL 时把请求重新入队（next cycle 重试），而不是 drop
- Safety cap: `m_prefetch_queue.size() < 16384` 防止极端 workload 下队列爆炸

代码位置：
- `grasp_prefetcher.h`: `bool no_throttle = false`（grasp_config_t）
- `grasp_prefetcher.cc:722`: TC gate 加 `&& !m_cfg.no_throttle`
- `grasp_prefetcher.cc:984-1014`: rfail 重入队块

### 0.3 新增计数器与输出

`GRASP_BOTTLENECK SM%u:` 行（每 SM 一条，跨 SM 由 traceL1 自动聚合到 EXPERIMENT SUMMARY）：

| 字段 | 含义 | 来源 |
|------|------|------|
| `idx_theory` | 理论上可预取的全部 IMAD index demand loads | `ima_demand_breakdown_t.idx_reads` |
| `idx_generated` | IPU 生成的 IST 预取数 | `ist_prefetch_generated` |
| `idx_accepted` | L1 实际接收的 INDEX_PF | `index_pf_hit + index_pf_mshr_merge + index_pf_issued` |
| `idx_rfail` | L1 reservation fail 累计 | `index_pf_reservation_fail` |
| `idx_retried` | 其中被 retry 的次数 | `index_pf_rfail_retried`（仅 no_throttle=1） |
| `data_theory` | 理论上可预取的全部 IMAD data demand loads | `ima_demand_breakdown_t.data_reads` |
| `data_enqueued` | DPU 在 PRB sector 释放时入队的 DATA_PF | `data_pf_enqueued` |
| `data_accepted` | L1 实际接收的 DATA_PF | `data_pf_hit + data_pf_mshr_merge + data_pf_issued` |
| `data_rfail` | DATA_PF reservation fail 累计 | `data_pf_reservation_fail` |
| `data_retried` | 其中被 retry 的次数 | `data_pf_rfail_retried` |
| `tc_suppressed` | DATA_PF 被 TC 抑制次数 | `throttle_suppressed`（no_throttle=1 时恒 0） |

### 0.4 测例清单（14 workloads，≤4h on full SM）

```
bfs_cit_dir          12 min       sssp_road_sym        1.8 h
sssp_cit_dir         13 min       cc_road_sym          2.3 h
spmv_road_sym        27 min       spmv_flickr_sym      2.3 h
spmv_web_sym         1.2 h        bfs_web_sym          2.6 h
bfs_road_sym         1.7 h        bfs_flickr_sym       3.0 h
                                  bc_road_sym          3.7 h
                                  sssp_flickr_sym      4.0 h
                                  cc_flickr_sym        4.0 h
                                  sssp_web_sym         4.1 h
```

排除（>4h）：bc_web_sym, cc_web_sym, bc_flickr_sym, vc_web_sym, vc_cit_sym, spmv_cit_sym, bfs_socLJ_sym, spmv_socLJ_sym

## 1. 结果（待填）

### 1.1 总览表

| Workload | IPC (default) | IPC (no_throttle) | Δ% | idx_theory | idx_accepted | idx_acc% | data_theory | data_accepted | data_acc% | idx_retried | data_retried |
|----------|---------------|-------------------|-----|------------|---------------|----------|-------------|----------------|-----------|-------------|--------------|
| bfs_cit_dir | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| sssp_cit_dir | ... | | | | | | | | | | |

### 1.2 Stage 1 (IPU) 瓶颈分解

每个 workload 计算：
- `idx_lost_total = idx_theory - idx_accepted`
- `idx_lost_generation = idx_theory - idx_generated`（GRASP 没有及时生成 → CT/IST 阶段瓶颈）
- `idx_lost_backpressure = idx_generated - idx_accepted`（L1 拒收 → MSHR/资源瓶颈）

### 1.3 Stage 2 (DPU) 瓶颈分解

类似：
- `data_lost_total = data_theory - data_accepted`
- `data_lost_generation = data_theory - data_enqueued`（pair table miss / index 未及时返回）
- `data_lost_backpressure = data_enqueued - data_accepted`（L1 拒收）

### 1.4 三类瓶颈相对贡献

按 workload 计算：
- A. Chain detection / IST coverage gap (Stage 1 generation)
- B. Pair table coverage gap (Stage 2 generation, idx returned but no data addr)
- C. L1 back-pressure (both stages combined back-pressure)

## 2. 结论（待填）

待 14 workloads 全部完成后填写。

## 3. 与已有 baseline 对比

数据源：
- Default GRASP 数据来自 `experiment_results.md`
- T40C200 / D5b 数据来自 `throttle_control_results.md`
- No-throttle 数据来自本文档 §1.1

预期解读：
- 若 `no_throttle IPC > T40C200 IPC`：rfail drop 在浪费机会，瓶颈在 L1 back-pressure
- 若 `no_throttle IPC ≈ T40C200 IPC`：rfail 很少，瓶颈在 generation 阶段
- 若 `no_throttle IPC < T40C200 IPC`：retry 反而污染 L1，TC 策略是正确的
