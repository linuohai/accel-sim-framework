# BFS 1SM Rootcause 分析报告

> 生成日期: 2026-04-02

## 1. 实验配置

| 项目 | 值 |
|------|-----|
| Workload | BFS ima_small (`bfs_ima_small`, web-Google 图) |
| SM 数 | 1 |
| CTA 限制 | 无（完整运行） |
| GPU 配置 | SM80_A100 |
| IMA Chain | 7 条: chain 0-1 (`0xc0→0xf0`, `0xc0→0x100`, worklist offset/neighbor) + chain 2-6 (`0x1d0→0x200`, `0x640→0x670`, `0x9a0→0x9d0`, `0xd00→0xd30`, `0x1060→0x1090`, ×4 展开 CSR edge lookup) |
| GRASP 参数 | `cd_fifo=20 ct_size=32 tt_size=8 ist_ipt=64 ist_dist=1 ist_conf=2 prb_cap=1024 tc_mshr_thr=80 pt_scope=0(per-warp)` |

**数据来源**: `bfs_1sm_rootcause.log` → `GRASP_CONFIG:` 行

## 2. Phase 2: Triage 指标

### Baseline vs GRASP IMA_DEMAND 对比

**Index Load:**

| 指标 | Baseline | GRASP | Delta |
|------|----------|-------|-------|
| reads | 88,178 | 88,186 | +8 |
| hits | 41,791 (47.4%) | 36,827 (41.8%) | **-4,964** |
| hit_reserved | 42 (0.05%) | 4,547 (5.2%) | +4,505 |
| misses | 46,345 (52.6%) | 46,812 (53.1%) | +467 |

**Data Load:**

| 指标 | Baseline | GRASP | Delta |
|------|----------|-------|-------|
| reads | 113,413 | 113,424 | +11 |
| hits | 20,686 (18.2%) | 26,459 (23.3%) | **+5,773** |
| hit_reserved | 13,707 (12.1%) | 14,418 (12.7%) | +711 |
| misses | 79,020 (69.7%) | 72,547 (64.0%) | **-6,473** |

**数据来源**: baseline `result/log/bfs_1sm_baseline.log` + GRASP `bfs_1sm_rootcause.log` → 各文件最后一条 `IMA_DEMAND:` 行

### GRASP 预取管线漏斗

**Index PF 注入 L1（59,276 次尝试，4 种互斥结果）：**

| L1 结果 | 数量 | 占比 | 后续 |
|---------|------|------|------|
| HIT | 21,179 | 35.7% | 立即 FILL_DISPATCH |
| MISS (issued) | 25,586 | 43.2% | on_fill 后 FILL_DISPATCH |
| RFAIL | 12,511 | 21.1% | 丢弃，无后续 |
| MSHR merge | 0 | 0.0% | on_fill 后 FILL_DISPATCH |

**FILL_DISPATCH → Data PF 转化（46,762 次）：**

| 分类 | 数量 | 占比 | 含义 |
|------|------|------|------|
| targets≥1 → data PF enqueued | 20,585 | 44.0% | PT 命中，产生 data PF |
| targets=0 | 26,177 | 56.0% | PT 无映射，无 data PF |

**Data PF 注入 L1（19,465 次尝试）：**

| L1 结果 | 数量 | 占比 |
|---------|------|------|
| MISS (issued) | 13,981 | 71.9% |
| HIT | 5,063 | 26.0% |
| RFAIL | 421 | 2.2% |
| MSHR merge | 0 | 0.0% |

**补充统计：**
- **Pair Table:** hit=25,080 / miss=34,196 (hit rate=42.3%)
- **RFAIL 原因 (总计 12,932):** missq=89.9%, mshr_entry=10.1%
- **存储峰值:** PRB=53/1024(5.2%), CT=6/32(18.8%), CD FIFO=20/20(100.0%), PF queue peak=27
- **L1 级效果:** useful=13,347, useless=21,071, late=5,264, accuracy=38.78%

**数据来源**: `bfs_1sm_rootcause.log` → 最后一条 `GRASP_SM0:`、`GRASP_STORAGE`、`GRASP_EFFECT`、`GRASP_RFAIL` 行；FILL_DISPATCH 统计从 `bfs_1sm_rootcause_grasp.csv`

### 核心指标

| 指标 | 值 | 判断 |
|------|-----|------|
| Data Coverage | 8.2% | 极低（<20%）→ 覆盖率问题 |
| Data Timeliness | 64.7% | 偏低（<70%）→ 及时性问题 |
| PT Hit Rate | 42.3% (25,080/59,276) | 不足（<50%）→ PT 瓶颈 |
| Index Hit 变化 | -4,964 (47.4%→41.8%) | GRASP 干扰了 index demand |

**数据来源**: PT stats 从 `bfs_1sm_rootcause.log` → 最后一条 `GRASP_SM0:` 行中 `pair_table(hit=25080 miss=34196)`

## 2.5 Chain 2-6 独立分析（排除 chain 0-1）

Chain 0-1（`0xc0→0xf0`, `0xc0→0x100`，worklist offset/neighbor）与 chain 2-6（CSR edge lookup，×4 展开）的行为模式完全不同。以下为排除 chain 0-1 后的独立数据。

### Baseline vs GRASP IMA_DEMAND（chain 2-6 only）

**Index Load（chain 2-6, idx_pc: 0x1d0/0x640/0x9a0/0xd00/0x1060）：**

| 指标 | Baseline | GRASP | Delta |
|------|----------|-------|-------|
| reads | 86,359 | 86,367 | +8 |
| hits | 41,766 (48.4%) | 36,805 (42.6%) | **-4,961** |
| hit_reserved | 10 (0.0%) | 4,513 (5.2%) | +4,503 |
| misses | 44,583 (51.6%) | 45,049 (52.2%) | +466 |

**Data Load（chain 2-6, data_pc: 0x200/0x670/0x9d0/0xd30/0x1090）：**

| 指标 | Baseline | GRASP | Delta |
|------|----------|-------|-------|
| reads | 84,425 | 84,436 | +11 |
| hits | 20,574 (24.4%) | 26,355 (31.2%) | **+5,781** |
| hit_reserved | 2,762 (3.3%) | 3,470 (4.1%) | +708 |
| misses | 61,089 (72.4%) | 54,611 (64.7%) | **-6,478** |

### GRASP 预取管线漏斗（chain 2-6 only）

**Index PF 注入 L1（58,663 次尝试）：**

| L1 结果 | 数量 | 占比 | 后续 |
|---------|------|------|------|
| HIT | 21,179 | 36.1% | 立即 FILL_DISPATCH |
| MISS (issued) | 25,449 | 43.4% | on_fill 后 FILL_DISPATCH |
| RFAIL | 12,035 | 20.5% | 丢弃，无后续 |
| MSHR merge | 0 | 0.0% | on_fill 后 FILL_DISPATCH |

**FILL_DISPATCH → Data PF 转化（46,625 次）：**

| 分类 | 数量 | 占比 | 含义 |
|------|------|------|------|
| targets≥1 → data PF enqueued | 20,585 | 44.1% | PT 命中，产生 data PF |
| targets=0 | 26,040 | 55.9% | PT 无映射，无 data PF |

**Data PF 注入 L1（19,465 次尝试，全部来自 chain 2-6）：**

| L1 结果 | 数量 | 占比 |
|---------|------|------|
| MISS (issued) | 13,981 | 71.9% |
| HIT | 5,063 | 26.0% |
| RFAIL | 421 | 2.2% |
| MSHR merge | 0 | 0.0% |

### 核心指标（chain 2-6 only）

| 指标 | Chain 2-6 | 全局（含 0-1） | 说明 |
|------|-----------|---------------|------|
| Data Coverage | 10.6% | 8.2% | 略好，chain 0-1 拖低整体 |
| Data Timeliness | **88.4%** | 64.7% | **显著优于全局**——chain 0-1 的 0.9% timeliness 拉低了整体 |
| PT Hit Rate | 42.3% | 42.3% | 全局统计，无法按 chain 拆分 |
| Index Hit 变化 | -4,961 (48.4%→42.6%) | -4,964 | 干扰几乎完全来自 chain 2-6 |

### Chain 0-1 为何不工作

| 指标 | Chain 0-1 | 说明 |
|------|-----------|------|
| Index PF 尝试 | 613 | 极少（vs chain 2-6 的 58,663） |
| Index PF RFAIL | 476 (77.7%) | 大多数被 L1 拒绝 |
| FILL_DISPATCH targets=0 | 137/137 (100%) | **PT 对 chain 0-1 完全无映射** |
| Data PF enqueued | **0** | 无任何 data 预取 |
| Data Coverage | -0.0% | GRASP 无贡献 |
| Data Timeliness | 0.9% | 近乎零（命中的 104 次 vs hit_reserved 的 10,948 次） |

**根因**：chain 0-1 的 worklist 访问模式（offset + neighbor lookup）stride 收敛极慢，且即使 index PF 成功注入，pair table 中也无对应映射（targets=0 占 100%）。这两条链贡献了 17,936 个 data miss（占总 miss 的 24.7%），但 GRASP 对其完全无效。

**数据来源**: `analyze_per_chain_group.py`（从 L1 trace + GRASP trace + root cause detail CSV 按 chain PC 分组）

## 3. Phase 3: Root Cause 分布

72,547 个 data demand miss 的归因（= IMA_DEMAND `data_misses`，完全对齐）：

| Root Cause | Count | % | 说明 |
|-----------|-------|---|------|
| IDX_NOT_TRIGGERED | 34,064 | 47.0% | stride 收敛但 index PF 未 enqueue |
| DATA_PF_THROTTLED | 14,480 | 20.0% | 实质是 per-lane PT miss（见 §4） |
| IDX_PF_RFAIL | 7,985 | 11.0% | index PF RESERVATION_FAIL |
| PT_MISS | 7,043 | 9.7% | pair table 查询失败 |
| STRIDE_NOT_CONVERGED | 6,477 | 8.9% | stride 训练未完成 |
| EVICTED | 1,898 | 2.6% | 预取成功但被 evict |
| DATA_PF_PENDING | 465 | 0.6% | data PF 在飞行中 |
| DATA_PF_RFAIL | 131 | 0.2% | data PF RFAIL |
| IDX_PF_PENDING | 4 | 0.0% | index PF 在飞行中 |

**数据来源**: `analyze_data_miss_rootcause.py`（使用完整 7 PC: `--data-pcs "0x00f0,0x0100,0x0200,0x0670,0x09d0,0x0d30,0x1090" --index-pcs "0x00c0,0x01d0,0x0640,0x09a0,0x0d00,0x1060"`），detail CSV 在 `bfs_1sm_rootcause_detail.csv`（72,548 行含 header）

### Root Cause 分布（chain 2-6 only，54,611 个 miss）

| Root Cause | Count | % | 说明 |
|-----------|-------|---|------|
| IDX_NOT_TRIGGERED | 21,904 | 40.1% | stride 收敛但 index PF 未 enqueue |
| DATA_PF_THROTTLED | 14,480 | 26.5% | fill 回来但 data PF 未覆盖目标 sector |
| IDX_PF_RFAIL | 7,985 | 14.6% | index PF RESERVATION_FAIL |
| PT_MISS | 7,043 | 12.9% | pair table 查询失败 |
| EVICTED | 1,898 | 3.5% | 预取成功但被 evict |
| STRIDE_NOT_CONVERGED | 701 | 1.3% | stride 训练未完成 |
| DATA_PF_PENDING | 465 | 0.9% | data PF 在飞行中 |
| DATA_PF_RFAIL | 131 | 0.2% | data PF RFAIL |
| IDX_PF_PENDING | 4 | 0.0% | index PF 在飞行中 |

### 结构性 Miss 过滤（chain 2-6）

**Batch** = 同一 (warp, idx_pc) 的一次 warp-level instruction execution（连续 demand gap < 100 cycles 为同一 batch）。

- **STRUCTURAL_BATCH1**（首次执行）：stride 未学习，无法预取。
- **STRUCTURAL_BATCH2**（stride 收敛点）：首次预测目标为 batch 3，当前 batch 的 IMA data 未被覆盖。

| Root Cause | Batch 1 | Batch 2 | Batch 3+ (非结构性) |
|-----------|---------|---------|-------------------|
| IDX_NOT_TRIGGERED | 2,016 | 573 | **19,315** |
| DATA_PF_THROTTLED | 458 | 753 | **13,269** |
| IDX_PF_RFAIL | 114 | 259 | **7,612** |
| PT_MISS | 2 | 354 | **6,687** |
| EVICTED | 93 | 24 | **1,781** |
| STRIDE_NOT_CONVERGED | 245 | 7 | **449** |
| DATA_PF_PENDING | 5 | 0 | **460** |
| DATA_PF_RFAIL | 1 | 0 | **130** |
| **合计** | **2,934 (5.4%)** | **1,970 (3.6%)** | **49,707 (91.0%)** |

→ 结构性 miss 占 9.0%（4,904 条），非结构性占 91.0%（49,707 条）。后续分析聚焦 batch 3+。

### Root Cause 分布（chain 0-1 only，17,936 个 miss）

| Root Cause | Count | % | 说明 |
|-----------|-------|---|------|
| IDX_NOT_TRIGGERED | 12,160 | 67.8% | stride 收敛但 index PF 未 enqueue |
| STRIDE_NOT_CONVERGED | 5,776 | 32.2% | stride 训练未完成 |

→ Chain 0-1 的 miss 只有两个原因：stride 未收敛（32%）和 index PF 未触发（68%）。没有任何 miss 进入 Step 5+ 阶段（PT/FILL/DATA），因为 chain 0-1 的 index PF 几乎全部 RFAIL 或在 FILL_DISPATCH 时 targets=0。

**数据来源**: `analyze_per_chain_group.py` 从 `bfs_1sm_rootcause_detail.csv` 按 data PC 分组

## 4. Phase 3.5: PT miss 深度分析

### FILL_DISPATCH targets 分布

| 分类 | 数量 | 占比 |
|------|------|------|
| targets=0 (PT 无映射) | 26,177 | 56.0% |
| targets>=1 (PT 有映射) | 20,585 | 44.0% |
| **总 FILL_DISPATCH** | **46,762** | |

实际 `throttle_suppressed`: **1,017**

→ DATA_PF_THROTTLED (14,480) 中绝大多数是 FILL_DISPATCH targets=0（per-lane PT miss），非真正 MSHR throttle。

**数据来源**: `bfs_1sm_rootcause_grasp.csv` → `grep "FILL_DISPATCH"` 统计 targets 字段；`bfs_1sm_rootcause.log` → `throttle_suppressed`

### PT miss 地址交叉比对

将全部 34,196 条 PT miss 的 `(warp_id, lane_addrs)` 与 runtime pair table dump 交叉比对：

| 分类 | 数量 | 占比 | 含义 |
|------|------|------|------|
| 同一 warp runtime PT 已有 | 14 | 0.0% | timing 边界 |
| 其他 warp runtime PT 已有 | 906 | 2.6% | per-warp scope 问题 |
| **任何 warp 都没有** | **33,276** | **97.3%** | **addr_map 未填充** |

→ PT miss 根因是 **prefetch 超前于 demand**，addr_map 尚无映射，非 per-warp scope 问题（97.3%）。per-warp scope 贡献 2.6%（906 条），可作为后续优化方向。

**数据来源**: PT miss 地址从 `bfs_1sm_rootcause.log` 提取全部 34,196 条 `GRASP_PT_MISS` 行（`pt_miss_full.txt`）；runtime PT dump 从 `bfs_1sm_rootcause_pair_table.csv`（115,403 条）；交叉比对脚本 `cross_compare_pt_miss.py`

### 修正后的 Root Cause 合并视图

将 PT_MISS 和 DATA_PF_THROTTLED 中的 PT miss 部分合并：

```
IDX_NOT_TRIGGERED:         34,064 (47.0%)  ← 最大瓶颈
addr_map 未填充 (PT_MISS + DATA_PF_THROTTLED 中 PT miss):
  ~7,043 + ~13,463 = ~20,506 (28.3%)
IDX_PF_RFAIL:               7,985 (11.0%)
STRIDE_NOT_CONVERGED:        6,477 ( 8.9%)
EVICTED:                    1,898 ( 2.6%)
真正的 Throttle:           ~1,017 ( 1.4%)
其他:                         600 ( 0.8%)
```

## 5. 关键发现与结论

1. **Chain 0-1 与 chain 2-6 行为完全不同**：chain 0-1（worklist 访问）贡献 17,936 miss（24.7%），但 GRASP 对其完全无效（0 条 data PF）；chain 2-6（CSR edge lookup）是 GRASP 实际工作的对象。

2. **排除 chain 0-1 后 timeliness 大幅改善**：chain 2-6 timeliness=88.4%（全局仅 64.7%），说明 GRASP 的及时性问题主要来自 chain 0-1 的 0.9% timeliness 拖低整体。

3. **Chain 2-6 的最大瓶颈是 IDX_NOT_TRIGGERED (40.1%) + addr_map 未填充 (39.4%)**：后者包括 PT_MISS (12.9%) + DATA_PF_THROTTLED 中的 PT miss (26.5%)。

4. **IDX_PF_RFAIL 在 chain 2-6 中占 14.6%**：missq 满（89.9%）是主因，可通过调整 miss queue 容量或降低 prefetch 积极性缓解。

5. **addr_map 未填充根因是 prefetch 超前于 demand**：全部 34,196 条 PT miss 交叉比对，97.3%（33,276）在任何 warp 都不存在；2.6%（906）存在于其他 warp（per-warp scope 局限）。

6. **Chain 0-1 不工作的根因**：stride 收敛慢（32.2% STRIDE_NOT_CONVERGED）+ 即使 index PF 成功注入也全部 targets=0（pair table 对 worklist 模式无映射）。

7. **GRASP 生效时效果极好**: stride 收敛后的多 lane iteration 中可实现 20x~75x 单 iteration speedup（iteration 116, 152）。瓶颈不在管线本身，而在覆盖率。

## 6. 数据来源汇总

| 数据 | 文件路径 |
|------|---------|
| GRASP 仿真日志 | `debug/bfs_1sm_rootcause/bfs_1sm_rootcause.log` |
| Baseline 仿真日志 | `result/log/bfs_1sm_baseline.log` |
| GRASP L1 trace | `debug/bfs_1sm_rootcause/bfs_1sm_rootcause_l1.csv` |
| Baseline L1 trace | `debug/bfs_1sm_rootcause/baseline/bfs_1sm_baseline_l1.csv` |
| GRASP event trace | `debug/bfs_1sm_rootcause/bfs_1sm_rootcause_grasp.csv` |
| Runtime pair table dump | `debug/bfs_1sm_rootcause/bfs_1sm_rootcause_pair_table.csv` |
| Ground truth pair table | `debug/bfs_1sm_rootcause/pair_table_full_trace.csv` |
| Root cause detail CSV | `debug/bfs_1sm_rootcause/bfs_1sm_rootcause_detail.csv` |
| PT miss 完整日志 (34,196 条) | `debug/bfs_1sm_rootcause/pt_miss_full.txt`（从 `bfs_1sm_rootcause.log` 提取） |
| PT miss 交叉比对脚本 | `debug/bfs_1sm_rootcause/cross_compare_pt_miss.py` |
| Chain 分组分析脚本 | `debug/bfs_1sm_rootcause/analyze_per_chain_group.py` |
| Per-iteration analysis | `debug/bfs_1sm_rootcause/analysis/` |
| 源码: throttle 机制 | `gpu-simulator/gpgpu-sim/src/gpgpu-sim/grasp_prefetcher.cc:620-631` |
| 源码: PT lookup | `gpu-simulator/trace-driven/trace_driven.cc:552-591` |
| 源码: IMA demand 统计 | `gpu-simulator/gpgpu-sim/src/gpgpu-sim/shader.cc:3224-3236` |
| 源码: L1 tracer (已修复) | `gpu-simulator/gpgpu-sim/src/gpgpu-sim/l1_tracer.cc` → per-mem_fetch 输出，不做 lane dedup |
| Golden chain CSV | `ima_plan/05_implementation/ima_pair_table/golden/strict_selected_chain_instances.csv` (BFS 7 条 chain) |
