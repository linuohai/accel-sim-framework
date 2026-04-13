---
name: paper-compile
description: Compile the GRASP paper LaTeX project to PDF. Handles multi-pass compilation, error diagnosis, page count validation, and submission readiness checks for MICRO 2026 (ACM sigconf).
---

# Paper Compile (Architecture Conference Edition)

> Compile `main.tex` to submission-ready PDF for MICRO 2026.

## Constants

| Key | Value |
|-----|-------|
| LATEX_DIR | `ima_plan/07_paper_outline/` |
| MAIN_TEX | `main.tex` |
| MAX_PAGES | 11 (body through Conclusion) |
| FORMAT | ACM sigconf (`acmart.cls`) |
| MAX_ATTEMPTS | 3 |

## Step 1: Verify Prerequisites

```bash
cd ima_plan/07_paper_outline/
# Check LaTeX installation
which latexmk pdflatex bibtex || echo "MISSING: install texlive"
# Check required files
ls main.tex latex_template/acmart.cls references.bib
# Check section files
ls sections/*.tex 2>/dev/null || echo "WARNING: no section files yet"
```

## Step 2: Initial Compilation

```bash
cd ima_plan/07_paper_outline/
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex 2>&1 | tail -50
```

If `latexmk` unavailable:
```bash
pdflatex -interaction=nonstopmode main.tex
bibtex main
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

## Step 3: Error Diagnosis

Common errors and fixes:

| Error Pattern | Fix |
|--------------|-----|
| `! LaTeX Error: File 'acmart.cls' not found` | Ensure `\documentclass` path points to `latex_template/acmart.cls` or copy to working dir |
| `! Undefined control sequence: \citep` | Replace with `\cite{}` (ACM style) |
| `! Missing $ inserted` | Math mode error — check inline formulas |
| `No file main.bbl` | Run `bibtex main` first |
| `Citation undefined` | Run bibtex + 2 more pdflatex passes |
| `Overfull \hbox` | Acceptable if ≤5pt; fix if >10pt |
| `File 'figures/xxx.pdf' not found` | Generate figure or add TODO placeholder |

## Step 4: Iterative Fix Loop

Up to MAX_ATTEMPTS rounds:
1. Read error log (`main.log`)
2. Fix the first error (often cascades)
3. Recompile
4. Repeat until clean or attempts exhausted

## Step 5: Validate Output

```bash
# PDF exists and has content
ls -la main.pdf
# Check page count (body = pages before References)
# Parse from log or use pdfinfo
pdfinfo main.pdf | grep Pages
```

### Page Count Rules (MICRO 2026)
- **Body**: §1 through §7 (Conclusion) ≤ 11 pages
- **References**: Unlimited, start on new page
- **Appendix**: NOT ALLOWED

## Step 6: Submission Readiness

- [ ] PDF compiles without errors
- [ ] No undefined references (`grep -c '??' main.log`)
- [ ] No undefined citations (`grep 'Citation.*undefined' main.log`)
- [ ] Body ≤ 11 pages
- [ ] No author names visible (anonymous mode)
- [ ] No `[VERIFY]` or `[TBD]` in output
- [ ] All figures render correctly
- [ ] Fonts are embedded (`pdffonts main.pdf | grep -v "yes"`)

## Step 7: Report

Output compilation status:
```
=== Compilation Report ===
Status: SUCCESS / FAILED
PDF: main.pdf (N pages total, M pages body)
Warnings: N overfull hbox, M undefined refs
Ready for submission: YES / NO (list blockers)
```
