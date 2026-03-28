> 最近更新: 2026-03-28

# cuGraph SASS IMA 链分析

## 目的

验证 NVIDIA cuGraph 24.6.0（production-grade GPU 图计算库）的编译产物中是否存在与 Gardenia benchmark 相同的 LDG → IMAD.WIDE → LDG 间接内存访问链。

## 方法

1. 从 `/usr/lib/libcugraph.so` (480 MB) 提取 sm_80 cubins（共 126 个）
2. 选取两个代表性 cubin 反汇编：
   - **cubin 23**（917 函数）：`transform_reduce_e_by_src_dst_key`, `per_v_transform_reduce_dst_key_aggregated_outgoing_e`, `DeviceSegmentedSort` — 边级聚合与分段排序
   - **cubin 8**（1340 函数）：`refine_clustering`, `multi_partition`, `shuffle_vertex_pairs` — Leiden/Louvain 社区检测
3. 使用 `scan_cugraph_sass.py`（source-agnostic 寄存器数据流追踪器）检测 IMA 链

## 结果

| cubin | 算法域 | 扫描函数 | 命中函数 | IMA 链总数 | IMAD.WIDE (canonical) | variant (multi-step) |
|-------|-------|---------|---------|----------|----------------------|---------------------|
| 23 | edge reduce / sort | 917 | 78 | **527** | 36 | 491 |
| 8 | Leiden / partition | 1248 | 11 | **140** | 0 | 140 |
| **合计** | | **2165** | **89** | **667** | **36** | **631** |

### 地址计算分布

| 类型 | cubin 23 | cubin 8 | 语义 |
|------|---------|--------|------|
| `IMAD.WIDE` (canonical) | 36 | 0 | 单指令 `base + index * scale` |
| `IADD3` (via IMAD.SHL) | 325 | 132 | 编译器展开：`IMAD.SHL.U32 → IADD3` 两步 |
| `LEA` | 166 | 8 | Load Effective Address 变体 |

### 关键发现

1. **cuGraph 100% 存在 IMA 链** — 89 个函数中检测到 667 条 LDG→{addr_compute}→LDG 链
2. **编译器差异**：Gardenia 在 sm_80 下生成 `IMAD.WIDE`（单条指令），cuGraph 的多数 kernel 被 -O3 展开为 `IMAD.SHL.U32 + IADD3` 两步序列。**本质相同**，都是 `base + index * scale` 的间接寻址
3. **典型 scale factor**：8 (64-bit index, `long long`) —— 与 Gardenia 使用 32-bit `int` (scale=4) 的区别来自 cuGraph 默认 64-bit vertex/edge type

### 手动验证的经典 IMA 链

`DeviceSegmentedSortKernelSmall`（cubin 23, PC 0x00c0-0x0100）：

```
/*00c0*/  IMAD.WIDE.U32 R2, R0, R2, c[0x0][0x170]  ; addr = seg_id * 4 + offsets
/*00d0*/  LDG.E R0, [R2.64]                          ; index = offsets[seg_id]
/*00f0*/  IMAD.WIDE.U32 R2, R0, R5, c[0x0][0x1a0]  ; addr = index * 8 + values
/*0100*/  LDG.E R4, [R2.64]                          ; data  = values[index]
```

这与 Gardenia BFS/SSSP 中的 `neighbor = col_idx[row_ptr[v] + i]` 模式完全同构。

## 论文意义

- IMA 模式不是 academic benchmark 特有，**NVIDIA 官方图库同样存在**
- 即使在 NVIDIA 自己的编译优化下，间接内存访问的 ISA 特征（IMAD.WIDE 或其展开形式）仍然可识别
- 为 GRASP Insight 1（"IMAD.WIDE 零推断检测"）提供了 production-level 验证
- 需注意：高优化级别下检测需支持 IMAD.SHL + IADD3 变体，不能仅依赖 IMAD.WIDE

## 文件清单

| 文件 | 用途 |
|------|------|
| `scan_cugraph_sass.py` | Source-agnostic IMA 链扫描器（支持 canonical + multi-step variant） |
| `cugraph_ima_chains.csv` | cubin 23 的链实例（527 条） |
| `cugraph_analysis_summary.md` | 本文档 |
