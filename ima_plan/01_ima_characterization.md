# 01 — IMA 特征化与分类

> 对应文件夹：`01_ima_characterization/`（存放 trace 数据、分析脚本、分类图表等）
>
> 状态：**进行中**（runtime SASS 基线已切换；`l1_miss_breakdown` 已按新基线重跑）

---

## 目标

建立一个**多层次的 IMA 分类体系**，从源码模式到 SASS 指令行为到微架构 cache/stall 特征，为后续 prefetcher 设计提供"需要解决什么问题"的明确定义。

---

## 分析框架：以 Prefetcher 可观测性为中心

### 核心原则

本文档的分析视角不是"IMA 长什么样"（描述性），而是 **"硬件 prefetcher 在 pipeline 各阶段能观测到哪些信号、能据此做出什么预取决策"**（规定性）。每一项 IMA 特征的价值，取决于它能否被 prefetcher 在正确的时间点观测到并转化为预取地址。

### Prefetcher 信息可观测层次

硬件 prefetcher 能获取的信息，按 pipeline 阶段分为三层：

| 层次 | 时机 | **可观测信号** | 示例 |
|------|------|-----------|------|
| **S1: 静态/Decode-time** | 指令解码时 | PC, opcode, 寄存器编号, 立即数, constant bank 引用 | `IMAD.WIDE Rd, Rsrc, R16, c[0x0][0x180]` 中的 scale=R16, base=c[0x0][0x180] |
| **S2: 动态/Execution-time** | 指令执行时 | 寄存器值, 分支结果, 循环状态(回边/计数) | index load 返回的实际 index 值; 循环归纳变量当前值; backward branch taken/not-taken |
| **S3: Memory-time** | 访存完成时 | 地址, hit/miss 状态, 返回数据, MSHR 占用 | Data Load 的目标地址(由 S2 的 index 值计算得出); L1 miss 触发 L2 请求 |

**关键约束**：prefetcher 在 S1 时刻能"免费"获取信息（不依赖任何运行时数据）；S2/S3 信息有延迟，prefetcher 必须在 **S2/S3 信息到达前** 就已经开始工作才有 timeliness 价值。这决定了不同 IMA pattern 的 prefetchability 本质差异：

- **Pattern I/II**：index 流地址在 S1 可预测（stride 已知），prefetcher 可提前发起 index prefetch → 拿到 index 值(S2) → 计算 data 地址 → 发起 data prefetch。Index-Data Pipeline 可行。
- **Pattern III**：data 地址依赖 f(S2 值)，f() 的输入本身需要等 load 返回。Prefetcher 只能在 S3（前序 load 数据返回后）才能开始计算，timeliness 受限。
- **Pattern IV**：每一跳的地址完全依赖上一跳的 S3 数据，prefetcher 无提前量。

### 两个新增分析维度

基于上述框架，Level 2 SASS 分析除了现有的"依赖链"和"IMA 三元组签名"外，需要补充两个维度：

#### 维度 A：循环结构特征

所有 5 个 workload 的 IMA 均发生在循环体内。这不是巧合——图算法的核心操作是遍历邻居（CSR 的 `[row_begin, row_end)` 范围），天然产生循环。循环为 prefetcher 提供了三类结构性保证：

1. **重复性保证**：同一 IMA 三元组（同一组 PC）将反复执行 → prefetcher 只需在第一次迭代检测 pattern，后续迭代直接复用
2. **trip count 可知性**：CSR 遍历的循环次数 = `row_end - row_begin`，在循环开始前已通过 `LDG row_offsets[src]` 和 `LDG row_offsets[src+1]` 获得 → prefetcher 可据此决定 prefetch 深度
3. **index 流可预测性**：循环归纳变量按固定 stride 推进（SASS 中 `IADD3 Rptr, Rptr, 0x4`），index load 的地址序列完全确定

但需区分两类循环：

| 循环类型 | 代表 | Trip count | Index 流 | Prefetch 策略 |
|---------|------|-----------|---------|-------------|
| **CSR bounded loop** | SpMV, BFS, SSSP, BC, CC hook | 已知（`row_end - row_begin`） | stride 固定，地址完全可预测 | 可计算精确的 prefetch window |
| **Convergence loop** | CC shortcut | 未知（数据依赖终止） | 无 index 流，纯 pointer chasing | 循环结构无法被利用 |

#### 维度 B：跨 IMA 链的信息复用

单个循环迭代内可能存在**多个 IMA 链共享同一 index value** 的情况。这意味着一次 index load 的返回值可以同时触发多条 prefetch：

- SpMV: 1 个 index → 1 个 data target（`Aj[offset]` → `x[]`），无复用
- BFS/SSSP: 1 个 index → 1 个 data target（`col_idx[offset]` → `dists[]`/`dist[]`），无复用
- BC forward: 1 个 index → 2 个 data target（`col_idx[offset]` → `depths[]` + `path_counts[]`）
- BC reverse: 1 个 index → 3 个 data target（`col_idx[offset]` → `depths[]` + `path_counts[]` + `deltas[]`）
- CC hook: 1 个 index → 1 个 data target，但 data 返回值又触发第 2 个 IMA 链

BC reverse 的 1→3 复用意味着 prefetcher 的 **每次 index 值获取的 ROI 是 SpMV 的 3 倍**——花同样的代价读一个 index，可以发出 3 条 data prefetch。

### 与 Prefetcher 设计的耦合方式

本文档（characterization）与 `04_prefetcher_design.md` 的关系是**双向的**：

- **正向**（Char → Design）：每项特征标注"可被 prefetcher 如何利用"，作为设计的输入信号规格
- **反向**（Design → Char）：当 prefetcher 设计需要某种信息时，回到 SASS 验证该信息是否在硬件层面可观测

后续各 Pattern 的 SASS 分析均按此框架组织：先标注 S1/S2/S3 各层的可观测信号，再分析循环结构特征和跨链复用关系。

---

## 分类层次

### Level 1：源码级 IMA 模式

从 5 个 Gardenia 算法（BFS, SSSP, BC, CC, SpMV）源码中提取 IMA 的代码模式。采用**两轴分类**：IMA 间接访问结构（源码模式）× GPU 执行模型特征。

> **范围说明**：不包含 TC（Triangle Counting），其核心瓶颈是 set intersection 搜索而非经典 IMA。

#### 轴 1：IMA 间接访问结构（4 类，按 prefetch 难度递增）

**Pattern I: Linear Gather** — `data[index[i]]`，`i` 顺序递增

- 代表：SpMV 内循环
- 源码：`gpu-app-collection/gardenia/src/spmv/base.cu:21-22`
  ```cuda
  for (int offset = row_begin; offset < row_end; offset++)
      sum += Ax[offset] * x[Aj[offset]];
  ```
- 特征：index 数组（`Aj`）按 stride-1 顺序访问；data 数组（`x`）按 `Aj` 值随机访问；**层间无数据依赖**
- 间接目标：单一数组（`x[]`）
- Prefetch 分析：可用Index-Data Pipeline（先预取 index，再用 index 值预取 data）

---

**Pattern II: Frontier-Driven Gather** — 同 Pattern I 核心循环，但 base address 来自动态 worklist

- 代表：BFS, SSSP, BC forward, BC reverse
- 源码（BFS）：`gpu-app-collection/gardenia/src/bfs/linear_base.cu:15-21`
  ```cuda
  if (in_queue.pop_id(tid, src)) {       // src 来自 worklist
      for (int offset = row_begin; offset < row_end; ++ offset) {
          int dst = column_indices[offset];
          ... dists[dst] ...
      }
  }
  ```
- 源码（SSSP）：`gpu-app-collection/gardenia/src/sssp/linear_base.cu:36-43`
  ```cuda
  int dst = column_indices[offset];
  DistT old_dist = dist[dst];
  DistT new_dist = dist[src] + weight[offset];
  if (new_dist < old_dist) atomicMin(&dist[dst], new_dist);
  ```
- 源码（BC forward）：`gpu-app-collection/gardenia/src/bc/linear_base.cu:52-57`
  ```cuda
  int dst = column_indices[offset];
  if ((depths[dst] == -1) && (atomicCAS(&depths[dst], -1, depth) == -1))
      ...
  atomicAdd(&path_counts[dst], path_counts[src]);
  ```
- 源码（BC reverse）：`gpu-app-collection/gardenia/src/bc/linear_base.cu:72-80`
  ```cuda
  int src = frontiers[tid];              // 额外一层间接：frontiers → src
  ...
  int dst = column_indices[offset];
  if (depths[dst] == depth + 1)
      delta_src += path_counts[src] / path_counts[dst] * (1 + deltas[dst]);
  ```
- 特征：内循环与 Pattern I 相同；**关键差异是 src 来自 worklist，不可预测**
- 子类型：
  - **II-a 单目标**：BFS（`dists[dst]`）、SSSP（`dist[dst]`）
  - **II-b 多目标**：BC forward（`depths[dst]` + `path_counts[dst]`），BC reverse（`depths[dst]` + `path_counts[dst]` + `deltas[dst]`）
  - BC reverse 还多了一层 `frontiers[tid] → src` 的间接，使总间接层数达到 3 层

---

**Pattern III: Data-Dependent Indirection** — `A[f(val₁, val₂, ...)]`，下一次访问的地址由先前 load 返回值经 `f()` 计算得出

- 核心特征：`addr_next = f(loaded_values)`。关键在于存在 **load → compute(f) → load 的串行依赖**，而非间接跳转的层数本身。`f()` 可以是比较、算术或任意计算——只要它消费了前序 load 的返回值来生成新地址，就属于此模式。
- 代表：CC hook kernel 中的 `comp[high_comp]` 访问
- 源码：`gpu-app-collection/gardenia/src/cc/base.cu:13-25`
  ```cuda
  int comp_src = comp[src];
  int comp_dst = __ldg(comp+dst);        // 先加载两个值
  int high_comp = comp_src > comp_dst ? comp_src : comp_dst;  // f() = max()
  if (high_comp == comp[high_comp]) {    // 地址依赖 f() 的结果！
      comp[high_comp] = low_comp;
  }
  ```
- 特征：`comp[high_comp]` 的地址来自 `f(comp[src], comp[dst])` 的运行时计算结果；**必须等前序 load 返回并完成 f() 计算后才能发出此 load**
- Prefetch 分析：prefetcher 无法在 f() 的输入 load 完成前预测后续地址，提前量受限于 load latency + f() 计算延迟

---

**Pattern IV: Pointer Chasing** — `A[A[A[...A[i]...]]]`，无限深度串行依赖

- 代表：CC shortcut kernel
- 源码：`gpu-app-collection/gardenia/src/cc/base.cu:34-35`
  ```cuda
  while (comp[src] != comp[comp[src]]) {
      comp[src] = comp[comp[src]];
  }
  ```
- 特征：每一跳的地址完全由上一跳返回的值决定；循环深度未知；**MLP ≈ 0**
- Prefetch 分析：传统 stride/stream prefetcher 无效，需推测性方法

#### 模式组合

实际 kernel 通常是多种 Pattern 的**组合**，而非单一模式。以 **CC hook** 为例：

1. **外层 — Pattern I (Linear Gather)**：CSR 邻居遍历，`column_indices[offset]` stride-1 顺序访问 → `comp[dst]` 间接读
2. **内层 — Pattern III (Data-Dependent)**：`comp[high_comp]` 的地址来自 `f(comp[src], comp[dst])` 的运行时计算

因此 CC hook 的完整访问模式是 **I + III** 的组合。类似地：

- **BC reverse** = Pattern II（Frontier-Driven Gather）+ 额外的 `frontiers[tid] → src` 间接层
- 更复杂的算法可能出现 II + III、I + IV 等组合

综合矩阵中的 **IMA Pattern** 标注 kernel 中 **prefetch 最困难的模式**（决定性能瓶颈），但同时注明组合关系。

#### 轴 2：GPU 执行模型特征（G1 / G2）

IMA 的 prefetch 收益不仅取决于间接访问结构本身，还取决于 GPU 执行模型如何将 vertex 分配给 thread：

| GPU Context | 说明 | 对 Prefetch 的影响 | 代表 |
|------------|------|------------------|------|
| **G1: TID-Indexed** | `src = tid`，相邻 thread 处理相邻 vertex | `row_offsets[src]` 访问 coalesced；warp 内首跳有 spatial locality | SpMV, CC |
| **G2: Worklist-Driven** | `src` 来自 worklist/frontier | 相邻 thread 的 src 分散，所有跳都高分散；warp 内 cache line 复用率低 | BFS, SSSP, BC |

- **G1** 下，`row_offsets[src]` 和 `row_offsets[src+1]` 在 warp 内天然 coalesced（相邻 thread 的 src 连续），首跳的 spatial locality 可以被 L1 cache 自然捕获。Prefetcher 主要需解决第二跳（`data[index[i]]`）的随机性。
- **G2** 下，worklist 中相邻位置的 src 通常来自图的不同区域，导致 `row_offsets[src]` 本身就已分散。Prefetcher 需要同时应对首跳和后续跳的随机性，收益上限更低。

#### 分类综合矩阵

| Workload (Kernel) | IMA Pattern | GPU Context | 间接层数 | 间接目标数 | Index 流模式 | Prefetch 难度 |
|-------------------|------------|------------|---------|-----------|-------------|--------------|
| SpMV | I (Linear Gather) | G1 (TID) | 2 | 1（`x[]`） | stride-1 顺序 | 最易 |
| BFS | II-a (Frontier Gather) | G2 (Worklist) | 2 | 1（`dists[]`） | 随机（worklist） | 中 |
| SSSP | II-a (Frontier Gather) | G2 (Worklist) | 2 | 1（`dist[]`） | 随机（worklist） | 中 |
| BC forward | II-b (Frontier Gather, multi) | G2 (Worklist) | 2 | 2（`depths[]` + `path_counts[]`） | 随机（worklist） | 中 |
| BC reverse | II-b (Frontier Gather, multi, +1层) | G2 (Worklist) | 3 | 3（`depths[]` + `path_counts[]` + `deltas[]`） | 随机（worklist） | 中偏高 |
| CC hook | I + III (Linear Gather + Data-Dependent) | G1 (TID) | 2 + f() | 1（`comp[]`） | stride-1 首跳 → f() 依赖 | 高 |
| CC shortcut | IV (Pointer Chasing) | G1 (TID) | ∞ | 1（`comp[]`） | 纯数据依赖 | 极高 |

**待完成**：
- [ ] 对每种 Pattern 标注间接层数与层间数据依赖关系（✅ 已在上表完成初步标注）
- [ ] 标注间接目标数组数量（✅ 已在上表完成）
- [ ] 标注 index 流的访问模式（stride-1 顺序 vs 随机）（✅ 已在上表完成）
- [ ] 标注 GPU 执行上下文（G1 TID-Indexed / G2 Worklist-Driven）（✅ 已在上表完成）
- [ ] 对每种模式给出 prefetch Index-Data Pipeline 的可行性判断（需结合 Level 2/3 数据细化）

### Level 2：SASS 指令级行为（面向 Prefetcher 设计）

> SASS 源码路径：`ima_plan/01_ima_characterization/sass_analysis/`
> SM 架构：SM80 (A100)，使用 `nvdisasm --print-code --print-line-info --separate-functions` 生成

#### SASS 基线说明（2026-03 更新）

Level 2 以及后续 `l1_miss_breakdown` 的 canonical SASS 不再来自离线
`cubin -> nvdisasm`。新的基线改为：

1. 用带 runtime dump 能力的 NVBit tracer 运行目标 binary
2. 在 trace header 中读取 `runtime cubin` 与 `runtime static map`
3. 对 runtime cubin 执行：

```bash
nvdisasm --print-code --print-line-info --separate-functions <runtime.cubin> > <runtime.cubin.sass>
```

4. 将 runtime `.cubin.sass` 复制或合并到
   `sass_analysis/*.sm80.sass`

原因是：L1/raw trace 的 PC offset 已确认与 NVBit 运行时看到的 code
object 一致，而旧的离线 cubin SASS 会把同一个 PC 映射到不同指令。对照
证据统一放在 `analyze/l1trace_mismatch/*_runtime_sm80/`。

当前 5 个 runtime SASS 文件的来源如下：

- `bfs` / `sssp` / `spmv`：来自代表性 `ima_high` runtime trace
- `bc` / `cc`：来自 tiny MatrixMarket graph 的 runtime trace，用于快速触发
  主 kernel；该做法成立，因为 runtime code object 取决于 executable，
  不取决于图规模

本节从硬件视角分析 IMA 的指令级特征——因为**硬件 prefetcher 能观测到的信息只有 SASS 指令流（PC、opcode、操作数）和内存访问流（地址、数据）**。分析思路参考 CPU IMA prefetcher 文献（IMP [MICRO'15]、DMP [HPCA'24]、Tyche [TACO'24]），提取 GPU 上等价的检测信号。

#### 核心观察：IMAD.WIDE 是主流 gather 型 IMA 的核心地址生成指令

核心 5 个 workload 的目标 IMA 主链都遵循同一个 SASS 模式；broader analysis 中新增的
`PR / VC` 也延续了这一结构。因此，对图 workload 中**绝大部分主流 gather 型 IMA**，
`LDG -> IMAD.WIDE -> LDG` 仍然是最重要的检测签名：

```
LDG.E    Rindex, [Rbase_idx.64 + offset]        // ① Index Load：加载索引值
IMAD.WIDE Raddr, Rindex, Rscale, c[0x0][0x1xx]  // ② 地址计算：addr = index × size + base_ptr
LDG.E    Rdata,  [Raddr.64]                      // ③ Data Load：间接访问目标数组
```

关键特征：
- `IMAD.WIDE`（Integer Multiply-Add, Wide result）将 32-bit 索引乘以元素大小再加上 64-bit 基地址，产生 64-bit 目标地址
- `Rscale` 是编译期常量：`int` → 0x4, `float` → 0x4, `double`/`uint64_t` → 0x8
- 基地址 `c[0x0][0x1xx]` 来自 **constant memory**（kernel 参数），在整个 kernel launch 期间不变
- 对核心 5 个测例以及 broader analysis 中的 `PR / VC` 而言，这个 `LDG → IMAD.WIDE → LDG` 三元组是 detector 的**主检测签名**，等价于 CPU 上 IMP/DMP 检测的 `Base + Index × Size` 模式

#### 适用范围与少量反例

前面的 5 个核心测例验证了：对 BFS、SSSP、SpMV、BC，以及 CC 的 hook 主链，
`IMAD.WIDE` 都能把 `base` 和 `scale` 结构化暴露出来。更进一步的 broader analysis
表明，这个结论并不只停留在核心样本上：`PR` 与 `VC` 在 `sm70 / sm80 / sm90`
上也基本保留了相同的 fast path。

但这并不意味着“所有 IMA 都必然经过单条 `IMAD.WIDE`”。目前已经确认的少量个例是
`SCC bfs_step` 这类 mixed-width 复合谓词：

- 源码条件同时访问 `mark[dst]`、`visited[dst]`、`colors[dst]`
- 其中 `mark/visited` 是 byte 访问，`colors` 是 word 访问
- 编译器会倾向于把 `colors[dst]` 的地址生成 lowering 成
  `LEA / LEA.HI.X / IADD3 + LDG`
- 因而语义上仍然是 IMA，但不再严格匹配单条 `IMAD.WIDE` 的模板

这意味着本文的 detect 方法可以合理宣称“覆盖绝大部分图 IMA 的主路径”，但不应再把
`IMAD.WIDE` 写成无例外的充分必要条件。更准确的表述应是：

> 当前 detector 针对绝大部分图 workload 中的主流 IMA fast path，也就是
> `LDG -> IMAD.WIDE -> LDG` 主链；确有少量 mixed-predicate 个例不满足这一严格模板，
> 后续可通过把检查标扩展为更一般的寄存器依赖跟踪，覆盖 `LEA / LEA.HI.X / IADD3`
> 参与的地址生成链。

换句话说，后续增强方向不是放弃当前 detect 方法，而是把“检查标”从只盯
`IMAD.WIDE` 的单点规则，升级为对同一 index load 派生出的 predicate / address
计算链做统一的寄存器依赖跟踪。这样既保留现有 fast path 的低成本优势，也能把
`SCC bfs_step` 这类少量反例纳入覆盖范围。

#### 各 Pattern 的 SASS 依赖链分析

##### Pattern I: Linear Gather — SpMV

源码: `spmv_base.sm80.sass`，kernel `spmv_csr_scalar`

**简单循环体** (`.L_x_4`，unroll × 1)：

```asm
/*0200*/  LDG.E R5, [R6.64]                      // ① Aj[offset]  — Index Load (stride-4)
/*0210*/  MOV R6, R10
/*0230*/  LDG.E R9, [R6.64]                      // Ax[offset]    — 值流 (stride-4, 非 IMA)
/*0240*/  IMAD.WIDE R4, R5, R16, c[0x0][0x180]   // ② addr = Aj[offset] × 4 + base_x
/*0250*/  LDG.E R4, [R4.64]                      // ③ x[Aj[offset]] — Data Load (irregular)
         ...
/*0280*/  IADD3 R12, P2, R12, 0x4, RZ            // Aj ptr += 4 (stride-4 递增)
/*02d0*/  FFMA R11, R4, R9, R11                   // sum += x[Aj[offset]] × Ax[offset]
```

**依赖链**：`LDG(0x200) → [等待 R5 返回] → IMAD.WIDE(0x240) → LDG(0x250)` — **3 条指令，链长 = 1 load latency + 1 ALU**

编译器优化：
- 主循环展开 **16×** (`.L_x_7`)，将 16 个 `LDG.E Aj` 批量发射，然后穿插 `IMAD.WIDE` + `LDG.E x[]`
- 这实际上是编译器实现的**软件 prefetch pipeline**：当前批次的 Data Load 等待返回时，下一批 Index Load 已经发出
- Prefetcher 视角：编译器已部分解决了 MLP 问题，但如果 unroll 不够深（如 x1 循环），prefetcher 仍有价值

##### Pattern II: Frontier-Driven Gather — BFS / SSSP

源码: `bfs_linear_base.sm80.sass`，kernel `bfs_kernel`

**Worklist 间接层**（循环外，一次性）：

```asm
/*00a0*/  IMAD.WIDE R2, R0, R24, c[0x0][0x180]   // addr = tid × 4 + worklist_base
/*00c0*/  LDG.E R2, [R2.64]                       // ⓪ src = worklist[tid] (G2: 随机值)
/*00e0*/  IMAD.WIDE R4, R2, R5, c[0x0][0x168]     // addr = src × 8 + row_offsets_base
/*00f0*/  LDG.E R17, [R4.64]                      // row_begin = row_offsets[src]
/*0100*/  LDG.E R22, [R4.64+0x8]                  // row_end = row_offsets[src+1]
```

**内循环** (`.L_x_20`，unroll × 4)：

```asm
/*0650*/  LDG.E R0, [R16.64]                      // ① column_indices[offset] — Index Load (stride-4)
/*0660*/  IMAD.MOV.U32 R11, RZ, RZ, 0x4           // R11 = 4 (sizeof int)
/*0670*/  IMAD.WIDE R2, R0, R11, c[0x0][0x178]    // ② addr = dst × 4 + dists_base
/*0680*/  LDG.E R4, [R2.64]                       // ③ dists[dst] — Data Load (irregular)
         ...
/*06b0*/  ISETP.NE.AND P0, PT, R4, 0x3b9aca00, PT // if (dists[dst] == INFINITY)
/*0700*/  ATOMG.E.CAS.STRONG.GPU PT, R2, [R2], R6, R7  // atomicCAS(&dists[dst], ...)
```

**依赖链**：与 Pattern I 完全相同的 3 条指令内循环链。关键差异在循环外：`LDG worklist → LDG row_offsets` 增加了 2 次串行 load。

SSSP (`bellman_ford` kernel) 结构几乎一致，仅多了 `LDG weight[offset]`（stride-4 顺序，不影响 IMA 链）和 `ATOMG.E.MIN` 替代 `ATOMG.E.CAS`。

##### Pattern I + III: Linear Gather + Data-Dependent — CC hook

源码: `cc_base.sm80.sass`，kernel `hook`

**内循环** (`.L_x_15`，unroll × 4)：

```asm
// —— Pattern I 部分：Linear Gather ——
/*0390*/  LDG.E R9, [R4.64]                       // ① column_indices[offset] — Index Load (stride-4)
/*03b0*/  IMAD.WIDE R8, R9, R6, c[0x0][0x178]     // ② addr = dst × 4 + comp_base
/*03c0*/  LDG.E.CONSTANT R13, [R8.64]             // ③ comp[dst] — Data Load (__ldg → 只读缓存)

// —— 等待 R13 返回（串行依赖屏障） ——

// —— Pattern III 部分：Data-Dependent f() ——
/*0400*/  IMNMX R7, R2, R13, !PT                  // ④ f() = max(comp_src, comp_dst)
/*0410*/  IMAD.WIDE R8, R7, R6, c[0x0][0x178]     // ⑤ addr = high_comp × 4 + comp_base
/*0420*/  LDG.E R10, [R8.64]                      // ⑥ comp[high_comp] — Dependent Load

// —— 条件写 ——
/*0440*/  ISETP.NE.AND P0, PT, R7, R10, PT        // if (high_comp == comp[high_comp])
/*0490*/ @!P0 STG.E [R8.64], R7                   // comp[high_comp] = low_comp
```

**依赖链**：`LDG(0x390) → IMAD.WIDE(0x3b0) → LDG.CONSTANT(0x3c0) → [等 R13] → IMNMX(0x400) → IMAD.WIDE(0x410) → LDG(0x420)` — **6 条指令，链长 = 2 load latency + 3 ALU**

关键 SASS 特征：
- `LDG.E.CONSTANT`：使用 `__ldg()` 走只读缓存路径，命中率可能较高（`comp[]` 是被多线程读的共享数据）
- `IMNMX`：整数 min/max 指令，1 cycle ALU，是 f() 的具体实现
- 前半（①②③）的地址可预测（stride-4 index stream），后半（④⑤⑥）不可预测（依赖 ③ 的返回值）
- Prefetcher 视角：可以用 IMP/DMP 方法预取前半链的 `comp[dst]`，但后半链的 `comp[high_comp]` 需要 Tyche 式的依赖链回放

##### Pattern IV: Pointer Chasing — CC shortcut

源码: `cc_base.sm80.sass`，kernel `shortcut`

**主循环** (`.L_x_0`)：

```asm
/*00f0*/  IMAD.WIDE R4, R7, R9, c[0x0][0x168]     // addr = value × 4 + comp_base
/*0100*/  STG.E [R2.64], R7                        // comp[src] = value (写回)
/*0110*/  LDG.E R4, [R4.64]                        // comp[value] — 下一跳 Load
/*0120*/  ISETP.NE.AND P0, PT, R7, R4, PT          // while (value != comp[value])
/*0130*/  MOV R7, R4                               // value = loaded result
/*0140*/ @P0 BRA .L_x_0                            // 继续
```

**依赖链**：`LDG(0x110) → MOV(0x130) → IMAD.WIDE(0x0f0) → LDG(0x110) → ...` — **每跳 = 1 load latency + 2 ALU，无限循环**

关键 SASS 特征：
- 整个循环体仅 6 条指令（含分支），极度 tight
- `STG.E` 和 `LDG.E` 地址来自同一个 `comp[]` 数组（读写同一数组）
- 每条 load 的地址完全由上一条 load 的返回值决定，**warp 内 MLP = 0**
- Prefetcher 视角：stride/stream 完全无效。唯一可能的策略是**跨 warp/跨迭代的统计预测**

#### SASS 级特征综合表

| Pattern | 代表 Kernel | 依赖链指令数 | Load 次数 | 关键地址生成指令 | 链内 f() | 编译器 Unroll |
|---------|------------|------------|----------|----------------|----------|-------------|
| I | SpMV `spmv_csr_scalar` | 3 | 2 (index+data) | `IMAD.WIDE` | 无 | 16× |
| II-a | BFS `bfs_kernel` | 3 (+ worklist 2) | 2 (+1 worklist) | `IMAD.WIDE` | 无 | 4× |
| II-a | SSSP `bellman_ford` | 3 (+ worklist 2) | 2 (+1 worklist +1 weight) | `IMAD.WIDE` | 无 | 4× |
| I+III | CC `hook` | 6 | 3 | `IMAD.WIDE` × 2 | `IMNMX` (max) | 4× |
| IV | CC `shortcut` | 4 (循环) | 1 per hop | `IMAD.WIDE` | 无 (恒等) | 1× |

#### GPU 特有的硬件可观测信号

与 CPU 相比，GPU 的 SASS 指令流为 prefetcher 提供了一些**额外优势**和**独特挑战**：

**优势**：

1. **IMAD.WIDE 使 IMA 关系显式化**：CPU 上 IMP/DMP 需要从地址差值反推 `shift` 和 `base_addr`；GPU 上 `IMAD.WIDE Rd, Rindex, Rscale, Cbase` 直接暴露了 `scale`（操作数 2）和 `base`（constant memory 操作数），无需推断。
2. **Constant memory 提供稳定的 base address**：所有 IMA 的基地址（`c[0x0][0x1xx]`）在整个 kernel launch 期间不变，prefetcher 只需在 kernel 启动时读一次。
3. **同 PC 指令跨 warp 执行**：GPU 的 SIMT 模型保证同一 PC 被大量 warp 执行，提供丰富的训练样本。CPU 上 DMP 需要 64 个 miss 采样窗口来确认模式；GPU 上仅需观察少量 warp 即可确认。
4. **YIELD 指令作为 stall 预告**：BFS/SSSP 内循环中出现 `YIELD`（如 BFS `0x0690`），表示编译器预期接下来会有长延迟 load。Prefetcher 可将此作为触发信号。

**挑战**：

1. **Warp 内地址分散度**：同一 `LDG.E` 指令的 32 个 lane 可能访问 32 个不同的 cache line（尤其在 G2 Worklist-Driven 模式下）。Prefetcher 需要为每个 lane 独立计算目标地址。
2. **循环展开模糊了 PC**：编译器将 4-16 次迭代展开为不同 PC 的 load 指令（如 BFS 的 `0x0650, 0x09c0, 0x0d20, 0x1080`），虽然它们在源码中是同一条 load。Prefetcher 需要识别这些不同 PC 属于同一个 IMA 模式。
3. **`LDG.E.CONSTANT` 走不同缓存路径**：CC hook 的 `comp[dst]` 通过 `__ldg()` 走只读缓存（L1 texture cache），与普通 `LDG.E` 的 L1 data cache 路径不同。Prefetcher 需要知道该向哪个缓存发出预取。

#### 对 CPU IMA Prefetcher 方法的 GPU 适配分析

| 方法 | 核心机制 | GPU 适配可行性 | 能覆盖的 Pattern |
|------|---------|--------------|----------------|
| **IMP** | 检测 stride 的 index 流 → 读取前方 index → 计算 `Base + Index × Size` | ✅ 高。IMAD.WIDE 使 Base/Size 显式可见，无需试探 shift。GPU 大量 warp 提供充足训练。 | I, II (内循环) |
| **DMP** | 差分匹配 index value 和 target addr 序列 | ⚠️ 中等。GPU 上 IMAD.WIDE 已使关系显式化，差分匹配的必要性降低。但 DMP 的 Range Filter 对 BC reverse 的多目标访问可能有用。 | I, II |
| **Tyche** | 记录 `LDG → ALU → ... → LDG` 依赖链，硬件回放 | ✅✅ 最佳匹配。GPU 的 IMA 链短（3-6 条指令）、操作种类少（`IMAD.WIDE`, `IMNMX`），硬件回放代价低。**唯一能覆盖 Pattern III 的方法**。 | I, II, III |
| **无** (传统 stride/stream) | 检测地址 stride | ❌ 仅对 index 流有效，对 data 流（irregular addresses）完全无效 | 仅 index 流 |

**Pattern IV (Pointer Chasing) 的特殊性**：以上三种方法均无法有效覆盖——因为下一跳地址完全依赖当前 load 返回值，没有可利用的提前量。可能的 GPU 特有策略：
- **跨 warp 预取**：若多个 warp 处理相邻 vertex，它们的 pointer chasing 路径可能有重叠（收敛到相同的 component root）
- **Value prediction**：推测性预测 `comp[value]` 的返回值（如 "不变" 预测——若 `comp[x] == x` 则链终止）

**待完成**：
- [ ] 记录各 kernel 关键 IMA load 的 PC 地址，与 issue trace 中的 stall PC 对应验证
- [ ] 量化循环展开对 PC 多样性的影响（✅ 详见 `01_ima_characterization/loop_unrolling_and_prefetch.md`）
- [ ] 分析 `LDG.E.CONSTANT` vs `LDG.E` 在 L1 miss rate 上的差异
- [ ] 确定 prefetcher 如何处理循环展开产生的多 PC 问题（三种思路见 loop_unrolling_and_prefetch.md §3.3）

### Level 3：微架构级行为特征

通过 L1/L2 trace + issue trace 量化 IMA 的微架构影响。

**需要收集的指标**：

| 指标 | 来源 | 意义 |
|------|------|------|
| L1 miss rate（IMA load vs 全局） | L1 trace | IMA 导致多少额外 miss |
| 同一 warp 的 IMA load 地址分散度 | L1 trace (per-lane) | coalescing 失败程度 |
| L2 miss rate | L2 trace | 工作集是否超出 L2 |
| MEM_WAIT stall 占比 | issue trace | 内存延迟在关键路径上的影响 |
| IMA load 的 miss latency 分布 | L1/L2 trace | 延迟特征 |
| 地址流的可预测性（stride / delta pattern） | L1 trace 地址序列 | prefetcher 有多大空间 |

#### 已完成：ima_high baseline L1 miss 分类统计

产物目录：`ima_plan/01_ima_characterization/l1_miss_breakdown/`

- 分析说明：`l1_miss_breakdown/analysis.md`
- 汇总数据：`l1_miss_breakdown/data/per_workload_class_summary.csv`
- 图表：`l1_miss_breakdown/figures/ima_high_baseline_l1_miss_share.svg`

当前统计只覆盖 **baseline 的 ima_high workload**，分类口径为：

- `regular`
- `stride`
- `ima`

注意：该统计只纳入 **主 kernel 的真实 `LDG*` 指令**。若某条 L1 trace 记录到的 `pc` 无法映射到这些真实 load PC，则会被排除在主图/主表之外，并在 coverage 中单独汇报。

关键结论（按 covered main-kernel miss_share 汇总）：

| Workload | regular | stride | ima | covered access | covered miss |
|----------|---------|--------|-----|----------------|--------------|
| bfs_ima_high | 15.7% | 5.0% | **79.3%** | 100.0% | 100.0% |
| sssp_ima_high | 40.0% | 9.0% | **51.1%** | 100.0% | 100.0% |
| bc_ima_high | 21.8% | 7.7% | **70.5%** | 92.9% | 92.2% |
| cc_ima_high | 5.1% | 11.3% | **83.6%** | 100.0% | 100.0% |
| spmv_ima_high | 7.9% | 25.2% | **66.9%** | 100.0% | 100.0% |

说明：

- `pc_classification.csv` 现在只包含真实 `LDG*` 指令，不再混入 `IMAD/MOV`。
- `coverage_summary.csv` 记录“全部 GLOBAL LD 中，真正落到主 kernel 真实 load PC 的访问/缺失比例”。
- runtime SASS 切换后，BFS 的 covered ratio 从旧基线下的约一半恢复到 100%，说明先前的大量 “uncovered” 主要来自错误的离线 SASS 对照基线，而不是 L1 trace 本身缺少真实 load PC。

#### 已有观测：L1 / L2 命中率不对称

已完成的 ima_high baseline 实验（SM80_A100）揭示了一个关键微架构现象：

| Workload | L1 Miss Rate | L2 Miss Rate | 说明 |
|----------|-------------|-------------|------|
| bfs_ima_high | 77.22% | 21.89% | L1 miss → L2 hit 为主 |
| sssp_ima_high | 76.66% | 25.87% | 同上 |
| bc_ima_high | 70.25% | 33.84% | 同上，BC 因多目标数组 L2 miss 略高 |

**解读**：

- IMA 的地址分散度超出了 L1D 的容量覆盖范围，但 IMA 目标数组（`dists[]`、`dist[]`、`comp[]` 等）的总工作集仍在 L2 cache 可承载范围内。
- 换言之，**IMA 在 per-SM 尺度上是高度随机的，但在全局尺度上仍有空间局部性**。这与 CPU 上 IMA 通常导致 LLC miss 的情况不同——GPU 的大容量 L2（如 A100 的 40 MB）可以兜底。
- **对 prefetcher 设计的指导**：prefetcher 的核心目标应是 **L2 → L1 的数据搬运**，而非 HBM → L2 的预取。这简化了设计（不需要考虑 DRAM 预取时序），但也意味着 prefetch 的延迟预算较短（L2 访问延迟 vs DRAM 延迟）。

数据来源：`result/log/{workload}.log` 中的 cache miss rate 统计。

**待完成**：
- [ ] 对 `bfs_ima_high`, `spmv_ima_high`, `cc` 各跑一次带 L1+L2+issue trace 的实验
- [ ] 编写分析脚本，提取上述指标
- [ ] 可视化地址分散度（scatter plot of addresses per warp per cycle）
- [ ] 补充 cc_ima_high 和 spmv_ima_high 的 L1/L2 miss rate 数据

---

## 预期产出

1. **IMA 分类表**：综合三个层次，对每种 IMA 模式给出完整画像
2. **各 workload 的 IMA 行为量化数据**（存放在 `01_ima_characterization/` 中）
3. **"哪些 IMA 模式是可预取的"初步判断**：为 Phase 3 prefetcher 设计提供输入
4. **现代推荐 / Embedding 补充线**：见 [`recsys_embedding_ima.md`](01_ima_characterization/recsys_embedding_ima.md)

---

## 文件夹内容规划

```
01_ima_characterization/
├── sass_analysis/          # runtime cubin 转译后的 canonical SASS
├── l1_miss_breakdown/      # ima_high baseline L1 miss 分类统计（脚本/CSV/图表/分析）
├── recsys_embedding_ima.md # 现代推荐 / embedding IMA 专题
├── trace_data/             # L1/L2 trace 分析的中间数据（汇总后的 CSV 等，非原始 trace）
├── scripts/                # 分析脚本
├── figures/                # 分类图、地址分散度可视化等
└── notes.md                # 分析过程笔记
```

---

## 关键问题（待讨论）

1. IMA 分类的"粒度"应该多细？论文中需要几种分类就够了？
2. 是否需要对同一算法、不同图规模的 IMA 行为做对比？（如 `bfs_ima_high` vs `bfs_ima_small`）
3. 地址可预测性分析用什么度量？（autocorrelation? delta entropy?）
4. 现代推荐 / embedding 线里，是否需要把 `inference` 和 `training` 分成两条独立子线？
