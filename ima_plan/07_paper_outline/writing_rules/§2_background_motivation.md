# §2 Background & Motivation 写作规则

> 标杆论文: Prodigy (HPCA'21) 的四层展开 + Snake (MICRO'23) 的图驱动论证 + DMP (HPCA'24) 的分类框架
> 目标篇幅: 1.5 pages

## 一、论证链

### 规则 B-1：Background 的双重使命

Background 不仅提供背景知识，还必须**为 Design 的每个模块预埋问题**。

| Background 提出的问题 | Design 中的对应模块 |
|---------------------|-------------------|
| IMA 串行依赖链 ~400 cycles | IPU/DPU 两步 pipeline |
| L1 miss 70-77% 但 L2 miss 仅 22-34% | Prefetch 聚焦 L2→L1 |
| PC 膨胀（60+ PC → 2 entries） | CT 的 (base, scale) PC-agnostic 索引 |
| 多 warp 地址流交织 | CD 的 tracked warp 机制 |
| IMAD.WIDE 结构性暴露 | CD 的零推断检测 |

**DMP 示范**：§II.C (Branch Misprediction) 预埋了 §III 的 Repetition Filter。没有这个 Background 子节，Repetition Filter 就缺乏动机。

### 规则 B-2：Case Study 四层展开（对标 Prodigy §2）

选一个代表性算法（推荐 BFS），从四个层次递进展开：

```
Layer 1: 算法层（伪代码，Fig）
    ↓ "该算法使用 CSR 格式存储图..."
Layer 2: 数据结构层（CSR 存储格式，Fig）
    ↓ "CSR 格式导致 data load 地址依赖 index load 返回值..."
Layer 3: 访存模式层（warp 级 LDG→IMAD.WIDE→LDG 依赖链）
    ↓ "这种串行依赖链使每次迭代产生 ~400 cycles 延迟..."
Layer 4: 性能数据层（L1 miss breakdown + Ideal speedup，Fig）
```

**Prodigy 示范**：Fig.3(a) BFS 伪代码 → Fig.3(b) CSR 数据结构 → 文字分析两类瓶颈 → Fig.4 全 workload 执行时间分解。三张图从软件到硬件形成完整证明链。

## 二、段落结构模式

### 规则 B-3："提问→展示→解读→结论" 循环

每个子主题对应一个 Figure，段落按以下循环组织（Snake 核心模式）：

```
"To study [X], we measure [Y]..."           ← 提问
"Figure Z shows..."                          ← 展示
"We observe that [quantitative finding]..."  ← 解读
"[implication for prefetcher design]."       ← 结论
```

**Snake 示范**：
> "To study the quantity of the reservation fails, we measure the number of reservation fails normalized to the total L1 data cache accesses... in Figure 3. We observe that reservation fails occur, on average, 30%."

### 规则 B-4："We make X key observations" 编号模式

每当有一张 Figure 需要解读时：

1. 先报告总观察数："Based on these results, we make N key observations."
2. 逐条编号展开："First... Second... Third..."
3. 每条：数字 + 1-2 句原因解释

**功能**：给读者预期；每条观察可独立被引用/跳读；编号让审稿人引用方便。

**Snake 示范**：
- §2 LPS 代码分析后："we make four key observations: (1)... (2)... (3)... (4)..."
- §2 链分析后："We make three key observations: (1)... (2)... (3)..."
- §5.1 Coverage："we make seven main observations. First... Second... Third..."

### 规则 B-5：Motivation 末句指向设计

Background 最后一段必须收敛到设计方向，作为 §3 的前提。

**Magellan 示范**：
> "efficient IMA prefetching necessitates identifying the patterns of nested loop structures and selecting the appropriate prefetching strategy accordingly."

**Snake 示范**：
> "Therefore, a prefetcher based on frequent chains of strides enhances prefetching opportunities."

## 三、定量 vs 定性

### 规则 B-6：Background 是全文量化密度最高的节

Background ~85% 为量化论证。每一个论点都配 Figure 支撑数字。**不允许出现无数据支撑的性能声明。**

### 规则 B-7：定量 Motivation 的三驾马车

Background 必须提供以下三组定量数据（可分布在不同子节）：

| 数据 | 功能 | 对 GRASP 的映射 |
|------|------|----------------|
| **问题严重性** | 证明 IMA 是性能瓶颈 | IMA 占 L1 miss 51-84%；L1 miss 70-77% |
| **理论上界** | 量化优化空间 | Ideal L1D speedup 1.75x-3.04x |
| **现有方案不足** | 量化 gap | 现有 GPU prefetcher 的 IMA coverage ~0% |

### 规则 B-8：Little's Law 推导的放置

定量推导（如 warp latency hiding 的 Little's Law）放在 §2 而非 §1。Introduction 只用结论（"52% 延迟无法被隐藏"），推导过程放 §2.3。

## 四、分类框架

### 规则 B-9：分类用 "图 + 代码 + 文字" 三合一

复杂分类系统的标准呈现方式（DMP 核心模式）：

**DMP Fig.3**：2×2 示意图，每个格子包含——
- 左侧：迭代代码（for 循环）
- 中间：数组内存布局图（箭头表示访存路径）
- 右侧：可视化访问序列

**Magellan Fig.8**：表格形式，每行是一个类别，每列是一个属性（code / memory traversal pattern / inner-outer loop direction / representative workload）。

**对 GRASP**：四类 IMA Pattern（Linear Gather / Frontier-Driven / Data-Dependent / Pointer Chasing）应以类似 DMP Fig.3 的形式呈现，每个 Pattern 配代码片段 + 内存访问示意图。

### 规则 B-10：分类后跟 Table 总结

分类图之后，用一张紧凑的 Table 总结 prefetchability 层级。

**对 GRASP（paper_structure.md Table 1）**：

| Pattern | 代表算法 | Index 可预取 | Data 可预取 | GRASP 覆盖 |
|---------|---------|:-----------:|:-----------:|:----------:|
| I | SpMV | Yes | Yes | Full |
| II | BFS/SSSP/BC | Yes | Yes | Full |
| III | CC hook | Yes | Partial | Partial |
| IV | CC shortcut | No | No | No |

## 五、图表

### 规则 B-11：Background 中图的三种类型

| 图类型 | 功能 | 示例 |
|--------|------|------|
| **概念图** | 建立心智模型 | GPU SM 架构简图、CSR 存储格式 |
| **分类图** | 呈现分类框架 | 四类 IMA Pattern 示例 |
| **量化动机图** | 数字驱动论证 | L1 miss breakdown、Ideal speedup |

三种类型应按此顺序出现：先建立概念 → 再给分类 → 最后用数字收尾。

### 规则 B-12：Figure Caption 中写 Motivation 目标

**Prodigy 示范**：Fig.4 的 caption 中直接写出 "*The goal of this work is to reduce the DRAM stalls (dark blue portion of the bar).*"

这使得图的意义一目了然，略读者可以从 caption 直接获取核心信息。

## 六、IMAD.WIDE 子节的特殊处理

### 规则 B-13：IMAD.WIDE 是 §2 的高潮

§2.4 (IMAD.WIDE) 是 Background 的逻辑终点，也是 GRASP 的核心差异化。结构：

```
IMAD.WIDE 指令格式（精确写出 operand 语义）
    ↓
为什么是结构性保证（唯一的 32×32+64→64 指令，编译器别无选择）
    ↓
覆盖率数据（88-99%，多算法验证）
    ↓
与 CPU 黑盒推断的对比（1 句引用 §1.4 对比表）
    ↓
SASS 代码片段 + 寄存器依赖箭头图
```

### 规则 B-14：形式化定义的时机

**先建立直觉（图示 + 例子），再给出形式化（公式/格式），再用真实案例验证。**

DMP 示范：先用 Fig.3 展示四种 pattern 的直觉 → 再给出 Equation 1 形式化定义 → 再用 Fig.4 的 BFS 真实案例验证。

如果先给公式，读者不知道为什么需要这些字段。
