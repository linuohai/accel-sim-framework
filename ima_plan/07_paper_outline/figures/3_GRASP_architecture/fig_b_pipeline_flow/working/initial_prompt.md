# Fig B — GRASP Pipeline Flow Prompt

> Version: v1 (2026-04-05)
> Target: 7.0" double-column, 16:9 aspect ratio
> Model: nano-banana-pro
> Color source: architecture_figure_style.md v5 (proven in Fig A)

---

## Prompt (for Gemini layout optimization → NanoPana rendering)

```
CRITICAL EXACT SPELLING — use ONLY these names, do NOT invent alternatives:
- "Chain Detector (CD)" — NOT "Conflict Detector", NOT "Change Detector"
- "Chain Table (CT)" — NOT "Confidence Table", NOT "Context Table"
- "Target Table (TT)" — NOT "Translation Table", NOT "Training Table"
- "Iteration Stride Tracker (IST)"
- "Index Prefetch Unit (IPU)" — NOT "Index Prediction Unit"
- "Data Prefetch Unit (DPU)" — NOT "Data Protection Unit"
- "Prefetch Request Buffer (PRB)" — NOT "Prefetch Buffer"
- "Address Computation Unit (ACU)"
- "Throttle Controller (TC)" — NOT "Tag Checker"
- "Prefetch" — NOT "Preffech", NOT "Preftech", NOT "Prefetech"
- "GRASP" — always uppercase
- "IMAD.WIDE" — NOT "IMAD Wide", NOT "IMADWIDE"
- "L1 D-Cache" — NOT "L1 Cashe"

Generate an algorithm flowchart for "GRASP Prefetch Pipeline" showing
three phases of operation.

Layout:
- Two-column layout, 16:9 aspect ratio (7.0" double-column paper width)
- Left column (~45% width): Phase 1 (Chain Detection) on top,
  Phase 2 (Stride Learning) below, separated by subtle spacing
- Right column (~45% width): Phase 3 (Two-Step Prefetch)
- Phase labels: gray italic text at the top-right corner of each phase area
- A horizontal dashed arrow labeled "Stride + Target Info" connects
  left column bottom to right column top (knowledge transfer)
- Bottom strip: legend row (arrow styles + component colors)
- IMPORTANT: Keep layout COMPACT with minimal whitespace

═══ LEFT COLUMN — Phase 1: "Chain Detection" ═══

Nodes from top to bottom:

Start node (rounded rectangle, blue #2B5EA7 fill, white text):
  "Instruction Issued"

Decision diamond (light blue #AED6F1 fill, dark text):
  "Tracked Warp?"
  → No: small gray (#BDC3C7) rounded terminal "Skip"
  → Yes: ↓

Process node (blue #2B5EA7 fill, white bold text):
  Line 1: "Monitor Issue Stream"
  Line 2 (smaller): "(CD)"

Decision diamond (light blue #AED6F1 fill, dark text):
  "Chain Detected?"
  Below diamond in small text: "LDG → IMAD.WIDE → LDG"
  → No: gray dashed arrow looping back, label "Wait"
  → Yes: ↓

Process node (amber gold #D4A843 fill, white bold text):
  Line 1: "Record Chain Info"
  Line 2 (smaller): "(CT + TT)"

Terminal (blue #2B5EA7 rounded rectangle, white text):
  "Chain Recorded"

═══ LEFT COLUMN — Phase 2: "Stride Learning" ═══

Start node (blue #2B5EA7 rounded rectangle, white text):
  "Index Load Observed"

Process node (blue #2B5EA7 fill, white bold text):
  Line 1: "Track Address Differences"
  Line 2 (smaller): "(IST)"

Decision diamond (light blue #AED6F1 fill, dark text):
  "Stride Stable?"
  → No: gray dashed arrow looping back, label "Update"
  → Yes: ↓

Process node (amber gold #D4A843 fill, white bold text):
  Line 1: "Stride Converged"
  Line 2 (smaller): "Store in CT"

═══ RIGHT COLUMN — Phase 3: "Two-Step Prefetch" ═══

Start node (purple #6C3483 rounded rectangle, white text):
  "Demand Index Load"

Decision diamond (light blue #AED6F1 fill, dark text):
  "CT Hit & Stride Valid?"
  → No: small gray (#BDC3C7) rounded terminal "No Prefetch"
  → Yes: ↓

Process node (purple #6C3483 fill, white bold text):
  Line 1: "Compute Prefetch Address"
  Line 2 (smaller): "(IPU)"

Process node (blue #2B5EA7 fill, white bold text):
  Line 1: "Allocate Tracking Entry"
  Line 2 (smaller): "(PRB)"

Process node (purple #6C3483 fill, white bold text):
  Line 1: "Issue Index Prefetch"
  Line 2 (smaller): "(→ L1 D-Cache)"
  Arrow going down is GREEN (#27AE60) DASHED, label "Index Prefetch"

A dashed gap or dotted line segment labeled "Wait for Fill Response"
in gray italic text

Process node (purple #6C3483 fill, white bold text):
  Line 1: "Compute Data Address"
  Line 2 (smaller): "(ACU)"

Decision diamond (light blue #AED6F1 fill, dark text):
  "Throttle Active?"
  Small text below: "(TC)"
  → Yes: small gray (#BDC3C7) rounded terminal "Suppress"
  → No: ↓

Process node (purple #6C3483 fill, white bold text):
  Line 1: "Issue Data Prefetch"
  Line 2 (smaller): "(DPU → PQ → L1)"
  Arrow going down is RED (#C0392B) DASHED, label "Data Prefetch"

End node (green #27AE60 rounded rectangle, white bold text):
  "Demand Load → L1 HIT"

═══ CROSS-COLUMN CONNECTION ═══

A horizontal dashed arrow (#808080 dark gray) from left column bottom area
to right column top area:
  Label: "Stride + Target Info"
  This arrow MUST physically cross from left column to right column.
  It represents CT/TT knowledge feeding into the prefetch pipeline.

═══ SIDE ANNOTATIONS ═══

Three small light gray (#F0F0F0) boxes with thin dotted lines connecting
to the relevant phase area. Place them in margins or corners:

1. Next to Phase 1 (right side):
   "IMAD.WIDE in GPU ISA explicitly encodes indirect access structure"

2. Next to Phase 2 (right side):
   "Typically converges within 2-3 observations"

3. Next to Phase 3 (right side):
   "Two-step: index value determines data address"

4. Next to TC diamond (right side):
   "MSHR > 40% triggers 200-cycle cooldown"

═══ LEGEND ROW (bottom of figure) ═══

Single horizontal row, full width:

Left box — Arrow Styles:
  Black solid line → "Main Flow"
  Green (#27AE60) dashed line → "Index Prefetch"
  Red (#C0392B) dashed line → "Data Prefetch"
  Gray (#BDC3C7) dashed line → "Loop / Skip"

Right box — Node Colors:
  Blue (#2B5EA7) square → "Training Steps"
  Purple (#6C3483) square → "Prefetch Steps"
  Gold (#D4A843) square → "Key Output"
  Green (#27AE60) square → "Success"
  Light blue (#AED6F1) diamond → "Decision"

═══ STYLE CONSTRAINTS (MUST follow) ═══

Style constraints (MUST follow):
- Academic paper figure style, clean and professional
- White background, no decorative elements or shadows
- Black outlines (1-1.5pt) on all boxes
- Font: Times New Roman for ALL text (node labels, arrow labels, legend)
- Bold for main text inside colored blocks
- Italic for arrow labels and side annotations
- Color palette: use only blue (#2B5EA7), purple (#6C3483), gold (#D4A843),
  green (#27AE60), light blue (#AED6F1), red (#C0392B),
  and grays (#BDC3C7, #808080, #F0F0F0)
- All text must be crisp and readable at print size (minimum 8pt equivalent)
- IEEE/ACM double-column paper format, figure width ~7.0in (full width)
- Do NOT include any title or caption in the image
- Do NOT include any text that is not a node label, arrow label,
  phase label, annotation, or legend entry
- Keep all node text SHORT (3-8 words per line, maximum 2 lines per node)
- Arrows connecting nodes must be clearly visible with proper arrowheads
```
