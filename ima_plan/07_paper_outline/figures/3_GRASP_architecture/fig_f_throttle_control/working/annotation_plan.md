# Fig F: Dynamic Throttle Control — Annotation Plan

> Base chart: `fig_f_base.png` (matplotlib, no text)
> Style reference: `figure_explore_v2_timeline.png` (nano-banana V2)

## Base Chart Data Reference

| Curve | Color | Style | Y-range |
|-------|-------|-------|---------|
| MSHR Occupancy | #1f77b4 (blue) | solid, 1.8pt | 30–75% |
| Effective Threshold | #d62728 (red) | dashed, 1.5pt | 50–90% (dynamic) |
| Without Throttle | #999999 (gray) | dashed, 1.0pt | 45–90% |
| Window Accuracy | #2ca02c (green) | area fill, 0.35α | 20–70% |

| Cooldown Region | X-range | Duration |
|-----------------|---------|----------|
| CD0 | 4.2K – 7.0K | ~2.8K cycles |
| CD1 | 14.3K – 17.1K | ~2.8K cycles |

## Annotations (all post-production)

### 1. Right-side Reference Line Labels

| Label | Y-position | Chart | Color |
|-------|-----------|-------|-------|
| Threshold High (90%) | y=90% | Top | #555555 |
| Threshold Low (50%) | y=50% | Top | #555555 |
| Accuracy High (60%) | y=60% | Bottom | #555555 |
| Accuracy Low (30%) | y=30% | Bottom | #555555 |

Place right of the chart boundary, aligned with each dotted reference line.

### 2. Direct Curve Labels (right end)

| Label | Y-position (approx at x=25K) | Color | Style |
|-------|-------------------------------|-------|-------|
| MSHR Occupancy | ~55% | #1f77b4 | Bold |
| Effective Threshold | ~85% | #d62728 | Bold |
| Without Throttle | ~70% | #999999 | Italic |

Place at the right end of each curve, in the right margin area.

### 3. Bracket Annotations (|—| style)

#### 3a. Cooldown Duration
- **Position**: Over the first cooldown (CD0), top of the chart (~y=92-95%)
- **X-span**: 4.2K to 7.0K
- **Style**: |—| bracket (left vertical bar, horizontal bar, right vertical bar)
- **Label**: "Cooldown Duration" above the bracket
- **Reference**: See V2 figure — two brackets already shown

#### 3b. Window Size
- **Position**: Between the two cooldowns, somewhere around x=8K–13K
- **X-span**: any 5K wide interval (e.g., 8K to 13K)
- **Style**: |—| bracket below the top chart or in the gap between charts
- **Label**: "Window Size (5K)" or "W = 5K"
- **Note**: This is NEW — not in V2 reference. Shows the sampling window period.

### 4. In-chart Text Labels

#### 4a. DATA_PF Suppressed
- **Position**: Inside the widest cooldown region (CD0 or CD1)
- **Approximate coords**: x=5.5K, y=65-75% (top chart)
- **Style**: Red (#c0392b) text, bold, with "✗" or "×" prefix
- **Background**: Semi-transparent white box for readability over pink shading

#### 4b. INDEX_PF (Always Active)
- **Position**: In a non-cooldown region where MSHR is low
- **Approximate coords**: x=9K, y=15-20% (top chart)
- **Style**: Green (#2ca02c) text, bold, with "✓" prefix
- **Frequency**: ONCE only (not repeated)

### 5. Causal Arrows (accuracy → threshold)

Two vertical dashed arrows connecting:

| Arrow | X-position | Top chart Y | Bottom chart Y | Meaning |
|-------|-----------|-------------|----------------|---------|
| A1 | ~5K | threshold drops from ~80% to ~50% | accuracy drops from ~50% to ~25% | Low accuracy → tight throttle |
| A2 | ~15K | threshold drops from ~85% to ~55% | accuracy drops from ~55% to ~25% | Same pattern repeated |

Style: Black dashed, 1pt, with downward arrowhead (from accuracy drop UP to threshold drop, or bi-directional).

### 6. Feedback Mapping Box

- **Position**: Right margin, between the two charts (or bottom-right)
- **Content**:
  ```
  Feedback Mapping
  ─────────────────
  Low Accuracy
    → Threshold Low (Tight)
  High Accuracy
    → Threshold High (Loose)
  ```
- **Style**: Small box with light gray background, thin border, 7-8pt text

### 7. Legend (bottom)

Compact horizontal legend:
- Blue solid line = MSHR Occupancy
- Red dashed line = Effective Threshold
- Gray dashed line = Without Throttle
- Green fill = Window Accuracy
- Pink shading = Cooldown (DATA_PF Suppressed)

### 8. Axis Labels

- Top Y-axis: "MSHR Occupancy (%)"
- Bottom Y-axis: "Window Accuracy (%)"
- Bottom X-axis: "Cycles" with ticks at 0, 5K, 10K, 15K, 20K, 25K
- Top X-axis: hide tick labels (shared with bottom)
