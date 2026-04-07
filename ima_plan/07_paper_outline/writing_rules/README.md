# GRASP 论文写作规则体系

> 最近更新: 2026-04-04
> 目标会议: MICRO 2026
> 基于 16 篇体系结构论文的实证分析提炼

## 本目录结构

| 文件 | 覆盖范围 |
|------|---------|
| `§1_introduction.md` | Introduction 漏斗论证链、gap 量化、Contribution 格式 |
| `§2_background_motivation.md` | Background & Motivation 四层展开、分类框架、图驱动动机 |
| `§3_design.md` | Design 自顶向下结构、组件子节模式、Worked Example |
| `§4_methodology.md` | Methodology 分块格式、Baseline 定义规范 |
| `§5_evaluation.md` | Evaluation 顺序策略、观察编号模式、Ablation 格式 |
| `§6_related_work.md` | Related Work 位置、引用策略、批评措辞 |
| `§7_conclusion_abstract.md` | Abstract 五句话模板、Conclusion 无新信息原则 |
| `figure_design.md` | 图表设计六大原则、颜色系统、Caption 写法 |

## 参考论文权重

| 层级 | 论文 | 权重 | 理由 |
|------|------|------|------|
| **T1** | Snake (MICRO'23) | ★★★★★ | 同期刊、同领域 GPU prefetcher SOTA |
| **T1** | DMP (HPCA'24) | ★★★★★ | 最新 IMA prefetcher，图表设计标杆 |
| **T1** | Magellan (ISCA'25) | ★★★★☆ | 最新 IMA 工作，Introduction 结构精良 |
| **T2** | IMP (MICRO'15) | ★★★☆☆ | 经典 IMA prefetcher，同期刊 |
| **T2** | Spare Register (HPCA'14) | ★★★☆☆ | 唯一 GPU+IMA 前驱 |
| **T2** | Prodigy (HPCA'21) | ★★★☆☆ | Background/Motivation 写法标杆 |
| **T3** | CAPS, APRES, Gretch, Tyche, ATP, Orchestrated, Many-Thread, DX100 | ★★☆☆☆ | 结构共性验证 |

**权重使用规则**：当 T1 论文间出现写法冲突时，选更好的那个（不取平均）。T3 论文仅用于验证"共性"是否成立，不作为风格标杆。

## 跨节通用规则

### 规则 G1：数字密度与节功能匹配

| 节 | 量化占比 | 功能 | 标杆 |
|---|---------|------|------|
| Introduction | ~70% | 建立 gap（必须数字支撑） | Snake, DMP |
| Background | ~85% | 动机论证（图驱动） | Snake |
| Design | ~20% | 机制描述（定性为主） | DMP |
| Methodology | ~10% | 工具/配置说明 | Snake |
| Evaluation | ~80% | 结果呈现 | DMP |
| Related Work | ~0% | 定性对比 | Snake |

### 规则 G2：过渡隐式化

节与节之间用最后一段的逻辑方向隐式引出下一节。**禁止**出现 "本节介绍了 X，下节将介绍 Y" 这类模板句。

- Snake §2 结尾："Therefore, a prefetcher based on frequent chains of strides enhances prefetching opportunities." → §3 直接开始 Snake 设计
- DMP §II 结尾：分支误预测分析自然引出 §III 的 Repetition Filter

**标准过渡模式**：末段的结论句 = 下一节的前提。

### 规则 G3：引用策略双轨制

| 场景 | 策略 | 示例 |
|------|------|------|
| 证明某领域事实 | 批量引用 [1-5] | "stride-based prefetching [15, 25, 27, 29, 37] reduces..." |
| 分析直接竞品 | 单引用精析（1-2 句） | "IMP [Yu et al.] detects... but requires accumulating address sequences." |
| 支撑自己的设计决策 | 不引用 | Design 节的 novelty 不需要引用支撑 |

### 规则 G4：语态与语气

- 技术描述用**主动语态**："We propose", "GRASP detects", "The CD monitors"
- 负面结果用**被动语态**软化："Performance degradation is observed in..."
- 技术声明**严格限定范围**："for most workloads", "in the evaluated configurations"
- **禁止**绝对化表述："always", "never", "best possible"
- 批评竞品**只批设计约束**（overhead/compatibility/invasiveness），不说"性能差"——性能比较留给 Evaluation 用数据说话

### 规则 G5："先肯定再否定" (However 策略)

讨论 existing work 的固定模式：

1. 先认可贡献："Prior research shows stride-based prefetching is effective for regular patterns..."
2. 用 "However" 引出局限："However, these approaches assume fixed stride patterns and cannot capture IMA's data-dependent addressing."

此模式贯穿 Abstract、Introduction、Related Work，避免"打倒前人"的攻击性。

### 规则 G6：16/16 结构共识

以下结构规律在全部 16 篇分析论文中 100% 一致：

1. Related Work 置于 Evaluation **之后**
2. Design 节采用 "Overview → 组件展开 → 示例/Cost" 的自顶向下结构
3. Methodology 与 Evaluation 分离（即使 Methodology 很短）
4. 每个 Evaluation 子节至少有一张对应的 Figure
