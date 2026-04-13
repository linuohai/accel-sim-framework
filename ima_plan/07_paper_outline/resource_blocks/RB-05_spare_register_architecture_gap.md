# RB-05: Spare Register — 唯一 GPU IMA Prefetcher 的架构局限

> 创建: 2026-04-05
> 最近更新: 2026-04-05

## 核心想法

Spare Register (Lakshminarayana & Kim, HPCA 2014) 是文献中**唯一**针对 GPU 间接内存访问 (IMA) 的硬件预取方案。然而，该工作基于 2010 年的 Fermi 架构设计和评估，与当代 GPU (Ampere, Hopper) 在 cache hierarchy、warp scheduling、内存子系统等方面存在代际差异。GPU IMA prefetching 领域在此后**十年没有后续硬件方案**，中间出现的 GPU prefetcher (Snake, CAPS, WASP 等) 均不处理 IMA 模式。

## 要素

### 1. 论文机制概述

Spare Register 提出了一种针对 GPU 图算法中 A[B[i]] 模式的硬件预取方案，核心包括三个部分：

**检测机制 — Value Tag**：在 register file 上附加 value tag 和 load-id tag，追踪 load 返回值在后续指令中的传播。当一个 load 的返回值（index value）被用作另一个 load 的地址计算输入时，硬件识别出 "load-pair" 关系（即 IMA 的 index load → data load）。需要 **3 个循环迭代**完成训练确认。

**两步预取 — Index→Fill→Data**：
1. 检测到 index load 的 stride 后，预取未来迭代的 index 地址
2. 当 index prefetch 的数据返回 (fill) 时，用返回值计算 data load 地址，发出第二步预取

**存储策略 — Spare Register**：预取的数据不存入 L1 cache（避免 GPU 小 L1 的 pollution），而是存入当前 warp 未使用的 "空闲寄存器"。论文指出 Fermi 架构下通常有足够的空闲寄存器可用。

**硬件开销**：~1365 B/SM（register file 的 1.04%），包括 value tags (126 bits)、load-id tags (126 bits)、shadow iteration counters、allocated register lists。

**评估结果**：9 个图算法 kernel，平均 10% IPC 提升，最高 51%。

### 2. 目标架构：Fermi (2010)

论文设计和评估均基于 NVIDIA Fermi 架构（2010 年），关键参数：

| 参数 | Fermi (GF100) |
|------|:---:|
| L1D Cache | 16 KB（可配为 48 KB，牺牲 shared memory） |
| Shared Memory | 48 KB（可配为 16 KB） |
| Cache Line | 128 B（整行 fill） |
| Register File | 128 KB/SM (32,768 × 32-bit) |
| Max Warps/SM | 48 (1,536 threads) |
| Max CTA/SM | 8 |
| 评估平台 | MacSim (in-house GPU timing simulator) |

Spare Register 的多个设计决策直接源于 Fermi 的特征——尤其是 16 KB L1D 导致的严重 cache pollution 问题，这是 "spare register 存储" 方案的核心动机。

### 3. 现代 GPU 架构 (Ampere A100) 的变化

以下为事实性对比，展示十年间 GPU 微架构的代际演进：

| 参数 | Fermi (2010) | Ampere A100 (2020) | 变化 |
|------|:---:|:---:|------|
| L1D + Shared | 16+48 KB 或 48+16 KB | **192 KB** unified | 12× 容量，硬件自动分区 |
| Cache 粒度 | 128 B line | **32 B sector** within 128 B line | Fill/evict 粒度不同 |
| L2 Cache | 768 KB | **40 MB** | 52× 容量 |
| Register File | 128 KB/SM | **256 KB/SM** (65,536 × 32-bit) | 2× 容量 |
| Warp Scheduling | 近似 round-robin | GTO / two-level | 调度策略根本不同 |
| Memory | GDDR5 | **HBM2e** (2 TB/s) | 带宽和延迟特征不同 |
| SM 数量 | 16 | **108** | 6.75× |
| 制程 | 40 nm | **7 nm** | 面积/功耗预算不同 |

注：这些变化涵盖了 cache hierarchy、内存子系统、调度策略、规模等多个维度。论文中基于 Fermi 参数的设计权衡（如 "L1 太小必须用寄存器存数据"）在现代架构下需要重新审视。

### 4. GPU IMA Prefetching 的十年空白

2014 年 Spare Register 之后，GPU prefetching 领域的后续工作均**不处理 IMA 模式**：

| 年份 | 论文 | 会议 | 目标模式 | IMA 支持 |
|------|------|------|---------|:---:|
| 2014 | **Spare Register** | HPCA | Load-pair (IMA) | **✓** |
| 2018 | DSAP | IEEE Access | CSR 图遍历 | BFS 专用 |
| 2018 | CAPS | IPDPS | CTA-aware stride | ✗（显式排除 IMA） |
| 2018 | WASP | IEEE TC | Warp-aware stride | ✗ |
| 2018 | Stream | J.Supercomp | 仿射模式 | ✗ |
| 2023 | Snake | MICRO | Stride chain | ✗ |
| 2026 | **本工作 (GRASP)** | — | IMA chain | **✓** |

CAPS 在其检测阶段通过回溯 source register 发现间接依赖时，**主动跳过**该 load（论文原文："if the source register depends on a load, we skip it"）。Snake 通过 stride chain 扩展了可检测模式的范围，但本质仍依赖固定 stride，无法处理数据依赖地址。

这意味着 GPU 上的 IMA prefetching **在 Spare Register 之后处于十年空白期**——没有新的硬件方案被提出来处理这一访存模式。

### 5. 论文引用信息

- **完整引用**: N. B. Lakshminarayana and H. Kim, "Spare Register Aware Prefetching for Graph Algorithms on GPUs," in *Proc. HPCA*, 2014, pp. 614–625.
- **PDF 位置**: `ima_plan/02_related_work/gpu_irregular/Lakshminarayana和Kim - 2014 - Spare register aware prefetching for graph algorithms on GPUs.pdf`
- **评估 kernel**: H-BFS, H-SSSP, H-MST (Harish), LS-BFS, LS-SSSP, LS-MST (LoneStar), ST-Connectivity, Graph Coloring, MIS

## 候选位置

| 论文章节 | 使用方式 |
|---------|---------|
| **§1 Introduction**（主选） | 一两句定位："唯一的 GPU IMA HW prefetcher 基于十年前的 Fermi 架构" |
| **§6 Related Work**（辅选） | 更完整的机制描述 + 架构代际对比 |

### Introduction 候选措辞

> The only hardware prefetcher targeting GPU IMA is Spare Register [Lakshminarayana & Kim, HPCA 2014], which was designed and evaluated on the Fermi architecture (2010). In the decade since, no GPU hardware prefetching scheme has addressed IMA—subsequent work (CAPS, WASP, Snake) targets stride-based patterns and explicitly excludes data-dependent accesses.

### Related Work 候选措辞

> Lakshminarayana and Kim [HPCA 2014] proposed Spare Register, which detects load-pair relationships via value tags on the register file and stores prefetched data in idle registers to avoid L1 pollution. Evaluated on Fermi-era parameters (16 KB L1D, 128-byte cache lines, MacSim simulator), the scheme achieved an average 10% IPC improvement across 9 graph algorithm kernels. However, modern GPUs feature fundamentally different cache hierarchies (192 KB unified L1D with 32-byte sector granularity on A100), and the design trade-offs of the Fermi era—particularly the motivation for register-based storage over cache-based storage—require re-examination under contemporary architectures.

## 与其他资源块的关系

| 资源块 | 关系 |
|--------|------|
| RB-04 (CPU IMA 迁移) | 互补：RB-04 论证 CPU→GPU 不可行，RB-05 论证已有 GPU 方案过时 → 共同引出"需要新方案" |
| RB-03 (Cache/IMA Breakdown) | RB-03 的 L1 miss 高→需要 prefetching 结论，为 RB-05 的"为什么要做新方案"提供数据支撑 |
| RB-01 (Warp 延时缺口) | RB-01 说明 IMA 破坏延时隐藏 → RB-05 说明唯一前作已不适用 → 叙事递进 |

## 依赖与约束

| 项目 | 状态 |
|------|------|
| Spare Register 论文 PDF | **已有** (`02_related_work/gpu_irregular/`) |
| Fermi Whitepaper 参数 | **已有**（公开资料） |
| A100 Whitepaper 参数 | **已有** |
| 无图表（纯文字+表格） | 不需要绘图脚本 |
