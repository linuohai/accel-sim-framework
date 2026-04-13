# GRASP 论文非数据图 — 生图 Prompt 模板

> 基于飞书素材库中 DMP / RICH / Snake / Tyche 等体系结构顶会论文的图片风格提取。
> 使用方式：选择对应的图类型模板，替换 `{{占位符}}` 中的内容，喂给生图模型。

---

## 通用风格约束（所有 prompt 都应包含）

```
Style constraints (MUST follow):
- Academic paper figure style, clean and professional
- White background, no decorative elements or shadows
- Black outlines (1-1.5pt) on all boxes and arrows
- Font: sans-serif bold for labels inside colored blocks, serif for captions
- Color palette: use only blue (#2B5EA7), red/dark-red (#C0392B), purple (#6C3483),
  orange (#E67E22), yellow (#F4D03F), green (#27AE60), and grays (#BDC3C7, #ECF0F1)
- Dashed gray rectangles for grouping/regions, with module name at top-right corner
- All text must be crisp and readable at print size (minimum 8pt equivalent)
- IEEE/ACM double-column paper format, figure width ~3.5in (single col) or ~7.0in (full width)
- Caption below figure in format "Fig. X. Description." (do NOT include caption in the image)
```

---

## Type 1: 硬件架构总览图

用于展示 prefetcher 整体硬件结构及其在 cache hierarchy 中的位置。

参考：DMP Fig. 10 (Overview of DMP hardware design), RICH Figure 6 (Architecture of RICH)

```
Generate a hardware architecture block diagram for a GPU prefetcher called "{{prefetcher_name}}".

Layout:
- Left side: vertical cache hierarchy stack from top to bottom:
  "{{top_level}}" → "{{mid_level}}" → "{{bottom_level}}" (e.g., "L2 Cache" → "L1 D-Cache" → "Core")
- Connected by thick black arrows labeled "Req" (downward) and "Rsp" (upward)
- Right side: the prefetcher module, enclosed in a large gray dashed rectangle
  labeled "{{prefetcher_name}}" at the top-right corner

Prefetcher internal structure:
- Divided into two sub-regions with dashed borders:
  - "{{detection_module_name}}" (e.g., "Chain Detection"):
    contains blocks: {{detection_blocks}} (e.g., "Snooper", "Chain Detector", "Chain Table")
  - "{{generation_module_name}}" (e.g., "Prefetch Generation"):
    contains blocks: {{generation_blocks}} (e.g., "Index Prefetch Unit", "Data Prefetch Unit", "Prefetch Buffer", "Address Computation Unit")

Color coding (shown in legend at bottom):
- Blue filled blocks = Storage components (tables, buffers, queues)
- Purple/dark-red filled blocks = Logic components (detectors, matchers, calculators)
- White blocks with black border = External components (caches, core)
- White text on dark blocks, black text on light blocks

Arrows:
- Black solid arrows = normal data/control flow
- Red dashed arrows = prefetch request path (highlighted)
- Arrow labels in italic (e.g., "index value", "prefetch addr")

{{Style constraints}}
```

---

## Type 2: 算法流程图

用于展示检测/匹配/预取的多步骤流程。

参考：DMP Fig. 5 (Indirect access pattern detection flow)

```
Generate an algorithm flowchart for "{{algorithm_name}}" (e.g., "IMA Chain Detection Flow").

Structure: top-to-bottom vertical flow, divided into {{N}} steps with step labels on the right side
("Step-1: {{step1_name}}", "Step-2: {{step2_name}}", ...).

Nodes:
- Rounded rectangles for process steps, filled with dark blue (#2B5EA7), white bold text
- Diamond shapes for decision points, filled with light blue (#AED6F1), black text
- Rectangles with yellow (#F4D03F) fill for key outputs/tables
- Small white rectangles for intermediate data labels

Flow:
{{flow_description}}
(e.g.,
"Step-1: 'Monitor Issue Stage' → detect LDG→IMAD→LDG chain → output 'Chain Entry'
 Step-2: 'Track Stride' → observe consecutive index addresses → decision 'Stride Stable?'
         → yes: 'Stride Converged' → Step-3
         → no: loop back to 'Track Stride'
 Step-3: 'Generate Prefetch' → compute index prefetch address → 'Prefetch Queue'")

Arrows:
- Solid black arrows for main flow
- Dashed arrows for feedback/loop paths
- Labels on arrows: "yes"/"no" at decision branches, signal names elsewhere

Legend at bottom: explain color coding if needed.

{{Style constraints}}
```

---

## Type 3: 代码分析图（伪代码 + 汇编 + 数据结构映射）

用于展示具体 workload 的 IMA 链识别过程。

参考：DMP Fig. 4 (BFS Code Analysis)

```
Generate a code analysis diagram for "{{algorithm_name}} IMA Pattern Analysis"
(e.g., "BFS Indirect Memory Access Analysis").

Layout: multi-panel composite figure with {{N}} sub-figures labeled (a), (b), (c), ...

Panel (a) — "{{algorithm_name}} Algorithm and Indirect Patterns":
- Left: pseudocode block with syntax highlighting
  - Background: light gray
  - Different code blocks colored: {{block_colors}}
    (e.g., "Block-A = light yellow, Block-B = light green, Block-C = light blue")
  - Key variables highlighted in bold
- Right: array diagram showing indirect access chain
  - Arrays as horizontal sequences of cells (labeled: {{array_names}}, e.g., "worklist", "ptrList", "edgeList", "visited")
  - Curved arrows between arrays showing indirection relationships
  - Arrow labels: "{{access_types}}" (e.g., "Stream", "Single Indirect", "Ranged Indirect")
  - A vertical bracket on the right labeled "Multi-Level"

Panel (b) — "{{algorithm_name}} SASS/Assembly Analysis":
- Show assembly instructions with PC addresses on the left (monospace font, e.g., "0xf0: LDG.E R17, [R4.64]")
- Color-code by basic block (same colors as pseudocode)
- Add inline comments in colored text:
  - Red = control flow / branch instructions
  - Green = data load instructions
  - Blue = address computation instructions

Panel (c) — "Indirection Pair Table":
- A table with columns: "Indirection Pair | Indirect Level | Index Flow (PC, Array, Type) | Target Flow (PC, Array, Type) | Prefetcher"
- Table header: dark gray background, white bold text
- Data rows: alternating white/light-gray, key cells highlighted
  (green = handled by stride, orange = handled by our prefetcher)

{{Style constraints}}
```

---

## Type 4: 数据结构与硬件表格图

用于展示 prefetcher 内部的表项格式和工作示例。

参考：DMP Fig. 7 (Differential sequence collection), Fig. 8 (Differential matching), Fig. 9 (Tables)

```
Generate a data structure and working example diagram for "{{component_name}}"
(e.g., "GRASP Chain Table and Target Table Working Example").

Layout: vertical flow showing data transformation pipeline.

Section 1 — Input Data Stream:
- A horizontal timeline/sequence of values: {{input_sequence}}
  (e.g., "0x1, 0x9, 0x9, 0x10, 0x1a, 0x2a, 0x2a, 0x3c, ...")
- Dots on a horizontal line, values labeled above
- Duplicate/filtered values highlighted in red text
- A processing block below: "{{filter_name}}" (e.g., "Repetition Filter")
  in dark blue rounded rectangle, with red annotation "Remove {{removed_values}}"

Section 2 — Filtered Data:
- Show the cleaned sequence on a new horizontal line
- Blue circle markers (●) with downward arrows showing diff computation
- Results feed into a table structure below

Section 3 — Table Structure:
- Draw the hardware table as a grid:
  - Header row: dark {{header_color}} background, white bold text
  - Fields: {{field_names}} (e.g., "Index PC | Diff1 | Diff2 | Diff3 | ... | Last Value")
  - Data row: light colored background, monospace values in cells
  - Key fields highlighted (green = index, blue = target, orange = computed result)

{{Style constraints}}
```

---

## Type 5: 时序/执行示意图

用于展示 prefetch 时序、pipeline 行为、或 branch misprediction 影响。

参考：DMP Fig. 4(e) (Disturbed sequence of misprediction)

```
Generate a timing/execution sequence diagram for "{{scenario_name}}"
(e.g., "GRASP Prefetch Timing: Index Load → Data Prefetch Pipeline").

Layout: horizontal timeline flowing left to right.

Lanes (vertical rows, labeled on the left):
{{lane_definitions}}
(e.g.,
- "Execution" lane: shows basic blocks as colored rectangles on the timeline
- "Index PF" lane: shows prefetch events as small markers
- "Data PF" lane: shows data prefetch events
- "L1 Cache" lane: shows hit/miss events)

Timeline elements:
- Colored rectangles for execution blocks: {{block_colors}}
  (e.g., "Block A = light blue, Block B = light red, Block C = light green")
- Vertical dashed lines connecting events across lanes (showing causality)
- Annotations above key events: {{annotations}}
  (e.g., "stride detected", "prefetch issued", "data arrives")
- A horizontal arrow at the bottom labeled "t" (time)

Highlight:
- {{highlight_description}}
  (e.g., "Show the latency gap between index load miss and data prefetch arrival
   with a red double-headed arrow labeled '~500 cycles'")

{{Style constraints}}
```

---

## Type 6: IMA 访存模式示意图

用于 Introduction/Background 中解释 indirect memory access 的基本概念。

参考：DMP Fig. 3 (Examples of indirect access types)

```
Generate an indirect memory access pattern illustration showing {{N}} types of indirection.

Layout: {{N}} sub-figures side by side, labeled (a), (b), (c), ...

For each sub-figure "{{pattern_name}}" (e.g., "(a) Single Indirect"):
- Top: a code snippet in a bordered box: "{{code}}" (e.g., "z[i] = x[a[i]]")
- Bottom: array visualization
  - Arrays as vertical columns of cells, labeled (e.g., "a", "x", "z")
  - An index pointer "i→" pointing to the current cell in array "a"
  - Curved arrows from source cell to target cell showing the indirection
  - Arrow color: dark gray or black
  - Accessed cells highlighted in light blue (#AED6F1)
  - Values shown inside cells in bold

Sub-figures to include:
{{subfigure_list}}
(e.g.,
"(a) Single Indirect: z[i] = x[a[i]] — one level of indirection
 (b) Ranged Indirect: z[i] += x[a[i]+j] — range access after indirection
 (c) Multi-level Indirect: z[i] = y[x[a[i]]] — two levels of indirection
 (d) Multi-way Indirect: z[i] = x1[a[i]] + x2[a[i]] — multiple targets from same index")

{{Style constraints}}
```

---

## 使用建议

1. **复制对应类型的模板**，替换所有 `{{占位符}}`
2. **始终包含底部的 Style constraints 段落**，确保风格一致
3. 生成的图作为**草图/起点**，后续在 draw.io / PowerPoint / Figma 中精修
4. 如果生图模型支持参考图，可以附上飞书文档中对应类型的参考图作为 style reference
