# RB-04: CPU IMA Prefetcher 迁移 GPU 的代价分析

> 创建: 2026-04-05
> 最近更新: 2026-04-05

## 核心想法

现有 CPU IMA 硬件 prefetcher（IMP, DMP, Tyche）的检测机制隐含**单上下文、单指令流**假设，无法直接迁移到 GPU 的多 warp 执行环境。强行迁移导致**检测机制在结构上失效**，且 per-warp 复制带来**存储面积膨胀**。

## 要素

### 1. CPU IMA Prefetcher 的单上下文假设

三个代表性 CPU IMA 硬件 prefetcher 及其核心检测结构：

| Prefetcher | 会议 | 总存储 | 核心检测机制 |
|-----------|------|:---:|----------|
| IMP [Yu'15] | MICRO | 0.7 KB | Snoop L1 access/miss stream → IPD 匹配 (shift, BaseAddr) |
| DMP [Fu'24] | HPCA | 0.9 KB | Snoop per-PC 地址差分序列 → differential matching |
| Tyche [Xue'24] | TACO | 0.57 KB | Front-end 寄存器依赖传播 → DCT 记录指令链 |

**共同假设**：一个检测单元对应**一个执行上下文**（一个 CPU 核心/线程），观察的是**单一、连续**的指令流和访存流。

### 2. GPU 为什么打破这个假设

一个 A100 SM 同时执行 **64 个 warp**（2048 个线程），它们**共享同一个 L1 cache** 和**同一条指令发射管线**。

#### 2.1 PC 流交织

CPU：`PC₁ → PC₂ → PC₃`（同一线程，连续可相关）

GPU warp 调度器交替发射不同 warp 的指令：

```
Cycle 1: Warp  0, PC=0x100 (LDG index)     ← B[i₀]
Cycle 2: Warp  5, PC=0x200 (unrelated)
Cycle 3: Warp 12, PC=0x100 (LDG index)     ← B[i₁₂]
Cycle 4: Warp  0, PC=0x110 (IMAD.WIDE)     ← depends on Cycle 1
Cycle 5: Warp  5, PC=0x100 (LDG index)     ← B[i₅]
```

→ IMP 的 IPD 看到的"连续 index stream"实际上来自不同 warp、不同图顶点的交织。

→ DMP 的 differential matching 计算的差分序列是跨 warp 的伪序列：`B[i₀], B[i₁₂], B[i₅], ...` 的差分没有规律。

#### 2.2 不同 warp 处理不同数据

即使 64 个 warp 执行**同一个 kernel 的同一个 PC**，它们访问的是图的**不同顶点**，index load 返回的值完全不同：

$$\text{Warp } w \text{ at PC } p: \quad B[i_w] \neq B[i_{w'}] \quad (w \neq w')$$

因此，IMP 的 (PC, loaded\_value) → predicted\_address 映射本质上是 **per-warp** 的，无法跨 warp 共享。

#### 2.3 结论：不能共享，必须复制

| CPU 假设 | GPU 现实 | 后果 |
|---------|--------|------|
| 单 PC 流，连续可相关 | 64 warp 交织 → PC 流混杂 | 需 per-warp demux + 独立检测状态 |
| 单地址流，delta 有意义 | 不同 warp 访问不同图顶点 | delta 跨 warp 无意义 → 必须 per-warp 跟踪 |
| 一套 table 够用 | 同一 PC、不同 loaded\_value | 映射不能共享 → 必须 per-warp 复制 |

### 3. 存储面积推导

对于 $N_w = 64$（A100 SM 最大并发 warp 数）：

$$S_{GPU/SM} = S_{CPU} \times N_w$$

| | CPU 原始 | GPU Per-Warp (×64) | 占 L1 Cache (192 KB) |
|---|:---:|:---:|:---:|
| IMP | 0.7 KB | **44.8 KB** | 23.3% |
| DMP | 0.9 KB | **57.6 KB** | 30.0% |
| Tyche | 0.57 KB | **36.5 KB** | 19.0% |

全 GPU（108 SM）总存储：

$$S_{GPU} = S_{GPU/SM} \times N_{SM} = S_{CPU} \times N_w \times N_{SM}$$

| | Per SM | 全 GPU (×108 SM) |
|---|:---:|:---:|
| IMP | 44.8 KB | **4.7 MB** |
| DMP | 57.6 KB | **6.1 MB** |
| Tyche | 36.5 KB | **3.9 MB** |

> 参考：A100 L2 Cache 总容量 = 40 MB。DMP 全 GPU 存储 = L2 的 15%。

### 4. 总结

CPU IMA prefetcher 迁移 GPU 面临的不是"能不能放下"的问题，而是三层递进的结构性障碍：

1. **检测失效**：多 warp PC/地址流交织 → 相关性分析基础被破坏
2. **存储膨胀**：per-warp 复制 → 20-30% L1 cache 面积预算

→ 需要一种从 GPU 执行模型出发的新检测方法，而非 CPU 方案的简单移植。

## 候选位置

| 论文章节 | 使用方式 |
|---------|---------|
| **§2.3 Motivation**（主选） | 完整推导，引出"为什么不能用 CPU 方案" |
| **§6 Related Work**（辅选） | 简要引用结论，解释与 IMP/DMP/Tyche 的根本区别 |

## 数据来源

| 数据 | 来源论文 | 位置 |
|------|--------|------|
| IMP 0.7 KB, PT 16 entries, IPD 4 entries | Yu et al., MICRO 2015 | Table 2 (IMP Configuration) |
| DMP 0.9 KB (912 bytes), TABLE I 详细分解 | Fu et al., HPCA 2024 | TABLE I (Storage Overhead of DMP) |
| DMP 0.018mm², 17mW (28nm TSMC) | 同上 | §IV.B (Implementation) |
| Tyche 0.57 KB, PT per-register | Xue et al., TACO 2024 | §4 (Our Design), Abstract |
| DMP TABLE III 列出 IMP=0.7KB 对照 | Fu et al. | TABLE III |
| A100 SM: 64 warps, 108 SMs, L1=192KB, L2=40MB | NVIDIA A100 Whitepaper | — |

## 依赖与约束

| 项目 | 状态 |
|------|------|
| IMP/DMP/Tyche 论文 PDF | **已有**（`02_related_work/ima_hw/`） |
| 存储参数提取 | **已完成** |
| 无图表（纯公式+表格） | 不需要绘图脚本 |
