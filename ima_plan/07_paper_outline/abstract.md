# Abstract

> 最近更新: 2026-04-03
> 结构：思路 C（与 Introduction 钳形结构对称），S1-S6 六段式

---

## Draft v2 (English, ~170 words)

> 参考 DMP (HPCA'24), Snake (MICRO'23), Magellan (ISCA'25) 的 Abstract 风格：
> 问题简述 → Gap 精炼 → "We propose" 融合 insight → 结果。不堆数据，不加首创性声明。

Indirect memory access (IMA), where one load's address depends on another load's returned data (e.g., A[B[i]]), is a major performance bottleneck for graph analytics and sparse linear algebra on GPUs, causing the majority of L1 cache misses. While CPU architects have developed effective IMA prefetchers, their single-threaded assumptions prevent adoption on massively multithreaded GPUs. Meanwhile, existing GPU prefetchers rely on stride-based patterns and cannot handle data-dependent accesses.

We propose GRASP (GPU Register-chain Aware Sector Prefetcher), a hardware prefetcher that exploits a structural property of GPU's SASS ISA: the IMAD.WIDE instruction directly exposes IMA parameters—scale, base address, and index value—as instruction operands, enabling zero-inference detection. GRASP identifies LDG→IMAD.WIDE→LDG dependency chains at the issue stage and employs a two-step index-then-data prefetch pipeline, with per-SM shared tables for training amortization and (base, scale) key merging to handle compiler-induced PC proliferation.

Evaluated on six graph algorithms across multiple real-world datasets with an A100 configuration in Accel-Sim, GRASP achieves a geomean IPC improvement of [TBD]% (up to [TBD]%), at a hardware cost of approximately 2.5 KB per SM.

> **[TBD 注]**: 评估范围已扩展为 6 算法 (BFS/SSSP/BC/CC/SpMV/VC) × 4+ 数据集 (cit-Patents/web-Google/flickr/roadNet-CA/soc-LiveJournal1 + 待扩充)。
> 最终 geomean 和 up-to 数据需在全量实验完成后更新。当前 ima_med 子集 geomean = 35.5%。

---

## S1–S6 与 Introduction 的对应关系

| Abstract | Introduction | 内容 |
|----------|-------------|------|
| S1 Problem | P1 + P3 | IMA 问题 + GPU 严重性数据 |
| S2 Gap | P2 + P4 压缩 | CPU 无法迁移 + GPU 回避 IMA |
| S3 Insight | P5 核心发现 | IMAD.WIDE 结构性暴露 |
| S4 Approach | P5 方法 | GRASP 两步 pipeline |
| S5 Results | P5 结果 | geomean +[TBD]%, up to +[TBD]% (6 算法 × 4+ 数据集) |
| S6 Significance | P5 Contribution | 首创性声明 |

## 硬件开销估算（~2.5 KB / SM）

| 组件 | 条目数 | 硬件每条目 | 小计 |
|------|:------:|:---------:|-----:|
| CT (Chain Table) | 32 | ~16 B | 512 B |
| TT (Target Table) | 8 | ~8 B | 64 B |
| IST (Stride Tracker) | 64 | ~16 B | 1024 B |
| CD (Detector FIFO) | 20 | ~16 B | 320 B |
| PRB (Request Buffer) | 32 | ~8 B | 256 B |
| Misc | — | — | ~100 B |
| **Total** | | | **~2.3 KB** |

对比：IMP 0.9 KB/core, DMP 0.9 KB/core, Tyche 0.57 KB/core。GRASP 2.5 KB/SM 被 64 warp 共享，等效 per-warp ~39 B。
