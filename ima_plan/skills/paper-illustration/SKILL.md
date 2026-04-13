---
name: paper-illustration
description: "Generate publication-quality AI illustrations for academic papers using NanoPana image generation. Creates architecture diagrams, method illustrations with Claude-supervised iterative refinement loop. Use when user says \"生成图表\", \"画架构图\", \"AI绘图\", \"paper illustration\", \"generate diagram\", or needs visual figures for papers."
argument-hint: [description-or-figure-plan-file]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent
---

# Paper Illustration: Claude-Supervised Figure Generation for Architecture Papers

Generate publication-quality illustrations using a **multi-stage workflow** with **Claude as the STRICT supervisor/reviewer**, targeting **MICRO / ISCA / HPCA** top-tier computer architecture conferences.

## Core Design Philosophy

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    MULTI-STAGE ITERATIVE WORKFLOW                        │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   User Request                                                           │
│       │                                                                  │
│       ▼                                                                  │
│   ┌─────────────┐                                                        │
│   │   Claude    │ ◄─── Step 1: Parse request, create initial prompt     │
│   │  (Planner)  │                                                        │
│   └──────┬──────┘                                                        │
│          │                                                               │
│          ▼                                                               │
│   ┌─────────────┐                                                        │
│   │   Gemini    │ ◄─── Step 2: Optimize layout description              │
│   │  (via POE)  │      - Refine component positioning                   │
│   │  Layout     │      - Optimize spacing and grouping                  │
│   └──────┬──────┘                                                        │
│          │                                                               │
│          ▼                                                               │
│   ┌─────────────┐                                                        │
│   │   Gemini    │ ◄─── Step 3: MICRO/ISCA/HPCA style verification      │
│   │  (via POE)  │      - Check color palette compliance                 │
│   │  Style      │      - Verify arrow semantics & typography            │
│   └──────┬──────┘                                                        │
│          │                                                               │
│          ▼                                                               │
│   ┌─────────────┐                                                        │
│   │  NanoPana   │ ◄─── Step 4: Render image via POE API                 │
│   │ (nano-      │      - nano-banana-pro (default, best quality)        │
│   │  banana-pro)│      - nano-banana (budget, quick drafts)             │
│   └──────┬──────┘                                                        │
│          │                                                               │
│          ▼                                                               │
│   ┌─────────────┐                                                        │
│   │   Claude    │ ◄─── Step 5: STRICT visual review + SCORE (1-10)      │
│   │  (Reviewer) │      - Verify EVERY arrow direction                    │
│   │   STRICT!   │      - Verify EVERY block content & spelling           │
│   └──────┬──────┘      - Verify architecture_figure_style compliance     │
│          │                                                               │
│          ▼                                                               │
│   Score ≥ 9? ──YES──► Accept & Output                                    │
│          │                                                               │
│          NO                                                              │
│          │                                                               │
│          ▼                                                               │
│   Generate SPECIFIC improvement feedback ──► Loop back to Step 2        │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## Constants

- **REASONING_MODEL = `Gemini-3.1-Pro`** — Gemini for layout optimization and style checking (via POE API)
- **IMAGE_MODEL**: See table below (NanoPana models via POE API)
- **MAX_ITERATIONS = 5** — Maximum refinement rounds
- **TARGET_SCORE = 9** — Minimum acceptable score (1-10)
- **OUTPUT_DIR** = Per-figure subdirectory under `ima_plan/07_paper_outline/figures/`
- **API_KEY_ENV = `POE_API_KEY`** — Environment variable
- **API_ENDPOINT = `https://api.poe.com/v1/chat/completions`** (POE OpenAI-compatible)
- **REQUEST_FORMAT**: Custom parameters MUST be inside `extra_body` (NOT top-level). See "API Call Template" below. Legacy top-level fields `image_only`/`aspect_ratio`/`image_size` are silently rejected with SSL EOF errors.

### Available Models (all via POE API)

**Text Reasoning (Layout + Style optimization):**

| Model ID | Purpose | Notes |
|----------|---------|-------|
| `Gemini-3.1-Pro` | Layout optimization, style verification | Default reasoning model |

**Image Rendering (NanoPana):**

| Model ID | Base Model | Best For | Native Resolution | Speed |
|----------|-----------|----------|-------------------|-------|
| `nano-banana-pro` | Gemini 3 Pro Image | High quality text rendering, final figures | **Fixed 1408×768** (ignores `size` param) | Medium |
| `nano-banana-2` | Gemini latest | **Native 4K support**, fast | Honors `size: 4K` → 3840×2160 | Fast |
| `nano-banana` | Gemini 2.5 Flash | Budget, quick exploration drafts | 1K | Fast |

**Default rendering policy**:
- **For 1K/1408×768 text-heavy figures (most architecture diagrams)**: use `nano-banana-pro` (best text rendering, sharpest labels)
- **For 4K camera-ready figures**: use `nano-banana-2` (the ONLY model that actually respects `size: 4K`)
- **For quick drafts**: `nano-banana` (lowest quality)

**CRITICAL**: If you need 4K output, `nano-banana-pro` **cannot provide it natively** — either:
1. Switch to `nano-banana-2` (native 4K), or
2. Upscale `nano-banana-pro` output via PIL LANCZOS to ~3840×2143 (sufficient quality for vector-style figures with text/lines — no neural hallucination risk, works well in paper print)

**Reasoning defaults**: `Gemini-3.1-Pro` for layout optimization and style verification.

### API Call Template (POE OpenAI-Compatible)

> **CRITICAL**: Custom parameters MUST be inside `extra_body`. The POE API
> silently rejects top-level custom fields (returning SSL EOF errors — see
> "API Error Diagnostics" below). Reference:
> https://creator.poe.com/docs/external-applications/openai-compatible-api

```bash
curl -s --max-time 300 "https://api.poe.com/v1/chat/completions" \
  -H "Authorization: Bearer $POE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nano-banana-pro",
    "messages": [{"role": "user", "content": "YOUR_PROMPT_HERE"}],
    "extra_body": {
      "aspect": "16:9",
      "size": "4K"
    }
  }'
```

Response contains a CDN URL in `choices[0].message.content` as a markdown image link `![...](URL)`. Extract the URL and download with curl. Strip the `?w=&h=` query params to get the native-resolution image.

### Parameters

All custom parameters go inside `extra_body`:

| Parameter | Values | Default | Notes |
|-----------|--------|---------|-------|
| `extra_body.aspect` | `1:1`, `3:4`, `4:3`, `16:9`, `21:9`, etc. | model default | Works on all three nano-banana models |
| `extra_body.size` | `1K`, `2K`, `4K` | model default | **Only `nano-banana-2` honors `4K`**; `nano-banana-pro` silently ignores it and outputs 1408×768 |

**Best-effort passing**: POE docs explicitly state these parameters are
"best-effort" — the API forwards them to each bot, but the bot may silently
ignore unsupported values. Always verify actual output dimensions with
`PIL.Image.open(f).size`, don't trust the URL query params.

**Do NOT use top-level custom fields** like `image_only`, `aspect_ratio`,
`image_size` — these return `SSL_read: unexpected eof` errors (legacy format
from before POE adopted OpenAI-compatible API).

### Aspect Ratio Guide (IEEE Double-Column)

| Paper Layout | Width | Aspect Ratio |
|-------------|-------|-------------|
| Double-column (7.0") | Full width | `16:9` |
| Single-column (3.5") | Half width | `3:4` |

---

## MICRO / ISCA / HPCA Top-Tier Conference Style Guide

> 风格定位: **中性高对比学术风** — 实填色块 + 白字，色调中性不阴暗
> 标杆: DMP Fig 5-10 (HPCA'24), Snake Fig 14 (MICRO'23)

### Color Palette (Project-Unified)

| Category | Fill Color | Text | Usage |
|----------|-----------|------|-------|
| **Storage units** | Medium Blue **#4472C4** | White #FFFFFF | CT, TT, PRB, IST, PQ |
| **Logic units** | Medium Purple **#7B68AE** | White #FFFFFF | CD, IPU, DPU, ACU, TC |
| **Key steps** (flowchart) | Amber Gold **#D4A843** | White #FFFFFF | Write actions, key processing |
| **Success/completion** | Green **#5AA469** | White #FFFFFF | Terminal states, L1 HIT |
| **External/existing HW** | White #FFFFFF | Dark #2C3E50 | SM, L1 Cache, L2 Cache |

### Arrow Semantics (MUST use consistently)

| Path | Color | Line Style | Meaning |
|------|-------|-----------|---------|
| **Training path** | Black #2C3E50 | **Solid** | CD detection → write CT/TT |
| **Index prefetch** | Green #2D8653 | **Dashed** | IPU → PRB → L1 → fill return |
| **Data prefetch** | Red #C0392B | **Dashed** | DPU → PQ → L1 |
| **Control/monitoring** | Gray #95A5A6 | **Dashed** | TC monitors MSHR, suppress |

### Box Standards

| Parameter | Value |
|----------|-------|
| Corner radius | 4-6pt (all components uniform) |
| Border width | 1.0-1.5pt |
| Border color | Same-family dark or #2C3E50 |
| Min height | 24pt |
| Min width | 56pt |
| Spacing | ≥ 10pt between boxes |
| Padding | 6pt inside boxes |

### Component Label Format
```
┌─────────────────────┐
│        CD            │  ← abbreviation, 10pt Bold, WHITE
│  (Chain Detector)    │  ← full name, 8pt Regular, WHITE
└─────────────────────┘
```

### Typography

| Usage | Font | Weight | Size |
|-------|------|--------|------|
| Component abbreviation | Sans-serif | Bold | 10pt |
| Component full name | Sans-serif | Regular | 8pt |
| Arrow labels | Sans-serif | Italic | 8pt |
| Step numbers | Sans-serif | Bold | 9pt |
| Region labels | Sans-serif | Bold | 10pt |
| Hex/code values | Monospace | Regular | 8pt |

Dark-filled boxes → white text. White/light-filled boxes → #2C3E50 text.

### Numbered Step Circles
① ② ③ ④ ⑤ — 16pt diameter dark circle + white 9pt Bold number, placed beside arrows.

### Figure Composition Rules

#### MUST include:
- Component boxes + arrows + labels + numbered circles
- Region dashed boxes + region labels
- **Bottom legend** (arrow color → path meaning mapping)

#### MUST NOT include:
- **Title** (goes in LaTeX caption)
- **Text paragraphs** (goes in paper body)
- **Excessive annotations** (self-contained but not a text wall)
- **Shadows, gradients, 3D effects**
- **Chinese text** (all English)

### Layout Standards
- **Horizontal flow** — Left-to-right is standard for pipelines
- **Clear grouping** — Use dashed gray rectangles to group related modules
- **Consistent sizing** — Similar components should have similar sizes
- **Balanced whitespace** — Not cramped, not sparse
- **No arrow crossings** — Reorganize layout to avoid

### Print Compatibility
- Must be readable in **grayscale** (many reviewers print papers)
- Arrow semantics also differ by **line style** (solid vs dashed), not just color
- Minimum text equivalent of **8pt** when printed at column width

### What to AVOID (CRITICAL)
- ❌ Rainbow color schemes (too many colors)
- ❌ Thin, hairline arrows (arrows must be visible when printed)
- ❌ Unlabeled connections
- ❌ Heavy drop shadows, glowing effects, 3D
- ❌ Small text unreadable when printed
- ❌ **WRONG arrow directions** — UNACCEPTABLE!
- ❌ Colors darker than specified (avoid #2B3A67 etc.)
- ❌ More than 5 semantic colors

---

## GRASP Component Dictionary (Critical Spelling)

**All prompts MUST include this spelling list to avoid AI text rendering errors:**

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
```

---

## Scope

| Figure Type | Quality | Examples |
|-------------|---------|----------|
| **Architecture diagrams** | Excellent | Hardware block diagrams, prefetcher overview |
| **Pipeline/flow diagrams** | Excellent | Two-step pipeline, chain detection flow |
| **Table structure diagrams** | Good | CT/TT entry formats, PC consolidation |
| **Timing diagrams** | Good | Prefetch timing, latency comparison |
| **Worked examples** | Good | BFS end-to-end lifecycle |

**Not for:** Performance bar charts, scatter plots (use matplotlib + `plot_util.py`)

---

## Workflow: MUST EXECUTE ALL STEPS

### Step 0: Pre-flight Check

```bash
# Check API key
if [ -z "$POE_API_KEY" ]; then
    echo "ERROR: POE_API_KEY not set"
    echo "Set it: export POE_API_KEY='your-key'"
    exit 1
fi

# Create output directory (per-figure)
FIGURE_NAME="figure_name"  # Claude fills this based on request
OUTPUT_DIR="ima_plan/07_paper_outline/figures/${FIGURE_NAME}"
mkdir -p "$OUTPUT_DIR"
```

### Step 1: Claude Plans the Figure (YOU ARE HERE)

**CRITICAL: Claude must first analyze the user's request and create an initial detailed prompt.**

Parse the input: **$ARGUMENTS**

Claude's task:
1. Understand what figure the user wants
2. Read relevant style specs: `ima_plan/07_paper_outline/plot_style/architecture_figure_style.md`
3. Read figure plan if available: `ima_plan/07_paper_outline/figures/3_GRASP_architecture/figure_plan.md`
4. Identify all components, connections, data flow
5. Create a **detailed, structured prompt** for Gemini layout optimization

**Initial Prompt Template (Claude generates this for Gemini):**

```
[GRASP COMPONENT SPELLING LIST — always prepend]

Create a PROFESSIONAL publication-quality academic diagram for a computer architecture paper targeting MICRO/ISCA/HPCA conferences.

## Figure Type
[Architecture Diagram / Pipeline Flowchart / Table Structure / Timing / Worked Example]

## Visual Style: 中性高对比学术风 (Neutral High-Contrast Academic Style)
### MUST follow:
- White background, clean and professional
- NO title in the figure (title goes in LaTeX caption)
- Component boxes: SOLID COLOR FILL with WHITE text inside, rounded corners (4-6pt)
- Storage units (tables, buffers, queues): MEDIUM BLUE #4472C4 fill
- Logic units (detectors, computation): MEDIUM PURPLE #7B68AE fill
- Key steps/actions: AMBER GOLD #D4A843 fill
- Success/completion states: GREEN #5AA469 fill
- External/existing hardware: WHITE fill, dark border #2C3E50
- Arrow semantics: Black solid = Training path, Green dashed #2D8653 = Index prefetch, Red dashed #C0392B = Data prefetch, Gray dashed #95A5A6 = Control
- Lines: 1.0-1.5pt, small triangular arrowheads
- NO shadows, NO gradients, NO 3D effects
- Component labels: abbreviation Bold + (full name) Regular below
- Bottom legend showing arrow color meanings
- Numbered step circles ①②③④⑤ on key data flow arrows

### MUST NOT have:
- Any title text at the top of the figure
- Shadows, gradients, 3D perspective
- Rainbow or excessive colors
- Text paragraphs or explanations in the figure

## Components to Include (BE SPECIFIC)
1. [Component 1]:
   - Label: "[abbreviation]" + "([full name])"
   - Color: [blue #4472C4 / purple #7B68AE / amber / green / white]
   - Position: [left/center/right, top/middle/bottom]
   - Internal structure: [sub-components if any]
2. [Component 2]: ...

## Layout
- Direction: [left-to-right / top-to-bottom]
- Grouping: [how components should be grouped in dashed rectangles]
- Spacing: [tight / normal / generous]

## Connections (BE EXPLICIT ABOUT DIRECTION)
1. [Source] → [Target]: [line style], label "[data/signal name]", numbered ①
2. [Source] → [Target]: [line style], label "[data/signal name]", numbered ②
...
VERIFY: Each arrow must point to the CORRECT target!

## Additional Requirements
[Any specific requirements from user]
```

### Step 2: Gemini Layout Optimization (via POE API)

**Claude sends the initial prompt to Gemini for layout optimization.**

```bash
#!/bin/bash
# Step 2: Optimize layout using Gemini (via POE API)
# Gemini refines component positioning, spacing, grouping, arrow routing

set -e

OUTPUT_DIR="ima_plan/07_paper_outline/figures/${FIGURE_NAME}"
mkdir -p "$OUTPUT_DIR"

# The initial prompt from Claude (Step 1)
INITIAL_PROMPT='[Claude fills in the detailed prompt here]'

# Layout optimization request
LAYOUT_REQUEST="You are an expert in academic figure layout design for MICRO/ISCA/HPCA computer architecture papers.

Analyze this figure request and provide an OPTIMIZED LAYOUT DESCRIPTION:

$INITIAL_PROMPT

Provide:
1. **Optimized Component Positions**: Exact positions for each component (x,y grid or relative)
2. **Spacing Recommendations**: Specific spacing between components (tight/normal/generous per region)
3. **Grouping Strategy**: Which components grouped in dashed rectangles, region labels
4. **Arrow Routing**: Optimal paths for arrows to avoid crossings, which arrows need numbered circles
5. **Visual Hierarchy**: Size recommendations (main components larger, sub-components smaller)
6. **Aspect Ratio**: 16:9 for double-column or 3:4 for single-column

Output a DETAILED layout specification for the rendering model."

# Escape for JSON
ESCAPED=$(python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))" <<< "$LAYOUT_REQUEST")

# Call Gemini via POE API for layout optimization
RESPONSE=$(curl -s --max-time 90 "https://api.poe.com/v1/chat/completions" \
  -H "Authorization: Bearer $POE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"Gemini-3.1-Pro\",
    \"messages\": [{\"role\": \"user\", \"content\": $ESCAPED}]
  }")

# Extract layout description
LAYOUT_DESCRIPTION=$(echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
try:
    print(data['choices'][0]['message']['content'])
except:
    print('Error extracting layout')
    print(str(data)[:500], file=sys.stderr)
")

echo "=== Layout Optimization Complete ==="
echo "$LAYOUT_DESCRIPTION" > "$OUTPUT_DIR/layout_description.txt"
```

### Step 3: Gemini Style Verification (via POE API)

**Claude sends the optimized layout to Gemini for MICRO/ISCA/HPCA style verification.**

```bash
#!/bin/bash
# Step 3: Verify and enhance style compliance using Gemini (via POE API)

OUTPUT_DIR="ima_plan/07_paper_outline/figures/${FIGURE_NAME}"

# Read layout from previous step
LAYOUT=$(cat "$OUTPUT_DIR/layout_description.txt")

# Style verification request
STYLE_REQUEST="You are a MICRO/ISCA/HPCA paper figure reviewer specializing in computer architecture diagram standards.

Review and ENHANCE this figure specification for top-tier architecture conference compliance:

$LAYOUT

Ensure compliance with the 中性高对比学术风 (Neutral High-Contrast Academic) style:

### Color Palette (MUST use exactly):
- Storage units (CT, TT, PRB, IST, PQ): MEDIUM BLUE #4472C4 fill, WHITE text
- Logic units (CD, IPU, DPU, ACU, TC): MEDIUM PURPLE #7B68AE fill, WHITE text
- Key steps/actions: AMBER GOLD #D4A843 fill, WHITE text
- Success/completion: GREEN #5AA469 fill, WHITE text
- External hardware (SM, L1, L2): WHITE fill, dark border #2C3E50

### Arrow Semantics (MUST use):
- Black solid = Training path (CD detection → write CT/TT)
- Green dashed #2D8653 = Index prefetch path (IPU → PRB → L1)
- Red dashed #C0392B = Data prefetch path (DPU → PQ → L1)
- Gray dashed #95A5A6 = Control/monitoring (TC → MSHR)

### MUST verify:
- Rounded corners 4-6pt on all boxes
- Lines 1.0-1.5pt, small triangular arrowheads
- NO title, NO shadows, NO gradients, NO 3D
- Bottom legend explaining arrow colors
- Numbered step circles ①②③ on key arrows
- All text on colored boxes is WHITE
- Component labels: abbreviation Bold 10pt + full name Regular 8pt
- Print-friendly (distinguishable in grayscale via line style)

Output an ENHANCED rendering-ready specification with explicit style instructions."

# Escape and call
ESCAPED=$(python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))" <<< "$STYLE_REQUEST")

RESPONSE=$(curl -s --max-time 90 "https://api.poe.com/v1/chat/completions" \
  -H "Authorization: Bearer $POE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"Gemini-3.1-Pro\",
    \"messages\": [{\"role\": \"user\", \"content\": $ESCAPED}]
  }")

STYLE_SPEC=$(echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
try:
    print(data['choices'][0]['message']['content'])
except:
    print('Error extracting style spec')
")

echo "=== Style Verification Complete ==="
echo "$STYLE_SPEC" > "$OUTPUT_DIR/style_spec.txt"
```

### Step 4: NanoPana Image Rendering (via POE API)

**Claude sends the optimized, style-verified specification to NanoPana for rendering.**

Choose the model based on target resolution:
- **1408×768 (default)**: `nano-banana-pro` — best text quality, use for iteration and most final figures
- **Native 4K (3840×2160)**: `nano-banana-2` — only model that honors `size: 4K`
- **4K via upscaling**: render with `nano-banana-pro`, then LANCZOS upscale locally (see Step 4b below)

```python
#!/usr/bin/env python3
# Step 4: Render via POE OpenAI-compatible API
# CRITICAL: custom params MUST be inside extra_body (not top-level)

import json, subprocess, os, re
from pathlib import Path

OUTPUT_DIR = Path(f"ima_plan/07_paper_outline/figures/{FIGURE_NAME}")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "nano-banana-pro"   # or "nano-banana-2" for native 4K
ASPECT = "16:9"             # "16:9" for double-col, "3:4" for single-col
SIZE = "1K"                 # nano-banana-pro ignores this; nano-banana-2 honors 4K
ITERATION = 1

STYLE_SPEC = (OUTPUT_DIR / "style_spec.txt").read_text()

render_prompt = f"""Render a publication-quality academic diagram based on this specification:

{STYLE_SPEC}

RENDERING REQUIREMENTS:
- Publication-quality vector-style output, sharp edges, clean text
- NO title text anywhere
- Immediately understandable at a glance
"""

# Build request with extra_body (POE OpenAI-compatible format)
payload = json.dumps({
    "model": MODEL,
    "messages": [{"role": "user", "content": render_prompt}],
    "extra_body": {
        "aspect": ASPECT,
        "size": SIZE
    }
})

# Write payload to file to avoid argv length limits
payload_file = f"/tmp/render_payload_{ITERATION}.json"
Path(payload_file).write_text(payload)

# Call POE API (timeout 300s — complex figures can take 2-3 min)
RESPONSE = subprocess.run(
    ["curl", "-sS", "--max-time", "300",
     "https://api.poe.com/v1/chat/completions",
     "-H", f"Authorization: Bearer {os.environ['POE_API_KEY']}",
     "-H", "Content-Type: application/json",
     "-d", f"@{payload_file}"],
    capture_output=True, text=True
).stdout

# Parse response for API errors (rate limit, etc.) BEFORE trying to extract URL
response_obj = json.loads(RESPONSE)
if "error" in response_obj:
    err = response_obj["error"]
    raise RuntimeError(f"POE API error: {err.get('type')} — {err.get('message')}")

# Extract image URL from markdown link in response
content = response_obj["choices"][0]["message"]["content"]
urls = re.findall(r"https?://[^\s\)]+", content)
if not urls:
    raise RuntimeError(f"No image URL in response: {content[:500]}")

# Strip CDN query params (?w=&h=) to get native-resolution image
image_url = urls[0].rstrip(")").split("?")[0]

# Download
output_file = OUTPUT_DIR / f"figure_v{ITERATION}.png"
subprocess.run(["curl", "-sL", image_url, "-o", str(output_file)], check=True)

# Verify actual pixel dimensions (don't trust URL params)
from PIL import Image
img = Image.open(output_file)
print(f"✅ Saved {output_file} ({img.size[0]}x{img.size[1]}, "
      f"{output_file.stat().st_size / 1024:.1f} KB)")
```

#### Step 4b (optional): LANCZOS Upscale to 4K

If you rendered with `nano-banana-pro` (1408×768) but need 4K for camera-ready:

```python
from PIL import Image
src = OUTPUT_DIR / "figure_v_final.png"   # 1408×768 from nano-banana-pro
img = Image.open(src)

# Scale to 4K UHD width (3840), preserve aspect ratio
target_w = 3840
target_h = round(target_w * img.size[1] / img.size[0])
upscaled = img.resize((target_w, target_h), Image.LANCZOS)

dst = OUTPUT_DIR / "figure_v_final_4k.png"
upscaled.save(dst, optimize=True)
print(f"✅ LANCZOS upscale: {upscaled.size}, {dst.stat().st_size / 1024 / 1024:.2f} MB")
```

**Why LANCZOS and not neural upscaling?** For vector-style figures (colored
boxes, thin borders, crisp text), LANCZOS produces clean pixel-perfect output
with zero hallucination risk. Neural super-resolution (ESRGAN etc.) can
invent spurious details in text and thin lines that no reviewer will accept.

### Step 5: Claude STRICT Visual Review & Scoring (MANDATORY)

**Claude MUST read the generated image using the Read tool and perform a STRICT review.**

1. **Visual Analysis**: What does the image show in detail?
2. **Strengths**: What's good about it?
3. **STRICT Verification**: Check EVERY item below
4. **Score**: Rate 1-10 (10 = perfect) — BE STRICT!

**STRICT Review Template:**

```markdown
## Claude's STRICT Review of Figure v{N}

### What I See
[Describe the generated image in DETAIL - every block, every arrow]

### Strengths
- [Strength 1]
- [Strength 2]

### ═══════════════════════════════════════════════════════════════
### STRICT VERIFICATION CHECKLIST (ALL must pass for score ≥ 9)
### ═══════════════════════════════════════════════════════════════

#### A. Arrow Correctness (CRITICAL — any failure = score ≤ 6)
Check EACH arrow:
- [ ] Arrow 1: [Source] → [Target] — Correct direction? Correct line style?
- [ ] Arrow 2: [Source] → [Target] — Correct direction? Correct line style?
- ...
- [ ] Arrow semantics: Black solid=Training, Green dashed=Index PF, Red dashed=Data PF?

#### B. Block Content & Spelling (any failure = score ≤ 7)
Check EACH block against the GRASP Component Dictionary:
- [ ] "Chain Detector (CD)" — NOT "Conflict Detector" etc.?
- [ ] "Chain Table (CT)" — NOT "Context Table" etc.?
- [ ] "Target Table (TT)" — NOT "Translation Table" etc.?
- [ ] All other component names spelled correctly?
- [ ] "Prefetch" not misspelled as "Preffech"/"Preftech"?

#### C. Arrow Visibility (any failure = score ≤ 7)
- [ ] ALL arrows have visible stroke (≥1.0pt)
- [ ] ALL arrows have CLEAR arrowheads
- [ ] ALL arrows use correct colors (not random)
- [ ] NO arrows too thin or invisible

#### D. Arrow Labels (any failure = score ≤ 7)
- [ ] Arrows have labels where needed
- [ ] Labels readable (not too small)
- [ ] Labels correctly describe data flow

#### E. Style Compliance — architecture_figure_style.md (any failure = score ≤ 8)
- [ ] Storage = Blue #4472C4, Logic = Purple #7B68AE?
- [ ] Colored boxes have WHITE text?
- [ ] NO title in figure?
- [ ] NO shadows, gradients, 3D?
- [ ] Bottom legend present?
- [ ] Numbered step circles on key arrows?
- [ ] No Chinese text?

#### F. Layout & Flow (any failure = score ≤ 7)
- [ ] Clean flow direction (left-to-right or top-to-bottom)
- [ ] No arrow crossings
- [ ] Data flow traceable in 5 seconds
- [ ] Balanced spacing
- [ ] Components grouped logically in dashed rectangles

#### G. Print Readability
- [ ] Readable at column width (~3.5" or ~7.0")
- [ ] Arrow line styles (solid vs dashed) distinguishable in grayscale
- [ ] Text ≥ 8pt equivalent

### ═══════════════════════════════════════════════════════════════

### Issues Found (BE SPECIFIC)
1. [Issue 1]: [EXACTLY what is wrong] → [How to fix in next prompt]
2. [Issue 2]: [EXACTLY what is wrong] → [How to fix in next prompt]
3. [Issue 3]: [EXACTLY what is wrong] → [How to fix in next prompt]

### Score: X/10

### Score Guide:
- **10**: Flawless. Publication-ready. All checks pass.
- **9**: Excellent. Minor cosmetic issues only. Acceptable for paper.
- **8**: Good but noticeable style violations or minor content errors.
- **7**: Usable but has clear problems (wrong labels, missing components).
- **6**: Arrow direction errors or major component missing.
- **1-5**: Major failures. Reject.

### Verdict
[ ] ACCEPT (score ≥ 9 AND all critical checks pass)
[ ] REFINE (score < 9 OR any critical check fails → specific feedback for next iteration)
```

### Step 6: Decision Point

```
IF score >= 9 AND all critical checks pass:
    → Accept figure, copy to figure_final.png, DONE
ELSE IF iteration < MAX_ITERATIONS:
    → Generate SPECIFIC improvement prompt based on EXACT issues
    → Go to Step 2 (Gemini Layout) with refined prompt
ELSE:
    → Max iterations reached, show best version
    → Ask user if they want to continue or accept current best
```

### Step 7: Generate Improvement Prompt (for refinement)

**Claude generates TARGETED improvement prompt with EXACT issues:**

```
Refine this academic diagram. This is iteration {N}.

## CRITICAL: Fix These EXACT Issues (from previous review)

### Must Fix:
1. [EXACT issue]: [How to fix — be specific about component names, arrow directions, etc.]
2. [EXACT issue]: ...

### Keep These Good Elements:
- [What to preserve from previous version]

## Generate the improved figure with ALL issues fixed.
```

### Step 8: Final Output

When figure is accepted (score ≥ 9):

1. Copy best version to `figure_final.png` (1408×768 from nano-banana-pro)
2. **For camera-ready 4K**: Either (a) re-render with `nano-banana-2` + `extra_body.size: "4K"`, OR (b) LANCZOS upscale `figure_final.png` to 3840×2143 (see Step 4b). Do NOT try `image_size` field on `nano-banana-pro` — it's silently ignored
3. Generate LaTeX snippet:

```latex
\begin{figure}[t]  % or figure* for double-column
    \centering
    \includegraphics[width=\columnwidth]{figures/FIGURE_NAME/figure_final.png}
    \caption{[Caption based on user's original request].}
    \label{fig:[label]}
\end{figure}
```

---

## Key Rules (MUST FOLLOW)

1. **NEVER skip the review step** — Always Read and STRICTLY score the image
2. **NEVER accept score < 9** — Keep refining until excellence
3. **VERIFY EVERY ARROW DIRECTION** — Wrong direction = automatic fail (score ≤ 6)
4. **VERIFY SPELLING** — Check against GRASP Component Dictionary every time
5. **BE SPECIFIC in feedback** — "CD labeled as Conflict Detector, should be Chain Detector" not "name is wrong"
6. **SAVE all iterations** — `figure_v1.png`, `figure_v2.png`, ..., `figure_final.png`
7. **Claude is the STRICT boss** — Accept only excellence
8. **ARROW CORRECTNESS IS NON-NEGOTIABLE**
9. **USE architecture_figure_style.md** — All style decisions come from this spec
10. **NEVER DOWNGRADE MODELS** — See Model Policy below
11. **PREPEND SPELLING LIST** to every image generation prompt

## Model Policy (STRICTLY ENFORCED)

**Rendering — default**: Use `nano-banana-pro` for iterative and final renders at 1408×768 (its fixed native resolution). Its text rendering quality is the best among the NanoPana family.

**Rendering — 4K camera-ready**: For 4K output (e.g., final submission at 3840×2160), use `nano-banana-2` — it is the ONLY model that honors `extra_body.size: "4K"`. Do not expect `nano-banana-pro` to produce 4K; it silently ignores the `size` parameter.

**Rendering — alternative for 4K**: If `nano-banana-2` is rate-limited, upscale `nano-banana-pro` output with PIL LANCZOS (3840×2143 for 16:9). For vector-style figures with text/lines, LANCZOS is essentially lossless and has no neural hallucination risk.

**DO NOT** downgrade to `nano-banana` (Gemini 2.5 Flash) except for exploratory drafts — its text rendering is too poor for final figures.

**Reasoning**: MUST use `Gemini-3.1-Pro` for both Step 2 (layout optimization) and Step 3 (style verification). Do NOT skip these steps or substitute other models.

**API Error Diagnostics (READ FIRST before assuming rate limiting)**:

Different error signatures indicate different root causes — the wrong diagnosis leads to wasted 10-minute waits:

| Error Signature | Root Cause | Fix |
|-----------------|------------|-----|
| `curl: (35/56) SSL_read: unexpected eof while reading` | **Wrong request format** — custom fields at top level | Move `aspect`/`size` inside `extra_body` object |
| JSON: `{"error": {"type": "rate_limit_exceeded"}}` | Model genuinely rate-limited | Wait 5-10 minutes, retry |
| HTTP 403 | Auth failure | Check `POE_API_KEY` env var |
| curl max-time exceeded (>300s) | Model overloaded processing complex prompt | Shorten prompt, retry later |
| Empty response, no error | Network hiccup | Retry once |

**CRITICAL — SSL EOF ≠ rate limiting**. SSL EOF means the API silently rejected the request body because a top-level field was unrecognized. Always verify request format BEFORE assuming the API is down. Example of common mistake:

```json
// ❌ WRONG — returns curl exit 35/56 SSL EOF:
{"model": "nano-banana-pro", "image_only": true, "aspect_ratio": "16:9", "image_size": "1K"}

// ✅ CORRECT — returns normal response:
{"model": "nano-banana-pro", "extra_body": {"aspect": "16:9", "size": "1K"}}
```

**Rate Limiting / Timeout Recovery**:
- Genuine rate limits return a proper JSON `{"error": {...rate_limit_exceeded...}}`, NOT SSL EOF
- **Wait 5–10 minutes**, then retry. Do NOT immediately retry in a loop — this worsens the rate limit
- If `nano-banana-pro` is rate-limited and you need 1K output, wait for it. If you need 4K and `nano-banana-2` is rate-limited, LANCZOS-upscale `nano-banana-pro` output as an immediate workaround
- Before retrying the full prompt, send a minimal health check (`"red circle"`) to confirm the model is back
- To minimize rate limiting: keep each iteration to 3–4 API calls (1 Gemini layout + 1 Gemini style + 1 render), avoid excessive retries

**Discovered on 2026-04-07**: The legacy top-level fields `image_only`, `aspect_ratio`, `image_size` are no longer accepted — POE migrated to OpenAI-compatible format where custom params go in `extra_body`. Also, `nano-banana-pro`'s `size` parameter is ignored (native fixed 1408×768).

## Model Summary

| Stage | Model | Platform | Purpose |
|-------|-------|----------|---------|
| Step 1 | Claude | Native | Parse request, create initial prompt |
| Step 2 | Gemini-3.1-Pro | POE API | Layout optimization (positioning, spacing, grouping) |
| Step 3 | Gemini-3.1-Pro | POE API | MICRO/ISCA/HPCA style verification |
| Step 4a | `nano-banana-pro` | POE API | **Default** iterative + final rendering (1408×768, best text quality) |
| Step 4b | `nano-banana-2` | POE API | **Only when 4K native is required** (honors `size: 4K`) |
| Step 4c | PIL LANCZOS (local) | Python | **Fallback for 4K** if `nano-banana-2` rate-limited (upscale from 1408×768 → 3840×2143) |
| Step 5 | Claude | Native | STRICT visual review and scoring |

## Output Structure

```
ima_plan/07_paper_outline/figures/{figure_name}/
├── layout_description.txt  # Step 2: Gemini layout optimization output
├── style_spec.txt          # Step 3: Gemini style verification output
├── figure_v1.png           # Iteration 1 (NanoPana render)
├── figure_v2.png           # Iteration 2
├── figure_v3.png           # Iteration 3 (if needed)
├── figure_final.png        # Accepted version (score ≥ 9)
├── latex_include.tex       # LaTeX snippet
└── review_log.md           # All review scores and STRICT feedback
```

## Reference Files

| File | Purpose |
|------|---------|
| `ima_plan/07_paper_outline/plot_style/architecture_figure_style.md` | Authoritative style spec (colors, boxes, arrows, typography) |
| `ima_plan/07_paper_outline/plot_style/figure_prompts.md` | Prompt templates by figure type |
| `ima_plan/07_paper_outline/figures/3_GRASP_architecture/figure_plan.md` | §3 figure plan (7 figures A-G) |
| `ima_plan/07_paper_outline/figures/3_GRASP_architecture/catalog.md` | Exploration catalog with ratings |
| `.claude/commands/generate-image.md` | Low-level API reference |
