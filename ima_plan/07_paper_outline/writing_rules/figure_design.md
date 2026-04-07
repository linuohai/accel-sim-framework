# 图表设计规则

> 标杆论文: DMP (HPCA'24) 的图表设计哲学（用户指定最佳参考）
> 补充参考: Snake (MICRO'23) 的 bar chart, Magellan (ISCA'25) 的 caption 写法
> 与 CLAUDE.md 绘图规范配合使用（颜色用 CB10、输出 PDF+SVG、constrained_layout 等）

## 一、DMP 六大图表设计原则

### 原则 F-1：用真实数据填充示意图

示意图中的 index 值、差分、访存地址全部使用**具体数字**（如 0x410, 0x414），而非抽象符号（a, b, c）或 value1, value2。

**功能**：读者可以在纸上自己验证算法正确性，极大提升可信度。

**DMP 示范**：Fig.2（differential matching 原理图）中 index 值 (6, 4, 8, 9)、差分 (-2, +4, +1)、地址 (0x410, 0x414, 0x418) 全部具体。

**对 GRASP**：CD 检测流程图中，应使用 BFS 的实际 PC 值和寄存器编号；CT/TT 查找示例应使用实际的 (base, scale) 值。

### 原则 F-2：全文颜色语义一致

确定一套颜色系统，在全文所有图中保持一致。

**DMP 示范**：
- 蓝色 = Index（Index PC、Index Table、Index Queue）
- 红色 = Target（Target PC、Target Table、Prefetch 输出）
- 黄色 = 关键处理步骤
- 绿色 = 已有组件

**对 GRASP 的建议颜色系统**（基于 CB10 调色板）：

| 概念 | 颜色 | 用途 |
|------|------|------|
| Index load/prefetch | CB10[0] (蓝) | CD 检测的 index LDG、IST、IPU |
| Data load/prefetch | CB10[1] (橙) | CT/TT、DPU |
| IMAD.WIDE | CB10[2] (绿) | CD 中的地址计算指令 |
| Demand/Baseline | CB10[7] (灰) | 对比基准 |
| GRASP (our work) | CB10[3] (红) | 性能图中 GRASP 方案 |

此颜色系统应从 §2 的概念图到 §5 的性能图保持一致。

### 原则 F-3：图的复杂度与概念重要性成正比

| 重要性 | 图复杂度 | 示例 |
|--------|---------|------|
| 最高（核心 motivation） | 四联图/多子图 | DMP Fig.1, Introduction 动机数据 |
| 高（核心概念） | 复合图 | DMP Fig.4 (BFS 五子图), 架构总图 |
| 中等（设计细节） | 单图 | 各组件 flowchart |
| 低（辅助数据） | 紧凑单图 | Sensitivity analysis |

### 原则 F-4：数据流图用 "层叠展示"

展示数据经过多个处理步骤的过程时，图的布局从上到下（或从左到右），每一层都写明具体数据值：

```
Unfiltered data (最顶)
  → Filter 1（中间层）
  → Filtered data（下一层）
  → Filter 2（中间层）
  → Final data（最底）
```

**DMP Fig.7 示范**：数据经过 Repetition filter → Range filter，每一层都写具体地址值。

### 原则 F-5：性能对比图 Legend 内嵌 average

性能 bar chart 的 legend 中直接写出每个方案的平均 speedup：

```
Legend: ■ No-PF (1.00×)  ■ Snake (1.02×)  ■ GRASP (1.35×)  □ Ideal L1D (2.30×)
```

**DMP Fig.12 示范**：Legend 包含 "IMP 1.13×, DMP(our work) 2.06×"。读者不需要去正文找平均值。

### 原则 F-6：超范围 bar 用数字标注

超出 y 轴范围的 bar 用数字标注在顶部，**不扩展 y 轴**（避免压缩其他 bar 的视觉差异）。

**DMP 示范**：5.6× 的 bar 超出 y 轴范围，在 bar 顶部标注 "5.6×"。

## 二、图类型规范

### 规则 F-7：各节的图类型

| 节 | 图类型 | 参考 |
|---|--------|------|
| §1 Introduction | 双子图 bar chart（motivation 数据） | DMP Fig.1 |
| §2 Background | 概念图 + 分类图 + 量化动机图 | DMP Fig.3-4, Prodigy Fig.3-4 |
| §3 Design - Overview | 全局架构框图 | DMP Fig.10, Snake Fig.14 |
| §3 Design - 组件 | Flowchart / Table lookup 示例 | Snake Fig.12, IMP Fig.4-5 |
| §3 Design - Pipeline | 时序图（demand vs prefetch 对比） | Snake Fig.15 |
| §3 Design - Example | 端到端数据流图 | DMP Fig.4, Snake Fig.15 |
| §4 Methodology | Table（benchmark + baseline） | DMP Table IV |
| §5 Evaluation - 主结果 | Grouped bar chart (双栏) | Snake Fig.18, DMP Fig.12 |
| §5 Evaluation - 指标 | 多组并列 bar chart | DMP Fig.11 |
| §5 Evaluation - Sensitivity | Line plot 或小 bar chart (单栏) | Snake Fig.16 |

### 规则 F-8：grouped bar chart 的设计清单

- [ ] ≥3 方案时颜色 + hatching（CLAUDE.md 规范）
- [ ] GRASP 用实色无 hatch（`HATCHES[0]`），视觉突出
- [ ] x 轴 workload 按算法类别排列（不按性能）
- [ ] 最右栏 GMEAN
- [ ] Legend 内嵌 average（原则 F-5）
- [ ] y 方向水平虚线网格（.mplstyle 默认）
- [ ] 超范围 bar 用数字标注（原则 F-6）
- [ ] annotate_bars() 后 ylim 上界留 data_max × 1.12

## 三、Caption 写法

### 规则 F-9：Caption 写命题句

Caption 是**完整的描述性命题**，不是散文描述：

**正确**："Fig. X: IPC speedup of GRASP over baseline across 6 algorithms and 4 datasets."
**错误**："Fig. X: A bar chart showing the IPC improvement."
**错误**："Fig. X: Results."

**Snake 示范**："Figure 18: Performance improvement of prefetching mechanisms."
**Prodigy 特殊做法**：Fig.4 caption 中直接写 motivation 目标——"The goal of this work is to reduce the DRAM stalls (dark blue portion of the bar)."

### 规则 F-10：Caption 独立可理解

Caption 应当让仅看 caption + 图的读者能理解图的核心信息（无需阅读正文）。

**Magellan 示范**：Caption 通常 1-2 句，描述图内容 + 包含关键结论。

### 规则 F-11：Figure 编号嵌入句子

引用图时，将 "Figure X" 作为句子主语或直接宾语，而非放在括号里：

**正确**："Figure 16 shows the coverage of Snake across all workloads."
**错误**："Snake achieves high coverage across all workloads (Figure 16)."

**功能**：使图表成为论证的主体，而非注脚。

## 四、Table 设计

### 规则 F-12：Hardware Cost Table 的格式

| 组件 | Entries | Per-Entry (B) | Total (B) | 功能 |
|------|:-------:|:------------:|:---------:|------|
| CD FIFO | 20 | 16 | 320 | ... |
| CT | 32 | 16 | 512 | ... |
| **Total** | | | **2,276** | |

后跟三角验证（DMP 模式）：
- vs L1 cache：占 L1 的 X%
- vs 竞品：vs IMP 0.9KB/core, DMP 0.9KB/core
- vs 真实 GPU：占 SM 面积的 X%（如果有数据）

### 规则 F-13：Benchmark Table 的格式

| 算法 | Suite | 数据集 | V/E | IMA Pattern | 主要 IMA kernel |
|------|-------|--------|-----|:-----------:|----------------|
| BFS | Gardenia | web-Google | 916K/5.1M | II | bfs_kernel |
| SpMV | Gardenia | flickr | 820K/9.8M | I | spmv_kernel |
| CC | Gardenia | cit-Patents | 3.8M/16.5M | III+IV | hook+shortcut |

IMA Pattern 列映射到 §2 的四类分类，让 Evaluation 中的结果可以按 Pattern 分组分析。

## 五、图表数量预算

### 规则 F-14：MICRO 2026 的图表密度

基于 T3 论文扫描的统计：

- **会议论文（MICRO/ISCA）平均图/页比 ≈ 1.1-1.5**
- MICRO 2026: 11 pages body → 预期 12-17 figures + 3-4 tables
- paper_structure.md 当前规划：17 figures + 4 tables（1.5 fig/page，符合惯例）

**DMP/Snake 的参考值**：
- DMP (HPCA, 15 pages): ~24 figures/tables
- Snake (MICRO, 14 pages): ~20 figures/tables
- 两者都偏高，体现了"data-driven"的写作哲学

### 规则 F-15：图表不跨页

每张图应与引用它的文字在同一页或相邻页。绝不让读者翻超过一页去找对应的图。

LaTeX 排版时使用 `[t]` 或 `[!ht]` 定位，必要时调整文字顺序以确保图文同页。
