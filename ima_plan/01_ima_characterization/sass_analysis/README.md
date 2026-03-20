# SASS Analysis

本目录汇总 “IMA 元寄存器依赖前提” 的两组 SASS 分析材料，统一回答下面这个硬件设计前提是否成立：

`LDG_idx -> IMAD.WIDE -> LDG_data`

需要同时检查两条约束：

- `LDG_idx` 的目的寄存器，在被 `IMAD.WIDE` 消费前，不会被其他指令作为源寄存器消费。
- `IMAD.WIDE` 的目的寄存器，在被 `LDG_data` 消费前，不会被其他指令作为源寄存器消费。

## 分析口径

本目录中的“成立/反例”采用收窄后的 IMA 口径：

- 只保留真正的 `A[B[i]]` 型 IMA 元。
- `idx` 必须来自前一条 load，而不是 `thread id`、frontier/worklist 取数、row pointer 等直接地址派生。
- 已知的非 `IMAD.WIDE` 变体，例如 `SCC bfs_step` 的 `LEA / IADD3 / LEA.HI.X` 路径，不纳入这次寄存器前提检查。

## 关键结论

- 在当前已检查的 in-scope 样本中，唯一确认反例是 `cc shortcut`。
- 该反例违反的是第一条前提，而不是第二条前提。
- `PR`、`VC` 以及 canonical `BFS / SSSP / BC / SpMV / CC hook` 中纳入本口径的 IMA 元，当前未发现新的 in-scope 反例。

`cc shortcut` 的关键链如下：

```sass
/*00b0*/ LDG.E R5, [R4.64] ;
/*00c0*/ ISETP.NE.AND P0, PT, R0, R5, PT ;
/*00e0*/ MOV R7, R5 ;
/*00f0*/ IMAD.WIDE R4, R7.reuse, R9, c[0x0][0x168] ;
/*0110*/ LDG.E R4, [R4.64] ;
```

这里 `LDG_idx` 写入的 `R5` 在 `IMAD.WIDE` 之前已经被 `ISETP` 和 `MOV` 消费，因此第一条前提不成立；但 `IMAD.WIDE` 产出的地址寄存器直到最终 `LDG` 前没有额外消费者，因此第二条前提仍成立。

## 内容导读

- `core_cases/`
  - 来自原 `core_sass_analysis/` 的核心测例材料。
  - 覆盖 canonical runtime SASS：`BFS / SSSP / BC / CC / SpMV`。
  - 适合先看主 workload 上是否存在稳定、可复用的 `LDG_idx -> IMAD.WIDE -> LDG_data` 模式。

- `broader_cases/`
  - 来自原 `broader_sass_analysis/` 的扩展测例材料。
  - 覆盖 `PR / VC / SCC × sm70 / sm80 / sm90`。
  - 适合看该模式在更广 Gardenia 范围内是否普遍，以及哪些 workload 会掉到 `LEA / IADD3` 类变体。

## 说明

- 当前只是复制汇总，原 `core_sass_analysis/` 和原 `broader_sass_analysis/` 均未删除。
- 若后续确认本目录组织没有问题，再由人工决定是否清理旧目录。
