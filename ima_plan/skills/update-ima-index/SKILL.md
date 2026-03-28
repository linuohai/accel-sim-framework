---
name: update-ima-index
description: Scan ima_plan/ and regenerate ima_plan/INDEX.md with the current phase status, key findings, directory summary, blockers, insight list, and open questions. Use when the user asks to update or refresh the IMA research index.
---

# Update IMA Index

扫描 `ima_plan/` 研究目录，智能理解各文档内容后生成/更新 `ima_plan/INDEX.md`。

## Constraints

- 只读 `.md` 文件提取内容，不解析 CSV/SVG/SASS/Python（只统计数量）
- INDEX.md 控制在 **300 行以内**
- `00_overview.md` 是权威计划文档，INDEX.md 是**派生摘要**（不含计划变更）
- 遵循仓库**中英混合**语言风格
- 生成前展示给用户确认，获得许可后再写入

## Step 0: 并发检查

1. 读 `.claude/BOARD.md`
2. 检查 Notes 中是否有 <10 分钟内的 "正在更新 INDEX.md" 条目
3. 若有 → 中止，告知用户另一个 session 正在更新
4. 若无 → 在 Notes 追加 "正在更新 INDEX.md"，然后继续
5. 完成后 → 更新 Notes 为 "INDEX.md 已更新 (N 行)"

## Step 1: 读取整体计划

读取 `ima_plan/00_overview.md`，提取：
- 当前所处阶段
- 各阶段的声明状态
- 整体研究目标

## Step 2: 扫描顶层阶段文档

逐一读取 `ima_plan/01_*.md` ~ `ima_plan/07_*.md`（如果存在），对每个文件：

1. 在**前 10 行**查找状态声明：`> 状态：` 或 `> Status:`
2. 查找并提取以下 section 的内容：
   - `## Key Findings` / `## 关键发现` / `## 已有实验结果` / `## 结论`
   - `## 关键问题` / `## 待讨论` / `## Pending Questions`
3. 记录文件最近修改时间

详细匹配模式见：`references/scan-patterns.md`

## Step 3: 扫描子目录

对 `ima_plan/` 下每个子目录：

1. 按优先级读取描述文件：`analysis.md` > `README.md` > 其他 `.md`（前 40 行）
2. 统计各类文件数量（.md, .py, .sh, .csv, .svg, .png）
3. 获取目录内最近修改时间
4. 提炼 4-6 行的目录摘要

## Step 4: 提取实现问题

读取 `ima_plan/05_implementation/v1_implementation_problems.md`（如果存在）：
- 提取所有 `- [ ]`（未解决）和 `- [x]`（已解决）条目
- 区分阻塞项和已关闭项

## Step 5: 提取 Insight 清单

读取 `ima_plan/07_paper_outline/insight.md`（如果存在）：
- 提取所有 `##` 或 `###` 标题作为 insight 条目
- 保留标题层级关系

## Step 6: 组装 INDEX.md

按照模板结构组装内容。模板见：`references/index-template.md`

组装规则：
- 总行数 ≤ 300 行
- 关键发现 8-12 条，每条必须含量化数据
- 目录详情每个 4-6 行
- 时间戳使用当前时间

## Step 7: 展示并写入

1. 将完整的 INDEX.md 内容展示给用户
2. 等待用户确认（可能有修改建议）
3. 确认后写入 `ima_plan/INDEX.md`
4. 报告生成统计：扫描了多少文件、INDEX.md 总行数、各 section 条目数

## Workflow Decision Tree

执行前先判断场景：

1. **INDEX.md 不存在** → 执行完整扫描（Step 0-7），从零生成
2. **INDEX.md 已存在** → 增量更新：先读现有 INDEX.md，对比各文件 mtime，只重新扫描有变更的部分
3. **用户只问某个阶段** → 读 INDEX.md 后按需深入对应阶段文档，不做全量扫描

## References

- `references/index-template.md` — 输出结构模板
- `references/scan-patterns.md` — 模式匹配规则
