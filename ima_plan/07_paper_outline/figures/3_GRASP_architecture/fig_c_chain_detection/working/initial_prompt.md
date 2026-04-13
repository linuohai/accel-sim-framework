CRITICAL EXACT SPELLING — use ONLY these names, do NOT invent alternatives:
- "Chain Detector (CD)" — NOT "Conflict Detector"
- "Chain Table (CT)" — NOT "Context Table"
- "Target Table (TT)" — NOT "Translation Table"
- "FIFO" — always uppercase
- "LOAD_RESULT" and "IMA_ADDR_COMPUTE" — exact entry type names
- "IMAD.WIDE" — NOT "IMAD WIDE" or "IMAD_WIDE"
- "LDG.E" or "LDG" — standard SASS load
- "CHAIN CONFIRMED" — the detection event
- "Prefetch" NOT "Preftech" — "GRASP" always uppercase

Generate a professional academic diagram showing the GRASP Chain Detection mechanism
for a MICRO/ISCA/HPCA computer architecture paper.
IEEE double-column full width (7.0"), 16:9 aspect ratio. Times New Roman font.
Black outlines (1-1.5pt). NO title. NO shadows. NO gradients. WHITE background.

This figure has THREE HORIZONTAL LAYERS stacked vertically, sharing a time axis (left to right).
COMPACT layout — minimize vertical gaps between layers.

=== LAYER 1 (Top, 2%-14%): SASS Source Code Snippet ===
A light gray (#F5F5F5) rounded box with monospace text showing 5 lines of GPU assembly.
Left side label: "SASS Code" in gray italic.

Line 1 (gray #BDC3C7 text): "FADD R1, R2, 3.0"
Line 2 (BLUE #2B5EA7 bold, with blue #2B5EA7 left bar 3pt): "LDG.E R5, [R24]       ; Index Load"
Line 3 (gray #BDC3C7 text): "FADD R4, R3, R1"
Line 4 (PURPLE #6C3483 bold, with purple #6C3483 left bar 3pt): "IMAD.WIDE R2, R5, 8, R0  ; Addr Compute"
Line 5 (AMBER #D4A843 bold, with amber #D4A843 left bar 3pt): "LDG.E R3, [R2]        ; Data Load"

Right side: curly brace grouping lines 2, 4, 5 with label "IMA Chain Pattern" in dark text.

Dashed gray arrows from each colored SASS line DOWN to its corresponding instruction block in Layer 2.

=== LAYER 2 (Middle, 17%-58%): Warp Execution Timeline ===
4 horizontal swim lanes (Warp 0 through Warp 3). Time flows LEFT to RIGHT.
Vertical dashed gray lines mark time points: t₀, t₁, t₂, t₃ across ALL lanes.

Lane labels (left side, 2%-14% width):
  "Warp 0" + "(TRACKED)" — blue #2B5EA7 bold text
  "Warp 1" + "(TRACKED)" — blue #2B5EA7 bold text
  "Warp 2" — gray #95A5A6 text
  "Warp 3" — gray #95A5A6 text

Instructions as colored rounded rectangles in each lane (16%-94% width):
  AT t₀:
    Warp 0: BLUE #2B5EA7 filled rect, white text: "LDG R5, [R24]"
    Warp 1: GRAY #BDC3C7 filled rect: "ALU OP"
  BETWEEN t₀ and t₁:
    Warp 2: GRAY #BDC3C7 rect: "ALU OP"
    Warp 3: GRAY #BDC3C7 rect: "BRANCH"
  AT t₁:
    Warp 0: PURPLE #6C3483 filled rect, white text: "IMAD.WIDE R2, R5, ..."
    Warp 1: GRAY #BDC3C7 rect: "LDG R7, [R8]"
  BETWEEN t₁ and t₂:
    Warp 2: GRAY #BDC3C7 rect: "FADD R1, R2, 3"
  AT t₂:
    Warp 0: AMBER #D4A843 filled rect, white text: "LDG R3, [R2]"
    Warp 3: GRAY #BDC3C7 rect: "FMA R9, ..."

Warp 2 and Warp 3 rows have very light background (#FAFAFA) to visually de-emphasize.
Small gray annotation box near top-right: "CD monitors only 2 tracked warps"

=== LAYER 3 (Bottom, 61%-87%): CD FIFO State Evolution ===
Aligned vertically with time markers from Layer 2. Shows step-by-step FIFO state.

AT t₀ (aligned with t₀ marker above):
  Numbered step circle: dark circle with white "1" (①)
  Label: "Push" in black bold
  One FIFO entry box (BLUE #2B5EA7 fill, white text):
    Top line: "LOAD_RESULT"
    Bottom line: "dst=R5, pc=0x640"
  Solid black arrow from Warp 0's blue LDG block DOWN to this entry.

AT t₁ (aligned with t₁ marker):
  Numbered step circle: ②
  Label: "Match + Push" in black bold
  TWO FIFO entries shown horizontally:
    Entry 1 (BLUE #2B5EA7, slightly faded/lighter): "LOAD_RESULT" + "dst=R5"
    Entry 2 (PURPLE #6C3483): "IMA_ADDR_COMPUTE" + "dst=R2, idx_pc=0x640"
  Gray italic curved arrow from Entry 1 to Entry 2: "src R5 matches dst R5"
  Solid black arrow from Warp 0's purple IMAD.WIDE DOWN to Entry 2.

AT t₂ (aligned with t₂ marker):
  Numbered step circle: ③
  Label: "Match → CHAIN CONFIRMED" in bold
  Large AMBER #D4A843 banner/box: "CHAIN CONFIRMED!" with white bold text
  Small green checkmark (✓) next to it
  Gray italic arrow from Entry 2 area: "src R2 matches dst R2"
  Solid black arrow from Warp 0's amber LDG block DOWN to this banner.

AT t₃ (aligned with t₃ marker, slightly right):
  Numbered step circle: ④
  Label: "Write Tables" in black bold
  Two small table-style boxes side by side:
    Box 1 (BLUE #2B5EA7): "CT" top, "idx_pc=0x640" + "data_pc=0x690" below
    Box 2 (BLUE #2B5EA7): "TT" top, "(base, scale)" below
  Amber dashed arrow from CHAIN CONFIRMED banner to both table boxes.

=== LEGEND (Bottom strip, 90%-98%, FULL WIDTH 5%-95%) ===
MUST stretch across the full figure width. Dense and information-rich.
Split into TWO sub-rows:

Top sub-row — Instruction Types (colored squares + text):
  Blue #2B5EA7 square → "Index Load (LDG)"
  Purple #6C3483 square → "Addr Compute (IMAD.WIDE)"
  Amber #D4A843 square → "Data Load (LDG)"
  Gray #BDC3C7 square → "Other Instructions"

Bottom sub-row — Detection Flow (line samples + text):
  Black solid arrow → "CD Tracking"
  Gray dashed arrow → "Code ↔ Runtime Mapping"
  Numbered circles ①②③④ → "Detection Steps"
  Green ✓ → "Chain Confirmed"

The legend MUST fill the entire width. Space items EVENLY.

=== STYLE CONSTRAINTS (MUST follow) ===
- Academic paper figure style, clean and professional
- White background, no decorative elements or shadows
- Black outlines (1-1.5pt) on all colored boxes
- Font: Times New Roman for labels; Courier/Monospace for SASS code ONLY
- Bold text inside colored blocks (white), italic for annotations (gray)
- All text minimum 8pt equivalent
- Color palette: Blue #2B5EA7, Purple #6C3483, Amber #D4A843, Gray #BDC3C7
- Do NOT include any title or caption in the image
- Do NOT include Chinese text or text not part of the diagram
- Keep the layout COMPACT — three layers close together
