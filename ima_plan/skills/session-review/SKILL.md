---
name: session-review
description: Session 结束前的强制回顾。扫描本次所有变更，检查全局影响是否已注册，执行文档自维护协议中的所有自检项。用户在结束 session 前主动调用，弥补 agent 在长 context 中可能遗忘自检规则的问题。
---

# Session Review（会话回顾）

在 session 结束前主动回顾本次所有变更，确保全局影响已注册、跟踪文档已更新。

**为什么需要这个命令**：CLAUDE.md 中的 session 自检是被动约定——随着 context 增长，agent 可能遗忘。本命令是主动触发的强制检查。

## Step 1: 收集本次变更

```bash
git diff --name-only HEAD   # 已修改但未提交的文件
git diff --cached --name-only  # 已暂存的文件
```

列出所有本次 session 中新建或修改的文件。按类别分组：
- **GRASP 源码** (`grasp_*.{h,cc}`)
- **模拟器其他代码** (`gpu-simulator/` 下非 grasp)
- **研究文档** (`ima_plan/*.md`)
- **分析脚本** (`ima_plan/**/*.py`)
- **实验结果** (`result/`)
- **Harness 文件** (`CLAUDE.md`, `.claude/`, `ima_plan/skills/`)
- **其他**

## Step 2: 逐类别检查路由表

对照 CLAUDE.md 中的 Post-Task 路由表，逐项确认：

### 2a. 跑了实验？
- 检查 `result/log/` 下是否有新文件
- 若有 → 确认 `experiment_progress.md` 是否已追加本次实验记录
- 若未追加 → 提示并协助补写

### 2b. 修改了 GRASP 源码？
- 检查 `grasp_*.{h,cc}` 是否有变更
- 若有 → 确认 `experiment_progress.md` 版本记录是否已更新
- 若有 → 确认回归测试是否已运行（`grasp_regression.sh check`）

### 2c. 更新了阶段文档？
- 检查 `ima_plan/0[1-7]_*.md` 是否有变更
- 若有 → 确认 `最近更新` 时间戳是否已更新为当天

### 2d. 写了论文内容/绘图？
- 检查 `ima_plan/07_paper_outline/` 下是否有变更
- 若有 → 确认 insight.md 是否需要更新

### 2e. 新增了 SOTA baseline 数据？
- 检查 `ima_plan/05_implementation/sota_baseline/` 下是否有变更
- 若有 → 确认 README.md 是否已追加结果行

## Step 3: 新能力注册检查（最关键）

扫描本次新建的文件，判断是否有全局影响：

### 判断标准
以下类型的新文件**必须注册**到全局文档：
- 新的 shell 脚本（`.sh`）→ 可能是测试/自动化工具
- 新的 Python 分析脚本 → 可能是通用分析工具
- 新的配置文件 → 可能影响实验默认行为
- 新的 skill/command 定义 → 影响所有 session 的可用命令

### 检查流程
对每个新建文件，问：
1. **这个文件是仅用于本次任务，还是后续 session 也需要知道？**
2. 若后续也需要 → 按 CLAUDE.md "新能力注册" 表确认已注册到对应位置
3. 若未注册 → 执行注册（更新 CLAUDE.md、BOARD.md Notes 等）

## Step 4: INDEX.md 刷新判断

检查 INDEX.md 刷新条件是否命中：
- experiment_progress.md 有追加？
- 阶段文档有修改？
- `ima_plan/` 下有新增文件？

任一命中 → 提示用户运行 `/update-ima-index`

## Step 5: BOARD.md 更新

- 将自己从 Active Sessions 移到 Completed Today
- 在 Notes 中留下本次变更摘要（如果有全局影响）
- 清理超过 24h 的旧 Notes

## Step 6: 输出报告

```
=== Session Review Report ===

## 变更概览
- 源码: N files modified
- 文档: N files modified
- 脚本: N files created
- 实验: N new results

## 路由表检查
- [x] experiment_progress.md 已更新
- [x] 回归测试已通过
- [ ] 阶段文档时间戳未更新 → 已修复

## 新能力注册
- [x] regression/grasp_regression.sh → 已注册到 CLAUDE.md
- [ ] analyze_xxx.py → 仅本次使用，无需注册

## INDEX.md
- 触发条件命中：experiment_progress 有追加
- → 建议运行 /update-ima-index

## BOARD.md
- [x] 已更新 Completed Today
```
