# 实验结果汇总（Experiment Results）

> 最近更新: 2026-04-04 (Acc% 已修正为 108-SM 聚合值; Coverage% 已从重跑 baseline 提取)
> 命名规范: `{algo}_{dataset}_{dir|sym}`（dir=有向 sym=无向）
> 数据来源: `result/log/*.log` — 每条数据标注具体 log
> 格式参考: `output_specification.md` §7.1 + §7.2

---

### cit-Patents

| Key | Algo | Sym | Base IPC | GRASP IPC | Speedup% | Ideal IPC | Headroom% | Idx T% | Data T% | Acc% | Idx Cov% | Data Cov% | Base Log | GRASP Log | Ideal Log |
|-----|------|:---:|--------:|----------:|--------:|----------:|---------:|-------:|--------:|-----:|---------:|----------:|----------|-----------|-----------|
| bfs_cit_sym | BFS | 1 | 102.3376 | 108.6590 | 6.2 | 179.6398 | 75.5 | 72.54 | 54.17 | 29.70 | 15.8 | 9.3 | bfs_ima_high.log | bfs_ima_high_grasp.log | bfs_ima_high_ideal_ideal_l1d.log |
| sssp_cit_sym | SSSP | 1 | 90.4341 | 92.6932 | 2.5 | 222.5751 | 146.1 | 79.54 | 46.03 | 34.38 | 11.0 | 5.9 | sssp_ima_high.log | sssp_ima_high_grasp.log | sssp_ima_high_ideal_ideal_l1d.log |
| bc_cit_sym | BC | 1 | 104.0350 | 105.7574 | 1.7 | 315.9068 | 203.7 | 89.90 | 84.87 | 25.79 | 4.2 | 1.1 | bc_ima_high.log | bc_ima_high_grasp.log | bc_ima_high_ideal_ideal_l1d.log |
| cc_cit_sym | CC | 1 | 426.7173 | 396.7720 | -7.0 | 950.4574 | 122.7 | 95.45 | 90.00 | 39.09 | -10.1 | 8.5 | cc_ima_high.log | cc_ima_high_grasp.log | cc_ima_high_ideal_ideal_l1d.log |
| spmv_cit_sym | SPMV | 1 | 373.9836 | 373.9898 | 0.0 | 857.0579 | 129.2 | 23.32 | 58.51 | 32.86 | 7.1 | 0.6 | spmv_ima_high.log | spmv_ima_high_grasp.log | spmv_ima_high_ideal_ideal_l1d.log |
| vc_cit_sym | VC | 1 | 341.7518 | 348.1072 | 1.9 | 692.7794 | 102.7 | 56.65 | 34.43 | 40.58 | 2.7 | 0.5 | vc_ima_high_baseline.log | vc_ima_high_grasp.log | vc_ima_high_ideal_ideal_l1d.log |
| bfs_cit_dir | BFS | 0 | 5.3349 | 6.0582 | 13.6 | 7.3081 | 37.0 | 94.46 | 43.14 | 99.89 | 34.3 | 18.3 | bfs_cit_dir_baseline.log | bfs_cit_dir_grasp.log | bfs_cit_dir_ideal_ideal_l1d.log |
| sssp_cit_dir | SSSP | 0 | 5.9499 | 6.6036 | 11.0 | 8.2054 | 37.9 | 95.28 | 41.90 | 99.78 | 31.6 | 17.2 | sssp_cit_dir_baseline.log | sssp_cit_dir_grasp.log | sssp_cit_dir_ideal_ideal_l1d.log |
| bc_cit_dir | BC | 0 | 95.2826 | 104.5995 | 9.8 | 168.6582 | 77.0 | 97.51 | 58.23 | 99.61 | 10.4 | 5.6 | bc_cit_dir_baseline.log | bc_cit_dir_grasp.log | bc_cit_dir_ideal_ideal_l1d.log |

### web-Google

| Key | Algo | Sym | Base IPC | GRASP IPC | Speedup% | Ideal IPC | Headroom% | Idx T% | Data T% | Acc% | Idx Cov% | Data Cov% | Base Log | GRASP Log | Ideal Log |
|-----|------|:---:|--------:|----------:|--------:|----------:|---------:|-------:|--------:|-----:|---------:|----------:|----------|-----------|-----------|
| bfs_web_sym | BFS | 1 | 7.3528 | 11.4803 | 56.1 | 10.3539 | 40.8 | 86.05 | 77.30 | 59.12 | 24.0 | 26.9 | bfs_ima_med_baseline.log | bfs_ima_med_grasp.log | bfs_ima_med_ideal_ideal_l1d.log |
| sssp_web_sym | SSSP | 1 | 9.5580 | 14.0103 | 46.6 | 13.9142 | 45.6 | 88.38 | 77.28 | 62.21 | 16.8 | 23.1 | sssp_ima_med_baseline.log | sssp_ima_med_grasp.log | sssp_ima_med_ideal_ideal_l1d.log |
| bc_web_sym | BC | 1 | 10.8322 | 12.0137 | 10.9 | 19.3066 | 78.2 | 96.50 | 87.79 | 59.00 | 5.1 | 5.5 | bc_ima_med_baseline.log | bc_ima_med_grasp.log | bc_ima_med_ideal_ideal_l1d.log |
| cc_web_sym | CC | 1 | 50.7687 | 98.2785 | 93.6 | 166.7668 | 228.5 | 95.39 | 90.76 | 54.64 | 25.6 | 34.1 | cc_ima_med.log | cc_ima_med_grasp.log | cc_ima_med_ideal_ideal_l1d.log |
| spmv_web_sym | SPMV | 1 | 129.6846 | 181.6270 | 40.1 | 461.7527 | 256.1 | 53.99 | 92.62 | 60.46 | 17.2 | 5.9 | spmv_ima_med_baseline.log | spmv_ima_med_grasp.log | spmv_ima_med_ideal_ideal_l1d.log |
| vc_web_sym | VC | 1 | 52.3822 | 52.8224 | 0.8 | 141.6423 | 170.4 | 60.05 | 59.48 | 53.92 | 7.2 | 2.8 | vc_ima_med_baseline.log | vc_ima_med_grasp.log | vc_ima_med_ideal_ideal_l1d.log |
| bfs_web_dir | BFS | 0 | 23.5588 | 30.3437 | 28.8 | 35.0002 | 48.6 | 88.34 | 73.18 | 55.00 | 22.3 | 20.4 | bfs_web_dir_baseline.log | bfs_web_dir_grasp.log | bfs_web_dir_ideal_ideal_l1d.log |
| sssp_web_dir | SSSP | 0 | 28.8141 | 35.2638 | 22.4 | 44.5283 | 54.5 | 86.95 | 68.64 | 51.90 | 19.9 | 16.0 | sssp_web_dir_baseline.log | sssp_web_dir_grasp.log | sssp_web_dir_ideal_ideal_l1d.log |
| bc_web_dir | BC | 0 | 37.6489 | 40.6961 | 8.1 | 68.6622 | 82.4 | 95.82 | 84.78 | 55.79 | 7.7 | 6.2 | bc_web_dir_baseline.log | bc_web_dir_grasp.log | bc_web_dir_ideal_ideal_l1d.log |

### flickr

| Key | Algo | Sym | Base IPC | GRASP IPC | Speedup% | Ideal IPC | Headroom% | Idx T% | Data T% | Acc% | Idx Cov% | Data Cov% | Base Log | GRASP Log | Ideal Log |
|-----|------|:---:|--------:|----------:|--------:|----------:|---------:|-------:|--------:|-----:|---------:|----------:|----------|-----------|-----------|
| bfs_flickr_sym | BFS | 1 | 9.7943 | 12.4394 | 27.0 | 14.5998 | 49.1 | 91.12 | 88.59 | 71.86 | 34.3 | 48.8 | bfs_flickr_sym_baseline.log | bfs_flickr_sym_grasp.log | bfs_flickr_sym_ideal_ideal_l1d.log |
| sssp_flickr_sym | SSSP | 1 | 11.7493 | 14.0832 | 19.9 | 18.7164 | 59.3 | 92.94 | 90.51 | 78.43 | 32.1 | 47.5 | sssp_flickr_sym_baseline.log | sssp_flickr_sym_grasp.log | sssp_flickr_sym_ideal_ideal_l1d.log |
| bc_flickr_sym | BC | 1 | 13.4772 | 16.4193 | 21.8 | 23.1370 | 71.7 | 98.46 | 94.52 | 81.94 | 11.4 | 16.6 | bc_flickr_sym_baseline.log | bc_flickr_sym_grasp.log | bc_flickr_sym_ideal_ideal_l1d.log |
| cc_flickr_sym | CC | 1 | 46.8674 | 111.8395 | 138.6 | 132.1259 | 181.9 | 95.29 | 93.60 | 76.84 | 39.6 | 59.0 | cc_flickr_baseline.log | cc_flickr_grasp.log | cc_flickr_ideal_ideal_l1d.log |
| spmv_flickr_sym | SPMV | 1 | 79.2566 | 109.3995 | 38.0 | 253.7695 | 220.2 | 60.30 | 89.03 | 69.75 | 26.7 | 24.2 | spmv_flickr_baseline.log | spmv_flickr_grasp.log | spmv_flickr_ideal_ideal_l1d.log |
| bfs_flickr_dir | BFS | 0 | 8.3156 | 10.4393 | 25.5 | 12.2783 | 47.7 | 91.26 | 86.91 | 71.92 | 36.4 | 48.5 | bfs_flickr_dir_baseline.log | bfs_flickr_dir_grasp.log | bfs_flickr_dir_ideal_ideal_l1d.log |
| sssp_flickr_dir | SSSP | 0 | 10.0362 | 11.9255 | 18.8 | 15.5165 | 54.6 | 92.52 | 88.63 | 77.15 | 35.3 | 48.3 | sssp_flickr_dir_baseline.log | sssp_flickr_dir_grasp.log | sssp_flickr_dir_ideal_ideal_l1d.log |
| bc_flickr_dir | BC | 0 | 11.9542 | 13.4415 | 12.4 | 19.8831 | 66.3 | 98.45 | 93.26 | 81.32 | 12.8 | 15.6 | bc_flickr_dir_baseline.log | bc_flickr_dir_grasp.log | bc_flickr_dir_ideal_ideal_l1d.log |

### roadNet-CA

| Key | Algo | Sym | Base IPC | GRASP IPC | Speedup% | Ideal IPC | Headroom% | Idx T% | Data T% | Acc% | Idx Cov% | Data Cov% | Base Log | GRASP Log | Ideal Log |
|-----|------|:---:|--------:|----------:|--------:|----------:|---------:|-------:|--------:|-----:|---------:|----------:|----------|-----------|-----------|
| bfs_road_sym | BFS | 1 | 14.3030 | 14.7858 | 3.4 | 21.4960 | 50.3 | 90.91 | 59.42 | 100.00 | 17.5 | 13.4 | bfs_road_sym_baseline.log | bfs_road_sym_grasp.log | bfs_road_sym_ideal_ideal_l1d.log |
| sssp_road_sym | SSSP | 1 | 17.5696 | 17.9242 | 2.0 | 24.9953 | 42.3 | 96.74 | 68.29 | 100.00 | 8.0 | 11.4 | sssp_road_sym_baseline.log | sssp_road_sym_grasp.log | sssp_road_sym_ideal_ideal_l1d.log |
| bc_road_sym | BC | 1 | 18.4855 | 18.8052 | 1.7 | 29.4113 | 59.1 | 90.67 | 74.86 | 98.76 | 16.3 | 12.7 | bc_road_sym_baseline.log | bc_road_sym_grasp.log | bc_road_sym_ideal_ideal_l1d.log |
| cc_road_sym | CC | 1 | 1490.0549 | 1489.4384 | -0.0 | 2018.8964 | 35.5 | 93.62 | 90.90 | 91.65 | 17.4 | 37.1 | cc_road_baseline.log | cc_road_grasp.log | cc_road_ideal_ideal_l1d.log |
| spmv_road_sym | SPMV | 1 | 1262.7443 | 1250.5500 | -1.0 | 2977.0181 | 135.8 | 89.31 | 84.76 | 91.87 | 20.9 | 27.4 | spmv_road_baseline.log | spmv_road_grasp.log | spmv_road_ideal_ideal_l1d.log |
| vc_road_sym | VC | 1 | 564.1312 | 562.5646 | -0.3 | 787.0948 | 39.5 | 89.04 | 67.88 | 69.59 | 3.6 | 8.2 | vc_road_sym_baseline_v2.log | vc_road_sym_g1_bugfix.log | vc_road_sym_ideal_v2_ideal_l1d.log |
| bfs_road_dir | BFS | 0 | 0.3776 | 0.3776 | 0.0 | 0.4934 | 30.7 | 99.46 | 38.39 | — | 0.0 | 0.0 | bfs_road_dir_baseline.log | bfs_road_dir_grasp.log | bfs_road_dir_ideal_ideal_l1d.log |
| sssp_road_dir | SSSP | 0 | 0.4094 | 0.4094 | 0.0 | 0.5234 | 27.8 | 99.46 | 54.81 | — | 0.0 | 0.0 | sssp_road_dir_baseline.log | sssp_road_dir_grasp.log | sssp_road_dir_ideal_ideal_l1d.log |
| bc_road_dir | BC | 0 | 68.0938 | 68.1183 | 0.0 | 87.2541 | 28.1 | 98.19 | 57.27 | — | 0.6 | 0.3 | bc_road_dir_baseline.log | bc_road_dir_grasp.log | bc_road_dir_ideal_ideal_l1d.log |

### soc-LJ1

| Key | Algo | Sym | Base IPC | GRASP IPC | Speedup% | Ideal IPC | Headroom% | Idx T% | Data T% | Acc% | Idx Cov% | Data Cov% | Base Log | GRASP Log | Ideal Log |
|-----|------|:---:|--------:|----------:|--------:|----------:|---------:|-------:|--------:|-----:|---------:|----------:|----------|-----------|-----------|
| bfs_socLJ_sym | BFS | 1 | 22.2490 | 29.1730 | 31.1 | 33.8400 | 52.1 | 87.54 | 84.11 | 49.05 | 20.3 | 23.4 | bfs_socLJ_sym_baseline.log | bfs_socLJ_sym_grasp.log | bfs_socLJ_sym_ideal_ideal_l1d.log |
| bfs_socLJ_dir | BFS | 0 | 23.2595 | 27.7606 | 19.4 | 34.0591 | 46.4 | 86.94 | 82.69 | 47.07 | 22.1 | 21.6 | bfs_socLJ_dir_baseline.log | bfs_socLJ_dir_grasp.log | bfs_socLJ_dir_ideal_ideal_l1d.log |
| spmv_socLJ_sym | SPMV | 1 | 138.3245 | 162.9411 | 17.8 | 551.1573 | 298.5 | 43.51 | 71.06 | 44.25 | 13.1 | 3.2 | spmv_socLJ_baseline.log | spmv_socLJ_grasp.log | spmv_socLJ_ideal_ideal_l1d.log |

---

## 数据说明

| 指标 | 公式 | Log 字段 |
|------|------|---------|
| **Speedup%** | (GRASP − Base) / Base × 100 | `final_ipc` |
| **Headroom%** | (Ideal − Base) / Base × 100 | `final_ipc` |
| **Idx Timeliness%** | hits / (hits + hit_reserved) × 100 | `IMA_TIMELINESS: index=` |
| **Data Timeliness%** | hits / (hits + hit_reserved) × 100 | `IMA_TIMELINESS: data=` |
| **Accuracy%** | Σ_all_SM pf_useful / Σ_all_SM (pf_useful + pf_useless) × 100 | `GRASP_EFFECT SM*:` 全 SM 聚合 |
| **Idx Coverage%** | (base_misses − grasp_misses) / base_misses × 100 | `IMA_DEMAND: index_misses=` |
| **Data Coverage%** | (base_misses − grasp_misses) / base_misses × 100 | `IMA_DEMAND: data_misses=` |

- ⏳ = 仍在运行（标注进度和时间）
- 命名: `{algo}_{dataset}_{dir|sym}`。旧名 `*_ima_high` = `*_cit_sym`，`*_ima_med` = `*_web_sym`
