#!/usr/bin/env python3
"""SVG -> PDF converter for figures/2-Background_Motivation/IMA_chain.drawio.svg.

drawio's exported SVG has two cairosvg-incompatible features that we patch
before rendering:

1. CSS `light-dark(X, Y)` color functions for theme adaptation. cairosvg
   doesn't understand them. We strip them recursively to the light value.

2. The bottom-row legend label `<b>IMAD.WIDE</b>` is wrapped in a
   `<switch>` whose foreignObject (HTML) is followed by a PNG fallback.
   cairosvg can't render HTML, so it uses the PNG -- which drawio
   pre-rendered into a 58 px box that is too narrow for the 9-char bold
   label, clipping the leading "I" to "MAD.WIDE". We replace the entire
   `<switch>` with a native SVG `<text>` element that cairosvg can draw
   without any layout constraints.

Run after editing IMA_chain.drawio.svg to regenerate IMA_chain.pdf.
"""

from pathlib import Path

import cairosvg

HERE = Path(__file__).resolve().parent
SVG_PATH = (HERE.parent / "latex_template" / "figures"
            / "2-Background_Motivation" / "IMA_chain.drawio.svg")
PDF_PATH = SVG_PATH.with_suffix(".pdf").with_name("IMA_chain.pdf")


def strip_light_dark(text: str) -> str:
    """Recursively replace light-dark(X, Y) with X (proper paren nesting)."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        if text[i:i + 11] == 'light-dark(':
            depth = 1
            j = i + 11
            while j < n and depth > 0:
                if text[j] == '(':
                    depth += 1
                elif text[j] == ')':
                    depth -= 1
                j += 1
            inner = strip_light_dark(text[i + 11:j - 1])
            depth = 0
            cut = -1
            for k, ch in enumerate(inner):
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                elif ch == ',' and depth == 0:
                    cut = k
                    break
            replacement = inner[:cut].strip() if cut != -1 else inner.strip()
            out.append(replacement)
            i = j
        else:
            out.append(text[i])
            i += 1
    return ''.join(out)


def replace_imad_label_switch(svg: str) -> str:
    """Replace the <switch> wrapping the bottom <b>IMAD.WIDE</b> label
    with a native SVG <text> element so cairosvg renders it cleanly."""
    target = '<b>IMAD.WIDE</b>'
    label_pos = svg.find(target)
    if label_pos == -1:
        raise RuntimeError("Bottom <b>IMAD.WIDE</b> label not found in SVG")
    sw_start = svg.rfind('<switch', 0, label_pos)
    sw_end = svg.find('</switch>', label_pos) + len('</switch>')
    if sw_start == -1 or sw_end == -1:
        raise RuntimeError("Enclosing <switch> not found")
    # Centre the text on the original cell rect (x=5, y=162, w=60, h=30):
    # midpoint x=35, baseline near y=183 for visual centring of 12pt bold.
    replacement = (
        '<text x="35" y="183" '
        'font-family="Helvetica, Arial, sans-serif" '
        'font-size="12" font-weight="bold" '
        'text-anchor="middle" fill="#000000">IMAD.WIDE</text>'
    )
    return svg[:sw_start] + replacement + svg[sw_end:]


def main():
    if not SVG_PATH.exists():
        raise FileNotFoundError(SVG_PATH)
    svg = SVG_PATH.read_text()
    svg = strip_light_dark(svg)
    svg = replace_imad_label_switch(svg)
    cairosvg.svg2pdf(bytestring=svg.encode("utf-8"), write_to=str(PDF_PATH))
    print(f"Wrote {PDF_PATH} ({PDF_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
