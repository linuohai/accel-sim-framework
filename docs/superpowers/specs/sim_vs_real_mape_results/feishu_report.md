# FA / Decode 算子在 GPGPU-Sim 与 A100 真机上的瓶颈一致性实验报告

> 实验日期：2026-04-14  
> 作者：linuohai  
> 平台：Linux / 8× NVIDIA A100 80GB PCIe  
> 工具链：GPGPU-Sim (Accel-Sim, commit 16278aa) + NVIDIA Nsight Compute 2024.3.0 + NVBit 1.7.4

---

## 一、实验目的

> **核心问题**：在相同的输入配置下，用 **GPGPU-Sim 模拟器** 分析 FA / Decode 算子的性能瓶颈，与用 **Nsight Compute** 在 A100 真机上分析的结果，两者的结论是否一致？

这直接影响后续我们是否可以信任模拟器的 DSE（Design Space Exploration）输出。

### 关注维度

1. **绝对 MAPE**：模拟器预测的数值（IPC、runtime、DRAM 利用率等）与真机的相对误差
2. **相对瓶颈分类一致性**：两边各自判断每个 config 是 compute-bound / memory-bw-bound / latency-bound / mixed，看是否落在同一区

---

## 二、Workload 与 Config 矩阵

> 14 个 config（7 FA + 7 Decode），覆盖 seq/KV 长度主轴 + 若干 sensitivity 变体。实际可用 **13 个**（cfg_05 FA s8k 因 NVBit 在大 kernel 上 hang 被放弃）。

### 2.1 FA — Flash Attention Prefill（7 configs）

| # | 标签 | batch | seqlen | nheads | head_dim | 说明 |
|---|------|-------|--------|--------|----------|------|
| 1 | FA-s512 | 1 | 512 | 32 | 128 | seq 主轴 |
| 2 | FA-s1k | 1 | 1024 | 32 | 128 | seq 主轴 |
| 3 | FA-s2k | 1 | 2048 | 32 | 128 | seq 主轴 |
| 4 | FA-s4k | 1 | 4096 | 32 | 128 | seq 主轴（trace 复用 `hw_run/fa_4096seq`） |
| 5 | ~~FA-s8k~~ | ~~1~~ | ~~8192~~ | ~~32~~ | ~~128~~ | **跳过：NVBit instrument 卡死** |
| 6 | FA-s2k-d64 | 1 | 2048 | 32 | 64 | head_dim sensitivity |
| 7 | FA-s2k-H8 | 1 | 2048 | 8 | 128 | 并发度 sensitivity |

### 2.2 Decode — Flashinfer BatchPrefillWithPagedKVCache（7 configs）

（flashinfer 的"decode" 底层实际走 BatchPrefill kernel；page_size=16, mode=paged, fp16）

| # | 标签 | batch | seqlen_k | num_heads | num_kv_heads | 说明 |
|---|------|-------|----------|-----------|--------------|------|
| 8 | DEC-k512 | 1 | 512 | 32 | 32 | KV 主轴 |
| 9 | DEC-k1k | 1 | 1024 | 32 | 32 | KV 主轴 |
| 10 | DEC-k2k | 1 | 2048 | 32 | 32 | KV 主轴 |
| 11 | DEC-k4k | 1 | 4096 | 32 | 32 | KV 主轴 |
| 12 | DEC-k2k-B8 | 8 | 2048 | 32 | 32 | batch sensitivity |
| 13 | DEC-k2k-B32 | 32 | 2048 | 32 | 32 | batch sensitivity |
| 14 | DEC-k2k-GQA | 1 | 2048 | 32 | 8 | GQA sensitivity (4:1) |

---

## 三、实验流程（Pipeline）

```
┌──────────────────── A100 real GPU ─────────────────────┐
│                                                         │
│  每个 config (i):                                        │
│                                                         │
│   ① NVBit tracer (LD_PRELOAD=tracer_tool.so)           │
│        python3 fa.py / flashinfer_decode.py            │
│        ↓                                                │
│        SASS trace (.traceg.xz) + kernelslist.g         │
│                                                         │
│   ② ncu profiler (sudo ncu --set speed-of-light …)     │
│        python3 fa.py / flashinfer_decode.py            │
│        ↓                                                │
│        cfg_XX.ncu-rep + cfg_XX.csv (--page raw)         │
│                                                         │
└─────────────────────────────────────────────────────────┘
         │                          │
         ▼                          ▼
   ┌──────────────┐          ┌──────────────┐
   │ GPGPU-Sim    │          │ parse_ncu.py │
   │ (CPU 并行)    │          │   ↓          │
   │   ↓          │          │ ncu JSON     │
   │ cfg_XX.log   │          │              │
   └──────┬───────┘          └──────┬───────┘
          │                          │
          ▼                          │
   ┌──────────────┐                  │
   │ parse_sim.py │                  │
   │   ↓          │                  │
   │ sim JSON     │                  │
   └──────┬───────┘                  │
          │                          │
          └───────►  collect_metrics.py  ◄───────┘
                          ↓
                   merged_metrics.csv
                          ↓
          ┌───────────────┴─────────────────┐
          ▼                                 ▼
  classify_bottleneck.py              make_report.py
          ↓                                 ↓
   sim_class / real_class / agree    mape_report.md
```

### 3.1 关键技术点

| 环节 | 技术决策 | 原因 |
|------|----------|------|
| Tracer attach 方式 | **CUDA_INJECTION64_PATH**（非 LD_PRELOAD） | NVBit 1.7.4 要求 |
| Post-processing | 每次 trace 后必跑 `post-traces-processing` | 把 .trace.xz → .traceg.xz + kernelslist.g |
| ncu 权限 | **sudo -E -n ncu**（passwordless sudo + SUID profile counter） | `RmProfilingAdminOnly=1` 阻止非 root |
| ncu 指标导出 | `--page raw` 而非 `--page details` | 拿稳定的原始 metric 名（sm__*, l1tex__*, smsp__*），而非人类可读 section 名 |
| Kernel 过滤 | FA 匹配 `flash_fwd`，Decode 匹配 `flashinfer::` | 排除 PyTorch 初始化 kernel（distribution_elementwise、CatArray 等） |
| 8-GPU 并行 | `xargs -n1 -P8 -I{}` + `CUDA_VISIBLE_DEVICES=(id-1)%8` | 8 张 A100 完全独立，无互相干扰 |

---

## 四、Nsight Compute 指标选择（重点章节）

> **采用方案 2**：列出本次实际采集的所有指标（184 个 raw metrics，来自 SpeedOfLight + ComputeWorkloadAnalysis + MemoryWorkloadAnalysis + WarpStateStats + SchedulerStats 5 个 section），**高亮真正入选 MAPE 对比的 6 个核心指标 + 5 个 stall 指标**。

### 4.1 入选的核心性能指标（6 个，用于 MAPE 计算）

| 维度 | ncu raw metric | 含义 | 典型值域 | 对应 sim 推导 |
|------|----------------|------|----------|--------------|
| 🔴 **runtime** | `gpu__time_duration.sum` | 每个 kernel 在 GPU 上的执行时长，单位自适应 us/ms/s | us ~ ms | `gpu_tot_sim_cycle / 1.41 GHz` |
| 🔴 **IPC** | `sm__inst_executed.avg.per_cycle_active` | 每个 active 周期里 SM 平均执行的 warp 指令数（**warp 级**，peak=4） | 0.5 – 2.0 | `gpu_tot_ipc_delta / (108×32)` |
| 🔴 **SM busy** | `sm__throughput.avg.pct_of_peak_sustained_elapsed` | SM 综合流水线吞吐占 peak 的百分比 | 0 – 100 % | `gpu_tot_ipc_delta / 13824 × 100` |
| 🔴 **DRAM util** | `dram__throughput.avg.pct_of_peak_sustained_elapsed` | HBM 带宽占 peak 1555 GB/s 的百分比 | 0 – 100 % | `(dram_reads+writes)×32B / runtime / 1555 GB/s × 100` |
| 🔴 **L1 hit rate** | `l1tex__t_sector_hit_rate.pct` | L1/TEX unit sector 命中率（%） | 0 – 100 % | `L1D_total_cache_hits / L1D_total_cache_accesses × 100` |
| 🔴 **L2 hit rate** | `lts__t_sector_hit_rate.pct` | L2 unit sector 命中率（%） | 0 – 100 % | `L2_total_cache_hits / L2_total_cache_accesses × 100` |

### 4.2 入选的 Warp Stall 指标（top-5，用于 Fig 4 stall composition）

> Stall 名称模式：`smsp__average_warps_issue_stalled_<reason>_per_issue_active.ratio`
> 总共 18 种，取占比最高的前 5 种，归一化到 100%。

| reason | 含义 |
|--------|------|
| 🟢 **long_scoreboard** | 等待远距离依赖（典型：global load 未返回） |
| 🟢 **short_scoreboard** | 等待近距离依赖（典型：shared mem、MIO） |
| 🟢 **mio_throttle** | MIO 单元背压，load/store 通路拥塞 |
| 🟢 **barrier** | 在 `__syncthreads()` 上阻塞 |
| 🟢 **not_selected** | 可 issue 但被调度器没选到（warp 多 scheduler 少） |

还收集到但**未入选 top-5** 的其它 stall reasons（共 12 种）：`wait`, `math_pipe_throttle`, `lg_throttle`, `tex_throttle`, `membar`, `sleeping`, `dispatch_stall`, `imc_miss`, `drain`, `branch_resolving`, `misc`, `no_instruction`。其中 `wait` 和 `math_pipe_throttle` 在 FA 类 workload 占比也很高，后续可以考虑加入。

### 4.3 采集但未入选的指标分类（约 160+ 个）

| 类别 | 数量 | 代表 | 为什么不用 |
|------|------|------|-----------|
| 设备常量 (`device__*`) | ~40 | `device__attribute_global_memory_bus_width` | 静态 capability 信息，非 workload 行为 |
| 启动配置 (`launch__*`) | ~20 | `launch__block_size`, `launch__grid_size` | 跟 workload 参数一一对应，从 config 可推 |
| 各种 detailed l1tex/lts 分项 | ~30 | `l1tex__t_sectors_pipe_lsu_mem_global_op_ld_lookup_hit.sum` | 过于细粒度，sim 无对应 |
| Tensor core 活动 | ~10 | `sm__pipe_tensor_cycles_active.sum` | GPGPU-Sim 对 tensor core 建模不完整，直接比不公平 |
| 指令 pipeline 分项 | ~20 | `sm__inst_executed_pipe_tensor.sum` 等 | 同上 |
| NVLink / NUMA | ~10 | `nvlink__*`, `numa__*` | A100 PCIe 无 NVLink，全 0 |
| profiler 元数据 | ~10 | `profiler__*` | 采集过程元信息，非性能 |

---

## 五、Sim IPC 推导链条（关键验证）

> 由于 GPGPU-Sim 的 `gpu_tot_ipc` 与 ncu 的 IPC **单位不同**（差了约 3000×），这是整个实验中最容易出错的点。下面用 cfg_01 (FA-s512) 完整展示正确提取过程。

### 5.1 原始日志（cfg_01.log）

```
(kernel 1 stats block, 末尾:)
kernel_name = _ZN2at6native54_GLOBAL__N__4b00444d...distribution_elementwise_grid_stride_kernel...  ← PyTorch init
gpu_tot_sim_cycle = 44959
gpu_tot_sim_insn  = 391716864
gpu_tot_ipc       = 8712.7578

(kernel 2 cumulative stats block, 末尾:)
kernel_name = _Z16flash_fwd_kernel...  ← 目标 kernel
gpu_tot_sim_cycle = 107043
gpu_tot_sim_insn  = 520031232
gpu_tot_ipc       = 4858.1528
```

### 5.2 Delta 提取（只保留 flash_fwd）

| 量 | 计算 | 结果 |
|----|------|------|
| Δcycles | 107043 − 44959 | **62084** |
| Δinsn | 520031232 − 391716864 | **128314368** |
| raw IPC | 128314368 / 62084 | **2066.79** |

### 5.3 单位归一（匹配 ncu 语义）

| 指标 | 公式 | 数值 | 对标 ncu |
|------|------|------|---------|
| **sim IPC (warp-IPC/SM)** | 2066.79 / (108 SMs × 32 lanes) = 2066.79 / 3456 | **0.598** | ncu `sm__inst_executed.avg.per_cycle_active` = **1.036** |
| **sim sm_busy_pct** | 2066.79 / (108×4×32 = 13824) × 100 | **14.95 %** | ncu `sm__throughput.avg.pct_of_peak_sustained_elapsed` = **35.0 %** |

> **两个除数不一样**：
> - warp-IPC 除以 `108 × 32 = 3456`（把总 thread-insts 折算到每 SM 每 active cycle 的 warp-insts）
> - sm_busy 除以 `108 × 4 × 32 = 13824`（peak 处每 SM 有 4 个 scheduler）
>
> 这是因为 ncu 的 IPC 是每 SM 每 active cycle 的 warp 指令数（peak=4），而 sm_busy 是 SM pipeline 利用率（占 peak SIMD 吞吐的比例）。两个量不一样，除数自然也不一样。

---

## 六、初步结果（13/13 ncu + 11/13 sim 时的快照）

> ⚠️ 本章数据仍会随剩余 sim 完成而更新，最终版会在所有 13 configs 都就绪后重新生成。

### 6.1 MAPE 汇总（10 个已完成 config）

| 指标 | MAPE (%) | 中位数 | 最大 | 在 ±20% 内 | 解读 |
|------|----------|--------|------|-----------|------|
| runtime_ms | **39.2** ⭐ | 30.6 | 108.9 | 4/10 | 最好对齐的指标 |
| ipc | 42.5 | 33.6 | 99.4 | 1/10 | sim 系统性偏低（缺 tensor core 建模） |
| sm_busy_pct | 39.8 | 55.9 | 99.4 | 4/10 | 与 ipc 相关，同样偏低 |
| l2_hit_pct | 209.8 | 146.3 | 514.1 | 3/10 | sim L2 命中率太乐观（几乎全中） |
| dram_util_pct | 462.5 | 167.0 | 1624.2 | 0/10 | sim 系统性高估内存带宽压力 |
| l1_hit_pct | **1086** ⚠️ | 751.7 | 3393.1 | 0/10 | 最差对齐；sim cache model vs 真实 A100 差距极大 |

### 6.2 瓶颈分类一致性

| 项 | 数值 |
|----|------|
| 分类一致 | **2 / 10 (20 %)** |
| 一致的 config | DEC-k512, DEC-k2k-GQA |
| 不一致的 config | FA-s512, FA-s1k, FA-s2k-d64, FA-s2k-H8, DEC-k1k, DEC-k2k, DEC-k4k, DEC-k2k-B32 |

### 6.3 关键洞察

> **sim 系统性将多数 config 判为 MEM-BW**，而 real GPU 更倾向于判为 COMPUTE 或 MIXED。原因不是 bug，而是：
>
> 1. sim L2 hit rate 几乎全是 ≥ 90 %（但 real A100 只有 16-95 %，并且随 seq 变化明显）——GPGPU-Sim 的 L2 容量模型偏乐观
> 2. sim DRAM 吞吐高估，再叠加 cache 命中率不准，导致 `dram_util_pct` 偏高
> 3. 结果：sim 看见"大量内存访问 + 高 DRAM 利用率" → 判 MEM-BW；real 看见"低 DRAM 利用率 + 中等 SM 繁忙" → 判 COMPUTE 或 MIXED

这与 ncu 一致认为 FA 在小 seq 是 compute-bound 的教科书结论相符。

---

## 七、已发现的坑（Debug 记录）

| 序号 | 现象 | 根因 | 解决方案 |
|------|------|------|---------|
| 1 | NVBit attach 失败 | NVBit 1.7.4 用 `CUDA_INJECTION64_PATH` 而非 `LD_PRELOAD` | 改注入方式 |
| 2 | `configs.csv` awk 解析错误 | Python csv 写入带 CRLF | 在 shell wrapper 里 `tr -d '\r'` |
| 3 | cfg_11/12/14 exit=141 但 trace 实际完成 | wrapper 末尾 `ls \| head` 在 `set -o pipefail` 下触发 SIGPIPE | 改成 `{ ls \| head; } \|\| true` |
| 4 | cfg_05 (FA s8k) 始终 0 kernel write | NVBit 在超大 flash_fwd kernel 上 instrument 卡死（22 min 无进展） | 接受放弃，13-config report |
| 5 | ncu ERR_NVGPUCTRPERM | `RmProfilingAdminOnly=1` 内核参数锁死 non-root counter | 用户加 passwordless sudo，wrapper 走 `sudo -E -n ncu` |
| 6 | ncu CSV 列名是 "Memory Throughput" 而非 raw metric 名 | 默认 `--page details` 会 flatten section | 改 `--page raw` |
| 7 | sim IPC MAPE 233460% | 单位混淆：sim=thread-insts/cycle 总和，ncu=warp-insts/cycle/SM | parse_sim 除以 108×32=3456 |
| 8 | cfg_13 sim 选错 kernel (CatArrayBatchedCopy) | 我在 kernel-198.traceg.xz post-processing 未完成时就启动 sim | 等文件写完再跑 |
| 9 | sim cfg_04 `no trace for cfg_04` | run_sim.sh 没尝试 `_reuse_src/NO_ARGS/traces/kernelslist.g` 路径 | 加多个 fallback path |

---

## 八、产出文件（路径清单）

| 类型 | 路径 | 数量 / 大小 |
|------|------|------------|
| 实验 spec | `docs/superpowers/specs/2026-04-14-fa-decode-sim-vs-real-mape-design.md` | 1 |
| 实施计划 | `docs/superpowers/plans/2026-04-14-fa-decode-sim-vs-real-mape.md` | 17 tasks |
| Config 清单 | `result/sim_vs_real_mape/scripts/configs.csv` | 14 rows |
| NCU 原始报告 | `result/sim_vs_real_mape/ncu_out/cfg_{01..14}.ncu-rep` | 14 文件 (5-34 MB) |
| NCU CSV (raw metrics) | `result/sim_vs_real_mape/ncu_out/cfg_{01..14}.csv` | 14 文件 |
| NCU 规范化 JSON | `result/sim_vs_real_mape/ncu_out/cfg_{01..14}.metrics.json` | 14 文件 |
| Sim 日志 | `result/sim_vs_real_mape/sim_logs/cfg_{01..14}.log` | 13 文件 (cfg_05 除外) |
| Sim 规范化 JSON | `result/sim_vs_real_mape/sim_logs/cfg_{01..14}.metrics.json` | 13 文件 |
| 合并表 | `result/sim_vs_real_mape/merged_metrics.csv` | 14 × 56 |
| 最终报告 | `result/sim_vs_real_mape/mape_report.md` | 含 Table 1/2/3 |
| 原型图（假数据） | `result/sim_vs_real_mape/figures/_proto_fig{1..4}.png` | 4 张（Brainstorm 阶段） |
| **待生产**：正式图 | `result/sim_vs_real_mape/figures/fig{1..4}.pdf` | 等数据完整后做 |

---

## 九、待补充事项（数据完整后）

1. ⏳ cfg_12、cfg_13 sim 跑完（进行中）
2. ⏳ 重跑 `parse_sim.py` + `collect_metrics.py` + `classify_bottleneck.py` + `make_report.py`
3. ⏳ 生产 4 张正式图（Fig 1 Roofline / Fig 2 MAPE / Fig 3 Trajectory / Fig 4 Stall）
4. ⏳ 根据真实数据分布回调 §4 的瓶颈阈值（当前 70/50/50 tentative）
5. ⏳ 把 mape_report.md + 4 张 PDF + merged_metrics.csv copy 到 `docs/superpowers/specs/sim_vs_real_mape_results/` 并 commit

---

## 十、参考原型图（已生成，待数据完整后重绘）

> 以下为假数据 prototype，用于确认布局。最终版用真数据 + `plot_util.py` 风格重绘为 PDF。

- **Fig 1 Roofline Overlay**：2 子图（FA | Decode），每个 config 画一对 (sim, real) 点 + 短连线
- **Fig 2 MAPE Breakdown**：2×3 子图，6 个指标并列，±20% 红线标合格区
- **Fig 3 Bottleneck Trajectory**：单图，随 seq/KV 主轴变化的 DRAM util 和 SM busy 折线
- **Fig 4 Stall Composition**：邻接 stacked bar，sim 实色 / real 半透明，5 种 stall 配共享深色 palette

原型预览见：`result/sim_vs_real_mape/figures/_proto_fig{1..4}.png`
