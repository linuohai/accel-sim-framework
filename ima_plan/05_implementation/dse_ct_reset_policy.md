# DSE: GRASP 可调参数探索

> 最近更新: 2026-04-02

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

## 对照实验总表

后续 DSE 以 2×2 矩阵方式验证两个特性的独立和组合效果：

| 配置 | Speculative Stride | CT Reset Policy |
|------|-------------------|-----------------|
| A（当前默认） | OFF | full |
| B | ON (stride_hint) | full |
| C | OFF | tracking_only |
| D | ON (stride_hint) | tracking_only |

每个配置跑 BFS/SSSP/BC/SpMV，对比 IPC + Coverage + Timeliness。
