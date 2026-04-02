# GRASP 小 Case Debug 方法学

> 最近更新: 2026-04-01

针对 GRASP IMA prefetcher 的小型测例（1SM / limited CTA）debug 规范。核心问题：IMA Data hit rate 偏低——对每个 data miss，追溯它是不是"真正的 miss"。

## 0. 工具链与数据源

### 工具

| 工具 | 路径 | 用途 |
|------|------|------|
| `extract_pair_table_from_trace.py` | `debug/` | 从原始 `.traceg` 提取 ground truth `(idx_addr, data_addr)` 映射 |
| `analyze_data_miss_rootcause.py` | `debug/` | 交叉比对三件套，分类每个 data miss 的 root cause |
| `analyze_grasp_iterations_v2.py` | `04_prefetcher_design/` | 逐 iteration 事件时间线 + baseline 对比 |

### 三件套（每次 debug 必需的数据文件）

| 文件 | 来源 | 内容 |
|------|------|------|
| `*_l1.csv` | L1 trace（baseline + GRASP 各一份） | 每次 L1 cache 访问的 cycle/addr/status/PC |
| `*_grasp.csv` | GRASP event trace | GRASP 管线事件（enqueue/inject/fill/L1_result） |
| `*_pair_table.csv` | GRASP pair table dump 或 `extract_pair_table_from_trace.py` | ground truth: `(idx_addr, data_addr)` per warp |

---

## 1. Phase 1: 实验准备（Run）

### 目标

生成 debug 三件套：baseline L1 trace + GRASP L1 trace + GRASP event trace + pair table。

### 命令模板

以 BFS roadnet 为例（替换 `bfs_roadnet` 和 `bfs` 为目标 workload）：

**Baseline（无 GRASP）：**
```bash
./traceL1 --max-completed-cta 50 \
    --no-l2-trace --no-hbm-trace \
    bfs_roadnet bfs_1sm_baseline
```

**GRASP + trace：**
```bash
./traceL1 --grasp-trace --max-completed-cta 50 \
    --no-l2-trace --no-hbm-trace \
    bfs_roadnet bfs_1sm_grasp
```

`--grasp-trace` 自动启用：
- GRASP prefetcher（`-grasp_enable 1`）
- 结构化事件 trace（`-grasp_trace_enable 1`，输出到 `result/grasp_trace/<log_name>_grasp.csv`）
- Pair table dump（输出到 `result/grasp_trace/<log_name>_pair_table.csv`）
- L1 trace（输出到 `result/L1cache_trace/<log_name>_l1.csv`）

### 输出文件

```
result/log/bfs_1sm_baseline.log          # baseline 仿真日志
result/log/bfs_1sm_grasp.log             # GRASP 仿真日志
result/L1cache_trace/bfs_1sm_baseline_l1.csv   # baseline L1 trace
result/L1cache_trace/bfs_1sm_grasp_l1.csv      # GRASP L1 trace
result/grasp_trace/bfs_1sm_grasp_grasp.csv     # GRASP 事件 trace
result/grasp_trace/bfs_1sm_grasp_pair_table.csv # GRASP 运行时 pair table dump
```

### 完整 pair table（可选但推荐）

GRASP 运行时 dump 的 pair table 只包含实际被注册的地址对，可能有遗漏。如需完整 ground truth：

```bash
python3 debug/extract_pair_table_from_trace.py \
    --trace-dir /path/to/traces/bfs_roadnet/ \
    --algorithm bfs --impl linear_base \
    --output debug/bfs_full_pair_table.csv
```

### 分析报告目录规范

每个 debug case 的所有数据和分析产物统一放在 `debug/<case_name>/` 目录下：

```
debug/<case_name>/
├── <case_name>.log                    # GRASP 仿真日志（或 symlink）
├── <case_name>_l1.csv                 # GRASP L1 trace
├── <case_name>_grasp.csv              # GRASP event trace
├── <case_name>_pair_table.csv         # runtime pair table dump
├── <case_name>_detail.csv             # root cause detail CSV（Phase 3 输出）
├── baseline/
│   └── <baseline_name>_l1.csv         # baseline L1 trace
├── analysis/                          # Phase 4 输出（analyze_grasp_iterations_v2）
│   ├── analysis_log.txt
│   ├── event_timeline_warp*.txt
│   ├── baseline_comparison_warp*.txt
│   └── format_a_warp*.txt
└── report.md                          # 本次分析的完整报告
```

**`report.md` 必须包含：**

1. 实验配置（workload, SM 数, CTA 数, GRASP 版本/参数）
2. Phase 2 Triage 指标表（Coverage, Timeliness, PT Hit Rate）+ baseline vs GRASP IMA_DEMAND 对比
3. Phase 3 Root Cause 分布表（含占比）
4. Phase 3.5: FILL_DISPATCH targets 分布 + PT miss 交叉比对结果
5. 关键发现与结论
6. **每项数据的来源文件路径**（便于复现和验证）

### Checklist

- [ ] baseline 和 GRASP 使用相同 `--max-completed-cta`
- [ ] 检查两者 log 的 `IMA_DEMAND:` 行，确认 `total_reads` 基本一致
- [ ] GRASP log 中存在 `GRASP_CONFIG:` 行（确认 GRASP 已启用）
- [ ] 所有数据文件和分析产物放在 `debug/<case_name>/` 目录下
- [ ] `report.md` 中每项数据标注了来源文件路径

---

## 2. Phase 2: 问题量化（Triage）

### 目标

从 log 中提取全局指标，判断主要瓶颈类型。

### 提取命令

```bash
# 最终 IMA_DEMAND（取 log 最后一条）
grep "^IMA_DEMAND:" result/log/bfs_1sm_baseline.log | tail -1
grep "^IMA_DEMAND:" result/log/bfs_1sm_grasp.log   | tail -1

# Pair Table hit/miss（从 GRASP_SM0 行提取）
grep "pair_table(" result/log/bfs_1sm_grasp.log | tail -1
```

### 关键指标

从 `IMA_DEMAND:` 行提取以下指标，baseline 和 GRASP 各一份：

| 指标 | 字段 | 说明 |
|------|------|------|
| Index Hit Rate | `index_hits / index_reads` | Index load 的 L1 命中率 |
| Data Hit Rate | `data_hits / data_reads` | Data load 的 L1 命中率（核心关注） |
| Data Timeliness | `data_hits / (data_hits + data_hit_reserved)` | 预取及时性 |
| Data Coverage | `1 - grasp_data_misses / baseline_data_misses` | GRASP 消灭了多少 miss |
| PT Hit Rate | `pair_table_hit / (pair_table_hit + pair_table_miss)` | Pair table 查询成功率 |

### 判断瓶颈类型

| 观察 | 瓶颈类型 | 下一步 |
|------|----------|--------|
| Data Coverage 低（<20%） | **覆盖率问题**——GRASP 没覆盖到多数 miss | Phase 3 归因 |
| Data Timeliness 低（<70%）但 Coverage 尚可 | **及时性问题**——预取了但不够快 | 检查 distance 参数 |
| PT Hit Rate 低（<50%） | **Pair Table 瓶颈**——无法查到 data 地址 | 检查 PT 容量/scope |
| Data Hit Rate 反而下降 | **干扰问题**——prefetch 挤占 cache | 检查 RFAIL 和 throttle |

---

## 3. Phase 3: Root Cause 归因（核心）

### 前提：pair table ground truth 是整条链路的基石

当我们看到一个 data miss（已知 `data_addr` 和 `warp_id`），**我们并不直接知道对应的 index address 是什么**——因为 IMA 的本质就是 `data_addr = mem[idx_addr]`，地址是间接的。

**Step 1 的作用就是解决这个问题**：拿着 `(data_addr, warp_id)` 去 pair table CSV 反查，得到 `(chain_id, idx_addr, idx_pc)`。有了 `idx_addr`，后续所有步骤才能在 GRASP event trace 中追踪这个 index 的处理情况。

示例：
```
已知: data_addr=0x7fc4b7c04e1c, warp_id=0, cycle=13084
反查: pair_table.csv → chain_id=2, idx_addr=0x7fc4d16cb9b0, idx_pc=0x1d0
计算: idx_sector = 0x7fc4d16cb9b0 & ~0x1F = 0x7fc4d16cb9a0
后续: 用 idx_sector 在 GRASP trace 中搜索 IDX_PF_ENQUEUE 等事件
```

### 归因管线（7 步）

给定一个 data demand miss（L1 trace: data PC, l1_status=MISS/SECTOR_MISS），逐步追溯。**每步失败就终止，返回对应 root cause。**

```
data_miss(addr=D, warp=W, cycle=T)
  │
  ▼ Step 0: 结构性 miss 判定
  │ 通过 pair table 反查 real_idx_addr → 查 L1 trace 确定 (warp, idx_pc) 的 batch 编号
  │ Batch 定义: 同一 (warp, idx_pc) 的连续 L1 demand，gap < 100 cycles 为同一 batch
  │ Batch 1 → STRUCTURAL_BATCH1（首次执行，无 stride 上下文）
  │ Batch 2 → STRUCTURAL_BATCH2（stride 收敛点，预测目标为 batch 3）
  │
  ▼ Step 1: pair table 反查  ← 整条链路的起点
  │ 用 (data_addr=D, warp_id=W) 查 pair_table.csv
  │ → 得到 (chain_id, idx_addr=I, idx_pc=P)
  │ → 计算 idx_sector = I & ~0x1F, data_sector = D & ~0x1F
  │ 找不到 → NOT_IN_PAIR_TABLE
  │
  ▼ Step 2: stride 是否收敛?
  │ GRASP trace: 是否有 STRIDE_CONVERGE(pc=P) 且 cycle <= T?
  │ 没有 → STRIDE_NOT_CONVERGED
  │
  ▼ Step 3: index prefetch 是否 enqueue?
  │ GRASP trace: 是否有 IDX_PF_ENQUEUE(warp=W, sector=idx_sector) 且 cycle < T?
  │ 没有 → IDX_NOT_TRIGGERED
  │
  ▼ Step 4: index prefetch 是否注入 L1?
  │ GRASP trace: enqueue 后、T 前，是否有 IDX_PF_INJECT(sector=idx_sector)?
  │ 没有 → IDX_PF_PENDING
  │ 有，但 L1_RESULT_RFAIL(kind=INDEX) → IDX_PF_RFAIL
  │
  ▼ Step 5: index 数据是否 fill 回来? pair table 是否命中?
  │ GRASP trace: inject 后、T 前，是否有 FILL_DISPATCH(sector=idx_sector)?
  │ 没有 → IDX_PF_PENDING（L2 还没返回）
  │ 有，检查 IDX_PF_INJECT detail 中 pair_hits
  │ pair_hits == 0 → PT_MISS
  │
  ▼ Step 6: data prefetch 是否 enqueue?
  │ GRASP trace: fill 后、T 前，是否有 DATA_PF_ENQUEUE(sector=data_sector)?
  │ 没有 → DATA_PF_THROTTLED
  │
  ▼ Step 7: data prefetch 的 L1 结果?
  │ GRASP trace: data enqueue 后、T 前的 L1_RESULT(sector=data_sector, kind=DATA):
  │ L1_RESULT_RFAIL → DATA_PF_RFAIL
  │ L1_RESULT_HIT/MISS 存在但 demand 仍 miss → EVICTED
  │ 无 L1 result → DATA_PF_PENDING
```

### Root Cause 详解

| Root Cause | 含义 | 判断依据 | 进一步排查 |
|------------|------|----------|-----------|
| **STRUCTURAL_BATCH1** | warp 在该 idx_pc 的首次执行，stride 未学习 | real_idx_addr 属于 (warp, idx_pc) 的第 1 个 batch | 不可避免，无需排查 |
| **STRUCTURAL_BATCH2** | stride 收敛点，首次预测目标为下一 batch | real_idx_addr 属于 (warp, idx_pc) 的第 2 个 batch | 不可避免，无需排查 |
| **NOT_IN_PAIR_TABLE** | data addr 在 ground truth 中无对应 index | pair table CSV 中搜 `(D, W)` 无结果 | pair table 未覆盖该 kernel？scope 设置？ |
| **STRIDE_NOT_CONVERGED** | stride 学习未完成，GRASP 不知道下个 index addr | GRASP trace 无 `STRIDE_CONVERGE(pc=P)` before T | IST 需要几个样本？跨 CTA 污染？ |
| **IDX_NOT_TRIGGERED** | stride 已收敛，但该 warp 的 index sector 未被 enqueue | GRASP trace 无 `IDX_PF_ENQUEUE(W, idx_sector)` before T | IST predict 是否触发？distance 配置？on_demand_load 是否执行？ |
| **IDX_PF_PENDING** | index PF 已 enqueue 但 L2 未返回 | 有 enqueue 但无 inject 或无 fill before T | PRB 深度？注入速率？ |
| **IDX_PF_RFAIL** | index PF 注入 L1 时 RESERVATION_FAIL | `L1_RESULT_RFAIL(kind=INDEX)` | RFAIL 原因：MSHR 满/miss queue 满/line alloc 失败 |
| **PT_MISS** | index fill 回来后，pair table 查不到对应 data addr | `IDX_PF_INJECT` detail `pair_hits=0` | PT 容量被淘汰？scope=per-warp 但值来自其他 warp？ |
| **DATA_PF_THROTTLED** | fill 回来但 data PF 未覆盖目标 data_sector | 有 `FILL_DISPATCH` 但无 `DATA_PF_ENQUEUE` for data_sector within time window | **注意归因陷阱**：脚本匹配最后一次 FILL，但正确的 data PF 可能由更早的 FILL 发出并 RFAIL。需全局搜索 `DATA_PF_ENQUEUE(data_sector)` 确认是否曾发出（见下方注意事项） |
| **DATA_PF_RFAIL** | data PF 注入 L1 时 RESERVATION_FAIL | `L1_RESULT_RFAIL(kind=DATA)` | 同 IDX_PF_RFAIL |
| **DATA_PF_PENDING** | data PF 已发出但还在飞行中 | 有 enqueue 但无 L1 result before T | **及时性问题**：distance 不够？ |
| **EVICTED** | data PF 成功 fill 到 L1，但 demand 到达前被替换 | `L1_RESULT_HIT/MISS(kind=DATA)` 存在但 demand 仍 MISS | **cache 竞争**：prefetch 太早？cache 太小？ |

### 归因陷阱：DATA_PF_THROTTLED 中的隐藏 RFAIL

归因脚本匹配**最后一次** IDX_PF_INJECT → FILL_DISPATCH 链来判断 data PF 状态。但同一 idx_sector 可能被多次预取（不同 batch 的 stride prediction 可能落在同一 sector）。正确的 data PF 可能由**更早的**预测发出，但遭遇了 L1_RESULT_RFAIL。后续预测再次命中同一 sector 时，pair table lookup 命中的是不同 lane 的 addr_map 条目，data PF 去了不同 sector。

**验证方法**：对 DATA_PF_THROTTLED 条目，全局搜索 `DATA_PF_ENQUEUE(data_sector)` + `L1_RESULT_RFAIL(data_sector)`。如果找到 RFAIL 记录，真实根因是 **DATA_PF_RFAIL**。

**BFS 1SM 实例**：warp=1 L29 batch 3 的 data miss (0x7fc4b7d5a2c0)。cycle 548974 GRASP 正确 enqueue 了此地址的 data PF，但 cycle 548976 遭遇 L1_RESULT_RFAIL。分析脚本匹配了 cycle 551058 的后续 FILL（来自 batch 3 自身的 idx PF），该 FILL 的 pair_hits=1 命中了其他 lane 的条目，导致误判为 DATA_PF_THROTTLED。

### 运行 Root Cause 分析

```bash
python3 debug/analyze_data_miss_rootcause.py \
    --pair-table result/grasp_trace/bfs_1sm_grasp_pair_table.csv \
    --l1-trace   result/L1cache_trace/bfs_1sm_grasp_l1.csv \
    --grasp-trace result/grasp_trace/bfs_1sm_grasp_grasp.csv \
    --data-pcs  "0x0200,0x0670,0x09d0,0x0d30,0x1090" \
    --index-pcs "0x01d0,0x0640,0x09a0,0x0d00,0x1060" \
    --output debug/bfs_rootcause_detail.csv
```

**重要：`--data-pcs` 和 `--index-pcs` 必须包含 golden chain CSV 中该 workload 的所有 chain PC，不能遗漏。** 用以下命令提取完整 PC 集合：

```bash
# 从 golden chain CSV 提取（以 bfs 为例）
grep "^bfs," ima_plan/05_implementation/ima_pair_table/golden/strict_selected_chain_instances.csv | \
    awk -F, '{print "idx="$6, "data="$10}' | sort -u
```

验证方法：分析完成后，L1 trace 中 data PC non-RFAIL/non-FILL 条目数应与 `IMA_DEMAND data_reads` 一致。若不一致，首先检查 PC 集合是否完整。

### 根据 Top Root Cause 的下一步行动

| Top Root Cause | 下一步 |
|----------------|--------|
| STRUCTURAL_BATCH1/2 | 预取器设计上无法避免的 miss，从非结构性 miss 的分析中排除 |
| IDX_NOT_TRIGGERED | 用 Phase 4 timeline 检查 stride predict 是否在目标 iteration 触发；检查 `GRASP_IST` stats |
| PT_MISS | 检查 PT hit rate（Phase 2）；考虑扩大 PT 容量或调整 scope |
| IDX_PF_RFAIL | 检查 `GRASP_RFAIL` 输出的各原因占比；考虑降低 prefetch 积极性 |
| DATA_PF_THROTTLED | 统计 FILL_DISPATCH targets=0 占比（Phase 3.5 Step A）；与 PT_MISS 合并视为同一类瓶颈 |
| EVICTED | 用 Phase 4 timeline 对比 prefetch fill 时间 vs demand 到达时间 |
| STRIDE_NOT_CONVERGED | 前期固有问题，通常占比小；关注是否跨 CTA 污染 |

### PT miss 深度分析（Phase 3.5）

当 PT_MISS + DATA_PF_THROTTLED 合计占比较大时（>30%），需进一步区分子原因。

#### Step A: FILL_DISPATCH targets=0 占比

验证 DATA_PF_THROTTLED 中有多少是 targets=0（per-lane PT miss）vs 真正 throttle：

```bash
# targets 分布（数据来源: *_grasp.csv）
grep "FILL_DISPATCH" <case>_grasp.csv | grep -oP 'targets=\d+' | sort | uniq -c | sort -rn

# 真正的 throttle 次数（数据来源: *.log）
grep "throttle_suppressed" <case>.log | tail -1
```

如果 `targets=0` 远大于 `throttle_suppressed`，说明 DATA_PF_THROTTLED 本质是 PT miss。

#### Step B: PT miss 地址在 runtime pair table 中的交叉比对

将 PT miss 的 `(warp_id, idx_addr)` 与 runtime pair table dump 做三分类：

```bash
# 需要的数据:
#   1. PT miss 地址: 从 rootcause detail CSV (root_cause=PT_MISS) 或 debug log (GRASP_PT_MISS)
#   2. Runtime PT dump: *_pair_table.csv (列: warp_id, idx_addr, data_addr)
#
# 三分类:
#   A. 同一 warp runtime PT 已有 → 不应发生（边界 timing 问题）
#   B. 其他 warp runtime PT 已有 → per-warp scope 导致
#   C. 任何 warp 都没有 → addr_map 未填充（prefetch 超前于 demand）
```

**BFS 1SM 实测结果**: 98.8% 是类别 C（addr_map 未填充），仅 1.1% 是类别 B（per-warp scope）。说明 PT miss 的根因是 **GRASP prefetch 超前于 demand，addr_map 中尚无对应映射**。

---

## 4. Phase 4: 逐 Iteration 深挖（Drill Down）

### 目标

选择特定 warp/iteration，追踪 GRASP 在单次循环中的完整行为。

### 工具

```bash
python3 ima_plan/04_prefetcher_design/analyze_grasp_iterations_v2.py \
    --grasp-dir    debug/bfs_1sm_rootcause/ \
    --baseline-dir debug/bfs_1sm_rootcause/baseline/ \
    --chain-csv    ima_plan/05_implementation/ima_pair_table/golden/strict_selected_chain_instances.csv \
    --algorithm bfs \
    --warps 0,1 \
    --format all \
    --output-dir debug/bfs_1sm_rootcause/analysis/
```

### 三种输出格式的用途

| 格式 | 文件 | 用途 |
|------|------|------|
| `summary` (format a) | `format_a_warp*.txt` | 每个 iteration 的 idx/data cycle + L1 status 概览，快速定位异常 iteration |
| `compare` (format c) | `baseline_comparison_warp*.txt` | baseline vs GRASP 逐 iteration 对比，找 speedup < 1.0 的退化 iteration |
| `timeline` (format b) | `event_timeline_warp*.txt` | 逐 cycle 事件流：L1 demand + GRASP 事件交织，追踪单次 prefetch 的完整生命周期 |

### 关键观察模式

**模式 A：GRASP 完全没生效（所有 iteration speedup = 1.0x）**
- 看 `analysis_log.txt` 确认 stride convergence 时间点
- 在 timeline 中搜索 `STRIDE_CONVERGE` 事件首次出现的 cycle
- 对比该 cycle 前后的 iteration 行为变化

**模式 B：GRASP 生效但 data 仍 miss**
- 在 timeline 中找到对应 iteration
- 检查是否有 `IDX_PF_ENQUEUE` → `IDX_PF_INJECT` → `FILL_DISPATCH` → `DATA_PF_ENQUEUE` → `DATA_PF_INJECT` 完整链路
- 链路断在哪一步 → 对应 Phase 3 的 root cause

**模式 C：Prefetch 成功 fill 但 demand 仍 miss（EVICTED）**
- 在 timeline 中找到 `DATA_PF_INJECT` → `L1_RESULT_MISS`（PF 成功进入 L2 pipeline）
- 找到对应的 demand MISS 事件
- 计算 fill 到 demand 之间的 cycle gap——gap 越大越可能被 evict

---

## 5. Phase 5: 假设验证与修复（Fix & Verify）

### 流程

1. 基于 Phase 3/4 确定 root cause 和假设
2. 修改 GRASP 代码或配置
3. 重跑**同一个小 case**（相同 workload、相同 `--max-completed-cta`）
4. 对比修改前后：
   - `IMA_DEMAND:` data_misses 变化
   - Root cause 分布变化
   - PT hit rate 变化
5. 确认其他 workload 未退化（`grasp_regression.sh check`）

### 对比 Checklist

- [ ] data_misses 减少了？减少了多少？
- [ ] 减少的 miss 从哪个 root cause 消失的？
- [ ] 是否引入了新的退化（index hit rate 下降？RFAIL 增加？）
- [ ] 回归测试 PASS？

---

## 附录：BFS 1SM 实战案例

### 实验配置

- Workload: BFS roadnet, 1 SM, ~50 CTA
- 数据目录: `debug/bfs_1sm_rootcause/`
- 7 条 IMA chain: index PCs `0xc0,0x1d0,0x640,0x9a0,0xd00,0x1060`, data PCs `0xf0,0x100,0x200,0x670,0x9d0,0xd30,0x1090`

### IMA_DEMAND 对比（完整运行，~201K reads）

**Index:**

| 指标 | Baseline | GRASP | Delta |
|------|----------|-------|-------|
| reads | 88,178 | 88,186 | +8 |
| hits | 41,791 (47.4%) | 36,827 (41.8%) | -4,964 |
| hit_reserved | 42 (0.05%) | 4,547 (5.2%) | +4,505 |
| misses | 46,345 (52.6%) | 46,812 (53.1%) | +467 |

**Data:**

| 指标 | Baseline | GRASP | Delta |
|------|----------|-------|-------|
| reads | 113,413 | 113,424 | +11 |
| hits | 20,686 (18.2%) | 26,459 (23.3%) | +5,773 |
| hit_reserved | 13,707 (12.1%) | 14,418 (12.7%) | +711 |
| misses | 79,020 (69.7%) | 72,547 (64.0%) | -6,473 |

Data Coverage: 8.2%  |  PT Hit Rate: 42.3% (25,080 / 59,276)

### Root Cause 分布（72,547 个 data miss = IMA_DEMAND `data_misses`）

| Root Cause | Count | % | 说明 |
|-----------|-------|---|------|
| IDX_NOT_TRIGGERED | 34,064 | 47.0% | 最大类：index PF 未发起 |
| DATA_PF_THROTTLED | 14,480 | 20.0% | 实质是 per-lane PT miss |
| IDX_PF_RFAIL | 7,985 | 11.0% | index PF 的 RESERVATION_FAIL |
| PT_MISS | 7,043 | 9.7% | pair table 查询失败 |
| STRIDE_NOT_CONVERGED | 6,477 | 8.9% | 训练未完成 |
| EVICTED | 1,898 | 2.6% | 预取成功但被 evict |
| DATA_PF_PENDING | 465 | 0.6% | data PF 在飞行中 |
| DATA_PF_RFAIL | 131 | 0.2% | data PF 的 RFAIL |
| IDX_PF_PENDING | 4 | 0.0% | index PF 在飞行中 |

### 关键发现

1. **IDX_NOT_TRIGGERED 47%** 是最大瓶颈——stride 已收敛但 index PF 没被 enqueue
2. **PT miss 类合计 28%**（PT_MISS 9.7% + DATA_PF_THROTTLED 中 PT miss ~13K），根因是 prefetch 超前于 demand
3. **STRIDE_NOT_CONVERGED 8.9%**——chain 0-1 的 stride 收敛较慢
4. **GRASP 反而降低了 index hit rate**（47.4% → 41.8%），额外的 MSHR 占用干扰了 demand

### Phase 3.5 深度分析结果

**FILL_DISPATCH targets 分布**（数据来源: `debug/bfs_1sm_rootcause/bfs_1sm_rootcause_grasp.csv`）：

| 分类 | 数量 | 占比 |
|------|------|------|
| targets=0 (PT 无映射) | 26,177 | 56.0% |
| targets>=1 (PT 有映射) | 20,585 | 44.0% |
| **总 FILL_DISPATCH** | **46,762** | |

实际 `throttle_suppressed`（数据来源: `debug/bfs_1sm_rootcause/bfs_1sm_rootcause.log`）: **1,017**

→ DATA_PF_THROTTLED (14,480) 中绝大多数是 `FILL_DISPATCH targets=0`（per-lane PT miss），非真正 throttle。

**PT miss 地址交叉比对**（数据来源: `debug/bfs_pt_miss_raw_sm0.txt` + `debug/bfs_1sm_rootcause/bfs_1sm_rootcause_pair_table.csv`）：

| 分类 | 数量 | 占比 | 含义 |
|------|------|------|------|
| 同一 warp runtime PT 已有 | 2 | 0.1% | timing 边界 |
| 其他 warp runtime PT 已有 | 25 | 1.1% | per-warp scope 问题 |
| **任何 warp 都没有** | **2,150** | **98.8%** | **addr_map 未填充** |

→ PT miss 的根因是 **prefetch 超前于 demand**，addr_map 尚无映射，不是 per-warp scope 问题。

### 修正后的 Root Cause 合并视图

将 PT_MISS 和 DATA_PF_THROTTLED 中的 PT miss 部分合并后：

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
