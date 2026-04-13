# Fig A — GRASP 总体架构框图 Prompt

> 版本: v12 (2026-04-05)
> 成果归档: [success/](fig_a_overall_arch/success/)（4 张迭代图 + SVG + 经验总结）
> 配色: 与 figure_prompts.md 通用配色对齐（#2B5EA7 蓝、#6C3483 紫）
> 结构: 单段提示词，风格约束在末尾

---

## v11→v12 变更记录

- 字体统一 Times New Roman
- TC 画大（与其他组件同等大小）
- TC→MSHR 长路径取消，改为 TC→PQ（灰色），PQ 引出两条箭头：红→L1，灰→MSHR
- PQ→L1 红色箭头方向明确修正

---

## 提示词（直接喂给 nano-banana-pro）

```
CRITICAL EXACT SPELLING — use ONLY these names, do NOT invent alternatives:
- "Streaming Multiprocessor (SM)" — NOT "Multiposster", NOT "Multiprocesser"
- "Chain Detector (CD)" — NOT "Conflict Detector", NOT "Change Detector"
- "Chain Table (CT)" — NOT "Confidence Table", NOT "Context Table"
- "Target Table (TT)" — NOT "Translation Table", NOT "Training Table"
- "Iteration Stride Tracker (IST)"
- "Index Prefetch Unit (IPU)" — NOT "Index Prediction Unit"
- "Data Prefetch Unit (DPU)" — NOT "Data Protection Unit"
- "Prefetch Request Buffer (PRB)" — NOT "Prefetch Buffer"
- "Address Computation Unit (ACU)"
- "Throttle Controller (TC)" — NOT "Tag Checker"
- "Prefetch Queue (PQ)"
- "L1 D-Cache" with "MSHR" inside — NOT "L1 Cashe"
- "L2 Cache" — NOT "L2 Cashe"
- "Prefetch" — NOT "Preffech", NOT "Preftech", NOT "Prefetech"
- "GRASP" — always uppercase

Generate a hardware architecture block diagram for a GPU prefetcher called "GRASP"
(GPU Register-chain Aware Sector Prefetcher).

Layout:
- Left side (~25% width): vertical SM pipeline column showing existing GPU hardware
- Right side (~70% width): GRASP prefetcher expanded detail, enclosed in a large
  gray dashed rectangle labeled "GRASP" at the top-right corner
- Below SM: L2 Cache, slightly separated
- Bottom strip: legend row (arrow legend + component legend)
- IMPORTANT: Keep the overall layout COMPACT with minimal whitespace.

LEFT SIDE — SM Pipeline (existing hardware):

Stack these white boxes vertically (1.5pt black border, white fill, dark text),
top to bottom. NO connecting arrows between the SM boxes:

  "Warp Scheduler" — white box
  "Issue Stage" — white box
  "GRASP Prefetcher" — blue (#2B5EA7) filled box with white text, medium-sized,
             this is GRASP's physical location in the SM. An expansion
             bracket or arrow points RIGHT to show it expands into the detail.
  "L1 D-Cache" — white box, smaller than GRASP but still contains
                  a small gray sub-box "MSHR" inside it

Below the SM boundary (slightly separated):
  "L2 Cache" — white box, 1.5pt black border
  TWO arrows between L1 and L2 — use DARK GRAY (#808080) SOLID lines
  (NOT black, to distinguish from the Training Path):
    - One dark gray solid arrow from L1 going DOWN to L2, labeled "Req"
    - One dark gray solid arrow from L2 going UP to L1, labeled "Rsp"

Cross-boundary arrows from SM to GRASP detail:
  From "Issue Stage": black solid arrow going RIGHT toward Chain Detection area,
    labeled "Issued Instructions"
  From "L1 D-Cache": arrows going RIGHT toward Prefetch Generation area

The overall SM pipeline is enclosed in a large rounded rectangle labeled
"Streaming Multiprocessor (SM)" at the top. Do NOT add any title above the figure.

RIGHT SIDE — GRASP Expanded Detail:

Large area enclosed by a dashed gray (#BDC3C7) rectangle. Divided into two
sub-regions by a horizontal dashed line.

UPPER SUB-REGION — "Chain Detection" label at top-left corner:

  Components arranged left to right:
    "CD (Chain Detector)" — purple (#6C3483) box, white bold text, 1.5pt black border
    "CT (Chain Table)" — blue (#2B5EA7) box, white bold text, 1.5pt black border
      Inside CT: smaller embedded box "IST (Iteration Stride Tracker)"
      — IST is PURPLE (#6C3483) fill (it is a Logic unit, NOT storage)
    "TT (Target Table)" — blue (#2B5EA7) box, white bold text, 1.5pt black border

  Arrows (all black solid — training path):
    Issue Stage → CD: labeled "Issued Instructions"
    CD → CT: labeled "Chain Entry"
    CT → TT: labeled "Target Index"

  ALL black training path arrows must have CONSISTENT arrowhead size and line weight.

LOWER SUB-REGION — "Prefetch Generation" label at top-left corner:

  IMPORTANT: Keep this area COMPACT.
  Arrange so L1-interacting ones are on the LEFT side (near the SM column),
  internal logic on the RIGHT side.

  Left side (near L1):
    "PRB (Prefetch Request Buffer)" — blue (#2B5EA7) box, white text, black border
    "ACU (Address Computation Unit)" — purple (#6C3483) box, white text, black border
    "PQ (Prefetch Queue)" — blue (#2B5EA7) box, white text, black border

  Right side (internal):
    "IPU (Index Prefetch Unit)" — purple (#6C3483) box, white text, black border
    "DPU (Data Prefetch Unit)" — purple (#6C3483) box, white text, black border
    "TC (Throttle Controller)" — purple (#6C3483) box, white text, black border,
       SAME SIZE as DPU (not smaller)

  Arrow flow with numbered circles ①②③④⑤⑥:

    ① Red (#C0392B) dashed arrow from CT/IST (upper section) DOWN to IPU.
       Label: "Stride, Chain Info"

    ② Green (#27AE60) dashed arrow from IPU to PRB.
       Label: "Index Address"

    ③ Green (#27AE60) dashed arrow from PRB going LEFT to L1 D-Cache.
       This arrow MUST physically reach the L1 box in the SM column.
       Label: "Index Prefetch to L1"

    ④ Green (#27AE60) dashed arrow from L1 D-Cache going RIGHT to ACU.
       Single arrowhead at ACU end only. MUST come FROM L1 and arrive AT ACU.
       Label: "Fill Response (Index Value)"

    ⑤ Red (#C0392B) dashed arrow from ACU to DPU.
       Label: "Data Address"

    ⑥ Red (#C0392B) dashed arrow from DPU to PQ.
       Label: "Data Prefetch"

  FROM PQ, two arrows emerge going LEFT toward the SM column:
    - Red (#C0392B) dashed arrow from PQ going LEFT to L1 D-Cache.
      Label: "Data Prefetch to L1"
    - Gray (#BDC3C7) dashed arrow from PQ going LEFT to MSHR sub-box inside L1.
      Label: "Monitor MSHR"

  TC arrows (gray #BDC3C7 dashed, NO numbered circles):
    TC → DPU: gray dashed arrow, label "Suppress"
    TC → PQ: gray dashed arrow, label "Throttle"

LEGEND ROW (bottom of figure, full width, single horizontal row):

  Left box — Arrow Legend:
    Four short line samples with actual colors and styles:
      Black solid line → "Training Path"
      Green (#27AE60) dashed line → "Index Prefetch (Step 1)"
      Red (#C0392B) dashed line → "Data Prefetch (Step 2)"
      Gray (#BDC3C7) dashed line → "Control"

  Right box — Component Legend:
    Three small colored squares:
      Blue (#2B5EA7) square → "Storage"
      Purple (#6C3483) square → "Logic"
      White square with black border → "Existing HW"

Style constraints (MUST follow):
- Academic paper figure style, clean and professional
- White background, no decorative elements or shadows
- Black outlines (1-1.5pt) on all boxes and arrows
- Font: Times New Roman for ALL text (component labels, arrow labels, legend)
- Bold for component abbreviations inside colored blocks
- Italic for arrow labels
- Color palette: use only blue (#2B5EA7), red/dark-red (#C0392B), purple (#6C3483),
  green (#27AE60), and grays (#BDC3C7, #ECF0F1)
- Dashed gray rectangles for grouping/regions, with module name at top-right corner
- All text must be crisp and readable at print size (minimum 8pt equivalent)
- IEEE/ACM double-column paper format, figure width ~7.0in (full width)
- Do NOT include any title or caption in the image
- Do NOT include any text that is not a component name, arrow label, or legend entry
```
