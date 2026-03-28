# GRASP Prefetcher 实验进度记录

> **目的**：统一的实验进度 + 问题追踪文档。记录实验配置、结果、发现的问题和解决方案。
> **写入规则**：**append-only**——新内容追加到对应 section 末尾，不修改已有条目。多个并发 session 可安全追加。
>
> 最近更新：2026-03-28

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

## 5. GRASP Tiny Case 逐 Iteration 验证 (2026-03-25 ~ 03-26)

### 5.1 验证目标

在 `ima_tiny_case` (dl64, 1SM_NOSUBCORE) 上逐 iteration 验证 GRASP 全管线行为，使用专用分析脚本 `grasp_verify/analyze_grasp_iterations.py`。

### 5.2 版本演进

| 版本 | Cycles | 改动 | 关键结果 |
|------|--------|------|---------|
| baseline | 30661 | — | 16 iter, 每 iter index 4xMISS |
| v1 (GRASP) | 24175 | 初始 GRASP 开启 | -21%, 验证管线功能正确 |
| v2 | 24175 | stride seed on CT creation + queue dedup + 4-sector inject | 与 v1 相同（优化未暴露新收益） |
| v3 | 23788 | 修复跨 warp FIFO bug（v2 的 FIFO 越界） | **-22.4%**, 2.37x per-iter speedup |
| v4 | 23788 | 3 项 trace 质量 + 功耗优化（见 §5.3） | 性能不变，事件流更干净 |
| v5 | 23788 | 修复 CD freeze 条件（见 §5.4） | 性能不变，确保 CT 未满时不误冻结 CD |

### 5.3 v4 改动详情

1. **DEMAND_CT_HIT / STRIDE_UPDATE per-instruction dedup**
   - 每条 LDG 产生 4 个 sector mem_fetch，共享同一 `inst_uid`。v3 对 4 个 sector 都触发 CT 查找和 stride 计算
   - v4：仅第一个 sector 触发（`is_first_sector` 检查），后 3 个 skip
   - 效果：每 iter DEMAND_CT_HIT 4→1, STRIDE_UPDATE 4→1（消除 delta=0 噪声）
   - 文件：`grasp_prefetcher.cc` `on_demand_load()`，`grasp_tables.h` `ct_entry_t` 新增 `last_demand_warp_id`/`last_demand_inst_uid`

2. **IDX_PF_INJECT 显示 prb_id**
   - 分析脚本 `format_detail_brief()` 解析 `prb_id` 字段
   - 效果：事件流中 `IDX_PF_INJECT` 显示 `prb=0`, `prb=1` 等

3. **CD check_freeze 激活**
   - `check_freeze()` 已存在但从未被调用
   - v4：在 `STRIDE_CONVERGE` 后调用 `m_cd.check_freeze(m_ct)`
   - 条件：`ct.all_stride_valid()` — **仅检查 valid entry，不检查 CT 是否满**
   - 效果：训练后 0 次 CHAIN_DETECT（v3 有 15 次冗余检测）

### 5.4 v5 改动详情

- **问题**：v4 的 `all_stride_valid()` 跳过 invalid slot，CT 只有 1 条 chain（未满）时仍返回 true → 过早冻结 CD → 新 IMA chain 无法被检测
- **修复**：`check_freeze()` 条件改为 `ct.is_full() && ct.all_stride_valid()`
  - `is_full()` 检查所有 slot 都 valid
  - 新增 `grasp_tables.{h,cc}` `is_full()` 方法
  - 修改 `grasp_chain_detector.cc` `check_freeze()`
- **效果**：tiny_case CT 未满 → CD 不冻结 → CHAIN_DETECT 恢复出现（15 次，与 v3 一致）。性能不变 23788 cycles
- **真实 workload**：CT 满后 CD 正确冻结，省功耗

### 5.5 Per-Iteration Speedup 模式

奇偶交替（distance=1 lookahead 限制）：

| 类型 | Index L1 | Data L1 | Speedup | 原因 |
|------|----------|---------|---------|------|
| 偶数 iter (2,4,6,...) | 4xHIT | 32xHIT | 7.6x–15.2x | 上轮 PF 已 FILL 完成 |
| 奇数 iter (3,5,7,...) | 4xHIT_RES | HIT+HIT_RES 混合 | 1.4x–2.7x | 当前 iter PF 刚发出，FILL 在途 |

Overall: avg baseline latency=748.4, avg GRASP latency=316.1, **2.37x per-iteration speedup**

### 5.6 验证产出文件索引

```
grasp_verify/
├── grasp_v5/
│   ├── grasp_verify_pf_v5.log
│   ├── grasp_verify_pf_v5_l1.csv
│   ├── grasp_verify_pf_v5_grasp.csv
│   └── analysis_output/
│       ├── event_timeline_warp1.txt    # 逐 iter 事件流
│       ├── baseline_comparison_warp1.txt  # Baseline vs GRASP 对比
│       ├── format_a_warp1.txt/csv      # 摘要表
│       └── analysis_log.txt            # 运行元信息
├── baseline_v4/                         # Baseline（v4/v5 共用）
└── analyze_grasp_iterations.py          # 分析脚本
```

### 5.7 v6: RESERVATION_FAIL Per-Reason 诊断 (2026-03-25)

**背景**：§3.2.2 显示 GRASP 运行后 RFAIL 增加 27,559 次（+0.9%），但无法区分是 MSHR 满、miss queue 满还是 cache line 全 reserved。原 `rfail` 统计只有总数，无法定位根因。

**改动**：为 GRASP 的 RESERVATION_FAIL 统计添加 per-reason breakdown。

| 文件 | 改动 |
|------|------|
| `gpu-cache.h` | `baseline_cache` 新增 `m_last_fail_reason` 成员 + `last_fail_reason()` getter |
| `gpu-cache.cc` | 所有 `inc_fail_stats()` 调用处（~15 处）同步设置 `m_last_fail_reason` |
| `grasp_prefetcher.h` | `grasp_stats_t` 新增 `index_pf_rfail[5]` / `data_pf_rfail[5]` per-reason 数组；`on_l1_access_result` 增加 `fail_reason` 参数 |
| `grasp_prefetcher.cc` | RESERVATION_FAIL 分支按 reason 分桶；`print_stats` 输出 per-reason breakdown |
| `shader.cc` | 传递 `m_L1D->last_fail_reason()` 给 GRASP |

**5 种 fail reason**：

| Reason | 含义 |
|--------|------|
| `LINE_ALLOC_FAIL` | 目标 set 中所有 cache line 都被 reserved |
| `MISS_QUEUE_FULL` | miss queue（到 interconnect/DRAM）满 |
| `MSHR_ENRTY_FAIL` | MSHR 无空闲 entry |
| `MSHR_MERGE_ENRTY_FAIL` | MSHR 已有该地址 entry 但 merge 满 |
| `MSHR_RW_PENDING` | Write-Read-Write 冒险 |

**日志输出格式**（每个 SM 的 GRASP 统计行新增）：
```
idx_rfail(line_alloc=X missq=X mshr_entry=X mshr_merge=X rw_pending=X)
data_rfail(line_alloc=X missq=X mshr_entry=X mshr_merge=X rw_pending=X)
```

**用途**：下一轮实验（distance=3-5 + throttle）前，先用此诊断确认 SpMV 的 rfail 根因分布，指导 throttle 策略（如 MSHR_ENRTY_FAIL 占比高则按 MSHR 占用率节流，MISS_QUEUE_FULL 占比高则按 miss queue 深度节流）。

---

## 5b. ima_med 全量实验 (2026-03-27 ~ 03-28)

### 5b.1 实验配置

- **GPU 配置**：SM80_A100 (108 SM)，默认参数
- **CTA 限制**：无（完整运行）
- **GRASP 参数**：默认（见 §2.2），distance=1（默认值）

**⚠ 不可与 §3 消融实验直接对比**：§3 使用 ima_high (cit-Patents) + 限制 CTA (50-100)，本实验使用 ima_med (web-Google) + 完整运行。数据集不同 + CTA 规模不同，结果无可比性。

### 5b.2 数据集说明

三级 IMA 数据集的差异不仅是图规模，更关键的是 **symmetrize 标志**（Gardenia `main.cc` 第 3 个参数）。对称化将有向图转为无向图，边数增加约 69%，导致 BFS/SSSP frontier 更大、IMA 访问更密集。

| 级别 | 图 | symmetrize | 节点数 | 边数 | 源节点 | 说明 |
|------|-----|:----------:|--------|------|--------|------|
| ima_small | web-Google | 0（有向） | 916,428 | 5,105,039 | 506742 | frontier 小，BFS/SSSP 非 memory-bound |
| **ima_med** | **web-Google** | **1（无向）** | **916,428** | **8,644,102** | **506742** | **本实验使用** |
| ima_high | cit-Patents | 1（无向） | ~3.5M | — | 3569341 | 更大图 + 无向 |

注意：ima_small 和 ima_med 是**同一张图、同一个源节点**，区别仅在 symmetrize。SpMV 不依赖源节点和 BFS frontier，对称化仅影响矩阵非零分布。

### 5b.3 ima_med 结果

| Workload | Baseline IPC | GRASP IPC | Baseline Cycles | GRASP Cycles | Speedup |
|----------|-------------|-----------|----------------|-------------|---------|
| bfs_ima_med | 7.3528 | 11.0151 | 18,473,259 | 12,331,255 | **+49.8%** |
| sssp_ima_med | 9.5580 | 13.7587 | 17,997,932 | 12,502,901 | **+44.0%** |
| spmv_ima_med | 129.6846 | 164.1219 | 760,487 | 600,916 | **+26.6%** |
| bc_ima_med | 10.8322 | 13.3567 | 41,346,547 | 33,531,935 | **+23.3%** |
| **Geomean** | | | | | **+35.5%** |

### 5b.4 ima_small baseline 对比（仅 baseline，无 GRASP 数据）

| Workload | ima_small Baseline IPC | ima_med Baseline IPC | IPC 比 | 原因 |
|----------|----------------------|---------------------|--------|------|
| bfs | 23.5588 | 7.3528 | small 3.2× 快 | 有向图 frontier 小 |
| sssp | 28.8141 | 9.5580 | small 3.0× 快 | 同上 |
| spmv | 130.4888 | 129.6846 | ≈ 相同 | SpMV 不受 symmetrize 显著影响 |
| bc | 499.5106 | 10.8322 | small 46× 快 | 有向图 BC 遍历深度极浅 |

ima_small（有向图）的 BFS/SSSP/BC 因 frontier 小而非 memory-bound，GRASP 在此级别预期无显著收益。

### 5b.5 日志文件索引

| 日志 | 说明 |
|------|------|
| `result/log/bfs_ima_med_baseline.log` | BFS 基线（全量） |
| `result/log/bfs_ima_med_grasp.log` | BFS GRASP（全量） |
| `result/log/sssp_ima_med_baseline.log` | SSSP 基线（全量） |
| `result/log/sssp_ima_med_grasp.log` | SSSP GRASP（全量） |
| `result/log/spmv_ima_med_baseline.log` | SpMV 基线（全量） |
| `result/log/spmv_ima_med_grasp.log` | SpMV GRASP（全量） |
| `result/log/bc_ima_med_baseline.log` | BC 基线（全量） |
| `result/log/bc_ima_med_grasp.log` | BC GRASP（全量） |

---

## 6. 下一步行动

### 6.1 高优先级（已完成）

| # | 行动 | 结果 |
|---|------|------|
| 1 | **增加 `ist_distance` 到 3-5** | ✅ distance=4 验证有效（SSSP +42.2%） |
| 2 | **CT stride 跨 kernel 持久化** | ✅ 已实现，多 kernel workload 不再丢训练 |
| 3 | **实现 Throttle Control** | ✅ 已实现（80% 阈值），SpMV 场景仍需调优 |

### 6.2 当前重点

> 新的行动项直接追加到本 section 末尾。

- SpMV ×16 展开导致 4/5 chain 学不到 stride → 需设计层面解决
- Throttle 80% 阈值在 MSHR 饱和场景未触发 → 需更激进策略
- SOTA Spare Register SpMV 实验待完成

---

## 7. 已知问题

> 历史阻塞项详见 [`v1_implementation_problems.md`](v1_implementation_problems.md)。新发现的问题直接追加在下方。

| 问题 | 状态 | 说明 |
|------|------|------|
| `warp_traces.size() > 0` 断言失败 | **Pre-existing** | BFS/BC `--max-completed-cta` 模式下 CTA 回收时触发。非 GRASP bug |
| `miss` 统计字段永远为 0 | Cosmetic | `index_pf_miss` / `data_pf_miss` 未被任何代码路径赋值，可移除 |
| `warp_exits=0` 在所有 SM | Needs investigation | tracked warp 退出事件未被记录，可能 hook 位置不对 |

---

## 8. 日志文件索引

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
