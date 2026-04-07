# GRASP 论文写作计划

> 最近更新: 2026-04-04
> 目标会议: MICRO 2026
> 本文件定义论文的写作流程、方法学和依赖关系。写作时以此为准。

---

## 一、写作顺序

```
Step 0: 锁定 §1 逻辑骨架 ──── 前置验证，不产出文字
    ↓
Step 1: §2 Background & Motivation
Step 2: §3 GRASP Design
Step 3: §4 Methodology
Step 4: §5 Evaluation
Step 5: §6 Related Work
Step 6: §7 Conclusion
    ↓
Step 7: §1 Introduction ──── 全文完成后回写
Step 8: Abstract ──── 最后写
    ↓
Step 9: 图渲染 + 文字与图对齐 + 文献格式 + 全文一致性检查
```

**原则**：Introduction 和 Abstract 放最后写，因为它们是全文的 "pitch"，需要知道全貌才能写好。但 Introduction 的**逻辑骨架**（gap 论证、核心 claim、Contributions）必须在 Step 0 稳定，因为所有其他 section 的方向都依赖它。

---

## 二、Step 0：锁定 §1 逻辑骨架

### 目标

不产出 Introduction 段落文字，而是确认以下三个问题的答案已经稳定：

| # | 问题 | 当前状态 | 稳定？ |
|---|------|---------|--------|
| 1 | **三次 However 是否确定？** CPU IMA 不可迁移 / GPU prefetcher 不处理 IMA / Spare Register 过时 | paper_structure.md §1.2-§1.3 已有详细大纲 | ⚠️ 待确认 |
| 2 | **核心 claim 的数字是否稳定？** geomean speedup、coverage、accuracy、hardware cost | 实验仍在进行中，数字未最终确定 | ❌ 不稳定 |
| 3 | **Contribution list 是否定稿？** 特别是第一条（四类 Pattern 分类 vs GPU 特有分类） | paper_structure.md 有批注质疑 | ⚠️ 待确认 |

### 前置条件

Step 0 可以在实验未全部完成时进行（问题 1 和 3 不依赖实验数据），但问题 2 需要等核心实验数据稳定后再锁定。

### 产出

更新 `paper_structure.md` §1 的骨架批注，标记每个 claim 为 ✅稳定 / ⚠️待数据 / ❌需重新设计。

---

## 三、每个 Step 的标准流程

### Phase 1: 讨论（1 轮）

1. **读 writing rules**：打开 `writing_rules/§N_xxx.md`，对照当前 section 的大纲
2. **讨论段落结构**：确定每个子节的论证链、段落数、每段的功能
3. **确定图 schema**：对于图密集的 section（§2, §5），必须在此阶段确定每张图的子图数量、x/y 轴、series；对于 §3 Design 只需确定"这里放一张 flowchart"的粗粒度
4. **参考范文**：对照具体范文的对应 section（不只看 rules 的抽象总结，要看论文原文的实际写法）
5. **更新 outline**：将讨论结果写入 `paper_structure.md` 对应 section

### Phase 2: 写初稿

1. **直接写段落**：不再回到 outline 阶段，如果发现 outline 需要调整，在写的过程中调整
2. **图 placeholder**：在文字中用 `[Fig.X: description, TODO]` 占位，写好对应的分析文字
3. **遵循 rules**：每段检查是否符合 writing rules 的要求（如 E-4 数字+原因配对）

### Phase 3: 对照范文修改

1. **对照范文**：将初稿与 T1 范文（Snake/DMP/Magellan）的对应 section 并排阅读
2. **检查缺失**：是否有范文中的标准元素被遗漏（如 Evaluation 中的 "We make X key observations" 模式）
3. **调整篇幅**：确认各子节篇幅与 paper_structure.md 的分配一致

### 各 Step 适用的 Phase

| Step | Phase 1 讨论 | Phase 2 写初稿 | Phase 3 对照 | 说明 |
|------|:-----------:|:------------:|:-----------:|------|
| Step 0 | ✅ | — | — | 只做逻辑验证 |
| Step 1 (§2) | ✅ | ✅ | ✅ | 图 schema 精度要求**高** |
| Step 2 (§3) | ✅ | ✅ | ✅ | 图 schema 精度要求**低** |
| Step 3 (§4) | — | ✅ | — | 直接写，最短的节 |
| Step 4 (§5) | ✅ | ✅ | ✅ | 图 schema 精度要求**高** |
| Step 5 (§6) | ✅ | ✅ | — | 需要讨论分段策略 |
| Step 6 (§7) | — | ✅ | — | 直接写 |
| Step 7 (§1) | ✅ | ✅ | ✅ | 最重要的节，读知识星球材料 |
| Step 8 (Abstract) | — | ✅ | ✅ | 最后写，对照 §7 对称 |

---

## 四、图 Schema 精度要求

### 高精度（§2 Background, §5 Evaluation）

这两节的文字结构直接由图的布局决定。写文字前必须确定：

- 子图数量（单图？双子图？四联图？）
- x 轴内容（workload 名称？参数值？）
- y 轴内容（miss rate %？speedup ×？）
- series/分组（几个方案？颜色+hatching？）
- 是否有 GMEAN 栏

不需要最终渲染（颜色、字体、annotation 等可以后补），但上述要素必须确定。

### 低精度（§3 Design）

只需确定：
- 图类型（flowchart / 架构图 / 时序图 / table lookup 示例）
- 图的大致内容（展示哪个组件的什么行为）
- 单栏还是双栏

具体布局、数值、配色可以在写完文字后再决定。

### 无图（§4 Methodology, §6 Related Work, §7 Conclusion）

这些节不含图（§4 有 Table），文字独立于图表。

---

## 五、图与文字的协同策略

### 已有数据的图

实验数据已在 `experiment_results.md` 中的部分，现在就可以确定图 schema。写文字时在对应位置写 placeholder + 完整的分析段落。

### 数据未就绪的图

1. 在 outline 中标记 `[DATA PENDING]`
2. 先写**不依赖具体数字**的框架文字（如 "Figure X compares GRASP with five baselines across all workloads."）
3. 数据就绪后：画图 → 补充具体数字和观察 → 完善分析段落

### 概念图 / 架构图

§3 Design 中的架构图、flowchart 等不依赖实验数据，可以在 Phase 2 之后或同时制作。

---

## 六、参考资料索引

### 写作规则（每个 Step 必读）

```
writing_rules/
├── README.md                  # 跨节通用规则 G1-G6
├── §1_introduction.md         # 规则 I-1 到 I-12
├── §2_background_motivation.md # 规则 B-1 到 B-14
├── §3_design.md               # 规则 D-1 到 D-13
├── §4_methodology.md          # 规则 M-1 到 M-7
├── §5_evaluation.md           # 规则 E-1 到 E-16
├── §6_related_work.md         # 规则 R-1 到 R-11
├── §7_conclusion_abstract.md  # 规则 A-1 到 A-4, C-1 到 C-4
└── figure_design.md           # 规则 F-1 到 F-15
```

### 范文 PDF（讨论时参考）

| 论文 | 路径 | 重点参考 section |
|------|------|-----------------|
| Snake (MICRO'23) | `02_related_work/gpu_stride/Mostofi 等 - 2023 - Snake...` | §1, §2, §3, §5（全文标杆） |
| DMP (HPCA'24) | `02_related_work/ima_hw/Fu 等 - 2024 - Differential-Matching...` | §2（分类）, §3（Design 子节模式）, 图表设计 |
| Magellan (ISCA'25) | `02_related_work/ima_sw/Fu 等 - 2025 - Magellan...` | §1（显式子标题）, §5（Prefetch Potential 开头） |
| IMP (MICRO'15) | `02_related_work/ima_hw/IMP...` | §1（gap 论证）, §3（公式化）, §5（多维指标） |
| Spare Register (HPCA'14) | `02_related_work/gpu_irregular/Lakshminarayana...` | §1（GPU 特异性）, §3（ISA 级描述）, §5（per-kernel） |
| Prodigy (HPCA'21) | `02_related_work/ima_hw/Prodigy...` | §2（四层展开标杆） |

### 知识星球写作方法论

| 讲 | 适用 Step | 核心原则 |
|---|-----------|---------|
| 第 1, 2, 4, 6, 7 讲 | Step 7 (§1 Introduction) | 首句逻辑、过渡艺术、第零上位、呼应标题 |
| 第 3 讲 | Step 1-6（全文） | 第一性原理验证、不前后打脸 |
| 第 5 讲 | Step 1-6（全文） | 句句咬紧、How/Why/So What |
| 第 8 讲 | Step 1, 5 (§2, §6) | 砖块/水泥理论、文献点评结构 |

### 其他关键文件

| 文件 | 用途 |
|------|------|
| `paper_structure.md` | 论文结构权威定义（每个 Step 的 Phase 1 更新此文件） |
| `experiment_results.md` | 实验数据唯一集中源（§5 写作的数据来源） |
| `insight.md` | 11 条 Insight 索引（各 section 的论证素材） |

---

## 七、前置依赖

### 实验数据依赖

| Step | 依赖的数据 | 当前状态 |
|------|----------|---------|
| Step 0 | 无（逻辑验证） | ✅ 可开始 |
| Step 1 (§2) | L1 miss breakdown, Ideal L1D speedup, IMAD.WIDE 覆盖率 | ✅ 数据已有，但需扩充 workload |
| Step 2 (§3) | 无（机制描述） | ✅ 可开始 |
| Step 3 (§4) | Benchmark/Dataset 最终列表 | ⚠️ 待实验确定 |
| Step 4 (§5) | 全部实验结果（所有 workload × 所有 baseline） | ❌ 实验进行中 |
| Step 5 (§6) | 无 | ✅ 可开始 |
| Step 6 (§7) | 同 §5（需要最终数字） | ❌ 依赖 Step 4 |
| Step 7 (§1) | 同 §5（需要最终 claim 数字） | ❌ 依赖 Step 4 |
| Step 8 | 同 §1 | ❌ 依赖 Step 7 |

### 可并行的工作

- Step 0 + Step 2 (§3 Design) 可以**立即开始**（不依赖实验数据）
- Step 1 (§2) 可以用现有数据开始，标记 `[DATA PENDING]` 的部分
- Step 4 (§5) 必须等实验完成
- Step 5 (§6) 理论上可以提前写，但建议在 §3 之后（需要理解自己的设计才能准确定位 related work）

---

## 八、质量检查清单

每个 Step 完成后，对照以下检查：

- [ ] 段落结构是否符合 writing rules 中的模式？
- [ ] 每个定量声明是否有数据来源标注？
- [ ] 每个 "We observe" 是否配有机制解释（规则 E-4）？
- [ ] 图 placeholder 是否包含足够信息供后续渲染？
- [ ] 是否有"前后打脸"（前文说了 X 好，后文又说 X 不好，在同一维度上）？
- [ ] 是否遵循"字字有关联"（原则五）——写进去的词后文必须呼应？
- [ ] 篇幅是否与 paper_structure.md 的分配一致？
