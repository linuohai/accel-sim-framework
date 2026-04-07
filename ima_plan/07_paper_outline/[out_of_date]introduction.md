# Introduction 段落素材与论证结构

> 最近更新: 2026-03-29
> 本文件记录论文 Introduction 部分的关键论点、论证链条和支撑数据。
> 叙事骨架（A+B+C 融合方案）：IMA 问题 + GPU 严重性 → CPU 10 年积累但无法迁移 → GPU 15 年进化但回避 IMA → 钳形闭合 → ISA Insight + GRASP。
> Little's Law 定量推导移至 Motivation §3，Introduction 只用结论数据。

---

## §1.1 IMA 问题与 GPU 的交汇

### 第一段：问题定义——IMA 是不规则计算的核心瓶颈

图分析、稀疏线性代数、推荐系统中广泛存在间接内存访问（IMA）模式 `A[B[i]]`：一次 load 的地址依赖另一次 load 的返回值。这种数据依赖打破了所有传统 locality 假设——data load 的地址在 index load 完成前不可知，使得 stride/stream prefetcher 完全失效。

引用素材：
- IMP [Yu, MICRO'15]: "A majority of these irregular accesses come from indirect patterns of the form A[B[i]]"
- Prodigy [Talati, HPCA'21]: "Irregular workloads are typically bottlenecked by the memory system... such traversals access large volumes of data and offer little locality"
- Tyche [Xue, TACO'24]: "IMAs exhibit poor locality, making prefetching ineffective"
- DMP [Fu, HPCA'24]: "Indirect memory access is a critical bottleneck for modern CPUs, especially for graph analysis and sparse linear algebra applications"

补充论据（图计算的不可替代性）：图计算是一类不可替代的计算范式——社交网络分析、推荐系统、知识图谱、生物信息学中的核心操作本质上都是图遍历。与规则计算（GEMM、stencil）不同，图计算的不规则性是问题本身的固有属性，无法通过数据重排或算法替换消除。GPU 正成为图计算的主力平台（Gunrock, cuGraph）。

### 第二段：IMA 在 GPU 上的严重性（三重打击，定量结论）

GPU 通过海量 warp 交替执行隐藏内存延迟，但 IMA 从三个维度同时打破这一机制（详细推导见 Motivation §3）：

**(1) L1 miss rate 飙升** — IMA 的 data load 地址呈随机 scatter pattern，摧毁 L1 空间局部性：

| Workload | L1 Miss Rate | 有效延迟 $L_{\text{eff}}$ |
|----------|-------------|--------------------------|
| bfs_ima_high | 77.22% | ~162 cycles（vs 规则负载 ~50 cycles） |
| sssp_ima_high | 76.66% | ~161 cycles |
| bc_ima_high | 70.25% | ~151 cycles |

**(2) 串行依赖链** — index→data 的数据依赖使有效延迟翻倍：$L_{\text{chain}} \approx 400$ cycles

**(3) 计算极少** — IMA 循环体仅 $C \approx 3$ cycles → 所需 warp 数 ~133，远超 A100 物理限制 64

### IMA 是 L1 miss 的绝对主因

| Workload | IMA miss share |
|----------|---------------|
| bfs_ima_high | **79.3%** |
| sssp_ima_high | **51.1%** |
| bc_ima_high | **70.5%** |
| cc_ima_high | **83.6%** |
| spmv_ima_high | **66.9%** |

### Ideal L1D 验证：优化空间巨大

| Workload | Baseline IPC | Ideal L1D IPC | Speedup |
|----------|-------------|---------------|---------|
| bfs_ima_high | 102.34 | 178.80 | **1.75×** |
| sssp_ima_high | 90.43 | 222.78 | **2.46×** |
| bc_ima_high | 104.04 | 315.89 | **3.04×** |
| cc_ima_high | 426.72 | 948.09 | **2.22×** |
| spmv_ima_high | 373.98 | 865.07 | **2.31×** |

Geomean ≈ **2.3×**。IMA 导致的 L1 miss 使图负载损失了超过一半的潜在性能。

**过渡句**: 要释放这些性能，需要专门的 IMA prefetcher——但 GPU 上至今没有。这个空白来自两个方向的各自局限。

---

## §1.2 CPU 的 10 年 IMA 之战——成熟但无法迁移

> 叙事目标：展示 CPU IMA prefetching 是成熟研究线（建立学术脉络），然后论证这些方案无法迁移到 GPU（第一把钳）。

### CPU IMA Prefetcher 的演进

CPU 社区对 IMA 的研究已有近十年积累，硬件和软件两条路线齐头并进：

**硬件路线** —— 从地址差分到指令依赖链：

| 年份 | 方案 | 核心机制 | 关键结果 | 出处 |
|------|------|---------|---------|------|
| 2015 | **IMP** | 地址差分反推 shift (试探 2/3/4/-3) + partial cacheline | 56% avg speedup | Yu, MICRO'15 |
| 2020 | **ATP** | SW-HW 混合，编译器插入元数据指令配置硬件 + 动态 distance | 2.17× avg | Cavus, TACO'20 |
| 2021 | **Gretch** | 纯硬件 DDA 检测，解决 instruction scheduling 敏感性 | 38% over no-pf | Kaushik, TACO'21 |
| 2024 | **DMP** | 差分匹配识别四类间接模式（单/范围/多层/多路） | 1.8× avg, 0.9KB | Fu, HPCA'24 |
| 2024 | **Tyche** | 双向传播挖掘指令依赖链，通用 IMA 识别 | 16.2% over Berti, 0.57KB | Xue, TACO'24 |

**软件 / 加速器路线** —— 从编译器辅助到可编程硬件：

| 年份 | 方案 | 核心机制 | 关键结果 | 出处 |
|------|------|---------|---------|------|
| 2013 | **Linearizing** | 将间接访问线性化为可预取序列 | — | Jain, 2013 |
| 2021 | **Prodigy** | HW-SW 协同，DIG 表示 + 编译器 pass | 2.6× avg, 0.8KB | Talati, HPCA'21 |
| 2025 | **ASaP** | MLIR 稀疏张量 dialect 自动注入 | SpMV 1.38× over A&J | Sotiropoulos, SC'25 |
| 2025 | **Magellan** | 跨循环层次检测 IMA 依赖图 | 1.14× avg | Fu, ISCA'25 |
| 2025 | **DX100** | 可编程间接访问加速器，请求重排/合并 | 2.6× over multicore | Khadem, ISCA'25 |

每一代解决一个新维度：单层→多层→非线性→编译器辅助→可编程。但关键转折是：**这些方案全部为 CPU 设计**。

### 四大迁移障碍

这些方案的设计假设与 GPU 微架构存在根本性冲突：

| 障碍 | CPU 假设 | GPU 现实 |
|------|---------|---------|
| **地址流交织** | 单线程/少线程，地址流清晰 | 每 SM 64 warp 同 PC 访问高度交织，pattern detection 基础被破坏 |
| **硬件预算** | Per-core 状态表 ~1KB 可行 | Per-warp 全量复制不现实（64×1KB = 64KB/SM） |
| **L1 容量** | 32–64 KB/core，预取数据可保留 | 32–128 KB 被 64 warp 共享，预取数据极易被驱逐 |
| **PC 膨胀** | 展开少（1-2×），per-PC 追踪可行 | 编译器展开 4-16×，1 条源码 load → 5-30 个不同 PC（SpMV 60+） |

引用素材：
- Many-Thread Aware [Lee, MICRO'10]: "straightforwardly applying [CPU] mechanisms to GPGPU systems does not deliver the expected performance benefits and can in fact hurt performance"
- APRES [Oh, ISCA'16]: "massive Thread-Level Parallelism often causes excessive cache contention"

**过渡句**: CPU 的 IMA 方案成熟但绑定 CPU 微架构。那么 GPU 自身的 prefetching 研究呢？

---

## §1.3 GPU Prefetching 15 年进化的盲区

> 叙事目标：展示 GPU prefetching 也在不断进化（建立 GPU 研究脉络），但所有工作都回避 IMA（第二把钳）。

### 四代 GPU Prefetcher 的进化

GPU prefetching 研究超过 15 年历史，可大致分为四个阶段：

| 阶段 | 代表 | 核心贡献 | 关键数据 |
|------|------|---------|---------|
| 一代 (2010) | **Many-Thread Aware** [Lee, MICRO'10] | 发现 CPU prefetcher 不能直搬 GPU，提出 inter-thread prefetching + 自适应节流 | avg 16% |
| 二代 (2013) | **Orchestrated** [Jog, ISCA'13], **APOGEE** [Sethia, PACT'13] | 认识到调度与预取必须协同；自适应能效优化 | 25% over RR; 90% accuracy |
| 三代 (2016-18) | **CAPS** [Koo, IPDPS'18], **APRES** [Oh, ISCA'16] | CTA 感知 leading-warp 检测；负载特征分类+调度 | 97% accuracy; 31.7% |
| 四代 (2023) | **Snake** [Mostofi, MICRO'23] | 突破固定 stride，variable-length chain + 节流 + 内存解耦 | 80% coverage, 17% |

补充：Treelet [Chou, MICRO'23] 在 ray tracing 领域针对 BVH 树 pointer-chasing 提出 treelet 预取 (32.1%)，但限于 RT 专用硬件。

### 共同的盲区——所有四代均假设地址可预测

四代 GPU prefetcher 在不同维度取得了进展，但共享一个核心假设：**地址流中存在可检测的步幅或流式 pattern**。面对 IMA，这个假设彻底失效：

- **CAPS 显式排除** indirect/data-dependent 访问——通过回溯 source register 检测到数据依赖后直接跳过
- **Snake 的 variable-length chain 仍然是步幅链**——每一步是一个 stride delta，而 IMA 的 data 地址由运行时 index 值决定，不存在 delta 规律
- **WASP 的分析证实**：BFS/SpMV 的 inter-warp stride ratio 远低于规则应用——从根本上缺乏 stride 信号

### 仅有的 GPU IMA 尝试

GPU 上唯一直接针对 IMA 的硬件方案是 **Spare Register** [Lakshminarayana & Kim, HPCA'14]：

**有价值的思路**: 利用空闲寄存器存储预取数据避免 L1 驱逐

**技术局限**:
1. **检测延迟高**: tag-based 依赖传播需 3 次循环迭代建立 load-pair（IMP 需 2 次，本工作 1 次指令观测）
2. **侵入式实现**: 向指令流注入 load/mov 指令，在 Volta+ independent thread scheduling 下正确性更难保证
3. **仅单层 load-pair**: 不支持 one-to-many（如 BC reverse 1 index → 3 data）
4. **架构绑定**: 基于 Fermi (2010) 评估，与 SM80+ 的 L1/shared memory 组织差异根本性

**实验结果**: avg 10%, up to 51% (9 个 graph kernel)

软件方面：GPU 软件预取 [Deng, DaMoN'24] 在 Ampere+ 上评估了 hash join (1.19×) 和 BTree search (1.31×)，但指令开销限制了其在 compute-light IMA 场景的适用性。BFS-specific prefetch [Guo, 2018] 利用 BFS 数据结构信息但不具通用性。DSAP [IEEE Access'18] 也仅针对 BFS。

### Gap 总结（钳形闭合）

> CPU 社区在 IMA prefetching 上积累了近十年经验（IMP→ATP→Gretch→DMP→Tyche；Prodigy→Magellan→DX100），但所有方案都绑定 CPU 微架构假设——单线程地址流、per-core 状态表、低 loop unrolling——无法迁移到 GPU 的海量 warp 环境。
>
> GPU prefetching 社区在 15 年间从 stride 到 scheduling-aware 到 variable-chain 不断演进（Many-Thread→Orchestrated→CAPS→Snake），但从未触及数据依赖驱动的间接访问——因为它在传统 stride/stream 框架下"不可预取"。
>
> 两个方向在 **GPU IMA prefetching** 这个交叉点留下了空白。

| Gap | 描述 |
|-----|------|
| **Gap 1** | GPU 上缺少**通用**的 IMA hardware prefetcher——Spare Register 仅支持单层 load-pair (Fermi)，DSAP 仅针对 BFS |
| **Gap 2** | CPU IMA 方案（IMP/DMP/Tyche/DX100）未考虑 GPU 微架构约束（海量 warp、小 L1、地址流交织、PC 膨胀） |
| **Gap 3** | 现有所有 GPU prefetcher（含 Spare Register）均未利用 GPU ISA 提供的 IMA 结构性信息（IMAD.WIDE 暴露的 scale/base） |

---

## §1.4 我们的发现与 GRASP

### 核心发现：GPU ISA 将 IMA 参数结构性暴露

虽然 CPU 的 IMA 检测方法无法迁移到 GPU，但我们发现 GPU 的 SASS ISA 提供了 CPU 所不具备的结构性优势：

```
IMAD.WIDE Rd, Rindex, Rscale, c[0x0][0x1XX]
```

这条指令将 IMA 地址计算 `base + index × scale` 的三个关键参数**直接暴露为指令操作数**：
- **Scale** (Rscale): 编译期常量 sizeof(element)，由 C++ 类型系统保证
- **Base** (c[0x0][...]): constant memory 中的 kernel 参数指针，整个 kernel launch 不变
- **Index value** (Rindex): 前序 LDG 的返回值

这不是经验性观察，而是**结构性保证**：IMAD.WIDE 是 SASS ISA 中唯一能单指令完成 32×32+64→64 宽乘加的指令，编译器在标准类型场景下必然选择它。在 8 个图算法家族的 56 个实现中，IMAD.WIDE 链覆盖了 88.4% 的 IMA 依赖链（排除系统性反例 SCC 后为 93.6%）。

**与已有方案的核心差异**:

| 方案 | IMA 检测方式 | 检测延迟 | 信息来源 |
|------|------------|---------|---------|
| IMP [MICRO'15] | 地址差分 + shift 试探 (2/3/4/-3) | 需积累地址序列 | 黑盒推断 |
| DMP [HPCA'24] | 差分序列比例匹配 | 需积累差分序列 | 黑盒推断 |
| Spare Register [HPCA'14] | value tag + load-id tag 传播 | 3 次循环迭代 | 黑盒推断 |
| **GRASP (本工作)** | **IMAD.WIDE 操作数直接读取** | **1 次指令观测** | **ISA 白盒提取** |

### 附带结构性优势

IMAD.WIDE 还自然解决了两个 GPU 特有的设计难题：

- **PC 膨胀归并**: 编译器 loop unrolling 将 1 条源码 load 膨胀为 5-30+ 个不同 PC，但所有展开副本共享同一个 (base, scale) constant operand → 自动归并到 1 个 pattern entry（SpMV 的 60+ PC → ~2 entries）
- **Per-SM 共享的 64 倍分摊**: Chain Table / Target Table 为 per-SM shared，任何 warp 的检测结果立即对同 SM 全部 64 个 warp 可用——训练开销被 64 倍分摊，这是 SIMT 执行模型的天然产物

**关键论断**：IMAD.WIDE 不是设计上的"简化"，而是 GPU ISA 结构性提供的优势。简洁的设计不是缺乏深度，而是 insight 驱动的结果。

### GRASP 方案概述

基于这些 insight，我们提出 **GRASP**（GPU Register-chain Aware Sector Prefetcher）：

**工作原理**: 在指令 issue 阶段检测 `LDG→IMAD.WIDE→LDG` 寄存器依赖链 → 提前发出 index prefetch → index 值返回后立即计算 data 地址 → 发出 data prefetch。整个过程利用 ISA 暴露的参数完成，无需地址推断或指令流修改。

**初步结果**: SSSP +42.2%, IMA-tiny +53.6%; BFS coverage 93.3% / accuracy 55.9% / timeliness 89.6%。

### Contribution 列表

1. **IMA 特征化与分类体系**：建立四类 IMA pattern（Linear Gather → Pointer Chasing）的多层次分类框架，从源码、SASS 指令到微架构三个层次量化图 workload 的 IMA 行为。揭示 IMA 占 L1 miss 51%–84%、L1 miss 导致 warp 延迟隐藏机制失效的关键发现。

2. **GPU IMA Hardware Prefetcher 设计**：提出 **GRASP**，基于 IMAD.WIDE 检测的 Index-Data Pipeline（index prefetch → data prefetch），利用 GPU ISA 的结构性优势实现零推断 IMA 检测，通过 (base, scale) 归并解决 PC 膨胀问题，支持 one-to-many 多目标预取。据我们所知，这是首个利用 GPU ISA 结构性特征实现 IMA 检测的硬件 prefetcher，也是首个在现代 GPU 架构（SM80, A100）上设计与评估的通用 IMA prefetcher。

3. **全面评估**：在 Accel-Sim/GPGPU-Sim 上对 5 类图算法（BFS/SSSP/BC/CC/SpMV）进行评估，与 4 种 SOTA baseline（stride-INTRA, stride-INTER, Snake, Spare Register）对比，展示平均 X% IPC 提升（达到 ideal L1D 天花板的 Y%），硬件开销 ~Z KB/SM。

---

## §1.5 论证链条总览

```
¶1 IMA 是不规则计算的核心瓶颈 [IMP, Prodigy, Tyche, DMP]
    ↓
¶1 IMA 在 GPU 上尤其严重
    ├─ L1 miss rate 70-77% → L_eff 从 50 飙升到 160 cycles
    ├─ index→data 串行依赖链 → L_chain = 400 cycles
    ├─ 循环体计算极少 → C ≈ 3 cycles → N_required = 133 >> N_max = 64
    ├─ IMA 占 L1 miss 51-84%
    └─ Ideal L1D 天花板 1.75×-3.04× (geomean 2.3×)
    ↓
¶2 CPU 有 10 年 IMA 积累 [IMP→ATP→Gretch→DMP→Tyche; Prodigy→Magellan→DX100]
    ├─ 每一代解决一个新维度
    └─ 但四大障碍无法迁移 GPU（warp 交织 / 小 L1 / PC 膨胀 / 存储预算）
    ↓
¶3 GPU prefetching 15 年进化 [Many-Thread→Orchestrated→CAPS→Snake]
    ├─ 四代都假设 stride/stream pattern
    ├─ CAPS 显式排除 IMA; Snake chain = stride chain
    └─ 唯一 GPU IMA 尝试: Spare Register [HPCA'14] (10%, Fermi, tag-based, 单层)
    ↓
    ╔═══════════════════════════════════════════════════════════════╗
    ║ 钳形闭合：CPU 解决了 IMA 但绑定 CPU 微架构                      ║
    ║           GPU 发展了 prefetching 但从未触及 IMA                ║
    ║           → GPU IMA prefetching 是交叉空白                    ║
    ╚═══════════════════════════════════════════════════════════════╝
    ↓
¶4 BUT: GPU ISA 提供了 CPU 所不具备的结构性优势
    ├─ IMAD.WIDE 零推断暴露 scale/base/index
    ├─ (base, scale) 归并解决 PC 膨胀
    └─ per-SM 共享表 64 倍分摊训练开销
    ↓
¶4 本工作：GRASP — 首个现代 GPU 通用 IMA prefetcher
    ↓
Contribution: 特征化 + 设计 + 评估
```

---

## §1.6 可用的 Related Work 定位句

> 用于 Introduction 中简要提及已有工作的不足

- "Prior GPU prefetchers (CAPS [IPDPS'18], WASP [TC'18], Snake [MICRO'23]) target stride-based patterns and explicitly exclude or cannot handle indirect memory access."
- "CPU IMA prefetchers (IMP [MICRO'15], DMP [HPCA'24], Tyche [TACO'24]) assume single-threaded address streams and modest hardware budgets, neither of which holds on GPUs with 64 concurrent warps per SM."
- "The only prior GPU work directly addressing IMA — Spare Register [HPCA'14] — employs a tag-based detection mechanism borrowed from CPU thinking, supports only single-level load-pairs, and was designed for the Fermi architecture (2010), which differs fundamentally from modern GPUs in L1/shared memory organization and thread scheduling."
- "We observe that GPU's IMAD.WIDE instruction structurally exposes the scale and base of indirect address computations as instruction operands — information that CPU prefetchers (IMP, DMP) must infer through costly address differential matching, and that Spare Register's tag propagation detects only after three loop iterations."
- "Our design's simplicity is not a limitation but a direct consequence of exploiting this ISA-level structural advantage — a key insight that prior work has not recognized."

---

## §1.7 Introduction 文献引用清单

### 在 Introduction 中直接引用（~21 篇）

**¶1 IMA 问题定义 + GPU 严重性**:
- IMP [Yu, MICRO'15] — 定义 A[B[i]] 问题
- Prodigy [Talati, HPCA'21] — irregular workload 瓶颈
- Tyche [Xue, TACO'24] — IMA poor locality
- DMP [Fu, HPCA'24] — critical bottleneck

**¶2 CPU IMA 演进 + 迁移障碍**:
- IMP [Yu, MICRO'15] — 56% avg, shift 试探
- ATP [Cavus, TACO'20] — 2.17×, SW-HW 混合
- Gretch [Kaushik, TACO'21] — 38%, graph DDA
- DMP [Fu, HPCA'24] — 1.8×, 差分匹配
- Tyche [Xue, TACO'24] — 16.2%, 双向传播
- Prodigy [Talati, HPCA'21] — 2.6×, DIG
- Magellan [Fu, ISCA'25] — 1.14×, 跨循环层次
- DX100 [Khadem, ISCA'25] — 2.6×, 可编程加速器

**¶3 GPU Prefetching 进化 + 盲区**:
- Many-Thread [Lee, MICRO'10] — MT-prefetching, 16%
- Orchestrated [Jog, ISCA'13] — 调度+预取协同, 25%
- APOGEE [Sethia, PACT'13] — 自适应能效, 90% accuracy
- CAPS [Koo, IPDPS'18] — CTA 感知, 97% accuracy
- APRES [Oh, ISCA'16] — 负载特征分类, 31.7%
- Snake [Mostofi, MICRO'23] — variable-chain, 80% coverage
- Spare Register [Lakshminarayana, HPCA'14] — 唯一 GPU IMA, 10%
- SW Prefetch GPU [Deng, DaMoN'24] — GPU 软件预取
- BFS Prefetch [Guo, 2018] — BFS 专用
- Treelet [Chou, MICRO'23] — RT 专用, 32.1%
- WASP — stride ratio 数据

### 仅在 Related Work 中详细讨论:
- ASaP [Sotiropoulos, SC'25] — MLIR 自动预取
- Linearizing [Jain, 2013] — 间接访问线性化
- Alecto [Li, HPCA'25] — prefetcher 选择
- Sublining [Heirman, TACO'21] — sparse access 优化
- G-MAP [Panda, DAC'17] — GPU 内存建模
- PIM Prefetching [Panda, ICS'16] — near-memory
- HW Prefetchers Parallel [Panda, PACT'12] — 并行应用
- Symbiotic Task [Posluns, MICRO'25] — task-parallel
- COMPASS [Woo, MICRO'10] — 可编程 GPU prefetcher

---

## §1.8 图算法重要性的论证素材

> 嵌入 ¶1 第一段，避免独立成段

### 结构性论据

图计算是一类**不可替代**的计算范式——社交网络分析、推荐系统、知识图谱、生物信息学、电路设计中的核心操作本质上都是图遍历。与规则计算（GEMM、stencil）不同，图计算的**不规则性是问题本身的固有属性**，无法通过数据重排或算法替换消除。

### 量化论据（可选引用）

- GPU 图计算框架（Gunrock [PPoPP'16, TOPC'17]、nvGraph、cuGraph）在学术界和工业界被广泛采用
- Gardenia [IISWC'19] 提供了标准化的 GPU 图算法基准集
- Pannotia [IISWC'12] 的 quantitative study 表明 GPU 上 irregular applications 的 L1 miss rate 系统性高于 regular applications

### 与 GPU 发展趋势的关系

GPU 正从专用图形/HPC 加速器演变为通用计算平台。IMA prefetcher 不仅解决图算法的性能问题，更是补齐 GPU 通用计算能力的关键一步。

---

## Appendix: Little's Law 定量推导（移至 Motivation §3）

> 以下内容从原 §1.1/§1.2 移出，用于 Motivation section 的详细展开。

### 延迟隐藏的定量模型

GPU SM 通过 warp 交替执行隐藏内存延迟。设每个 warp 在两次 memory-dependent stall 之间执行 $C$ 个 cycle 的计算，SM 上有 $N$ 个 active warp，内存有效延迟为 $L_{\text{eff}}$，则延迟被完全隐藏的条件是：

$$N \times C \geq L_{\text{eff}}$$

**规则负载**满足条件：
- 访存 coalesced → L1 hit rate 高（~90%）
- $L_{\text{eff}} = 0.9 \times 34 + 0.1 \times 200 \approx 50$ cycles
- Compute-heavy：$C$ 大（数十到数百个 FMA）
- $N \times C \gg L_{\text{eff}}$ ✓

**IMA 负载**三重打击：
- L1 miss rate 70-77% → $L_{\text{eff}} \approx 160$ cycles（规则负载的 3 倍）
- index→data 串行依赖 → $L_{\text{chain}} = 200 + 200 = 400$ cycles
- $C \approx 3$ cycles

$$N_{\text{required}} = \frac{L_{\text{chain}}}{C} = \frac{400}{3} \approx 133 \text{ warps}$$

$$N_{\max} = 64 \ll 133 = N_{\text{required}}$$

即使充分利用所有 warp 槽位，延迟仍有 $\frac{133-64}{133} \approx 52\%$ 无法被隐藏。

**参数来源**（SM80_A100 gpgpusim.config）：
- $L_{\text{hit}}$：L1 hit latency ≈ 34 cycles
- $L_{\text{miss}}$：L1 miss → L2 hit latency ≈ 200 cycles（`-gpgpu_l2_rop_latency 200`）
- $N_{\max}$：每 SM 最多 64 warp（A100）
