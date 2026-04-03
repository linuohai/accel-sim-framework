# DSE: GRASP 可调参数探索

> 最近更新: 2026-04-03

本文档记录已实现但默认关闭的 GRASP 优化特性，作为后续 DSE（Design Space Exploration）的候选参数。每个特性需通过对照实验（开启 vs 不开启）验证其对各 workload 的影响。

---

## 1. Speculative Stride（推测预取）

### 机制

GRASP stride 训练需要同一 warp 对同一 PC 执行两次 demand load 才能收敛（第一次记地址，第二次算 delta）。Speculative stride 在首次 observation 时即用预设值标记 `stride_valid=true`，使第一次 iteration 就能发起预取。第二次 observation 自动确认或修正。

### 参数

```
-grasp_speculative_stride <N>    # 0=关闭（默认），N>0 = 全局推测 stride
```

chain CSV 可选列 `stride_hint`：per-chain 推测 stride（优先于全局值），从 SASS 分析得出。

**优先级**：CSV stride_hint > data_size (from trace) > `-grasp_speculative_stride` 全局值

### 当前状态

**默认关闭**（`-grasp_speculative_stride 0`）。chain CSV 中已填入 SASS 分析的 stride_hint 值（BFS/SSSP/BC inner loop=4, unrolled×4=16, SpMV unrolled×16=64, 无循环 PC=0）。

### SASS 分析的 stride_hint 值

| 类型 | stride_hint | 适用 |
|------|-------------|------|
| Thread-ID 索引（无循环） | 0 | BFS/SSSP 0x00c0, BC 0x0090/0x00c0 |
| Inner loop base（step=1, int*） | 4 | BFS 0x01d0, SSSP 0x0250, BC 0x0200/0x01d0, SpMV 0x0200 |
| Unrolled ×4 | 16 | BFS/SSSP/BC 的 unrolled PCs |
| Unrolled ×16（SpMV） | 64 | SpMV 28 个 unrolled PCs |

### 初步实验结果（`-grasp_speculative_stride 4` + CSV stride_hint）

| Workload | Baseline | 旧 GRASP | Speculative | vs 旧 GRASP |
|----------|----------|----------|-------------|-------------|
| BFS | 23.56 | 29.75 | 30.81 | +3.56% |
| SSSP | 28.81 | 34.28 | 35.39 | +3.23% |
| SpMV | 129.68 | 164.12 | 175.35 | +6.84% |
| BC | 37.65 | 44.61 | 40.79 | -8.56% |
| Geomean | | | | +1.09% |

BC 退化原因待查（stride 值本身已正确，可能是推测机制的副作用）。

### 对照实验设计

| 配置 | 命令行 | 说明 |
|------|--------|------|
| A: 关闭（默认） | `--grasp` | 当前默认行为 |
| B: 开启 | `--grasp` + `-grasp_speculative_stride 4` | 全局推测 + CSV per-chain hint |

跑 BFS/SSSP/BC/SpMV（以及后续新增 workload），对比 IPC + IMA_DEMAND + Coverage。

### 代码位置

| 文件 | 改动 |
|------|------|
| `grasp_tables.h` | `ct_entry_t.stride_speculative`, `speculative_stride_hint`, `m_speculative_stride` |
| `grasp_tables.cc` | `update_stride()` 首次推测 + 二次确认 |
| `grasp_chain_detector.h/cc` | `data_size` 传递链路 |
| `grasp_prefetcher.h/cc` | config, CSV 解析 (`load_stride_hints`), CT insert hint 设置 |
| `gpu-sim.cc` | `-grasp_speculative_stride` option |
| `shader.h/cc` | config 字段 + copy |
| chain CSV | `stride_hint` 列 |

---

## 2. CT Reset Policy on Kernel Switch

### 机制

BFS 交替运行 `insert` kernel 和 `bfs_kernel`（不同 kernel function）。当前 `on_kernel_launch()` 对不同 kernel 执行 `m_ct.reset()`（全量重置 CT），清除已学到的 stride 信息，导致每轮 BFS level 重新训练。

### 参数（未实现）

```
-grasp_ct_reset_on_kernel_switch {full|tracking_only}
```
- `full`（默认，当前行为）：全量 reset CT
- `tracking_only`：仅清 per-warp tracking，保留 stride

### BFS 1SM 实测数据

| 指标 | 值 |
|------|-----|
| CT_INSERT(ct_new=1) 次数 | 30（6 chain × 5 轮 CTA） |
| STRIDE_CONVERGE 次数 | 30（每次 CT_INSERT 后重新收敛） |
| 无效期总 cycles | 65,358（占总仿真 4.1%） |
| stride_valid=0 的 demand 占比 | 6.7% |

### 风险

| 风险 | 严重性 | 缓解 |
|------|--------|------|
| 不同 kernel 有不同 IMA stride | 高 | BFS 的 insert/bfs_kernel 共享相同 index array |
| stride frozen 后无法更新 | 中 | 需要 unfreeze 机制 |

### 代码位置

`grasp_prefetcher.cc:240-243`（`m_ct.reset()` → `m_ct.reset_tracking()`）

### 状态

**未实现** — 待后续 DSE 探索。

---

## 3. Throttle Control: Cooldown Timer（已验证，推荐启用）

### 机制

DATA_PF 在 MSHR 占用率超阈值时被抑制，并进入固定长度冷却期（期间所有 DATA_PF 均被丢弃），给 cache/MSHR 子系统排空时间。INDEX_PF 始终不受影响。

### 参数

```
-grasp_tc_mode 4                    # 0=legacy(默认), 4=cooldown timer
-grasp_tc_mshr_threshold 40         # MSHR 占用率触发阈值 %（默认 80）
-grasp_tc_cooldown 200              # 冷却周期数（默认 0=关闭）
```

### 推荐配置: `tc_mode=4, thr=40, cooldown=200` (T40C200)

### 验证结果（9 workloads, Full-SM）

| Workload | ΔIPC | Baseline Acc | T40 Acc | ΔUseless | 类别 |
|----------|------|-------------|---------|----------|------|
| spmv_ima_med (sym) | **+3.47%** | 51.3% | 66.3% | -60.7% | 高收益 |
| spmv_road_sym | +0.88% | 87.8% | 88.6% | -49.1% | 中收益 |
| bfs_ima_small (sym) | +0.39% | 55.5% | 62.3% | -25.9% | 中收益 |
| sssp_ima_small (sym) | +0.37% | 52.5% | 59.1% | -24.3% | 中收益 |
| bfs_cit_dir | +0.07% | 99.9% | 99.9% | +0.0% | 安全 |
| sssp_cit_dir | +0.04% | 99.7% | 99.7% | +0.0% | 安全 |
| bc_cit_dir | +0.03% | 99.6% | 99.6% | +7.7% | 安全 |
| bc_road_dir | +0.00% | 100.0% | 100.0% | +0.0% | 安全 |
| bfs_road_dir | +0.00% | 0.0% | 0.0% | +0.0% | 安全 |

**0/9 退化。GeoMean(sym workloads) = +1.40%。**

### 核心发现

- 收益与 baseline accuracy 负相关：acc < 55% → +0.37~3.47%；acc > 99% → ~0%
- IPC 提升来自 MSHR 拥塞缓解 + cache pollution 减少，不是 miss 数量减少
- "不伤害"的默认配置：高 accuracy 无影响，低 accuracy 显著改善

### 代码位置

- 策略分发: `grasp_prefetcher.cc:701-761`（`inject_prefetch()` tc_mode dispatch）
- 配置字段: `grasp_prefetcher.h` `grasp_config_t::tc_mode/tc_mshr_threshold/tc_cooldown_cycles`
- 运行时状态: `grasp_prefetcher.h` `m_tc_cooldown_until`

### 状态

**已实现 + 已验证（9 workloads）**。推荐作为新默认。详细 DSE 数据见 `dse_throttle_control/README.md`。

---

## 对照实验总表

后续 DSE 以 2×2×2 矩阵方式验证三个特性的独立和组合效果：

| 配置 | Speculative Stride | CT Reset Policy | Throttle Control |
|------|-------------------|-----------------|------------------|
| A（当前默认） | OFF | full | legacy (thr=80) |
| B | ON (stride_hint) | full | legacy (thr=80) |
| C | OFF | tracking_only | legacy (thr=80) |
| D | ON (stride_hint) | tracking_only | legacy (thr=80) |
| E | OFF | full | **cooldown (T40C200)** |
| F | ON (stride_hint) | full | **cooldown (T40C200)** |

每个配置跑 BFS/SSSP/BC/SpMV，对比 IPC + Coverage + Timeliness。
