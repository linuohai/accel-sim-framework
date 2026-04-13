#!/bin/bash
# Generate 15 architecture figure variants (5 palettes x 3 figures: A, B, C)
set -euo pipefail

BASE_DIR="/workspace/prefetch/ima_plan/07_paper_outline/figures/3_GRASP_architecture"

SPELLING_LIST='EXACT SPELLING — use these terms exactly as written, do not paraphrase or abbreviate: Streaming Multiprocessor (SM), Chain Detector (CD), Chain Table (CT), Target Table (TT), Iteration Stride Tracker (IST), Index Prefetch Unit (IPU), Data Prefetch Unit (DPU), Prefetch Request Buffer (PRB), Address Computation Unit (ACU), Throttle Controller (TC), Prefetch Queue (PQ), L1 D-Cache, MSHR, L2 Cache.'

generate_image() {
    local prompt="$1"
    local outfile="$2"
    local aspect="$3"
    local label="$4"

    echo "  Generating: $label → $(basename $outfile)"

    local payload
    payload=$(jq -n \
        --arg model "nano-banana" \
        --arg content "$prompt" \
        --arg aspect "$aspect" \
        '{
            model: $model,
            messages: [{role: "user", content: $content}],
            image_only: true,
            aspect_ratio: $aspect,
            image_size: "1K"
        }')

    local response
    response=$(curl -s --max-time 120 "https://api.poe.com/v1/chat/completions" \
        -H "Authorization: Bearer $POE_API_KEY" \
        -H "Content-Type: application/json" \
        -d "$payload" 2>&1) || { echo "  FAIL (curl error): $label"; return 1; }

    local url
    url=$(echo "$response" | jq -r '.choices[0].message.content' 2>/dev/null | grep -oP '!\[.*?\]\(\K[^)]+' | head -1)

    if [ -z "$url" ]; then
        # Try plain URL
        url=$(echo "$response" | jq -r '.choices[0].message.content' 2>/dev/null | grep -oP 'https?://[^\s\)]+' | head -1)
    fi

    if [ -z "$url" ]; then
        echo "  FAIL (no URL): $label"
        echo "  Response: $(echo "$response" | head -c 300)"
        return 1
    fi

    curl -s --max-time 60 -o "$outfile" "$url" || { echo "  FAIL (download): $label"; return 1; }

    local fsize
    fsize=$(stat -c%s "$outfile" 2>/dev/null || echo 0)
    if [ "$fsize" -lt 1000 ]; then
        echo "  FAIL (too small ${fsize}B): $label"
        return 1
    fi
    echo "  OK: ${fsize} bytes"
}

# ============================================================
# PALETTE DEFINITIONS
# ============================================================
declare -A PAL_STORAGE PAL_LOGIC PAL_KEY PAL_SUCCESS PAL_TRAINING PAL_INDEX PAL_DATA

PAL_STORAGE[blue_purple]="#4472C4"; PAL_LOGIC[blue_purple]="#7B68AE"; PAL_KEY[blue_purple]="#D4A843"; PAL_SUCCESS[blue_purple]="#5AA469"
PAL_TRAINING[blue_purple]="black solid"; PAL_INDEX[blue_purple]="#2D8653 green dashed"; PAL_DATA[blue_purple]="#C0392B red dashed"

PAL_STORAGE[teal_coral]="#2D8B7E"; PAL_LOGIC[teal_coral]="#E07B54"; PAL_KEY[teal_coral]="#4A90D9"; PAL_SUCCESS[teal_coral]="#6BAF73"
PAL_TRAINING[teal_coral]="#2C3E50 solid"; PAL_INDEX[teal_coral]="#2D8B7E teal dashed"; PAL_DATA[teal_coral]="#E07B54 coral dashed"

PAL_STORAGE[navy_steel]="#1B4F72"; PAL_LOGIC[navy_steel]="#5B9BD5"; PAL_KEY[navy_steel]="#F0B429"; PAL_SUCCESS[navy_steel]="#27AE60"
PAL_TRAINING[navy_steel]="#1B4F72 solid"; PAL_INDEX[navy_steel]="#27AE60 green dashed"; PAL_DATA[navy_steel]="#E74C3C red dashed"

PAL_STORAGE[indigo_slate]="#3F37C9"; PAL_LOGIC[indigo_slate]="#6C757D"; PAL_KEY[indigo_slate]="#F77F00"; PAL_SUCCESS[indigo_slate]="#06D6A0"
PAL_TRAINING[indigo_slate]="#3F37C9 solid"; PAL_INDEX[indigo_slate]="#06D6A0 mint dashed"; PAL_DATA[indigo_slate]="#EF476F pink dashed"

PAL_STORAGE[sage_terracotta]="#6B8E6B"; PAL_LOGIC[sage_terracotta]="#C0714A"; PAL_KEY[sage_terracotta]="#5B7DB1"; PAL_SUCCESS[sage_terracotta]="#3A7D44"
PAL_TRAINING[sage_terracotta]="#4A4A4A solid"; PAL_INDEX[sage_terracotta]="#3A7D44 forest dashed"; PAL_DATA[sage_terracotta]="#C0714A terracotta dashed"

PALETTES="blue_purple teal_coral navy_steel indigo_slate sage_terracotta"

make_style_block() {
    local pal="$1"
    cat <<STYLEEOF
Style: Academic paper figure for IEEE/ACM architecture conference (MICRO/ISCA/HPCA).
- White background, clean and professional
- NO title in the figure. Do NOT put any title text at the top.
- Component boxes: SOLID COLOR FILL with WHITE text inside. Rounded corners (4-6pt).
- Storage units (CT, TT, PRB, PQ): ${PAL_STORAGE[$pal]} fill, white text
- Logic/processing units (CD, IPU, DPU, ACU, TC): ${PAL_LOGIC[$pal]} fill, white text
- Key action steps: ${PAL_KEY[$pal]} fill, white text
- Success/completion states: ${PAL_SUCCESS[$pal]} fill, white text
- External hardware (Warp Scheduler, Issue Stage, L1 D-Cache, L2 Cache): WHITE fill, dark border #2C3E50
- Training path arrows: ${PAL_TRAINING[$pal]} lines with arrowheads
- Index prefetch path arrows: ${PAL_INDEX[$pal]} lines with arrowheads
- Data prefetch path arrows: ${PAL_DATA[$pal]} lines with arrowheads
- Control/feedback arrows: gray #95A5A6 dashed lines
- NO shadows, NO gradients, NO 3D effects. NO title text at top.
- Legend at bottom of figure showing arrow types and box color meanings.
STYLEEOF
}

# ============================================================
# FIG A — Overall Architecture (16:9)
# ============================================================
make_fig_a_prompt() {
    local pal="$1"
    local style
    style=$(make_style_block "$pal")
    cat <<PROMPTEOF
$SPELLING_LIST

Draw a hardware architecture block diagram for the GRASP GPU prefetcher.

Layout: Two horizontal bands.

TOP BAND (occupying ~75% height): labeled "Streaming Multiprocessor (SM)" with a light gray (#F5F5F5) background rectangle.

LEFT SIDE of top band (~30% width): White boxes stacked vertically, connected by downward arrows:
  "Warp Scheduler" (top) then "Issue Stage" (middle) then "L1 D-Cache" (large box at bottom, with a smaller "MSHR" sub-box drawn inside it).
  These are external hardware: white fill, dark #2C3E50 border.

RIGHT SIDE of top band (~65% width): A dashed-border rectangle labeled "GRASP Prefetcher" containing two logical sub-regions:
  Sub-region 1 "Chain Detection" (top-right area):
    - Chain Detector (CD) box: ${PAL_LOGIC[$pal]} fill, white text
    - Chain Table (CT) box: ${PAL_STORAGE[$pal]} fill, white text, with "IST" (Iteration Stride Tracker) shown as a small embedded sub-box inside CT
    - Target Table (TT) box: ${PAL_STORAGE[$pal]} fill, white text
  Sub-region 2 "Prefetch Generation" (bottom-right area):
    - Index Prefetch Unit (IPU) box: ${PAL_LOGIC[$pal]} fill
    - Prefetch Request Buffer (PRB) box: ${PAL_STORAGE[$pal]} fill
    - Address Computation Unit (ACU) box: ${PAL_LOGIC[$pal]} fill
    - Data Prefetch Unit (DPU) box: ${PAL_LOGIC[$pal]} fill
    - Throttle Controller (TC) box: ${PAL_LOGIC[$pal]} fill, small
    - Prefetch Queue (PQ) box: ${PAL_STORAGE[$pal]} fill, narrow vertical shape

BOTTOM BAND (~20% height): "L2 Cache" white box, dark border, spanning full width.

Arrows with numbered circle labels:
  (1) Issue Stage to CD: ${PAL_TRAINING[$pal]} arrow (training path)
  (2) IPU to PRB: ${PAL_INDEX[$pal]} arrow (index prefetch)
  (3) PRB to L1 D-Cache: ${PAL_INDEX[$pal]} arrow (index prefetch)
  (4) L1 D-Cache fill to ACU: ${PAL_INDEX[$pal]} arrow (index return)
  (5) DPU to PQ: ${PAL_DATA[$pal]} arrow (data prefetch)
Also draw:
  CD to CT and CD to TT: ${PAL_TRAINING[$pal]} arrows
  CT to IPU: gray #95A5A6 dashed arrow (control)
  PQ to L1 D-Cache: ${PAL_DATA[$pal]} arrow
  TC to MSHR: gray #95A5A6 dashed arrow (control/feedback)
  L1 D-Cache to L2 Cache: bidirectional arrows labeled "Req" and "Rsp"

Each component appears EXACTLY ONCE. NO title text at top of figure.

$style
PROMPTEOF
}

# ============================================================
# FIG B — Pipeline Flow (3:4)
# ============================================================
make_fig_b_prompt() {
    local pal="$1"
    local style
    style=$(make_style_block "$pal")
    cat <<PROMPTEOF
$SPELLING_LIST

Draw a compact single-column algorithm flowchart for the GRASP GPU prefetcher two-step prefetch pipeline.

NO TITLE at top. Vertical flow from top to bottom:

1. "Instruction Issued" white rounded rectangle, dark border
   downward arrow
2. Diamond shape "Tracked Warp?" ${PAL_LOGIC[$pal]} fill, white text
   "No" branch goes right to "Skip" (gray rounded rect), then stops
   "Yes" branch goes down
3. "CD: Analyze FIFO" ${PAL_KEY[$pal]} fill, white text, rounded rect
   downward arrow
4. Diamond "Chain Detected?" ${PAL_LOGIC[$pal]} fill, white text
   "Yes" branch goes right to "Write CT/TT" (${PAL_KEY[$pal]} fill), then arrow curves back to rejoin main flow below
   "No" branch goes down
5. Diamond "Index Load PC in CT?" ${PAL_LOGIC[$pal]} fill, white text
   "No" branch goes right to "Normal Load" (gray rect), stops
   "Yes" branch goes down
6. Diamond "Stride Valid?" ${PAL_LOGIC[$pal]} fill, white text
   "No" branch goes right to "Wait" (gray rect), stops
   "Yes" branch goes down
7. "IPU: Index Prefetch" ${PAL_STORAGE[$pal]} fill, white text, rounded rect
   downward arrow
8. "PRB: Allocate and Track" ${PAL_STORAGE[$pal]} fill, white text
   downward arrow
9. "Wait for Index Fill" gray dashed border rect, gray text
   downward arrow
10. "DPU: Data Prefetch" ${PAL_STORAGE[$pal]} fill, white text
    downward arrow
11. "Data in L1 for Demand" ${PAL_SUCCESS[$pal]} fill, white text, rounded rect (final state)

Decision diamonds should have bold "Yes" and "No" labels on their branches.
Legend at bottom showing box and arrow color meanings.

$style
PROMPTEOF
}

# ============================================================
# FIG C — Chain Detection Contrast (16:9)
# ============================================================
make_fig_c_prompt() {
    local pal="$1"
    local style
    style=$(make_style_block "$pal")
    cat <<PROMPTEOF
$SPELLING_LIST

Draw a comparison diagram showing why tracking specific warps matters for GPU prefetcher chain detection. This figure contrasts the noisy "all warps" view with GRASP's clean "filtered warp" view.

NO TITLE at top. Two rows separated by a horizontal divider.

TOP ROW labeled "Without Warp Filtering" on the left:
Show a chaotic interleaved instruction stream from ALL warps as a horizontal sequence of small rectangular boxes:
  [W0:LDG] [W2:ALU] [W3:LDG] [W1:ALU] [W0:IMAD] [W3:ALU] [W2:LDG] [W1:LDG] [W0:LDG]
Each box colored differently by warp ID (W0=light blue, W1=light orange, W2=light green, W3=light pink).
Draw red curved arrows between some boxes showing FALSE register dependency matches (spurious matches due to interleaving).
Put a red X icon and text "Too noisy, false matches" at the right side.

HORIZONTAL DIVIDER: A line with text in the middle: "GRASP Solution: CD tracks only 2 warps via per-warp FIFO"

BOTTOM ROW labeled "GRASP: Tracked Warp Only" on the left:
Show a clean filtered instruction stream for ONE tracked warp as horizontal boxes:
  [LDG R5, [R1]] (${PAL_STORAGE[$pal]} fill, white text) ... gray dots ... [IMAD.WIDE R2, R5, ...] (${PAL_KEY[$pal]} fill, white text) ... gray dots ... [LDG R3, [R2]] (${PAL_STORAGE[$pal]} fill, white text)
The gray dots represent filtered-out instructions from other warps.
Draw green arcs above connecting the matching instructions:
  Arc 1 from first LDG to IMAD labeled "(1) dst to src match"
  Arc 2 from IMAD to second LDG labeled "(2) dst to src match"
Put a green checkmark icon and text "Clean signal, accurate chain detection" at the right side.

Legend at bottom showing colors and symbols.

$style
PROMPTEOF
}

# ============================================================
# MAIN
# ============================================================
echo "=========================================="
echo "Generating 15 figure variants (A/B/C x 5 palettes)"
echo "=========================================="

RESULTS=()

for pal in $PALETTES; do
    echo ""
    echo "=== Palette: $pal ==="

    # Fig A
    prompt_a=$(make_fig_a_prompt "$pal")
    outfile_a="$BASE_DIR/fig_a_overall_arch/a_${pal}.png"
    if generate_image "$prompt_a" "$outfile_a" "16:9" "fig_a_${pal}"; then
        RESULTS+=("a_${pal}.png|$pal|OK|Overall arch")
    else
        RESULTS+=("a_${pal}.png|$pal|FAIL|Overall arch")
    fi
    sleep 2

    # Fig B
    prompt_b=$(make_fig_b_prompt "$pal")
    outfile_b="$BASE_DIR/fig_b_pipeline_flow/b_${pal}.png"
    if generate_image "$prompt_b" "$outfile_b" "3:4" "fig_b_${pal}"; then
        RESULTS+=("b_${pal}.png|$pal|OK|Pipeline flow")
    else
        RESULTS+=("b_${pal}.png|$pal|FAIL|Pipeline flow")
    fi
    sleep 2

    # Fig C
    prompt_c=$(make_fig_c_prompt "$pal")
    outfile_c="$BASE_DIR/fig_c_chain_detection/c_${pal}.png"
    if generate_image "$prompt_c" "$outfile_c" "16:9" "fig_c_${pal}"; then
        RESULTS+=("c_${pal}.png|$pal|OK|Chain detection")
    else
        RESULTS+=("c_${pal}.png|$pal|FAIL|Chain detection")
    fi
    sleep 2
done

echo ""
echo "=========================================="
echo "SUMMARY TABLE"
echo "=========================================="
printf "| %-28s | %-18s | %-6s | %-20s |\n" "File" "Palette" "Status" "Figure"
printf "|%-30s|%-20s|%-8s|%-22s|\n" "------------------------------" "--------------------" "--------" "----------------------"
for r in "${RESULTS[@]}"; do
    IFS='|' read -r file palette status fig <<< "$r"
    printf "| %-28s | %-18s | %-6s | %-20s |\n" "$file" "$palette" "$status" "$fig"
done
echo ""
echo "Done. Files in:"
echo "  $BASE_DIR/fig_a_overall_arch/"
echo "  $BASE_DIR/fig_b_pipeline_flow/"
echo "  $BASE_DIR/fig_c_chain_detection/"
