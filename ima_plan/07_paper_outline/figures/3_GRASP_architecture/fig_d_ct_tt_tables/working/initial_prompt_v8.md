CRITICAL EXACT SPELLING — use ONLY these names, do NOT invent alternatives:
- "Chain Table (CT)", "Target Table (TT)", "Iteration Stride Tracker (IST)"
- "IMAD.WIDE", "LDG.E", "SpMV", "IMA", "GRASP"
- "Index Load", "Addr Generation", "Data Load"
- "Prefetch" — NOT "Preffech", NOT "Preftech"

Professional academic diagram for MICRO/ISCA/HPCA. 16:9, 7.0" IEEE double-column. Sans-serif for labels, Monospace for code/hex. NO title. NO shadows. NO gradients. White background. Black outlines 1-1.5pt on all boxes.

DO NOT render any metadata, section headers, or layout percentages as visible text. Do NOT write "BLOCK A", "TOP SECTION", "FORMULA BAR" or any structural labels.

=== OVERALL LAYOUT (4 zones) ===
Upper-left (~45% width, ~35% height): SpMV CUDA source code box
Upper-right (~55% width, ~35% height): SASS Assembly box (tall, aligned with code box top)
Middle band (~100% width, thin): Formula + convergence annotation
Lower-left (~70% width, ~55% height): Chain Table (CT)
Lower-right (~30% width, split into two stacked blocks): Target Table (TT) on top, IST block on bottom

Key visual feature: BLACK SOLID ARROWS from CT rows' tt_idx column pointing RIGHT to corresponding TT rows, showing many-to-one convergence (16 CT entries → 1 TT entry). This is the CENTRAL VISUAL STORY of this figure.

=== UPPER LEFT: SpMV CUDA Source ===
Light gray #F5F5F5 rounded box, small label "SpMV CUDA Kernel" in gray italic at top-left corner.
Monospace code (compact, 4 lines):
  // CSR SpMV (base.cu:22)
  for (int offset = row_begin;
       offset < row_end; offset++) {
    sum += Ax[offset] * x[Aj[offset]];
  }
Key expression highlighted: "Aj[offset]" underlined in blue #2B5EA7 with small label "Index Load" below. "x[...]" underlined in amber #D4A843 with small label "Data Load" below.
Gray dashed arrow pointing right to SASS box, labeled "compiles to" in small italic.

=== UPPER RIGHT: SASS Assembly ===
Light gray #F5F5F5 rounded box, label "SASS Assembly (x16 Unrolled Loop)" at top.
Show THREE instruction groups with color-coded brackets on the right margin:

Group 1 — BLUE bracket labeled "IMA Index Loads":
  BLUE #2B5EA7 bold: *0x03d0* LDG.E R9, [R6+-0x8]
  BLUE #2B5EA7 bold: *0x03e0* LDG.E R27, [R6+-0x4]
  GRAY: *0x03f0* LDG.E R13, [R6]
  GRAY italic: ... (13 more index loads)

Group 2 — PURPLE bracket labeled "Addr Generation":
  PURPLE #6C3483 bold: *0x0480* IMAD.WIDE R8, R9, R16, c[0x180]
  PURPLE #6C3483 bold: *0x0490* IMAD.WIDE R26, R27, R16, c[0x180]
  GRAY: ... (14 more IMAD.WIDEs)

Group 3 — AMBER bracket labeled "IMA Data Loads":
  AMBER #D4A843 bold: *0x04a0* LDG.E R14, [R8]
  AMBER #D4A843 bold: *0x04c0* LDG.E R24, [R26]
  GRAY: ... (14 more data loads)
  GRAY: *0x0580* FFMA R14, R14, R18, R11 ... (accumulation)

=== MIDDLE: Formula Bar ===
Centered formula in math style:
  Addr_target = base + scale × index
"base" colored purple #6C3483, "scale" colored purple #6C3483, "index" colored blue #2B5EA7, "Addr_target" colored amber #D4A843.
Thin arrows from "base" and "scale" pointing to TT's Base Address and Scale columns.

=== LOWER RIGHT TOP: Target Table (TT) ===
PURPLE #6C3483 header bar with white bold text: "Target Table (TT)" on left, "8 entries" in smaller white text on right.

Table with GROUPED columns using thin vertical gaps between groups:

Group "Entry": 
  | Idx |
Group "Status":
  | V |  (Valid bit)
Group "Target Descriptor":
  | Base Address | Scale | Type |

Data rows (monospace hex, regular text for others):
Row 0: 0 | GREEN #5AA469 checkmark | c[0x0][0x180] | 4B | f32
Row 1: 1 | GREEN checkmark | 0x7FC4B7E40000 | 4B | f32
Row 2: 2 | GREEN checkmark | 0x7FC4B8100000 | 8B | f64
Row 3: 3 | GRAY dash (invalid) | — | — | —

Small annotation below TT in italic: "CAM: lookup by (base, scale)"

=== LOWER LEFT: Chain Table (CT) ===
BLUE #2B5EA7 header bar with white bold text: "Chain Table (CT)" on left, "32 entries" in smaller white text on right.

Table with GROUPED columns (DMP-style grouped headers with sub-headers):

Group "Identification" (light blue #E8F0FE tinted background):
  | V | Index PC |
Group "Target Mapping" (light purple #F0E8F8 tinted background):  
  | tt_idx[0] | [1] | [2] | K |
Group "Stride Learning (IST)" (light gold #FFF8E1 tinted background):
  | Iter Stride | Stride Valid |

Data rows (3 shown + ellipsis):
Row 0: GREEN sq | 0x03d0 | 0 | — | — | 1 | 64 B | TRUE (green)
Row 1: GREEN sq | 0x03e0 | 0 | — | — | 1 | 64 B | TRUE (green)
Row 2: GREEN sq | 0x0A20 | 0 | 1 | — | 2 | 16 B | TRUE (green)
... (ellipsis row in gray)

=== LOWER RIGHT BOTTOM: IST Block ===
Blue #2B5EA7 outlined box with white background, title "Iteration Stride Tracker (IST)" in bold above.
Compact visual showing stride computation example:

  PC 0x03d0, Warp 0:
    iter i:   A1 = 0x7FC4D0DA4864
    iter i+1: A2 = 0x7FC4D0DA48A4
    stride = A2 − A1 = 0x40 = 64 B

Small italic note at bottom: "★ Any warp can contribute"
LEFT-pointing arrow from IST to CT's "Iter Stride" column, showing IST feeds stride into CT.

=== KEY ARROWS (CORRECT DIRECTIONS — VERIFY EACH) ===
1. SASS → CT: BLACK solid arrows from SASS blue lines (PC 0x03d0, 0x03e0) pointing DOWN to CT rows with same PC. Small numbered circles ① ② on these arrows. Label: "CD detects chain"
2. CT → TT CONVERGENCE: BLACK solid arrows from CT column "tt_idx[0]" (showing value "0") pointing RIGHT to TT Row 0. MULTIPLE CT rows' arrows CONVERGE to the SAME TT row. This is the key visual — draw 3 arrows from CT rows 0,1 all pointing to TT entry 0. Bold annotation near convergence: "16 CT entries → 1 TT entry (many-to-one)"
3. SASS → TT: GRAY dashed arrows from IMAD.WIDE operands "c[0x180]" and "R16" pointing to TT's Base Address and Scale. Label: "operands"
4. IST → CT: Thin arrow from IST block pointing LEFT to CT stride column
5. Formula → TT: Short thin arrows from formula "base"/"scale" to TT columns

=== ANNOTATIONS ===
Bold colored text placed in whitespace, with thin pointing lines. NO background boxes around annotations.
1. Near CT→TT convergence: "Many-to-one: 16 index PCs share 1 target" in bold #2C3E50, 8pt
2. Near SASS right margin: colored brackets already serve as annotation
3. Near IST: the stride computation IS the annotation

=== STYLE RULES ===
- CT header: BLUE #2B5EA7 fill, white text (storage unit)
- TT header: PURPLE #6C3483 fill, white text (distinguishes from CT visually)
- Column group sub-headers: light tinted backgrounds (blue/purple/gold) as specified above
- Data rows: white background, black monospace text for hex, regular for numbers
- Valid bits: small green #5AA469 filled squares
- "TRUE"/"FALSE" in stride_valid: green/gray colored text
- All box corners: 4-6pt radius
- Print-friendly: distinguishable in grayscale
- NO title at top of figure
- Bottom legend: "■ Storage (Blue) ■ Logic (Purple) □ External — Training path ⟶ --- Index PF --- Data PF"
