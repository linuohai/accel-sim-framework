# §3 Design 写作规则

> 标杆论文: Snake (MICRO'23) 的自顶向下结构 + DMP (HPCA'24) 的五段子节模式 + IMP (MICRO'15) 的形式化
> 补充参考: Spare Register (HPCA'14) 的 GPU ISA 级描述
> 目标篇幅: 3.5 pages

## 一、论证链

### 规则 D-1：自顶向下，Overview → 组件 → 示例 → Cost

这是 16/16 篇论文的共识结构：

```
§3.1 Overview（~0.3 page）
    全局架构图 + 三句话概述
    ↓
§3.2-3.6 各组件子节（~2.5 pages）
    每个子节展开一个组件
    ↓
§3.7 Worked Example（~0.4 page）
    用具体数值走完整个 pipeline
    ↓
§3.8 Hardware Cost（~0.2 page）
    Table 形式，每组件 entries × per-entry size
```

**Snake 示范**：三步总览（detection → prefetching → throttling）→ §3.1/3.2/3.3 各展开 → §3.4 Illustration → §3.5 Compiler Support
**DMP 示范**：Overview 段 + Fig.5 总体流程图 → A/B/C/D/E 五个子节 → Hardware §IV

### 规则 D-2：Overview 段不超过 3 句话

Overview 段精确完成三件事：

1. **系统定位**："GRASP is a per-SM hardware prefetcher that operates at the instruction issue stage..."
2. **流程概要**："It detects IMA chains via LDG→IMAD.WIDE→LDG dependency, then issues two-step prefetch (index → data)."
3. **导读**："This section explains the detection mechanism (§3.2), table structures (§3.3), stride tracking (§3.4), prefetch generation (§3.5), and throttle control (§3.6)."

**DMP 示范**：第一段精确做了系统定位 + 两步流程 + 导读，然后立即引入 Fig.5。

### 规则 D-3：Overview 后必有架构总图

架构总图是 Design 的入口，必须在 Overview 段之后立即出现。

**图的要求**：
- Per-SM 视角，标注所有组件和数据流方向
- 区分 training path（实线）和 prefetch path（虚线）
- 标注每个组件在 SM 中的物理位置（CD 在 issue stage、CT/TT/IST 在 L1 旁）
- 参考风格：DMP Fig.10 (hardware overview) / Snake Fig.14 (major components)

## 二、组件子节的段落结构（最重要的模式）

### 规则 D-4：每子节 "目标→约束→洞察→机制→参数" 五段结构

这是 DMP 在 A/B/C/D/E 五个子节中重复使用的模式：

```
¶1: 功能目标定义
    "The goal of [component] is to [functional description]."

¶2: 设计约束分析（为什么难）
    "A naive approach would require [expensive operation]... which is impractical because..."

¶3: 关键洞察/假设
    "We observe that [insight]..." 或 "We exploit the fact that..."

¶4: 机制描述（配图）
    "As shown in Fig. X, [component] operates as follows: ..."
    按步骤（Step 1... Step 2... Step 3...）或按数据流描述

¶5: 实现参数
    "We set [parameter] to [value] based on [empirical finding / sensitivity analysis in §5]."
```

**对 GRASP 各子节的映射**：

| 子节 | 目标 | 约束 | 洞察 | 机制 | 参数 |
|------|------|------|------|------|------|
| CD | 检测 IMA 链 | 不能等 load 返回 | IMAD.WIDE 在 issue 阶段可见 | FIFO + 三步匹配 | 20 entries |
| CT/TT | 存储已检测的链 | PC 膨胀 60+ | (base,scale) PC-agnostic | 32-entry LRU + TT 支持 one-to-many | 32 + 8 entries |
| IST | 学习 stride | warp 交织 | tracked warp + freeze | per-PC stride + confidence counter | 64 entries |
| IPU/DPU | 发出预取 | MSHR 竞争 | 两步 pipeline 隐藏 ~400cy | stride predict → index pf → data pf | distance=4 |
| TC | 防止 cache 污染 | burst access | MSHR 占用率相关 | cooldown timer | T40C200 |

### 规则 D-5：先 what 再 why 再 how

每个组件的描述顺序：

1. **What**：prefetch 的触发条件是什么
2. **Why**：为什么需要这个机制（必要性）
3. **How**：具体状态机/数据结构

**Snake §3.2 示范**：先说 prefetch 触发条件 → 再解释 training 的必要性 → 再描述 T1/T2 状态转换。

每当引入新概念时，立即用一句话解释其必要性。
**Snake 示范**："This approach ensures that prefetched data does not replace useful data that is already in the L1 cache."

## 三、形式化与公式

### 规则 D-6：公式 "三明治" 结构

公式不独立存在，前后各有一段解释文字：

```
文字：描述问题（"需要计算 data address..."）
    ↓
公式：data_addr = base + index_value × scale
    ↓
文字：解释每个变量（"where base and scale are extracted from IMAD.WIDE operands..."）
```

**DMP 示范**：Equation 2（BaseAddr 计算）的引入：先描述问题 → 给公式 → 解释变量 → 附加判断逻辑。
**IMP 示范**：公式(1) ADDR(A[B[i]]) = Coeff × B[i] + BaseAddr → 公式(2) 优化为移位+加法，避免乘法。

### 规则 D-7：伪代码与行号引用

如果使用 Algorithm 伪代码，正文中应引用行号：

**Magellan 示范**：Algorithm 1 的伪代码精简（21 行），每个关键步骤在正文中有对应引用（"line 3", "line 7", "line 9"）。读者可并行阅读伪代码和文字。

## 四、图表

### 规则 D-8：每个组件子节至少一张对应图

| 组件 | 图类型 | 参考 |
|------|--------|------|
| CD | Flowchart（指令进入→判断→FIFO 操作→确认/拒绝） | Snake Fig.12 |
| CT/TT | Table lookup 过程示例（IMAD.WIDE → 提取 → 查找 → 匹配） | IMP Fig.4-5 |
| IST | 可选，与 CD/CT 合并 | — |
| IPU/DPU | Pipeline 时序图（demand vs prefetch 路径对比） | Snake Fig.15 |
| 总架构 | 全局数据流图 | DMP Fig.10 |

### 规则 D-9：Flowchart 与文字完全对应

如果使用 flowchart（如 CD 检测流程），文字按 flowchart 的决策节点顺序描述。读者应能对照 flowchart 逐步跟随文字。

**Snake 示范**：Fig.12 flowchart 的每个决策节点在 §3.1 文字中都有对应描述。

### 规则 D-10：数据结构的字段逐一解释

表格/数据结构的每个字段都在文字中逐一解释，但通过 "(1)... (2)..." 编号避免段落碎片化。

## 五、Worked Example

### 规则 D-11：Worked Example 的组织方式

Worked Example 是 Design 的收尾，用一个具体 workload（推荐 BFS）的真实数值走完整个 pipeline。

**结构**：
1. 首句声明简化假设："For clarity, we consider a single SM with 4 active warps."
2. 按时间步骤描述（Step 1 → Step 2 → ... → Step 7）
3. 标注 "noteworthy" 的特殊行为
4. 配一张大的 Figure，展示数据值在各组件间的流动

**Snake §3.4 示范**：用 Fig.15（具体数值的表格）展示整个 training + prefetch 过程，按 a→b→c 时间步骤描述。

**对 GRASP**：用 BFS 的一个 iteration，展示 CD 检测 → CT 注册 → IST 学 stride → IPU 发 index pf → DPU 算 data addr → demand data hit。

## 六、Hardware Cost

### 规则 D-12：Hardware Cost 在 Design 末尾，Table 形式

| 组件 | Entries | Per-Entry | Total | 功能 |
|------|:-------:|:---------:|------:|------|
| CD FIFO | 20 | ~16 B | 320 B | ... |
| CT | 32 | ~16 B | 512 B | ... |
| ... | ... | ... | ... | ... |
| **Total** | | | **~2.3 KB/SM** | |

然后给出 per-warp 等效数字（2.3KB / 64 warps ≈ 36 B/warp）和与竞品的对比（vs IMP 0.9KB/core, DMP 0.9KB/core）。

**DMP §IV.B 的三角验证**：绝对数字 + 相对比较（vs cache） + 相对比较（vs 竞品） + 相对比较（vs 真实 CPU），从三个角度证明 overhead negligible。

## 七、防御性写法

### 规则 D-13：预防性子节

如果设计有可能与某技术冲突，专门加一个子节说明两者互补。

**Snake §3.5 示范**："Compiler Optimization Support"——预先回答审稿人 "与 compiler tiling 冲突吗" 的问题。

**对 GRASP 可能需要的防御**：
- "为什么不做 software prefetching？"（可在 §2 讨论 GPU 上 SW prefetch 的 overhead）
- "为什么 distance=4 而不是动态调整？"（可在 sensitivity analysis 中回应）
- "如何处理 kernel 切换？"（CT kernel reset 机制）
