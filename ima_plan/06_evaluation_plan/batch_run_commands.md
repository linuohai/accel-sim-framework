# Batch Simulation Commands — 2026-04-03

> Review before execution. All commands use `--no-l1-trace --no-l2-trace --no-hbm-trace`.

## Baseline（32 个，需要新跑）

已有可复用 baseline（10 个）：bfs/sssp/bc/cc/spmv 的 ima_high + ima_med。

```bash
# --- cit-Patents sym=1 补充 (VC/SymGS) ---
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace vc_ima_high vc_ima_high_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace symgs_ima_high symgs_ima_high_baseline &

# --- cit-Patents dir (4 个) ---
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace bfs_cit_dir bfs_cit_dir_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace sssp_cit_dir sssp_cit_dir_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace bc_cit_dir bc_cit_dir_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace symgs_cit_dir symgs_cit_dir_baseline &

# --- web-Google sym=1 补充 (VC/SymGS) ---
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace vc_ima_med vc_ima_med_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace symgs_ima_med symgs_ima_med_baseline &

# --- web-Google dir (4 个) ---
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace bfs_web_dir bfs_web_dir_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace sssp_web_dir sssp_web_dir_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace bc_web_dir bc_web_dir_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace symgs_web_dir symgs_web_dir_baseline &

# --- flickr (8 个) ---
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace bfs_flickr_dir bfs_flickr_dir_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace bfs_flickr_sym bfs_flickr_sym_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace sssp_flickr_dir sssp_flickr_dir_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace sssp_flickr_sym sssp_flickr_sym_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace bc_flickr_dir bc_flickr_dir_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace bc_flickr_sym bc_flickr_sym_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace cc_flickr cc_flickr_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace spmv_flickr spmv_flickr_baseline &

# --- roadNet-CA (9 个) ---
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace bfs_road_dir bfs_road_dir_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace bfs_road_sym bfs_road_sym_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace sssp_road_dir sssp_road_dir_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace sssp_road_sym sssp_road_sym_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace bc_road_dir bc_road_dir_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace bc_road_sym bc_road_sym_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace cc_road cc_road_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace spmv_road spmv_road_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace symgs_road_dir symgs_road_dir_baseline &

# --- soc-LiveJournal1 (3 个) ---
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace bfs_socLJ_dir bfs_socLJ_dir_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace bfs_socLJ_sym bfs_socLJ_sym_baseline &
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace spmv_socLJ spmv_socLJ_baseline &
```

## GRASP（42 个，全部重跑）

已有 baseline 的 10 个 + 上面 32 个新 baseline 对应的 workload。
VC/SymGS 在 flickr 和 soc-LJ1 上 MAXCOLOR crash，不跑（已排除）。

```bash
# --- cit-Patents sym=1 (7 个) ---
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace bfs_ima_high bfs_ima_high_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace sssp_ima_high sssp_ima_high_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace bc_ima_high bc_ima_high_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace cc_ima_high cc_ima_high_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace spmv_ima_high spmv_ima_high_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace vc_ima_high vc_ima_high_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace symgs_ima_high symgs_ima_high_grasp &

# --- cit-Patents dir (4 个) ---
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace bfs_cit_dir bfs_cit_dir_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace sssp_cit_dir sssp_cit_dir_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace bc_cit_dir bc_cit_dir_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace symgs_cit_dir symgs_cit_dir_grasp &

# --- web-Google sym=1 (7 个) ---
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace bfs_ima_med bfs_ima_med_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace sssp_ima_med sssp_ima_med_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace bc_ima_med bc_ima_med_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace cc_ima_med cc_ima_med_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace spmv_ima_med spmv_ima_med_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace vc_ima_med vc_ima_med_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace symgs_ima_med symgs_ima_med_grasp &

# --- web-Google dir (4 个) ---
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace bfs_web_dir bfs_web_dir_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace sssp_web_dir sssp_web_dir_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace bc_web_dir bc_web_dir_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace symgs_web_dir symgs_web_dir_grasp &

# --- flickr (8 个，无 VC/SymGS) ---
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace bfs_flickr_dir bfs_flickr_dir_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace bfs_flickr_sym bfs_flickr_sym_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace sssp_flickr_dir sssp_flickr_dir_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace sssp_flickr_sym sssp_flickr_sym_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace bc_flickr_dir bc_flickr_dir_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace bc_flickr_sym bc_flickr_sym_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace cc_flickr cc_flickr_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace spmv_flickr spmv_flickr_grasp &

# --- roadNet-CA (9 个，无 VC — vc_road=vc_ima_small 单独处理) ---
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace bfs_road_dir bfs_road_dir_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace bfs_road_sym bfs_road_sym_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace sssp_road_dir sssp_road_dir_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace sssp_road_sym sssp_road_sym_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace bc_road_dir bc_road_dir_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace bc_road_sym bc_road_sym_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace cc_road cc_road_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace spmv_road spmv_road_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace symgs_road_dir symgs_road_dir_grasp &

# --- soc-LiveJournal1 (3 个) ---
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace bfs_socLJ_dir bfs_socLJ_dir_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace bfs_socLJ_sym bfs_socLJ_sym_grasp &
./traceL1 --grasp --no-l1-trace --no-l2-trace --no-hbm-trace spmv_socLJ spmv_socLJ_grasp &
```

## 总计

| 类型 | 数量 |
|------|------|
| Baseline（新跑） | 32 |
| GRASP（全部重跑） | 42 |
| **并行总数** | **74** |

## 内存估算

- 系统 RAM: 2.0 TB，可用 ~1.9 TB
- 单仿真 RSS: ~0.6-3 GB（小图~0.6G，cit-Patents~2-3G）
- 74 并行最坏: ~74 × 3 GB = 222 GB（占 12%）
- **结论: 可以全部并行，内存安全**

## 风险 workloads（可能超时或被 OOM kill）

| Workload | 预计时间 | 风险 |
|----------|---------|------|
| vc_ima_high_baseline/grasp | 未知 | 第 1 kernel 从未完成 |
| vc_ima_med_baseline/grasp | 未知 | 从未完成 |
| cc_ima_high_*grasp | ~17h | 长但之前跑过 |
| bc_ima_high_*grasp | ~16h | 长但之前跑过 |
| bfs_socLJ_sym_* | ~26h? | 大图 sym=1 |
