# Throttle Control 实验结果（论文最终版）

> 最近更新: 2026-04-07 (24 workloads 完成，新增 soc-LiveJournal1)
> 格式与 `experiment_results.md` 一致。
> 配置:
>   - **Default**: tc_mode=0, thr=80
>   - **T40C200**: tc_mode=4, thr=40, cooldown=200（静态 cooldown）
>   - **D5b**: tc_mode=5, window=5000, acc=[30,70], mshr=[40,90], cooldown=200（动态，**论文版本**）
> Workload: cit-Patents 用 dir(BFS/SSSP/BC) + sym(CC/SpMV/VC)，其余全 sym

---

## T40C200（静态 cooldown）

### cit-Patents

| Key | Algo | Sym | Base IPC | GRASP IPC | Speedup% | Idx T% | Data T% | Acc% | Data Cov% | Log |
|-----|------|:---:|--------:|----------:|--------:|-------:|--------:|-----:|----------:|-----|
| bfs_cit_dir | BFS | 0 | 5.3349 | 6.0830 | 14.0 | 94.18 | 46.16 | 99.88 | 38.3 | bfs_cit_dir_g_T40C200.log |
| sssp_cit_dir | SSSP | 0 | 5.9499 | 6.5949 | 10.8 | 95.00 | 44.44 | 99.70 | 37.0 | sssp_cit_dir_g_T40C200.log |
| bc_cit_dir | BC | 0 | 95.2826 | 104.6244 | 9.8 | 97.37 | 58.82 | 99.53 | 40.4 | bc_cit_dir_g_T40C200.log |
| cc_cit_sym | CC | 1 | 426.7173 | 445.4083 | 4.4 | 96.70 | 93.98 | 60.49 | 8.0 | cc_cit_sym_g_T40C200.log |
| spmv_cit_sym | SPMV | 1 | 373.9836 | 369.8046 | -1.1 | 24.03 | 53.42 | 16.08 | 2.1 | spmv_cit_sym_g_T40C200.log |
| vc_cit_sym | VC | 1 | 341.7518 | 348.1434 | 1.9 | 56.94 | 32.42 | 20.16 | 5.3 | vc_cit_sym_g_T40C200.log |

### web-Google

| Key | Algo | Sym | Base IPC | GRASP IPC | Speedup% | Idx T% | Data T% | Acc% | Data Cov% | Log |
|-----|------|:---:|--------:|----------:|--------:|-------:|--------:|-----:|----------:|-----|
| bfs_web_sym | BFS | 1 | 7.3528 | 11.4819 | 56.2 | 87.16 | 77.36 | 66.87 | 34.4 | bfs_web_sym_g_T40C200.log |
| sssp_web_sym | SSSP | 1 | 9.5580 | 14.0433 | 46.9 | 88.95 | 77.33 | 68.65 | 31.1 | sssp_web_sym_g_T40C200.log |
| bc_web_sym | BC | 1 | 10.8322 | 12.3684 | 14.2 | 96.57 | 87.84 | 64.14 | 37.9 | bc_web_sym_g_T40C200.log |
| cc_web_sym | CC | 1 | 50.7687 | 86.2021 | 69.8 | 96.56 | 93.19 | 72.60 | 36.2 | cc_web_sym_g_T40C200.log |
| spmv_web_sym | SPMV | 1 | 129.6846 | 181.8048 | 40.2 | 57.73 | 92.38 | 66.31 | 8.2 | spmv_web_sym_g_T40C200.log |
| vc_web_sym | VC | 1 | 52.3822 | 53.6679 | 2.5 | 62.14 | 56.30 | 51.74 | 9.3 | vc_web_sym_g_T40C200.log |

### flickr

| Key | Algo | Sym | Base IPC | GRASP IPC | Speedup% | Idx T% | Data T% | Acc% | Data Cov% | Log |
|-----|------|:---:|--------:|----------:|--------:|-------:|--------:|-----:|----------:|-----|
| bfs_flickr_sym | BFS | 1 | 9.7943 | 12.4611 | 27.2 | 91.90 | 89.15 | 79.21 | 67.6 | bfs_flickr_sym_g_T40C200.log |
| sssp_flickr_sym | SSSP | 1 | 11.7493 | 14.0945 | 20.0 | 93.11 | 90.73 | 83.42 | 65.4 | sssp_flickr_sym_g_T40C200.log |
| bc_flickr_sym | BC | 1 | 13.4772 | 16.6540 | 23.6 | 98.49 | 94.57 | 85.94 | 63.2 | bc_flickr_sym_g_T40C200.log |
| cc_flickr_sym | CC | 1 | 46.8674 | 94.8873 | 102.5 | 96.23 | 94.74 | 88.93 | 71.1 | cc_flickr_sym_g_T40C200.log |
| spmv_flickr_sym | SPMV | 1 | 79.2566 | 109.2283 | 37.8 | 63.51 | 89.29 | 74.00 | 51.1 | spmv_flickr_sym_g_T40C200.log |

### roadNet-CA

| Key | Algo | Sym | Base IPC | GRASP IPC | Speedup% | Idx T% | Data T% | Acc% | Data Cov% | Log |
|-----|------|:---:|--------:|----------:|--------:|-------:|--------:|-----:|----------:|-----|
| bfs_road_sym | BFS | 1 | 14.3030 | 15.5226 | 8.5 | 88.25 | 59.58 | 100.00 | 42.5 | bfs_road_sym_g_T40C200.log |
| sssp_road_sym | SSSP | 1 | 17.5696 | 18.6798 | 6.3 | 94.22 | 68.37 | 100.00 | 52.1 | sssp_road_sym_g_T40C200.log |
| bc_road_sym | BC | 1 | 18.4855 | 19.3459 | 4.7 | 88.45 | 75.06 | 98.97 | 54.9 | bc_road_sym_g_T40C200.log |
| cc_road_sym | CC | 1 | 1490.0549 | 1480.1456 | -0.7 | 93.54 | 91.90 | 91.26 | 79.6 | cc_road_sym_g_T40C200.log |
| spmv_road_sym | SPMV | 1 | 1262.7443 | 1250.0414 | -1.0 | 89.11 | 87.52 | 88.62 | 70.7 | spmv_road_sym_g_T40C200.log |
| vc_road_sym | VC | 1 | 564.1312 | 564.2900 | 0.0 | 89.44 | 67.18 | 66.43 | 57.0 | vc_road_sym_g_T40C200.log |

### soc-LiveJournal1

| Key | Algo | Sym | Base IPC | GRASP IPC | Speedup% | Idx T% | Data T% | Acc% | Data Cov% | Log |
|-----|------|:---:|--------:|----------:|--------:|-------:|--------:|-----:|----------:|-----|
| bfs_socLJ_sym | BFS | 1 | 22.2490 | 29.2638 | 31.5 | 89.56 | 84.80 | 59.63 | 37.3 | bfs_socLJ_sym_g_T40C200.log |
| spmv_socLJ_sym | SPMV | 1 | 138.3245 | 152.0381 | 9.9 | 34.51 | 67.34 | 37.85 | 27.5 | spmv_socLJ_sym_g_T40C200.log |

---

## D5b（动态滑动窗口，论文版本）

### cit-Patents

| Key | Algo | Sym | Base IPC | GRASP IPC | Speedup% | Idx T% | Data T% | Acc% | Data Cov% | Log |
|-----|------|:---:|--------:|----------:|--------:|-------:|--------:|-----:|----------:|-----|
| bfs_cit_dir | BFS | 0 | 5.3349 | 6.0789 | 13.9 | 94.20 | 46.15 | 99.88 | 38.3 | bfs_cit_dir_g_D5b.log |
| sssp_cit_dir | SSSP | 0 | 5.9499 | 6.5920 | 10.8 | 94.96 | 44.47 | 99.70 | 37.1 | sssp_cit_dir_g_D5b.log |
| bc_cit_dir | BC | 0 | 95.2826 | 104.6116 | 9.8 | 97.37 | 58.79 | 99.59 | 40.4 | bc_cit_dir_g_D5b.log |
| cc_cit_sym | CC | 1 | 426.7173 | 410.5897 | -3.8 | 95.94 | 91.69 | 47.93 | 10.7 | cc_cit_sym_g_D5b.log |
| spmv_cit_sym | SPMV | 1 | 373.9836 | 367.6747 | -1.7 | 24.40 | 55.21 | 18.46 | 2.4 | spmv_cit_sym_g_D5b.log |
| vc_cit_sym | VC | 1 | 341.7518 | 348.2836 | 1.9 | 56.85 | 34.06 | 23.70 | 5.5 | vc_cit_sym_g_D5b.log |

### web-Google

| Key | Algo | Sym | Base IPC | GRASP IPC | Speedup% | Idx T% | Data T% | Acc% | Data Cov% | Log |
|-----|------|:---:|--------:|----------:|--------:|-------:|--------:|-----:|----------:|-----|
| bfs_web_sym | BFS | 1 | 7.3528 | 11.4992 | 56.4 | 86.47 | 77.33 | 64.46 | 35.5 | bfs_web_sym_g_D5b.log |
| sssp_web_sym | SSSP | 1 | 9.5580 | 14.0398 | 46.9 | 88.67 | 77.36 | 66.60 | 31.7 | sssp_web_sym_g_D5b.log |
| bc_web_sym | BC | 1 | 10.8322 | 11.9936 | 10.7 | 96.60 | 87.88 | 64.03 | 38.0 | bc_web_sym_g_D5b.log |
| cc_web_sym | CC | 1 | 50.7687 | 86.7824 | 70.9 | 96.22 | 91.26 | 60.05 | 36.4 | cc_web_sym_g_D5b.log |
| spmv_web_sym | SPMV | 1 | 129.6846 | 177.2448 | 36.7 | 57.09 | 91.64 | 57.48 | 10.8 | spmv_web_sym_g_D5b.log |
| vc_web_sym | VC | 1 | 52.3822 | 53.3770 | 1.9 | 61.87 | 57.86 | 49.78 | 9.7 | vc_web_sym_g_D5b.log |

### flickr

| Key | Algo | Sym | Base IPC | GRASP IPC | Speedup% | Idx T% | Data T% | Acc% | Data Cov% | Log |
|-----|------|:---:|--------:|----------:|--------:|-------:|--------:|-----:|----------:|-----|
| bfs_flickr_sym | BFS | 1 | 9.7943 | 12.4545 | 27.2 | 91.31 | 88.74 | 76.37 | 68.7 | bfs_flickr_sym_g_D5b.log |
| sssp_flickr_sym | SSSP | 1 | 11.7493 | 14.0946 | 20.0 | 92.93 | 90.62 | 81.68 | 65.9 | sssp_flickr_sym_g_D5b.log |
| bc_flickr_sym | BC | 1 | 13.4772 | 16.4246 | 21.9 | 98.48 | 94.54 | 85.04 | 63.2 | bc_flickr_sym_g_D5b.log |
| cc_flickr_sym | CC | 1 | 46.8674 | 104.0304 | 122.0 | 95.54 | 93.64 | 79.55 | 76.4 | cc_flickr_sym_g_D5b.log |
| spmv_flickr_sym | SPMV | 1 | 79.2566 | 108.7362 | 37.2 | 62.16 | 89.38 | 68.83 | 54.1 | spmv_flickr_sym_g_D5b.log |

### roadNet-CA

| Key | Algo | Sym | Base IPC | GRASP IPC | Speedup% | Idx T% | Data T% | Acc% | Data Cov% | Log |
|-----|------|:---:|--------:|----------:|--------:|-------:|--------:|-----:|----------:|-----|
| bfs_road_sym | BFS | 1 | 14.3030 | 15.5202 | 8.5 | 88.21 | 59.82 | 100.00 | 42.8 | bfs_road_sym_g_D5b.log |
| sssp_road_sym | SSSP | 1 | 17.5696 | 18.6726 | 6.3 | 94.22 | 68.37 | 100.00 | 52.1 | sssp_road_sym_g_D5b.log |
| bc_road_sym | BC | 1 | 18.4855 | 19.3477 | 4.7 | 88.41 | 75.11 | 98.99 | 55.1 | bc_road_sym_g_D5b.log |
| cc_road_sym | CC | 1 | 1490.0549 | 1491.3196 | 0.1 | 93.35 | 89.57 | 88.96 | 85.7 | cc_road_sym_g_D5b.log |
| spmv_road_sym | SPMV | 1 | 1262.7443 | 1249.5670 | -1.0 | 89.12 | 84.16 | 87.42 | 78.4 | spmv_road_sym_g_D5b.log |
| vc_road_sym | VC | 1 | 564.1312 | 566.0939 | 0.3 | 89.16 | 67.81 | 68.98 | 58.4 | vc_road_sym_g_D5b.log |

### soc-LiveJournal1

| Key | Algo | Sym | Base IPC | GRASP IPC | Speedup% | Idx T% | Data T% | Acc% | Data Cov% | Log |
|-----|------|:---:|--------:|----------:|--------:|-------:|--------:|-----:|----------:|-----|
| bfs_socLJ_sym | BFS | 1 | 22.2490 | 29.2004 | 31.2 | 88.14 | 84.37 | 53.94 | 39.6 | bfs_socLJ_sym_g_D5b.log |
| spmv_socLJ_sym | SPMV | 1 | 138.3245 | 152.3991 | 10.2 | 34.46 | 67.60 | 41.13 | 27.7 | spmv_socLJ_sym_g_D5b.log |

---

## Default GRASP 结果（对照）

### cit-Patents

| Key | Algo | Sym | Base IPC | GRASP IPC | Speedup% | Idx T% | Data T% | Acc% | Data Cov% |
|-----|------|:---:|--------:|----------:|--------:|-------:|--------:|-----:|----------:|
| bfs_cit_dir | BFS | 0 | 5.3349 | 6.0582 | 13.6 | 94.46 | 43.14 | 99.89 | 18.3 |
| sssp_cit_dir | SSSP | 0 | 5.9499 | 6.6036 | 11.0 | 95.28 | 41.90 | 99.78 | 17.2 |
| bc_cit_dir | BC | 0 | 95.2826 | 104.5995 | 9.8 | 97.51 | 58.23 | 99.61 | 5.6 |
| cc_cit_sym | CC | 1 | 426.7173 | 396.7720 | -7.0 | 95.45 | 90.00 | 39.09 | 0.0 |
| spmv_cit_sym | SPMV | 1 | 373.9836 | 373.9898 | 0.0 | 23.32 | 58.51 | 32.86 | 0.6 |
| vc_cit_sym | VC | 1 | 341.7518 | 348.1072 | 1.9 | 56.65 | 34.43 | 40.58 | 0.5 |

### web-Google

| Key | Algo | Sym | Base IPC | GRASP IPC | Speedup% | Idx T% | Data T% | Acc% | Data Cov% |
|-----|------|:---:|--------:|----------:|--------:|-------:|--------:|-----:|----------:|
| bfs_web_sym | BFS | 1 | 7.3528 | 11.4803 | 56.1 | 86.05 | 77.30 | 59.12 | 26.9 |
| sssp_web_sym | SSSP | 1 | 9.5580 | 14.0103 | 46.6 | 88.38 | 77.28 | 62.21 | 23.1 |
| bc_web_sym | BC | 1 | 10.8322 | 12.0137 | 10.9 | 96.50 | 87.79 | 59.00 | 5.5 |
| cc_web_sym | CC | 1 | 50.7687 | 98.2785 | 93.6 | 95.39 | 90.76 | 54.64 | 34.1 |
| spmv_web_sym | SPMV | 1 | 129.6846 | 181.6270 | 40.1 | 53.99 | 92.62 | 60.46 | 5.9 |
| vc_web_sym | VC | 1 | 52.3822 | 52.8224 | 0.8 | 60.05 | 59.48 | 53.92 | 2.8 |

### flickr

| Key | Algo | Sym | Base IPC | GRASP IPC | Speedup% | Idx T% | Data T% | Acc% | Data Cov% |
|-----|------|:---:|--------:|----------:|--------:|-------:|--------:|-----:|----------:|
| bfs_flickr_sym | BFS | 1 | 9.7943 | 12.4394 | 27.0 | 91.12 | 88.59 | 71.86 | 48.8 |
| sssp_flickr_sym | SSSP | 1 | 11.7493 | 14.0832 | 19.9 | 92.94 | 90.51 | 78.43 | 47.5 |
| bc_flickr_sym | BC | 1 | 13.4772 | 16.4193 | 21.8 | 98.46 | 94.52 | 81.94 | 16.6 |
| cc_flickr_sym | CC | 1 | 46.8674 | 111.8395 | 138.6 | 95.29 | 93.60 | 76.84 | 59.0 |
| spmv_flickr_sym | SPMV | 1 | 79.2566 | 109.3995 | 38.0 | 60.30 | 89.03 | 69.75 | 24.2 |

### roadNet-CA

| Key | Algo | Sym | Base IPC | GRASP IPC | Speedup% | Idx T% | Data T% | Acc% | Data Cov% |
|-----|------|:---:|--------:|----------:|--------:|-------:|--------:|-----:|----------:|
| bfs_road_sym | BFS | 1 | 14.3030 | 14.7858 | 3.4 | 90.91 | 59.42 | 100.00 | 13.4 |
| sssp_road_sym | SSSP | 1 | 17.5696 | 17.9242 | 2.0 | 96.74 | 68.29 | 100.00 | 11.4 |
| bc_road_sym | BC | 1 | 18.4855 | 18.8052 | 1.7 | 90.67 | 74.86 | 98.76 | 12.7 |
| cc_road_sym | CC | 1 | 1490.0549 | 1489.4384 | -0.0 | 93.62 | 90.90 | 91.65 | 37.1 |
| spmv_road_sym | SPMV | 1 | 1262.7443 | 1250.5500 | -1.0 | 89.31 | 84.76 | 91.87 | 27.4 |
| vc_road_sym | VC | 1 | 564.1312 | 562.5646 | -0.3 | 89.04 | 67.88 | 69.59 | 8.2 |

### soc-LiveJournal1

| Key | Algo | Sym | Base IPC | GRASP IPC | Speedup% | Idx T% | Data T% | Acc% | Data Cov% |
|-----|------|:---:|--------:|----------:|--------:|-------:|--------:|-----:|----------:|
| bfs_socLJ_sym | BFS | 1 | 22.2490 | 29.1730 | 31.1 | 87.54 | 84.11 | 49.05 | 23.4 |
| spmv_socLJ_sym | SPMV | 1 | 138.3245 | 162.9411 | 17.8 | 43.51 | 71.06 | 44.25 | 3.2 |

---

## 版本选择

**论文使用 D5b (`tc_mode=5`) 作为 GRASP 的最终配置。**

理由：
1. **Coverage 全面领先**: 22 workloads 中 D5b Coverage ≥ T40C200
2. **IPC 平均持平**: 两者 vs Default 的 IPC 变化几乎一致
3. **对高效预取 workload 更安全**: cc_flickr_sym IPC 退化从 T40 的 -15.2% 改善到 D5b 的 -7.0%
4. **roadNet-CA 图遍历大幅改善**: bfs_road +8.5%, sssp_road +6.3%, bc_road +4.7%
5. **cc_cit_sym 例外**: T40C200(+4.4%) 明显优于 D5b(-3.8%)，但 D5b Coverage 更高(10.7 vs 8.0)

---

## 数据说明

| 指标 | 公式 | Log 字段 |
|------|------|---------|
| **Speedup%** | (GRASP − Base) / Base × 100 | `final_ipc` |
| **Idx Timeliness%** | hits / (hits + hit_reserved) × 100 | `IMA_TIMELINESS: index=` |
| **Data Timeliness%** | hits / (hits + hit_reserved) × 100 | `IMA_TIMELINESS: data=` |
| **Accuracy%** | Σ_SM pf_useful / Σ_SM (pf_useful + pf_useless) × 100 | `GRASP_EFFECT SM*:` 全 SM 聚合 |
| **Data Coverage%** | (data_hits + data_hit_reserved) / data_reads × 100 | `IMA_DEMAND:` |

详细 DSE 过程: `ima_plan/05_implementation/dse_throttle_control/README.md`