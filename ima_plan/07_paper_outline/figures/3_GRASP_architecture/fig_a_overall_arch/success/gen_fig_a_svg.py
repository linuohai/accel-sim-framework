#!/usr/bin/env python3
"""Generate GRASP architecture diagram (Fig A) as editable SVG.
Combines V2's SM layout (GRASP above L1) with V1's compact GRASP detail."""

W, H = 1400, 680

# Colors
BLUE    = '#2B5EA7'
PURPLE  = '#6C3483'
WHITE   = '#FFFFFF'
BORDER  = '#2C3E50'
GREEN   = '#27AE60'
RED     = '#C0392B'
GRAY_A  = '#BDC3C7'
DGRAY   = '#808080'
BG      = '#F8F8F8'

parts = []
def add(s): parts.append(s)

# ── SVG helpers ──────────────────────────────────────────

def rect(x, y, w, h, fill=WHITE, stroke='black', sw=1.5, rx=6, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '\
           f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>'

def txt(x, y, s, fill='black', sz=12, bold=False, italic=False, anchor='middle', family=None):
    w = ' font-weight="bold"' if bold else ''
    i = ' font-style="italic"' if italic else ''
    fam = f' font-family="{family}"' if family else ''
    return f'<text x="{x}" y="{y}" fill="{fill}" font-size="{sz}"{w}{i}'\
           f' text-anchor="{anchor}"{fam}>{s}</text>'

def ln(x1, y1, x2, y2, stroke='black', sw=1.5, dash=None, mk=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    m = f' marker-end="url(#{mk})"' if mk else ''
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '\
           f'stroke="{stroke}" stroke-width="{sw}"{d}{m}/>'

def pline(pts, stroke='black', sw=1.5, dash=None, mk=None):
    p = ' '.join(f'{x},{y}' for x,y in pts)
    d = f' stroke-dasharray="{dash}"' if dash else ''
    m = f' marker-end="url(#{mk})"' if mk else ''
    return f'<polyline points="{p}" fill="none" stroke="{stroke}" '\
           f'stroke-width="{sw}"{d}{m}/>'

def cnum(cx, cy, n):
    return (f'<circle cx="{cx}" cy="{cy}" r="11" fill="{BORDER}"/>\n'
            f'<text x="{cx}" y="{cy+4}" fill="white" font-size="11" '
            f'font-weight="bold" text-anchor="middle">{n}</text>')

def box(x, y, w, h, fill, abbr, full, abbr_sz=13):
    """Component box: abbreviation + full name, white text on colored fill."""
    return '\n'.join([
        rect(x, y, w, h, fill=fill, stroke='black', sw=1.5),
        txt(x+w/2, y+h/2-3, abbr, fill='white', sz=abbr_sz, bold=True),
        txt(x+w/2, y+h/2+11, full, fill='white', sz=8),
    ])

# ── Header + Defs ────────────────────────────────────────

add(f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     width="7in" height="3.4in" viewBox="0 0 {W} {H}"
     font-family="Times New Roman, serif">
<defs>''')

for mid, color in [('arr-k', BORDER), ('arr-g', GREEN), ('arr-r', RED),
                    ('arr-y', GRAY_A), ('arr-d', DGRAY)]:
    add(f'  <marker id="{mid}" viewBox="0 0 10 7" refX="9" refY="3.5" '
        f'markerWidth="8" markerHeight="6" orient="auto">'
        f'<polygon points="0 0,10 3.5,0 7" fill="{color}"/></marker>')

add('</defs>\n')

# White background
add(f'<rect width="{W}" height="{H}" fill="white"/>\n')

# ── SM Pipeline (LEFT, from V2 layout) ───────────────────

add('<!-- ====== SM Pipeline ====== -->')
add('<g id="sm-pipeline">')

# SM enclosure
add(rect(15, 10, 305, 460, fill=BG, stroke=BORDER, sw=1.5, rx=8))
add(txt(167, 32, 'Streaming Multiprocessor (SM)', fill=BORDER, sz=12, bold=True))

# Warp Scheduler
add(rect(35, 48, 260, 36, fill=WHITE, stroke=BORDER))
add(txt(165, 71, 'Warp Scheduler', fill=BORDER, sz=11))

# Issue Stage
add(rect(35, 96, 260, 36, fill=WHITE, stroke=BORDER))
add(txt(165, 119, 'Issue Stage', fill=BORDER, sz=11))

# GRASP Prefetcher (blue, bigger — V2 improvement)
add(rect(35, 146, 260, 55, fill=BLUE, stroke='black'))
add(txt(165, 170, 'GRASP', fill='white', sz=14, bold=True))
add(txt(165, 186, 'Prefetcher', fill='white', sz=10))

# Expansion dashed line to detail
add(ln(295, 173, 348, 173, stroke=GRAY_A, sw=1.5, dash='4,3'))

# L1 D-Cache (smaller than GRASP — V2 improvement)
add(rect(35, 216, 260, 68, fill=WHITE, stroke=BORDER))
add(txt(200, 242, 'L1 D-Cache', fill=BORDER, sz=11))
add(rect(45, 255, 72, 24, fill=WHITE, stroke='#888', sw=1, rx=3))
add(txt(81, 271, 'MSHR', fill='#555', sz=9))

add('</g>\n')

# L2 Cache (below SM)
add('<g id="l2-cache">')
add(rect(35, 510, 260, 36, fill=WHITE, stroke=BORDER))
add(txt(165, 533, 'L2 Cache', fill=BORDER, sz=11))
add('</g>\n')

# L1 ↔ L2 arrows (dark gray — distinct from Training Path)
add('<g id="l1-l2-arrows">')
add(ln(125, 284, 125, 510, stroke=DGRAY, sw=1.5, mk='arr-d'))
add(txt(108, 405, 'Req', fill=DGRAY, sz=10, italic=True, anchor='end'))
add(ln(205, 510, 205, 284, stroke=DGRAY, sw=1.5, mk='arr-d'))
add(txt(222, 405, 'Rsp', fill=DGRAY, sz=10, italic=True, anchor='start'))
add('</g>\n')

# ── GRASP Detail (RIGHT, from V1 compact layout) ────────

add('<!-- ====== GRASP Detail ====== -->')
add('<g id="grasp-detail">')
add(rect(348, 10, 1038, 575, fill='none', stroke=GRAY_A, sw=1.5, rx=0, dash='8,5'))
add(txt(1355, 30, 'GRASP', fill=BORDER, sz=14, bold=True, anchor='end'))

# ── Chain Detection (upper) ──
add('<g id="chain-detection">')
add(txt(363, 48, 'Chain Detection', fill='#555', sz=11, bold=True, anchor='start'))

# Separator
add(ln(355, 195, 1378, 195, stroke=GRAY_A, sw=1, dash='6,3'))

# CD (purple - logic)
add(box(390, 62, 148, 65, PURPLE, 'CD', '(Chain Detector)'))

# CT (blue - storage) — custom text positioning (IST occupies lower portion)
add(rect(605, 52, 200, 100, fill=BLUE, stroke='black', sw=1.5, rx=6))
add(txt(705, 76, 'CT', fill='white', sz=13, bold=True))
add(txt(705, 92, '(Chain Table)', fill='white', sz=8))
# IST inside CT (purple - logic!)
add(rect(620, 112, 170, 32, fill=PURPLE, stroke='black', sw=1, rx=4))
add(txt(705, 133, 'IST (Iteration Stride Tracker)', fill='white', sz=8, bold=True))

# TT (blue - storage)
add(box(870, 62, 148, 65, BLUE, 'TT', '(Target Table)'))

add('</g>\n')

# ── Prefetch Generation (lower, compact like V1) ──
add('<g id="prefetch-generation">')
add(txt(363, 222, 'Prefetch Generation', fill='#555', sz=11, bold=True, anchor='start'))

# Left column (near L1)
add(box(390, 248, 170, 55, BLUE,   'PRB', '(Prefetch Request Buffer)'))
add(box(390, 335, 170, 55, PURPLE, 'ACU', '(Address Computation Unit)'))
add(box(390, 422, 170, 50, BLUE,   'PQ',  '(Prefetch Queue)'))

# Right column (internal logic)
add(box(660, 248, 170, 55, PURPLE, 'IPU', '(Index Prefetch Unit)'))
add(box(660, 335, 170, 55, PURPLE, 'DPU', '(Data Prefetch Unit)'))

# TC (same size as other components)
add(box(920, 335, 170, 55, PURPLE, 'TC', '(Throttle Controller)'))

add('</g>')
add('</g>\n')

# ── Training Path Arrows (black solid) ───────────────────

add('<!-- ====== Training Path ====== -->')
add('<g id="training-arrows">')

# Issue Stage → CD
add(ln(295, 114, 390, 94, stroke=BORDER, sw=1.5, mk='arr-k'))
add(txt(342, 84, 'Issued Instructions', fill=BORDER, sz=9, italic=True))

# CD → CT
add(ln(538, 94, 605, 94, stroke=BORDER, sw=1.5, mk='arr-k'))
add(txt(572, 86, 'Chain Entry', fill=BORDER, sz=9, italic=True))

# CT → TT
add(ln(805, 94, 870, 94, stroke=BORDER, sw=1.5, mk='arr-k'))
add(txt(838, 86, 'Target Index', fill=BORDER, sz=9, italic=True))

add('</g>\n')

# ── Prefetch Flow Arrows ─────────────────────────────────

add('<!-- ====== Prefetch Flow ====== -->')
add('<g id="prefetch-arrows">')

# ① Red dashed: CT/IST → IPU (stride, chain info)
add(ln(705, 152, 745, 248, stroke=RED, sw=1.5, dash='8,4', mk='arr-r'))
add(cnum(738, 195, '①'))
add(txt(752, 192, 'Stride, Chain Info', fill=BORDER, sz=9, italic=True, anchor='start'))

# ② Green dashed: IPU → PRB (going left)
add(ln(660, 275, 560, 275, stroke=GREEN, sw=1.5, dash='8,4', mk='arr-g'))
add(cnum(610, 263, '②'))
add(txt(610, 256, 'Index Address', fill=BORDER, sz=9, italic=True))

# ③ Green dashed: PRB → L1 (going left, reaches L1 box)
add(ln(390, 270, 295, 232, stroke=GREEN, sw=1.5, dash='8,4', mk='arr-g'))
add(cnum(348, 242, '③'))
add(txt(355, 234, 'Index Prefetch to L1', fill=BORDER, sz=8, italic=True, anchor='start'))

# ④ Green dashed: L1 → ACU (going right)
add(ln(295, 248, 390, 362, stroke=GREEN, sw=1.5, dash='8,4', mk='arr-g'))
add(cnum(330, 300, '④'))
add(txt(342, 294, 'Fill Response', fill=BORDER, sz=8, italic=True, anchor='start'))
add(txt(342, 306, '(Index Value)', fill=BORDER, sz=8, italic=True, anchor='start'))

# ⑤ Red dashed: ACU → DPU (going right)
add(ln(560, 362, 660, 362, stroke=RED, sw=1.5, dash='8,4', mk='arr-r'))
add(cnum(610, 350, '⑤'))
add(txt(610, 343, 'Data Address', fill=BORDER, sz=9, italic=True))

# ⑥ Red dashed: DPU → PQ
add(ln(660, 378, 560, 440, stroke=RED, sw=1.5, dash='8,4', mk='arr-r'))
add(cnum(615, 405, '⑥'))
add(txt(622, 400, 'Data Prefetch', fill=BORDER, sz=8, italic=True, anchor='start'))

# From PQ: two arrows going LEFT
# PQ → L1 (red dashed: data prefetch to L1)
add(ln(390, 440, 295, 240, stroke=RED, sw=1.5, dash='8,4', mk='arr-r'))
add(txt(348, 350, 'Data Prefetch', fill=BORDER, sz=8, italic=True, anchor='start'))
add(txt(348, 362, 'to L1', fill=BORDER, sz=8, italic=True, anchor='start'))

# PQ → MSHR (gray dashed: monitor MSHR)
add(ln(390, 455, 117, 268, stroke=GRAY_A, sw=1.2, dash='6,3', mk='arr-y'))
add(txt(260, 380, 'Monitor MSHR', fill='#999', sz=8, italic=True))

add('</g>\n')

# ── TC Control Arrows (gray dashed, no circles) ─────────

add('<!-- ====== TC Control ====== -->')
add('<g id="tc-arrows">')

# TC → DPU: Suppress
add(ln(920, 360, 830, 360, stroke=GRAY_A, sw=1.2, dash='6,3', mk='arr-y'))
add(txt(875, 353, 'Suppress', fill='#999', sz=8, italic=True))

# TC → PQ: Throttle (replaces long TC→MSHR routing)
add(ln(920, 375, 560, 450, stroke=GRAY_A, sw=1.2, dash='6,3', mk='arr-y'))
add(txt(750, 418, 'Throttle', fill='#999', sz=8, italic=True))

add('</g>\n')

# ── Legend ────────────────────────────────────────────────

add('<!-- ====== Legend ====== -->')
add('<g id="legend">')
ly = 600
add(rect(15, ly, 1370, 55, fill='#FAFAFA', stroke='#DDD', sw=1, rx=4))

# Arrow Legend
add(txt(35, ly+17, 'Arrow Legend', fill=BORDER, sz=10, bold=True, anchor='start'))

samples = [
    (35,  BORDER, None,   'arr-k', 'Training Path'),
    (210, GREEN,  '8,4',  'arr-g', 'Index Prefetch (Step 1)'),
    (450, RED,    '8,4',  'arr-r', 'Data Prefetch (Step 2)'),
    (680, GRAY_A, '6,3',  'arr-y', 'Control'),
]
for ax, col, dash, mk, label in samples:
    add(ln(ax, ly+38, ax+40, ly+38, stroke=col, sw=1.5, dash=dash, mk=mk))
    add(txt(ax+50, ly+42, label, fill=BORDER, sz=9, anchor='start'))

# Component Legend
add(txt(850, ly+17, 'Component Legend', fill=BORDER, sz=10, bold=True, anchor='start'))

for bx, fill, label in [(850, BLUE, 'Storage'), (960, PURPLE, 'Logic'),
                          (1070, WHITE, 'Existing HW')]:
    add(rect(bx, ly+24, 18, 18, fill=fill, stroke='black' if fill!=WHITE else BORDER, sw=1, rx=3))
    add(txt(bx+26, ly+38, label, fill=BORDER, sz=9, anchor='start'))

add('</g>\n')
add('</svg>')

# ── Write output ─────────────────────────────────────────

out = 'tmp/test/fig_a_combined.svg'
with open(out, 'w', encoding='utf-8') as f:
    f.write('\n'.join(parts))

print(f'SVG saved to {out}  ({len(parts)} elements)')
