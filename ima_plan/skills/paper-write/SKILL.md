---
name: paper-write
description: Write a specific section of the GRASP paper as compilable LaTeX. Reads paper_structure.md for section spec, source materials for content, and follows architecture conference writing conventions. Argument: section number or name (e.g., "§3" or "design").
---

# Paper Section Writer (Architecture Conference Edition)

> Adapted from ARIS paper-write skill. Customized for architecture conferences.
> **Usage**: `/paper-write §3` or `/paper-write design`

## Constants

| Key | Value |
|-----|-------|
| TARGET_VENUE | MICRO 2026 (ACM sigconf) |
| MAX_PAGES | 11 (body only) |
| CITATION_CMD | `\cite{}` (ACM style, NOT natbib \citep/\citet) |
| OUTLINE_FILE | `ima_plan/07_paper_outline/paper_structure.md` |
| MATERIALS_DIR | `ima_plan/07_paper_outline/` |
| LATEX_DIR | `ima_plan/07_paper_outline/` |
| WRITING_REF | `ima_plan/skills/shared-references/writing-principles.md` |
| CITATION_REF | `ima_plan/skills/shared-references/citation-discipline.md` |

## Step 0: Parse Arguments & Gate Check

1. Parse section argument: map "§1"/"intro"/"introduction" → Section 1, etc.
2. Read `paper_structure.md` — 找到目标 section 的 header
3. **Gate check**: 检查 section header 的状态标记
   - 如果是 `[占位符]` → **拒绝写作**，提示用户：
     > "§N 还是占位符状态。请先提供该 section 的图表，然后让我细化大纲。
     > 大纲细化并确认后，我会将标记改为 [已细化]，届时可调用 /paper-write。"
   - 如果是 `[已细化]` → 继续 Step 1
   - 如果是 `[已完成]` → 提示已有 LaTeX，询问是否重写
4. 从已细化的 section 内容中提取：
   - 段落级大纲（每段的论点、字数、图表引用）
   - Figure/table 放置位置
   - Page budget
   - Data source files
5. Read `shared-references/writing-principles.md` for style guidance

## Step 1: Collect Source Materials

For each section, read the relevant source files:

| Section | Primary Sources | Secondary Sources |
|---------|----------------|-------------------|
| §1 Introduction | `introduction.md` (论证链条 + 引用清单) | `paper_structure.md` §1 |
| §2 Background | `insight.md` (#2,#3,#8,#9), `01_ima_characterization.md` | `03_performance_ceiling.md` |
| §3 Design | GRASP source code (`grasp_*.{h,cc}`), `insight.md` (#1,#4-6,#10-11) | `04_prefetcher_design.md` |
| §4 Methodology | `06_evaluation_plan/benchmark_suite.md` | GPU config files |
| §5 Evaluation | `06_evaluation_plan/experiment_results.md` | `future_work.md` for §5.5 |
| §6 Related Work | `02_related_work/venue_classification.md`, `introduction.md` §1.7 | Individual paper notes |
| §7 Conclusion | All above (summary) | — |
| Abstract | All above (distill) | `abstract.md` (existing draft) |

## Step 2: Write LaTeX Content

Generate compilable LaTeX for the section. Follow these rules:

### Architecture Paper Section Guidelines

**§1 Introduction** (~1.5 pages)
- Open with the problem's practical importance (1-2 sentences, no grand claims)
- Quantify the problem early (L1 miss %, Ideal speedup) — architecture reviewers expect data in the intro
- Keep CPU IMA coverage brief (~5 sentences) with migration cost calculation
- Acknowledge prior GPU prefetching contributions positively before identifying the IMA gap
- IMAD.WIDE insight: one paragraph, point to §2.4 for details
- Contributions: 3 bullets, each ≤2 sentences, start with action verb
- **Must include Fig 1** (motivation data)

**§2 Background & Motivation** (~1.5 pages)
- GPU architecture background: only what the prefetcher design needs (SM, warp, L1, MSHR)
- IMA characterization: pattern classification with code snippets + memory diagrams
- Quantitative motivation: Little's Law derivation with actual numbers
- IMAD.WIDE: full instruction format, compiler reasoning, coverage statistics
- **Must include Fig 2-5 + Table 1**

**§3 Design** (~3.5 pages, THE CORE)
- Architecture papers are judged primarily on the design section
- Progressive disclosure: Overview → Components → Pipeline → Hardware Cost → Example
- Each component: what it does → why this design choice → hardware realization
- Worked example: trace through a real BFS iteration step by step
- Hardware cost table: precise to the byte, compare with prior work
- **Must include Fig 6-10 + Table 2**
- Every design choice must be justified (not just "we chose X" but "we chose X because Y")

**§4 Methodology** (~0.5 pages)
- Simulation framework + GPU configuration (table format)
- Benchmarks + datasets (table format)
- Baselines (table format with what each measures)
- Metrics definitions
- **Must include Table 3**

**§5 Evaluation** (~3.0 pages)
- Lead with the strongest result (geomean speedup)
- Coverage/Accuracy/Timeliness: split by index vs data (our unique angle)
- SOTA comparison: grouped bar with hatching (≥3 baselines)
- Sensitivity: at least 4 parameters
- Negative results: honest analysis (CC regression, SpMV stride failure)
- Hardware overhead comparison table
- **Must include Fig 11-19 + Table 4**

**§6 Related Work** (~0.5 pages)
- Three categories: CPU IMA HW / GPU Prefetching / GPU IMA
- For each: acknowledge contribution, then state how GRASP differs
- Spare Register gets most detailed treatment (closest prior work)
- Never criticize — state objective architectural differences

**§7 Conclusion** (~0.5 pages)
- Problem recap (1 sentence)
- Contribution summary (2-3 sentences)
- Key result (1 sentence with numbers)
- Future work (1 sentence)

### LaTeX Formatting Rules

```latex
% Section files go in: ima_plan/07_paper_outline/sections/
% Naming: 1_introduction.tex, 2_background.tex, etc.

% Citation style (ACM sigconf):
\cite{yu2015imp}          % NOT \citep or \citet
\cite{fu2024dmp,mostofi2023snake}  % Multiple citations

% Figure placement:
\begin{figure}[t]  % Top of page preferred
\begin{figure*}[t] % Full-width for 7.0" figures

% Cross-references:
\S\ref{sec:design}  % Section reference with §
Table~\ref{tab:hardware_cost}  % Table reference
Fig.~\ref{fig:architecture}    % Figure reference (abbreviated)
```

### Writing Style for Architecture Papers

1. **Precise technical language** — "the Chain Detector examines the instruction opcode" not "we look at the instruction"
2. **Quantify everything** — every claim backed by a number
3. **Hardware perspective** — discuss entries, bits, bytes, cycles; not "data structures"
4. **Active voice for contributions** — "GRASP detects..." not "the chains are detected by..."
5. **Passive for methodology** — "experiments were conducted on..." is fine
6. **No AI-typical inflation** — avoid "groundbreaking", "novel" (except in contributions), "cutting-edge"
7. **No hedging where evidence is clear** — "GRASP achieves 35.5%" not "GRASP seems to achieve"

## Step 3: Insert Figure/Table Placeholders

For each figure/table specified in `paper_structure.md` for this section:

```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=\columnwidth]{figures/fig_name.pdf}
  \caption{Caption text from paper_structure.md.}
  \label{fig:label}
\end{figure}
```

If the figure PDF doesn't exist yet, add a comment:
```latex
% TODO: Generate this figure using plot_util.py
% Data source: experiment_results.md
% Spec: see paper_structure.md Fig N
```

## Step 4: Citation Scaffolding

For each citation needed:
1. Check if entry exists in `references.bib`
2. If not, add a placeholder with `[VERIFY]` tag
3. Follow `shared-references/citation-discipline.md` for verification

```bibtex
% [VERIFY] Need to confirm venue/year
@inproceedings{yu2015imp,
  title={IMP: Indirect Memory Prefetcher},
  author={Yu, Xiangyao and others},
  booktitle={MICRO},
  year={2015}
}
```

## Step 5: Self-Check

Before outputting, verify:
- [ ] Content matches paper_structure.md spec for this section
- [ ] All quantitative claims trace to a data source file
- [ ] Page estimate is within budget (±0.2 pages)
- [ ] All figures/tables from spec are placed
- [ ] Citations use `\cite{}` not `\citep`/`\citet`
- [ ] No author names or identifying information
- [ ] LaTeX compiles without errors (mental check)

## Step 6: Output

Write the section file to `ima_plan/07_paper_outline/sections/N_name.tex`.

Update `main.tex` to `\input{sections/N_name.tex}` if not already present.

Report to user:
- Section length estimate (lines → approximate pages)
- Figures placed vs still needed
- Citations added vs needing verification
- Any content gaps marked with `% TODO`

## Step 7: Visual Review (多模态审稿)

> 文字正确 ≠ 视觉正确。纯文本 review 无法发现排版问题。
> 此步骤通过编译 PDF + 多模态模型审阅，从**审稿人视觉视角**检查。

### 7.1 编译 + 截图

```bash
cd ima_plan/07_paper_outline/
latexmk -pdf -interaction=nonstopmode main.tex
# 将该 section 所在页面转为图片
# 例如 §3 Design 占 p3-p6:
pdftoppm -png -r 200 -f 3 -l 6 main.pdf _visual_review
```

### 7.2 多模态模型视觉审稿

将渲染页面发送给多模态模型（Gemini 3.1 Pro via POE API），以**审稿人视角**审阅：

**审阅 prompt**:
```
你是一位体系结构顶会（MICRO/ISCA）的审稿人，正在审阅一篇论文。
请从视觉和排版角度检查以下页面，报告问题：

1. **Figure 布局**: 图是否靠近首次引用位置？是否被推到了远处？跨栏图是否在合理位置？
2. **Column 平衡**: 双栏是否严重失衡？是否有大片空白？
3. **文字密度**: 是否某页过于拥挤或过于稀疏？
4. **Figure/Table 质量**: 字体是否太小（<6pt）？标签是否清晰？legend 是否遮挡数据？
5. **整体专业感**: 从第一眼印象看，这像一篇高质量的 MICRO 投稿吗？

对每个问题给出 OK / WARNING / ISSUE，附具体位置和建议。
```

### 7.3 模型权重

不同模型的视觉审阅可信度不同：

| 模型 | 权重 | 适合审阅的方面 |
|------|:----:|-------------|
| Gemini 3.1 Pro (POE) | **高** | Figure 布局、整体排版、视觉专业感 |
| Claude (自身) | 中 | 文字内容一致性、引用位置 |
| GPT-5.4 (Codex) | 中-高 | 综合审阅（文字+视觉，如果支持图片输入） |

**优先使用多模态能力强的模型**。Claude 自身适合内容检查但视觉排版判断较弱。

### 7.4 常见视觉问题 & 修复

| 问题 | 原因 | 修复 |
|------|------|------|
| Figure 被推到下一页 | `[t]` 放不下 | 改 `[!t]` 或调整前文长度 |
| 双栏严重失衡 | 一侧有大 figure | 调整 figure 位置或用 `figure*` |
| Figure 字体太小 | figsize 太大导致缩放 | 减小 figsize，保持 fontsize≥6pt |
| 大片空白 | figure 占位但内容不足 | 增加文字或调整 figure 尺寸 |
| Legend 遮挡数据 | legend 放在图内 | 移至图外 `bbox_to_anchor` |
| Caption 与图分离 | 跨页断裂 | 加 `\captionsetup{belowskip=0pt}` 或调位置 |

### 7.5 输出

将视觉审阅结果附在 Step 6 报告之后：
```
=== Visual Review ===
Page 3: OK — figure placement good
Page 4: WARNING — Fig 8 pushed to bottom, 3cm from first reference
Page 5: ISSUE — right column 40% empty after Table 2
Suggested fixes: [具体修改建议]
```

用户确认后实施修复，重新编译验证。
