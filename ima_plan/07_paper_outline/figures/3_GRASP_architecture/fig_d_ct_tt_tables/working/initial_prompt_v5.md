CRITICAL EXACT SPELLING:
- "Chain Table (CT)", "Target Table (TT)", "IMAD.WIDE", "LDG.E", "SpMV", "IMA"
- "Index Load", "Addr Generation", "Data Load"

Professional academic diagram for MICRO/ISCA/HPCA. 16:9, 7.0" IEEE. Times New Roman + Courier code. NO title. NO shadows. NO gradients. White background. Black outlines 1-1.5pt.

DO NOT render any metadata, section headers, block labels, or layout percentages.

=== LAYOUT ===
Upper 2/3: three blocks (two stacked left, one tall right). Left+right tops and bottoms aligned.
Lower 1/3: one wide CT table.
Between them: a formula line.

=== UPPER LEFT TOP: SpMV CUDA Source ===
Gray #F5F5F5 rounded box, label "SpMV CUDA Kernel" gray italic.
Monospace code:
  // CSR SpMV (base.cu:22)
  for (int offset = row_begin;
       offset < row_end; offset++) {
    sum += Ax[offset] * x[Aj[offset]];
  }
Bold key line. "Aj[offset]" blue #2B5EA7 underline = "Index Load". "x[...]" amber #D4A843 underline = "Data Load".
Gray dashed arrow right to SASS, labeled "compiles to" italic.

=== UPPER LEFT BOTTOM: Target Table (TT) ===
PURPLE #6C3483 header (different from CT!), white bold text.
Title: "Target Table (TT)" bold, "Entry 0" gray italic.
Table style like DMP paper: grouped fields with thin vertical gaps between groups.
  Group 1: | Valid |
  Group 2: | Base Address | Scale |
Data row: GREEN #5AA469 square | c[0x0][0x180] (&x[]) | 4 |
Monospace for hex values. Small note "(sizeof float)" near 4.

=== UPPER RIGHT (full height): SASS Assembly ===
Gray #F5F5F5 rounded box, label "SASS Assembly (x16 Unrolled Loop)".
Monospace code, only Chain 1 and 2 colored, ALL other lines GRAY:

BLUE #2B5EA7 bold: /*03d0*/ LDG.E R9, [R6+-0x8]       (1)
BLUE #2B5EA7 bold: /*03e0*/ LDG.E R27, [R6+-0x4]      (2)
GRAY: /*03f0*/ LDG.E R13, [R6]
GRAY: /*0400*/ LDG.E R21, [R6+0x4]
GRAY italic: ... (12 more index loads)

PURPLE #6C3483 bold: /*0480*/ IMAD.WIDE R8, R9, R16, c[0x180]      (1)
PURPLE #6C3483 bold: /*0490*/ IMAD.WIDE R26, R27, R16, c[0x180]   (2)
GRAY: /*04b0*/ IMAD.WIDE R12, R13, R16, c[0x180]
GRAY italic: ... (13 more)

AMBER #D4A843 bold: /*04a0*/ LDG.E R14, [R8]     (1)
AMBER #D4A843 bold: /*04c0*/ LDG.E R24, [R26]    (2)
GRAY: /*04d0*/ LDG.E R12, [R12]
GRAY italic: ... (13 more data loads)
GRAY: /*0580*/ FFMA R14, R14, R18, R11

Right-side colored brackets: blue "IMA Index Load", purple "Addr Generation", amber "IMA Data Load"

=== FORMULA (centered, between upper and lower) ===
Use LaTeX math formatting with proper subscript:
  Addr_{data} = base + scale x index
Use proper multiplication sign (dot or times), NOT letter "x".
"base" in purple #6C3483, "scale" in purple #6C3483, "index" in blue #2B5EA7.
Upward arrows from "base" and "scale" to TT cells.

=== LOWER: Chain Table (CT) — ONE full-width table ===
BLUE #2B5EA7 header (different from TT's purple!), white bold text.
Title: "Chain Table (CT)" bold, "32 entries" gray italic.

Table style like DMP paper: GROUPED columns with group sub-headers and thin vertical gaps between groups.
Three column groups with spanning group labels:

Group "Identification": | Valid | Index PC |
Group "Target Mapping": | tt_idx[0] | Num Targets |
Group "Stride Learning": | Iter Stride | Stride Valid |

Data rows (monospace for hex, regular for numbers):
Row 1: GREEN sq | 0x03d0 | 0 | 1 | 64 B | TRUE
Row 2: GREEN sq | 0x03e0 | 0 | 1 | 64 B | TRUE
Row 3: GREEN sq | 0x03f0 | 0 | 1 | 64 B | TRUE
... (ellipsis row)

NOTE: CT does NOT have data_pc or imad_pc columns. Those are only used during detection and not stored.

=== ARROWS (CORRECT DIRECTIONS) ===
1. Gray dashed: SpMV CUDA -> SASS ("compiles to")
2. SASS to TT: Gray dashed arrows from IMAD.WIDE operands "c[0x180]" and "R16" pointing LEFT to TT Base Address and Scale cells (showing where values come from)
3. SASS to CT: Black solid arrows from SASS index load lines (/*03d0*/ and /*03e0*/) pointing DOWN to corresponding CT rows, labeled (1) and (2). Direction: FROM SASS TO CT (showing that these instructions create these CT entries)
4. CT to TT convergence: Black solid arrows from CT tt_idx[0] column (all showing "0") pointing UP-LEFT to TT Entry 0, converging to show many-to-one mapping
5. Formula to TT: Short upward arrows from formula terms to TT cells

=== ANNOTATIONS (bold text, NOT dialog boxes) ===
Just bold colored text placed in blank areas with thin pointing lines:
1. Near the convergence arrows: "16 CT entries -> 1 TT entry" in bold dark text
2. Near CT stride column: "Stride = 64B (x16 unroll x 4B/element)" in smaller text

=== STYLE ===
Blue #2B5EA7 for CT header, Purple #6C3483 for TT header (MUST be different colors).
Green #5AA469 for Valid squares. Amber #D4A843 for Data Load.
Tables: DMP-style grouped columns with sub-headers, thin gaps between groups, clean borders.
Compact layout. Print-friendly.
