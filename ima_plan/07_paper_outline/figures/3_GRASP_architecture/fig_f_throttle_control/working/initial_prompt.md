# Fig F: Dynamic Throttle Control — Initial Prompt

## Exploration Plan

3 structural variants to explore:

### Variant 1: Feedback Loop Diagram
- Central feedback loop: GRASP pipeline → DATA_PF → L1 Cache → Useful/Useless counters → Sliding Window Accuracy → Adaptive Threshold → Suppress Gate → back
- Problem inset: small panel showing "without throttle" = useless PF flooding cache
- INDEX_PF bypass arrow around the gate
- Cooldown Timer as a sub-component

### Variant 2: Split Panel (Problem + Solution)
- Left panel: "Without Throttle" — GRASP emitting DATA_PF → MSHR congestion → cache pollution → demand miss latency increase
- Right panel: "Dynamic Throttle" — feedback loop with sliding window, adaptive threshold, cooldown
- Visual contrast between chaotic left and controlled right

### Variant 3: Timeline/Waveform
- X-axis = cycles, two traces:
  - MSHR Occupancy % (blue line)
  - Effective Threshold (red dashed line, dynamic)
- Shaded cooldown regions
- DATA_PF suppress events (red X marks)
- INDEX_PF exempt events (green check marks)
- Below: Sliding Window Accuracy bar showing how it drives threshold changes

## Shared Technical Content

### Mode 5 Dynamic Throttle Mechanism
1. Every W cycles (Window Size), sample L1 cache Useful/Useless deltas
2. Compute Window Accuracy = ΔUseful / (ΔUseful + ΔUseless)
3. Linear interpolation: accuracy → effective MSHR threshold
   - Accuracy ≤ Accuracy Low → Threshold Low (tight throttle)
   - Accuracy ≥ Accuracy High → Threshold High (loose throttle)
4. If MSHR Occupancy ≥ Effective Threshold → suppress DATA_PF + enter Cooldown Duration
5. During cooldown: all DATA_PF suppressed unconditionally
6. INDEX_PF NEVER throttled (pipeline correctness)

### Key Parameters (Title Case, NOT code variable names)
- Window Size (5000 cycles)
- Accuracy Low / Accuracy High (30% / 60%)
- Threshold Low / Threshold High (50% / 90%)
- Cooldown Duration (200 cycles)

### Components (GRASP spelling)
- Throttle Controller (TC) — purple #7B68AE
- L1 D-Cache with MSHR — white fill, dark border
- Prefetch Queue (PQ) — blue #4472C4
- INDEX_PF / DATA_PF distinction
