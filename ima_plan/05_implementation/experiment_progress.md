# GRASP Prefetcher 实验进度记录

> **目的**：统一的实验进度 + 问题追踪文档。记录实验配置、结果、发现的问题和解决方案。
> **写入规则**：**append-only**——新内容追加到对应 section 末尾，不修改已有条目。多个并发 session 可安全追加。
>
> 最近更新：2026-04-02

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
| chain CSV | `ima_plan/05_implementation/ima_pair_table/golden/strict_selected_chain_instances.csv` | 默认 |

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

## 7b. 实验基础设施改进 + Accuracy/Coverage/Timeliness 首次测量 (2026-03-29)

**版本**: gpgpu-sim commit `7250426` (grasp v7 + prefetch metrics)

**新增基础设施**:
- `traceL1`: `verify_completion()` 实验完成性验证 + `update_baseline_registry()` 自动写入 baseline
- `grasp_prefetcher.cc`: `GRASP_CONFIG` / `GRASP_DEMAND` / `GRASP_EFFECT` 三行新输出
- `gpu-cache.{h,cc}`: `pf_useful` (demand hit prefetched line), `pf_useless` (sector-level evict), `pf_late` (demand merge into pf MSHR)
- `grasp_regression.sh`: 去掉 baseline 重跑 + 并行化 + `--quick` 模式（默认）

**Prefetch 三指标（SM0, IMA loads only, ima_small/ima_med 全量运行）**:

| Workload | IPC | IMA Misses | pf_useful | pf_useless | pf_late | Accuracy | Coverage | Timeliness |
|----------|-----|-----------|-----------|------------|---------|----------|----------|------------|
| BFS | 30.34 | 11,897 | 11,102 | 8,762 | 1,156 | 55.89% | 93.32% | 89.59% |
| SSSP | 34.59 | 16,767 | 8,977 | 9,274 | 1,378 | 49.19% | 53.54% | 84.65% |
| SpMV | 152.04 | 42,332 | 6,572 | 16,220 | 1,519 | 28.83% | 15.52% | 76.89% |
| BC | 44.72 | 33,333 | 19,419 | 18,719 | 2,223 | 50.92% | 58.26% | 88.55% |

**发现**:
- BFS coverage 93% — GRASP 几乎覆盖所有 IMA miss，是最佳 workload
- SpMV accuracy 仅 29% — 大量 useless prefetch，与 ×16 展开 + MSHR 饱和一致
- Timeliness 全部 >76%，说明大部分预取能在 demand 前完成
- Coverage 使用 IMA-only demand misses 作为分母（更准确反映对目标 load 的覆盖）

---

## 7c. v7→v8 设计审阅 + P4/P5 修复 + MSHR Sweep (2026-03-29)

**版本变更**:
- **P1** (v7): PRB per-sector → per-instruction（shared PRB, remaining_sectors=N）
- **P2** (v7): Pair table exact_match_only（只查 active lane 预测地址，不盲扫 sector 8 slot）
- **P3** (v7): MSHR_HIT piggyback（不 delete mf，cache 持有后由 fill 回调触发 data PF）
- **P4** (v8): CD 用 `sass_opcode.find("LDG")` 检测 load（排除 ATOM 误判）
- **P5** (v8): Pair table 按 `data_source_file:line` 归并（展开 PC 共享 addr_map）

**v8 回归（golden = v6 commit 9ebfe62）**:

| Benchmark | Golden GRASP | v8 GRASP | vs Golden | 状态 |
|-----------|-------------|----------|-----------|------|
| BFS | 29.75 | **30.34** | +1.98% | PASS |
| SSSP | 34.28 | **34.59** | +0.91% | PASS |
| BC | 44.61 | **44.72** | +0.25% | PASS |
| SpMV | 164.12 | **152.04** | -7.36% | FAIL |

**SpMV 回退根因分析**:
- P5 归并使 pair_table hit +223%（7081→22889）→ data_pf +117% → MSHR 争用加剧
- idx_rfail 中 mshr_entry_fail 从 5459 涨到 9252（+69%）

**MSHR Sweep 实验（SpMV, 108SM）**:

| MSHR entries | NP IPC | GRASP IPC | Delta | mshr_entry_fail |
|-------------|--------|-----------|-------|-----------------|
| 512 (default) | 129.68 | 152.04 | +17.2% | 9,252 |
| 1024 | 130.56 | 151.58 | +16.1% | 638 |
| 2048 | 130.40 | 156.29 | +19.9% | 0 |

**结论**: 增大 MSHR 消除了 mshr_entry_fail 但 GRASP delta 仅从 +17.2% 提升到 +19.9%（+2.7pp）。SpMV 瓶颈不在 MSHR 容量，而在 pair table accuracy（28.8%）和 stride 跨展开 PC 边界问题。

**审阅中发现的其他问题**:
- BFS 分析脚本 `find_iteration_boundaries` 有 sector 全局去重 bug（同 sector 不同迭代被合并）→ 已修复
- BFS 1SM 诊断的负 speedup 是因为仅观测到 frontier 极小的早期 kernel（GRASP 收益在中间层级 kernel）
- `analyze_grasp_iterations_v2.py` 的 iteration 粒度（node 级）比 GRASP stride 学习（循环体级）粗

**日志文件**:
- `result/log/regress_{bfs,sssp,spmv,bc}_grasp.log` — v8 回归
- `result/log/spmv_mshr{512,1024,2048}_{np,grasp}.log` — MSHR sweep
- `result/log/bfs_v8_diag_{base,grasp}.log` — v8 BFS 1SM 诊断
- `ima_plan/05_implementation/grasp_real_diag/bfs_v8/` — v8 BFS 分析文档

---

## 7d. Timeliness/Coverage 指标体系重构 (2026-03-30)

**问题**：旧 `pf_useful`/`pf_late` 计数器存在计数域不对齐 bug：
- `ima_reads` 只统计 index PC 的 CT 命中（499），漏了 data demand
- `pf_useful`/`pf_late` 在 L1 tag_array 统计，不区分 IMA index/data/非 IMA
- 导致 `pf_late(693) > ima_reads(499)` 的数值矛盾

**方案**：在 ldst_unit 层按 IMA PC 分类统计 L1 probe 结果（HIT/HIT_RESERVED/MISS），不依赖 cache block prefetch flag：
- `reads = hits + hit_reserved + misses`（恒等式，有 assert 保证）
- Timeliness = hits / (hits + hit_reserved)
- Coverage = (baseline_misses - grasp_misses) / baseline_misses
- Index/Data 分别统计 + 总和

**TinyCase 验证** (2026-03-30)：

| | reads | hits(d) | hit_res(c) | misses(b) | d+c+b=N | Timeliness |
|---|---|---|---|---|---|---|
| **GRASP Index** | 512 | 208 | 197 | 107 | 512 ✓ | 51.36% |
| **GRASP Data** | 4096 | 3291 | 743 | 62 | 4096 ✓ | 81.58% |
| **Baseline Index** | 512 | 0 | 0 | 512 | 512 ✓ | — |
| **Baseline Data** | 4096 | 2761 | 1079 | 256 | 4096 ✓ | — |

Data Coverage = (256 - 62) / 256 = **75.78%**. trace-driven 下 N (reads) baseline/GRASP 一致。

**新增输出行**：`GRASP_IMA_DEMAND SM*`、`GRASP_TIMELINESS SM*`、`IMA_DEMAND`（扩展）、`IMA_TIMELINESS`

**日志文件**：`result/log/tiny_metrics_v2.log`、`result/log/tiny_baseline_v2.log`

### BFS Distance Sweep + 四算法新指标 (2026-03-30)

BFS distance d=1~8 sweep + SSSP/SpMV/BC d=1 全部使用新指标体系。

**四算法 d=1 汇总**：

| 算法 | Baseline IPC | GRASP IPC | Speedup | Data Timeliness | Data Coverage | Accuracy | Index Coverage |
|---|---|---|---|---|---|---|---|
| BFS | 23.56 | 30.34 | +28.8% | 67.85% | 14.09% | 55.89% | −5.15% |
| SSSP | 28.81 | 34.59 | +20.1% | 64.36% | 11.54% | 49.19% | +8.05% |
| SpMV | 129.68 | 152.04 | +17.2% | 93.34% | 5.87% | 28.83% | +5.49% |
| BC | 37.65 | 44.72 | +18.8% | 85.83% | 11.05% | 50.92% | +4.21% |

**BFS distance sweep**：d=1 最优（IPC 30.34, +28.8%），d 增大后 Data Timeliness/Coverage 单调下降（d=8: timeliness 44.56%, coverage −0.27%）。Index timeliness 随 d 增大而上升（95%→99.97%）。

**关键发现**：
1. BFS Index Coverage 全为负（−5%~−28%）：index prefetch 导致 cache pollution
2. SpMV baseline index hit_reserved 370 万（×16 展开的自然 MSHR 共享）
3. Data HitRes 在 BFS 中几乎不随 d 变化（~44 万），由 L2 latency 决定

**日志文件**：`result/log/bfs_d{2..8}.log`、`result/log/{sssp,spmv,bc}_d1.log`、`result/log/{bfs,sssp,spmv,bc}_baseline_v2.log`

---

## 7e. BFS 循环级 Iteration 分析（2026-03-31）

**目的**：为 BFS kernel 建立循环级（而非 BFS 波级）的 iteration 分析，支持逐 iteration 的 GRASP 行为诊断。

**配置**：SM80_A100_1SM_NOSUBCORE, `--max-completed-cta 5`, `bfs_ima_small`, L1 trace + GRASP trace 开启。

**脚本改动**：`analyze_grasp_iterations_v2.py` 新增 `--iteration-mode bfs`：
- BFS kernel ×4 展开，5 组 (index_pc, data_pc)，来自 golden chain CSV
- Boundary PCs = {0x01d0 (prologue), 0x0640 (unroll_0)}，每个 loop trip 一个 iteration
- 默认 merge_window=300（同一 LDG 的 mem_fetch 在 L1 trace 中散布最大 ~240 cycles）

**结果**（GRASP, 1SM 5CTA）：

| Warp | Iterations | avg_latency | idx_hit_rate | data_hit_rate |
|------|-----------|-------------|-------------|--------------|
| 1 | 122 | 9004.8 | 49.6% | 24.8% |
| 2 | 132 | — | — | — |
| 3 | 126 | — | — | — |

对比之前 boundary=0x0c0 的 13 iteration（BFS 波级），现在 ~125 iteration 是循环级粒度。

**输出文件**：`ima_plan/05_implementation/grasp_real_diag/bfs_iter/`

**日志文件**：
- Baseline: `result/log/bfs_iter_base2.log` + `result/L1cache_trace/bfs_iter_base2_l1.csv`
- GRASP: `result/log/bfs_iter_grasp3.log` + `result/L1cache_trace/bfs_iter_grasp3_l1.csv` + `result/grasp_trace/bfs_iter_grasp3_grasp.csv`

---

## 7f. Stride 学习 Bug 修复（2026-03-31）

### 问题

BFS event timeline 中发现 stride 值出现百万级异常（如 iter_stride=17605328），而非预期的 4（prologue）或 16（4x unrolled loop）。

### 根因分析

三层问题叠加：
1. **`update_stride()` 允许覆盖已收敛 stride**（`grasp_tables.cc:148-151`）：当 CTA 完成、warp slot 被新 CTA 复用时，跨 CTA 的地址差覆盖了正确的 stride
2. **`on_warp_exit()` 未清理 stride observation**（`grasp_prefetcher.cc:253-258`）：旧 CTA 的 `last_addr` 残留在 CT 中
3. **trace-driven warp exit hook 缺失**（`trace_driven.cc:1361-1364`）：trace-driven 模式的 warp exit 走独立代码路径，漏掉了 GRASP hook，导致 cleanup 代码从未执行

### 修复（三处）

| 文件 | 改动 | 行数 |
|------|------|------|
| `grasp_tables.cc` | stride 收敛后冻结，不再允许覆盖 | -3 行 |
| `grasp_prefetcher.cc` | `on_warp_exit()` 清理退出 warp 的 stride observation | +13 行 |
| `trace_driven.cc` | 补 trace-driven warp exit 的 GRASP hook | +3 行 |

### 验证结果（bfs_ima_small, 108SM 全量）

| 指标 | 修复前 | 修复后 | 变化 |
|------|--------|--------|------|
| IPC | 30.34 | 30.47 | +0.43% |
| Accuracy (SM0) | 55.89% | 58.97% | +3.08pp |
| pf_useful (SM0) | 11,102 | 14,113 | +27.1% |
| data_enqueued (SM0) | 9,842 | 18,265 | +85.6% |
| Coverage (SM0) | 33.86% | 38.88% | +5.02pp |
| PT hit rate (SM0) | 29.2% | 60.2% | +31.0pp |
| Index RFAIL rate | 18.3% | 12.3% | -6.0pp |
| Index timeliness | 95.85% | 89.98% | -5.87pp |
| Data timeliness | 68.77% | 75.00% | +6.23pp |

**STRIDE_CONVERGE 验证**（1SM trace）：修复后只出现 stride=4（PC 0x01D0）和 stride=16（PC 0x0640-0x1060）。PC 0x00C0（worklist）不再学习到错误 stride。wild delta 完全消除。

### 诊断产出

- Event timeline: `ima_plan/05_implementation/grasp_real_diag/bfs_stride_fix/event_timeline_warp{1,2,3}.txt`
- Baseline comparison: 同目录 `baseline_comparison_warp{1,2,3}.txt`
- 实验 log: `result/log/bfs_stride_fix_test.log`（108SM）、`bfs_warp_exit_fix.log`（1SM, 10CTA, hook 验证）

### 遗留

- 回归测试待运行（`grasp_regression.sh check`）
- Pair table miss 41%（stride 越过邻接表末尾的固有限制，非 bug）

---

## 7b. Speculative Stride 实验（2026-04-02）

**版本**：submodule commit `9066f5f`，默认关闭（`-grasp_speculative_stride 0`）

**机制**：CT entry 在首次 stride observation 时用预设值立即标记 `stride_valid=true`，第二次 observation 确认或修正。per-chain stride_hint 从 chain CSV 读取（SASS 分析得出）。

**stride_hint 值（SASS 分析）**：
- Inner loop base (int*): 4
- Unrolled ×4: 16
- Unrolled ×16 (SpMV): 64
- Thread-ID 索引（无循环）: 0 (disabled)

**回归结果**（`-grasp_speculative_stride 4` + CSV stride_hint）：

| Workload | Baseline | 旧 GRASP | Speculative | vs 旧 GRASP |
|----------|----------|----------|-------------|-------------|
| BFS | 23.56 | 29.75 | 30.81 | +3.56% |
| SSSP | 28.81 | 34.28 | 35.39 | +3.23% |
| SpMV | 129.68 | 164.12 | 175.35 | +6.84% |
| BC | 37.65 | 44.61 | 40.79 | -8.56% |
| Geomean | | | | +1.09% |

**BC 退化分析**：stride 值本身正确（inner=4, unrolled=16, outer=0），但推测机制本身导致退化。原因待进一步排查。

**决定**：默认关闭，记录为 DSE 参数（见 `dse_ct_reset_policy.md`）。

**同时发现**：CT 在不同 kernel 切换时全量 reset stride（BFS 每轮 level 重训练 7K-29K cycles），也记录为 DSE 参数。

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
| `result/log/bfs_stride_fix_test.log` | bfs_ima_small stride fix 验证 (108SM 全量) |
| `result/log/bfs_stride_fix_diag2.log` | bfs_ima_small stride fix 诊断 (1SM, 10CTA, L1+GRASP trace) |
| `result/log/bfs_warp_exit_fix.log` | bfs_ima_small warp exit hook 验证 (1SM, 10CTA, GRASP trace) |
