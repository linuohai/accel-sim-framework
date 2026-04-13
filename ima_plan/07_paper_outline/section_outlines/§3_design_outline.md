# §3 GRASP Design — 段落级大纲

> 最近更新: 2026-04-08 (用户 review 完成 + 7 项 OQ 已解决，进入 Step D)
> 状态: Step C 完成 → Step D 进行中（写 LaTeX 到 main.tex §3）
> 目标会议: MICRO 2026 (ACM sigconf, 11 页 body)
> 章节预算: 3.5 pages
> 写作规则: `writing_rules/§3_design.md` (D-1 ~ D-13) + `writing_rules/figure_design.md`
> 来源决策记录: `.claude_global/plans/clever-questing-hearth.md`

---

## 0. 章节概览

### 结构定型（6 子节）

| 子节 | 标题 | 长度 | 图（尺寸） | 主旨 |
|------|------|------|-----------|------|
| §3.1 | Overview | ~0.5 page | Fig 7 + Fig 8 单栏（column-stacked in 单 float） | 系统定位 + spatial 架构图 + temporal 算法流 |
| §3.2 | **Detecting Chains at Issue** | ~0.6 page | Fig 9 单栏 | issue stage 检测 LDG→IMAD.WIDE→LDG，零推断 |
| §3.3 | **Storing Chains Compactly** | ~0.8 page | Fig 10 单栏 | (base,scale) 归并 PC 膨胀 + per-CT-entry stride 学习（含 IST） |
| §3.4 | **The Two-Step Prefetch** | ~0.8 page | Fig 11 单栏 | IPU + PRB + DPU 隐藏 ~1120cy 双 round-trip — **章节 climax** |
| §3.5 | **Adaptive Throttling** | ~0.5 page | Fig 12 单栏 (bottom-right) | 滑动窗 accuracy + 自适应 MSHR 阈值 + cooldown |
| §3.6 | Hardware Budget | ~0.2 page | Table 2 | ~1.4 KB/SM, 与 IMP/DMP 对比 |

**标题风格（2026-04-08 rename）**: action/concept-oriented，不列组件缩写。参考 Snake §3（"Detection"/"Prefetching"/"Throttling"）和 DMP 的概念化标题风格。

**所有图改为单栏**（用户决定，2026-04-08）：双栏在 §3 占的篇幅过大且效果不好。Captions 也全部收紧到 1-2 句（F-9/F-10）。

**总计**: ~3.4 pages（在 3.5 预算内）, 6 figures + 1 table。

### 叙事弧

```
§3.1 set the stage (Fig A 架构 + Fig B 算法流)
   ↓
§3.2 detection (building block)
   ↓
§3.3 storage + learning (building block)
   ↓
§3.4 ★ TWO-STEP PIPELINE — climax ★ (核心贡献)
   ↓
§3.5 throttling refinement
   ↓
§3.6 cost (短收尾)
```

**关键设计**: 没有 anticlimactic recap。Fig B (Flowchart) 放 §3.1 而不是结尾，避免 §3.4 的 climax 被后续 6-step recap 稀释。

### 4 个已锁定的设计决策（用户拍板）

| 维度 | 选择 | 实现含义 |
|------|------|---------|
| **组件子节布局** | 4 组件子节，时间执行顺序：CD → CT&TT(含 IST) → IPU&DPU → TC | IST 折入 §3.3（非独立成节） |
| **Throttle 版本** | `tc_mode=5` (Dynamic) | 描述 sliding-window accuracy + adaptive MSHR threshold + cooldown |
| **CT/TT key 叙事** | 代码现状：CT 由 `index_PC` 索引，TT 由 `(base, scale)` CAM 归并 | PC 归并发生在 TT 层级（多个 CT entry 的 `tt_idx[]` 共享同一 TT entry） |
| **Pair Table 披露** | §3 完全隐藏，只描硬件 CAM 视角 | trace-driven 简化在 §Methodology 中说明 |

---

## §3.1 Overview (~0.5 page, Fig A 双栏 + Fig B 单栏)

**论证目标**: 30 秒建立 GRASP 的 mental model——通过 Fig A (spatial: 组件在 SM 中的位置 + 数据流) 和 Fig B (temporal: 算法 6 步的执行顺序) 双视角"展示一下"GRASP 整体设计。**这不是 worked example——只是 set the stage**。

### 段落规划（D-2 精神保留：核心定位句 ≤ 3 句话）

| 段 | 功能 | 内容要点 | 字数 |
|---|------|---------|------|
| ¶1 | 系统定位（D-2） | (a) "GRASP is a per-SM hardware prefetcher operating at the instruction issue stage." (b) "It detects IMA chains via the LDG→IMAD.WIDE→LDG dependency, then issues a two-step prefetch—index first, then data—predicted from per-PC stride." (c) "Fig.~\\ref{fig:arch} shows the hardware components; Fig.~\\ref{fig:flow} shows the algorithmic flow." | ~70 |
| ¶2 | Fig A 解读 (spatial view) | 描两条路径：(1) **Training path**（实线）：tracked-warp 指令进入 issue → CD 识别 chain → 写 CT/TT；(2) **Prefetch path**（虚线）：demand load → CT lookup → IPU 发 index PF → PRB → fill → DPU 计算 data 地址 → data PF → L1。关键标注：CD 位于 issue stage（不在 L1 旁），CT/TT/IPU/DPU/PRB/TC 集中在 L1 cache 旁边作为 sidecar。所有组件 per-SM 共享（非 per-warp 复制）。 | ~110 |
| ¶3 | Fig B 解读 (temporal view) + 章节导读 | 用 Fig B 的 6 步把 §3.2-§3.5 串成时间线："The chain progresses through six steps: (1) detect (CD), (2) register (CT/TT), (3) learn stride, (4) issue index PF (IPU), (5) compute and issue data PF on fill (DPU), (6) demand hit. Throttle Control (TC) gates step (5) when MSHR is congested." 自然引出 §3.2 第一句。 | ~90 |

**Fig A** (`figures/3-Design/Top-Level_Architecture_Diagram.pdf`, **双栏 7.0"**): Per-SM 视角，4 组件位置 + Training/Prefetch 双路径 + 每个 box 的 entry 数和总存储（~1.4 KB/SM）。**TC 在 Fig A 右下角**作为 prefetch queue 的 gate。参考 DMP Fig 10 / Snake Fig 14 风格。

**Fig B** (`figures/3-Design/Flowchart.pdf`, **单栏 3.5"**): 6 步算法流程图。

**与 §2 衔接**: §2.5 末尾 "...a single shared table can serve all 64 warps on an SM, because every warp executes the same IMAD.WIDE instruction at the same PC." → §3.1 ¶1 第一句直接接 "GRASP realizes this observation as a per-SM hardware prefetcher..."。

**与 §3.2 衔接**: 末尾不出现 "the next subsection introduces CD"。改为以 Fig B 第 1 步自然引出："We now describe each step, starting with how the chain detector identifies the LDG→IMAD.WIDE→LDG sequence at issue."

**版面注意**: §3.1 双图（双栏 + 单栏）占用空间较大，文字预算压缩到 ~270 words。LaTeX 用 `\begin{figure}[t]` 顶部漂浮，Fig A 用单独 figure 块、Fig B 也单独 figure 块（避免 subfigure 复杂度）。如果版面紧张可考虑 Fig B 用 `wrapfigure` 嵌入文字旁。

---

## §3.2 Detecting Chains at Issue (~0.6 page, Fig 9 单栏)

**论证目标**: 让读者相信 CD 能在 issue stage 准确识别 IMA 链，且硬件代价小（共享 FIFO + tracked-warp）。

### 段落规划（D-4 五段结构）

| 段 | 五段角色 | 内容要点 | 字数 |
|---|---------|---------|------|
| ¶1 | **目标** (Goal) | "The goal of the Chain Detector is to identify the LDG→IMAD.WIDE→LDG sequence as soon as it issues, *before* any of the loads complete." 解释为什么必须在 issue stage：要预取下一次迭代的 index 必须先知道目标 PC。 | ~50 |
| ¶2 | **约束** (Constraint) | "A naive approach would track per-warp register state for all 64 warps, which is prohibitive." 两个具体困难：(a) 64 warps × 多 in-flight LDG → 状态爆炸；(b) GPU 多 warp 交织让 register-history 算法很难匹配。可呼应 §2.4。 | ~70 |
| ¶3 | **洞察** (Insight) | "We exploit two observations." (1) IMAD.WIDE 在 issue stage 携带 base 和 scale 立即数（来自 §2.5）。(2) 同一 PC 在所有 warp 上执行同一 chain——只追踪少量 warp 就能采样到完整链。这两点把检测从"统计推断"降为"模式匹配"。 | ~70 |
| ¶4 | **机制** (Mechanism) | 配 Fig C 描述 3 步：**Step 1** tracked warp 发 LDG → CD 把 (PC, dest_reg) push 进 FIFO。**Step 2** tracked warp 发 IMAD.WIDE → CD 在 FIFO 中查 src_reg → 命中则记下 (index_PC, base, scale, IMAD_dest_reg)。**Step 3** tracked warp 发 LDG 且 src_reg == IMAD_dest_reg → chain 确认，写入 CT/TT。强调 FIFO write-invalidation：非 IMA 指令覆写 dest_reg 时清除该 FIFO entry（如果 CD 压力大时，读失效的方式清除 entry，即目的寄存器被非 IMA chain 指令消费，有误消除风险，但在 CD 紧张时也可以被看做是一种节流机制）（Insight #10，保证正确性）。 | ~140 |
| ¶5 | **参数** (Params) | "We size the CD FIFO at 20 entries and track 2 warps per SM, based on a sensitivity analysis (§5)." Justify: SpMV ×16 展开需要 17+ 槽位，20 留余量。tracked warp = 2 是 PC 覆盖度 vs 硬件成本的折中。 | ~50 |

**Fig C** (`figures/3-Design/Chain_detect.pdf`, 单栏 3.5"): 多 warp 时间线 + tracked warp 高亮 + FIFO 状态变化 + 3 步匹配标注。引用方式：在 ¶4 开头 "As shown in Fig.~\\ref{fig:cd}, ..."。

### 关键技术声明
- "Zero-inference" — 来自 §2.5 IMAD.WIDE 的结构性优势
- "Per-SM shared, not per-warp replicated" — Insight #6
- "Write-invalidation guarantees correctness" — 防误检 (Insight #10)

### Defensive note (D-13)
不单独写防御段，把"为什么不每个 warp 都追踪"放在 ¶2/¶5 中自然回应。

### 数字溯源
- FIFO 20 entries → `grasp_prefetcher.h:50` `cd_fifo_depth = 20`
- tracked warps = 2 → `grasp_chain_detector.{h,cc}`
- SpMV ×16 → `01_ima_characterization/sass_analysis/`

---

## §3.3 Storing Chains Compactly (~0.8 page, Fig 10 单栏)

**论证目标**: 让读者理解 CT/TT 如何用极小的硬件成本（~860 B）解决两个核心问题：(a) loop unrolling 导致的 PC 膨胀；(b) per-PC stride 学习的跨 CTA 污染。

### 段落规划（最长子节，7 段）

| 段 | 五段角色 | 内容要点 | 字数 |
|---|---------|---------|------|
| ¶1 | **目标** | "The Chain Table (CT) and Target Table (TT) jointly store every detected IMA chain in compact form, indexed for O(1) lookup at demand-load time." 强调 "compact"——60+ unrolled PC 不能各占一项。 | ~50 |
| ¶2 | **约束** | 引入 PC 膨胀问题：SpMV ×16 展开产生 60+ 不同的 IMAD.WIDE PC，每条都用同一 (base, scale=4)。BFS ×4 类似。如果每个 PC 都占独立 entry，要么 32-entry CT 不够、要么需要数百 entries。提一句 prior CPU prefetchers（IMP, DMP）没遇到这个问题因为 CPU 没这么激进的展开。 | ~80 |
| ¶3 | **洞察** | "We observe that loop unrolling preserves the constant operands of IMAD.WIDE while only changing the destination/source registers." (base, scale) 是 loop-invariant，可作为天然归并 key（Insight #4）。引出 CT/TT 双表分工：**CT 负责 index PC dispatch（每个 index_PC 一项，含 stride 状态）、TT 负责 (base,scale) coalescing（多 CT entry 的 `tt_idx[]` 指向同一 TT entry）**。这是 PC 归并发生的层级。 | ~100 |
| ¶4 | **机制 — CT** (配 Fig D 上半) | CT key = `index_PC`；CT entry = {data_PC list, tt_idx[3], stride state, confidence}。说明为什么 tt_idx 是数组（最多 3）：支持 BC reverse 的 one-to-many（1 index → 3 data targets，Insight #5）。LRU 替换。Kernel 切换时按 kernel name 比较清空（避免指针比较 bug，Insight #11）。 | ~110 |
| ¶5 | **机制 — TT** (配 Fig D 下半) | TT key = `(base, scale)`，CAM lookup。TT entry = {base, scale}。具体例子：SpMV 中 PC 0x03d0、0x03e0、0x03f0 三个 IMAD.WIDE 都用 c[0x0][0x178] + scale=4 → CT 中 3 个 entry 的 tt_idx[0] 全 = 0 → TT[0] = (x_base, 4)。这就是 "60+ PC → 1 TT entry" 的归并效果。 | ~110 |
| ¶6 | **机制 — Stride 学习 + Speculative stride hint（IST 折入）** | "Embedded in each CT entry is a per-PC stride state, updated when the tracked warp re-executes the same index_PC." 每次 demand load 时把 (current_addr - prev_addr) 比对前一次观察，连续 N 次相同则 freeze。Cross-CTA cleanup：warp 退出时清除 tracked state，防止旧 CTA 的尾部和新 CTA 的头部之间产生伪 stride（Insight #11，PT hit rate 29%→60%）。**Speculative stride hint**: 编译器可以通过专用的 ISA 接口（如 IMAD.WIDE 的 hint bit 或 kernel metadata）把 element_size 直接传给 GRASP，让 IST 跳过观测阶段直接 freeze stride，缩短首迭代的训练延迟。CC/VC 等 stride 学习收敛慢的 workload 受益最大。 | ~150 |
| ¶7 | **参数** | "We size CT at 32 entries, TT at 8 entries; stride confidence threshold = 2." Justify: 经验上 1 个 kernel 的活跃 chain 数 ≤ 8，CT 32 留余量避免 LRU 抖动。Confidence=2 在 §5 sensitivity 验证最优。 | ~50 |

**Fig D** (`figures/3-Design/CT_TT.pdf`, 单栏 3.5"): 上半 SASS 代码片段（3 条 IMAD.WIDE 不同 PC 共享 base/scale）；中间 CT 表（3 行，tt_idx 全指向 0）；下半 TT 表（1 行 (x_base, 4)）；箭头汇聚展示归并。引用："Fig.~\\ref{fig:tables} illustrates this with a SpMV example."

### 关键技术声明
- "(base, scale) is the natural merge key" — Insight #4
- "One-to-many index→data fan-out via tt_idx[3]" — Insight #5（BC reverse）
- "Cross-CTA stride pollution fix" — Insight #11

### 数字溯源
- CT 32 / TT 8 → `grasp_prefetcher.h:53-54` `ct_size = 32; tt_size = 8`
- tt_idx[3] → `grasp_tables.h` (chain entry struct)
- Confidence threshold = 2 → `grasp_prefetcher.h:59` `ist_confidence = 2`
- Stride pollution 修复证据 → `experiment_progress.md` S7f

---

## §3.4 The Two-Step Prefetch (~0.8 page, Fig 11 单栏) — **章节 climax**

**论证目标**: 让读者理解为什么"两步预取"是 GRASP 的核心价值——它是把 ~400 cycle 的双 L2 round trip 隐藏掉的关键机制。**这是 §3 的高潮段，two-step pipeline 是论文的核心贡献，写法上要让 §3.4 的 punch 落地（特别是 ¶6 的 cycle 对比）**。

### 段落规划

| 段 | 五段角色 | 内容要点 | 字数 |
|---|---------|---------|------|
| ¶1 | **目标** | "The Index/Data Prefetch Units (IPU/DPU) translate detected chains into actual L1 fills, with the Prefetch Request Buffer (PRB) serving as the bridge between them." 一句话明确"两步预取"是核心，PRB 是 cross-step 状态的载体。 | ~50 |
| ¶2 | **约束** | 关键挑战：data address 依赖 index 返回值（data dependency）。CPU prefetcher 用 lookahead PC 解决，但 GPU 上 ~64 warps 同时 in-flight → per-warp lookahead 状态爆炸。Snake/CAPS 等 GPU stride 预取器只能预测 stride，无法处理 data-dependent 地址。这是 GPU 上为什么没有真正的 IMA prefetcher 的根本原因。 | ~80 |
| ¶3 | **洞察** | "We split the prefetch into two pipelined stages: index prefetch on demand observation, data prefetch on index fill." Index PF 用 stride 预测下一个 index 地址，Data PF 等到 index PF fill 才计算 data 地址（用 IMAD.WIDE 公式）。两步彼此重叠，PRB 携带 (base, scale) 元数据穿越 fill latency。 | ~80 |
| ¶4 | **机制 — IPU** (配 Fig E 上半) | demand load 命中 CT 且 stride_valid 时触发：`pf_addr = current_addr + stride × distance`。PRB 分配一个 entry，snapshot CT 当时的 `tt_idx[]`（避免 CT eviction race）。INDEX_PF 入 prefetch queue。 | ~100 |
| ¶5 | **机制 — DPU + ACU**（fill path） | INDEX_PF fill 返回 → 在 PRB 中找到对应 entry → 读 fill 中的 index value → 通过 PRB 的 `tt_idx[]` 查 TT → 计算 `data_addr = base + value × scale`（ACU 内置）→ 发出 DATA_PF。强调 PRB 的双重职责：(a) 状态承接（穿越 fill latency），(b) sector tracking（一个 PRB entry 可对应多个 sector fill）。 | ~120 |
| ¶6 | **时序对比** (引用 Fig E) | 用 Fig E 的双行时间轴：上行 demand-only ~1120 cycles（两次串行 ~560cy）；下行 GRASP ~0 cycles（两次 prefetch 完全 overlap 在 demand 之前）。这是 GRASP 的核心 win 来源——这一段是 §3 的 punch line。 | ~90 |
| ¶7 | **参数** | "We set distance = 1 by default." **设计选择的依据**: GPU IMA workload 的 active-lane 数量在迭代之间可能急剧变化（典型从 32 lane 跌到 4-8 lane）。如果 prefetch distance 大（如 4），lane mask 不匹配会导致每次 burst 浪费 24-28 个 prefetch；distance=1 即使全部不匹配，单 iter 损失也 ≤10 个无效 prefetch。这是 GPU 上 SIMT 调度模型对 lookahead 的天然约束，与 CPU prefetcher 的 distance scaling 思路相反。**PRB capacity = 512** entries（每 entry 仅存 ct_idx ≈ 1B，总开销 ~512 B）。这两项参数的 sensitivity 在 §5 中有完整曲线。 | ~120 |

**Fig E** (`figures/3-Design/prefetch_pipe.pdf`, **双栏 7.0"**): 双行时间轴对比 demand-only vs GRASP（含 IPU→PRB→fill→DPU→data fill 的完整流）。引用：在 ¶4/¶6 双引用。

### 关键技术声明
- "Two-step pipeline hides ~400 cycles" — 用真实 cycle 数据
- "PRB carries (base, scale) across fill latency" — 解释为什么需要 snapshot
- "INDEX_PF/DATA_PF 是不同的 prefetch kind" — 区别于单一 stride 预取

### 公式三明治 (D-6)
在 ¶5 中嵌入 IMA address 公式：

> 文字 → "When the index prefetch fill returns, the ACU computes the data address using the operands captured in the PRB:" → 公式 `data_addr = base + index_value × scale` → 文字 → "where `base` and `scale` are read from the TT entry referenced by the PRB snapshot."

### 数字溯源
- distance=1 设计依据 → 用户 Q3 答复（active-lane 变异性）
- ~560 cy round-trip → `04_prefetcher_design/extra_pattern/small_1sm_cta5/`
- PRB capacity 512 → 用户 Q4 答复（每 entry ~1B 资源极小）

---

## §3.5 Adaptive Throttling (~0.5 page, Fig 12 单栏 bottom-right)

**论证目标**: 让读者相信 GRASP 的 throttle 不是简单 MSHR 阈值——而是一个自适应反馈机制，能应对 BFS（高 accuracy 期）和 SpMV（低 accuracy 期）两种 workload 的差异。

> ✅ **数据来源已确认**: tc_mode=5 (D5b) 的多 workload 评估数据在 `06_evaluation_plan/throttle_control_results.md` 的 D5b 表（覆盖 cit-Patents / web-Google / flickr / roadNet-CA / soc-LiveJournal1 × 6 算法）。

### 段落规划

| 段 | 五段角色 | 内容要点 | 字数 |
|---|---------|---------|------|
| ¶1 | **目标** | "Throttle Control (TC) prevents prefetch-induced cache pollution when MSHR contention is high, without blocking useful prefetches in benign phases." 既要防污染、又要不杀好预取。 | ~50 |
| ¶2 | **约束** | "A static MSHR threshold either over-throttles (blocking useful prefetches) or under-throttles (causing pollution)." 引用 §5 sensitivity 的 binary cliff 现象（mode=0 thr=80 在 SpMV 上 3M RFAIL）。说明 workload 之间和同一 workload 不同阶段的 prefetch 质量都在变化。 | ~70 |
| ¶3 | **洞察** | "We observe a strong inverse correlation between window-level prefetch accuracy and the optimal MSHR threshold." 高 accuracy 期 → 放宽阈值；低 accuracy 期 → 收紧阈值。这是 Dynamic TC 的核心反馈机制。 | ~70 |
| ¶4 | **机制** (配 Fig F) | 三步：(1) **Sliding window** (~5000 cycles)：跟踪 L1 的 pf_useful / pf_useless 比例 → 计算 window accuracy。(2) **Linear interpolation**：accuracy ≤ acc_lo (30%) → eff_thr = mshr_lo (50%)；accuracy ≥ acc_hi (60%) → eff_thr = mshr_hi (90%)；中间线性插值。(3) **Cooldown timer**：MSHR 占用率超过 eff_thr 时，触发 200-cycle cooldown，期间 DATA_PF 全部 suppress；INDEX_PF 始终豁免（pipeline 正确性要求）。 | ~140 |
| ¶5 | **参数** | window=5000 cy, acc_lo/hi=30/60%, mshr_lo/hi=50/90%, cooldown=200cy。这些参数在 §5 sensitivity 给 trade-off 曲线。 | ~50 |

**Fig F** (`figures/3-Design/throttle.pdf`, 单栏 3.5"): 上图 MSHR Occupancy vs effective threshold（红色虚线随 accuracy 浮动）+ cooldown 区间用阴影标注；下图 sliding window accuracy。引用："Fig.~\\ref{fig:tc} illustrates the feedback loop."（已 cairosvg 从 throttle.drawio.svg 转换）

### 关键技术声明
- "Sliding-window accuracy feedback adapts to phase changes"
- "INDEX_PF exempt for pipeline correctness"
- "Cooldown provides drain windows for cache to absorb pending prefetches"

### 数字溯源
- tc_mode=5 实现 → `grasp_prefetcher.cc:790-825`
- window=5000, acc_lo/hi=30/60, mshr_lo/hi=50/90 → `grasp_prefetcher.h:73-76`
- cooldown=200 → `grasp_prefetcher.h:73` `tc_cooldown_cycles = 200`

---

## §3.6 Hardware Cost (~0.2 page, Table 2)

**论证目标**: D-12 规则——用一个 table 量化所有组件的存储开销，证明 GRASP 是 negligible overhead，并以此作为 §3 的简洁收尾。

### Table 2: GRASP Hardware Budget (per SM)

> **数字来源**: `04_prefetcher_design.md` §7.1（用户 Q7 答复 + Phase 1 capacity probe 后的实际配置）

| Component | Entries | Per-Entry | Total | Notes |
|-----------|:-------:|:---------:|------:|-------|
| CT (Chain Table) | 32 | ~17 B | 544 B | index_PC tag(24b) + tt_idx[3](≈9b) + iter_stride(16b) + stride_obs[2](76b) + meta(≈12b) |
| TT (Target Table) | 8 | ~5 B | 40 B | base_addr_tag(32b) + scale(3b) + valid(1b) |
| PRB (Prefetch Request Buffer) | 512 | ~1 B | 512 B | valid + ct_idx (4-7 bit/entry); 仅记录 in-flight index PF 的最小信息 |
| CD FIFO (Register Tracker) | 20 | ~15 B | 300 B | dst_reg(8b) + type(2b) + PC(24b) + ima_info; per-SM 共享, 2 tracked warps |
| SM global state | 1 | ~2 B | 2 B | tracked_warp_ids[2] + priority + training_frozen |
| TC state (sliding window) | — | — | ~20 B | window accuracy counters + cooldown timer |
| **Total** | | | **~1.4 KB/SM** | **占 128 KB L1D 的 ~1.1%** |

**Per-warp 等效**: 1418 B / 64 warps ≈ **22 B/warp** (远小于单个寄存器分配)

**对照表**:
| Prefetcher | Storage/SM | 备注 |
|------------|-----------|------|
| IMP (2015) | ~0.7 KB | per-core (不能 amortize 到多线程) |
| Tyche (2024) | ~0.57 KB | per-core |
| Spare Register (2014) | ~1.365 KB | GPU 但 per-warp |
| **GRASP** | **~1.4 KB** | per-SM 共享 64 warps → ~22 B/warp |

### 段落规划

| 段 | 内容要点 | 字数 |
|---|---------|------|
| ¶1 | 引入 Table + 总数声明 | "Table~\\ref{tab:budget} summarizes GRASP's per-SM storage budget at ~1.4 KB, dominated by the Chain Table (544 B) and Prefetch Request Buffer (512 B)." | ~35 |
| ¶2 | Per-warp 等效 + 三角对比（D-12 规则） | "Per-warp this works out to 22 B—an order of magnitude smaller than a single thread's register-file slice. As a fraction of A100's 128 KB L1D, GRASP adds 1.1%. Compared to CPU IMA prefetchers (IMP 0.7 KB, Tyche 0.57 KB) and the GPU Spare Register prefetcher (1.4 KB), GRASP fits in the same envelope but, crucially, amortizes its cost across all 64 warps on the SM." | ~85 |
| ¶3 | 一句话收尾 | "We conclude that GRASP's storage overhead is negligible relative to GPU register and cache budgets while extending IMA prefetching to GPU's massively-parallel execution model." | ~30 |

### 与 §4 衔接
§3.6 ¶3 收尾后，§4 自然引入 "Pair table simplification" 作为 trace-driven simulator 的实现细节。**§3 完全不提 chain CSV / pair table**。

---

## 跨节叙事检查

### 与 §2 的衔接（隐式过渡，G2 规则）

§2.5 末尾："...a single shared table can serve all 64 warps on an SM, because every warp executes the same IMAD.WIDE instruction at the same PC."

§3.1 第一句："GRASP realizes this observation as a per-SM hardware prefetcher that detects IMA chains at instruction issue, then issues a two-step prefetch (index → data) for the predicted next iteration."

→ 不出现 "In this section we present GRASP" 这种 boilerplate。

### 与 §5 (Evaluation) 的对应

每个 §3 子节都应该有对应的 §5 数据点：

| §3 | §5 数据点 |
|----|----------|
| §3.2 CD | ablation: CD-disabled |
| §3.3 CT/TT | sensitivity: CT_size, TT_size |
| §3.4 IPU/DPU | sensitivity: distance (1/2/4/8), PRB_capacity |
| §3.5 TC | sensitivity: tc_mode 对比 (0/4/5) |
| §3.6 Cost | hardware overhead 对照表 |

---

## Open Questions（已全部解决 ✓）

| # | 问题 | 用户 review 的解决方案 |
|---|------|----------------------|
| 1 | tc_mode=5 多 workload 数据 | ✅ 数据在 `06_evaluation_plan/throttle_control_results.md` D5b（D5b = 论文版本，覆盖 cit/web/flickr/road/socLJ ×6 算法）|
| 2 | Fig F SVG → PDF | ✅ 已用 cairosvg 转换 → `latex_template/figures/3-Design/throttle.pdf`（47 KB）|
| 3 | distance 默认值 | ✅ distance = **1**（不是 4）。理由：GPU IMA 的 active-lane 数量在迭代间变化大；distance=1 即使 lane mask 不匹配，单 iter 浪费 ≤10 个 prefetch，distance=4 浪费会到 24-28 个 → §3.4 ¶7 已加入此 rationale |
| 4 | PRB capacity | ✅ **512** entries（每 entry ~1 B 资源极小，总开销 ~512 B）→ §3.4 ¶7 + §3.6 表已更新 |
| 5 | Speculative stride | ✅ 加入 §3.3 ¶6，作为 compiler-aided IST hint：编译器通过 ISA 接口传递 element_size，让 IST 跳过观测阶段直接 freeze stride |
| 6 | Fig A 中 TC 位置 | ✅ 右下角（写正文时引用 Fig A 标注） |
| 7 | Hardware cost 字节数 | ✅ 来自 `04_prefetcher_design.md` §7.1：CT ~17B/entry, TT ~5B/entry, PRB ~1B/entry, CD FIFO 固定 300B → §3.6 表已使用精确数字 |

### 文件状态变更（用户 review 后）
- **新建**: `figures/3-Design/throttle.pdf`（cairosvg 从 throttle.drawio.svg 转换）
- **新建**: `figures/3-Design/CT_TT.pdf`（CT&TT.pdf 的 LaTeX-friendly 副本，避免 `&` 在路径中的转义问题）
- **已存在**: `figures/3-Design/Top-Level_Architecture_Diagram.pdf`（用户已重命名为下划线版本）

---

## 写作 Checklist (D-1 ~ D-13)

| 规则 | 检查 | 状态 |
|------|------|------|
| D-1 自顶向下 (Overview→Components→Cost) | §3.1 → §3.2-§3.5 → §3.6 | ✓ |
| D-2 Overview 核心定位句 ≤ 3 句 | §3.1 ¶1 三句话；¶2/¶3 是图解读 | ✓ |
| D-3 架构图紧跟 Overview | Fig A 在 §3.1 ¶2，伴随 Fig B 一起 | ✓ |
| D-4 每子节五段结构 | §3.2-§3.5 都用 | ✓ |
| D-5 What→Why→How 顺序 | 每子节 ¶1 (what) → ¶2 (why) → ¶4 (how) | ✓ |
| D-6 公式三明治 | §3.4 ¶5 嵌入 `data_addr = base + value × scale` | ✓ |
| D-7 伪代码与行号引用 | 暂不使用伪代码 | N/A |
| D-8 每组件子节至少一图 | CD/CT-TT/IPU-DPU/TC 都有 | ✓ |
| D-9 Flowchart 与文字完全对应 | Fig B 6 步在 §3.1 ¶3 + §3.2-§3.5 的开头都有引用 | ✓ |
| D-10 数据结构字段逐一解释 | §3.3 ¶4 (CT entry 字段) + ¶5 (TT entry 字段) | ✓ |
| D-11 Worked Example | **跳过**——用 Fig B (Flowchart) 代替（用户选择） | N/A |
| D-12 Hardware Cost 收尾 + Table | §3.6 + Table 2 + 三角对比 | ✓ |
| D-13 防御性子节 | 内嵌在 §3.2 ¶2 (per-warp tracking) + §3.4 ¶2 (CPU lookahead) | ✓ |
| **叙事弧** | §3.4 是 climax，无 anticlimax recap | ✓ |

---

## 输入参考（Step D 写正文时必读）

### 设计文档
- `paper_structure.md` §3.1-§3.8 (lines 283-432) — 仅供参考
- `writing_rules/§3_design.md` (D-1 ~ D-13)
- `writing_rules/figure_design.md`
- `writing_rules/README.md` (G1 ~ G6)
- `figures/3_GRASP_architecture/figure_plan.md` — 图 schema
- `insight.md` — Insight #4 (PC 归并), #5 (one-to-many), #6 (per-SM 共享), #10 (写无效化), #11 (跨 CTA 修复)

### 源码（精确数字溯源）
- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/grasp_prefetcher.{h,cc}`
- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/grasp_chain_detector.{h,cc}`
- `gpu-simulator/gpgpu-sim/src/gpgpu-sim/grasp_tables.{h,cc}`

### 实验数据
- `05_implementation/dse_throttle_control/README.md` §6 (T40C200 数据)
- `05_implementation/experiment_progress.md` (distance, stride pollution)
- `04_prefetcher_design/extra_pattern/small_1sm_cta5/` (cycle 数据)

### 图（已全部就位 6/6, LaTeX-ready）
- ✅ `latex_template/figures/3-Design/Top-Level_Architecture_Diagram.pdf` → **Fig A 双栏** (§3.1)
- ✅ `latex_template/figures/3-Design/Flowchart.pdf` → **Fig B 单栏** (§3.1)
- ✅ `latex_template/figures/3-Design/Chain_detect.pdf` → Fig C 单栏 (§3.2)
- ✅ `latex_template/figures/3-Design/CT_TT.pdf` → Fig D 单栏 (§3.3)（CT&TT.pdf 的 LaTeX-safe 副本）
- ✅ `latex_template/figures/3-Design/prefetch_pipe.pdf` → **Fig E 双栏** (§3.4 climax)
- ✅ `latex_template/figures/3-Design/throttle.pdf` → Fig F 单栏 (§3.5)（cairosvg 转换自 throttle.drawio.svg）

---

## 下一步

1. ✅ ~~用户 review 本大纲~~ — 已完成 2026-04-08
2. ✅ ~~解决 7 条 Open Questions~~ — 已全部解决
3. ✅ **Step D 完成**: §3 LaTeX 正文已写入 `latex_template/main.tex`（替换 line 742 起的占位符，6 子节 + 6 figures + table）
   - §3.4 ¶6 climax 段已由 AI 直接起草（用 BFS small_1sm_cta5 ~560cy round-trip 数据 + 1120cy → 0cy overlap framing）
   - 所有 figures 改为单栏（用户决定）
   - 所有 captions 收紧到 1-2 句（F-9/F-10 caption 长度规则）
4. **Step E 编译**: `/paper-compile` 验证页数 ≤ 3.5 page，所有 figure 引用正常
