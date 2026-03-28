---
name: grasp-health-check
description: Periodic code + documentation garbage collection. Scans GRASP source for code smells, documentation for stale/redundant content, and generates a cleanup report with actionable fixes. Run weekly or when the codebase feels messy.
---

# GRASP Health Check（代码 + 文档 GC）

定期扫描代码和文档中的"垃圾"——过时内容、违反 Golden Rules 的代码、膨胀的文件——并生成清理报告。

## Constraints

- 在 `fa` 容器内 `/workspace/prefetch` 工作
- 扫描是只读的；修复需要用户确认后才执行
- 报告输出到 stdout，不写入文件（除非用户要求保存）

## Step 1: 代码扫描（GRASP Golden Rules 检查）

扫描 `gpu-simulator/gpgpu-sim/src/gpgpu-sim/grasp_*.{h,cc}`：

### 1a. Magic Number 检查
- grep 数字常量（排除 0/1/-1 和已在 `grasp_config_t` 中定义的）
- 报告：文件:行号 + 上下文，建议提取到 config

### 1b. 裸 printf/cout 检查
- grep `printf\|std::cout\|fprintf` in grasp_* 文件
- 排除 `GRASP_DPRINTF` 调用
- 报告：应替换为 `GRASP_DPRINTF`

### 1c. 实验性代码残留
- grep `#ifdef GRASP_EXPERIMENTAL`，检查是否有已完成但未清理的实验分支
- grep `TODO\|FIXME\|HACK\|XXX`，统计数量和年龄（通过 git blame）

### 1d. 编码惯例
- 检查新增函数是否遵循 `m_` 成员前缀、`_t` 类型后缀
- 检查是否有未使用的 `#include`（通过 grep 引用计数）

## Step 2: 文档扫描

### 2a. experiment_progress.md 膨胀检查
- 统计总行数
- 识别超过 30 天的旧实验条目（通过 section 中的日期标记）
- 若 >300 行：建议归档旧条目到 `05_implementation/experiment_logs/YYYY-MM.md`

### 2b. 阶段文档 TODO 残留
- 扫描 `ima_plan/01-07_*.md` 中的 `TODO\|待办\|待完成\|Needs investigation`
- 通过 git blame 检查 TODO 年龄
- 超过 14 天的 TODO：报告并建议清理或转为正式 issue

### 2c. INDEX.md 链接有效性
- 提取 INDEX.md 中所有 `](` 链接
- 验证目标文件是否存在
- 报告 dead links

### 2d. 文档新鲜度批量检查
- 扫描 `ima_plan/` 下所有 `.md` 文件的 `最近更新` 时间戳
- 与文件实际 mtime 和当前日期对比
- 报告时间戳过时 >7 天的文件

### 2e. 冗余内容检测
- 检查同一实验数据（如 "SSSP +42.2%"）是否出现在多个文件中
- 按权威优先级报告：哪个是源、哪些是应改为链接的副本

## Step 3: 分析脚本检查

扫描 `ima_plan/**/*.py`：

### 3a. 绘图规范违反
- grep 不使用 `apply_style()` 的绘图脚本（含 `plt.` 但不含 `apply_style`）
- grep 内联 `rcParams` 设置
- grep `plt.show()`（无头环境禁用）

### 3b. 孤立脚本
- 检查 `.py` 文件是否被任何 `.md` 文档引用
- 未被引用的脚本可能是临时产物，建议归档或删除

## Step 4: 生成报告

输出格式：

```
=== GRASP Health Check Report ===
Date: YYYY-MM-DD

## Code Quality
- [ ] N magic numbers found (files: ...)
- [ ] N bare printf/cout (files: ...)
- [ ] N TODO/FIXME (oldest: N days, file:line)
- [x] No experimental code residue

## Documentation
- [ ] experiment_progress.md: N lines (threshold: 300), N entries >30 days
- [ ] N stale TODOs in phase documents
- [ ] N dead links in INDEX.md
- [ ] N files with outdated timestamps
- [x] No redundant data across files

## Analysis Scripts
- [ ] N scripts missing apply_style()
- [x] No orphaned scripts

## Recommended Actions (按优先级)
1. [HIGH] ...
2. [MED] ...
3. [LOW] ...
```

## Step 5: 用户确认后执行修复

报告生成后，等待用户选择要修复的项目。可能的修复动作：

- 归档旧实验条目（创建 `experiment_logs/YYYY-MM.md`，从主文件删除）
- 删除已完成的 TODO
- 修复 dead links
- 更新过时的时间戳
- 替换裸 printf 为 GRASP_DPRINTF

每个修复动作需单独确认。
