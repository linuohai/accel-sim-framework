# 循环展开（Loop Unrolling）与 Prefetcher 设计的关系

> 本文档解释 CUDA 编译器的循环展开优化在 SASS 层面产生的效果，以及它对硬件 IMA prefetcher 设计的影响。

---

## 1. 什么是循环展开？

循环展开是编译器的一种优化：将循环体**复制 N 份**到同一个循环迭代中，使每次循环执行 N 个原始迭代的工作。目的是减少分支指令开销、增加指令级并行度。

### 用 BFS 内循环举例

**源码**（`bfs/linear_base.cu:18-21`）—— 只有**一个**循环体：

```cuda
for (int offset = row_begin; offset < row_end; ++ offset) {
    int dst = column_indices[offset];       // ← 一条 index load
    if (dists[dst] == MYINFINITY) { ... }   // ← 一条 data load
}
```

程序员写了 1 条 `column_indices[offset]` 的 load 和 1 条 `dists[dst]` 的 load。

**编译后 SASS**（`bfs_linear_base.sm80.sass`）—— 编译器生成了**两个版本**的循环：

```
版本 A（简单版，×1）：处理不能被 4 整除的余数部分
    ┌─────────────────────────────────────────┐
    │  LDG column_indices[offset]   PC=0x01d0 │ ← 1 个 index load
    │  LDG dists[dst]               PC=0x0200 │ ← 1 个 data  load
    │  offset++                               │
    │  循环回到顶部                             │
    └─────────────────────────────────────────┘

版本 B（展开版，×4）：主循环体，一次处理 4 个 neighbor
    ┌─────────────────────────────────────────┐
    │  LDG column_indices[offset+0] PC=0x0650 │ ← index load #1
    │  LDG dists[dst_0]             PC=0x0680 │ ← data  load #1
    │  ... atomicCAS / out_queue.push ...     │
    │                                         │
    │  LDG column_indices[offset+1] PC=0x09c0 │ ← index load #2
    │  LDG dists[dst_1]             PC=0x09f0 │ ← data  load #2
    │  ... atomicCAS / out_queue.push ...     │
    │                                         │
    │  LDG column_indices[offset+2] PC=0x0d20 │ ← index load #3
    │  LDG dists[dst_2]             PC=0x0d50 │ ← data  load #3
    │  ... atomicCAS / out_queue.push ...     │
    │                                         │
    │  LDG column_indices[offset+3] PC=0x1080 │ ← index load #4
    │  LDG dists[dst_3]             PC=0x10b0 │ ← data  load #4
    │  ... atomicCAS / out_queue.push ...     │
    │                                         │
    │  offset += 4                            │
    │  循环回到顶部                             │
    └─────────────────────────────────────────┘
```

源码中的**同一行** `column_indices[offset]`，在 SASS 中变成了 **5 个不同 PC 地址**的 `LDG.E` 指令。

### 关键点

- 每个展开副本处理的是**逻辑上相邻的数组元素**（offset+0, offset+1, offset+2, offset+3）
- 但在 SASS 中，它们是**完全不同的指令**，拥有不同的 PC（程序计数器）地址
- 硬件看到的是 5 个"不同的" load 指令，但它们其实都在做同一件事

---

## 2. 三个算法的具体展开分析

### 2.1 BFS — 4× 展开

**SASS 文件**：`sass_analysis/bfs_linear_base.sm80.sass`，kernel `bfs_kernel`

源码中的 **1 条** `column_indices[offset]` load，在 SASS 中对应：

| 循环版本 | 展开因子 | Index Load PC (`column_indices`) | Data Load PC (`dists[dst]`) |
|---------|---------|--------------------------------|-----------------------------|
| 简单版 `.L_x_6` | ×1 | `0x01d0` | `0x0200` |
| 展开版 `.L_x_20` 第 1 份 | ×4 | `0x0650` `[R16.64]` | `0x0680` |
| 展开版 `.L_x_20` 第 2 份 | | `0x09c0` `[R16.64+0x4]` | `0x09f0` |
| 展开版 `.L_x_20` 第 3 份 | | `0x0d20` `[R16.64+0x8]` | `0x0d50` |
| 展开版 `.L_x_20` 第 4 份 | | `0x1080` `[R16.64+0xc]` | `0x10b0` |

**识别标志**：4 份展开副本的 index load 都标注源码行号 `line 19`，且基地址寄存器相同（`R16`），只有偏移不同（+0x0, +0x4, +0x8, +0xc = 0, 4, 8, 12 字节）。

完整的 IMA 依赖链（以第 1 份为例）：

```asm
/*0650*/  LDG.E R0, [R16.64]                    // ① column_indices[offset]  (PC = 0x0650)
/*0660*/  IMAD.MOV.U32 R11, RZ, RZ, 0x4         //    sizeof(int) = 4
/*0670*/  IMAD.WIDE R2, R0, R11, c[0x0][0x178]  // ② addr = dst × 4 + dists_base
/*0680*/  LDG.E R4, [R2.64]                     // ③ dists[dst]             (PC = 0x0680)
```

第 2/3/4 份完全相同的依赖链结构，只是 PC 不同。

---

### 2.2 CC hook — 4× 展开

**SASS 文件**：`sass_analysis/cc_base.sm80.sass`，kernel `hook`

CC hook 的 IMA 链更长（Pattern I + III），展开使 PC 膨胀更严重：

| 循环版本 | 展开因子 | Index Load PC (`column_indices`) | Data Load PC (`comp[dst]`) | Dependent Load PC (`comp[high_comp]`) |
|---------|---------|--------------------------------|--------------------------|-------------------------------------|
| 简单版 `.L_x_6` | ×1 | `0x01b0` | `0x01e0` (CONSTANT) | `0x0270` |
| 展开版 `.L_x_15` 第 1 份 | ×4 | `0x0390` | `0x03c0` (CONSTANT) | `0x0420` |
| 展开版 `.L_x_15` 第 2 份 | | `0x04b0` | `0x04d0` (CONSTANT) | `0x0530` |
| 展开版 `.L_x_15` 第 3 份 | | `0x05c0` | `0x05e0` (CONSTANT) | `0x0640` |
| 展开版 `.L_x_15` 第 4 份 | | `0x06d0` | `0x06f0` (CONSTANT) | `0x0750` |

展开第 1 份的完整 IMA 链（6 条指令）：

```asm
// —— Pattern I: Linear Gather ——
/*0390*/  LDG.E R9, [R4.64]                       // ① column_indices[offset]   (PC=0x0390)
/*03b0*/  IMAD.WIDE R8, R9, R6, c[0x0][0x178]     // ② addr = dst × 4 + comp_base
/*03c0*/  LDG.E.CONSTANT R13, [R8.64]             // ③ comp[dst]               (PC=0x03c0)

// —— Pattern III: Data-Dependent f() ——
/*0400*/  IMNMX R7, R2, R13, !PT                  // ④ f() = max(comp_src, comp_dst)
/*0410*/  IMAD.WIDE R8, R7, R6, c[0x0][0x178]     // ⑤ addr = high_comp × 4 + comp_base
/*0420*/  LDG.E R10, [R8.64]                      // ⑥ comp[high_comp]         (PC=0x0420)
```

**PC 膨胀**：源码中 3 种 load × 展开 5 份 = **15 个不同的 PC**（对比源码只有 3 个逻辑 load）。

---

### 2.3 SpMV — 多级展开（16×/8×/4×/1×）

**SASS 文件**：`sass_analysis/spmv_base.sm80.sass`，kernel `spmv_csr_scalar`

SpMV 的情况更极端——编译器生成了**4 个不同版本的循环**来处理不同的迭代次数：

```
迭代总数 = row_end - row_begin

如果迭代次数 ≥ 16：              → 用 ×16 版本处理（.L_x_7）
    处理完后，剩余 < 16 个：
        如果剩余 ≥ 8：          → 用 ×8 版本处理（.L_x_5）
            处理完后，剩余 < 8：
                如果剩余 ≥ 4：  → 用 ×4 版本处理（.L_x_8 尾部）
                    处理完后：  → 用 ×1 版本处理余数（.L_x_4）
如果迭代次数 < 4：              → 直接用 ×1 版本

这类似于 "Duff's device"：先用大步长处理主体，再逐级缩小处理余数。
```

**×16 展开版** (`.L_x_7`) 中，源码的**一条** `Aj[offset]` load 变成了：

```asm
// 16 个 index load（Aj[offset+0] 到 Aj[offset+15]）：
/*03d0*/  LDG.E R9,  [R6.64+-0x8]     // Aj[offset+0]
/*03e0*/  LDG.E R27, [R6.64+-0x4]     // Aj[offset+1]
/*03f0*/  LDG.E R13, [R6.64]          // Aj[offset+2]
/*0400*/  LDG.E R21, [R6.64+0x4]      // Aj[offset+3]
/*0410*/  LDG.E R23, [R6.64+0x8]      // Aj[offset+4]
/*0440*/  LDG.E R28, [R6.64+0xc]      // Aj[offset+5]
/*0460*/  LDG.E R25, [R6.64+0x10]     // Aj[offset+6]
/*0470*/  LDG.E R15, [R6.64+0x14]     // Aj[offset+7]
/*0520*/  LDG.E R13, [R6.64+0x18]     // Aj[offset+8]
/*0550*/  LDG.E R20, [R6.64+0x1c]     // Aj[offset+9]
/*0570*/  LDG.E R23, [R6.64+0x20]     // Aj[offset+10]
/*0640*/  LDG.E R9,  [R6.64+0x24]     // Aj[offset+11]
/*0670*/  LDG.E R29, [R6.64+0x28]     // Aj[offset+12]
/*06a0*/  LDG.E R13, [R6.64+0x2c]     // Aj[offset+13]
/*06b0*/  LDG.E R15, [R6.64+0x30]     // Aj[offset+14]
/*06c0*/  LDG.E R25, [R6.64+0x34]     // Aj[offset+15]
```

然后是 16 个对应的 IMAD.WIDE + LDG.E 间接访问（x[Aj[offset+k]]），每个都有不同的 PC。

加上 ×8、×4、×1 版本，SpMV 中源码的 **1 条** `Aj[offset]` load 在 SASS 中展开为约 **30+ 个不同 PC**。

---

## 3. 为什么这对 Prefetcher 设计很重要？

### 3.1 问题：PC 是 prefetcher 识别 IMA 的核心标识

CPU 上的 IMA prefetcher（IMP、DMP、Tyche）都依赖 **load 指令的 PC** 来识别和追踪 IMA 模式：

```
IMP:   PC_index → Stream Table entry → 检测 stride → 触发间接预取
DMP:   PC_index → Index Table entry → 收集 value differential
Tyche: PC (striding load) → Propagation Table → 依赖链
```

它们假设：**同一个 PC 的 load 访问同一个数组，因此共享同一套预取参数（base, shift 等）。**

### 3.2 展开导致的问题

```
                源码视角                          硬件视角
          ┌──────────────────┐            ┌──────────────────────┐
          │ 1 个 for 循环    │            │ 5 个不同 PC 的 LDG   │
          │ 1 条 load 语句   │   编译后    │                      │
          │                  │ ────────→  │ PC=0x0650  ─┐        │
          │ column_indices   │            │ PC=0x09c0   │ 同一   │
          │   [offset]       │            │ PC=0x0d20   │ 个 IMA │
          │                  │            │ PC=0x1080   │ 模式！ │
          │                  │            │ PC=0x01d0  ─┘        │
          └──────────────────┘            └──────────────────────┘
```

如果 prefetcher 按 PC 独立追踪，它会认为这是 **5 个不同的 load 模式**，为每个分配独立的表项：

| 方法 | 无展开时的存储 | BFS 4× 展开后 | SpMV 多级展开后 |
|------|-------------|--------------|---------------|
| IMP (per PC entry) | 1 entry | 5 entries | ~30 entries |
| Tyche (per PC chain) | 1 chain × 3 inst | 5 chains × 3 inst | ~30 chains × 3 inst |

这意味着：
1. **表项浪费**：多个表项追踪的其实是同一个 IMA 模式，只有 base 寄存器偏移不同
2. **训练变慢**：每个 PC 的训练样本变成 1/N，需要更多次执行才能确认模式
3. **预取不协调**：各展开副本独立预取，可能产生重复请求

### 3.3 GPU 上的可能解决思路

**思路 A：利用 IMAD.WIDE 的 constant operand 归组**

展开的多个副本虽然 PC 不同，但它们共享同一个 `IMAD.WIDE` 的 constant memory operand（基地址）：

```asm
// BFS 展开版第 1 份：
/*0670*/  IMAD.WIDE R2, R0, R11, c[0x0][0x178]    // dists_base = c[0x0][0x178]

// BFS 展开版第 2 份（不同 PC，但同一个 constant operand）：
/*09e0*/  IMAD.WIDE R2, R0, R11, c[0x0][0x178]    // dists_base = c[0x0][0x178]  ← 相同！
```

Prefetcher 可以用 **`(constant_operand, scale)` 作为 IMA 模式的唯一标识**，而非 PC。这样所有展开副本自动归为一组。

**思路 B：Per-PC 独立追踪（接受存储开销）**

在 GPU 上，warp scheduler 管理大量 warp，每个 warp 都会执行所有展开副本。因此每个 PC 获得的训练样本很多（= warp 数量），训练速度不成问题。代价是 prefetcher table 需要更大。

**思路 C：编译器辅助（标注 IMA 组）**

编译器在生成代码时已经知道哪些 load 来自同一个循环展开。可以通过 SASS 指令的元数据（如 `.pragma` 或寄存器 hint）告知硬件"这些 PC 属于同一 IMA 组"。

---

## 4. 总结

| Kernel | 源码 load 种类 | SASS 中 PC 总数 | 展开策略 | PC 膨胀倍数 |
|--------|--------------|----------------|---------|-----------|
| BFS `bfs_kernel` | 1 index + 1 data | (1+4)×2 = **10** | ×1 + ×4 | **5×** |
| CC `hook` | 1 index + 1 data + 1 dependent | (1+4)×3 = **15** | ×1 + ×4 | **5×** |
| SpMV `spmv_csr_scalar` | 1 index + 1 data | ~30 index + ~30 data ≈ **60+** | ×1 + ×4 + ×8 + ×16 | **~30×** |
| CC `shortcut` | 1 per hop | **1** | ×1（无展开） | **1×** |

注意 CC shortcut 没有被展开——因为循环体有**串行数据依赖**（每一跳的地址依赖上一跳的返回值），展开无法获得指令级并行的收益，所以编译器选择不展开。这也从侧面验证了 Pattern IV 的"MLP ≈ 0"特征。
