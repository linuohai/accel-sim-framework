# Venue Checklists for Architecture Conferences

> Adapted from ARIS venue-checklists.md. Focused on CCF-A architecture venues.

---

## MICRO (International Symposium on Microarchitecture)

**Our target: MICRO 2026 (59th edition, Athens, Greece)**

| Item | Requirement |
|------|-------------|
| Format | ACM `sigconf` (acmart.cls) |
| Page limit | **11 pages** (main body through Conclusion) |
| References | Unlimited, not counted in page limit |
| Appendix | **Not allowed** |
| Review | Double-blind |
| Author info | Anonymous — no names, affiliations, or identifying URLs |
| Template | Official ACM template (`\documentclass[sigconf,anonymous]{acmart}`) |
| Font size | Enforced by template (≥9pt body) |
| Columns | Two-column |
| Figures | Inline (no separate figure pages) |
| Formatting check | Automatic — papers violating format may be desk-rejected |
| Artifact | Optional but encouraged (Artifact Evaluation available) |

### MICRO-Specific Expectations
- **Hardware cost analysis is mandatory** — reviewers will reject if missing
- **Cycle-accurate simulation or RTL** expected (trace-driven is acceptable with justification)
- **Comparison with ≥3 baselines** — ideally including the most recent related work
- **Sensitivity analysis** for key parameters (≥4 dimensions)
- **Reproducibility**: simulation configuration must be fully specified

---

## ISCA (International Symposium on Computer Architecture)

| Item | Requirement |
|------|-------------|
| Format | ACM `sigconf` or IEEE (varies by year) |
| Page limit | **11 pages** (recent years) or **12 pages** |
| References | Unlimited |
| Review | Double-blind |
| Artifact | Strongly encouraged |

### ISCA-Specific
- Historically more theoretical than MICRO
- Novelty expectations are very high
- Cross-layer papers (compiler + architecture) welcome

---

## HPCA (International Symposium on High-Performance Computer Architecture)

| Item | Requirement |
|------|-------------|
| Format | IEEE double-column |
| Page limit | **11 pages** (including references for IEEE format) |
| Review | Double-blind |
| Template | IEEE conference template |

### HPCA-Specific
- More applied / system-oriented than ISCA
- GPU-focused papers have good acceptance rate
- Evaluation thoroughness valued highly

---

## ASPLOS (Architectural Support for Programming Languages and Operating Systems)

| Item | Requirement |
|------|-------------|
| Format | ACM `sigconf` |
| Page limit | **11 pages** (body) + unlimited references |
| Review | Double-blind, two rounds (recent years) |
| Artifact | Strongly encouraged |

### ASPLOS-Specific
- Cross-cutting papers (HW + SW + OS) preferred
- Pure hardware papers less common but accepted if impact is clear
- SW artifact availability valued more than at MICRO/ISCA

---

## Key Differences from AI/ML Venues

| Dimension | Architecture (MICRO/ISCA) | ML (ICLR/NeurIPS) |
|-----------|--------------------------|-------------------|
| Citation command | `\cite{}` (ACM) | `\citep{}`/`\citet{}` (natbib) |
| Page counting | Body only (refs excluded) | Body only (refs + appendix excluded) |
| Appendix | **Not allowed** (MICRO) | Allowed and common |
| Broader Impact | Not required | Often required |
| Reproducibility | Sim config in paper | Code + data release |
| Hardware cost | **Mandatory** | N/A |
| Sensitivity analysis | **Expected (4+ params)** | Ablation studies (similar) |
| Related Work placement | **End** (before Conclusion) | After Introduction or End |
| Review style | Technical depth + novelty | Novelty + clarity + significance |
| Reviewer count | 3-4 | 3-4 |
| Rebuttal | Yes (most venues) | Yes |
