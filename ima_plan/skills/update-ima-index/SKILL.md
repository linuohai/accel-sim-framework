---
name: update-ima-index
description: Scan ima_plan/ and regenerate ima_plan/INDEX.md with the current phase status, key findings, directory summary, blockers, insight list, and open questions. Use when the user asks to update or refresh the IMA research index.
---

# Update IMA Index

## Overview

Use this skill to rebuild `ima_plan/INDEX.md` from the current state of `ima_plan/`. The goal is to keep the research index synchronized with the latest phase progress, findings, and outstanding issues.

## Constraints

- Work inside the `fa` container at `/workspace/prefetch`.
- Before changing any repo files, provide a change plan and wait for user confirmation.
- Do not use destructive git commands such as `git reset --hard` or `git checkout --`.
- Keep the generated `INDEX.md` concise and within the template guidance in `references/index-template.md`.
- Prefer evidence pulled from files in `ima_plan/`; do not invent status, findings, or blockers.

## Workflow

1. Scan the top-level `ima_plan/` markdown files and subdirectories.
2. Extract phase status from the first lines of each phase document when present.
3. Pull key findings from sections such as `Key Findings`, `关键发现`, `已有实验结果`, `结论`, `Summary`, and `主要结论`.
4. Collect open questions and blockers from sections such as `关键问题`, `待讨论`, `Pending Questions`, `Open Questions`, `TODO`, and `未解决问题`.
5. Summarize each subdirectory with its purpose, key files, file counts, and most recent modification time.
6. Update `ima_plan/INDEX.md` using the structure and section order in `references/index-template.md`.

## Special Cases

- For `05_implementation/v1_implementation_problems.md`, extract `- [ ]` and `- [x]` items as the blocker list.
- For `07_paper_outline/insight.md`, extract the insight headings as the insight list.
- For `00_overview.md`, preserve the overall phase framing and current research direction.
- If a file has no explicit status line, infer status from its content:
  - experimental results or conclusions present -> completed or partially completed
  - TODOs or unresolved items present -> in progress
  - outline only -> planned

## Output Expectations

- Update `ima_plan/INDEX.md` in place.
- Keep the final document readable and stable for quick navigation.
- Ensure the metadata line shows the current generation time and that the content reflects the latest repository state.

## References

- `references/index-template.md`
- `references/scan-patterns.md`
- `../00_overview.md`
- `../../INDEX.md`
