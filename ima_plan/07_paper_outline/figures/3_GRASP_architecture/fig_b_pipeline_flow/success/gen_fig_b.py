#!/usr/bin/env python3
"""Generate Fig B v5 — V3c layout + white bg + full-width legend."""

import json, os, re, sys, subprocess, tempfile

API_KEY = os.environ.get('POE_API_KEY')
if not API_KEY:
    print("ERROR: POE_API_KEY not set"); sys.exit(1)

OUT_DIR = 'ima_plan/07_paper_outline/figures/3_GRASP_architecture/fig_b_pipeline_flow/working'

PROMPT = r"""CRITICAL EXACT SPELLING — use ONLY these names:
- "Chain Detector (CD)" - "Chain Table (CT)" - "Target Table (TT)"
- "Iteration Stride Tracker (IST)" - "Index Prefetch Unit (IPU)"
- "Data Prefetch Unit (DPU)" - "Prefetch Request Buffer (PRB)"
- "Address Computation Unit (ACU)" - "Throttle Controller (TC)"
- "Prefetch" NOT "Preftech" - "GRASP" always uppercase
- "IMAD.WIDE" - "L1 D-Cache" NOT "L1 Cashe"

Generate a professional academic algorithm flowchart for "GRASP Prefetch Pipeline".
IEEE double-column, 16:9, Times New Roman font, black outlines 1-1.5pt.
NO title. NO shadows. NO gradients. WHITE background.

LAYOUT: Two columns CLOSE together, COMPACT, information-dense.
- Left Column (8%-46%): Phase 1 top, Phase 2 bottom
- Right Column (54%-92%): Phase 3 full height
- Bottom row (full width 5%-95%): LARGE legend bar spanning the ENTIRE width
- IMPORTANT: The legend at bottom MUST stretch across the full figure width.
  It should contain enough items and spacing to FILL the entire bottom strip.
  Do NOT leave empty space on the left or right of the legend.
- The two columns should be CLOSE with only a small gap (~8%).
- Phase labels in gray italic at the top-left of each phase.
- A SOLID GRAY line (#AAAAAA, 1.5pt) horizontally separating Phase 1 and Phase 2
  in the left column. This line MUST be clearly visible, running across the full
  width of the left column, clearly dividing Chain Detection from Stride Learning.

=== Phase 1: "Chain Detection" (Left, top 55%) ===
Vertical flow, black solid arrows:
1. Rounded rect, blue #2B5EA7, white: "Instruction Issued"
2. Diamond, light blue #AED6F1, dark text: "Tracked Warp?"
   -> No: gray #BDC3C7 terminal "Skip" -> Yes: down
3. Rect, blue #2B5EA7, white bold: "Monitor Issue Stream" + "(CD)"
4. Diamond, light blue #AED6F1: "Chain Detected?"
   small: "LDG -> IMAD.WIDE -> LDG"
   -> No: gray dashed loop "Wait" -> Yes: down
5. Rect, amber #D4A843, white bold: "Record Chain Info" + "(CT + TT)"
6. Rounded rect, blue #2B5EA7, white: "Chain Recorded"

=== Phase 2: "Stride Learning" (Left, bottom 40%) ===
Vertical flow, black solid arrows:
1. Rounded rect, blue #2B5EA7, white: "Index Load Observed"
2. Rect, blue #2B5EA7, white bold: "Track Address Differences" + "(IST)"
3. Diamond, light blue #AED6F1: "Stride Stable?"
   -> No: gray dashed loop "Update" -> Yes: down
4. Rect, amber #D4A843, white bold: "Stride Converged" + "Store in CT"

=== Phase 3: "Two-Step Prefetch" (Right, full height) ===
Vertical flow:
1. Rounded rect, purple #6C3483, white: "Demand Index Load"
2. Diamond, light blue #AED6F1: "CT Hit & Stride Valid?"
   -> No: gray terminal "No Prefetch" -> Yes: down
3. Rect, purple #6C3483, white bold: "Compute Prefetch Address" + "(IPU)"
4. Rect, blue #2B5EA7, white bold: "Allocate Tracking Entry" + "(PRB)"
5. Rect, purple #6C3483, white bold: "Issue Index Prefetch" + "(to L1 D-Cache)"
   Arrow down: GREEN #27AE60 DASHED, label "Index Prefetch"
6. Dotted gap, gray italic: "Wait for Fill Response"
7. Rect, purple #6C3483, white bold: "Compute Data Address" + "(ACU)"
8. Diamond, light blue #AED6F1: "Throttle Active?" + "(TC)"
   -> Yes: gray terminal "Suppress" -> No: down
9. Rect, purple #6C3483, white bold: "Issue Data Prefetch" + "(DPU)"
   Arrow down: RED #C0392B DASHED, label "Data Prefetch"
10. Rounded rect, green #27AE60, white bold: "Demand Load -> L1 HIT"

=== Cross-Column Arrow ===
Dashed arrow (#808080, 1.5pt) from "Stride Converged" going RIGHT
to "Demand Index Load". Label: "Stride + Target Info".
This MUST physically cross from left column to right column.

=== Annotations (small gray #F0F0F0 boxes, dotted lines) ===
1. Near Phase 1: "IMAD.WIDE explicitly encodes indirect access"
2. Near Phase 2: "Converges within 2-3 observations"
3. Near Phase 3 top: "Index value determines data address"
4. Near TC: "MSHR > 40% triggers 200-cycle cooldown"

=== LEGEND (BOTTOM, FULL WIDTH — THIS IS CRITICAL) ===
The legend occupies the entire bottom strip from left edge to right edge.
It should look DENSE and INFORMATION-RICH, spanning the full 7-inch width.
Split into TWO sub-rows within the legend bar for maximum coverage:

Top sub-row — Arrow Styles (with actual colored line samples):
  Black solid line -> "Main Flow"
  Green (#27AE60) dashed line -> "Index Prefetch (Step 1)"
  Red (#C0392B) dashed line -> "Data Prefetch (Step 2)"
  Gray (#BDC3C7) dashed line -> "Loop / Skip"
  Dark gray (#808080) dashed line -> "Knowledge Transfer"

Bottom sub-row — Component Types (with colored squares):
  Blue (#2B5EA7) square -> "Training Step"
  Purple (#6C3483) square -> "Prefetch Step"
  Amber (#D4A843) square -> "Key Output / Table Write"
  Green (#27AE60) square -> "Success State"
  Light blue (#AED6F1) diamond -> "Decision Point"
  Gray (#BDC3C7) square -> "Skip / Suppress"

The legend MUST fill the entire width. Space items EVENLY across the full row.

Style constraints (MUST follow):
- Academic paper figure style, clean and professional
- White background, no decorative elements
- Black outlines (1-1.5pt) on all boxes
- Font: Times New Roman for ALL text
- Bold inside colored blocks, italic for arrow labels and annotations
- All text minimum 8pt equivalent
- Do NOT include any title or caption in the image
- Do NOT include text that is not a label, arrow label, annotation, or legend
"""

version = sys.argv[1] if len(sys.argv) > 1 else '5'

payload = json.dumps({
    'model': 'nano-banana-pro',
    'messages': [{'role': 'user', 'content': PROMPT}],
    'image_only': True,
    'aspect_ratio': '16:9',
    'image_size': '1K',
})

with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
    f.write(payload)
    pf = f.name

try:
    result = subprocess.run(
        ['curl', '-s', '--max-time', '150',
         'https://api.poe.com/v1/chat/completions',
         '-H', f'Authorization: Bearer {API_KEY}',
         '-H', 'Content-Type: application/json',
         '-d', f'@{pf}'],
        capture_output=True, text=True, timeout=160
    )

    if not result.stdout:
        print(f"Empty response")
        sys.exit(1)

    data = json.loads(result.stdout)
    content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
    urls = re.findall(r'!\[.*?\]\((https?://[^\)]+)\)', content)

    if not urls:
        print(f"No URL: {content[:300]}")
        sys.exit(1)

    out_file = f'{OUT_DIR}/figure_v{version}.png'
    subprocess.run(['curl', '-sL', urls[0], '-o', out_file], timeout=60)
    size = os.path.getsize(out_file) // 1024
    print(f"Saved: {out_file} ({size}KB)")

finally:
    os.unlink(pf)
