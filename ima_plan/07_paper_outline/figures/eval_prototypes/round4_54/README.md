# Round 5 §5.4 Sensitivity + Ablation Prototypes (nohatch)

> 最近更新: 2026-04-08
> 方向: §5.4 Sensitivity + Ablation — 所有 prototype 纯色 (nohatch) 版本
> Palette: `PALETTE_TOL_BRIGHT` (green/red/purple/yellow/gray)
> 样式参考: `../round4/proto_r4_52_A_nohatch.py`
> 数据源: `ima_plan/06_evaluation_plan/sensitivity_ablation/sensitivity_ablation_experiments.md`

8 个 prototype — 6 个单独图 + 2 个合并替代方案。`_data.py` 集中存放所有表格，8 个脚本共享。

## Group 1: Ablation (full-width grouped bars, y = speedup × over NoPF)

### (a) `proto_r4_54_A_component` — Component Ablation
- 20 workloads × 3 schemes: Data-Only / Index-Only / Full GRASP
- NoPF = 1.0× 隐式基线
- GMEAN: Data-Only 1.13× / Index-Only 1.08× / Full GRASP **1.22×**
- Clipped (>1.50×): CC-wg Full 1.70×, CC-fl Full 2.02×, CC-wg Data 1.52×, CC-fl Data 1.53×, BFS-wg Full 1.56×
- 颜色: Data-Only=red, Index-Only=purple, Full GRASP=**green**
- Key finding: Full > Data+Index (流水线互补); SpM-wg Index-Only carries most gain; CC workloads benefit from both stages

### (b) `proto_r4_54_B_ipc` — Throttle IPC Ablation
- 22 workloads × 3 schemes: Default / D5b (paper) / T40C200
- GMEAN 三者 virtually identical: Default 1.204× / D5b 1.200× / T40C200 1.203×
- Clipped: cc_flickr (Default 2.39×, D5b 2.22×, T40C200 2.02×); cc_web (Default 1.94×, D5b 1.71×, T40C200 1.70×); BFS-wg (~1.56× all)
- 颜色: Default=red, D5b=**green (paper)**, T40C200=yellow
- Key finding: Throttle 几乎不影响 IPC GMEAN, 但在 cc_* outliers 上 Default > D5b > T40C200

### (c) `proto_r4_54_B_acc` — Throttle Accuracy
- 15 workloads × 3 schemes, y = Accuracy %
- Mean accuracy: Default 69.7% / D5b 71.3% / T40C200 **75.0%**
- 颜色同 (b)
- Key finding: Throttle 显著提升 accuracy (+5pp); T40C200 最高但 coverage 低

### (d) `proto_r4_54_B_cov` — Throttle Data Coverage
- 16 workloads × 3 schemes, y = Data Coverage %
- Mean coverage: Default 23.1% / D5b **46.7%** / T40C200 45.7%
- 颜色同 (b)
- Key finding: Throttle 翻倍 coverage (23→47%), D5b 略领先 T40C200; 这是选 D5b 作 paper 版的核心理由

## Group 2: Sensitivity (full-width line plots, 6 algorithm GMEANs + bold overall)

### (e) `proto_r4_54_C_distance` — Distance Sensitivity
- 20 workloads aggregated → 6 algorithm lines (BFS/SSSP/BC/CC/SpMV/VC) + **overall GMEAN (bold black)**
- x = {D=1, D=2, D=4, D=8}
- y = normalized speedup over D=1 (range 0.90-1.15)
- Overall GMEAN: D=1→1.000, D=2→1.006, D=4→0.992, D=8→0.991
- CC 是唯一 benefit 大 distance 的算法 (GMEAN D=8=1.11×); BFS/SSSP/BC/SpMV/VC 全部递减
- Key finding: D=1 最优 (整体), 仅 CC 受益 large D — 与 GPU L1 竞争假说一致

### (f) `proto_r4_54_D_storage` — Storage Sensitivity
- 20 workloads aggregated → 6 algorithm lines + overall GMEAN
- x = {S1 712B, S2 1.1KB, S3 1.9KB, S4 3.6KB}
- y = normalized speedup over S1 (range 0.95-1.10)
- Overall GMEAN 几乎完全平 (1.000 / 1.002 / 1.001 / 1.004)
- 16/20 workloads 完全 flat (标注在图上)
- 只有 SpMV 和 VC 有细微波动, SpMV S4 达 1.026×
- Key finding: **712B (0.54% L1D) 即可获完整收益**, S4 仅 SpMV 有边际增益

## Group 3: Combined alternatives (1×N horizontal subplots)

### `proto_r4_54_BC_throttle3` — Throttle 3-metric combined
- 1×3 subplots (7.0 × 2.5 in): (a) IPC × / (b) Accuracy % / (c) Coverage %
- 与单图相比: 一次展示 throttle 在三个质量指标上的效果
- 每个 panel 都是 per-algorithm lines + overall GMEAN
- Shared legend above the figure
- **推荐方案** — 三个指标同时呈现, 与其有 3 张单图不如合并

### `proto_r4_54_CD_sens` — Distance + Storage combined
- 1×2 subplots (7.0 × 2.5 in): (a) Distance / (b) Storage
- Distance panel 用 clip_upper=1.15 保留 CC 的 1.11 不超出
- Storage panel 用窄 y 范围 (0.97-1.08) 突出 SpMV/VC 的细微波动, 标注 "16/20 wkls flat"
- **推荐方案** — 两种 sensitivity sweep 在同一 figure, 节省版面

## Data source & shared module

`_data.py` — 集中存放所有表格数据 (copy 自 MD, 非运行时 parse):
- `ABLATION_PCT` (20 wkl) — Exp-A Speedup%
- `THROTTLE_IPC_PCT` (22 wkl) — Exp-B IPC Speedup%
- `THROTTLE_ACC` (15 wkl) — Exp-B Accuracy%
- `THROTTLE_COV` (16 wkl) — Exp-B Data Coverage%
- `DISTANCE_IPC` (20 wkl) — Exp-C IPC (D=1,2,4,8)
- `STORAGE_IPC` (20 wkl) — Exp-D IPC (S1..S4)
- `SENS_ALGORITHMS` — 6 algorithm groups for sensitivity aggregation
- Helpers: `gmean()`, `pct_to_mult()`, `sensitivity_normalized()`, `algorithm_gmean_lines()`, `overall_gmean_line()`

## Style rules (all 8 figures)

- `parents[5]` for `_REPO`
- `apply_style()` + `figsize_full()` + `constrained_layout=True`
- `PALETTE_TOL_BRIGHT` only — **no blue/orange** (reserved for §2-§4)
- **NO hatching** anywhere (DMP-style color-only)
- Bars sit on `bottom = Y_LO`, outliers clipped + annotated w/ arrow + `1.XX×`
- Overlapping clip annotations stacked vertically (e.g., CC-fl in B_ipc has 3 stacked labels)
- Vertical group separators (gray dashed) between algorithm groups
- Algorithm group labels (BFS/SSSP/BC/CC/SpMV/VC) below xtick labels
- GMEAN bar at right with solid black separator (`GMEAN_GAP = 0.6`)
- Subtitle via `subplot_label(ax, "(x) Title", y=-0.55)` (not `set_title`)
- Algorithm colors in sensitivity plots: BFS=green, SSSP=red, BC=purple, CC=yellow, SpMV=gray, VC=slate
- Markers: o (BFS), s (SSSP), ^ (BC), D (CC), v (SpMV), * (VC)
- Overall GMEAN line: bold black, marker "o", larger size

## Outputs

8 scripts × 2 formats = 16 output files (+ 1 `_data.py` helper + this README):

| Figure | Purpose | PDF | SVG |
|--------|---------|-----|-----|
| `proto_r4_54_A_component` | Component Ablation (20 wkl) | ✓ | ✓ |
| `proto_r4_54_B_ipc` | Throttle IPC (22 wkl) | ✓ | ✓ |
| `proto_r4_54_B_acc` | Throttle Accuracy (15 wkl) | ✓ | ✓ |
| `proto_r4_54_B_cov` | Throttle Coverage (16 wkl) | ✓ | ✓ |
| `proto_r4_54_C_distance` | Distance Sensitivity (20 wkl) | ✓ | ✓ |
| `proto_r4_54_D_storage` | Storage Sensitivity (20 wkl) | ✓ | ✓ |
| `proto_r4_54_BC_throttle3` | Throttle 3-metric combined | ✓ | ✓ |
| `proto_r4_54_CD_sens` | Distance + Storage combined | ✓ | ✓ |

## 选图建议

1. **Ablation** — 必须用 (a) `A_component` (组件互补 story 核心)
2. **Throttle** — 推荐合并版 (g) `BC_throttle3` (3 个质量指标同时呈现);
   如果版面紧, 则选 (d) `B_cov` (coverage 翻倍是 D5b 的最强证据);
   (b) `B_ipc` 不推荐作主图 — GMEAN 几乎无差别, 只能突出 outlier
3. **Sensitivity** — 推荐合并版 (h) `CD_sens` (两种 sweep 节省版面);
   如果版面宽松则 (e) `C_distance` 单独出 (CC 的 outlier 是 key finding)
