CRITICAL EXACT SPELLING — use ONLY these names, do NOT invent alternatives:
- "Chain Table (CT)" — NOT "Context Table" or "Confidence Table"
- "Target Table (TT)" — NOT "Translation Table"
- "IMAD.WIDE" — NOT "IMAD WIDE" or "IMAD_WIDE"
- "LDG.E" or "LDG" — standard SASS load instruction
- "Index Load" — the first LDG in the chain
- "Addr Generation" — the IMAD.WIDE step
- "Data Load" — the final LDG in the chain
- "IMA" = Indirect Memory Access — always uppercase
- "SpMV" = Sparse Matrix-Vector multiplication
- "IST" = Iteration Stride Tracker

Generate a professional academic diagram for a MICRO/ISCA/HPCA computer architecture paper.
IEEE double-column full width (7.0"), 16:9 aspect ratio. Times New Roman for labels, Courier/Monospace for code and hex addresses ONLY.
Black outlines (1–1.5 pt). NO title. NO shadows. NO gradients. WHITE background. All text minimum 8 pt.
Color palette: Blue #2B5EA7, Purple #6C3483, Amber #D4A843, Gray #BDC3C7, Green #5AA469.
IMPORTANT: Do NOT render any section headers, layout labels, or metadata text (no "BLOCK A", "TOP SECTION", "FORMULA BAR", etc.). Only render the actual content described below.

The figure has two visual regions: top ~2/3 and bottom ~1/3, separated by a centered formula.

TOP REGION — Three blocks:
Left column (~55% width) has two stacked blocks; right column (~40% width) has one tall block. Combined height of the two left blocks equals the right block height. Small gap (~5%) between columns.

(1) SpMV CUDA Source — top-left.
Light gray (#F5F5F5) rounded box, 1 pt black outline.
Small gray italic label: "SpMV CUDA Kernel".
Content in Monospace ~10 pt:
  Line 1 (gray): "// CSR SpMV (base.cu:22)"
  Line 2 (gray): "for (int offset = row_begin;"
  Line 3 (gray): "     offset < row_end; offset++) {"
  Line 4 (BLACK bold): "  sum += Ax[offset] * x[Aj[offset]];"
  Line 5 (gray): "}"
On Line 4: "Aj[offset]" highlighted blue #2B5EA7, small label "Index Load" below; "x[...]" highlighted amber #D4A843, small label "Data Load" below.

(2) Target Table (TT) — bottom-left, same width as (1).
Title: "Target Table (TT)" in bold, left-aligned. Subtitle: "8 entries" in gray italic.
Header row: PURPLE #6C3483 background, white bold text.
This table has 3 rows of data. Columns: Valid | Base Address | Scale.
Address prefix label: small gray text "addr prefix: 0x7FC4B7" above or beside the table.

| Valid | Base Address | Scale |
|-------|-------------|-------|
| [green square] | 0x...C20000  (x[]) | 4 |
| [green square] | 0x...E40000  (y[]) | 4 |
| [green square] | 0x...100000  (z[]) | 8 |

"Valid" cells: small solid GREEN #5AA469 filled square (NOT a checkmark).
Base Address values in monospace; array name annotation "(x[])" etc. in italic.
Scale "4" can have small gray annotation "sizeof(float)".

(3) SASS Assembly — right side, full height of top region.
Light gray (#F5F5F5) rounded box, 1 pt black outline.
Small gray italic label: "SASS Assembly (×16 Unrolled Loop)".
Content in Monospace ~9 pt, showing 2 highlighted chains out of 16:

  (1) /*03d0*/ LDG.E R9, [R6+-0x8]          — BLUE #2B5EA7 bold
  (2) /*03e0*/ LDG.E R27, [R6+-0x4]         — BLUE #2B5EA7 bold
      /*03f0*/ LDG.E R13, [R6]              — gray
      /*0400*/ LDG.E R21, [R6+0x4]          — gray
               ... (12 more index loads)     — gray italic

  (1) /*0480*/ IMAD.WIDE R8, R9, R16, c[0x180]    — PURPLE #6C3483 bold
  (2) /*0490*/ IMAD.WIDE R26, R27, R16, c[0x180]  — PURPLE #6C3483 bold
      /*04b0*/ IMAD.WIDE R12, R13, R16, c[0x180]  — gray
               ... (13 more IMAD.WIDEs)            — gray italic

  (1) /*04a0*/ LDG.E R14, [R8]              — AMBER #D4A843 bold
  (2) /*04c0*/ LDG.E R24, [R26]             — AMBER #D4A843 bold
      /*04d0*/ LDG.E R12, [R12]             — gray
               ... (13 more data loads)      — gray italic

      /*0580*/ FFMA R14, R14, R18, R11       — gray
               ... (accumulation)            — gray italic

ONLY lines marked (1) or (2) are colored. ALL other code lines are GRAY #BDC3C7.

Right-side brackets on the SASS block grouping instruction phases:
- Lines 1–5 bracket: "IMA Index Load" in blue #2B5EA7
- Lines 6–9 bracket: "Addr Generation" in purple #6C3483
- Lines 10–13 bracket: "IMA Data Load" in amber #D4A843

FORMULA — centered, full width, between top region and CT.
Light background (#EBF5FB or white), subtle 0.5 pt border.
Content in Times New Roman ~11 pt, LaTeX-style with proper subscript:
  "Addr_target = base + scale × index"
where "Addr" has subscript "target" (like LaTeX $\text{Addr}_{\text{target}}$).
"base" colored blue #2B5EA7. "scale" colored purple #6C3483. "index" colored blue #2B5EA7.
Multiplication sign is "×" (NOT the letter "x").
Short arrows from "base" UP to TT "Base Address" column and from "scale" UP to TT "Scale" column.

BOTTOM REGION — Chain Table (CT), occupying ~70% of the bottom width (leave ~30% right side for IST block).

Title: "Chain Table (CT)" in bold, left-aligned. Subtitle: "32 entries" in gray italic.

DMP-STYLE GROUPED TABLE HEADERS (two-layer, like DMP paper Fig 8–9):
Top row has GROUP NAMES spanning multiple sub-columns, with thin gaps between groups.
Sub-row has individual FIELD NAMES.

Header colors: BLUE #2B5EA7 background, white bold text (both layers).

Group layout (3 groups separated by 2–3 px white gaps):

  Group "Identification":        | Valid | Index PC |
  Group "Target Mapping":        | TT Index          | K |
                                   [0]  [1]  [2]
  Group "Stride Learning (IST)": | Stride Obs    | Iter   | Stride |
                                   [0]     [1]     Stride   Valid

IMPORTANT for "TT Index" and "Stride Obs": draw as two-layer sub-headers.
Upper layer: group name spanning all sub-cells (e.g., "TT Index" spans 3 cells).
Lower layer: individual sub-cells [0], [1], [2].

Address prefix label: small gray text "addr prefix: 0x7FC4D0DA" near the table.

Data rows (white background, black text, 1 pt borders):

Row 1: | [green] | 0x03d0 | 0 | — | — | 1 | W5: 0x...4864 | W5: 0x...48A4 | 64 B | [green] |
Row 2: | [green] | 0xA120 | 0 | 1 | — | 2 | W3: 0x...2100 | W3: 0x...2110 | 16 B | [green] |
Row 3: | [green] | 0xB340 | 0 | 1 | 2 | 3 | W8: 0x...5040 | —              |  4 B | [empty] |
Row 4: |  ...    |  ...   |   |   |   |...|                |                | ...  |  ...    |

"Valid" and "Stride Valid": GREEN #5AA469 filled square when valid, empty when not.
Row 3 has Stride Valid empty (stride still learning).
PC values and addresses in monospace. "—" in gray for unused TT Index slots.

IST BLOCK — small rounded box to the right of CT table, in the remaining ~30% bottom-right space.
Light gray (#F5F5F5) background, 1 pt black outline, rounded corners.
Title: "IST" in bold, subtitle "Iteration Stride Tracker" in small gray.
Content (~8–9 pt):
  A₁ = 0x...4864  @  iter i
  A₂ = 0x...48A4  @  iter i+1
  stride = A₂ − A₁ = 0x40 = 64 B  ✓
  ★ Any warp can contribute
A connecting arrow from IST block LEFT to CT's "Stride Learning" group (specifically Iter Stride / Stride Valid columns).

ARROWS (cross-section connections):

1. CUDA → SASS: gray dashed arrow (#808080) from SpMV CUDA block rightward to SASS block, labeled "compiles to" in gray italic.

2. SASS chain PCs → CT Index PC: black solid arrows from SASS lines (1)/(2) DOWNWARD to CT Row 1 / Row 2 "Index PC" cells. Small labels "①" "②".

3. CT TT Index → TT: black solid arrows from CT Rows' "TT Index [0]" cells UPWARD-LEFT converging toward TT table, showing many-to-one mapping. Multiple arrows converge to show 16 CT entries → 1 TT entry.

4. SASS IMAD.WIDE → TT: gray dashed arrows from "c[0x180]" operand in SASS to TT "Base Address"; from "R16" to TT "Scale".

ANNOTATIONS — placed in naturally blank areas of the figure. Use bold text with thin pointing lines (NOT dialog boxes, NOT bordered boxes). Just bold black text ~8 pt with a thin line or arrow pointing to the relevant element.

Annotation 1 (near CT–TT arrow convergence area):
  "16 CT entries → 1 TT entry"

Annotation 2 (near IST or CT stride area):
  "stride = 16 elements × 4 B = 64 B"

STYLE CONSTRAINTS:
- DRAW EXACTLY ONE copy of each table (CT and TT). Do NOT duplicate any table.
- Do NOT render any layout metadata, section headers, or block labels.
- No Chinese text anywhere.
- Keep layout COMPACT — blocks close together, minimal wasted space.
- Monospace font for ALL hex addresses (0x03d0, 0x...4864 etc.) and SASS instructions.
