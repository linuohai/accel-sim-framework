> 最近更新: 2026-04-14

# Sim vs Real-GPU Bottleneck Consistency — FA / Decode 实验设计

## 1. 目标与范围

**目标**：在 A100 上对 Flash Attention (prefill) 和 flashinfer decode 两个算子，跨多种输入参数配置，对比 **GPGPU-Sim 模拟器**与 **Nsight Compute (ncu)** 各自得到的性能/瓶颈结论是否一致。

**定位**：内部实验，非论文。不追求 reviewer-proof 的覆盖面，重点是摸清"哪些 regime 下模拟器结论可信"。

**Out of scope**：
- IMA / GRASP prefetcher 相关分析（本实验与 IMA 无关）
- 硬件微架构参数 sweep（L1 size / MSHR 等，真机没对照）
- nsys timeline 级分析（只用 ncu per-kernel）

## 2. Workload 与 Config 矩阵（14 configs）

### FA — flash attention prefill (7 configs)

固定：dtype=fp16，调用 `gpu-app-collection/flash_attention/fa.py --batch_size B --seqlen S --nheads H --d D`

| # | batch | seqlen (S) | nheads (H) | head_dim (D) | 类别 |
|---|-------|------------|------------|--------------|------|
| 1 | 1 | 512 | 32 | 128 | seq 主轴 |
| 2 | 1 | 1024 | 32 | 128 | seq 主轴 |
| 3 | 1 | 2048 | 32 | 128 | seq 主轴 |
| 4 | 1 | 4096 | 32 | 128 | seq 主轴（复用现有 `fa4k` trace） |
| 5 | 1 | 8192 | 32 | 128 | seq 主轴 |
| 6 | 1 | 2048 | 32 | 64  | head_dim sensitivity |
| 7 | 1 | 2048 | 8  | 128 | 并发度 sensitivity（CTA 总数从 32 → 8） |

### Decode — flashinfer decode (7 configs)

固定：head_dim=128, num_heads=32, page_size=16, dtype=fp16, mode=paged
调用 `gpu-app-collection/src/cuda/flashinfer_decode/flashinfer_decode.py --batch B --seqlen-k K --num-heads 32 --num-kv-heads KH --head-dim 128`

| # | batch (B) | seqlen_k (K) | num_heads | num_kv_heads (KH) | 类别 |
|---|-----------|--------------|-----------|--------------------|------|
| 8  | 1  | 512  | 32 | 32 | KV 主轴（尝试复用 `fi_dec_512`，但其默认 kv_heads=8，可能需重抓） |
| 9  | 1  | 1024 | 32 | 32 | KV 主轴 |
| 10 | 1  | 2048 | 32 | 32 | KV 主轴 |
| 11 | 1  | 4096 | 32 | 32 | KV 主轴（尝试复用 `fi_dec_4k`） |
| 12 | 8  | 2048 | 32 | 32 | batch sensitivity |
| 13 | 32 | 2048 | 32 | 32 | batch sensitivity |
| 14 | 1  | 2048 | 32 | 8  | GQA sensitivity (4:1) |

> 现有 `fi_dec_512` / `fi_dec_4k` trace 的 `num_kv_heads` 默认值为 8（非 32），若口径不一致则必须重抓；提交 trace 前先核对抓取时的 config 参数。

**预期瓶颈迁移**：
- FA：seq 512 → compute-bound（low arithmetic intensity 但 per-CTA work 小），seq 8k → DRAM BW-bound
- Decode：全部 memory-bound，但 batch 1 低 occupancy（latency-bound 成分高），batch 32 饱和 BW

## 3. 工具链与数据流

```
                ┌──────────── A100 real GPU ──────────────┐
config (i) ──► accel-sim tracer ──► SASS trace (kernelslist.g)
   │                                          │
   │                                          ▼
   └──► ncu --set speed-of-light        GPGPU-Sim (sim)
        + MemoryWorkloadAnalysis              │
        + WarpStateStats                      │
                │                             │
                ▼                             ▼
        ncu_metrics.csv            sim log + EXPERIMENT SUMMARY
                │                             │
                └──────► merge & analyze ◄────┘
                            │
                            ▼
                 mape_report.md + roofline figs
```

**注意**：tracer 和 ncu 都独占 GPU，不能同时跑；仿真在 CPU 侧并行。

## 4. 指标映射（sim ↔ ncu）

| 维度 | sim 指标 | ncu 指标 | MAPE 计算 |
|------|---------|----------|-----------|
| 吞吐 | `gpu_sim_cycle` × period → runtime | `gpu__time_duration.sum` | yes |
| IPC | `gpu_tot_ipc` | `sm__inst_executed.avg.per_cycle_active` | yes |
| DRAM BW util | `dram_total_bw / peak_bw` | `dram__throughput.avg.pct_of_peak_sustained_elapsed` | yes |
| L1 hit rate | `l1D_cache_stats hit_rate` | `l1tex__t_sector_hit_rate.pct` | yes |
| L2 hit rate | `L2_cache_stats hit_rate` | `lts__t_sector_hit_rate.pct` | yes |
| SM busy | `gpu_tot_ipc / peak_ipc` | `sm__throughput.avg.pct_of_peak_sustained_elapsed` | yes |
| Stall 分布 | `warp_issue_idle breakdown` | `smsp__average_warp_latency_per_inst_issued` + stall reason 分桶 | Spearman / overlap@3 |

**瓶颈分类决策（方案 D 的定性部分，阈值先用当前定义，拿到数据后再调）**：
- **Compute-bound**: SM busy ≥ 70% 且 DRAM util < 50%
- **Memory BW-bound**: DRAM util ≥ 70%
- **Latency-bound**: SM busy < 50% 且 DRAM util < 50%（warp 等内存但 BW 没满）
- **Mixed**: 其他

两边各自按上述阈值打标签，输出 14×2 的一致性矩阵。**阈值为初始 tentative 值**，拿到 14 个 config 实测数据后检查分布（如大部分点都落在 "Mixed" 则阈值太严、反之太松），再调整定版。

## 5. 产出：数据文件、表格与图表

### 5.1 数据文件（原始 ground truth）

1. **`ncu_metrics.csv`** — 14 行 × ncu 指标列（per-kernel 展平，若多 kernel 则按 duration-weighted 聚合）
2. **`sim_metrics.csv`** — 14 行 × sim 指标列（列名与 ncu 对齐）
3. **`merged_metrics.csv`** — 两边并排，加 `*_mape` 和 `*_rel_err` 列，供绘图与 mape_report.md 读入

### 5.2 原始数据表格（写入 `mape_report.md`）

用户要求：报告必须包含完整原始数据，不只是结论。

- **Table 1 — Raw Metrics (14 × ~12 列)**：config_id / workload / param / `sim_IPC` / `real_IPC` / `sim_runtime_ms` / `real_runtime_ms` / `sim_dram_util` / `real_dram_util` / `sim_l1_hit` / `real_l1_hit` / `sim_l2_hit` / `real_l2_hit` / `sim_sm_busy` / `real_sm_busy`
- **Table 2 — MAPE Summary**：每个指标一行，`MAPE / median_abs_err / max_abs_err / #configs_within_20%`
- **Table 3 — Bottleneck Classification Matrix**：14 行，`sim_class` / `real_class` / `agree?`

### 5.3 图表规格（≥2 张多子图，混合图型，遵循 plot_util.py 风格）

严格遵循 `ima_plan/07_paper_outline/plot_style/` 规范（`apply_style()` + `CB10` + PDF+SVG + `constrained_layout`）。

按 `ima_plan/skills/paper-figure/` 的两阶段流程：
- **Phase 1（原型）**：先用默认风格出 PNG 原型，**用户打分后再定稿**
- **Phase 2（定稿）**：用户确认后改成 `plot_util.py` 风格输出 PDF+SVG

计划图表清单（有意混合 scatter / line / heatmap / bar / matrix 五种图型）：

| Fig | 类型 | 子图 | 描述 |
|-----|------|------|------|
| **Fig 1 — Roofline Overlay** ⭐ | Scatter + 折线 | **2 子图** (a) FA \| (b) Decode | 每个 config 一对点（sim, real），用短连线配对；背景是 A100 roofline（compute ceiling + DRAM BW ceiling）。视觉第一眼就能看出两者是否落在同一 regime |
| **Fig 2 — Metric MAPE Breakdown** ⭐ | bar + 误差线 | **6 子图 (2×3)** | 每个子图一个指标（IPC / runtime / DRAM util / L1 hit / L2 hit / SM busy），X 轴 14 个 config，Y 轴相对误差%；FA/Decode 用不同颜色；红虚线标 ±20% 合格线 |
| **Fig 3 — Bottleneck Trajectory** | Line plot | 单图 | X = seq/KV 主轴（log scale），Y = util%，sim/real × FA/Decode 多线叠画，展示瓶颈如何随输入规模迁移；BW-bound 区域用红色 shading |
| **Fig 4 — Stall Composition (Stacked)** | Stacked bar | 单图（14×2 组邻接柱） | 每个 config 两条邻接柱：左 Sim (实色)、右 Real (hatch)，每条柱按 top-5 stall reason 分段堆叠到 100%。颜色 = stall 类别，可直接肉眼比"每个类别在两侧占比是否接近" |

**Table 3**（bottleneck 分类一致性矩阵）原计划为 Fig 5，现改为 `mape_report.md` 中的纯表格，不再出图（14 行 × 列：sim_class / real_class / agree?）。

**满足用户要求**：
- ≥2 张多子图 → Fig 1、Fig 2 共 2 张 ✓
- 非纯柱状图 → scatter (Fig 1) / line (Fig 3) / stacked bar (Fig 4) / bar (Fig 2) 4 种图型 ✓
- 包含 roofline → Fig 1 ✓
- 原始数据表格 → `mape_report.md` Table 1/2/3 ✓

### 5.4 目录结构

实验产出根目录：`result/sim_vs_real_mape/`（与现有 `result/log/`、`result/plot/` 平级）

```
result/sim_vs_real_mape/
├── scripts/
│   ├── gen_configs.py              # 枚举 14 configs 并生成 trace/ncu/sim 调用参数
│   ├── run_tracer.sh               # accel-sim tracer 驱动
│   ├── run_ncu.sh                  # ncu 驱动
│   ├── run_sim.sh                  # GPGPU-Sim 并行驱动
│   ├── collect_metrics.py          # 解析 ncu csv + sim log → merged_metrics.csv
│   ├── classify_bottleneck.py      # 打瓶颈标签
│   ├── fig1_roofline.py            # 生产版
│   ├── fig2_mape_breakdown.py
│   ├── fig3_trajectory.py
│   ├── fig4_stall_stacked.py
│   └── _proto_*.py                 # Phase 1 原型脚本（带 _proto 前缀）
├── traces/                         # symlink 到实际 accel-sim trace 目录
├── ncu_out/
│   └── cfg_{01..14}.ncu-rep        # ncu 原始输出
├── sim_logs/
│   └── cfg_{01..14}.log
├── ncu_metrics.csv
├── sim_metrics.csv
├── merged_metrics.csv
├── mape_report.md                  # 含 Table 1/2/3
└── figures/
    ├── _proto_fig{1..4}.png        # 原型（打分用）
    ├── fig{1..4}.pdf               # 定稿
    └── fig{1..4}.svg
```

与 `ima_plan/` 隔离（本工作非 IMA 研究）。

## 6. 时间预算（今日）

| 阶段 | 预估 | 并行 |
|------|------|------|
| 1. Config 生成脚本 + trace harness | 1h | — |
| 2. A100 tracer 抓 ~11 个新 trace（复用 fa4k / fi_dec_512 / fi_dec_4k） | 1-2h | 串行独占 GPU |
| 3. A100 ncu 14 个 config（speed-of-light + 2 sections） | 1-2h | 串行，可与 (2) 交替 |
| 4. Sim 并行跑 14 config | 2-3h wall | CPU 并行 |
| 5. 分析脚本 + 出图 | 1h | — |
| **合计** | **6-8h** | |

## 7. 风险与回退

- **Risk 1**：某些 seq/KV 长度下 FA/flashinfer 的原始 CUDA 代码需要改输入参数才能跑。**回退**：若 3 个以上 config 无法抓 trace，降到 seq/KV 主轴各 3 点（共 6-8 config）。
- **Risk 2**：ncu full section 时间远超预期。**回退**：退到 `--set speed-of-light` 单 section，丢弃 stall reason 细粒度对比，保留 A/B/D 部分。
- **Risk 3**：sim 跑不完（某些 config kernel 太大）。**回退**：用 `--max-completed-cta` 限 CTA 数，ncu 也同步限（需确认 ncu 能否按 CTA 截断，通常不行 → 改用小 seq 点替代）。

## 8. 开放项确认（今日开工前）

- [x] **A100 独占** — 用户确认可独占
- [x] **现有 trace 复用** — 用户确认 `fa4k` 可直接用于 config #4；`fi_dec_512` / `fi_dec_4k` 若抓取时 `--num-kv-heads=8` 则与本 spec 口径不一致（本 spec 取 kv_heads=32），开工时读取现有 trace metadata 核对后决定
- [x] **源码参数化** — 已核实：`fa.py` 支持 `--batch_size/--seqlen/--nheads/--d`；`flashinfer_decode.py` 支持 `--batch/--seqlen-k/--num-heads/--num-kv-heads/--head-dim/--page-size`，无需改源码

## 9. 用户偏好 / 显式约束

来自 brainstorm 对话的显式要求，后续 implementation plan 必须遵守：

1. **图表不能全是柱状图** — 至少混 scatter / line / heatmap / matrix
2. **至少 2 张多子图 figure**（本 spec 设计了 3 张）
3. **要有 roofline 图**
4. **报告要含原始数据表格**，不只是结论
5. **图表走 prototype → 用户打分 → 定稿 两阶段**（paper-figure skill 流程）
6. **今日完成** — 时间预算 6-8h
