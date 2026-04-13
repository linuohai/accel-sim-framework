# 实验耗时统计（Experiment Timing Reference）

> 最近更新: 2026-04-03
> 用途: 指导后续实验的时间规划和资源分配
> 数据来源: 各 log 文件中 `gpgpu_simulation_time = X days, Y hrs, Z min, W sec (N sec)`

---

## 1. 总览：单实验耗时范围

| 耗时区间 | Baseline | GRASP | Ideal L1D | 说明 |
|----------|:-------:|:-----:|:---------:|------|
| < 1h | 17 | 14 | 28 | SpMV、roadNet-CA dir、cit-Patents dir BFS/SSSP |
| 1-5h | 13 | 13 | 11 | flickr BFS/SSSP、web-Google BFS/SSSP、VC |
| 5-10h | 6 | 6 | 0 | BC、CC、vc_cit_sym |
| 10-20h | 1 | 1 | 0 | soc-LJ1、bc_cit_sym |
| 20-40h | 0 | 1 | 0 | CC cit-Patents GRASP |
| > 40h | 0 | 0 | 0 | — |

---

## 2. 按数据集 × 算法的耗时表

### 2.1 cit-Patents（最大图，|E|=33M sym / 16.5M dir）

| Key | Algo | Sym | Kernels | Baseline | GRASP | Ideal | 说明 |
|-----|------|:---:|:------:|--------:|------:|------:|------|
| bfs_cit_sym | BFS | 1 | 18 | 4.7h | 10.5h | 2.6h | GRASP 比 baseline 慢 2.2× |
| sssp_cit_sym | SSSP | 1 | 18 | 3.4h | 21.5h | 2.9h | GRASP 慢 6.3× |
| bc_cit_sym | BC | 1 | 58 | 7.0h | 26.9h | 5.1h | GRASP 慢 3.8× |
| cc_cit_sym | CC | 1 | 18 | 6.6h | 30.9h | 9.7h | GRASP 慢 4.7× |
| spmv_cit_sym | SpMV | 1 | 1 | 3.3h | 4.9h | 1.0h | 相对快 |
| vc_cit_sym | VC | 1 | 14 | 9.5h | 9.7h | 4.1h | GRASP ≈ Baseline |
| bfs_cit_dir | BFS | 0 | 15 | 13m | 12m | 6m | 非常快 |
| sssp_cit_dir | SSSP | 0 | 15 | 15m | 13m | 6m | |
| bc_cit_dir | BC | 0 | 49 | 46m | 45m | 18m | |

### 2.2 web-Google（中等图，|E|=8.6M sym / 5.1M dir）

| Key | Algo | Sym | Kernels | Baseline | GRASP | Ideal | 说明 |
|-----|------|:---:|:------:|--------:|------:|------:|------|
| bfs_web_sym | BFS | 1 | 16 | 2.4h | 2.6h | 1.6h | |
| sssp_web_sym | SSSP | 1 | 16 | 3.5h | 4.1h | 1.4h | |
| bc_web_sym | BC | 1 | 52 | 5.5h | 7.2h | 2.8h | |
| cc_web_sym | CC | 1 | 20 | 6.7h | 11.6h | 4.5h | |
| spmv_web_sym | SpMV | 1 | 1 | 43m | 1.2h | 18m | |
| vc_web_sym | VC | 1 | 62 | 4.6h | 4.6h | 1.8h | |
| bfs_web_dir | BFS | 0 | 31 | 1.0h | 1.1h | 30m | |
| sssp_web_dir | SSSP | 0 | 31 | 1.6h | 1.5h | 29m | |
| bc_web_dir | BC | 0 | 97 | 2.3h | 2.3h | 57m | |

### 2.3 flickr（社交网络，|E|=19.6M sym / 9.8M dir）

| Key | Algo | Sym | Kernels | Baseline | GRASP | Ideal | 说明 |
|-----|------|:---:|:------:|--------:|------:|------:|------|
| bfs_flickr_sym | BFS | 1 | 12 | 3.4h | 3.0h | 1.4h | GRASP 略快于 baseline |
| sssp_flickr_sym | SSSP | 1 | 12 | 3.8h | 4.0h | 1.4h | |
| bc_flickr_sym | BC | 1 | 40 | 7.7h | 6.4h | 3.3h | GRASP 略快 |
| cc_flickr_sym | CC | 1 | 4 | 5.1h | 4.0h | 2.0h | GRASP 快 20% |
| spmv_flickr_sym | SpMV | 1 | 1 | 2.4h | 2.3h | 31m | |
| bfs_flickr_dir | BFS | 0 | 12 | 2.9h | 2.6h | 1.4h | |
| sssp_flickr_dir | SSSP | 0 | 12 | 3.5h | 3.4h | 1.5h | |
| bc_flickr_dir | BC | 0 | 40 | 6.5h | 6.0h | 3.0h | |

### 2.4 roadNet-CA（道路网络，|E|=2.8M）

| Key | Algo | Sym | Kernels | Baseline | GRASP | Ideal | 说明 |
|-----|------|:---:|:------:|--------:|------:|------:|------|
| bfs_road_sym | BFS | 1 | 728 | 1.7h | 1.7h | 40m | 728 kernel！高 BFS 直径 |
| sssp_road_sym | SSSP | 1 | 728 | 1.8h | 1.8h | 42m | |
| bc_road_sym | BC | 1 | 2188 | 3.7h | 3.7h | 1.5h | 2188 kernel |
| cc_road_sym | CC | 1 | 14 | 2.3h | 2.3h | 1.3h | |
| spmv_road_sym | SpMV | 1 | 1 | 21m | 27m | 5m | 最快 |
| vc_road_sym | VC | 1 | 24 | — | — | — | ❌ 未跑 |
| bfs_road_dir | BFS | 0 | 108 | 4m | 4m | 2m | 最快组 |
| sssp_road_dir | SSSP | 0 | 108 | 4m | 4m | 2m | |
| bc_road_dir | BC | 0 | 328 | 17m | 18m | 8m | |

### 2.5 soc-LiveJournal1（大社交，|E|=138M sym / 69M dir）

| Key | Algo | Sym | Kernels | Baseline | GRASP | Ideal | 说明 |
|-----|------|:---:|:------:|--------:|------:|------:|------|
| bfs_socLJ_sym | BFS | 1 | 14 | 15.1h | 16.9h | 5.7h | |
| bfs_socLJ_dir | BFS | 0 | 15 | 14.3h | 13.7h | 4.9h | |
| spmv_socLJ_sym | SpMV | 1 | 1 | 14.9h | 17.5h | 2.9h | 单 kernel 但图巨大 |

---

## 3. 规划参考

### 3.1 GRASP 开销倍率

GRASP 仿真通常比 Baseline 慢（因为 prefetcher 逻辑开销）：

| 数据集 | 典型倍率 (GRASP/Baseline) | 说明 |
|--------|:--:|------|
| cit-Patents sym=1 | 2.2× ~ 6.3× | 大图上 GRASP 开销显著 |
| cit-Patents dir | 0.9× ~ 1.0× | 小 workload 开销可忽略 |
| web-Google sym=1 | 1.1× ~ 1.7× | |
| flickr | 0.8× ~ 1.1× | flickr 上 GRASP 有时更快（IPC 提升减少了总 cycle） |
| roadNet-CA | 1.0× | 几乎无开销 |
| soc-LJ1 | 1.0× ~ 1.2× | |

### 3.2 Ideal L1D 加速比

Ideal L1D 通常比 Baseline 快（所有 load miss → hit）：

| 数据集 | Ideal/Baseline | 说明 |
|--------|:-:|------|
| cit-Patents sym=1 | 0.3× ~ 0.6× | 显著加速 |
| web-Google | 0.4× ~ 0.7× | |
| flickr | 0.3× ~ 0.5× | |
| roadNet-CA | 0.3× ~ 0.6× | |
| soc-LJ1 | 0.2× ~ 0.4× | Ideal 效果最大 |

### 3.3 新实验时间预估公式

对于新的 workload，可用以下经验公式估算仿真时间：

```
Baseline_time ≈ f(|E|, kernels, algo_complexity)

参考点:
  BFS/SSSP: ~0.15h per million edges (sym=1)
  BC:       ~0.25h per million edges (sym=1)  
  CC:       ~0.25h per million edges (sym=1)
  SpMV:     ~0.10h per million edges (sym=1)
  VC:       ~0.15h per million edges (sym=1)

GRASP_time ≈ Baseline_time × 1.5 (中位数倍率)
Ideal_time ≈ Baseline_time × 0.4
```

### 3.4 并行容量

- 系统: 128 核 / 2 TB RAM
- 单仿真 RSS: 0.6 ~ 3 GB
- 安全并行: ~100 个仿真（内存 <15%）
- 实际瓶颈: CPU 核数（128），非内存
