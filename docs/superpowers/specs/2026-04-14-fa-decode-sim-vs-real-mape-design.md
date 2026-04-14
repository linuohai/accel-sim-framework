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

固定：head_dim=128, causal=on, B×H=32, dtype=fp16

| # | seq_len | head_dim | B×H | 类别 |
|---|---------|----------|-----|------|
| 1 | 512 | 128 | 32 | seq 主轴 |
| 2 | 1024 | 128 | 32 | seq 主轴 |
| 3 | 2048 | 128 | 32 | seq 主轴 |
| 4 | 4096 | 128 | 32 | seq 主轴（复用现有 fa4k trace 如可用） |
| 5 | 8192 | 128 | 32 | seq 主轴 |
| 6 | 2048 | 64 | 32 | head_dim sensitivity |
| 7 | 2048 | 128 | 8 | 并发度 sensitivity |

### Decode — flashinfer decode (7 configs)

固定：head_dim=128, num_q_heads=32, num_kv_heads=32, dtype=fp16

| # | KV_len | batch | GQA (kv_heads) | 类别 |
|---|--------|-------|----------------|------|
| 8  | 512  | 1  | 32 | KV 主轴（复用 fi_dec_512） |
| 9  | 1024 | 1  | 32 | KV 主轴 |
| 10 | 2048 | 1  | 32 | KV 主轴 |
| 11 | 4096 | 1  | 32 | KV 主轴（复用 fi_dec_4k） |
| 12 | 2048 | 8  | 32 | batch sensitivity |
| 13 | 2048 | 32 | 32 | batch sensitivity |
| 14 | 2048 | 1  | 8  | GQA sensitivity |

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

**瓶颈分类决策（方案 D 的定性部分）**：
- **Compute-bound**: SM busy ≥ 70% 且 DRAM util < 50%
- **Memory BW-bound**: DRAM util ≥ 70%
- **Latency-bound**: SM busy < 50% 且 DRAM util < 50%（warp 等内存但 BW 没满）
- **Mixed**: 其他

两边各自按上述阈值打标签，输出 14×2 的一致性矩阵。

## 5. 产出文件

1. **`ncu_metrics.csv`** — 14 行 × ncu 指标列
2. **`sim_metrics.csv`** — 14 行 × sim 指标列（对齐列名）
3. **`mape_report.md`** — 每个指标的 MAPE 表 + 瓶颈分类一致性矩阵 + 每 config top-3 stall reason 对比
4. **`fig_roofline_fa.pdf`** — FA 7 config 在 roofline 上的位置（sim 和 real 叠画）
5. **`fig_roofline_decode.pdf`** — Decode 7 config 同上
6. **`fig_mape_per_metric.pdf`** — 每个指标的 MAPE 分布（bar chart）

实验产出根目录：`result/sim_vs_real_mape/`（与现有 `result/log/`、`result/plot/` 平级）
- `ncu_metrics.csv`、`sim_metrics.csv`、`mape_report.md`、`fig_*.pdf` 都落在此目录
- 脚本与 analysis notebook：`result/sim_vs_real_mape/scripts/`
- 与 `ima_plan/` 隔离（本工作非 IMA 研究）

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

## 8. 开放项（今天开工前需确认）

- [ ] A100 是否空闲独占（ncu + tracer 需要）
- [ ] 现有 `fa4k` / `fi_dec_512` / `fi_dec_4k` trace 是否可复用（如果 FA/flashinfer 源码未变可直接用）
- [ ] FA 源码 `gpu-app-collection/flash_attention/fa.py` 是否已支持参数化 seq_len / head_dim 入参
