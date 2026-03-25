# 02 — 相关工作调研

> 对应文件夹：`02_related_work/`（论文 PDF 按 `cpu/`、`gpu/` 分类存放）
>
> 状态：**调研进行中** — 论文收集完成（CPU 8篇 + GPU 9篇），笔记与分析进行中
>
> 补充文档：
> - `02_related_work/gpu_prefetcher_impl_provenance.md`：GPU prefetcher 的实现公开性、evaluation baseline provenance、开源 simulator 依赖梳理

---

## 目标

系统调研 CPU/GPU 上针对 irregular/indirect memory access 的 prefetch 方案，明确：
1. 已有方案能做什么、不能做什么
2. 本工作的 **novelty 定位**（gap 在哪里）
3. 可以借鉴的核心思路

---

## A. CPU 端 IMA Prefetcher（8 篇）

这些工作通常假设单线程/少线程、大 cache、hardware budget 不是首要限制。

### A1. IMP — Indirect Memory Prefetcher
- **来源**: Yu et al., **MICRO 2015**
- **机制**: 检测 A[B[i]] 模式——利用 streaming prefetcher 捕获 B[i] 的顺序访问，当 B[i] 的值与后续内存地址匹配时，建立间接关系并预取 A[B[i]]。同时提出 partial cacheline 机制减少带宽浪费。
- **硬件开销**: ~0.7 KB（Prefetch Table 16 entries + Indirect Pattern Detector 4 entries）
- **效果**: 64 核平均 56% 加速（最高 2.3x），覆盖 85% L1 miss，准确率 85%
- **局限**: 不能处理 ranged indirect（如 BFS/SSSP 中 row_offsets 范围遍历，覆盖率 <5%）；依赖 index array 的顺序流式访问；假设有限的 shift 候选集（2,3,4,-3）
- **评估负载**: PageRank, TC, Graph500, SGD, LSH, SpMV, SymGS
- **GPU 适配障碍**: 多 warp 地址流交织破坏 streaming pattern 检测；in-order tiled 架构假设与 GPU 不同

### A2. DMP — Differential-Matching Prefetcher
- **来源**: Fu et al., **HPCA 2024**
- **机制**: 比较 index 值的差分序列与访问地址的差分序列，如果成比例则确认间接模式。支持四种模式：single-level、ranged、multi-level、multi-way。动态调整预取 degree 保持覆盖率。
- **硬件开销**: ~0.9 KB
- **效果**: 平均 1.8x 加速（最高 5.6x），覆盖率 79.5%，准确率 92.8%，时效性 95.2%
- **局限**: 仍需 index array 有可检测的 stride；差分匹配在分支预测错误时可能被污染
- **评估负载**: GAP (SpMV/PR/BFS/SSSP/BC/CC), NAS (IS/CG), HPCG, HashJoin
- **GPU 适配障碍**: 差分序列受 warp 交替影响可能失真

### A3. Magellan — Loop-Guided Prefetcher
- **来源**: Fu et al., **ISCA 2025**
- **机制**: 纯软件编译器方案（LLVM IR pass）。提取跨循环层级的依赖图检测复杂 IMA 模式，包括 "local IMA"（同一循环内）和 "global IMA"（依赖外层循环变量）。能跨外层循环迭代预取，解决内层循环短导致预取距离不够的问题。
- **硬件开销**: 无（纯软件），动态指令数降低 14%（相比其他 SW prefetcher）
- **效果**: 比最佳 SW prefetcher 平均再提升 14%，cache miss 减少 25%。检测近 100% IMA 模式。87.6% 的 cache miss 与 IMA 相关。
- **局限**: 需要源码和重编译；无法动态适应运行时条件；prefetch distance 静态设定
- **评估负载**: GAP/GraphBIG (SpMV/PR/BFS/SSSP/BC/CC/TC/DC), HPCG, NAS, HashJoin, RandomAccess
- **GPU 适配障碍**: GPU kernel 编译流程不同（CUDA/PTX/SASS），SW prefetch 指令效果受 warp 调度影响

### A4. Tyche — Bilateral Propagation Prefetcher
- **来源**: Xue et al., **TACO 2024**
- **机制**: 利用前端指令依赖信息（PC 和操作数依赖）精确挖掘 IMA 生产者-消费者关系。记录中等长度的依赖链，支持非线性 IMA（如 A[func(B[i])]）。
- **硬件开销**: 仅 0.57 KB（所有对比方案中最小——PT 31 entries + DCT 24 entries + AGQ 16 entries）
- **效果**: 比 stride prefetcher 平均提升 20.3%，超越 IMP 15.9%、Vector Runahead 10.7%
- **局限**: 需要在 decode/rename 阶段记录依赖信息；完全关联表功耗较高；仅评估单核
- **评估负载**: Crono, Ligra, Graph500, HashJoin, HPCC, SpMV
- **GPU 适配障碍**: GPU 前端结构（warp-based fetch/decode）与 CPU 差异大

### A5. ISB — Irregular Stream Buffer (Linearizing)
- **来源**: Jain & Lin, **MICRO 2013**
- **机制**: 引入额外间接层，将任意相关地址映射到连续的 "结构地址空间"，使不规则流转化为顺序流。结合 PC localization 和地址关联。元数据与 TLB 同步。
- **硬件开销**: 8-32 KB on-chip + 片外 DRAM 元数据
- **效果**: 32KB 配置平均 23.1% 加速，准确率 93.7%；8KB+stride 混合 40.8%
- **局限**: 针对时间关联性（general irregularity）而非 A[B[i]] 特定模式；需要片外 DRAM 存储元数据（8.4% 额外流量）
- **评估负载**: SPEC CPU 2006
- **GPU 适配障碍**: 存储开销大（32KB/core 在 GPU 上不现实）；片外元数据访问增加延迟

### A6. Prefetch Arrays — 链式数据结构预取
- **来源**: Karlsson et al., **HPCA 2000**
- **机制**: 在链式数据结构中构建 jump pointer + prefetch array，允许跳过多个节点进行预取。提供软件版和硬件辅助版。
- **硬件开销**: 极小（简单预取引擎：base addr register + counter + prefetch issue logic）
- **效果**: 内存 stall 减少 23%-51%（链表），~60%（二叉树）
- **局限**: 需要修改数据结构（侵入式）；仅针对链表/树，**不适用于数组型 A[B[i]]**；评估基于简单单发射处理器
- **评估负载**: Olden 基准 (mst/health/treeadd/perimeter), MySQL TPC-B
- **GPU 适配障碍**: 数据结构修改方案在 GPU 并行上下文中更复杂；pointer chasing 在 GPU 图负载中较少见

### A7. SW Prefetch — Software Prefetching for IMA
- **来源**: Ainsworth & Jones, **CGO 2017**
- **机制**: LLVM 编译器 pass，自动识别循环中的 A[f(B[i])] 模式，通过 DFS 算法找到需复制的指令集来计算未来迭代的预取地址。为 index 和 data 数组分别插入 staggered prefetch。
- **硬件开销**: 无（纯软件），但动态指令数增加 10-100%
- **效果**: Haswell 1.3x, Cortex-A57 1.1x, Cortex-A53 (in-order) 2.1x, Xeon Phi 2.7x
- **局限**: 指令开销大；无法处理复杂控制流（如 Graph500 edge list）；prefetch distance 非自适应；仅限最内层循环
- **评估负载**: NAS (IS/CG), RandomAccess, HashJoin, Graph500
- **GPU 适配障碍**: GPU 的 SIMT 模型使 SW prefetch 的粒度和时机难以精确控制

### A8. ATP — Array Tracking Prefetcher (Informed Prefetching)
- **来源**: Cavus et al., **TACO 2020** (扩展自 ICCD 2018)
- **机制**: 软硬协同设计。软件侧插入 Array Tracking Instructions (ATI) 传递数据结构遍历信息（base address, element size, 间接深度）；硬件侧的 Prefetch Computation Unit (PCU) 从 L1 读 index 值并计算间接地址。配合 Dynamic Stride 机制动态调整预取距离。
- **硬件开销**: ~251 B/core（约 IMP 的 1/4），8-entry Prefetch Request Queue
- **效果**: 单核平均 2.17x（最高 5.57x），显著优于 SW prefetch (1.84x) 和 IMP (1.32x)
- **局限**: 需要编译器/程序员插入 ATI 指令；index 值 L1 miss 时预取管线停顿并放弃；需要额外 L1 和 DTLB 读端口
- **评估负载**: NAS, PageRank, TC, Graph500, Histogram, HashJoin
- **GPU 适配障碍**: 需要 ISA 扩展（ATI 指令）；GPU 的 L1 端口竞争更激烈

---

## B. GPU 端 Prefetch / Cache 优化（9 篇）

### B1. DSAP — Data Structure-Aware Prefetching
- **来源**: Guo et al., **IEEE Access 2018**
- **机制**: 利用 BFS 中 CSR 数据结构的已知遍历顺序（worklist → vertex list → edge list → visited list）生成链式预取请求。自适应细粒度管理根据预取数据利用率动态调整预取的数据结构级别。
- **硬件开销**: 每 SM 一个 DSAP Unit（地址范围表 4 entries + 8 comparators + runtime info table + 4 request generators）
- **效果**: 几何平均 IPC 提升 28%（最高 48.4%），L1 miss 减少 11.9%-26.7%，预取利用率 >75%，功耗增加 8.3%
- **局限**: **仅适用于 BFS 风格的 CSR 遍历**；需要修改 cudaMalloc API 注入地址范围信息；链式预取有串行延迟依赖
- **IMA 相关性**: ★★★ 直接针对图算法 IMA，但通用性不足

### B2. CAPS — CTA-Aware Prefetching and Scheduling
- **来源**: Koo et al., **IPDPS 2018**
- **机制**: 将地址分解为 per-CTA base + inter-warp stride。"leading warp" 先执行获取 base，然后为所有 trailing warp 生成预取地址。含预取感知调度器 (PAS)，在 two-level scheduler 基础上区分 leading/trailing warp。
- **硬件开销**: PerCTA Table (21B/entry, up to 4 entries/CTA) + DIST Table (9B/entry)
- **效果**: 平均 8% 加速（最高 27%），预测准确率 >97%
- **局限**: **显式排除 indirect/data-dependent 访问**（通过回溯 source register 检测并跳过）；假设 stride 跨 CTA 一致
- **IMA 相关性**: ★★ 提供了 CTA 级地址分析框架和 leading warp 概念，但核心机制不适用于 IMA

### B3. Spare Register Aware Prefetching
- **来源**: Lakshminarayana & Kim, **HPCA 2014**
- **机制**: 检测 "load-pair" 模式——strided head-load（如遍历 edge list）+ data-dependent tail-load（如查 visited list）。用硬件 tag (value tag + load-id tag) 追踪依赖关系。**将预取数据存入空闲寄存器**而非 cache，避免 GPU 小 cache 的提前驱逐问题。预取距离根据循环平均迭代次数自适应调整。
- **硬件开销**: ~1365 B/SM（register file 的 1.04%）— value tags 126 bits + load-id tags 126 bits + shadow iteration counters + allocated reg lists
- **效果**: 平均 10% 加速（最高 51%），9 个图算法 kernel (H-BFS, H-SSSP, H-MST, LS-BFS, LS-SSSP, LS-MST, ST-Connectivity, Graph Coloring, MIS)
- **局限**: 仅限 load-pair（一层间接）；需 3 次迭代训练检测目标 load；依赖空闲寄存器可用性；仅 intra-warp 级别，未利用 inter-warp 或 inter-CTA 机会
- **IMA 相关性**: ★★★★ **最直接相关**——load-pair 即 A[B[i]]，寄存器存储方案巧妙解决 GPU 特有问题

### B4. Many-Thread Aware Prefetching (MT-Prefetching)
- **来源**: Lee et al., **MICRO 2010**
- **机制**: 提出 inter-thread prefetching (IP)——线程 N 为线程 N+k 预取，利用 GPU 线程共享相同访问模式的特点。Per-warp stride (PWS) → global stride (GS) 晋升机制。含自适应 throttling（基于 early eviction rate 和 merge ratio）。
- **硬件开销**: PWS Table + GS Table + Prefetch Cache + Throttle Engine
- **效果**: 平均 ~15-16% 加速（最高 ~50%）
- **局限**: 针对规则 stride 模式；inter-thread 假设（线程 N 的 pattern 可预测 N+32）在图算法中不成立；训练开销大
- **IMA 相关性**: ★★ 奠基性工作；throttling 机制（early eviction rate + merge ratio）是通用方法，可借鉴

### B5. Snake — Variable-length Chain-based Prefetching
- **来源**: Mostofi et al., **MICRO 2023**
- **机制**: 将单 stride 扩展为可变长度的 stride chain，检测 inter-thread chain（连续 PC 间 stride）+ intra-warp stride + inter-warp stride。解耦存储策略将预取数据分离存放在 unified shared memory 中。需 3 个 warp 训练后晋升。
- **硬件开销**: Head Table + Tail Table（< 1% V100 面积/功耗）
- **效果**: memory-bound 应用平均 17% 加速，覆盖率 ~80%，准确率 ~75%，能耗降低最高 17%
- **局限**: 本质仍依赖固定 stride 模式；需 3 个 warp 训练；解耦存储减少有效 L1 容量
- **IMA 相关性**: ★★ chain 概念部分适用，但无法处理数据依赖地址
- **注**: 基于 **Accel-Sim v1.2.0** 评估，与本项目使用相同模拟器

### B6. Stream Data Prefetcher
- **来源**: Neves et al., **Journal of Supercomputing 2018**
- **机制**: 离线编码 CTA 级访问模式为 3D 仿射函数描述符 {offset, hsize, stride, vsize, span, dsize}，运行时解码生成预取地址。独立 prefetch buffer (32KB) 并行于 L1。预取请求绕过 L2 直达 global memory。
- **硬件开销**: Prefetch Buffer 32KB/SM + AGU + Descriptor Memory 1KB/SM
- **效果**: 平均 3x 加速（最高 9.2x），L1 hit rate 平均提升 61%
- **局限**: **仅处理可静态描述的仿射模式**；需要离线分析和手动编码；不适用于数据依赖访问
- **IMA 相关性**: ★ 不适用于 IMA，但独立 prefetch buffer 架构可借鉴

### B7. Rethinking Prefetching in GPGPUs
- **来源**: Lashgar & Baniasadi, ~2013-2014
- **机制**: 静态分析将数组索引分为可预测/准静态可预测（依赖 threadIdx/blockIdx）/不可预测（依赖运行时变量或间接 load）。对可预测索引，编译器传递线性多项式给硬件，CTA 分派时计算地址范围进行 burst 预取。
- **硬件开销**: Prefetch Table 64 entries + Prefetch Controller + Prefetch Buffer（评估中使用理想化无限 buffer）
- **效果**: 最高 59% 加速（理想条件），但低 occupancy 时反而降性能（CTA stall 等待预取完成）
- **局限**: **显式将 IMA 归为 "不可预测" 并排除**；需 API 修改 (cudaSetCTATracker)
- **IMA 相关性**: ★ 互补方案——处理规则部分，IMA 留给其他机制。其 "unpredictable" 分类恰好界定了 IMA prefetcher 的目标

### B8. WASP — Warp-Aware Selective Prefetching
- **来源**: Oh et al., **IEEE TC 2018**
- **机制**: 利用 SIMT 所有 warp 执行相同指令流的特性——监控每个 warp 的 dynamic load execution count，先进 warp 的访问用于为落后 warp 生成 inter-warp stride 预取。动态调整预取距离（参数 k），基于冗余预取和 early eviction 检测。
- **硬件开销**: Load Execution Count Table (48 entries) + Stride Calculator + 48 comparators
- **效果**: 平均 16.8% 加速，冗余预取 <10%（对比 MTA 24.7%, SLD 26.0%）
- **局限**: 依赖 inter-warp stride 规则性；**BFS/SPMV 的规则 stride 比例显著偏低**
- **IMA 相关性**: ★★ warp 进度监控思路可借鉴，但 stride 预测对 IMA 失效。论文量化了 BFS/SPMV 的 stride 不规则性（inter-warp regular stride ratio 远低于规则应用）

### B9. COMPASS — Programmable Prefetcher Using Idle GPU Shaders
- **来源**: Woo & Lee, **ASPLOS 2010**
- **机制**: 利用集成 CPU-GPU 平台中空闲的 GPU shader 模拟各种 prefetcher（stride/Markov/delta/region），为 CPU 单线程应用预取。GPU register file 作为 prefetch table，可模拟 4096+ entries。
- **硬件开销**: Miss Address Provider (MAP) + GPU register file 作为 prefetch table + 16-entry command queue
- **效果**: CPU 单线程平均 68% 加速
- **局限**: 针对 CPU 应用，非 GPU 应用预取；GPU 忙时失效；特定集成架构假设
- **IMA 相关性**: ★ 直接相关性低，但可编程预取引擎的思想有启发——不同应用可加载不同 prefetch 算法

---

## C. 综合对比

### C1. CPU IMA Prefetcher 对比

| 论文 | 年份 | 会议 | 类型 | 存储 | 平均加速 | IMA 模式支持 |
|------|------|------|------|------|---------|-------------|
| Prefetch Arrays | 2000 | HPCA | SW+HW | 极小 | stall↓23-51% | 链式数据结构 |
| ISB | 2013 | MICRO | HW | 8-32 KB | 1.23-1.41x | 通用时间关联 |
| IMP | 2015 | MICRO | HW | 0.7 KB | 1.56x (64c) | Single-level A[B[i]] |
| SW Prefetch | 2017 | CGO | SW | 0 | 1.1-2.7x† | A[f(B[i])] |
| ATP | 2020 | TACO | SW+HW | 251 B | 2.17x | Single/multi-level |
| DMP | 2024 | HPCA | HW | 0.9 KB | 1.8x | Single/ranged/multi-level/multi-way |
| Tyche | 2024 | TACO | HW | 0.57 KB | 1.20x‡ | 含非线性 A[func(B[i])] |
| Magellan | 2025 | ISCA | SW | 0 | 1.14x§ | 跨循环层级复杂 IMA |

> †架构差异大（in-order 收益高）  ‡相对 stride prefetcher  §相对最佳 SW prefetcher

**CPU 端演进趋势**: 2000→2015 单层 A[B[i]] 或链式结构 → 2017→2020 编译器方案和软硬协同 → 2024→2025 多层/ranged/非线性 + 极紧凑硬件 (0.57-0.9 KB) 或高级编译分析

### C2. GPU Prefetcher 对比

| 论文 | 年份 | 会议 | 目标模式 | 平均加速 | IMA 支持 |
|------|------|------|---------|---------|---------|
| MT-Prefetch | 2010 | MICRO | Stride + inter-thread | ~15% | ✗ |
| COMPASS | 2010 | ASPLOS | 可编程 (for CPU) | 68%* | ✗ |
| Spare Register | 2014 | HPCA | Load-pair (IMA) | 10% (max 51%) | ✓ 单层 |
| DSAP | 2018 | IEEE Access | CSR 图遍历 | 28% | ✓ BFS 专用 |
| CAPS | 2018 | IPDPS | CTA-aware stride | 8% | ✗ 显式排除 |
| Stream | 2018 | J.Supercomp | 仿射模式 | 3x | ✗ |
| WASP | 2018 | IEEE TC | Warp-aware stride | 16.8% | ✗ |
| Rethinking | ~2014 | — | CTA-level burst | max 59% | ✗ 显式排除 |
| Snake | 2023 | MICRO | Stride chain | 17% | ✗ |

> *COMPASS 用于 CPU 单线程应用

**GPU 端演进趋势**: 2010→2014 stride-based 为主 + 少量 IMA 探索 → 2018 CTA/warp 感知 + 一个 BFS 专用方案 → 2023 stride chain 扩展。**至今没有通用的 GPU IMA hardware prefetcher。**

---

## D. Gap 分析与 Novelty 定位

### D1. 已识别的关键 Gap

**Gap 1: GPU 上缺少通用 IMA hardware prefetcher**
- CPU 侧已有 IMP/DMP/Tyche 等成熟方案，但它们假设单线程/少线程、大 cache、地址流不交织
- GPU 侧仅 Spare Register (2014) 处理 load-pair（单层 IMA），DSAP (2018) 仅针对 BFS
- **没有 GPU 上支持 multi-level / ranged / 通用图算法的 IMA prefetcher**

**Gap 2: CPU IMA 方案未考虑 GPU 微架构约束**
- 海量并发 warp → 地址流高度交织，per-warp 状态表不现实
- L1D 容量小 (32-128KB) → prefetch 污染风险极高
- Coalescing 已聚合 → prefetcher 看到的是合并后的请求
- NoC 带宽共享 → 无用预取直接抢占有效带宽
- 多 warp 切换已提供 latency hiding → prefetch 的增量收益受限

**Gap 3: GPU prefetcher 未利用 IMA 的结构性信息**
- CAPS/WASP/Snake 都基于 stride 检测，显式或隐式排除 IMA
- 但 IMA 并非完全不可预测——index array 通常是顺序/stride 访问的，可利用
- CPU 侧的 IMP/DMP 核心思想（检测 index load → 用 index 值预取 data）可以适配

### D2. Novelty 定位

<!-- TODO(human): 基于以上 gap 分析，确定本工作的 novelty 定位 -->
<!-- 需要回答以下三个问题：                                    -->
<!-- 1. 我们的方案将填补哪个/哪些 gap？                          -->
<!-- 2. 与最近的工作（Spare Register, DSAP, DMP）的核心差异化？    -->
<!-- 3. 预期的 contribution claim 框架（3 点）                   -->

---

## E. 可借鉴的核心思路

### 从 CPU IMA 方案借鉴

| 思路 | 来源 | 适配挑战 |
|------|------|---------|
| Index load 值 → 计算 data address 预取 | IMP, DMP, ATP | GPU 地址流交织需要 PC-based 过滤 |
| 差分匹配检测间接模式 | DMP | GPU 上差分序列受 warp 交替影响 |
| 指令依赖链追踪 producer→consumer | Tyche | GPU 前端结构不同（warp-based fetch/decode） |
| Dynamic stride (自适应预取距离) | ATP | GPU 的 warp 切换使 "距离" 概念不同 |
| Partial cacheline 减少带宽浪费 | IMP | GPU coalescing 已部分实现类似效果 |
| 软硬协同 (ISA hint + HW prefetch) | ATP | 需 CUDA/PTX 扩展，但思路可行 |

### 从 GPU Prefetcher 借鉴

| 思路 | 来源 | 直接可用性 |
|------|------|-----------|
| 预取数据存入空闲寄存器 | Spare Register | ★★★ 解决 L1 提前驱逐的核心难题 |
| 数据结构地址范围注册 | DSAP | ★★ 可推广到通用 IMA |
| CTA/warp 感知调度配合预取 | CAPS, WASP | ★★ 协调预取时序 |
| Early eviction rate throttling | MT-Prefetch | ★★★ 必要的污染控制 |
| 解耦预取存储 (prefetch buffer) | Snake, Stream | ★★ 避免污染 L1 |
| Warp 进度监控 → 选择性预取 | WASP | ★★ 识别哪些 warp 需要预取 |
| Indirect access detection (排除法) | CAPS | ★★ 反向可用——识别哪些 load 是 IMA |

---

## F. 关键问题（已回答）

1. **是否已有专门针对 GPU graph workload IMA 的 hardware prefetcher？**
   → 部分有。Spare Register (2014) 做 load-pair 单层 IMA，DSAP (2018) 做 BFS 专用。但**没有通用方案**，这是核心 gap。

2. **CPU 端 IMP/DMP 等方案在 GPU 上最大的障碍是什么？**
   → 三大障碍：(a) 地址流交织——多 warp 同 PC 的访问混合破坏 pattern detection；(b) 硬件预算——per-warp 状态表不可行；(c) L1 容量小导致预取数据被提前驱逐（Spare Register 方案的寄存器存储可解决）。

3. **Software prefetch 是否需要作为 baseline？**
   → 建议是。Magellan (ISCA'25) / SW Prefetch (CGO'17) 代表了编译器方案的能力上界，与之对比可展示硬件方案在 GPU 上的优势（无需重编译、可动态适应）。

---

## G. 文件夹实际内容

```
02_related_work/
├── gpu_prefetcher_impl_provenance.md   # GPU 实现来源 / baseline provenance 调研
├── cpu/                    # CPU IMA prefetch 论文 PDF（8 篇）
│   ├── IMP (MICRO'15)
│   ├── DMP (HPCA'24)
│   ├── Magellan (ISCA'25)
│   ├── Tyche (TACO'24)
│   ├── ISB / Linearizing (MICRO'13)
│   ├── Prefetch Arrays (HPCA'00)
│   ├── SW Prefetch (CGO'17)
│   └── ATP / Informed Prefetching (TACO'20)
├── gpu/                    # GPU prefetch 论文 PDF（9 篇）
│   ├── DSAP (IEEE Access'18)
│   ├── CAPS (IPDPS'18)
│   ├── Spare Register (HPCA'14)
│   ├── MT-Prefetch (MICRO'10)
│   ├── Snake (MICRO'23)
│   ├── Stream Prefetcher (J.Supercomp'18)
│   ├── Rethinking (~2014)
│   ├── WASP (IEEE TC'18)
│   └── COMPASS (ASPLOS'10)
└── (本文件 02_related_work.md 即为综合分析文档)
```
