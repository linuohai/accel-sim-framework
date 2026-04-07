# §7 Conclusion + Abstract 写作规则

> 标杆论文: Snake (MICRO'23) + DMP (HPCA'24)
> 补充参考: Magellan (ISCA'25), IMP (MICRO'15)
> 目标篇幅: Conclusion 0.5 pages, Abstract ~200 词

## 一、Abstract

### 规则 A-1：五句话模板

Abstract 严格遵循五步结构，每步 1-2 句：

```
S1: 问题/现象（IMA 在 GPU 上是严重瓶颈）
S2: 现有方案的具体缺陷（CPU IMA 不可迁移 + GPU prefetcher 忽视 IMA）
S3: 本文方案一句话概括（"We propose GRASP, a ..."）
S4: 核心机制简述（IMAD.WIDE 零推断检测 + index-data two-step pipeline）
S5: 量化结果 + 实用性声明
```

**DMP 示范**：严格五步——问题→缺陷→方案→机制→结果。
**Snake 示范**：问题→TLP 局限→现有 prefetcher 局限→Snake 三步→结果数字。

### 规则 A-2：三层数字——均值 + 峰值 + 开销

Abstract 中必须同时出现三个维度的数字：

| 维度 | 功能 | 对 GRASP 的映射 |
|------|------|----------------|
| **均值** | 代表性 | "geomean speedup of 35.5%" |
| **峰值** | 潜力 | "up to 138.6% on CC-flickr" |
| **开销** | 可行性 | "~2.3 KB per SM" |

**DMP 示范**：1.8× avg + up to 5.6× + 0.9KB storage

三个维度构成"性能-可行性"的完整背书，缺一不可。

### 规则 A-3：Abstract 不渲染背景

Abstract 直奔主题，不花超过一句话在背景上。

**正确**："Indirect memory access (IMA) is a critical bottleneck for GPU graph analytics, causing 51-84% of L1 cache misses."
**错误**："Modern GPUs are widely used in many applications. Graph analytics is an important domain. These applications often involve irregular memory access patterns..."

### 规则 A-4：约 200 词

MICRO 格式 Abstract 约 200 词（±20%）。不超过 250 词。

## 二、Conclusion

### 规则 C-1：无新信息原则

Conclusion **严格不引入任何新内容**，是 Abstract 关键数字的重申。

**Snake 示范**：3 句话——(1) Snake 是什么，(2) 四个关键数字（75% accuracy, 17% IPC, 17% energy, 1% L1 overhead），(3) 结束。没有 future work。

### 规则 C-2：3-5 句话结构

```
S1: 一句话概括 GRASP 是什么（动机 + 方案）
S2: 核心技术要点（IMAD.WIDE 检测 + two-step prefetch）
S3: 关键量化结果（geomean speedup + coverage + accuracy）
S4: 硬件开销声明（~2.3 KB/SM, X% of L1 cache）
[S5: 可选——展望性声明（不量化，不承诺）]
```

### 规则 C-3：不写 Future Work（MICRO 风格）

MICRO 论文倾向于简洁结尾，不添加 future work。如果必须提及，用一句不量化的展望性声明：

**DMP 示范**：
> "We believe DMP would encourage the next generation of efficient hardware prefetchers targeting more general and complex access patterns."

这句话不量化、不承诺，但通过 "next generation" 暗示研究影响力。

**对 GRASP**（如果需要）：
> "We believe GRASP's ISA-level detection approach opens new opportunities for hardware prefetching in emerging GPU workloads beyond graph analytics."

### 规则 C-4：Conclusion 不引用文献

Conclusion 中不引用任何文献。这是约定俗成的——Conclusion 是自己工作的总结，不需要外部支撑。

## 三、Abstract 与 Conclusion 的关系

### 规则 AC-1：对称结构

Abstract 和 Conclusion 应是对称的：

| 要素 | Abstract | Conclusion |
|------|---------|------------|
| 问题 | 明确描述 | 一句话回顾 |
| 方案 | 一句话概括 | 一句话概括（可以更技术化） |
| 机制 | 核心机制简述 | 核心技术要点 |
| 结果 | 三层数字 | 关键数字重申 |
| 展望 | 无 | 可选一句 |

### 规则 AC-2：数字必须一致

Abstract 和 Conclusion 中出现的数字必须完全一致。如果 Abstract 写 "35.5% geomean speedup"，Conclusion 也必须是 35.5%，不能四舍五入为 36%。

## 四、写作时序

### 规则 AC-3：Abstract 最后写

虽然 Abstract 出现在论文最前面，但应该在全文完成后最后撰写。原因：

1. Abstract 需要精确的结果数字（来自 §5）
2. Abstract 的问题表述需要与 §1 Introduction 完全一致
3. Abstract 的方案描述需要与 §3 Design 的术语一致

同理，Conclusion 也应在 Abstract 之后写——两者必须对称，先写哪个都行，但必须交叉检查一致性。
