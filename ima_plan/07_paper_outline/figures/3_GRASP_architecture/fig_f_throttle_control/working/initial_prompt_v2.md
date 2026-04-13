# Fig F V2: Dynamic Throttle Control Timeline — Initial Prompt for Gemini

## Figure Type
Timeline / waveform diagram showing dynamic throttle control behavior over time.
Will be rendered with matplotlib (not AI image generation).

## Purpose
Explain how GRASP's dynamic throttle (mode=5) works:
- Sliding window accuracy feedback drives adaptive MSHR threshold
- When MSHR exceeds threshold → suppress DATA_PF + cooldown period
- INDEX_PF is never throttled
- Show cause-effect: accuracy change → threshold change → suppress/allow

## Layout: Two vertically stacked charts sharing X-axis (Cycles)

### Top Chart (~65% height): MSHR Occupancy vs Effective Threshold
- X-axis: Cycles (0 to 25K)
- Y-axis: Percentage (0-100%)
- Blue solid line: MSHR Occupancy (fluctuating 20-85%)
- Red dashed line: Effective Threshold (dynamic, adapts between Threshold Low and Threshold High)
- Two horizontal dotted reference lines: Threshold Low (50%) and Threshold High (90%)
- Light red/pink shaded regions: Cooldown periods (DATA_PF suppressed)
- During cooldown: "DATA_PF Suppressed" text with red X marks (2-3 instances max)
- Outside cooldown: "INDEX_PF (Always Active)" with green checkmark (1-2 instances max, NOT repeated)
- Cooldown Duration bracket annotation on one cooldown region
- Optional: gray dashed line showing "Without Throttle" MSHR baseline (higher peaks)

### Bottom Chart (~30% height): Window Accuracy
- Same X-axis aligned with top
- Y-axis: Accuracy % (0-100%)
- Green area fill showing Window Accuracy over time
- Two horizontal dotted reference lines: Accuracy Low (30%) and Accuracy High (60%)
- When accuracy drops, the Effective Threshold in top chart drops correspondingly

### Connecting Elements
- Vertical dashed lines or arrows connecting key accuracy changes to threshold changes (1-2 max)
- Right side: small annotation box explaining "Low Accuracy → Low Threshold (Tight)" and "High Accuracy → High Threshold (Loose)"

### Legend
- Compact, at bottom, single row or two rows
- MSHR Occupancy, Effective Threshold, Window Accuracy, Cooldown region

## Style Requirements
- Academic paper quality (MICRO/ISCA/HPCA)
- Use project's apply_style() from plot_util.py
- Clean, not cluttered — fewer annotations placed more thoughtfully
- Minimum 8pt text when printed at column/full width
- Key insight should be graspable in 5 seconds: "accuracy feedback drives adaptive throttling"

## What V1 got wrong (avoid these)
- Too many visual elements competing (activity strip, dual background colors)
- Mapping box too prominent on right side
- INDEX_PF label style not matching V2's natural placement
- Background shading too dominant — should be subtle
- Overall: overdesigned, lost the clarity V2 had

## Reference
The nano-banana-pro V2 (figure_explore_v2_timeline.png) is the target quality/style.
Key elements from V2 to preserve:
- Clean MSHR line with natural fluctuation
- Red dashed threshold that visibly adapts
- Cooldown shading clearly marked but not overwhelming
- "DATA_PF Suppressed" and "INDEX_PF (Always Active)" placed naturally near relevant events
- Green accuracy area chart below
- Right-side parameter labels (Threshold High/Low, Accuracy High/Low)
- Mapping annotation box
