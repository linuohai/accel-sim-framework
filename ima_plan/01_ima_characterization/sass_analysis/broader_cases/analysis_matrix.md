# Gardenia 更广泛 SASS 分析

## 一句话结论

这轮 `algorithm × sm_xx` 扩展分析的结论是：你的前提假设

`A[B[i]] -> LDG(index) -> IMAD.WIDE(base+scale) -> LDG(data)`

在 Gardenia 里是“主流模式”，但不是“无条件普遍模式”。

- `PR` 和 `VC` 在 `sm70 / sm80 / sm90` 上基本都符合这个结构。
- `SCC` 是主要反例来源，尤其是 `bfs_step`；它的 IMA 语义仍然存在，但编译器常把目标地址生成拆成 `LEA / LEA.HI.X / IADD3 + LDG`，而不是单条 `IMAD.WIDE`。
- `PR` 里出现的 `LDG.E.CONSTANT` 不是反例，它只是 `__ldg()` 触发的只读缓存路径变体。

## 结果文件说明

本目录下的结果文件含义如下。

- `analysis_matrix.md`
  - 人读版总说明。
  - 用中文总结 `PR / VC / SCC × sm70 / sm80 / sm90` 的整体判断，并解释哪些情况符合、哪些情况不符合。

- `algorithm_sm_summary.csv`
  - 按 `algorithm, sm` 聚合后的总表。
  - 最适合先看全局分布，比如某个算法在某个架构上有多少 `exact_chain`、多少 `chain_with_preamble`、多少 `variant_non_imadwide`。
  - 当前关键结论是：
    - `pr`: 三个架构上都没有 `variant`
    - `vc`: 只有 `sm90` 出现 1 个 `variant`
    - `scc`: 三个架构上都是 `5/7` 个实例落在 `variant_non_imadwide`

- `source_sass_mapping.csv`
  - 以“源码语句”为中心的映射表。
  - 每条记录对应一个源码里的 IMA 语句，说明它在某个 kernel、某个架构上对应到了哪组 SASS 指令。
  - 适合回答“`colors[dst]` 这一句在 SASS 里到底落到了哪里”。

- `ima_chain_instances.csv`
  - 最细粒度实例表。
  - 每一行对应一个具体的 SASS 链实例，记录 `index_pc / addr_pc / data_pc`、指令 opcode、源码行号、分类标签。
  - 适合做逐条核对，也适合后续做 detector 规则扩展时回查“哪些变体被漏掉了”。

## 分类口径

本分析沿用下面三类标签。

- `exact_chain`
  - 明确出现 `LDG(index) -> IMAD.WIDE -> LDG(data)`。

- `chain_with_preamble`
  - 核心 IMA 子链仍然存在，但前面夹了额外的 load、循环展开或地址准备指令。

- `variant_non_imadwide`
  - 仍然是 IMA，但目标地址生成不是单条 `IMAD.WIDE`，而是更一般的 `LEA / LEA.HI.X / IADD3` 等组合。

## 实验矩阵结论

实验矩阵的两个维度是：

- 算法：`PR / VC / SCC`
- 架构：`sm70 / sm80 / sm90`

聚合统计如下。

| 算法 | 架构 | 总实例数 | exact | with_preamble | variant | 判断 |
|---|---:|---:|---:|---:|---:|---|
| PR | sm70 | 29 | 2 | 27 | 0 | 基本成立 |
| PR | sm80 | 29 | 2 | 27 | 0 | 基本成立 |
| PR | sm90 | 29 | 1 | 28 | 0 | 基本成立 |
| VC | sm70 | 30 | 2 | 28 | 0 | 基本成立 |
| VC | sm80 | 30 | 3 | 27 | 0 | 基本成立 |
| VC | sm90 | 31 | 3 | 27 | 1 | 基本成立，存在少量变体 |
| SCC | sm70 | 7 | 0 | 2 | 5 | 不稳健 |
| SCC | sm80 | 7 | 0 | 2 | 5 | 不稳健 |
| SCC | sm90 | 7 | 0 | 2 | 5 | 不稳健 |

对应的总体判断是：

- `PR`
  - 假设成立。
  - 变体主要来自 `__ldg()` 让最终 load 变成 `LDG.E.CONSTANT`，不是地址生成模式被破坏。

- `VC`
  - 假设基本成立。
  - `first_fit` 和大多数 `conflict_resolve` 都是标准 `column_indices[offset] -> colors[neighbor]` 链。
  - `sm90` 上有少量局部 lowering 差异，但不构成 workload 级别反例。

- `SCC`
  - 假设不稳健。
  - `trim_kernel` 仍可看到 `IMAD.WIDE -> LDG`。
  - `bfs_step` 大量出现 `LEA / LEA.HI.X / LDG` 变体，是这轮分析里最典型的反例。

## 代表性实例

| 算法 | 架构 | kernel | 源码表达式 | index_pc | addr_pc | data_pc | data opcode | 分类 |
|---|---:|---|---|---|---|---|---|---|
| PR | sm80 | `pull_step` | `outgoing_contrib[src]` | `01f0` | `0220` | `0230` | `LDG.E.CONSTANT` | exact_chain |
| VC | sm80 | `first_fit` | `colors[neighbor]` | `0a00` | `0a10` | `0a20` | `LDG.E` | exact_chain |
| VC | sm90 | `conflict_resolve` | `colors[neighbor]` | `00d0` | `0160` | `0190` | `LDG.E` | variant_non_imadwide |
| SCC | sm80 | `trim_kernel_in` | `colors[dst]` |  | `01c0` | `01d0` | `LDG.E` | chain_with_preamble |
| SCC | sm80 | `bfs_step` | `colors[dst]` | `02f0` | `03f0` | `0420` | `LDG.E` | variant_non_imadwide |

## 为什么会出现“不符合”

下面结合 CUDA 源码和对应 SASS，解释为什么有些 IMA 访问没有落成严格的

`LDG(index) -> IMAD.WIDE -> LDG(data)`。

### 1. `PR` 不是反例，它只是 `__ldg()` 路径不同

源码在 `gpu-app-collection/gardenia/src/pr/base.cu:30-35`：

```cuda
for (IndexT offset = row_begin; offset < row_end; ++ offset) {
    IndexT src = __ldg(column_indices+offset);
    incoming_total += __ldg(outgoing_contrib+src);
}
```

`sm80` 的关键 SASS 片段：

```sass
/*01f0*/ LDG.E.CONSTANT R8, [R10.64] ;
/*0220*/ IMAD.WIDE R8, R8, R12, c[0x0][0x180] ;
/*0230*/ LDG.E.CONSTANT R9, [R8.64] ;
```

解释如下。

- 第一条 `LDG.E.CONSTANT` 取的是 `src = __ldg(column_indices + offset)`。
- 第二条 `IMAD.WIDE` 用 `src` 乘以元素宽度，再加上 `outgoing_contrib` 的基址。
- 第三条 `LDG.E.CONSTANT` 取的是 `outgoing_contrib[src]`。

这里看起来和普通 `LDG.E` 不同，是因为源码显式写了 `__ldg()`，编译器选择走只读缓存路径，所以 opcode 变成了 `LDG.E.CONSTANT`。但核心依赖关系并没有变，仍然是“先取索引，再生成宽地址，再取目标数据”。因此 `PR` 应归类为“符合假设”，而不是反例。

### 2. `SCC bfs_step` 是真正的反例

源码在 `gpu-app-collection/gardenia/src/scc/base.cu:20-25`：

```cuda
for (int offset = row_begin; offset < row_end; ++ offset) {
    int dst = column_indices[offset];
    if (!mark[dst] && !visited[dst] && (colors[dst] == colors[src])) {
        *changed = true;
        visited[dst] = 1;
    }
}
```

这个源码结构的关键点不是只有 `colors[dst]` 这一条 IMA，而是同一个条件里同时混入了三种依赖：

- `mark[dst]`，字节访问
- `visited[dst]`，字节访问
- `colors[dst]`，4 字节访问

`sm80` 的关键 SASS 片段如下：

```sass
/*0530*/ IMAD.WIDE R6, R5, R6, c[0x0][0x170] ;
/*0540*/ LDG.E R4, [R6.64] ;
/*0560*/ IADD3 R8, P0, R4, c[0x0][0x180], RZ ;
/*0580*/ LDG.E.U8 R8, [R8.64] ;
/*05c0*/ IADD3 R10, P0, R4, c[0x0][0x188], RZ ;
/*05e0*/ LDG.E.U8 R8, [R10.64] ;
/*0610*/ LEA R8, P0, R4, c[0x0][0x178], 0x2 ;
/*0620*/ LEA.HI.X R9, R4, c[0x0][0x17c], R13, 0x2, P0 ;
/*0640*/ LDG.E R9, [R8.64] ;
```

这段 SASS 可以分成两段理解。

第一段：

- `/*0530*/ IMAD.WIDE ...`
- `/*0540*/ LDG.E R4, [R6.64]`

这两条对应 `dst = column_indices[offset]`。也就是说，索引数组 `column_indices` 本身仍然是标准“宽地址生成 + load”。

真正的偏离发生在第二段，也就是条件判断里的三个 `dst` 派生访问。

- `mark[dst]` 对应
  - `/*0560*/ IADD3 ... c[0x0][0x180]`
  - `/*0580*/ LDG.E.U8`
- `visited[dst]` 对应
  - `/*05c0*/ IADD3 ... c[0x0][0x188]`
  - `/*05e0*/ LDG.E.U8`
- `colors[dst]` 对应
  - `/*0610*/ LEA ... c[0x0][0x178], 0x2`
  - `/*0620*/ LEA.HI.X ...`
  - `/*0640*/ LDG.E`

之所以 `colors[dst]` 没有继续变成单条 `IMAD.WIDE`，核心原因是：

- `dst` 已经被前面的 `mark[dst]` 和 `visited[dst]` 使用过，而这两者都是 byte-addressed 数组，编译器已经在当前 basic block 里为它们展开了 64 位地址拼装。
- 到了 `colors[dst]` 时，虽然元素宽度变成 4 字节，但它仍然处于同一个复合谓词链里，编译器更倾向于继续沿用通用的地址生成方式，而不是再单独收敛回一条 `IMAD.WIDE`。
- 因而 `colors[dst]` 在语义上仍然是典型 `A[B[i]]`，但在形态上已经变成：

`LDG(dst) -> LEA / LEA.HI.X -> LDG(colors[dst])`

这正是 `variant_non_imadwide` 的含义：IMA 没消失，只是地址生成模板变了。

对 detector 的意义也很直接：

- 如果 prefetcher 只识别“中间必须出现单条 `IMAD.WIDE`”的链，就会漏掉这类复合条件里的 IMA。
- 如果希望覆盖 `SCC bfs_step` 这类代码，需要允许 `LEA / LEA.HI.X / IADD3` 作为 `IMAD.WIDE` 的替代地址生成器。

### 3. 为什么 `SCC trim_kernel` 又重新符合了假设

源码在 `gpu-app-collection/gardenia/src/scc/base.cu:42-44`：

```cuda
for (int offset = row_begin; offset < row_end; ++ offset) {
    int dst = in_column_indices[offset];
    if(!mark[dst] && colors[dst] == colors[src]) { in_degree ++; break; }
}
```

以及 `:50-52`：

```cuda
for (int offset = row_begin; offset < row_end; ++ offset) {
    int dst = out_column_indices[offset];
    if(!mark[dst] && colors[dst] == colors[src]) { out_degree ++; break; }
}
```

`sm80` 的关键 SASS 片段：

```sass
/*01c0*/ IMAD.WIDE R8, R13, R8, c[0x0][0x170] ;
/*01d0*/ LDG.E R9, [R8.64] ;
...
/*03d0*/ IMAD.WIDE R6, R11, R6, c[0x0][0x180] ;
/*03e0*/ LDG.E R7, [R6.64] ;
```

这里虽然前面也有 `mark[dst]` 的判断，但和 `bfs_step` 相比，控制流更短，条件更简单，没有同时叠加 `visited[dst]` 那样的额外 byte 访问链，也没有同一个谓词里那么密集的地址复用压力。因此编译器更容易把 `colors[dst]` 保持成标准 `IMAD.WIDE -> LDG`。

这说明问题不是 “SCC 一定不符合”，而是：

- 同样的算法里，不同源码上下文会把编译器推向不同 lowering；
- 真正决定是否保留 `IMAD.WIDE` 的，是“同一个 basic block 里地址生成是否被复合谓词和 mixed-width 访问打散”。

### 4. `VC sm90` 的少量变体为什么不影响总体判断

源码在 `gpu-app-collection/gardenia/src/vc/linear_base.cu:50-52`：

```cuda
for (int offset = row_begin; offset < row_end; offset ++) {
    int neighbor = column_indices[offset];
    if (colors[vertex] == colors[neighbor] && vertex < neighbor) {
```

`sm90` 的一段代表性 SASS：

```sass
/*00d0*/ LDG.E R0, desc[UR4][R2.64] ;
/*0160*/ LEA R2, P0, R0, UR6, 0x2 ;
/*0170*/ LEA.HI.X R3, R0, UR7, R3, 0x2, P0 ;
/*0190*/ LDG.E R14, desc[UR4][R2.64] ;
```

它和 `sm70 / sm80` 的差别在于：

- `sm70 / sm80` 更常见的是 `LDG(neighbor) -> IMAD.WIDE -> LDG(colors[neighbor])`
- `sm90` 的这一小部分实例把地址生成替换成了 `LEA / LEA.HI.X`

但 `VC` 的总体统计仍然是：

- `sm90` 一共 31 个实例
- 其中 27 个 `chain_with_preamble`
- 3 个 `exact_chain`
- 只有 1 个 `variant_non_imadwide`

所以它更像是某个局部 basic block 的架构相关 lowering 差异，而不是 `VC` 这类 IMA 代码在 `sm90` 上系统性失去 `IMAD.WIDE`。

## 对 prefetcher detector 的启示

这轮分析给出的实现启示很明确。

- 如果 detector 只覆盖 `LDG -> IMAD.WIDE -> LDG`，那么对 `PR`、大多数 `VC` 和 `SCC trim_kernel` 已经有效。
- 如果希望把 `SCC bfs_step` 这类复合谓词场景也覆盖进去，就不能把 `IMAD.WIDE` 当成唯一地址生成锚点。
- 更稳健的规则应该把下列序列都视作合法 IMA 地址生成：
  - `IMAD.WIDE`
  - `LEA + LEA.HI.X`
  - `IADD3 / IADD3.X` 组成的 64 位地址拼装
- 同时还要允许最终数据 load 的 opcode 变体，例如 `LDG.E` 和 `LDG.E.CONSTANT`。

换句话说，这次 Gardenia 扩展分析支持的不是“`IMAD.WIDE` 必然出现”，而是更宽泛的命题：

“IMA 的索引依赖链几乎总会保留下来，但地址生成的具体指令模板会受源码谓词结构、数据宽度混合和目标架构 lowering 的影响。”

## 结果回指

如果需要进一步逐条核对，可优先查看：

- `algorithm_sm_summary.csv`
  - 看各算法在不同 `sm_xx` 上的总体分布。
- `source_sass_mapping.csv`
  - 看每条源码表达式对应的代表性 `index_pc / addr_pc / data_pc`。
- `ima_chain_instances.csv`
  - 看所有展开后的具体实例。

这三份表和本文是一一对应的，不额外引入新的分类口径。  
