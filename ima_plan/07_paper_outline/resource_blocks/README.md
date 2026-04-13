# 资源块系统 (Resource Blocks)

> 创建: 2026-04-04

## 什么是资源块

资源块是论文写作的**素材积累单元**。每个资源块封装一个完整的论点或展示策略，包含：
- 核心想法（一句话）
- 图/表设计（具体描述）
- 文字组织（叙事顺序）
- 候选位置（论文中可能放置的章节）
- 数据依赖（需要什么支撑）

资源块 ≠ 论文章节。它们是**待组装的零件**——后续制定大纲时，从中选取、组装、检查逻辑流。参考 `introduction_golden_rules.md` 的 "字字有关联" 原则：不是所有资源块都必须用上。

## 命名规范

```
RB-{编号}_{简短英文标签}.md
```

示例：`RB-01_ima_latency_warp_gap.md`

## 资源块 Schema

每个资源块文件包含以下结构：

```markdown
# RB-XX: {标题}

> 创建: YYYY-MM-DD

## 核心想法
一句话概括这个资源块要传达什么。

## 要素
按编号列出具体内容点（术语、数据、公式、图等）。

## 图/表
每张图的详细规格：类型、轴定义、数据源、尺寸。

## 文字组织
叙事顺序：先说什么，后说什么。

## 候选位置
论文 paper_structure.md 中哪些 section 可能使用此资源块。

## 依赖与约束
- 已有数据 / 待补充数据
- 与 golden_rules 的关联
- [PLACEHOLDER] 标记待补充内容
```

## 目录结构

```
resource_blocks/
├── README.md                 ← 本文件
├── reference_fig/            ← 参考图片（来自其他论文）
├── scripts/                  ← 绘图/分析脚本
│   ├── plot_ima_latency_dist.py      (RB-01)
│   ├── plot_warp_gap.py              (RB-01)
│   ├── plot_stall_breakdown.py       (RB-01)
│   ├── plot_execution_timeline.py    (RB-01, DEFERRED)
│   ├── generate_multi_sm_sass.sh     (RB-02, 编���脚本)
│   ├── detect_chains_all.py          (RB-02, 链检测)
│   └── plot_chain_stability.py       (RB-02)
├── data/                     ← 分析数据
│   ├── sass/                 ← SASS 编��输��� (72 组合)
│   ├── chain_conformance.csv  ← RB-02 一致率数据
│   └── cache_ima_breakdown.csv ← RB-03 cache/IMA 数据
├── figures/                  ← 脚本输出（SVG）
│   ├── rb01/
│   ├── rb02/
│   └── rb03/
├── RB-01_ima_latency_warp_gap.md
├── RB-02_ima_chain_stability.md
└── RB-03_cache_ima_breakdown.md
```

## 已有资源块索引

| 编号 | 标题 | 核心论点 | 候选位置 | 状态 |
|------|------|---------|---------|------|
| RB-01 | IMA 延时与 Warp 需求缺口 | IMA 打破 GPU warp 延时隐藏机制 | §1.1, §2.3 | 3/4 图完成，timeline 搁置 |
| RB-02 | IMA 依赖链编译稳定性 | IMAD.WIDE 是编译器结构性产出 | §3 Design, §2 | 图完成，9/12 算法 ≥86% |
| RB-03 | L1/L2 Cache 与 IMA Miss | L1 miss 高 + IMA 占主导 → 需要 L1 prefetching | §2 Motivation | 图完成，37 数据点 |
| RB-04 | CPU IMA Prefetcher 迁移代价 | 单上下文假设 → GPU 多 warp 下检测失效+面积膨胀 | §2.3, §6 | 纯公式+表格，无图 |
| RB-05 | Spare Register 架构局限 | 唯一 GPU IMA prefetcher 基于十年前 Fermi 架构，十年无后续 | §1, §6 | 纯文字+表格，无图 |

## 并行构建说明

多个资源块可以同时构建。每个资源块：
- 有独立的绘图脚本（在 `scripts/` 下）
- 输出到 `figures/` 目录（文件名以 RB 编号为前缀避免冲突）
- 完成后更新本 README 的索引表
