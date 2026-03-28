# GRASP Prefetcher Metrics Framework

> **状态**：已实现，通过 SSSP / tiny_case 验证
>
> **代码位置**：`gpu-simulator/gpgpu-sim/src/gpgpu-sim/grasp_prefetcher.{h,cc}`, `gpu-cache.{h,cc}`, `shader.cc`
>
> **最近更新**：2026-03-27

---

## 1. 概述

为 GRASP 添加三层评估指标，使性能分析从"看原始计数器猜原因"进化到"看标准化指标定位瓶颈"。

**新增输出**（在每个 SM 的 stats dump 中追加三行）：

```
GRASP_DEMAND SM%u: global_reads=... global_misses=... ct_loads=... ct_misses=... ct_hits=... demand_hit_pf=...
GRASP_METRICS SM%u: coverage=... accuracy=... timeliness=...
GRASP_QUALITY SM%u: ct_chain_cov=...(=.../...) ct_util=... prb_util=... eff_pf=... avg_stride_obs=... stride_reconverge=... coalesce=... throttle=... pf_rfail_rate=...
```

---

## 2. 指标定义

### 2.1 标准预取指标（A 层）

| 指标 | 公式 | 含义 |
|------|------|------|
| **Coverage** | `demand_hit_pf / (demand_hit_pf + global_misses)` | prefetch 消除的 miss 占"本应 miss 总量"的比例。越高越好。 |
| **Accuracy** | `demand_hit_pf / total_pf_issued` | 发出的 prefetch 中有多少被后续 demand load 用上。越高说明浪费越少。 |
| **Timeliness** | `demand_hit_pf / (demand_hit_pf + pf_late)` | 有用 prefetch 中及时到达的比例。`pf_late ≈ index_pf_mshr_merge + data_pf_mshr_merge`（prefetch 到达时发现已有 in-flight demand，说明晚了）。 |

> **⚠ Timeliness 当前实现是近似值，已知局限**：
>
> - `mshr_merge` 不一定代表 "demand 先于 prefetch"——也可能是两个 prefetch 之间的 merge，或 demand 与 prefetch 几乎同时到达
> - SSSP 上 timeliness=1.0（mshr_merge=0），说明该指标在当前 workload 上缺乏区分力
> - **改进方向**：在 cache block 的 `m_prefetched` 标记旁新增 `m_prefetch_fill_cycle` 字段，demand HIT 时计算 `demand_cycle - fill_cycle`，报告延迟分布（histogram 或平均值）。这是 CPU prefetcher 文献中更标准的 timeliness 度量方式（Jain & Lin 2013 等）
> - **暂不修改**：待项目结构重构完成后再细化

**Coverage × Accuracy 联合解读**：

| Coverage | Accuracy | 诊断 |
|----------|----------|------|
| 高 | 高 | 理想状态 |
| 高 | 低 | 有效但浪费带宽（大量无用 PF，需 throttle） |
| 低 | 高 | 精准但覆盖不足（stride/distance 太保守） |
| 低 | 低 | 根本性问题（stride 学错、pair table miss 多） |

### 2.2 GRASP 结构指标（B 层）

| 指标 | 公式 | 含义 |
|------|------|------|
| **ct_chain_cov** | `ct_valid_entries / cd_unique_pcs` | CD 发现的链中最终存活在 CT 中的比例。< 1.0 说明 CT 容量不足导致链被淘汰。用于 **硬件 sizing**。 |
| **avg_stride_obs** | `Σ(demand_before_converge) / converge_count` | stride 收敛前平均需要多少次 demand load。值越小说明训练越快。 |
| **stride_reconverge** | 收敛后又被推翻的次数 | **Sanity check**。期望恒为 0。非零说明 stride 不稳定。 |
| **eff_pf** | `demand_hit_pf / total_pf_issued` | 等价于 accuracy（同一个值）。 |

### 2.3 资源指标（C 层）

| 指标 | 公式 | 含义 |
|------|------|------|
| **ct_util** | `ct_peak_occ / ct_size` | CT 峰值利用率。用于 **硬件 sizing**：决定最终部署需要多大的 CT。 |
| **prb_util** | `prb_peak_occ / prb_capacity` | PRB 峰值利用率。用于 **硬件 sizing**：决定最终部署需要多大的 PRB。 |
| **coalesce** | DATA_PF 被合并的次数 | 观察同一 cache line 的多个 target 合并程度。 |
| **pf_rfail_rate** | `total_rfail / (total_pf + total_rfail)` | prefetch 因 MSHR/miss queue 满被丢弃的比例。高值说明 MSHR 争用严重。 |

---

## 3. 实现方式

### 3.1 demand_hit_pf 的检测机制

在 `cache_block_t` 层级新增 `m_prefetched` 标记位：

1. **标记**：`baseline_cache::fill()` 中，若 `mf->is_ima_prefetch()` 为 true，对填入的 cache block 设置 `set_prefetched(true, sector_mask)`
2. **检测**：`data_cache::rd_hit_base()` 中，demand load HIT 时检查 `block->is_prefetched(sector_mask)`，若 true 则 `tag_array.inc_demand_hit_prefetch()` 并清除标记
3. **读取**：GRASP 持有 L1D 指针（`m_l1d`），在 `print_stats()` 时通过 `m_l1d->get_demand_hit_prefetch()` 读取

`m_prefetched` 对 `line_cache_block` 是单个 bool；对 `sector_cache_block` 是 `bool[SECTOR_CHUNCK_SIZE]` 数组，per-sector 粒度。

### 3.2 global demand 计数

在 `shader.cc` 的 `L1_latency_queue_cycle()` 中，对 `GLOBAL_ACC_R` 类型的 demand load：
- 每次进入 L1D access：`++total_demand_global_reads`
- access 结果为 MISS 或 SECTOR_MISS：`++total_demand_global_misses`

### 3.3 CT PC demand 计数

在 `on_demand_load()` 中，CT lookup 命中后（`ct_idx >= 0`），利用新增的 `cache_status` 参数：
- `++demand_loads_ct_pc`
- HIT → `++demand_hits_ct_pc`
- MISS/SECTOR_MISS → `++demand_misses_ct_pc`

### 3.4 stride 收敛质量

- `ct_entry_t` 新增 `demand_count_before_stride`：在 `on_demand_load()` 中 `!stride_valid` 时递增
- stride 收敛时（`update_stride()` 返回 true）：`++stride_converge_count`，`stride_converge_total_demands += demand_count_before_stride`
- `ct_stats_t` 新增 `stride_reconverge_count`：在 `update_stride()` 中 `stride_valid && delta != iter_stride` 时递增

### 3.5 unique_index_pcs

`cd_stats_t` 新增 `unique_index_pcs_detected`。CD 内部用 `std::unordered_set<new_addr_type>` 对 index PC 去重，仅训练阶段增长，冻结后停止。

---

## 4. 验证结果

### 4.1 SSSP (ima_high, --max-completed-cta 5) SM0 最终 kernel

```
GRASP_DEMAND SM0: global_reads=128958 global_misses=36382 ct_loads=23434 ct_misses=5442 ct_hits=5768 demand_hit_pf=3735
GRASP_METRICS SM0: coverage=0.0931 accuracy=0.2260 timeliness=1.0000
GRASP_QUALITY SM0: ct_chain_cov=1.0000(=6/6) ct_util=0.1875 prb_util=0.4463 eff_pf=0.2260 avg_stride_obs=1784.4 stride_reconverge=0 coalesce=2 throttle=0 pf_rfail_rate=0.1252
```

**解读**：
- GRASP 消除了 9.3% 的 demand miss（coverage=0.093）
- 约 22.6% 的 prefetch 被实际使用（accuracy=0.226），其余浪费
- 所有 useful prefetch 都及时到达（timeliness=1.0）
- CT 完整覆盖 6 条链（ct_chain_cov=1.0），CT 只用了 18.8%（可缩小）
- PRB 峰值占 44.6%（可从 1024 缩小到 ~512）
- 12.5% 的 prefetch 因 MSHR/miss queue 满被丢弃

### 4.2 正确性检查

| 约束 | SSSP 结果 | tiny_case 结果 |
|------|-----------|---------------|
| coverage ∈ [0, 1] | 0.0931 ✓ | 0.0000 ✓ |
| accuracy ∈ [0, 1] | 0.2260 ✓ | 0.0000 ✓ |
| timeliness ∈ [0, 1] | 1.0000 ✓ | 0.0000 ✓ |
| ct_chain_cov ≤ 1.0 | 1.0000 ✓ | 1.0000 ✓ |
| stride_reconverge = 0 | 0 ✓ | 0 ✓ |
| ct_loads ≤ global_reads | 23434 ≤ 128958 ✓ | 489 ≤ 5135 ✓ |

---

## 5. 改动文件清单

| 文件 | 改动 |
|------|------|
| `grasp_prefetcher.h` | +11 stats 字段, `stats_mut()`, `set_l1d()`, `on_demand_load` 签名加 `cache_status` |
| `grasp_prefetcher.cc` | 6 个插桩点 + `print_stats()` 新增 3 行输出 |
| `grasp_tables.h` | `ct_entry_t` +`demand_count_before_stride`, `ct_stats_t` +`stride_reconverge_count` |
| `grasp_tables.cc` | `update_stride()` reconverge 计数 + `insert()` 重置 demand_count |
| `grasp_chain_detector.h` | `cd_stats_t` +`unique_index_pcs_detected`, +`m_unique_index_pcs` set |
| `grasp_chain_detector.cc` | chain 检测时去重计数, `reset()` 清空 set |
| `shader.cc` | global demand 计数 + 传 `status` + `set_l1d()` |
| `gpu-cache.h` | `cache_block_t` +`set/is_prefetched`, `line/sector_cache_block` 实现, `tag_array` +计数器, `baseline_cache` +accessor |
| `gpu-cache.cc` | `fill()` 标记 prefetch, `rd_hit_base()` 检测 demand hit |
