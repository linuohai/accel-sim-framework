---
name: paper-writing
description: Orchestrate academic paper writing workflow for architecture conferences (MICRO/ISCA/HPCA/ASPLOS). Coordinates section writing, figure generation, compilation, and review. Adapts to existing project state — never regenerates what already exists.
---

# Paper Writing Orchestrator (Architecture Conference Edition)

> Adapted from ARIS paper-writing skill. Customized for:
> - **Venue**: MICRO 2026 (ACM sigconf, 11 pages body, double-blind)
> - **Domain**: Computer architecture / GPU microarchitecture
> - **Project**: GRASP prefetcher (existing outline + materials)

## Constants

| Key | Value | Notes |
|-----|-------|-------|
| TARGET_VENUE | MICRO 2026 | ACM sigconf format, 11 pages body |
| MAX_PAGES | 11 | Body only; references unlimited, no appendix |
| ANONYMOUS | true | Double-blind; no author names |
| REVIEWER_MODEL | gpt-5.4 via `/codex:task` | For Phase 5 review (when enabled) |
| REVIEWER_REASONING | xhigh | Codex reasoning effort level |
| OUTLINE_FILE | `ima_plan/07_paper_outline/paper_structure.md` | Authoritative outline |
| LATEX_DIR | `ima_plan/07_paper_outline/` | LaTeX project root |
| LATEX_MAIN | `main.tex` | Main LaTeX file |
| FIGURE_STYLE | `ima_plan/07_paper_outline/plot_style/plot_util.py` | Must use `apply_style()` |
| TEMPLATE_DIR | `ima_plan/07_paper_outline/latex_template/` | ACM template files |

## Pre-Requisites (What Already Exists)

Before running, verify these exist (DO NOT regenerate):

| File | Role | Status Check |
|------|------|-------------|
| `paper_structure.md` | Authoritative §1-§7 outline with figure placement | Must exist |
| `abstract.md` | Abstract draft | Must exist |
| `introduction.md` | Introduction 素材库 | Must exist |
| `insight.md` | 10 design insights with section mapping | Must exist |
| `future_work.md` | Known limitations for §5.5/§7 | Must exist |
| `main.tex` | LaTeX main file | Must exist |
| `latex_template/acmart.cls` | ACM class file | Must exist |
| `plot_style/plot_util.py` | Figure generation utilities | Must exist |
| `plot_style/academic.mplstyle` | Matplotlib style | Must exist |

## Phase Overview

```
Per-Section Workflow (重复):
  Step A: /paper-figure §N    → 确定该 section 的图表形式，渲染原型
  Step B: 用 plot_util.py 画最终版图表（或手动绘制架构图）
  Step C: 细化该 section 大纲 → 用户 review
  Step D: /paper-write §N     → 基于大纲 + 图表生成 LaTeX

Cross-Section:
  Phase 4: /paper-compile     → 编译 + 页数验证
  Phase 5: Review (when ready) → Codex GPT-5.4 / paper-audit
```

## Phase 0: Pre-Check & Status

1. Read `paper_structure.md` — extract section list, figure plan, [TBD] items
2. Read `main.tex` — check which sections already have content vs placeholders
3. For each section, assess completion status:
   - **Done**: Has polished LaTeX content
   - **Draft**: Has content but needs revision
   - **Stub**: Has placeholder/empty
   - **Missing**: Not yet created
4. For each figure, assess:
   - **Final**: PDF exists in `figures/`
   - **Prototype**: `_prototype_` exists, awaiting final version
   - **Planned**: Spec in paper_structure.md but not yet started
5. Output **status matrix**:

```
Section / Figure Status:
§3 Design    [Missing]  Figs: 6[Planned] 7[Planned] 8[Planned] 9[Planned] 10[Planned]
§2 Background [Missing] Figs: 2[Planned] 3[Planned] 4[Planned] 5[Planned]
§5 Evaluation [Missing] Figs: 11[Prototype] 12[Prototype] 13[Planned] 14-17[Planned]
...
```

6. Ask user which section to work on

## Per-Section Workflow (核心循环)

对用户选定的 section，按以下 4 步执行：

### Step A: Figure Design (`/paper-figure §N`)

确定该 section 需要的每张图的**内容组织和布局**：
- 数据驱动图：X/Y 轴、分组方式、子图划分 → 渲染原型 (`_prototype_`)
- 架构图：block 组成、数据流、标注 → 文字描述 + 粗略布局
- 代码图：SASS 片段 + 寄存器依赖标注

**输出**：原型图 + 布局说明，展示给用户确认。

### Step B: Final Figure Production (用户 + Claude 协作)

用户确认原型后，生成最终版：
- **数据图**：用 `plot_util.py` 的 `apply_style()` + `save_fig()` 生产
- **架构图**：`/paper-illustration` 渲染，或用户在 draw.io / Figma 手绘
- **代码图**：LaTeX `lstlisting` + TikZ

必须遵守 CLAUDE.md 绘图规范（hatching、CB10、no title in figure 等）。

### Step C: Outline Refinement (用户 review)

`paper_structure.md` 的 section spec 可能还不够细。在写 LaTeX 之前：

1. 基于已有的图表，**细化该 section 的段落级大纲**：
   - 每段的核心论点
   - 图表的引用位置
   - 每段的大致字数/行数
   - 数据来源指向
2. 将细化大纲**展示给用户 review**
3. 用户可能修改论点顺序、增删内容、调整强调重点
4. **只有用户确认后才进入 Step D**

### Step D: Section Writing (`/paper-write §N`)

用确认的大纲 + 最终图表，生成可编译的 LaTeX：
- 读取 Step C 确认的细化大纲
- 读取源材料（introduction.md, insight.md, source code 等）
- 插入 Step B 的图表引用
- 输出到 `sections/N_name.tex`
- 检查页数是否在预算内

**写完一个 section 后回到 Phase 0 更新 status matrix。**

### 推荐 Section 顺序

```
1. §3 Design       — 核心贡献，先写以锚定叙事
2. §2 Background   — 为 Design 提供前置知识
3. §5 Evaluation   — 依赖最终实验数据
4. §1 Introduction — 最后写（需要知道论文实际交付了什么）
5. §4 Methodology  — 短，事实性
6. §6 Related Work — 定位
7. §7 Conclusion   — 总结
8. Abstract        — 最后的最后
```

## Phase 4: Compilation

Invoke `/paper-compile` to:
1. Run `latexmk -pdf main.tex`
2. Fix errors iteratively
3. Validate page count (≤11 pages body)
4. Check anonymous compliance

## Phase 5: Review (Available, Not Auto-Triggered)

When user requests review:

1. Compile current PDF
2. Concatenate all section .tex files into a single review document
3. Send to Codex GPT-5.4 via:
```
/codex:task --model gpt-5.4 --reasoning xhigh \
  "Review this architecture conference paper for MICRO 2026. \
   Score 1-10 on: technical depth, novelty, evaluation completeness, \
   writing clarity, claim-evidence alignment. \
   List CRITICAL/MAJOR/MINOR issues."
```
4. Parse response, implement fixes by severity
5. Recompile and optionally iterate (max 2 rounds)

Alternative: Use `/paper-audit` skill for Claude-based multi-reviewer simulation.

## Interaction with Existing Skills

| Skill | When to Use |
|-------|------------|
| `/paper-write §N` | Write a specific section |
| `/paper-compile` | After writing sections |
| `/paper-illustration` | For architecture/flow diagrams |
| `/paper-audit` | Claude-based paper review |
| `/codex:task` | GPT-5.4 external review |
| `/academic-paper-reviewer` | Multi-perspective review simulation |

## Key Rules

1. **Never overwrite existing polished content** — always backup before rewriting
2. **paper_structure.md is the source of truth** — all section content must align with it
3. **Incremental workflow** — write one section at a time, compile, check page count
4. **Architecture paper conventions** — see `shared-references/writing-principles.md`
5. **Citation verification** — see `shared-references/citation-discipline.md`
6. **No fabricated data** — all quantitative claims must trace to experiment logs
