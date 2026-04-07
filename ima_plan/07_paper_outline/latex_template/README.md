# MICRO 2026 LaTeX Template

> Source: https://www.microarch.org/micro59/submit/micro59-latex-template.zip
> Downloaded: 2026-03-29

## Files

| File | Description |
|------|-------------|
| `acmart.cls` | ACM master article class (MICRO 2026 uses `sigconf` style) |
| `ACM-Reference-Format.bst` | BibTeX style for ACM numbered references |
| `sample-base.bib` | Sample bibliography entries |
| `main.tex` | MICRO 2026 sample/guidelines paper (use as reference for preamble) |

## Document Class

Submission (double-blind review):
```latex
\documentclass[sigconf, screen, review]{acmart}
```

Camera-ready (after acceptance):
```latex
\documentclass[sigconf]{acmart}
```

## Key Preamble Settings (from official template)

```latex
\setcopyright{none}           % For submission; change after acceptance
\copyrightyear{2026}
\acmYear{2026}
\acmConference[MICRO 2026]{The 59th IEEE/ACM International Symposium on Microarchitecture}{October 31--November 04, 2026}{Athens, Greece}
\settopmatter{printfolios=true}
\settopmatter{printacmref=false}
```

## Compile

```bash
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

Or with latexmk:
```bash
latexmk -pdf main.tex
```

## Important Rules

- **Do NOT modify** `acmart.cls` or formatting settings
- **Do NOT use** `\vspace` or spacing manipulation packages
- Submissions are **automatically inspected** for formatting violations
- Use `\acmSubmissionID{XXX}` to set your submission number (replaces `#NaN` in banner)
