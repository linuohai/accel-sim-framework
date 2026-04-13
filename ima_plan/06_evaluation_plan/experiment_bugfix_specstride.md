# Bug-Fix & Speculative Stride 实验结果

> 最近更新: 2026-04-05
> 目的: 对比 (1) GRASP bug-fix 效果 (2) Speculative Stride 额外收益
> 说明: 排除 PR 算法（耗时过长），共 38 workload × 2 组 = 76 实验，全部完成
> Baseline IPC 引用自 experiment_results.md（未变）
> 数据来源: `result/log/*_g1_bugfix.log` / `*_g2_specstride.log`

---

## 改动说明

### Bug Fixes（Group 1 & 2 均包含）
- CT kernel reset: 使用 kernel name 比较代替 pointer 比较（trace-driven 下 same_kernel 永远 false）
- CD FIFO push: 回收 invalid slot，避免 FIFO 满导致新 chain 无法检测

### Speculative Stride（仅 Group 2）
- 全局 fallback: `-grasp_speculative_stride 4`
- Per-chain CSV stride_hint: BFS/SSSP/BC (4/16), SpMV (4/64), CC (4/16), VC (4/16/32/64)
- 效果: 首次迭代即可 prefetch（无需等第二次观测确认 stride）

---

## Group 1: Bug-Fix Only（`--grasp`，spec_stride=0）

### cit-Patents

| Key | Algo | Sym | Base IPC | Old GRASP | New GRASP | Speedup vs Base% | Delta vs Old% | Log |
|-----|------|:---:|--------:|----------:|----------:|:----------------:|:-------------:|-----|
| bfs_cit_sym | BFS | 1 | 102.3376 | 108.6590 | 108.6400 | +6.2 | -0.0 | bfs_cit_sym_g1_bugfix.log |
| sssp_cit_sym | SSSP | 1 | 90.4341 | 92.6932 | 93.1339 | +3.0 | +0.5 | sssp_cit_sym_g1_bugfix.log |
| bc_cit_sym | BC | 1 | 104.0350 | 105.7574 | 106.0615 | +1.9 | +0.3 | bc_cit_sym_g1_bugfix.log |
| cc_cit_sym | CC | 1 | 426.7173 | 396.7720 | 395.6974 | -7.3 | -0.3 | cc_cit_sym_g1_bugfix.log |
| spmv_cit_sym | SPMV | 1 | 373.9836 | 373.9898 | 368.3230 | -1.5 | -1.5 | spmv_cit_sym_g1_bugfix.log |
| vc_cit_sym | VC | 1 | 341.7518 | 348.1072 | 347.2743 | +1.6 | -0.2 | vc_cit_sym_g1_bugfix.log |
| bfs_cit_dir | BFS | 0 | 5.3349 | 6.0582 | 6.0789 | +13.9 | +0.3 | bfs_cit_dir_g1_bugfix.log |
| sssp_cit_dir | SSSP | 0 | 5.9499 | 6.6036 | 6.5920 | +10.8 | -0.2 | sssp_cit_dir_g1_bugfix.log |
| bc_cit_dir | BC | 0 | 95.2826 | 104.5995 | 104.6449 | +9.8 | +0.0 | bc_cit_dir_g1_bugfix.log |

### web-Google

| Key | Algo | Sym | Base IPC | Old GRASP | New GRASP | Speedup vs Base% | Delta vs Old% | Log |
|-----|------|:---:|--------:|----------:|----------:|:----------------:|:-------------:|-----|
| bfs_web_sym | BFS | 1 | 7.3528 | 11.4803 | 11.4916 | +56.3 | +0.1 | bfs_web_sym_g1_bugfix.log |
| sssp_web_sym | SSSP | 1 | 9.5580 | 14.0103 | 14.0324 | +46.8 | +0.2 | sssp_web_sym_g1_bugfix.log |
| bc_web_sym | BC | 1 | 10.8322 | 12.0137 | 11.9947 | +10.7 | -0.2 | bc_web_sym_g1_bugfix.log |
| cc_web_sym | CC | 1 | 50.7687 | 98.2785 | 91.9986 | +81.2 | -6.4 | cc_web_sym_g1_bugfix.log |
| spmv_web_sym | SPMV | 1 | 129.6846 | 181.6270 | 175.6998 | +35.5 | -3.3 | spmv_web_sym_g1_bugfix.log |
| vc_web_sym | VC | 1 | 52.3822 | 52.8224 | 53.6611 | +2.4 | +1.6 | vc_web_sym_g1_bugfix.log |
| bfs_web_dir | BFS | 0 | 23.5588 | 30.3437 | 30.8493 | +30.9 | +1.7 | bfs_web_dir_g1_bugfix.log |
| sssp_web_dir | SSSP | 0 | 28.8141 | 35.2638 | 35.3925 | +22.8 | +0.4 | sssp_web_dir_g1_bugfix.log |
| bc_web_dir | BC | 0 | 37.6489 | 40.6961 | 40.8004 | +8.4 | +0.3 | bc_web_dir_g1_bugfix.log |

### flickr

| Key | Algo | Sym | Base IPC | Old GRASP | New GRASP | Speedup vs Base% | Delta vs Old% | Log |
|-----|------|:---:|--------:|----------:|----------:|:----------------:|:-------------:|-----|
| bfs_flickr_sym | BFS | 1 | 9.7943 | 12.4394 | 12.4446 | +27.1 | +0.0 | bfs_flickr_sym_g1_bugfix.log |
| sssp_flickr_sym | SSSP | 1 | 11.7493 | 14.0832 | 14.0901 | +19.9 | +0.0 | sssp_flickr_sym_g1_bugfix.log |
| bc_flickr_sym | BC | 1 | 13.4772 | 16.4193 | 16.4004 | +21.7 | -0.1 | bc_flickr_sym_g1_bugfix.log |
| cc_flickr_sym | CC | 1 | 46.8674 | 111.8395 | 90.1851 | +92.4 | -19.4 | cc_flickr_sym_g1_bugfix.log |
| spmv_flickr_sym | SPMV | 1 | 79.2566 | 109.3995 | 109.1782 | +37.8 | -0.2 | spmv_flickr_sym_g1_bugfix.log |
| bfs_flickr_dir | BFS | 0 | 8.3156 | 10.4393 | 10.4406 | +25.6 | +0.0 | bfs_flickr_dir_g1_bugfix.log |
| sssp_flickr_dir | SSSP | 0 | 10.0362 | 11.9255 | 11.9252 | +18.8 | -0.0 | sssp_flickr_dir_g1_bugfix.log |
| bc_flickr_dir | BC | 0 | 11.9542 | 13.4415 | 13.4340 | +12.4 | -0.1 | bc_flickr_dir_g1_bugfix.log |

### roadNet-CA

| Key | Algo | Sym | Base IPC | Old GRASP | New GRASP | Speedup vs Base% | Delta vs Old% | Log |
|-----|------|:---:|--------:|----------:|----------:|:----------------:|:-------------:|-----|
| bfs_road_sym | BFS | 1 | 14.3030 | 14.7858 | 15.5202 | +8.5 | +5.0 | bfs_road_sym_g1_bugfix.log |
| sssp_road_sym | SSSP | 1 | 17.5696 | 17.9242 | 18.6726 | +6.3 | +4.2 | sssp_road_sym_g1_bugfix.log |
| bc_road_sym | BC | 1 | 18.4855 | 18.8052 | 19.2755 | +4.3 | +2.5 | bc_road_sym_g1_bugfix.log |
| cc_road_sym | CC | 1 | 1490.0549 | 1489.4384 | 1491.2617 | +0.1 | +0.1 | cc_road_sym_g1_bugfix.log |
| spmv_road_sym | SPMV | 1 | 1262.7443 | 1250.5500 | 1239.1661 | -1.9 | -0.9 | spmv_road_sym_g1_bugfix.log |
| vc_road_sym | VC | 1 | 564.1312 | — | 562.5646 | -0.3 | — | vc_road_sym_g1_bugfix.log |
| bfs_road_dir | BFS | 0 | 0.3776 | 0.3776 | 0.3776 | +0.0 | +0.0 | bfs_road_dir_g1_bugfix.log |
| sssp_road_dir | SSSP | 0 | 0.4094 | 0.4094 | 0.4094 | +0.0 | +0.0 | sssp_road_dir_g1_bugfix.log |
| bc_road_dir | BC | 0 | 68.0938 | 68.1183 | 68.1805 | +0.1 | +0.1 | bc_road_dir_g1_bugfix.log |

### soc-LJ1

| Key | Algo | Sym | Base IPC | Old GRASP | New GRASP | Speedup vs Base% | Delta vs Old% | Log |
|-----|------|:---:|--------:|----------:|----------:|:----------------:|:-------------:|-----|
| bfs_socLJ_sym | BFS | 1 | 22.2490 | 29.1730 | 29.0899 | +30.7 | -0.3 | bfs_socLJ_sym_g1_bugfix.log |
| bfs_socLJ_dir | BFS | 0 | 23.2595 | 27.7606 | 27.7619 | +19.4 | +0.0 | bfs_socLJ_dir_g1_bugfix.log |
| spmv_socLJ_sym | SPMV | 1 | 138.3245 | 162.9411 | 159.2426 | +15.1 | -2.3 | spmv_socLJ_sym_g1_bugfix.log |

---

## Group 2: Bug-Fix + Speculative Stride（`--grasp --grasp-speculative-stride 4`）

### cit-Patents

| Key | Algo | Sym | Base IPC | G1 IPC | G2 IPC | Speedup vs Base% | Delta vs G1% | Log |
|-----|------|:---:|--------:|-------:|-------:|:----------------:|:------------:|-----|
| bfs_cit_sym | BFS | 1 | 102.3376 | 108.6400 | 108.9718 | +6.5 | +0.3 | bfs_cit_sym_g2_specstride.log |
| sssp_cit_sym | SSSP | 1 | 90.4341 | 93.1339 | 92.9880 | +2.8 | -0.2 | sssp_cit_sym_g2_specstride.log |
| bc_cit_sym | BC | 1 | 104.0350 | 106.0615 | 105.7772 | +1.7 | -0.3 | bc_cit_sym_g2_specstride.log |
| cc_cit_sym | CC | 1 | 426.7173 | 395.6974 | 396.3212 | -7.1 | +0.2 | cc_cit_sym_g2_specstride.log |
| spmv_cit_sym | SPMV | 1 | 373.9836 | 368.3230 | 368.3230 | -1.5 | +0.0 | spmv_cit_sym_g2_specstride.log |
| vc_cit_sym | VC | 1 | 341.7518 | 347.2743 | 345.7480 | +1.2 | -0.4 | vc_cit_sym_g2_specstride.log |
| bfs_cit_dir | BFS | 0 | 5.3349 | 6.0789 | 6.0789 | +13.9 | +0.0 | bfs_cit_dir_g2_specstride.log |
| sssp_cit_dir | SSSP | 0 | 5.9499 | 6.5920 | 6.5945 | +10.8 | +0.0 | sssp_cit_dir_g2_specstride.log |
| bc_cit_dir | BC | 0 | 95.2826 | 104.6449 | 104.7031 | +9.9 | +0.1 | bc_cit_dir_g2_specstride.log |

### web-Google

| Key | Algo | Sym | Base IPC | G1 IPC | G2 IPC | Speedup vs Base% | Delta vs G1% | Log |
|-----|------|:---:|--------:|-------:|-------:|:----------------:|:------------:|-----|
| bfs_web_sym | BFS | 1 | 7.3528 | 11.4916 | 11.4924 | +56.3 | +0.0 | bfs_web_sym_g2_specstride.log |
| sssp_web_sym | SSSP | 1 | 9.5580 | 14.0324 | 13.9780 | +46.2 | -0.4 | sssp_web_sym_g2_specstride.log |
| bc_web_sym | BC | 1 | 10.8322 | 11.9947 | 12.2965 | +13.5 | +2.5 | bc_web_sym_g2_specstride.log |
| cc_web_sym | CC | 1 | 50.7687 | 91.9986 | 88.2214 | +73.8 | -4.1 | cc_web_sym_g2_specstride.log |
| spmv_web_sym | SPMV | 1 | 129.6846 | 175.6998 | 175.6998 | +35.5 | +0.0 | spmv_web_sym_g2_specstride.log |
| vc_web_sym | VC | 1 | 52.3822 | 53.6611 | 54.1943 | +3.5 | +1.0 | vc_web_sym_g2_specstride.log |
| bfs_web_dir | BFS | 0 | 23.5588 | 30.8493 | 30.8897 | +31.1 | +0.1 | bfs_web_dir_g2_specstride.log |
| sssp_web_dir | SSSP | 0 | 28.8141 | 35.3925 | 35.4256 | +22.9 | +0.1 | sssp_web_dir_g2_specstride.log |
| bc_web_dir | BC | 0 | 37.6489 | 40.8004 | 40.7633 | +8.3 | -0.1 | bc_web_dir_g2_specstride.log |

### flickr

| Key | Algo | Sym | Base IPC | G1 IPC | G2 IPC | Speedup vs Base% | Delta vs G1% | Log |
|-----|------|:---:|--------:|-------:|-------:|:----------------:|:------------:|-----|
| bfs_flickr_sym | BFS | 1 | 9.7943 | 12.4446 | 12.4437 | +27.1 | -0.0 | bfs_flickr_sym_g2_specstride.log |
| sssp_flickr_sym | SSSP | 1 | 11.7493 | 14.0901 | 14.0852 | +19.9 | -0.0 | sssp_flickr_sym_g2_specstride.log |
| bc_flickr_sym | BC | 1 | 13.4772 | 16.4004 | 16.4016 | +21.7 | +0.0 | bc_flickr_sym_g2_specstride.log |
| cc_flickr_sym | CC | 1 | 46.8674 | 90.1851 | 111.4586 | +137.8 | +23.6 | cc_flickr_sym_g2_specstride.log |
| spmv_flickr_sym | SPMV | 1 | 79.2566 | 109.1782 | 109.1782 | +37.8 | +0.0 | spmv_flickr_sym_g2_specstride.log |
| bfs_flickr_dir | BFS | 0 | 8.3156 | 10.4406 | 10.4411 | +25.6 | +0.0 | bfs_flickr_dir_g2_specstride.log |
| sssp_flickr_dir | SSSP | 0 | 10.0362 | 11.9252 | 11.9278 | +18.8 | +0.0 | sssp_flickr_dir_g2_specstride.log |
| bc_flickr_dir | BC | 0 | 11.9542 | 13.4340 | 13.4500 | +12.5 | +0.1 | bc_flickr_dir_g2_specstride.log |

### roadNet-CA

| Key | Algo | Sym | Base IPC | G1 IPC | G2 IPC | Speedup vs Base% | Delta vs G1% | Log |
|-----|------|:---:|--------:|-------:|-------:|:----------------:|:------------:|-----|
| bfs_road_sym | BFS | 1 | 14.3030 | 15.5202 | 15.4842 | +8.3 | -0.2 | bfs_road_sym_g2_specstride.log |
| sssp_road_sym | SSSP | 1 | 17.5696 | 18.6726 | 18.6702 | +6.3 | -0.0 | sssp_road_sym_g2_specstride.log |
| bc_road_sym | BC | 1 | 18.4855 | 19.2755 | 19.2560 | +4.2 | -0.1 | bc_road_sym_g2_specstride.log |
| cc_road_sym | CC | 1 | 1490.0549 | 1491.2617 | 1490.1407 | +0.0 | -0.1 | cc_road_sym_g2_specstride.log |
| spmv_road_sym | SPMV | 1 | 1262.7443 | 1239.1661 | 1239.1661 | -1.9 | +0.0 | spmv_road_sym_g2_specstride.log |
| vc_road_sym | VC | 1 | 564.1312 | 562.5646 | 566.1298 | +0.4 | +0.6 | vc_road_sym_g2_specstride.log |
| bfs_road_dir | BFS | 0 | 0.3776 | 0.3776 | 0.3776 | +0.0 | +0.0 | bfs_road_dir_g2_specstride.log |
| sssp_road_dir | SSSP | 0 | 0.4094 | 0.4094 | 0.4094 | +0.0 | +0.0 | sssp_road_dir_g2_specstride.log |
| bc_road_dir | BC | 0 | 68.0938 | 68.1805 | 68.1805 | +0.1 | +0.0 | bc_road_dir_g2_specstride.log |

### soc-LJ1

| Key | Algo | Sym | Base IPC | G1 IPC | G2 IPC | Speedup vs Base% | Delta vs G1% | Log |
|-----|------|:---:|--------:|-------:|-------:|:----------------:|:------------:|-----|
| bfs_socLJ_sym | BFS | 1 | 22.2490 | 29.0899 | 29.1254 | +30.9 | +0.1 | bfs_socLJ_sym_g2_specstride.log |
| bfs_socLJ_dir | BFS | 0 | 23.2595 | 27.7619 | 27.7799 | +19.4 | +0.1 | bfs_socLJ_dir_g2_specstride.log |
| spmv_socLJ_sym | SPMV | 1 | 138.3245 | 159.2426 | 159.2426 | +15.1 | +0.0 | spmv_socLJ_sym_g2_specstride.log |

---

## 补充实验: vc_road_sym

| Mode | IPC | Log |
|------|----:|-----|
| Baseline | 564.1312 | vc_road_sym_baseline_v2.log |
| GRASP G1 (bug-fix) | 562.5646 | vc_road_sym_g1_bugfix.log |
| GRASP G2 (+spec stride) | 566.1298 | vc_road_sym_g2_specstride.log |
| Ideal L1D | 787.0948 | vc_road_sym_ideal_v2_ideal_l1d.log |

---

## 最终汇总（全部 38/38 workloads）

### 一、Bug-Fix 效果（G1 vs Old GRASP）

#### 按算法分类

| 算法 | 正面 (>+0.5%) | 中性 (±0.5%) | 负面 (<-0.5%) |
|------|:---:|:---:|:---:|
| BFS (10) | road_sym **+5.0%**, web_dir +1.7% | 8 个 ±0.3% | — |
| SSSP (8) | road_sym **+4.2%** | 7 个 ±0.5% | — |
| BC (8) | road_sym **+2.5%** | 7 个 ±0.3% | — |
| CC (4) | — | cit -0.3%, road +0.1% | flickr **-19.4%**, web **-6.4%** |
| SpMV (5) | — | — | web **-3.3%**, socLJ **-2.3%**, cit -1.5%, road -0.9%, flickr -0.2% |
| VC (3) | web +1.6% | cit -0.2%, road — | — |

#### Bug-Fix 核心发现

1. **CT kernel reset fix 在多 kernel 场景（road_sym 728 kernel）显著受益**：BFS +5.0%, SSSP +4.2%, BC +2.5%
2. **CC 算法回退严重**：与图平均度数正相关 — flickr(-19.4%) > web(-6.4%) > cit(-0.3%) > road(+0.1%)。原因：同名 kernel 跨迭代保留的 stride 在高度数图上反而有害
3. **SpMV 全线回退（-0.2% ~ -3.3%）**：SpMV 仅 1 个 kernel，CT reset 改动不应影响；需进一步调查 CD FIFO 回收对 SpMV chain 检测的副作用

### 二、Speculative Stride 效果（G2 vs G1）

#### 按算法分类

| 算法 | 正面 (>+0.5%) | 中性 (±0.5%) | 负面 (<-0.5%) |
|------|:---:|:---:|:---:|
| BFS (10) | — | 10 个 ±0.3% | — |
| SSSP (8) | — | 8 个 ±0.4% | — |
| BC (8) | web_sym **+2.5%** | 7 个 ±0.3% | — |
| CC (4) | flickr **+23.6%** | cit +0.2%, road -0.1% | web **-4.1%** |
| SpMV (5) | — | 5 个 +0.0% | — |
| VC (3) | web **+1.0%**, road +0.6% | — | cit -0.4% |

#### Spec Stride 核心发现

1. **cc_flickr +23.6% 是唯一的大幅正效果** — CSV stride hint 绕过了错误的 runtime stride 学习，完全补偿了 bug-fix 的 -19.4% 回退
2. **bc_web +2.5% 和 vc_web +1.0%** — 中高度数图（web-Google）上首次迭代即 prefetch 有价值
3. **cc_web -4.1%** — spec stride 并非万能补偿，web-Google 的 CC 模式与 flickr 不同
4. **SpMV 完全无效** — stride hint 正确但无法补偿 bug-fix 回退，说明 SpMV 问题根源不在 stride 学习
5. **BFS/SSSP 几乎无效** — 这两个算法的 runtime stride 学习本身就很快收敛，首次迭代的额外 prefetch 收益极小

### 三、综合推荐

| 配置 | 适用场景 | 说明 |
|------|---------|------|
| **G2（bug-fix + spec stride）** | flickr CC | 唯一需要 spec stride 的场景（+23.6%） |
| **G1（bug-fix only）** | road_sym BFS/SSSP/BC | bug fix 提升最大的场景（+2.5~5.0%） |
| **Old GRASP（不合入 bug fix）** | CC web/flickr, SpMV | 避免 CC/SpMV 回退 |

**建议方案**：合入 bug fix + spec stride，但需额外修复 CC 和 SpMV 的回退问题后再发布。CC 回退的 root cause 是 CT kernel reset by name 对同名 kernel 跨迭代 stride 分布差异的处理不当；SpMV 回退需独立调查。
