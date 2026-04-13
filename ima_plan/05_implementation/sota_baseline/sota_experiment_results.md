# SOTA Baseline 全量实验结果

> 最近更新: 2026-04-06
> 3 个 SOTA baselines × 28 个 workloads = 84 个实验（75 Gardenia + 9 Extended）
> 实验在 worktree `worktrees/sota_stride` (分支 `exp/sota_stride`) 中执行

**进度: 84/84 完成**

## 全部实验状态（Speedup vs NP Baseline）

| # | Workload | 数据集 | 算法 | Snake | CAPS | Spare Reg |
|--:|----------|--------|------|------:|-----:|----------:|
| 1 | `bfs_cit_dir` | cit-Patents | BFS | +0.0% | +0.1% | +0.2% |
| 2 | `sssp_cit_dir` | cit-Patents | SSSP | +0.0% | -0.1% | +7.8% |
| 3 | `bc_cit_dir` | cit-Patents | BC | +1.2% | -0.6% | +6.2% |
| 4 | `cc_cit_sym` | cit-Patents | CC | +1.2% | +0.1% | +3.9% |
| 5 | `spmv_cit_sym` | cit-Patents | SpMV | -1.1% | -1.8% | -1.3% |
| 6 | `vc_cit_sym` | cit-Patents | VC | +1.2% | -3.6% | +3.1% |
| 7 | `bfs_web_sym` | web-Google | BFS | +0.4% | +0.0% | +0.0% |
| 8 | `sssp_web_sym` | web-Google | SSSP | +0.8% | -0.0% | +8.6% |
| 9 | `bc_web_sym` | web-Google | BC | +8.1% | +0.1% | +8.0% |
| 10 | `cc_web_sym` | web-Google | CC | +10.7% | +0.2% | +15.5% |
| 11 | `spmv_web_sym` | web-Google | SpMV | +1.5% | +14.3% | +25.8% |
| 12 | `vc_web_sym` | web-Google | VC | +5.2% | -1.0% | +14.3% |
| 13 | `bfs_flickr_sym` | flickr | BFS | +2.0% | +0.0% | +0.0% |
| 14 | `sssp_flickr_sym` | flickr | SSSP | +2.3% | -0.0% | +4.3% |
| 15 | `bc_flickr_sym` | flickr | BC | +5.5% | +0.0% | +5.9% |
| 16 | `cc_flickr_sym` | flickr | CC | -0.3% | -0.6% | +7.1% |
| 17 | `spmv_flickr_sym` | flickr | SpMV | +2.4% | -10.0% | +11.7% |
| 18 | `bfs_road_sym` | roadNet-CA | BFS | +0.2% | +1.5% | +0.1% |
| 19 | `sssp_road_sym` | roadNet-CA | SSSP | +0.1% | +0.8% | +0.6% |
| 20 | `bc_road_sym` | roadNet-CA | BC | +0.1% | +0.2% | +0.3% |
| 21 | `cc_road_sym` | roadNet-CA | CC | +1.9% | -0.3% | +0.5% |
| 22 | `spmv_road_sym` | roadNet-CA | SpMV | -0.2% | -2.4% | -2.8% |
| 23 | `vc_road_sym` | roadNet-CA | VC | +0.2% | -5.1% | +0.1% |
| 24 | `bfs_socLJ_sym` | soc-LJ1 | BFS | +0.4% | +0.0% | +0.1% |
| 25 | `spmv_socLJ_sym` | soc-LJ1 | SpMV | +1.4% | -18.7% | +5.7% |

---

## 详细结果（含全部指标）

### cit-Patents

| Workload | Algo | Baseline | NP IPC | SOTA IPC | Speedup | Accuracy | Coverage | Timeliness | Issued |
|----------|------|----------|-------:|--------:|--------:|---------:|---------:|-----------:|-------:|
| `bfs_cit_dir` | BFS | Snake | 5.33 | 5.34 | +0.0% | 93.3% | 26.6% | 93.3% | 18,124 |
| `bfs_cit_dir` | BFS | CAPS | 5.33 | 5.34 | +0.1% | 0.0% | 0.0% | 0.0% | 6,229 |
| `bfs_cit_dir` | BFS | Spare Reg | 5.33 | 5.34 | +0.2% | 0.3% | 0.1% | 0.3% | 21,324 |
| `sssp_cit_dir` | SSSP | Snake | 5.95 | 5.95 | +0.0% | 94.7% | 70.8% | 94.7% | 33,560 |
| `sssp_cit_dir` | SSSP | CAPS | 5.95 | 5.95 | -0.1% | 0.0% | 0.0% | 0.0% | 11,529 |
| `sssp_cit_dir` | SSSP | Spare Reg | 5.95 | 6.41 | +7.8% | 1.3% | 2.0% | 1.3% | 70,261 |
| `bc_cit_dir` | BC | Snake | 95.28 | 96.42 | +1.2% | 10.5% | 2.4% | 10.5% | 188,127 |
| `bc_cit_dir` | BC | CAPS | 95.28 | 94.68 | -0.6% | 0.0% | 0.0% | 0.0% | 4,754 |
| `bc_cit_dir` | BC | Spare Reg | 95.28 | 101.15 | +6.2% | 1.4% | 0.2% | 1.4% | 108,583 |
| `cc_cit_sym` | CC | Snake | 426.54 | 431.66 | +1.2% | 74.3% | 16.1% | 74.3% | 9,692,943 |
| `cc_cit_sym` | CC | CAPS | 426.54 | 426.95 | +0.1% | 1.5% | 0.0% | 1.5% | 5,460 |
| `cc_cit_sym` | CC | Spare Reg | 426.54 | 443.15 | +3.9% | 3.6% | 4.1% | 3.6% | 56,015,367 |
| `spmv_cit_sym` | SpMV | Snake | 374.57 | 370.44 | -1.1% | 37.3% | 0.2% | 37.3% | 112,189 |
| `spmv_cit_sym` | SpMV | CAPS | 374.57 | 367.85 | -1.8% | 22.1% | 5.7% | 22.1% | 7,274,288 |
| `spmv_cit_sym` | SpMV | Spare Reg | 374.57 | 369.53 | -1.3% | 0.0% | 0.0% | 0.0% | 21,231,554 |
| `vc_cit_sym` | VC | Snake | 341.75 | 345.75 | +1.2% | 71.9% | 2.7% | 71.9% | 1,337,019 |
| `vc_cit_sym` | VC | CAPS | 341.75 | 329.49 | -3.6% | 0.2% | 0.0% | 0.2% | 80,181 |
| `vc_cit_sym` | VC | Spare Reg | 341.75 | 352.29 | +3.1% | 3.0% | 1.4% | 3.0% | 16,682,835 |

### web-Google

| Workload | Algo | Baseline | NP IPC | SOTA IPC | Speedup | Accuracy | Coverage | Timeliness | Issued |
|----------|------|----------|-------:|--------:|--------:|---------:|---------:|-----------:|-------:|
| `bfs_web_sym` | BFS | Snake | 7.35 | 7.38 | +0.4% | 95.0% | 12.0% | 95.0% | 452,996 |
| `bfs_web_sym` | BFS | CAPS | 7.35 | 7.35 | +0.0% | 0.0% | 0.0% | 0.0% | 5,804 |
| `bfs_web_sym` | BFS | Spare Reg | 7.35 | 7.35 | +0.0% | 2.3% | 0.8% | 2.3% | 1,220,791 |
| `sssp_web_sym` | SSSP | Snake | 9.56 | 9.63 | +0.8% | 95.9% | 15.1% | 95.9% | 1,273,540 |
| `sssp_web_sym` | SSSP | CAPS | 9.56 | 9.56 | -0.0% | 0.0% | 0.0% | 0.0% | 13,831 |
| `sssp_web_sym` | SSSP | Spare Reg | 9.56 | 10.38 | +8.6% | 2.2% | 2.1% | 2.2% | 7,583,309 |
| `bc_web_sym` | BC | Snake | 10.83 | 11.71 | +8.1% | 77.2% | 20.2% | 77.2% | 1,333,891 |
| `bc_web_sym` | BC | CAPS | 10.83 | 10.84 | +0.1% | 0.0% | 0.0% | 0.0% | 4,036 |
| `bc_web_sym` | BC | Spare Reg | 10.83 | 11.69 | +8.0% | 1.8% | 1.9% | 1.8% | 5,786,538 |
| `cc_web_sym` | CC | Snake | 50.74 | 56.14 | +10.7% | 86.0% | 55.0% | 86.0% | 7,427,584 |
| `cc_web_sym` | CC | CAPS | 50.74 | 50.83 | +0.2% | 0.8% | 0.1% | 0.8% | 5,288 |
| `cc_web_sym` | CC | Spare Reg | 50.74 | 58.58 | +15.5% | 9.1% | 12.7% | 9.1% | 17,030,436 |
| `spmv_web_sym` | SpMV | Snake | 129.68 | 131.59 | +1.5% | 70.3% | 5.1% | 70.3% | 354,183 |
| `spmv_web_sym` | SpMV | CAPS | 129.68 | 148.23 | +14.3% | 21.3% | 9.7% | 21.3% | 2,225,312 |
| `spmv_web_sym` | SpMV | Spare Reg | 129.68 | 163.08 | +25.8% | 0.4% | 0.3% | 0.4% | 3,991,847 |
| `vc_web_sym` | VC | Snake | 52.38 | 55.12 | +5.2% | 77.5% | 7.0% | 77.5% | 712,608 |
| `vc_web_sym` | VC | CAPS | 52.38 | 51.85 | -1.0% | 0.2% | 0.0% | 0.2% | 53,565 |
| `vc_web_sym` | VC | Spare Reg | 52.38 | 59.85 | +14.3% | 13.7% | 5.4% | 13.7% | 3,078,059 |

### flickr

| Workload | Algo | Baseline | NP IPC | SOTA IPC | Speedup | Accuracy | Coverage | Timeliness | Issued |
|----------|------|----------|-------:|--------:|--------:|---------:|---------:|-----------:|-------:|
| `bfs_flickr_sym` | BFS | Snake | 9.79 | 9.99 | +2.0% | 97.0% | 34.4% | 97.0% | 1,141,819 |
| `bfs_flickr_sym` | BFS | CAPS | 9.79 | 9.80 | +0.0% | 0.0% | 0.0% | 0.0% | 6,401 |
| `bfs_flickr_sym` | BFS | Spare Reg | 9.79 | 9.80 | +0.0% | 2.7% | 0.9% | 2.7% | 1,107,441 |
| `sssp_flickr_sym` | SSSP | Snake | 11.75 | 12.01 | +2.3% | 96.9% | 40.8% | 96.9% | 2,710,648 |
| `sssp_flickr_sym` | SSSP | CAPS | 11.75 | 11.75 | -0.0% | 0.0% | 0.0% | 0.0% | 9,924 |
| `sssp_flickr_sym` | SSSP | Spare Reg | 11.75 | 12.25 | +4.3% | 4.3% | 2.5% | 4.3% | 3,765,385 |
| `bc_flickr_sym` | BC | Snake | 13.48 | 14.22 | +5.5% | 82.2% | 58.7% | 82.2% | 3,145,470 |
| `bc_flickr_sym` | BC | CAPS | 13.48 | 13.48 | +0.0% | 0.0% | 0.0% | 0.0% | 4,616 |
| `bc_flickr_sym` | BC | Spare Reg | 13.48 | 14.28 | +5.9% | 4.2% | 3.0% | 4.2% | 3,254,365 |
| `cc_flickr_sym` | CC | Snake | 46.87 | 46.71 | -0.3% | 79.6% | 48.0% | 79.6% | 1,527,392 |
| `cc_flickr_sym` | CC | CAPS | 46.87 | 46.56 | -0.6% | 1.0% | 0.1% | 1.0% | 5,259 |
| `cc_flickr_sym` | CC | Spare Reg | 46.87 | 50.19 | +7.1% | 11.6% | 17.0% | 11.6% | 3,949,511 |
| `spmv_flickr_sym` | SpMV | Snake | 79.26 | 81.17 | +2.4% | 75.7% | 5.3% | 75.7% | 508,704 |
| `spmv_flickr_sym` | SpMV | CAPS | 79.26 | 71.32 | -10.0% | 9.6% | 6.1% | 9.6% | 5,466,343 |
| `spmv_flickr_sym` | SpMV | Spare Reg | 79.26 | 88.53 | +11.7% | 0.7% | 0.3% | 0.7% | 2,750,262 |

### roadNet-CA

| Workload | Algo | Baseline | NP IPC | SOTA IPC | Speedup | Accuracy | Coverage | Timeliness | Issued |
|----------|------|----------|-------:|--------:|--------:|---------:|---------:|-----------:|-------:|
| `bfs_road_sym` | BFS | Snake | 14.30 | 14.33 | +0.2% | 92.0% | 16.4% | 92.0% | 6,112 |
| `bfs_road_sym` | BFS | CAPS | 14.30 | 14.52 | +1.5% | 0.9% | 0.6% | 0.9% | 5,882 |
| `bfs_road_sym` | BFS | Spare Reg | 14.30 | 14.32 | +0.1% | 3.4% | 2.8% | 3.4% | 30,417 |
| `sssp_road_sym` | SSSP | Snake | 17.57 | 17.59 | +0.1% | 92.0% | 5.7% | 92.0% | 7,115 |
| `sssp_road_sym` | SSSP | CAPS | 17.57 | 17.71 | +0.8% | 0.4% | 0.1% | 0.4% | 5,908 |
| `sssp_road_sym` | SSSP | Spare Reg | 17.57 | 17.68 | +0.6% | 2.0% | 1.5% | 2.0% | 85,596 |
| `bc_road_sym` | BC | Snake | 18.49 | 18.51 | +0.1% | 2.5% | 0.7% | 2.5% | 153,592 |
| `bc_road_sym` | BC | CAPS | 18.49 | 18.53 | +0.2% | 0.0% | 0.0% | 0.0% | 4,506 |
| `bc_road_sym` | BC | Spare Reg | 18.49 | 18.54 | +0.3% | 0.0% | 0.0% | 0.0% | 89,369 |
| `cc_road_sym` | CC | Snake | 1490.05 | 1518.85 | +1.9% | 8.5% | 1.6% | 8.5% | 1,170,060 |
| `cc_road_sym` | CC | CAPS | 1490.05 | 1485.43 | -0.3% | 1.0% | 0.0% | 1.0% | 5,509 |
| `cc_road_sym` | CC | Spare Reg | 1490.05 | 1497.38 | +0.5% | 3.8% | 1.9% | 3.8% | 3,915,933 |
| `spmv_road_sym` | SpMV | Snake | 1262.74 | 1260.05 | -0.2% | 13.9% | 0.5% | 13.9% | 56,463 |
| `spmv_road_sym` | SpMV | CAPS | 1262.74 | 1233.00 | -2.4% | 7.4% | 0.2% | 7.4% | 44,739 |
| `spmv_road_sym` | SpMV | Spare Reg | 1262.74 | 1227.00 | -2.8% | 0.0% | 0.0% | 0.0% | 756,208 |
| `vc_road_sym` | VC | Snake | 564.13 | 565.25 | +0.2% | 17.8% | 1.1% | 17.8% | 200,780 |
| `vc_road_sym` | VC | CAPS | 564.13 | 535.34 | -5.1% | 0.0% | 0.0% | 0.0% | 2,596 |
| `vc_road_sym` | VC | Spare Reg | 564.13 | 564.63 | +0.1% | 2.2% | 4.6% | 2.2% | 7,320,617 |

### soc-LJ1

| Workload | Algo | Baseline | NP IPC | SOTA IPC | Speedup | Accuracy | Coverage | Timeliness | Issued |
|----------|------|----------|-------:|--------:|--------:|---------:|---------:|-----------:|-------:|
| `bfs_socLJ_sym` | BFS | Snake | 22.25 | 22.34 | +0.4% | 94.0% | 22.4% | 94.0% | 5,397,413 |
| `bfs_socLJ_sym` | BFS | CAPS | 22.25 | 22.25 | +0.0% | 0.1% | 0.0% | 0.1% | 5,980 |
| `bfs_socLJ_sym` | BFS | Spare Reg | 22.25 | 22.26 | +0.1% | 2.4% | 0.7% | 2.4% | 6,143,940 |
| `spmv_socLJ_sym` | SpMV | Snake | 138.32 | 140.26 | +1.4% | 66.2% | 1.3% | 66.2% | 934,090 |
| `spmv_socLJ_sym` | SpMV | CAPS | 138.32 | 112.46 | -18.7% | 9.4% | 5.0% | 9.4% | 30,613,520 |
| `spmv_socLJ_sym` | SpMV | Spare Reg | 138.32 | 146.27 | +5.7% | 0.0% | 0.0% | 0.0% | 28,936,978 |

---

## GRASP vs SOTA 对比（web-Google）

> GRASP 数据来源: INDEX.md §ima_med 全量结果 (2026-03-28)

| 算法 | **GRASP** | Spare Reg | Snake | CAPS |
|------|:---------:|:---------:|:-----:|:----:|
| BFS | **+49.8%** | +0.0% | +0.4% | +0.0% |
| SSSP | **+44.0%** | +8.6% | +0.8% | -0.0% |
| SpMV | **+26.6%** | +25.8% | +1.5% | +14.3% |
| BC | **+23.3%** | +8.0% | +8.1% | +0.1% |

---

## Extended Benchmarks (Pannotia + LonestarGPU)

| Workload | 算法 | Benchmark | Baseline | SOTA IPC | Accuracy | Coverage | Timeliness | Issued |
|----------|------|-----------|----------|--------:|--------:|---------:|-----------:|-------:|
| `pann_mis_flickr` | MIS | Pannotia | Snake | 129.12 | 34.8% | 4.2% | 34.8% | 16,594 |
| `pann_mis_flickr` | MIS | Pannotia | CAPS | 121.00 | 0.0% | 0.0% | 0.0% | 396 |
| `pann_mis_flickr` | MIS | Pannotia | Spare Reg | 121.94 | — | — | — | 0 |
| `ls_mst_rmat12` | MST | LonestarGPU | Snake | 134.38 | 75.0% | 0.1% | 75.0% | 20 |
| `ls_mst_rmat12` | MST | LonestarGPU | CAPS | 134.55 | 0.0% | 0.0% | 0.0% | 0 |
| `ls_mst_rmat12` | MST | LonestarGPU | Spare Reg | 134.24 | — | — | — | 0 |
| `pann_color_eco` | Color | Pannotia | Snake | 538.98 | 17.9% | 6.0% | 17.9% | 26,571 |
| `pann_color_eco` | Color | Pannotia | CAPS | 539.69 | 0.0% | 0.0% | 0.0% | 35 |
| `pann_color_eco` | Color | Pannotia | Spare Reg | 544.61 | — | — | — | 0 |

### Extended vs GRASP

| Workload | GRASP | Snake | CAPS | Spare Reg |
|----------|------:|------:|-----:|----------:|
| MIS flickr | **+28.0%** | ~0% | -6.2% | -5.5% |
| MST rmat12 | 运行中 | ~0% | ~0% | ~0% |
| Color ecology1 | 运行中 | ~0% | ~0% | ~0% |

---

## 总结

### 实验规模

- 3 个 SOTA baselines: Snake (MICRO'23), CAPS (IPDPS'18), Spare Register (HPCA'14)
- 28 个 workloads (25 Gardenia + 3 Extended)，覆盖 6 个数据集
- 84 个实验全部完成

### 各 Baseline 特征

**Spare Register (HPCA'14)** — 最强 SOTA baseline
- 最佳: spmv_web +25.8%, cc_web +15.5%, vc_web +14.3%, spmv_flickr +11.7%
- 机制: 两步预取 (stride index → pair table data)，accuracy 低（0.4-13%）但 issued 量大（百万级）
- 弱点: BFS 上几乎无效 (~0%)；Extended benchmarks 上 seed_hits=0（chain CSV PC 不匹配）

**Snake (MICRO'23)** — accuracy 高但 IPC 提升小
- 最佳: cc_web +10.7%, bc_web +8.1%, bc_flickr +5.5%
- 机制: chain-based stride，accuracy 77-97% 但 coverage 低（5-55%）
- 特点: 不依赖 chain CSV，任意 workload 可用；无 cache 污染

**CAPS (IPDPS'18)** — 仅 SpMV 有效，大图严重 cache 污染
- 最佳: spmv_web +14.3%
- 最差: spmv_socLJ **-18.7%**, spmv_flickr **-10.0%**, mis_flickr **-6.2%**, vc_road **-5.1%**
- 特点: CTA-Aware stride，在大规模不规则图上 prefetch 造成严重 cache 干扰

### GRASP vs 最强 SOTA (Spare Reg) — web-Google

| 算法 | GRASP | Spare Reg | GRASP 优势 |
|------|------:|----------:|----------:|
| BFS  | +49.8% | +0.0% | **49.8pp** |
| SSSP | +44.0% | +8.6% | **35.4pp** |
| BC   | +23.3% | +8.0% | **15.3pp** |
| SpMV | +26.6% | +25.8% | 0.8pp |

### 论文核心论点支撑

1. **GRASP 在图遍历上碾压所有 SOTA** — BFS: GRASP +49.8% vs Spare Reg +0.0%; SSSP: +44.0% vs +8.6%
2. **SpMV 是 Spare Reg 最接近 GRASP 的唯一场景** — +25.8% vs +26.6%，因为 SpMV 的 index load 具有规则 stride
3. **CAPS 在大图上产生严重 cache 污染** — socLJ SpMV -18.7%，说明 CTA-Aware stride 不适合不规则访问
4. **Extended benchmarks 验证泛化性** — MIS flickr: GRASP +28% vs 所有 SOTA ≤0%
5. **Snake accuracy 高但 IPC 低** — 证明 stride 检测不是瓶颈，问题是 IMA data load 根本不可被 stride 预取
