# 扫描模式参考

Agent 在扫描 `ima_plan/` 生成 INDEX.md 时，应使用以下模式匹配关键信息。

## 1. 阶段状态提取

在每个顶层 `.md` 文件（`01_*.md` ~ `07_*.md`）的**前 10 行**中查找：

```
> 状态：<状态文本>
> Status: <status text>
```

如果没有显式状态行，根据内容推断：有实验数据/结论 → 完成；有 TODO → 进行中；只有大纲 → 计划中。

## 2. 关键发现提取

匹配以下任一 section 标题，提取其下的要点：

```
## Key Findings
## 关键发现
## 已有实验结果
## 结论
## Summary
## 主要结论
```

提取规则：
- 优先提取含**数字**的结论（miss rate、speedup、百分比等）
- 每个阶段最多提取 2-3 条
- 附带来源文件路径

## 3. 问题提取

匹配以下 section 标题：

```
## 关键问题
## 待讨论
## Pending Questions
## Open Questions
## TODO
## 未解决问题
```

## 4. 子目录描述优先级

扫描子目录时，按以下优先级读取描述文件：

1. `analysis.md` — 最高优先级，通常包含分析结论
2. `README.md` — 次优先级，通常包含目录说明
3. 其他 `.md` 文件 — 读取前 40 行获取概述

## 5. 文件统计

对每个子目录统计：
- `.md` 文件数量
- `.py` 脚本数量
- `.sh` 脚本数量
- `.csv` / `.svg` / `.png` 数据/图表文件数量
- 最近修改时间（取目录内最新文件的 mtime）

## 6. 特殊文件

以下文件有特殊提取逻辑：

| 文件 | 提取内容 |
|------|----------|
| `00_overview.md` | 整体计划阶段声明 |
| `05_implementation/v1_implementation_problems.md` | 问题清单（`- [ ]` 和 `- [x]` 条目） |
| `07_paper_outline/insight.md` | 各 insight 的标题行（`## ` 或 `### ` 开头） |
| `04_prefetcher_design.md` | prefetcher 方案状态 |
