# Writing Principles for Architecture Conference Papers

> Adapted from ARIS writing-principles.md. Customized for computer architecture venues
> (MICRO, ISCA, HPCA, ASPLOS). Based on analysis of 9 CCF-A papers:
> Snake[MICRO'23], DMP[HPCA'24], Magellan[ISCA'25], IMP[MICRO'15],
> Spare Register[HPCA'14], Prodigy[HPCA'21], Tyche[TACO'24], CAPS[IPDPS'18], DX100[ISCA'25].

---

## 1. Architecture Paper Structure (The Invariant Skeleton)

All analyzed CCF-A architecture papers follow this 7-section structure:

```
§1 Introduction     — Problem → Gap → Insight → Contributions
§2 Background       — Domain knowledge + Quantitative motivation
§3 Design           — Core contribution (LONGEST section, 30-35%)
§4 Methodology      — Experimental setup (SHORTEST section, ~5%)
§5 Evaluation       — Systematic validation (25-30%)
§6 Related Work     — Positioning & differentiation
§7 Conclusion       — Summary & future work
```

### Page Allocation (for 11-page MICRO)

| Section | Pages | % | Key Observation |
|---------|:-----:|:-:|-----------------|
| §1 Introduction | 1.5 | 14% | Must contain 1 motivation figure |
| §2 Background | 1.5 | 14% | Little's Law / quantitative motivation essential |
| §3 Design | 3.5 | 32% | **Architecture papers live or die here** |
| §4 Methodology | 0.5 | 5% | Tables, not prose |
| §5 Evaluation | 3.0 | 27% | ≥10 figures typical |
| §6 Related Work | 0.5 | 5% | At the end (not after intro) |
| §7 Conclusion | 0.5 | 5% | 1 sentence future work |

### Figure Density

Architecture papers at MICRO/ISCA average **2.0 figures per page**. For 11 pages: **20-22 figures + 3-4 tables**.

---

## 2. The Design Section: What Architecture Reviewers Care About

The Design section is the soul of an architecture paper. Reviewers judge primarily on:

### 2.1 Progressive Disclosure Pattern

Every analyzed paper follows: **Overview → Components → Worked Example → Hardware Cost**

```
§3.1 Overview (0.3 page)
  → Block diagram showing all components + data flow
  → One paragraph explaining the key idea

§3.2-3.6 Component-by-Component (2.0 pages)
  → Each component: What → Why → How → Hardware realization
  → Flowcharts for detection/decision logic
  → Table examples for lookup/matching processes

§3.7 Hardware Cost (0.2 page)
  → Precise storage breakdown to the byte
  → Comparison with prior work (table format)

§3.8 Worked Example (0.4 page)
  → Trace through one real iteration of a benchmark
  → Show training + prefetching in action
```

### 2.2 Design Justification

Architecture reviewers expect **every design choice to be justified**:

| Bad | Good |
|-----|------|
| "We use 32 CT entries" | "We use 32 CT entries because our analysis of 56 implementations shows ≤28 unique (base,scale) pairs across all workloads" |
| "The FIFO is shared per-SM" | "Per-warp FIFOs would require 64× storage; per-SM sharing is viable because SIMT execution means warps execute the same instructions" |

### 2.3 Hardware Cost Must Be Precise

```
Component: CT (Chain Table)
  32 entries × (64-bit key + 32-bit data_PC + 8-bit confidence + ...) = 512 bytes
```

Not: "approximately 0.5 KB". Architecture reviewers can and will check the math.

---

## 3. Writing Style for Architecture Community

### 3.1 Technical Precision

Architecture papers demand hardware-level specificity:

| AI Paper Style | Architecture Paper Style |
|---------------|--------------------------|
| "our model processes inputs" | "the Chain Detector examines the instruction opcode at the issue stage" |
| "we store the patterns" | "the Chain Table maintains 32 entries, each containing a 64-bit (base, scale) key" |
| "the results improve" | "IPC improves by 35.5% (from 7.35 to 11.02) on BFS web-Google" |
| "we train the predictor" | "stride learning requires 2 outer-loop iterations (~3200 cycles) per warp to converge" |

### 3.2 Quantify Everything

Every claim must have a number. Architecture reviewers distrust unquantified assertions.

| Bad | Good |
|-----|------|
| "significant overhead" | "57.6 KB/SM — nearly double the L1 cache size" |
| "improves performance" | "geomean IPC +35.5% (up to +49.8% on BFS)" |
| "covers most patterns" | "covers 88.4% of IMA chains (93.6% excluding SCC)" |
| "low hardware cost" | "2.3 KB/SM, equivalent to 36 bytes per warp" |

### 3.3 Active Voice for Contributions, Passive for Setup

- Contributions: "GRASP detects LDG→IMAD.WIDE→LDG chains at the issue stage"
- Setup: "Experiments were conducted on Accel-Sim with SM80_A100 configuration"
- Results: "GRASP achieves 35.5% geomean IPC improvement" (active, emphasize our work)

### 3.4 Avoid AI-Typical Inflation

| Avoid | Use Instead |
|-------|-------------|
| "novel" (overused) | "first" (if true) or just describe what's new |
| "groundbreaking" | delete — let results speak |
| "cutting-edge" | "state-of-the-art" (if comparing) or delete |
| "we believe" | "our analysis shows" (with evidence) |
| "it is worth noting that" | delete — if worth noting, just state it |
| "interestingly" | delete — let the reader decide what's interesting |

### 3.5 Respectful Positioning Against Prior Work

Architecture is a small community. Never criticize prior work:

| Bad | Good |
|-----|------|
| "Prior work fails to address IMA" | "Prior GPU prefetchers have made significant progress on stride patterns; IMA requires fundamentally different detection mechanisms" |
| "Spare Register's approach is limited" | "Spare Register pioneered GPU IMA prefetching; the GPU architecture has evolved significantly since 2014 (Fermi → SM80)" |
| "CPU methods are not applicable" | "CPU IMA prefetchers assume per-core detection; GPU's 64 concurrent warps per SM create different design constraints" |

---

## 4. Figures and Tables

### 4.1 Architecture Paper Figure Types

| Type | Example | Tool |
|------|---------|------|
| **Architecture block diagram** | GRASP components + data flow | TikZ / draw.io / paper-illustration |
| **Flowchart** | Detection algorithm | TikZ / paper-illustration |
| **SASS code + annotations** | LDG→IMAD.WIDE→LDG chain | LaTeX listings |
| **Grouped bar chart** | IPC speedup across workloads | Matplotlib (plot_util.py) |
| **Sensitivity plot** | Performance vs parameter sweep | Matplotlib |
| **Timeline/pipeline** | Prefetch timing diagram | TikZ |
| **Table lookup example** | CT/TT working process | LaTeX tabular |

### 4.2 Mandatory Figure Conventions

- **No title inside figures** — titles go in `\caption{}`
- **Vector format (PDF)** for all plots
- **Colorblind-safe palette** (CB10 from plot_util.py)
- **≥3 baselines** → must use color + hatching (CLAUDE.md rule)
- **Our work (GRASP)** uses solid fill, no hatch — visually prominent
- **Y-axis grid** enabled by default (academic.mplstyle)
- **Legend** must not overlap data; prefer outside figure or fig.legend()

### 4.3 Caption Writing

Captions must be self-contained — a reader should understand the figure without reading surrounding text.

```latex
% Bad:
\caption{Results on BFS.}

% Good:
\caption{IPC speedup of GRASP over baseline across four graph datasets.
GRASP achieves the highest improvement on web-Google (+56.1\%) due to
high IMA density. roadNet shows minimal benefit due to sparse graph structure
(avg degree 3).}
```

---

## 5. Abstract Formula (Architecture Adaptation)

5-part flow, 150-250 words:

1. **Problem** (1-2 sentences): IMA bottleneck on GPU, quantified
2. **Gap** (1-2 sentences): CPU solutions can't migrate; GPU prefetchers don't address IMA
3. **Approach** (2-3 sentences): IMAD.WIDE insight + GRASP mechanism
4. **Results** (1-2 sentences): Geomean speedup, best case, hardware cost
5. **Significance** (0-1 sentences): First GPU IMA prefetcher on modern architecture

No citations in abstract. One quantitative result minimum.

---

## 6. Pre-Submission Checklist

- [ ] Paper compiles without warnings
- [ ] All `\cite{}` resolve (no `?` in PDF)
- [ ] No author names or identifying info (double-blind)
- [ ] Page count ≤ 11 (body through Conclusion)
- [ ] All figures are PDF (vector)
- [ ] No `[VERIFY]` or `[TBD]` markers remain
- [ ] Every quantitative claim traces to experiment_results.md
- [ ] Hardware cost table sums correctly
- [ ] Contribution list in §1 matches what paper actually delivers
- [ ] Abstract geomean matches §5 reported number
