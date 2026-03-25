# Introduction 段落素材与论证结构

> 本文件记录论文 Introduction 部分的关键论点、论证链条和支撑数据。
> 按修正后的叙事骨架组织：GPU 并行基石 → IMA 打破前提 → 现有方案空白 → 我们的发现与方案。

---

## §1.1 GPU 并行能力的来源与前提条件

### 核心论点

GPU 的高吞吐量并行能力建立在一个关键前提之上：**通过海量 warp 交替执行来隐藏内存访问延迟**。这个机制要求内存访问具有足够的空间局部性（coalesced/strided），使大部分访问能命中 L1 cache，从而保持较低的有效延迟。

### 延迟隐藏的定量模型（Little's Law 变体）

GPU SM 通过 warp 交替执行隐藏内存延迟。设每个 warp 在两次 memory-dependent stall 之间执行 $C$ 个 cycle 的计算，SM 上有 $N$ 个 active warp，内存有效延迟为 $L_{\text{eff}}$，则延迟被完全隐藏的条件是：

$$N \times C \geq L_{\text{eff}}$$

**规则负载**（dense GEMM、stencil computation 等）满足这个条件：

- 访存 coalesced → L1 hit rate 高（~90%）
- 有效延迟低：$L_{\text{eff}} = 0.9 \times L_{\text{hit}} + 0.1 \times L_{\text{miss}} = 0.9 \times 34 + 0.1 \times 200 \approx 50$ cycles
- Compute-heavy：$C$ 大（数十到数百个 FMA）
- $N \times C \gg L_{\text{eff}}$ → 延迟被轻松隐藏 ✓

**参数来源**（SM80_A100 gpgpusim.config）：
- $L_{\text{hit}}$：L1 hit latency ≈ 34 cycles
- $L_{\text{miss}}$：L1 miss → L2 hit latency ≈ 200 cycles（`-gpgpu_l2_rop_latency 200`）
- $N_{\max}$：每 SM 最多 64 warp（A100）

---

## §1.2 IMA 从根本上打破 GPU 延迟隐藏的前提

### 核心论点

图算法中的 Indirect Memory Access（IMA）—— `data[index[i]]` ——从两个维度**同时**打破延迟隐藏的条件，使 GPU 的并行优势无法发挥。

### 第一重打击：L1 miss rate 飙升 → $L_{\text{eff}}$ 剧增

IMA 的 data load 地址由 index 值的运行时数据决定，呈现高度随机的 scatter pattern，完全摧毁 L1 cache 的空间局部性：

| Workload | L1 Miss Rate | $L_{\text{eff}}$ |
|----------|-------------|-----------------|
| bfs_ima_high | 77.22% | $0.23 \times 34 + 0.77 \times 200 \approx 162$ cycles |
| sssp_ima_high | 76.66% | ≈ 161 cycles |
| bc_ima_high | 70.25% | ≈ 151 cycles |

对比规则负载的 $L_{\text{eff}} \approx 50$ cycles，IMA 的有效延迟增大了 **3 倍**。

### 第二重打击：串行依赖链 → 有效延迟翻倍

但上述还不是问题的全部。IMA 的 index load 和 data load 之间存在**数据依赖**——data load 的地址必须等待 index load 返回后才能计算。这形成了一个串行依赖链：

```
index load 发出 → [等待 ~200 cycles] → index 值返回 → 计算 data 地址 → data load 发出 → [等待 ~200 cycles] → data 值返回
```

有效延迟变为两次 L1 miss 的串行叠加：

$$L_{\text{chain}} = L_{\text{miss}}(\text{index}) + L_{\text{miss}}(\text{data}) \approx 200 + 200 = 400 \text{ cycles}$$

### 第三重打击：极少的计算量 → $C$ 极小

IMA 循环体（CSR 邻居遍历）的计算极为稀薄——SASS 中 index load 到 data load 之间仅有 1 条 `IMAD.WIDE`（地址计算），data load 返回后仅有 1-2 条比较/分支指令：

$$C \approx 2\text{-}5 \text{ cycles}$$

### 定量论证：延迟隐藏条件不可满足

将三重打击合并：

$$N_{\text{required}} = \frac{L_{\text{chain}}}{C} = \frac{400}{3} \approx 133 \text{ warps}$$

$$N_{\max} = 64 \ll 133 = N_{\text{required}}$$

**A100 每 SM 最多 64 个 warp，物理上不可能满足 133 warp 的需求。** Warp 交替执行——这一 GPU 并行计算的基石——在 IMA 面前失效了。即使充分利用所有 warp 槽位，内存延迟仍有约 $\frac{133 - 64}{133} \approx 52\%$ 无法被隐藏。

### Ideal L1D 验证：优化空间巨大

这一分析与 ideal L1D 实验结果完全吻合——当 L1 miss 被消除时（等价于将 $L_{\text{eff}}$ 降至 $L_{\text{hit}}$），性能提升巨大：

| Workload | Baseline IPC | Ideal L1D IPC | Speedup |
|----------|-------------|---------------|---------|
| bfs_ima_high | 102.34 | 178.80 | **1.75×** |
| sssp_ima_high | 90.43 | 222.78 | **2.46×** |
| bc_ima_high | 104.04 | 315.89 | **3.04×** |
| cc_ima_high | 426.72 | 948.09 | **2.22×** |
| spmv_ima_high | 373.98 | 865.07 | **2.31×** |

Geomean speedup ≈ **2.3×**。这意味着 IMA 导致的 L1 cache miss 使这些图负载损失了**超过一半**的潜在性能。

### IMA 是 miss 的绝对主因

进一步的 miss 归因分析确认，IMA 相关的 load 贡献了 L1 miss 的绝对多数：

| Workload | IMA miss share |
|----------|---------------|
| bfs_ima_high | **79.3%** |
| sssp_ima_high | **51.1%** |
| bc_ima_high | **70.5%** |
| cc_ima_high | **83.6%** |
| spmv_ima_high | **66.9%** |

**结论**：IMA 从根本上打破了 GPU 延迟隐藏的前提条件，导致巨大的性能损失。要在图算法等 IMA-heavy 领域释放 GPU 的并行潜力，必须从 cache 层面解决 IMA 导致的 L1 miss 问题——这正是 prefetcher 的角色。

---

## §1.3 现有方案的空白

### 传统 GPU Prefetcher 对 IMA 无效

传统的 stride/stream prefetcher 依赖地址序列的规律性（固定 stride 或顺序流），但 IMA 的 data load 地址由 index 值的运行时数据决定，呈现高度不规则的 scatter pattern。

GPU 上已有的 prefetcher **显式排除或无法处理 IMA**：

- **CAPS [IPDPS'18]**：显式排除 indirect/data-dependent 访问（通过回溯 source register 检测并跳过）
- **WASP [IEEE TC'18]**：量化了 BFS/SpMV 的 inter-warp regular stride ratio 远低于规则应用
- **Snake [MICRO'23]**：本质仍依赖固定 stride 模式的 chain 扩展

### CPU IMA Prefetcher 无法直接迁移 GPU

CPU 端已有成熟的 IMA prefetcher（IMP [MICRO'15], DMP [HPCA'24], Tyche [TACO'24]），但它们的设计假设与 GPU 微架构存在根本性冲突：

| 障碍 | CPU 假设 | GPU 现实 |
|------|---------|---------|
| **地址流交织** | 单线程/少线程，地址流清晰 | 每 SM 64 warp，同 PC 的访问高度交织，破坏 pattern detection |
| **硬件预算** | Per-core 状态表可行（~1KB） | Per-warp 全量状态表不现实（64 warp × 1KB = 64KB/SM） |
| **L1 容量** | L1 较大（32–64 KB/core），预取数据可保留 | L1 极小（32–128 KB 共享），预取数据易被提前驱逐 |
| **Loop unrolling → PC 膨胀** | 展开少（1-2×），per-PC 追踪可行 | 编译器展开 4-16×，1 条源码 load → 5-30 个不同 PC |

### Spare Register [HPCA'14]：唯一的前序工作，但存在技术局限

Spare Register（Lakshminarayana & Kim, HPCA 2014）是唯一直接针对 GPU 图算法 IMA 的硬件 prefetcher。它提出了有价值的思路（利用空闲寄存器存储预取数据避免 L1 驱逐），但存在以下**技术层面的局限**：

| 局限 | 具体内容 | 与本工作的差异 |
|------|--------|-------------|
| **检测方式原始** | 使用 value tag + load-id tag 传播追踪依赖（本质是 CPU tag-based 思路搬到 GPU），未利用 GPU ISA 的结构性信息。需要 **3 次循环迭代** 才能检测到 load-pair | 本工作利用 IMAD.WIDE 的操作数直接提取 IMA 参数，**零推断、1 次指令观测即可建立依赖** |
| **侵入式实现** | 向指令流中注入额外的 load/mov 指令（修改 pipeline 行为），在 Volta+ 的 independent thread scheduling 下正确性更难保证 | 本工作作为独立硬件模块（L1 client），**不修改指令流** |
| **仅支持单层 load-pair** | 只能处理 `A[B[i]]` 单层间接，不支持 one-to-many（如 BC reverse 的 1 index → 3 data） | 本工作通过 Target Table (TT) 的 `targets[K]` 支持 one-to-many |
| **架构绑定** | 基于 Fermi 架构评估（2010 年），利用 Fermi 特有的 unified register/cache 架构。Volta+ 的 L1/shared memory 架构、async copy 等与 Fermi 有本质差异 | 本工作基于 SM80 (A100) 设计与评估 |

**DSAP [IEEE Access'18]** 也针对 GPU 图 IMA，但仅限 BFS 一种算法，不具备通用性。

### Gap 总结

| Gap | 描述 |
|-----|------|
| **Gap 1** | GPU 上缺少**通用**的 IMA hardware prefetcher——Spare Register 仅支持单层 load-pair，DSAP 仅针对 BFS |
| **Gap 2** | CPU IMA 方案（IMP/DMP/Tyche）未考虑 GPU 微架构约束（海量 warp、小 L1、地址流交织、PC 膨胀） |
| **Gap 3** | 现有所有 GPU prefetcher（含 Spare Register）均未利用 GPU ISA 提供的 IMA 结构性信息（IMAD.WIDE 暴露的 scale/base） |

---

## §1.4 我们的发现与方案

### 核心发现：GPU ISA 提供了 CPU 所不具备的结构性优势

虽然 CPU IMA prefetcher 不能直接迁移到 GPU，但我们发现 GPU 的 SASS ISA 提供了 CPU 所不具备的结构性优势，使得**更简洁且更高效**的 IMA 检测成为可能。**简洁的设计不是缺乏深度，而是 insight 驱动的结果。**

| 优势 | 内容 | CPU 对比 |
|------|------|---------|
| **IMAD.WIDE 显式暴露 IMA 参数** | `IMAD.WIDE Rd, Rindex, Rscale, c[base]` 直接暴露 scale 和 base 为指令操作数 | CPU (x86 `lea`/`mov`) 需要从地址差分反推 shift（IMP 试探 2/3/4/-3），或差分序列匹配（DMP） |
| **Constant memory 提供稳定 base** | 所有 IMA 基地址在 `c[0x0][0x1XX]` 中，整个 kernel launch 不变 | CPU base address 可能被运行时修改 |
| **Per-SM 共享表的 64 倍分摊** | CT/TT 为 per-SM shared，1 个 warp 完成训练 → 64 个 warp 立即受益，训练开销被 64 倍分摊 | CPU per-core 独立训练，复用率 1:1 |
| **(base, scale) 自然归并展开副本** | 30+ 个不同 PC 的 IMAD.WIDE 共享同一 constant operand → 自动归到 1 个 pattern entry | CPU 展开少，PC 膨胀问题不存在 |

**关键论断**：IMAD.WIDE 不是设计上的"简化"，而是 GPU ISA 结构性提供的优势。GPU 编译器**必然**使用 IMAD.WIDE 来完成 `base + index × sizeof(element)` 运算（这是 SASS 中唯一能单指令完成 32×32+64→64 的指令），scale 由 C++ 类型系统在编译期保证，base 由 CUDA kernel 参数 → `.param` → `c[0x0]` 的固定映射链保证。这些都是**结构性保证**，而非经验性观察。

### Contribution 列表

1. **IMA 特征化与分类体系**：建立四类 IMA pattern（Linear Gather → Pointer Chasing）的多层次分类框架，从源码、SASS 指令到微架构三个层次量化图 workload 的 IMA 行为。揭示 IMA 占 L1 miss 51%–84%、L1 miss 导致 warp 交织延迟隐藏机制失效的关键发现。

2. **GPU IMA Hardware Prefetcher 设计**：提出 **GRASP**（GPU Register-chain Aware Sector Prefetcher），基于 IMAD.WIDE 检测的 Index-Data Pipeline（index prefetch → data prefetch），利用 GPU ISA 的结构性优势实现零推断 IMA 检测，通过 (base, scale) 归并解决编译器 loop unrolling 导致的 PC 膨胀问题，支持 one-to-many 的多目标预取。据我们所知，这是首个利用 GPU ISA 结构性特征（IMAD.WIDE 操作数直接提取）实现 IMA 检测的硬件 prefetcher，也是首个在现代 GPU 架构（SM80, A100）上设计与评估的通用 IMA prefetcher。

3. **全面评估**：在 Accel-Sim/GPGPU-Sim 上对 5 类图算法（BFS/SSSP/BC/CC/SpMV）进行评估，展示平均 X% IPC 提升（达到 ideal L1D 天花板的 Y%），硬件开销 ~Z KB/SM。

---

## §1.5 论证链条总览

```
GPU 的高吞吐并行建立在 warp 交替隐藏延迟的前提上
    ↓  前提：N × C ≥ L_eff，要求访存规则、L1 hit rate 高
    ↓
图算法的 IMA 从三个维度同时打破这个前提
    ├─ L1 miss rate 70-77% → L_eff 从 50 飙升到 160 cycles
    ├─ index→data 串行依赖链 → L_chain = 400 cycles
    └─ 循环体计算极少 → C ≈ 3 cycles
    ↓
N_required = 133 >> N_max = 64 → 延迟物理不可隐藏
    ↓
Ideal L1D 验证：消除 L1 miss 可获 1.75×-3.04× 加速
    ↓
传统 GPU stride/stream prefetcher 显式排除 IMA
CPU IMA prefetcher 三大障碍无法迁移
Spare Register [HPCA'14] 技术局限（tag-based / 单层 / Fermi）
    ↓
**BUT**: GPU ISA 提供结构性优势（IMAD.WIDE 零推断暴露）
    ↓  + per-SM 共享表使训练开销被 64 倍分摊
    ↓  这些 insight 使得更简洁高效的设计成为可能
    ↓  简洁不是缺陷，而是 insight 驱动的结果
    ↓
本工作：利用这些优势，设计 GRASP — 通用 GPU IMA prefetcher
    ↓
Contribution: 特征化 + 设计 + 评估
```

---

## §1.6 可用的 Related Work 定位句

> 用于 Introduction 中简要提及已有工作的不足

- "Prior GPU prefetchers (CAPS [IPDPS'18], WASP [TC'18], Snake [MICRO'23]) target stride-based patterns and explicitly exclude or cannot handle indirect memory access."
- "CPU IMA prefetchers (IMP [MICRO'15], DMP [HPCA'24]) assume single-threaded address streams and modest hardware budgets, neither of which holds on GPUs with 64 concurrent warps per SM."
- "The only prior GPU work directly addressing IMA — Spare Register [HPCA'14] — employs a tag-based detection mechanism borrowed from CPU thinking, supports only single-level load-pairs, and was designed for the Fermi architecture (2010), which differs fundamentally from modern GPUs in L1/shared memory organization and thread scheduling."
- "We observe that GPU's IMAD.WIDE instruction structurally exposes the scale and base of indirect address computations as instruction operands — information that CPU prefetchers (IMP, DMP) must infer through costly address differential matching, and that Spare Register's tag propagation detects only after three loop iterations."
- "Our design's simplicity is not a limitation but a direct consequence of exploiting this ISA-level structural advantage — a key insight that prior work has not recognized."

---

## §1.7 图算法重要性的论证素材

> 避免泛泛罗列应用领域，提供量化或结构性论据

### 结构性论据

图计算是一类**不可替代**的计算范式——社交网络分析、推荐系统、知识图谱、生物信息学、电路设计中的核心操作本质上都是图遍历。与规则计算（GEMM、stencil）不同，图计算的**不规则性是问题本身的固有属性**，无法通过数据重排或算法替换消除。

### 量化论据（可选引用）

- GPU 图计算框架（Gunrock [PPoPP'16, TOPC'17]、nvGraph、cuGraph）在学术界和工业界被广泛采用
- Gardenia [IISWC'19] 提供了标准化的 GPU 图算法基准集
- Pannotia [IISWC'12] 的 quantitative study 表明 GPU 上 irregular applications 的 L1 miss rate 系统性高于 regular applications

### 与 GPU 发展趋势的关系

GPU 正从专用图形/HPC 加速器演变为通用计算平台。要实现这一愿景，GPU 必须能高效处理**所有**类型的计算负载——包括以 IMA 为核心的图计算。IMA prefetcher 不仅解决图算法的性能问题，更是补齐 GPU 通用计算能力的关键一步。
