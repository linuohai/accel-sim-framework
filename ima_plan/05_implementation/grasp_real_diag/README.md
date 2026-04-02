# GRASP Real Workload Diagnostic

> 日期：2026-03-27
> 目的：在真实 Gardenia 图算法上评估 GRASP，定位性能瓶颈

---

## 1. Full-Scale IPC 对比 (ima_small, SM80_A100 108SM)

| Benchmark | trace_key | NP IPC | GRASP IPC | Delta | 说明 |
|-----------|-----------|-------:|----------:|:-----:|------|
| **BFS** | `bfs_ima_small` | 23.56 | 29.75 | **+26.3%** | v6 dedup 修复后从 -0.6% 跃升 |
| **SpMV** | `spmv_ima_med` | 129.68 | 164.12 | **+26.6%** | v6 冗余 PF 减少 77% |
| **SSSP** | `sssp_ima_small` | 28.81 | 34.28 | **+19.0%** | 稳定 IMA 密度 24.6% |
| **BC** | `bc_ima_small` | 37.65 | 44.61 | **+18.5%** | 双向遍历，chain 最多 (19) |
| CC | `cc_ima_small` | 368.07 | 368.07 | 0.0% | 无 IMA chain，零开销 |

**GRASP 配置**: `grasp_ist_distance=1`, `grasp_ct_size=32`, `grasp_tt_size=8`, `grasp_ist_ipt_size=64`, `grasp_ist_confidence=2`, `grasp_prb_capacity=1024`, `grasp_tc_mshr_threshold=80`。chain CSV 使用 `ima_plan/05_implementation/ima_pair_table/golden/strict_selected_chain_instances.csv`。

> **注意**：配置中还存在 `gpgpu_ima_prefetch_distance=4` 等 legacy IMA prefetcher 参数，但 `gpgpu_ima_prefetch_enable=0`（已禁用）。GRASP 与 legacy prefetcher 互斥（`shader.cc:3842-3863`），GRASP 的预取距离仅由 `grasp_ist_distance` 控制。

**实验命令**:
```bash
EVAL="--no-l1-trace --no-l2-trace --no-hbm-trace --no-issue-trace --no-stall-reason-pc-stats"
./traceL1 $EVAL <trace_key> <log_name>           # baseline
./traceL1 --grasp $EVAL <trace_key> <log_name>   # GRASP
```

---

## 2. BFS 小规模诊断 (1SM, 5 CTA)

**配置**: `SM80_A100_1SM_NOSUBCORE`, `--max-completed-cta 5`, `bfs_ima_small`

### GRASP 活动统计

| 指标 | 值 | 评估 |
|------|-----|------|
| Chain Detection | 837 CHAIN_DETECT events → 6 unique CT entries (24 CT_INSERT events) | 正常 |
| Stride 收敛 | 22/24 CT_INSERT converged = **92%** (6 entries 全部收敛) | 正常 |
| Index PF inject | 141k / 1.1M enqueued = **12.6%** | 严重积压 |
| Data PF inject | 17.6k / 18.6k = 94.6% | 正常 |
| PF RFAIL | 65k / 159k = **41%** | MSHR 饱和 |
| Per-iter speedup | 0.13x–7.73x (avg **0.82x**) | 净负面 |

### 根因

1. **MSHR 饱和**：BFS demand load 已填满 MSHR，GRASP 添加 141k 额外请求 → 41% RFAIL
2. **Index PF 洪泛**：1.1M 入队但仅 12.6% 注入 → 队列溢出
3. **Throttle 不足**：80% MSHR 阈值未能在 BFS 场景下有效抑制

### 1SM vs 108SM 差异

| 环境 | IPC Delta | 原因 |
|------|-----------|------|
| 1SM (5 CTA) | **-3.1%** | 单 MSHR 承受全部 demand + PF 流量 (NP=1.2888, GRASP=1.2493) |
| 108SM (全量, v6) | **+26.3%** | v6 dedup 修复后 MSHR 洪泛消除 (NP=23.56, GRASP=29.75) |

### 文件

- `bfs/event_timeline_warp{1,2,3}.txt` — 逐 iteration 事件流
- `bfs/baseline_comparison_warp{1,2,3}.txt` — Baseline vs GRASP 对比
- `bfs/format_a_warp{1,2,3}.{txt,csv}` — 摘要表
- `bfs/analysis_log.txt` — 分析汇总

---

## 3. SpMV 小规模诊断 (1SM, 10 CTA)

**配置**: `SM80_A100_1SM_NOSUBCORE`, `--max-completed-cta 10`, `spmv_ima_med`
**GRASP 版本**: v6（含 P1-P4 修复：per-warp CT dedup + DATA PF 32B sector 对齐）

### GRASP 活动统计

| 指标 | 修复前 (v5) | 修复后 (v6) | 变化 |
|------|------------|------------|------|
| Chain Detection | 169 → 28 CT | 94 → 28 CT | CD 次数减少（dedup 生效） |
| Stride 收敛 | 20/28 = 71% | 20/28 = **71%** | 不变 |
| DEMAND_CT_HIT | 18,805 | **12,133** | **-35%**（per-warp dedup 消除冗余） |
| Index PF enqueue | 159,679 | **36,347** | **-77%**（冗余 PF 生成消除） |
| Index PF inject | 39,294 | 23,848 | inject 率提升 (24.5% → 65.6%) |
| Data PF enqueue | 7,763 | 6,178 | 略减 |
| Data PF inject | 2,232 | 2,352 | 基本持平 |
| PF RFAIL | 15,120 (36%) | **6,681 (25%)** | MSHR 争用减轻 |
| PF L1 HIT | 6,311 | 7,801 | 有效命中增加 |
| 1SM IPC Delta | +0.8% | **+2.7%** | 改善 |

### 根因（仍存在的问题）

1. **×16 展开破坏 stride 学习**：29 条 chain 来自同一源码行循环展开，8 条 stride 不收敛（与修复前相同）
2. **Data PF 交付率仍然偏低**：2,352 / 6,178 = 38%（修复前 28.7%，略有改善）
3. **MSHR 争用缓解但未消除**：RFAIL 从 36% 降至 25%

### P1-P4 修复效果

| 修复项 | SpMV 上的效果 |
|--------|-------------|
| **P1** per-warp CT dedup | DEMAND_CT_HIT -35%, IDX_PF_ENQUEUE -77%, RFAIL -44% |
| **P2+P3** DATA PF 32B 对齐 | 地址从 byte 级 (`0x...9328`) → sector 级 (`0x...9f60`) |
| **P4** trace sector_addr | DEMAND_CT_HIT detail 中显示触发 sector 地址 |

### 1SM vs 108SM 差异

| 环境 | 修复前 | 修复后 | 原因 |
|------|--------|--------|------|
| 1SM (10 CTA) | +0.8% | **+2.7%** | dedup 减少 MSHR 争用 |
| 108SM (全量) | +15.6% | **+26.6%** | 冗余 PF 减少 77% 效果显著 (NP=129.68, GRASP=164.12) |

### 文件

- `spmv/event_timeline_warp{1,2,3}.txt` — 逐 iteration 事件流（`--boundary-pcs 0x200 --merge-window 300`）
- `spmv/baseline_comparison_warp{1,2,3}.txt` — Baseline vs GRASP 对比
- `spmv/format_a_warp{1,2,3}.{txt,csv}` — 摘要表
- `spmv/analysis_log.txt` — 分析汇总

---

## 4. 分析工具

使用泛化版分析脚本 `ima_plan/04_prefetcher_design/analyze_grasp_iterations_v2.py`（从 tiny_case 版本泛化而来）。

**BFS 分析命令（波级，boundary=worklist pop）**:
```bash
python3 analyze_grasp_iterations_v2.py \
    --chain-csv ima_plan/05_implementation/ima_pair_table/golden/bfs_linear_base_strict.csv \
    --boundary-pcs 0x0c0 \
    --grasp-dir <grasp_dir> --baseline-dir <baseline_dir> \
    --warps 1,2,3 --format all
```

**BFS 分析命令（循环级，内置 BFS PC 配置）**:
```bash
python3 analyze_grasp_iterations_v2.py \
    --iteration-mode bfs \
    --grasp-dir <grasp_dir> --baseline-dir <baseline_dir> \
    --warps 1,2,3 --format all
```
- `--iteration-mode bfs` 自动设置 boundary_pcs={0x01d0, 0x0640}、merge_window=300
- 每个 main loop trip（×4 展开）= 1 个 iteration，prologue 每次 = 1 个 iteration
- 不需要 `--chain-csv`（PC 内置），但可选提供用于 GRASP event 过滤

**SpMV 分析命令**:
```bash
python3 analyze_grasp_iterations_v2.py \
    --chain-csv ima_plan/05_implementation/ima_pair_table/golden/spmv_base_strict.csv \
    --boundary-pcs 0x200 --merge-window 300 \
    --grasp-dir <grasp_dir> --baseline-dir <baseline_dir> \
    --warps 1,2,3 --format all
```

- `--boundary-pcs 0x0c0`：BFS 用 worklist PC 做迭代边界（非 CSR 内层循环 PC）
- `--boundary-pcs 0x200`：SpMV 用 `row_ptr` 访问做行边界（非展开的 `col_idx` PC）
- `--merge-window 300`：合并 300 cycle 内的 boundary 事件（同一 warp 指令的多 sector）

---

## 5. 待改进方向

| 方向 | 预期效果 | 复杂度 | 状态 |
|------|---------|--------|------|
| ~~降低 Throttle 阈值 (80% → 50-60%)~~ | BFS RFAIL 减少 | 改 1 个参数 | ✅ 已实现 |
| ~~`ist_distance=4` 全量实验~~ | 预取更提前，覆盖 L2 latency | 改 1 个参数 | ✅ 已在消融实验验证 (SSSP +42.2%) |
| 展开 chain 合并 (29→~5 等价类) | SpMV stride 收敛率提升 | 需 chain CSV 预处理 | 待实现 |
| BC/SSSP 诊断分析 | 理解为何 BC 收益最高 | 跑 1SM 分析 | 待实现 |

---

## 6. 日志文件索引

| 日志 | 说明 |
|------|------|
| `result/log/{bfs,sssp,bc,cc}_small_v6_{np,grasp}.log` | **108SM 全量实验 (v6, §1 数据来源)** |
| `result/log/spmv_med_v6_{np,grasp}.log` | **SpMV 108SM 全量 (v6, §1 数据来源)** |
| `result/log/bfs_diag_base2.log` | BFS 1SM baseline (§2 数据来源) |
| `result/log/bfs_diag_grasp2.log` | BFS 1SM GRASP (§2 数据来源) |
| `result/log/spmv_diag_base2.log` | SpMV 1SM baseline v5 (§3 修复前) |
| `result/log/spmv_diag_grasp2.log` | SpMV 1SM GRASP v5 (§3 修复前) |
| `result/log/spmv_base_v6.log` | SpMV 1SM baseline v6 (§3 修复后) |
| `result/log/spmv_pf_v6.log` | SpMV 1SM GRASP v6 (§3 修复后) |
| `result/log/{bfs,sssp,bc,cc}_small_{np,grasp}.log` | 108SM 全量实验 (pre-v6, 旧版) |
| `result/log/spmv_med_{np,grasp}.log` | SpMV 108SM 全量 (pre-v6, 旧版) |
