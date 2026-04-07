# §5 Evaluation 写作规则

> 标杆论文: Snake (MICRO'23) 的 "X key observations" + DMP (HPCA'24) 的 ablation 结构 + Magellan (ISCA'25) 的潜力上界
> 补充参考: IMP (MICRO'15) 的多维指标, Spare Register (HPCA'14) 的 per-kernel 分析
> 目标篇幅: 3.0 pages

## 一、论证链（子节顺序）

### 规则 E-1：先质量后量，先收益后代价

Evaluation 子节的黄金顺序（Snake 验证）：

```
§5.1 Prefetch Potential / Coverage-Accuracy  ← prefetch 质量（机制做得好不好）
    ↓
§5.2 主要结果: IPC Speedup                   ← 端到端性能
    ↓
§5.3 与 SOTA Baseline 对比                   ← 差异化论证
    ↓
§5.4 敏感性分析                               ← 设计点合理性
    ↓
§5.5 Hardware Cost                           ← 代价
```

**理由**：先展示"prefetch 质量好"，才能让 IPC 提升有说服力；先展示收益，再承认代价。

### 规则 E-2：先展示 Prefetch Potential（Magellan 模式）

在所有结果之前，先展示理论上界（如 IMA miss 占总 miss 的比例）。

**Magellan §5.1 示范**：
> "Fig.12 shows that, on average, 87.6% of total cache misses are IMA misses, which can be seen as potential candidates for the Magellan prefetcher."

**功能**：建立理论空间。后续 coverage/speedup 与这个上界隐式对比，让读者自己判断 GRASP 释放了多少潜力。

**对 GRASP**：可用 Ideal L1D speedup (1.75x-3.04x) 作为天花板，然后展示 GRASP 达到了天花板的 X%。

## 二、段落结构模式

### 规则 E-3："We make X key observations" 是 Evaluation 核心模式

每个子节对应一张 Figure，解读模式：

```
"Figure X shows [metric] for [configurations]."
"Based on these results, we make N key observations."
"First, [observation + number + cause]."
"Second, [observation + number + cause]."
...
```

**Snake 示范**：
- §5.1: "we make seven main observations. First... Second... Third..."
- §5.2: "We make four key observations."

**DMP 示范**：每个指标子节（coverage/accuracy/timeliness/detection coverage）结构高度统一——指标定义→指向图→DMP 结果→关键观察→机制解释。

### 规则 E-4：数字 + 原因配对（永不落单）

报告任何性能数字后，**必须紧跟一句机制层面的原因解释**。

| 写法 | 正确性 |
|------|--------|
| "BFS speedup +49.8%." | ❌ 数字落单 |
| "BFS speedup +49.8%. This improvement is attributed to GRASP's high index coverage (92%) which enables timely data prefetch." | ✅ 数字+原因 |
| "BFS speedup +49.8% because GRASP effectively predicts index strides." | ✅ 简洁版 |

**Snake 示范**：
> "[数字]... This [improvement] is attributed to [机制X]."
> "[数字]... The reason behind [performance] is that [具体行为]."

这是 MICRO 论文的因果严谨性要求——数字本身不够，必须解释为什么。

### 规则 E-5：Baseline 逐一对比，不笼统

不是笼统说"GRASP 更好"，而是对每个 baseline 逐一解释为何 GRASP 优于它。

| Baseline | 为什么 GRASP 更好（示例） |
|----------|------------------------|
| stride-INTRA | 只捕获规则 stride，对 IMA data load 无能为力 |
| Snake | Variable-chain 但仍是 stride chain，不处理数据依赖 |
| CAPS | CTA-aware 但显式排除 indirect access |
| Spare Register | Fermi 架构 tag-based 检测，现代 GPU ISA 不适用 |

### 规则 E-6：负面结果不回避

**Magellan 的标准处理**：不回避差的结果，给机制解释，将"未解决"转为 future work。

```
"CC shows -7.0% degradation. This is due to [具体原因: Pattern IV pointer chasing 
不在 GRASP 的覆盖范围内，且 prefetch 占用的 MSHR 加剧了 demand 竞争]."
```

**Prodigy 示范**：BC 性能下降时，列出 "two primary reasons"。
**Snake 示范**：能耗节刻意简短——节能是"赠品"，不需要大篇幅论证。

## 三、定量 vs 定性

### 规则 E-7：Evaluation 约 80% 量化

- 量化：数字 + 图表引用
- 定性：仅限原因分析（"This is attributed to..."）

每句话要么给数字，要么解释数字。不允许出现无数字支撑的性能声明。

### 规则 E-8：结果的层次报告

先报最重要的均值，再报峰值，再报与理想系统的差距：

> "GRASP achieves a geomean speedup of 35.5% across all workloads (up to 138.6% on CC-flickr), reaching XX% of the Ideal L1D performance ceiling."

**IMP 示范**："56% speedup on average (up to 2.3×)"、"within 23% of the performance of an idealized system."

## 四、图表

### 规则 E-9：主结果图的设计

主结果图（IPC Speedup）是全文最重要的图，双栏 7.0" grouped bar chart。

**设计要求**（综合 Snake Fig.18 + DMP Fig.12）：

1. x 轴：workload（按算法类别排列，不按 GRASP 性能排序——体现对结果的自信）
2. y 轴：Speedup (×) 或 IPC improvement (%)
3. 颜色 + hatching（≥3 方案必须同时使用，GRASP 用实色无 hatch 视觉突出）
4. 最右栏：GMEAN
5. Legend 内嵌 average speedup（DMP 模式）：读者不需要查正文找均值
6. 超出 y 轴范围的 bar 用数字标注在顶部（DMP 模式）

### 规则 E-10：多指标并列图

Coverage / Accuracy / Timeliness 三指标用三组并列的 bar chart，每组按 workload 分。

**DMP Fig.11 示范**：4 个竖向排列的 bar chart，相同 x 轴 workload 顺序，让读者视线垂直移动即可对比。

### 规则 E-11：Ablation 图与主图同 x 轴排列

Sensitivity/Ablation study 图的 workload 顺序与主结果图一致。

**DMP Fig.16-23 示范**：workload 顺序与 Fig.12 一致，让读者快速定位。

## 五、Sensitivity Analysis

### 规则 E-12：Ablation 固定四步结构

每个 sensitivity 分析点（DMP 称 "Discussion"）固定结构：

```
实验目的（一句话："We study the impact of [parameter] on performance."）
    ↓
实验设计（"We vary [parameter] from X to Y."）
    ↓
两条关键观察（"First... Second..."）
    ↓
设计决策理由（"Based on these observations, we set [parameter] to [value]."）
```

**DMP Discussion 示范**：8 个 discussion 点，每个约 0.5-1 段，对应一张图。

### 规则 E-13：Sensitivity 结论总是"设计选择合理"

每个 sensitivity 分析收敛到当前配置是合理的折衷点。如果某个参数点更好，需要解释为什么不选（如面积/功耗约束）。

**Snake 示范**：Tail table entry size / eviction policy / throttling time interval 三个维度，每个收敛到当前选择。

### 规则 E-14：至少 6 个 Sensitivity 维度

DMP 有 8 个 Discussion 点，Snake 有 3 个 sensitivity + 2 个 tiling/decoupling。

**对 GRASP 的建议维度**：

1. CT size (8/16/32/64 entries)
2. Prefetch distance (2/4/8)
3. Throttle 参数 (tc_mode / mshr_threshold / cooldown)
4. CD FIFO size
5. IST confidence threshold
6. Stride learning: tracked warp vs all warps

## 六、特殊分析

### 规则 E-15：Per-workload 深度分析

对关键 workload 进行逐一分析，解释 root cause。平均值可能掩盖重要现象。

**Spare Register 示范**：§5.2.2 对每个 kernel 逐一分析——H-BFS, H-SSSP, H-MST 等。每个 kernel 的分析包含：为什么有/没有性能提升 + 具体的访存行为解释。

**对 GRASP**：至少对以下 workload 给出深度分析——
- BFS-web（高 speedup 代表）：为什么好？
- CC-cit（退化代表）：为什么差？Pattern IV 还是 overhead？
- SpMV（特殊行为）：为什么 Throttle 对 SpMV 效果最大？

### 规则 E-16：Alternative Explanation Elimination

专门分析"替代解释"是否成立。

**Spare Register §5.5 示范**："更大的 cache (64KB) 能否替代预取？"——结论是 SPREF1 在大多数情况下优于 64KB cache baseline。

**对 GRASP 可考虑的 alternative**：
- "更多的 MSHR entries 能否替代 GRASP？"（参考实验：消除 RFAIL 后 IPC 反降 4.7%）
- "更大的 L1 cache 能否替代？"（Ideal L1D 对比）
