# GRASP Paper Structure (Authoritative Outline)

> 最近更新: 2026-04-08
> 目标会议: MICRO 2026 (11 pages body + unlimited references, no appendix)
> 本文件是论文结构的唯一权威定义。写作时以此为准。
>
> ## 使用方式
>
> 每个 §N section 的内容经历两个阶段：
> 1. **[占位符]** — 当前状态，记录要点和图表位置，粒度较粗
> 2. **[已细化]** — 用户提供该 section 的图后，Claude 将占位符细化为段落级大纲，用户 review 确认
>
> `/paper-write §N` **仅在对应 section 标记为 [已细化] 后才可调用**。
> 占位符阶段调用会被拒绝，需先完成大纲细化。

---

## 总体架构

```
§1 Introduction          1.5 pages    14%
§2 Background & Motivation  1.5 pages    14%
§3 GRASP Design          3.5 pages    32%
§4 Methodology           0.5 pages     5%
§5 Evaluation            3.0 pages    27%
§6 Related Work          0.5 pages     5%
§7 Conclusion            0.5 pages     5%
                        ─────────    ────
                        11.0 pages   100%
```

**图表预算**: ~21 figures + 4 tables (密度 ~2.0 fig/page, 与 DMP/Snake 一致)

**核心叙事 (One-Sentence Pitch)**:
GPU ISA 中的 IMAD.WIDE 指令天然暴露了 IMA 的结构参数，GRASP 利用这一零推断特性，以极低硬件开销 (~2.5KB/SM) 实现了 GPU 上首个专用 IMA prefetcher，弥补了 CPU IMA prefetching 与 GPU 之间长期存在的 gap。

---

## §1 Introduction (1.5 pages) `[已细化]`

> 叙事主线: GPU + IMA + Prefetch（对应论文标题三要素）
> 素材来源: `introduction.md`, `introduction_golden_rules.md`, `resource_blocks/`
> 结构: GPU-centric 线性流程, 概念链单向下降（Golden Rules 原则二）
> 设计原则: §1 给结论数字, §2 给推导过程（不重复）
>
> 概念链:
> ```
> IMA pattern（¶1）→ IMA on GPU（¶2）→ GPU Prefetching 盲区（¶3）
>   → CPU 搬不过来 + Spare Register 十年无后续（¶4-5）
>     → GPU IMA Prefetching = open problem（第零上位落地）
>       → IMAD.WIDE 核心发现（¶6）→ GRASP（¶7）→ Contributions（¶8）
> ```

### §1.1 IMA 的广泛性与 GPU 上的严重性 (~0.35 page)

**¶1: IMA 定义 + 广泛性**
- IMA 模式 `A[B[i]]`: 一次 load 的地址依赖另一次 load 的返回值, 打破传统 locality 假设
- 广泛存在于 graph analytics (e.g., social networks, road networks, web graphs), sparse linear algebra, and data-intensive applications（领域级命名 + parenthetical 画面感例子, 每个例子都有评估数据集支撑: flickr/road_usa/web-Google）
- GPU 已成为加速这些 workload 的主力平台
- 不规则性是问题固有属性, 无法通过数据重排消除
- 引用:
  - IMA 模式定义 `A[B[i]]`: \cite{yu2015imp}, \cite{fu2024dmp}
  - IMA 是 irregular workload 瓶颈: \cite{talati2021prodigy}, \cite{xue2024tyche}
  - GPU irregular program 量化: \cite{burtscher2012irregular}（2012 但仍是该领域权威定量研究, 配 \cite{shi2018graph} 等新综述一起引用, 表明结论 14 年后依然成立）
  - GPU 图处理综述: \cite{shi2018graph}
  - GPU 图框架/benchmark: \cite{wang2016gunrock}, \cite{xu2019gardenia}, \cite{beamer2015gap}
  - GPU 图计算 linear algebra: \cite{yang2022graphblast}
  - SpMV 重要性: \cite{bell2009spmv}
  - 工业需求: GraphBIG \cite{nai2015graphbig}
  - GPU graph mining: Pangolin \cite{chen2020pangolin}（Gardenia 推荐引文中选取的高影响力一篇, PVLDB 2020; 其余 workshop 论文如需引用放 §6 Related Work）

**¶2: IMA 打破 GPU latency hiding + Prefetching opportunity**
- GPU 核心设计哲学: 海量 warp 交替执行隐藏内存延迟
- **IMA 打破这一哲学** (只给结论数字, 详细推导移至 §2.3):
  - IMA 占 L1 miss 的 61-93%（per-algo median, sym-only, Fig 1a）
  - IMA 串行依赖链使所需 warp 数远超 A100 物理上限 (§2.3)
- **Prefetching opportunity (RB-03 核心论点)**: L1 miss rate 高 (38-59%) 但 L2 hit rate 也高 (70-89%) → 数据在 L2 不在 L1 → L1 prefetching opportunity exists（per-algo median, sym-only, Fig 1a）
- Ideal L1D: 消除 L1 miss 后 **geomean 2.0× speedup** (25 workload 配置, 范围 1.4×-4.0×)
- 引用: \cite{lee2010manythread}, \cite{burtscher2012irregular}
- **Fig 1**: 双子图 [双栏 7.0”]
  - (a) L1 miss rate (IMA data / IMA index / other stacked) + L2 miss rate 叠加对比
  - (b) Ideal L1D speedup
  - 数据来源: RB-03 (cache_ima_breakdown.csv) + experiment_results.md (全量 sym 变体)

**过渡**: This motivates GPU-specific prefetching for IMA — yet no existing GPU prefetcher addresses this access pattern.

### §1.2 GPU Prefetching: Stride 成功但 IMA 是盲区 (~0.3 page)

**¶3: GPU stride prefetching 15 年进展 (认知桥梁)**
- GPU prefetching 研究超过 15 年, 在 stride/stream 模式上持续进化:
  - Many-Thread \cite{lee2010manythread}: inter-thread prefetching + 自适应节流, avg 16%
  - Orchestrated \cite{jog2013orchestrated}: 调度+预取协同, 25% improvement
  - APRES \cite{oh2016apres}: 负载特征分类 + 预取, 31.7% improvement
  - CAPS \cite{koo2018caps}: CTA 感知 leading-warp 检测, 97% accuracy
  - Snake \cite{mostofi2023snake}: variable-length stride chain, 80% coverage
- 水泥: 这些工作从调度协同到 CTA 感知再到变长 stride 链, 不断拓展 GPU prefetching 的能力边界
- **转折**: 但 IMA 需要根本不同的检测机制 — data load 地址由运行时 index 值决定, 不存在可检测的 stride 规律
  - CAPS 检测到 data-dependent access 时显式跳过 \cite{koo2018caps}
  - Snake 的 chain 仍是 stride chain, 无法处理数据依赖 \cite{mostofi2023snake}
- 批量引用 (建立"15 年"丰富性): \cite{lee2010manythread}, \cite{jog2013orchestrated}, \cite{oh2016apres}, \cite{koo2018caps}, \cite{oh2018wasp}, \cite{mostofi2023snake}
- 可选 parenthetical（篇幅允许时）: "Specialized prefetchers have also been proposed for TLB \cite{yoon2023latpc} and ray-tracing \cite{viitanen2018treelet}, but none addresses data-dependent IMA patterns." — 强化 IMA 盲区论点; 如篇幅紧张则省略

**¶4: CPU 有方案但搬不过来 (压缩为 2-3 句)**
- CPU 社区已有近十年 IMA hardware prefetching 积累, 证明 IMA prefetching 可行且收益显著
  - IMP \cite{yu2015imp}: 地址差分检测 `A[B[i]]`, 56% avg (How + So What)
  - DMP \cite{fu2024dmp} (当前 SOTA): 差分匹配四类间接模式, 1.8× avg, 0.9KB (How + So What)
  - 水泥: subsequent work progressively addressed multi-level and non-linear patterns \cite{cavus2020atp}, \cite{kaushik2021gretch}, \cite{xue2024tyche}, \cite{talati2021prodigy}
- **但**: 这些方案假设单线程地址流 + per-core 独立状态 → GPU 64-warp 并发下检测结构性失效, per-warp 复制高达 57.6 KB/SM (§2.3)
- 引用: \cite{lee2010manythread}, \cite{ainsworth2019indirect}

**¶5: Spare Register — 唯一 GPU IMA 尝试, 十年无后续**
- Lakshminarayana & Kim \cite{lakshminarayana2014spare} 是唯一针对 GPU IMA 的硬件 prefetcher
  - 利用 value tag 检测 load-pair + 空闲寄存器存储预取数据, avg 10% IPC (How + So What)
- 但基于 Fermi 架构 (2010) 设计与评估 — cache hierarchy, warp scheduling 与 SM80+ 有代际差异
- **此后十年, 无新的 GPU IMA 硬件方案** — 后续 GPU prefetcher 全部针对 stride \cite{koo2018caps}, \cite{oh2018wasp}, \cite{mostofi2023snake}
- ~~可选引用 GPU 软件预取~~ → **移至 §6 Related Work**: \cite{deng2024swprefetch} 讨论 GPU 上 SW prefetch, 与 §1 的 HW prefetcher 叙事线不一致 (§1 线: GPU stride HW → CPU IMA HW → Spare Register HW → gap → GRASP HW); 在 §6 中作为 "GPU prefetch 其他路线" 讨论

**过渡 (第零上位落地)**: GPU IMA prefetching thus remains an open problem — one that demands a detection approach native to GPU's execution model.

### §1.3 核心发现与 GRASP (~0.3 page)

> 标题贡献性关键词在此段集中亮相: ISA-Exposed / IMAD.WIDE / Register-Chain / GRASP
> §1.1-§1.2 中这些词均未出现或极少出现

**¶6: IMAD.WIDE — GPU ISA 的结构性优势**
- 尽管 CPU 社区已积累多种 IMA 检测方法, 将它们应用到 GPU 上的代价很高 (¶4 已论证); 然而我们发现 **GPU ISA 本身提供了一条更直接的路径** — 无需迁移 CPU 方案, GPU 有自己的结构性优势
- **核心发现**: `IMAD.WIDE Rd, Rindex, Rscale, c[base]` — 一条指令包含了 IMA data prefetch 所需的**全部信息**:
  - **base address** (数据数组基地址) — constant memory 操作数, 整个 kernel 不变
  - **scale** (元素大小) — 寄存器操作数, 编译期常量
  - **index dependency** (索引值来源) — 源寄存器, 连接前序 LDG
- 一次指令观测即获取全部 prefetch 参数, 无需任何推断
- 结构性保证: GPU 指针 64-bit, 图/稀疏数据 index 通常为 INT32/UINT32 → 地址计算 = index(32) × element_size(32) + base(64) → 需要 32×32+64→64 宽乘加 → IMAD.WIDE 是 SASS ISA 唯一满足此宽度的指令, 编译器必然选择它（§1 简述理由, §2.4 完整展开推理链 + NVIDIA spec 验证）
- ~~覆盖率: 8 算法 56 实现 → 88.4%~~ — 已删除, 数据来源不稳定（原则九: 半定量审查）
- 跨架构稳定 (主要覆盖率论据): 12 算法 × 6 代 GPU (Volta→Hopper), 9/12 算法一致率 ≥ 86% (RB-02 结论, 受控实验, 数据可靠)
- 与已有方案对比:

| 方案 | 检测方式 | 检测延迟 | 信息来源 |
|------|---------|---------|---------|
| IMP \cite{yu2015imp} | 地址差分 + shift 试探 | 需积累地址序列 | 黑盒推断 |
| DMP \cite{fu2024dmp} | 差分序列比例匹配 | 需积累差分序列 | 黑盒推断 |
| Spare Register \cite{lakshminarayana2014spare} | value tag 传播 | 3 次循环迭代 | 黑盒推断 |
| **GRASP** | **IMAD.WIDE 操作数** | **1 次指令观测** | **ISA 白盒** |

**¶7: 方案概述 + 附带优势**
- GRASP (GPU Register-chain Aware Sector Prefetcher):
  - Issue-stage 检测 `LDG→IMAD.WIDE→LDG` 寄存器依赖链
  - 两步 index-then-data prefetch pipeline
- 附带结构性优势 (IMAD.WIDE 的自然产物):
  - (base, scale) 归并: SpMV 60+ PC → ~2 entries, 解决 PC 膨胀
  - Per-SM 共享表: 64 倍训练分摊, 硬件仅 ~2.3 KB/SM
- 选取结果 (只填前文 gap): geomean 18% IPC improvement (up to 122%), 28 workloads, 6 algorithms × 5 datasets（数据来源: D5b throttle_control_results.md + extra_case_results.csv）

### §1.4 Contributions (~0.1 page)

1. **IMA Characterization and IMAD.WIDE Discovery**: 首次系统量化现代 GPU 上 IMA 行为 (占 L1 miss 61-93%, Ideal headroom geomean 2.0×); 发现 IMAD.WIDE 指令结构性地包含 IMA data prefetch 所需的全部参数 (base, scale, index dependency), 跨 6 代 GPU 架构 (Volta→Hopper) 9/12 算法一致率 ≥ 86%
2. **GRASP Design**: 基于 IMAD.WIDE 的零推断检测 + index-data two-step pipeline + (base,scale) 归并 + per-SM 共享表, 以 ~2.3KB/SM 实现面向现代 GPU 的通用 IMA prefetcher
3. **Comprehensive Evaluation**: 9 算法 × 5 数据集 (28 workloads) × 3 SOTA baseline (Snake, CAPS, Spare Register), geomean 18% IPC improvement (up to 122%), 23/28 workloads positive

### §1 逻辑闭环验证

| §1.1-§1.2 挖的坑 | §1.3 回应 | 状态 |
|---|---|---|
| IMA 占 L1 miss 61-93%, 性能损失巨大 | GRASP 的 IMA coverage + speedup | ✓ |
| L1 miss 高但 L2 hit 高 → prefetching opportunity | GRASP 做 L2→L1 prefetch | ✓ |
| Ideal L1D geomean 2.0× | GRASP 达到天花板的 Y% | ✓ 待数据 |
| GPU stride prefetcher 排除 IMA | GRASP 专门针对 IMA | ✓ |
| CPU 方案不能迁移 (57.6 KB/SM) | ISA 白盒检测 / per-SM 共享 ~2.3KB | ✓ |
| Spare Register: Fermi + 单层 + 3 次迭代 | SM80/A100 + one-to-many + 1 次观测 | ✓ |
| 十年无 GPU IMA 新方案 | GRASP 填补空白 | ✓ |

### §1 资源块分配

| 资源块 | §1 用法 (结论) | §2+ 用法 (推导/详细) |
|---|---|---|
| RB-01 (Warp Gap) | ¶2: “所需 warp 数远超物理上限” 一句 | §2.3: Little's Law + 图 |
| RB-02 (Chain Stability) | ¶6: “12×6 跨架构, 9/12 ≥ 86%” 一句 | §3: 完整数据表 + 图 |
| RB-03 (Cache/IMA) | ¶2 + Fig 1(a): L1/L2 gap + IMA 分解 | §2.3: 37 组合详细分析 |
| RB-04 (CPU Migration) | ¶4: “57.6 KB/SM” 结论一句 | §2.3: 完整推导 |
| RB-05 (Spare Register) | ¶5: 事实陈述 + 十年 void | §6: 详细机制对比 |

---

## §2 Background & Motivation (~2 pages) `[已完成 v2 — 2026-04-07]`

> 目标: 建立 GPU + IMA 心智模型 → 量化 latency crisis → 论证现有方案无解 → 落地 IMAD.WIDE Insight。**§3 Key Insight 整章已下沉为 §2.5**，原 §3 整章移除，后续 sections 全部降级 1 位（原 §4 GRASP Design → §3 等）。
> 对应 Insight: #1(零推断检测), #2(L1/L2不对称), #3(IMA占L1miss主体), #7(覆盖率), #9(Ideal天花板)
> 状态: Fig 2 (GPU.pdf) ✓ Fig 3 (csr_spmv.pdf) ✓ Fig 4 (warp_gap.pdf) ✓ Fig 5 (IMA_chain.pdf) ✓ Table 1 (CPU 迁移代价) ✓
>
> **5-subsection 三幕叙事结构（locked v2，按 Snake 节奏）**:
>
> | Subsection | Act | 内容要点 | 视觉资产 |
> |---|---|---|---|
> | §2.1 GPU Memory Hierarchy | Setup | 严格按 Fig 2 白名单描述（无 64w/192KB 等数字，留到 §2.3/§2.4） | Fig 2 |
> | §2.2 The Indirect Memory Access Pattern | Setup | CSR + SpMV running example + 概念三步硬件执行（**无 SASS 代码**，SASS 留到 §2.5） | Fig 3 |
> | §2.3 IMA Breaks Warp Latency Hiding | Obstacle A | Little's Law 推导 + Fig 4 (warp gap, 6 Gardenia 全部 ≥2.5×) + 引用 Fig 1 (L1 miss + L2 hit) → 末句 "need a prefetcher" | Fig 4 + Eq 1 + Fig 1 引用 |
> | §2.4 Why Existing Prefetchers Fall Short | Obstacle B | CPU 检测塌陷 + Table 1 per-warp 复制爆 19-30% L1 + Spare Register Fermi 假设过时 → 末句 "yet none has examined the SASS ISA itself" | Table 1 |
> | §2.5 The IMAD.WIDE Insight | Opening | IMAD.WIDE 结构性论证 + Fig 5 (chain + operand 分解) + 跨架构稳定性 (5/6 Gardenia ≥86%, BC 78%) + zero-inference 论证 → 钩 §3 Design | Fig 5 |
>
> **数字搬家**: 64 warps/SM 在 §2.3 ¶3 首次引入；192 KB L1 在 §2.4 ¶3 首次引入；都引用 `nvidia2020a100`。Fermi 16 KB / 128 B line 在 §2.4 ¶4 出现。

### §2.1 GPU 执行模型与内存层次 (~0.3 page)

**内容**:
- SM / Warp / SIMT 执行模型 (简要, 仅 prefetcher 设计需要的部分)
- L1 Data Cache / Shared Memory / L2 / HBM 层次
- MSHR (Miss Status Holding Register) 机制: 每个 miss 占用 MSHR entry 直到数据返回
- Prefetch request 如何通过 MSHR 发出 + reservation fail (RFAIL) 概念
- **Fig 2**: GPU SM 架构简图 [单栏 3.5"]
  - 标注 L1 cache, MSHR, warp scheduler
  - 灰色虚线框标注 GRASP 组件将插入的位置 (CD 在 issue stage, CT/TT/IST 在 L1 旁)
  - 参考风格: Snake Fig 2

### §2.2 IMA 模式的特征化 (~0.5 page)

> 对应 Insight #8 (四类 Pattern), #4 (PC 膨胀), #5 (one-to-many)

**内容**:
- `A[B[i]]` 模式定义: 源码 → SASS → 微架构三层分解
  - 源码: `data[index[i]]`
  - SASS: `LDG (index) → IMAD.WIDE → LDG (data)` 依赖链
  - 微架构: index miss → stall → data miss → stall (串行)
- IMA Pattern 分类 (按 **GPU 上的 prefetchability** 维度, 非照搬 DMP 的 single/ranged/multi-level/multi-way):
  - I: Linear Gather (SpMV) — index stride-1 顺序遍历, data 地址随机 scatter
  - II: Frontier-Driven (BFS/SSSP/BC) — 外层由 worklist 驱动 (不可预测), 内层同 I (stride 遍历邻居)
  - III: Data-Dependent (CC hook) — 第一层 index 可 stride 预测, 但第二层 data 地址依赖第一层 data 值
  - IV: Pointer Chasing (CC shortcut) — 纯数据依赖链, 每一步都依赖前一步返回值
  - 来源: `01_ima_characterization.md` (Insight #8), 分类依据是 index 流的可预测性 + data 地址的可计算时机
  - 与 DMP 四类的关系: DMP 从 CPU 视角按 indirection 结构分 (single/ranged/multi-level/multi-way); 我们从 GPU prefetcher 视角按 prefetchability 分, 维度不同
- **Fig 3**: 四类 IMA Pattern 示例 [双栏 7.0"]
  - 4 子图: 每个 pattern 的代码片段 + 内存访问示意图
  - 参考风格: DMP Fig 3 (4 种 indirection type 的并列展示)
  - 数据来源: `01_ima_characterization.md`
- **Table 1**: IMA Pattern Prefetchability 层级

| Pattern | 代表算法 | Index 可预取 | Data 可预取 | GRASP 覆盖 |
|---------|---------|:----------:|:----------:|:----------:|
| I: Linear Gather | SpMV | Yes (stride) | Yes (index→data) | Full |
| II: Frontier-Driven | BFS/SSSP/BC | Yes (stride) | Yes (index→data) | Full |
| III: Data-Dependent | CC hook | Yes (stride) | Partial (1st layer) | Partial |
| IV: Pointer Chasing | CC shortcut | No | No | No |

### §2.3 定量动机: 为什么需要 IMA Prefetcher (~0.5 page)

> 对应 Insight #2, #3, #9

**内容**:
- **Little's Law 推导** (从 introduction.md §Appendix 移入):
  - Warp latency hiding 条件: N × C >= L_eff
  - 规则负载: L_eff ≈ 50 cycles, C 大 → 条件满足
  - IMA 负载: L1 miss 70-77% → L_eff ≈ 160 cycles; 串行依赖 → L_chain = 400 cycles; C ≈ 3 → N_required = 133 >> N_max = 64
  - 52% 延迟无法被隐藏
- **L1/L2 不对称** (Insight #2):
  - L1 miss 70-77%, 但 L2 miss 仅 22-34%
  - A100 的 40MB L2 能容纳 IMA 目标数组工作集
  - → Prefetch 聚焦 L2→L1 搬运 (延迟预算 ~200 cycles, 非 DRAM ~500 cycles)
- **Fig 4**: L1 miss rate + L2 hit rate [单栏 3.5"]
  - 分组 bar chart, 5 workloads × 2 metrics
  - 参考风格: Snake Fig 3-5 合并
  - 数据来源: `03_performance_ceiling.md`, `01_ima_characterization.md`

### §2.4 IMAD.WIDE: GPU ISA 的结构性优势 (~0.2 page)

> 对应 Insight #1 (零推断检测), #7 (覆盖率)
> 这里完整展开, §1.4 只用结论

**内容**:
- IMAD.WIDE 指令格式: `IMAD.WIDE Rd, Rindex, Rscale, c[0x0][0x1XX]`
  - Rd: 64-bit 输出地址
  - Rindex: 前序 LDG 返回的 index 值
  - Rscale: sizeof(element), 编译期常量
  - c[0x0][...]: kernel 参数 base pointer, constant memory
- 为什么是结构性保证: IMAD.WIDE 是 SASS 唯一的 32×32+64→64 指令, 编译器必然选择
- 覆盖率: 8 算法 56 实现 → 88.4% (排除 SCC 后 93.6%)
- 与 CPU 黑盒推断的本质差异 (1 句, 引用 §1.4 对比表)
- **Fig 5**: LDG→IMAD.WIDE→LDG 依赖链示例 [单栏 3.5"]
  - BFS 主 kernel 的 SASS 代码片段 (5-7 行)
  - 寄存器依赖箭头 (R_idx → IMAD.WIDE → R_addr → LDG)
  - 参考风格: Snake Fig 7-8 (代码 + stride 图组合)
  - 数据来源: `01_ima_characterization/sass_analysis/`

---

## §3 GRASP Design (3.5 pages) `[占位符]`

> 渐进式展开: Overview → 各组件 → Pipeline 时序 → Hardware Cost → Worked Example
> 参考结构: Snake §3 (Detection → Prefetching → Throttling → Example)
> 对应 Insight: #1(检测), #4(PC归并), #5(one-to-many), #6(64倍分摊), #10(写无效化)
> 源码参考: `grasp_prefetcher.{h,cc}`, `grasp_chain_detector.{h,cc}`, `grasp_tables.{h,cc}`
> **细化条件**: 需提供 Fig 6(架构框图), Fig 7(CD流程), Fig 8(CT/TT示例), Fig 9(Pipeline时序), Fig 10(Worked Example)

### §3.1 Overview (~0.3 page)

**内容**:
- GRASP 核心思路: 在 issue stage 检测 IMA 依赖链 → 两步 prefetch (index → data)
- 六大组件:
  - **CD** (Chain Detector): 检测 LDG→IMAD.WIDE→LDG
  - **CT** (Chain Table): (base, scale) 索引, PC-agnostic
  - **TT** (Target Table): 存储 data PC + offset (支持 one-to-many)
  - **IST** (Iteration Stride Tracker): per-PC stride 学习
  - **IPU/DPU** (Index/Data Prefetch Unit): 发出 prefetch request
  - **PRB** (Prefetch Request Buffer) + **TC** (Throttle Controller)
- 数据流: issue → CD 检测 → CT/TT 注册 → IST 学 stride → IPU 发 index pf → index 值返回 → DPU 算 data addr → data pf
- **Fig 6**: GRASP 整体架构框图 [双栏 7.0"]
  - Per-SM 视角, 标注所有组件和数据流方向
  - 区分 training path (实线) 和 prefetch path (虚线)
  - 参考风格: DMP Fig 10 (hardware overview) / Snake Fig 14 (major components)

### §3.2 Chain Detector (CD) (~0.5 page)

> 源码: `grasp_chain_detector.{h,cc}`, `on_issue()`, `check_chain()`

**内容**:
- **检测位置**: Instruction issue stage (不等待 load 返回)
- **检测模式**: LDG → IMAD.WIDE → LDG 的寄存器依赖链
  - Step 1: 看到 LDG 写 Rd → 将 (PC, Rd) 存入 FIFO
  - Step 2: 看到 IMAD.WIDE 读 Rindex → 在 FIFO 中查找 Rd == Rindex
  - Step 3: 看到 LDG 读 IMAD.WIDE 的 Rd → chain 确认
- **FIFO 设计**: per-SM 共享 (非 per-warp), 20 entries, 节省硬件
  - tracked warp 机制: 同时只追踪有限数量的 warp
  - FIFO invalidation: 非追踪指令覆写 Rd 时清除旧 entry (Insight #10, 保证正确性)
  - m_count 回收: push 时扫描 invalid slot 复用
- **Fig 7**: CD 检测流程图 [单栏 3.5"]
  - Flowchart: 指令进入 → 操作码判断 → FIFO 操作 → chain 确认/reject
  - 参考风格: Snake Fig 12 (detection step flowchart)

### §3.3 Chain Table (CT) & Target Table (TT) (~0.5 page)

> 源码: `grasp_tables.{h,cc}`
> 对应 Insight #4 (PC归并), #5 (one-to-many)

**内容**:
- **CT (Chain Table)**: 存储已检测到的 IMA chain
  - Key: **(data_base, scale)** → PC-agnostic, 自动归并 loop unrolling 膨胀的多个 PC
    - SpMV 60+ PC → ~2 CT entries (所有展开副本共享同一 constant operand)
  - Value: index PC, data PC list, confidence counter
  - 32 entries, LRU 淘汰
  - Kernel reset: 新 kernel 启动时清除过时 entries (用 kernel name 比较, 非指针)
  - 跨 kernel 持久化: same kernel 重复 launch 时保留
- **TT (Target Table)**: 存储 chain 的 data 目标
  - 支持 **one-to-many**: 1 个 index → K 个 data target (K=3 for BC reverse)
  - 8 entries
- **Fig 8**: CT/TT 查找过程示例 [单栏 3.5"]
  - 展示: IMAD.WIDE 操作数 → 提取 (base, scale) → CT lookup → match → 获取 data PC 集合
  - 用 BFS 的实际 constant operand 值作例子
  - 参考风格: IMP Fig 4-5 (table lookup illustration)

### §3.4 Iteration Stride Tracker (IST) (~0.4 page)

> 源码: `grasp_tables.cc` `update_stride()`
> 对应 Insight #11 (stride 学习跨 CTA 污染修复, from INDEX.md)

**内容**:
- **Per-PC stride 学习**: 记录同一 PC 的连续两次执行地址 → 计算差值 → stride
  - 使用 tracked warp: 只追踪一个 warp 的地址序列, 避免多 warp 交织
  - Confidence counter: stride 连续匹配 N 次后 freeze
- **Stride freeze + warp exit cleanup**: 解决跨 CTA 污染
  - 问题: 旧 CTA 的 warp 退出后, 新 CTA 的 warp 地址不连续, IST 学到错误 stride
  - 解决: warp exit 时 cleanup tracked state; stride freeze 后不再更新
  - 效果: PT hit rate 29% → 60%, accuracy +3pp
- 64 entries (per-SM)

### §3.5 Index & Data Prefetch Units (IPU/DPU) (~0.4 page)

**内容**:
- **IPU (Index Prefetch Unit)**:
  - 触发条件: IST 中对应 PC 的 stride 已学到 + confidence 达阈值
  - 地址计算: next_index_addr = current_index_addr + stride × distance
  - 发出 L2→L1 prefetch request
  - distance=4 (distance=1 已证明无效, 见 INDEX.md E1)
- **DPU (Data Prefetch Unit)**:
  - 触发条件: index prefetch 命中 L1 (或 demand hit) → 获得 index 值
  - 地址计算: data_addr = base + index_value × scale (从 CT/TT 获取 base, scale)
  - 对 one-to-many chain, 为每个 target 分别计算 data_addr 并发出 prefetch
  - 关键: **两步 pipeline 的核心价值** — index prefetch 节省 ~200 cycles, data prefetch 再节省 ~200 cycles, 总共 ~400 cycles latency hiding
- **Fig 9**: Index-Data Pipeline 时序图 [双栏 7.0"]
  - 展示 1 个 warp 的完整 prefetch 过程 (时间轴从左到右):
    ```
    demand index miss → [~200cy] → index value ready
                                     ↓
    stride predict → index pf ─────→ index pf hit (L1)
                                     ↓
                      compute data addr → data pf ─────→ data pf hit (L1)
                                                          ↓
    demand data hit (L1) ← ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
    ```
  - 对比 no-prefetch 的 demand 路径 (~400cy) vs GRASP 的 prefetch 路径 (overlap)
  - 参考风格: Snake Fig 15 (training/prefetching example)

### §3.6 Prefetch Request Buffer (PRB) & Throttle Controller (TC) (~0.3 page)

**内容**:
- **PRB**: 缓冲 prefetch request, 避免与 demand request 争抢 MSHR
  - 32 entries
  - 优先级: demand > prefetch (prefetch 在 MSHR 有空时才发出)
- **TC (Throttle Controller)** — Cooldown Timer (tc_mode=4, T40C200):
  - MSHR 占用率超过 40% 时触发, 暂停 DATA_PF 发射 200 cycles (INDEX_PF 始终豁免)
  - Cooldown 期间 cache 有时间排空无效预取, 缓解 pollution
  - 效果: SpMV +3.47%, BFS/SSSP +0.37%, 0/9 workload 退化; useless PFs 减少 25-61%
  - 设计依据: `05_implementation/dse_throttle_control/README.md` §7
- **RFAIL 处理**: prefetch request 被 MSHR 拒绝 → 丢弃 (不重试, 避免活锁)

### §3.7 Hardware Cost Analysis (~0.2 page)

**Table 2**: GRASP 硬件开销明细

| 组件 | Entries | Per-Entry | Total | 功能 |
|------|:-------:|:---------:|------:|------|
| CD FIFO | 20 | ~16 B | 320 B | 寄存器依赖追踪 |
| CT (Chain Table) | 32 | ~16 B | 512 B | IMA chain 索引 |
| TT (Target Table) | 8 | ~8 B | 64 B | Data target 映射 |
| IST (Stride Tracker) | 64 | ~16 B | 1024 B | Per-PC stride |
| PRB (Request Buffer) | 32 | ~8 B | 256 B | Prefetch 缓冲 |
| Misc (TC, counters) | — | — | ~100 B | 控制逻辑 |
| **Total** | | | **~2.3 KB/SM** | |

**Per-warp 等效**: 2.3KB / 64 warps ≈ **36 B/warp** (vs IMP 0.9KB/core, DMP 0.9KB/core — CPU 方案是 per-core 独占)

**面积**: 占 L1 cache 的 ~X% [TBD: 需估算]

### §3.8 Worked Example (~0.4 page)

**Fig 10**: 端到端 BFS 示例 [双栏 7.0"]
- 展示 BFS 的一个 iteration 中 GRASP 的完整工作流:
  1. Warp 0 执行 LDG (index load) → CD 记录 (PC_idx, R5) 到 FIFO
  2. Warp 0 执行 IMAD.WIDE → CD 匹配 R5, 提取 (base, scale=4)
  3. Warp 0 执行 LDG (data load) → CD 确认 chain, 写入 CT
  4. IST 在 warp 0 第二次执行 PC_idx 时学到 stride=16
  5. Warp 1 执行 PC_idx → IST 预测 next_addr → IPU 发出 index prefetch
  6. Index prefetch 命中 L1 → DPU 读 index 值, 计算 data addr → 发出 data prefetch
  7. Warp 1 的 demand data load → L1 hit (prefetch 数据已到达)
- 参考风格: DMP Fig 4 (BFS algorithm + indirection pair example)

---

## §4 Methodology (0.5 pages) `[已细化]`

> **状态**: 2026-04-08 已写入 main.tex line 1106-1180（plan: `.claude_global/plans/replicated-chasing-pizza.md`）。4 个 block (Simulation / Benchmarks / Comparison Points / Metrics) 句子级填充完成，编译验证通过。

### §4.1 仿真框架

- Accel-Sim / GPGPU-Sim (trace-driven mode)
- GPU 配置: SM80_A100 (108 SMs, 64 warps/SM, 128KB L1D, 40MB L2)
- 配置文件: `gpu-simulator/gpgpu-sim/configs/tested-cfgs/SM80_A100/`

### §4.2 Benchmarks & Datasets

**Table 3**: 评估矩阵 [TBD: 最终范围]

| 算法 | Suite | 说明 |
|------|-------|------|
| BFS | Gardenia | Breadth-First Search |
| SSSP | Gardenia | Single-Source Shortest Path |
| BC | Gardenia | Betweenness Centrality |
| CC | Gardenia | Connected Components |
| SpMV | Gardenia | Sparse Matrix-Vector Multiply |
| VC | Gardenia | Vertex Coloring |
| [TBD] | [TBD] | 可能增加的其他算法 |

| 数据集 | 顶点数 | 边数 | 类型 |
|--------|-------|------|------|
| cit-Patents | 3.8M | 16.5M | citation |
| web-Google | 916K | 5.1M | web |
| flickr | 820K | 9.8M | social |
| roadNet-CA | 2.0M | 5.5M | road |
| soc-LiveJournal1 | 4.8M | 69M | social |
| [TBD] | [TBD] | [TBD] | [TBD] |

> 注: 评估范围仍在扩充中。PageRank (PR) 因运行问题已排除。最终以实际完成的实验为准。

### §4.3 Baselines

| Baseline | 来源 | 说明 |
|----------|------|------|
| No Prefetch | — | 性能下界 |
| stride-INTRA (+ IMA gating) | 参考 Snake | Intra-warp stride, 过滤 IMA PC |
| Snake | MICRO'23 | Variable-length chain stride |
| Spare Register | HPCA'14 | 唯一 GPU IMA 前驱 [TBD: 部分完成] |
| CAPS | IPDPS'18 | CTA-aware stride |
| Ideal L1D | — | 性能上界 (load-only perfect L1) |

### §4.4 Metrics

- **IPC Speedup**: 主性能指标
- **IMA Coverage**: IMA demand hits / (IMA demand hits + misses), 分 index/data
- **IMA Accuracy**: IMA useful prefetch / total prefetch
- **Timeliness**: hits / (hits + hit_reserved), 衡量预取是否及时
- **MSHR Pressure**: RFAIL 分布, miss_queue/MSHR peak

---

## §5 Evaluation (3.0 pages) `[占位符]`

> 结构参考: Snake §5 (Coverage → Performance → Energy → Sensitivity → Cost)
> 数据来源: `06_evaluation_plan/experiment_results.md` (唯一集中数据源)
> **细化条件**: 需提供 Fig 11-19 中至少主结果图（Fig 11 IPC Speedup）

### §5.1 主要结果: IPC Speedup (~0.7 page)

**Fig 11**: 全量 IPC Speedup [双栏 7.0"]
- Grouped bar chart: 6 算法 × 4+ 数据集 (x 轴), 3 方案 (No-PF / GRASP / Ideal L1D)
- 颜色 + hatching (per CLAUDE.md 绘图规范, ≥3 方案必须同时使用)
- GRASP 使用实色无 hatch (视觉突出)
- 参考风格: Snake Fig 18 / DMP Fig 12

**分析要点**:
- Geomean 数据 [TBD: 最终全量 geomean]
- 各 workload 差异分析 (为什么 BFS/SSSP 高, CC 有退化)
- 达到 Ideal L1D 天花板的百分比 → 量化 GRASP 释放了多少潜在性能

**亮点数据** (from INDEX.md, ima_med 全量):
- BFS +49.8%, SSSP +44.0%, SpMV +26.6%, BC +23.3%, geomean +35.5%

**4类图 × 7算法数据** (from INDEX.md):
- web-Google: BFS +56.1%, SSSP +46.6%, CC +93.6%, SpMV +40.1%
- flickr: BFS +27.0%, CC +138.6%, SpMV +38.0%

### §5.2 Coverage, Accuracy, Timeliness (~0.5 page)

**Fig 12**: 三指标并列 [双栏 7.0"]
- 3 组 bar chart: Coverage / Accuracy / Timeliness
- 每组按 workload 分, 分 index / data 两层 (GRASP 特色)
- 参考风格: DMP Fig 11

**分析要点**:
- Index coverage vs data coverage 差异 → 两步 pipeline 各自的贡献
- Accuracy 讨论: 当前整体 accuracy (~22.8% in expanded eval, 55.9% in ima_med) → root cause 分析
- Timeliness: index 高 (stride 预测准) vs data 略低 (依赖 index 返回时机)

### §5.3 与 SOTA Baseline 对比 (~0.5 page)

**Fig 13**: GRASP vs All Baselines [双栏 7.0"]
- Grouped bar: 各 workload × 5 方案 (stride-INTRA / Snake / CAPS / Spare Register / GRASP)
- 颜色 + hatching

**关键对比点**:
| Baseline | 为什么 GRASP 更好 | 关键数据 |
|----------|-----------------|---------|
| stride-INTRA | 只捕获规则 stride, 无法处理 IMA | geomean +2.0% |
| Snake | Variable-chain 但仍是 stride chain | [TBD] |
| CAPS | CTA-aware 但显式排除 indirect access | SpMV +14.3%, 其余 <0.1% |
| Spare Register | Fermi 架构, 单层 load-pair, tag-based | avg 10% |

### §5.4 敏感性分析 (~0.7 page)

**Fig 14-17**: 4 个敏感性图 [各单栏 3.5"]
- (a) **CT size**: 8 / 16 / 32 / 64 entries → IPC 变化
- (b) **Prefetch distance**: 2 / 4 / 8 → coverage vs RFAIL trade-off
- (c) **IST confidence threshold**: 1 / 2 / 4 / 8 → accuracy vs warm-up 时间
- (d) **Throttle cooldown**: 不同 (threshold, cooldown) 组合 → IPC + useless PF (已有 DSE 数据)

可合并为一个 Fig 14 (4 subfigures) 节省空间, 或分成 2 个双子图。

### §5.5 案例分析 & 负面结果 (~0.3 page)

> 数据来源: `future_work.md` §2, §3

**Fig 17**: 逐 kernel 性能分解 [单栏 3.5"]
- 选 1-2 个代表 workload (e.g., BFS 正面 + CC 负面), stacked bar 展示各 kernel 的 speedup

**负面结果坦诚分析**:
- **CC cit-Patents -7%**: Pattern III/IV 占主导, GRASP 的 index prefetch 有效但 data prefetch timeliness ≈ 0, 额外 MSHR 占用反而造成性能损失
- **SpMV stride 学习失效**: ×16 展开使 16 PC 中仅 4-5 个学到 stride → IST 利用率低, 3M RFAIL
- **roadNet 系列收益低**: 图稀疏 (avg degree ~3), IMA 不是瓶颈, 几乎无优化空间

### §5.6 Hardware Overhead (~0.3 page)

**Table 4**: 存储开销对比

| Prefetcher | Storage/Unit | Unit | Effective per-thread |
|------------|:-----------:|:----:|:-------------------:|
| IMP [MICRO'15] | 0.9 KB | per-core | 0.9 KB |
| DMP [HPCA'24] | 0.9 KB | per-core | 0.9 KB |
| Tyche [TACO'24] | 0.57 KB | per-core | 0.57 KB |
| Snake [MICRO'23] | ~0.8 KB | per-SM | ~12 B/warp |
| **GRASP** | **2.3 KB** | **per-SM** | **~36 B/warp** |

注: CPU per-core 和 GPU per-SM 不直接可比; per-warp 等效更公平

**面积/功耗估算** [TBD: 需要 CACTI 或类似工具]

---

## §6 Related Work `[已完成 v2 — 2026-04-08]`

> 组织: **三分法** (CPU IMA / GPU Prefetchers / Adjacent) — v2 合并 GPU stride + GPU IMA void
> 参考: Snake §6 (terse), DMP §VI (comprehensive)
> 写作策略: 混合 single-citation 精析 + batch 引用
> 实装: `main.tex` §6 v1 (2026-04-08, 4-section) → v2 合并 §6.2+§6.3, 压缩 §6.4
> 详细写作计划: `.claude_global/plans/tingly-cooking-snail.md`

### §6 Opening (R-2 uniqueness reassertion)

> "GRASP is the first dedicated IMA prefetcher for modern GPU architectures, and the first to exploit ISA-exposed structural information for zero-inference chain detection."

### §6.1 CPU IMA Prefetchers

- **精析 (5)**: IMP [MICRO'15], Prodigy [HPCA'21], DMP [HPCA'24], DVR [MICRO'23], Tyche [TACO'24]
- **Batch (8)**: ATP, Gretch, Event-Trigger [ASPLOS'18], Vector Runahead [ISCA'21], Precise Runahead [HPCA'20], CRISP [ASPLOS'22], Domino [HPCA'18], Magellan [ISCA'25]
- **Closing**: "assume single-threaded instruction stream with per-core state; replicating per warp → 19-30% L1 storage (see §2.4)"

### §6.2 GPU Prefetchers (merged from old §6.2 + §6.3)

- **精析 (4) — stride**: MT-Prefetch [MICRO'10], CAPS [IPDPS'18], APRES [ISCA'16], Snake [MICRO'23]
- **Batch (8) — stride family**: Orchestrated [ISCA'13], WASP [TC'18], Stream [JSupercomp'18], APOGEE [PACT'13], COMPASS [ASPLOS'10], Ganguly UVM [ISCA'19], DSAP [Access'18], G-MAP [DAC'17]
- **Spare Register tail (1)**: 2-sentence trailing note instead of standalone subsection — "sole prior GPU prefetcher to address indirect access directly … three-iteration training latency and one-to-one mapping have not been revisited in the intervening decade"

### §6.3 Adjacent Directions (compressed)

Three batch-cite clusters in five sentences total (was three italic-labeled paragraphs in v1):

**(a) Software prefetching**: jain2013linearize [MICRO'13], ainsworth2019indirect [ToCS'19], jain2024dlrm [MICRO'24], deng2024swprefetch [DaMoN'24], sotiropoulos2025asap [SC'25]

**(b) Specialised GPU prefetchers**: chou2023treelet [MICRO'23], ha2025latpc [MICRO'25], posluns2025tsp [MICRO'25]

**(c) Graph & irregular accelerators**: ham2016graphicionado [MICRO'16], mukkara2018hats [MICRO'18], ahn2015tesseract [ISCA'15], rahman2020graphpulse [MICRO'20], geng2021igcn [MICRO'21], orenes2022maple [ISCA'22]

**Closing (chapter-level, natural hand-off to §7)**:
> "GRASP thus occupies the previously empty cell at the intersection of *GPU*, *hardware-only*, and *IMA-aware*."

### Citation inventory (v2)

- **Total**: 40 distinct cites (preserved through the merge)
- **MICRO hits**: 13 (IMP, DVR, Snake, MT-Prefetch, Jain&Lin, DLRM, Treelet, LATPC, TSP, GraphPulse, HATS, I-GCN, Graphicionado)
- **New bib entries added (v1)**: 24 (see `sample-base.bib` "§6 Related Work — additional citations")
- **Dropped**: `chatterjee2014rethinking` / Lashgar&Baniasadi — venue unverified
- **v2 changes vs v1**: §6.2 + §6.3 → merged §6.2 "GPU Prefetchers"; §6.4 → compressed §6.3 "Adjacent Directions"; Spare Register downgraded from solo subsection to 2-sentence trailing note in §6.2; cite count unchanged

---

## §7 Conclusion (0.5 pages) `[占位符]`

> **细化条件**: 需 §1-§5 完成后才能写，无图表依赖

- ¶1: 问题回顾 — GPU IMA 导致 51-84% L1 miss, 1.75-3.04× potential, 但 CPU IMA 方案无法迁移且 GPU prefetcher 回避 IMA
- ¶2: 核心贡献 — IMAD.WIDE 结构性发现 + GRASP 设计 (零推断检测, index-data pipeline, PC 归并, per-SM 共享)
- ¶3: 主要结果 — geomean +X% [TBD], up to Y% [TBD], 超越所有 SOTA GPU prefetcher baseline, ~2.3 KB/SM
- ¶4: Future work (1 句) — Pattern III/IV 覆盖扩展 + IMAD.WIDE 变体检测泛化 + throttle 策略优化

---

## Figure 架构总览

| Fig | 名称 | Section | 类型 | 尺寸 | 参考 | 状态 |
|:---:|------|:-------:|------|:----:|------|:----:|
| 1 | IMA L1 miss 占比 + Ideal speedup | §1.1 | 双子图 bar | 7.0" | DMP Fig 1 | 已有数据 |
| 2 | GPU SM 架构 + GRASP 位置 | §2.1 | 架构图 | 3.5" | Snake Fig 2 | 需绘制 |
| 3 | 四类 IMA Pattern 示例 | §2.2 | 4 子图 | 7.0" | DMP Fig 3 | 需绘制 |
| 4 | L1 miss rate + L2 hit rate | §2.3 | 分组 bar | 3.5" | Snake Fig 3-5 | 已有数据 |
| 5 | LDG→IMAD.WIDE→LDG 链 | §2.4 | SASS+箭头 | 3.5" | Snake Fig 7 | 已有 SASS |
| 6 | GRASP 整体架构框图 | §3.1 | Block diagram | 7.0" | DMP Fig 10 | 需绘制 |
| 7 | CD 检测流程图 | §3.2 | Flowchart | 3.5" | Snake Fig 12 | 需绘制 |
| 8 | CT/TT 查找示例 | §3.3 | Table+箭头 | 3.5" | IMP Fig 4-5 | 需绘制 |
| 9 | Index-Data Pipeline 时序 | §3.5 | Timeline | 7.0" | Snake Fig 15 | 需绘制 |
| 10 | 端到端 Worked Example | §3.8 | 综合示例 | 7.0" | DMP Fig 4 | 需绘制 |
| 11 | IPC Speedup (全量) | §5.1 | Grouped bar | 7.0" | Snake Fig 18 | 部分数据 |
| 12 | Coverage/Accuracy/Timeliness | §5.2 | 三组 bar | 7.0" | DMP Fig 11 | 部分数据 |
| 13 | GRASP vs SOTA Baselines | §5.3 | Grouped bar | 7.0" | Snake Fig 18 | 部分数据 |
| 14 | 敏感性: CT size | §5.4 | Line/bar | 3.5" | Snake Fig 20 | 待实验 |
| 15 | 敏感性: Prefetch distance | §5.4 | Line/bar | 3.5" | Snake Fig 20 | 待实验 |
| 16 | 敏感性: IST threshold | §5.4 | Line/bar | 3.5" | Snake Fig 20 | 待实验 |
| 17 | 敏感性: Throttle cooldown | §5.4 | Line/bar | 3.5" | Snake Fig 23 | 已有数据 |
| 18 | 案例分析 / 逐 kernel | §5.5 | Stacked bar | 3.5" | DMP Fig 16 | 部分数据 |
| 19 | RFAIL / Useless PF 分布 | §5.5 | Stacked bar | 3.5" | DMP Fig 16 | 部分数据 |
| 20 | PC 膨胀归并效果 | §5.2 | Bar (before/after) | 3.5" | — | 已有数据 |
| 21 | IMAD.WIDE 覆盖率 (跨算法) | §2.4 | Bar | 3.5" | — | 已有数据 |

## Table 架构总览

| Table | 名称 | Section | 状态 |
|:-----:|------|:-------:|:----:|
| 1 | IMA Pattern Prefetchability | §2.2 | 已有分类 |
| 2 | GRASP 硬件开销明细 | §3.7 | 已有数据 |
| 3 | 实验配置 (GPU + Benchmarks) | §4 | 部分 [TBD] |
| 4 | 存储开销对比 | §5.6 | 已有数据 |

---

## Insight → Section 映射

| Insight | 内容 | 论文位置 |
|:-------:|------|---------|
| #1 | IMAD.WIDE 零推断检测 | §1.4 (结论) + §2.4 (展开) + §3.2 (设计) |
| #2 | L1/L2 不对称 → L2→L1 | §2.3 |
| #3 | IMA 占 L1 miss 51-84% | §1.1 + §2.3 |
| #4 | (base,scale) 归并解 PC 膨胀 | §1.4 + §3.3 |
| #5 | One-to-many 索引复用 | §2.2 + §3.3 |
| #6 | Per-SM 共享 64 倍分摊 | §1.4 + §3.1 |
| #7 | IMAD.WIDE 覆盖率 88-99% | §2.4 |
| #8 | 四类 Pattern Prefetchability | §2.2 (Table 1) |
| #9 | Ideal L1D 天花板 | §1.1 (Fig 1) + §5.1 |
| #10 | 写无效化保证正确性 | §3.2 |
| #11 | Stride 跨 CTA 污染修复 | §3.4 |

---

## [TBD] 标记汇总

| 项目 | 位置 | 依赖 |
|------|------|------|
| 最终 geomean 数据 | §1.5, §5.1, §7 | 全量实验完成 |
| 评估范围 (算法+数据集) | §4.2 | benchmark 扩充完成 |
| Spare Register baseline 数据 | §5.3 | 实验完成 |
| 面积/功耗估算 | §3.7, §5.6 | CACTI 估算 |
| 敏感性分析数据 | §5.4 | 参数扫描实验 |
| Snake baseline 数据 | §5.3 | 实验完成 |
