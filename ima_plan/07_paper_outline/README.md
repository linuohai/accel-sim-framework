# GRASP 论文工程导览

> 目标会议：MICRO 2026（ACM sigconf 模板）
>
> 论文标题：*GRASP: Grasping GPU Indirect Memory Patterns via ISA-Exposed Register-Chain Prefetching*

---

## 文件结构

```
07_paper_outline/
│
├── latex_template/              LaTeX 编译工程
│   ├── main.tex                 ★ 论文主文件（在这里写正文）
│   ├── table_templates.tex      ★ 6 张表格模板（被 main.tex \input）
│   ├── sample-base.bib          ★ 参考文献库（需填充 BibTeX 条目）
│   ├── figures/                 ★ 论文最终图（PDF/SVG，\includegraphics 从这里引用）
│   │   └── fig1_cache_ima_ideal.pdf   Fig 1: L1 Miss + Ideal Headroom
│   ├── acmart.cls                 ACM 模板类（不动）
│   └── ACM-Reference-Format.bst   参考文献格式（不动）
│
├── figures/                     绘图脚本 + 工作副本（迭代用，非最终版）
│   ├── plot_fig1_cache_ima_ideal.py   Fig 1 生产脚本（输出到 latex_template/figures/）
│   ├── plot_batch_results.py          旧脚本（待迁移）
│   └── _prototype_*.py                原型脚本（不入论文）
│
├── plot_style/                  绘图风格基础设施
│   ├── academic.mplstyle          matplotlib 样式（字体/尺寸/颜色/网格）
│   ├── plot_util.py               绘图工具（apply_style, save_fig, 调色板, legend helpers）
│   └── figure_prompts.md          非数据图（架构图/流程图）的生图 prompt 模板
│
├── abstract.md                  Abstract 中文思路 + 英文 Draft v2
├── introduction.md              Introduction 段落素材 + 论证结构
├── introduction_golden_rules.md ★ Introduction 写作 Golden Rules（14 原则 + 5 框架 + GRASP 映射 + 自检清单）
├── insight.md                   11 个核心 Insight 汇总
├── future_work.md               Future Work 素材
├── paper_structure.md           论文结构规划
│
├── paper_assit/                 论文写作辅助材料（视频总结等）
└── submission_guidelines/       MICRO 2026 投稿规范
    ├── MICRO2026_guidelines.md
    └── micro59-sample-paper.pdf
```

---

## 你需要修改的文件

### 核心（3 个）

| 文件 | 做什么 |
|------|--------|
| `latex_template/main.tex` | 写论文正文。每个 `\section` 下的 `\textit{[placeholder]}` 替换为英文正文 |
| `latex_template/table_templates.tex` | 更新表格数据。实验出新数据后替换 `---` 占位值 |
| `latex_template/sample-base.bib` | 添加参考文献的 BibTeX 条目 |

### 辅助（生成图片时）

| 文件 | 做什么 |
|------|--------|
| `figures/plot_figN_*.py` | 绘图生产脚本，自动输出到 `latex_template/figures/` |
| `latex_template/figures/*.pdf` | **论文最终图的唯一位置**。main.tex 用 `\includegraphics{figures/xxx.pdf}` 引用 |

> **约定**：`figures/` 是工作目录（脚本+原型+迭代），`latex_template/figures/` 是论文最终图。只有后者会被 LaTeX 编译引用。

### 参考用（不需要修改）

| 文件 | 用途 |
|------|------|
| `abstract.md` | Abstract 已嵌入 main.tex，后续微调直接改 tex |
| `introduction.md` | 写 §1 时参考的段落计划和数据素材 |
| `introduction_golden_rules.md` | **写 §1 时必读**：14 条写作原则 + GRASP 映射 + 逐段自检清单 |
| `insight.md` | 写各章节时参考的 Insight 详细描述 |
| `paper_structure.md` | 已体现在 main.tex 章节骨架中 |

---

## 编译

```bash
cd ima_plan/07_paper_outline/latex_template

# 首次编译（含参考文献）
pdflatex -interaction=nonstopmode main.tex
bibtex main
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex

# 日常编译（无新参考文献时）
pdflatex -interaction=nonstopmode main.tex
```

产物：`latex_template/main.pdf`

---

## main.tex 章节结构

| Section | 标题 | 对应素材 | 建议写作顺序 |
|:-------:|------|---------|:----------:|
| §1 | Introduction | `introduction.md` | 8 |
| §2 | Background and Motivation | `introduction.md` §1.1-1.3 | 6 |
| §3 | Key Insight: ISA-Exposed IMA Structure | `insight.md` Insight 1 | 5 |
| §4 | GRASP Design | `04_prefetcher_design.md` | 2 |
| §5 | Implementation | `05_implementation/` | 7 |
| §6 | Experimental Methodology | `06_evaluation_plan/benchmark_suite.md` | 1 |
| §7 | Evaluation | 实验数据 | 3 |
| §8 | Related Work | `02_related_work/` | 4 |
| §9 | Conclusion | 浓缩 Abstract | 9 |

建议先写最机械的 §6（搬数据），再写最熟悉的 §4（设计），最后写最难的 §1。

---

## 表格清单（table_templates.tex）

| 表格 | 用途 | 放置章节 |
|------|------|---------|
| Table 1: GPU Config | 模拟器参数 | §6 Methodology |
| Table 2: Prefetcher Config | Baseline 对比 | §6 Methodology |
| Table 3: Datasets | 图数据集参数 | §6 Methodology |
| Table 4: Benchmark Matrix | 算法 × 数据集 checkmark | §6 Methodology |
| Table 5: Hardware Budget | GRASP 组件存储分解 | §7 Evaluation |
| Table 6: Performance | 主结果 Speedup 汇总 | §7 Evaluation |

目前所有表格通过 `\input{table_templates}` 集中在 §4.7。写正文时将各表格剪切到对应章节。

---

## 绘图规范

所有论文数据图必须使用 `plot_style/academic.mplstyle`：

```python
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[N] / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, figsize_col, figsize_full, save_fig, CB10
apply_style()
```

详细规范见 `CLAUDE.md` 中的「绘图规范」章节。

---

## 非数据图（架构图/流程图）

`plot_style/figure_prompts.md` 中有 6 种图类型的生图 prompt 模板：

1. 硬件架构总览图（GRASP 在 cache hierarchy 中的位置）
2. 算法流程图（Chain Detection → Stride Learning → Prefetch Generation）
3. 代码分析图（BFS SASS 级 IMA 链识别）
4. 数据结构表格图（CT/TT 工作示例）
5. 时序/执行示意图（prefetch pipeline 时序）
6. IMA 访存模式示意图（Introduction 用）

复制 prompt → 替换占位符 → 喂给生图模型 → 在 draw.io/PPT 中精修。
