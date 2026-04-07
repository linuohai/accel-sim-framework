# §6 Related Work 写作规则

> 标杆论文: Snake (MICRO'23) + DMP (HPCA'24)
> 补充参考: Magellan (ISCA'25), Prodigy (HPCA'21)
> 目标篇幅: 0.5 pages

## 一、位置与功能

### 规则 R-1：位置——Evaluation 之后，§6

16/16 篇分析论文 100% 将 Related Work 放在 Evaluation 之后。

**战略意图**：读者已看完技术内容和实验结果，带着具体认知读 Related Work 时能更好地理解对比点。

### 规则 R-2：开头重申独特性

Related Work 的**第一句话**重申本文的差异化定位。

**Snake 示范**：
> "Snake is the first GPU prefetcher that utilizes chains of strides."

**对 GRASP**：
> "GRASP is the first dedicated IMA prefetcher for GPU architectures, exploiting ISA-level structural information unavailable to prior approaches."

## 二、论证链

### 规则 R-3：按技术方向分段，每段 2-3 个方案

Related Work 通常分 2-3 个子段/子节，每个覆盖一个技术方向：

**推荐的 GRASP Related Work 结构**：

```
§6.1 CPU IMA Prefetchers（~3 句/方案）
    IMP → ATP → Gretch → DMP → Magellan → DX100
    定位：成熟技术，但绑定 CPU 微架构，无法直接迁移 GPU

§6.2 GPU Prefetchers（~2 句/方案）
    Many-Thread → Orchestrated → CAPS → APRES → Snake
    定位：GPU 领域活跃，但全部假设 stride/stream pattern

§6.3 GPU IMA Prefetching（~3 句/方案，只有 Spare Register）
    Spare Register → 唯一前驱，tag-based 检测，Fermi 架构局限
    定位：最接近 GRASP 的工作，需要详细比较
```

### 规则 R-4：每个方案 2-3 句精析

对每个 cited work：
1. **一句**描述其核心思路
2. **一句**指出其与 GRASP 的关系（互补/不同方向/子集）
3. **可选一句**量化差异（如"而 GRASP 不需要编译器支持"）

**Snake §6.2 示范**：每个 GPU prefetcher 2-3 句话——介绍 + 局限 + Snake 如何解决。

### 规则 R-5：排除一类方案时给理由

当排除某类方案（如 CPU prefetcher）作为 baseline 时，Related Work 是解释原因的地方。

**Snake §6.1 示范**：
> "Hardware prefetchers designed for CPUs cannot be directly applied to GPUs due to their inherent characteristics."

**DMP §VI 示范**：对 graph accelerators 单独一段，承认存在但指出不在 scope 内。

## 三、引用策略

### 规则 R-6：Related Work 采用 "单引用精析" 风格

与 Introduction 的批量引用不同，Related Work 中每个引用**单独**一句话介绍其核心思路和局限。

| 场景 | Introduction | Related Work |
|------|-------------|-------------|
| 成熟技术方向 | 批量引用 [1-5] | 逐一精析 |
| 直接竞品 | 1-2 句否定 | 2-3 句中立比较 |

**DMP 示范**：
- 批量引用用于"宣示覆盖范围"："[3], [17], [36], [39], [44], [49], [68], [71]"
- 个别分析用于"建立对比基准"：对 IMP、Ainsworth、Prodigy 各 1-2 句

### 规则 R-7：对同组先前工作的处理

如果引用自己组的先前工作（如 DMP 和 Magellan 同组），需要特别注意客观性。

**Magellan 示范**：将 DMP 定位为性能锚点而非竞争对手——"on par with DMP, but without hardware overhead"。在 Evaluation 中作为普通竞品列入图表，不给特殊地位。

## 四、措辞规范

### 规则 R-8：批评只批 "设计约束"

**允许的批评维度**：overhead / compatibility / invasiveness / scalability / scope limitation

**DMP 对竞品的批评示范**（措辞级别）：
- "such methods may greatly inflate kernel size" (SW prefetching)
- "requires recompilation and has limited compatibility with legacy workloads" (compiler-based)
- "requires heavy modification of the core design, which limits its application" (run-ahead)

**禁止**直接说"它们性能差"——性能比较留给 §5 Evaluation 用数据说话。

### 规则 R-9：措辞层次

| 关系 | 措辞 | 示例 |
|------|------|------|
| 无关/互补 | "orthogonal to" / "complementary to" | "Snake focuses on stride chains, which is orthogonal to GRASP's IMA focus." |
| 不同假设 | "assumes" / "targets" | "CAPS targets CTA-level stride patterns and explicitly excludes indirect access." |
| 有关但不足 | "limited to" / "does not capture" | "Spare Register is limited to single-level load pairs on Fermi architecture." |
| 直接改进 | "extends" / "generalizes" | 一般不用——这会暗示前人工作不好 |

## 五、篇幅控制

### 规则 R-10：0.5 page，不超过 15 个引用

Related Work 不应超过半页（MICRO 格式下约 1 栏 + 少许）。

**Snake 示范**：§6 约 0.5 page，分 CPU/GPU 两小节。
**DMP 示范**：§VI 约 1 page（HPCA 格式较宽松），分 SW/SW-HW/HW/Graph Accelerator 四段。

对于 MICRO 2026 的 11 页限制，Related Work 应严格控制在 0.5 page。

### 规则 R-11：不重复 Introduction 的否定

Introduction 中已经用 "However" 驳倒的方案，Related Work 中**不重复论证**，只补充技术细节和引用。

**反面教材**：如果 Introduction 已经论证了"CPU IMA prefetcher 不可迁移到 GPU"，Related Work 不应再次论证这一点，只需说"See §1 for a discussion of migration barriers."
