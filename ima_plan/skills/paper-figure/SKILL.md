---
name: paper-figure
description: 确定论文图表的内容组织和布局，渲染原型草图，并指导如何用项目自有风格（plot_util.py）生成最终版。用法：`/paper-figure §3` 或 `/paper-figure Fig 6`。
---

# Paper Figure (Architecture Conference Edition)

> 两阶段工作流：**原型设计**（确定图的组织方式）→ **生产指导**（用 plot_util.py 生成最终版）

## Constants

| Key | Value |
|-----|-------|
| OUTLINE_FILE | `ima_plan/07_paper_outline/paper_structure.md` |
| FIGURE_DIR | `ima_plan/07_paper_outline/figures/` |
| STYLE_FILE | `ima_plan/07_paper_outline/plot_style/plot_util.py` |
| MPLSTYLE | `ima_plan/07_paper_outline/plot_style/academic.mplstyle` |
| DATA_SOURCE | `ima_plan/06_evaluation_plan/experiment_results.md` |
| PROMPTS_FILE | `ima_plan/07_paper_outline/plot_style/figure_prompts.md` |

## Step 0: 解析参数 & 加载 Figure Spec

1. 解析参数：`§3` → 该 section 所有 figure；`Fig 6` → 单个 figure
2. 从 `paper_structure.md` 的 **Figure 架构总览** 读取目标 figure 的：
   - 名称、Section、类型、尺寸、参考风格、数据来源
3. 分类：

| 图的类型 | 处理路径 |
|---------|---------|
| **数据驱动图** (bar chart, line plot, heatmap) | Step 1A → Step 2A |
| **架构/流程图** (block diagram, flowchart, pipeline) | Step 1B → Step 2B |
| **代码/SASS 图** (code listing, instruction annotation) | Step 1C → Step 2C |

---

## Phase 1: 原型设计 (确定图长什么样)

### Step 1A: 数据驱动图 — 原型

1. 从 `experiment_results.md` 或其他数据源读取实际数据
2. 确定图的组织方式：
   - **X 轴**: workload 名称? 参数值? 数据集?
   - **Y 轴**: IPC? Speedup %? Coverage %?
   - **分组**: 按 baseline? 按数据集? 按算法?
   - **子图**: 需要 (a)(b) 子图吗?
3. 用 matplotlib **快速渲染一个原型**（使用默认风格，不需要精美）：

```python
# 原型脚本 — 仅用于确认布局，不是最终版
import matplotlib.pyplot as plt
import numpy as np

# 示例数据 (从 experiment_results.md 提取)
workloads = ['BFS', 'SSSP', 'BC', 'CC', 'SpMV', 'VC']
baseline = [...]
grasp = [...]

fig, ax = plt.subplots(figsize=(7.0, 2.7))
x = np.arange(len(workloads))
ax.bar(x - 0.2, baseline, 0.4, label='Baseline')
ax.bar(x + 0.2, grasp, 0.4, label='GRASP')
ax.set_ylabel('IPC Speedup (%)')
ax.legend()
plt.title('[PROTOTYPE] Fig 11: IPC Speedup')
plt.savefig('figures/_prototype_fig11.png', dpi=100)
plt.close()
```

4. **展示原型给用户**，附带以下问题：
   - 数据分组方式是否合理？
   - 是否需要增加/减少对比项？
   - X 轴排列顺序是否合适？
   - 是否需要 geomean bar？
   - 子图划分是否清晰？

### Step 1B: 架构/流程图 — 描述

1. 用文字详细描述图应包含的元素：
   - 哪些 block/component
   - 数据流方向（箭头）
   - 哪些信号/接口需要标注
   - 整体布局（上下/左右/层级）
2. 参考 `paper_structure.md` 中的参考风格（如 "参考 DMP Fig 10"）
3. 如果可能，用 Mermaid 或文字 ASCII 画一个粗略布局
4. **选项**：
   - 用 `/paper-illustration` 生成高质量渲染
   - 用 TikZ 直接在 LaTeX 中绘制
   - 用 draw.io 手动绘制（推荐复杂架构图）

### Step 1C: 代码/SASS 图 — 提取

1. 从 `01_ima_characterization/sass_analysis/` 提取相关 SASS 代码
2. 确定标注方式（寄存器依赖箭头、颜色高亮）
3. 输出 LaTeX `lstlisting` 格式的代码块 + `\tikz` 箭头

---

## Phase 2: 生产指导 (用项目风格生成最终版)

### Step 2A: 数据驱动图 — 最终版脚本

用户确认原型布局后，生成使用 `plot_util.py` 的完整生产脚本：

```python
#!/usr/bin/env python3
"""Fig 11: IPC Speedup — 全量评估结果"""
import sys
from pathlib import Path

# 引入项目绘图工具
_REPO = Path(__file__).resolve().parents[2]  # 调整到仓库根
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, figsize_full, save_fig, CB10, HATCHES

apply_style()

import matplotlib.pyplot as plt
import numpy as np

# === 数据 (从 experiment_results.md 提取) ===
workloads = [...]
datasets = [...]
# ... 实际数据 ...

# === 绘图 ===
fig, ax = plt.subplots(figsize=figsize_full, constrained_layout=True)

# ≥3 baselines: 必须用 颜色 + hatching
for i, (label, data, color, hatch) in enumerate(zip(labels, all_data, CB10, HATCHES)):
    ax.bar(x + i*width, data, width, label=label, color=color, hatch=hatch,
           edgecolor='black', linewidth=0.5)

# GRASP: 实色无 hatch，视觉突出
ax.bar(x + grasp_offset, grasp_data, width, label='GRASP',
       color=CB10[0], edgecolor='black', linewidth=0.5)

ax.set_ylabel('IPC Speedup (\\%)')
ax.set_xticks(x + ...)
ax.set_xticklabels(workloads, rotation=45, ha='right')
ax.legend(loc='upper left', ncol=3)

# Geomean 标注
ax.axhline(y=geomean, color='gray', linestyle='--', linewidth=0.8)
ax.annotate(f'Geomean: {geomean:.1f}\\%', xy=(len(workloads)-0.5, geomean),
            fontsize=7, va='bottom')

save_fig(fig, 'fig11_ipc_speedup', _REPO / 'ima_plan/07_paper_outline/figures')
plt.close(fig)
```

### Step 2A 必须遵守的规范 (from CLAUDE.md)

- `apply_style()` 加载 `academic.mplstyle`
- 颜色用 `CB10` 或语义调色板
- 输出 PDF + SVG (`save_fig`)
- `constrained_layout=True`
- ≥3 baseline → 颜色 + hatching (`HATCHES`)
- GRASP 使用 `HATCHES[0]`（实色无 hatch）
- `plt.close(fig)` 防止内存泄漏
- 不加 `plt.show()`
- 不内联 `rcParams`
- Y 方向网格已在 mplstyle 默认开启
- `figsize` 不超 `(7.0, 5.0)`
- 文字不小于 6pt
- 不用 red+green 对比

### Step 2B: 架构图 — 生产

根据 Phase 1 确认的布局，选择工具：
- **复杂架构图** (Fig 6 整体框图): `/paper-illustration` 或 draw.io → 导出 PDF
- **简单流程图** (Fig 7 CD 流程): TikZ in LaTeX
- **表格+箭头** (Fig 8 CT/TT): LaTeX tabular + TikZ overlay

### Step 2C: SASS/代码图 — 生产

```latex
\begin{figure}[t]
\centering
\begin{lstlisting}[style=sass]
LDG.E.SYS R5, [R2.64]       // index load
IMAD.WIDE R8, R5, 0x4, c[0x0][0x160]  // addr calc
LDG.E.SYS R10, [R8.64]      // data load
\end{lstlisting}
% TikZ arrows for register dependencies
\begin{tikzpicture}[overlay, remember picture]
  \draw[->, red, thick] (R5-out) -- (R5-in);
  \draw[->, blue, thick] (R8-out) -- (R8-in);
\end{tikzpicture}
\caption{LDG→IMAD.WIDE→LDG dependency chain in BFS.}
\label{fig:sass_chain}
\end{figure}
```

---

## 输出

每个 figure 产出两个文件：
1. `figures/_prototype_figN.png` — 原型（确认布局用，不入论文）
2. `figures/plot_figN.py` — 生产脚本（用 plot_util.py 风格）

最终 PDF 通过运行生产脚本生成：
```bash
cd ima_plan/07_paper_outline
python3 figures/plot_figN.py  # 输出 figures/figN.pdf + figures/figN.svg
```
