# §1 Introduction 写作规则

> 标杆论文: Snake (MICRO'23) + DMP (HPCA'24) + Magellan (ISCA'25)
> 补充参考: IMP (MICRO'15), Spare Register (HPCA'14), Prodigy (HPCA'21)
> 目标篇幅: 1.5 pages

## 一、论证链（最高优先级）

### 规则 I-1：漏斗式七层论证结构

Introduction 必须按以下逻辑递进展开，每层对应一个或多个段落：

```
Layer 1: 领域重要性 + IMA 问题定义
    ↓
Layer 2: GPU 上的严重性（定量）
    ↓
Layer 3: 现有方案回顾 + 逐类否定（3 次 "However"）
    ↓
Layer 4: Gap 的定量证明（Ideal baseline 对比）
    ↓
Layer 5: 核心技术洞察（点到为止）
    ↓
Layer 6: 方案概述（一句话）
    ↓
Layer 7: Contributions（bullet list）
```

**证据**：
- DMP：领域重要性→根因定位→问题扩展→Fig.1 四联图数据证明→技术洞察→方案→贡献
- Snake：GPU 内存墙→TLP 副作用→现有 prefetcher 局限→Ideal 对比量化 gap→观察变长 stride 链→提出 Snake→贡献
- Magellan：IMA 广泛性→SW Prefetch 失败（85.3% 越界）→三个目标→两个 insight→方案→贡献

### 规则 I-2：Gap 必须量化，不能只说"不够好"

用 Ideal/Oracle 基准量化 existing work 与理论上界的差距。

**正确示范** (Snake):
> "The Ideal prefetcher outperforms CTA-aware and MTA in terms of coverage by 70% and 25%, respectively."

**错误示范**:
> "Existing GPU prefetchers cannot effectively handle IMA patterns."（无数字支撑）

### 规则 I-3：三次 "However" 清空竞争空间

Introduction 中至少出现 3 次转折，每次驳倒一类现有方案：

1. **However #1**：CPU IMA prefetcher 不可直接迁移到 GPU（给出 GPU-specific 失效原因）
2. **However #2**：现有 GPU prefetcher 不处理 IMA 模式（肯定 stride 贡献，指出盲区）
3. **However #3**：唯一的 GPU IMA 尝试 (Spare Register) 的客观局限

每次 However 前必须先肯定对方贡献（规则 G5）。

**DMP 示范**：Introduction 中 3 次 "However"，每次驳倒一类方案（stride prefetcher → compiler-based → existing HW），最终清空竞争空间。

### 规则 I-4：精确否定而非笼统否定

不说"先前方案不够好"，而是指出**具体的失效机制**。

| 论文 | 精确否定示例 |
|------|------------|
| IMP | "software prefetching... not able to capture patterns that are only exposed at runtime" |
| Spare Register | "CPU prefetchers have to be thread (or warp) aware" |
| Prodigy | "pointer-based prefetchers fall short because graph algorithms use indices instead of pointers" |

**对 GRASP**：否定 CPU IMA 方案时，应给出具体计算（如 DMP 移植到 GPU 的面积开销），而非抽象声称"太贵"。

## 二、段落结构模式

### 规则 I-5：每段 "现象→原因→后果" 三段论

- **首句**：陈述事实/现象（通常有文献引用）
- **中间**：解释机制/原因
- **末句**：引出下一层次的问题或过渡

**DMP 示范**：第一段末句 "...indirect memory accesses are typically the main cause of the memory bottleneck." → 直接引出第二段对 indirect access 形式的分析。

### 规则 I-6：可选——使用显式加粗子标题

对于机制复杂的论文，可采用 Magellan 的做法：在 Introduction 内使用加粗子标题分块。

```
**Challenges:**  [具体挑战 + 量化反例]
**Goal:**  [三个目标，对应三个挑战]
**Insights and Mechanisms:**  [核心洞察，不展开细节]
**Key Results:**  [量化结果预览]
**Contributions:**  [bullet list]
```

此模式的优势：读者可快速定位任意论点，减少过渡句需求。

### 规则 I-7：Contribution 格式

- 放在 Introduction 末尾，不放 Abstract
- 3-4 条 bullet，每条独立无冗余
- 开头动词统一："We propose / demonstrate / show / evaluate"
- 或名词短语统一："A compact representation... / A low-cost design... / A comprehensive evaluation..."

**Snake 示范**：4 条 bullet，格式 "We demonstrate/propose/show..."
**Prodigy 示范**：3 条 bullet，名词短语开头 "A compact representation..."

## 三、定量 vs 定性

### 规则 I-8：Introduction 硬数字的两种用途

| 用途 | 允许 | 示例 |
|------|------|------|
| 量化问题严重性 | ✅ | "IMA 占 L1 miss 的 51%-84%" |
| 量化 gap | ✅ | "现有最好方案比 Ideal 差 70%" |
| 预报方案性能 | ⚠️ 仅在 Key Results 部分 | "geomean +35.5%" |
| 预报具体 workload 数字 | ❌ | 留给 §5 Evaluation |

**DMP 规律**：Introduction 中数据作为"旁证"（"only ≤ 20%"，"≥ 60% unsolved"），不是 claim 本身。结尾预告（"1.8× up to 5.6×"）出现在完整动机铺垫之后。

## 四、过渡与衔接

### 规则 I-9：Introduction → §2 的过渡

Introduction 的最后一段（Contributions 之前或之后）应暗示 §2 的结构，而非显式说"下一节介绍背景"。

**DMP 示范**：贡献列表第一条暗示了分类框架 → §2 Preliminary 自然展开分类。
**Snake 示范**：Introduction 末段的 Ideal 对比 → §2 自然承接这个对比的细节。

### 规则 I-10：核心洞察"点到为止"

Introduction 中提到 IMAD.WIDE 零推断检测时，只给结论（覆盖率 88-99%、1 次指令观测），不展开 ISA 细节。ISA 分析留给 §2.4。

**Magellan 示范**：Insights and Mechanisms 只给 high-level 直觉（LDG + nested loop pattern），细节留 §3。

## 五、图表

### 规则 I-11：Introduction 中的 Figure

**DMP 模式（推荐）**：Fig.1 是四联图，分别证明——
- (a) 运行时间分解 → memory stall 主导
- (b) L2 miss 分解 → indirect access 主导
- (c) Indirect access 细分 → 最严重的 pattern
- (d) 现有 prefetcher 效果 → ≥60% miss 未解决

这四个子图形成**完整的 motivation 证据链**：重要性→当前状态→问题细分→现有方案局限。

**Snake 模式**：Introduction 不内嵌 Figure，量化论证纯文字，Figure 集中在 §2。

**对 GRASP 的建议**：参考 DMP，在 Introduction 放一张双子图：(a) IMA L1 miss 占比，(b) Ideal L1D speedup。

## 六、引用策略

### 规则 I-12：Introduction 引用以批量为主

- 领域事实："Graph analytics widely use IMA [Gunrock, cuGraph, Ligra, ...]"
- 现有方案列举："stride-based GPU prefetching [Many-Thread, CAPS, Snake, ...]"
- 只在构建 "However" 否定链时逐一分析关键竞品

**Prodigy 的特殊做法**：在 Introduction 内嵌了详细的 Related Work 批评。此做法适合竞争方案较少（<5 个直接竞品）的论文。GRASP 可参考，因为 GPU+IMA 直接竞品仅 Spare Register 一个。
