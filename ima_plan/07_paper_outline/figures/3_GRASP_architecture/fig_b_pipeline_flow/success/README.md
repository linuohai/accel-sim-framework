# Fig B 成果归档 + 经验总结

> 最近更新: 2026-04-05
> 适用范围: GRASP 论文 §3 Design 章节——算法流程图
> 模型: nano-banana-pro (Gemini 3 Pro Image via PoE API)

---

## 1. 迭代概览

| 版本 | 文件 | 模型 | 解决的问题 |
|------|------|------|-----------|
| V5 | `v5_compact_white.png` | nano-banana-pro | 白色背景、紧凑双列、图例全宽底部——**布局定型** |
| V6 | `v6_phase_separator.png` | nano-banana-pro | Phase 1/2 虚线分隔（效果偏弱） |
| V8 | `v8_final.png` | nano-banana-pro | Phase 1/2 实线分隔——**最终版** |

完整迭代路径：v1→v2（间距优化）→v3b/v3c（背景探索，放弃）→v4a/b/c（灰色背景探索，放弃）→v5（白色定型）→v6/v8（分隔线）

提示词文件：`../working/initial_prompt.md`（v1 初始）, `../../tmp/gen_fig_b_v5.py`（v5+ 脚本）

---

## 2. Fig B 的设计决策

### 2.1 为什么选双列而非单列

GRASP 有两条独立触发的通路（Training + Prefetch），双列布局直接映射这个结构。
单列 flowchart 会让流程看起来是串行的，但实际上 Training 和 Prefetch 是并行触发的。

### 2.2 三 Phase 分区

| Phase | 位置 | 触发条件 | 颜色 |
|-------|------|---------|------|
| Phase 1: Chain Detection | 左列上半 | Issue Stage 发射 LDG 指令 | 蓝 #2B5EA7 |
| Phase 2: Stride Learning | 左列下半 | Demand index load 观测到 | 蓝 #2B5EA7 |
| Phase 3: Two-Step Prefetch | 右列全高 | Demand index load + CT hit | 紫 #6C3483 |

Phase 1+2 用蓝色（Training），Phase 3 用紫色（Prefetch），颜色语义与 Fig A 一致。

### 2.3 跨列箭头 "Stride + Target Info"

从 Phase 2 "Stride Converged" 到 Phase 3 "Demand Index Load"，表示 Training 产出的知识（CT/TT 内容）喂给 Prefetch 通路。灰色虚线，与数据流箭头区分。

---

## 3. 流程图特有的经验（区别于 Fig A 架构图）

### 3.1 节点文字精简规则

**每个节点最多两行，3-8 词/行：**

| 原来（代码风格） | 改为（学术风格） |
|-----------------|----------------|
| `CD: Check if LDG's source register was written by IMAD.WIDE` | "Monitor Issue Stream" + "(CD)" |
| `addr_diff = current_addr - last_addr` | "Track Address Differences" + "(IST)" |
| `CT entry: (index_PC, data_PC, tt_idx, stride_state)` | "Record Chain Info" + "(CT + TT)" |
| `IPU: Compute prefetch_addr = current_addr + iter_stride × distance` | "Compute Prefetch Address" + "(IPU)" |

**规律**：第一行写动作（动词短语），第二行写组件名（括号内缩写）。禁止把代码表达式、变量名、字段列表塞进节点。

### 3.2 配色体系（flowchart 专用）

与 Fig A 的架构图配色一致，但增加了 flowchart 特有的颜色：

| 类别 | 颜色 | Hex | 用途 |
|------|------|-----|------|
| Training 步骤 | 饱和蓝 | **#2B5EA7** | Phase 1/2 的处理节点 |
| Prefetch 步骤 | 饱和紫 | **#6C3483** | Phase 3 的处理节点 |
| 关键输出 | 琥珀金 | **#D4A843** | 写表操作（Record Chain Info, Stride Converged） |
| 成功终态 | 绿 | **#27AE60** | "Demand Load → L1 HIT" |
| 判断菱形 | 浅蓝 | **#AED6F1** | 所有 Decision 节点 |
| 跳过/抑制 | 灰 | **#BDC3C7** | Skip, No Prefetch, Suppress |
| Index PF 箭头 | 绿虚线 | **#27AE60** | IPU→L1 路径 |
| Data PF 箭头 | 红虚线 | **#C0392B** | DPU→L1 路径 |
| 回环/跳过 | 灰虚线 | **#BDC3C7** | Wait, Update, loop-back |
| 知识传递 | 深灰虚线 | **#808080** | Stride + Target Info 跨列 |

### 3.3 判断节点（菱形）规则

- 填充浅蓝 #AED6F1，深色文字
- Yes/No 标签紧贴箭头
- 菱形下方可加小字说明（如 "LDG → IMAD.WIDE → LDG"）
- 每列最多 2 个菱形，过多会显得冗长

---

## 4. 布局经验（最重要的发现）

### 4.1 紧凑 > 留白

**核心发现**：AI 生图默认留大量空白。必须在 prompt 中反复强调 COMPACT + 两列 CLOSE together + minimal gap。

用百分比定位效果好：
```
Left Column (8%-46%): Phase 1 top, Phase 2 bottom
Right Column (54%-92%): Phase 3 full height
```
中间 gap 只留 ~8%（46%→54%），不要留 >10%。

### 4.2 图例必须铺满底部全宽

**关键**：在 prompt 中写 "MUST stretch across the full figure width" + "FILL the entire bottom strip"。
分两行：上行 Arrow Styles（5 项），下行 Component Types（6 项），共 11 个图例项填满宽度。

### 4.3 Phase 分隔线用实线

虚线分隔太弱，AI 渲染后几乎不可见。改用 SOLID GRAY line (#AAAAAA, 1.5pt) 效果明显。

### 4.4 不要用彩色背景区域

尝试过三种背景方案：
- 统一灰色卡片（v4a）→ 布局混乱
- 暖灰/冷灰色调（v4b）→ 冷色偏蓝，不够"灰"
- 彩色区域底色（v3c）→ 用户反馈"不好看"、"诡异"

**结论**：白色背景最安全。如果要区分区域，用分隔线而不是底色。

---

## 5. 提示词结构（flowchart 版）

```
1. 拼写词典（CRITICAL EXACT SPELLING）
2. 一句话概述 + 格式约束（IEEE, 16:9, Times New Roman, NO title）
3. 布局描述（百分比定位，强调 COMPACT + 图例全宽底部）
4. Phase 1 节点列表（逐个描述：形状+颜色+文字+分支）
5. Phase 2 节点列表
6. Phase 3 节点列表
7. 跨列箭头描述（MUST physically cross）
8. Side Annotations
9. 图例描述（强调 FULL WIDTH + 11 项填满）
10. 标准风格约束段
```

### 与 Fig A 的区别

| 维度 | Fig A (架构图) | Fig B (流程图) |
|------|--------------|--------------|
| 节点描述 | 组件名 + 类型（Storage/Logic） | 动作短语 + 组件缩写 |
| 箭头 | 4 种语义色 | 同 4 色 + 灰色回环 + 深灰知识传递 |
| 布局强调 | 左右分区（SM vs GRASP） | 双列紧凑 + Phase 分隔线 |
| 图例位置 | 底部 | 底部全宽铺满 |
| 背景 | 白色 | 白色（彩色背景已验证不适合） |

---

## 6. 常见问题及修复

| 问题 | 原因 | 修复 |
|------|------|------|
| 中间大片留白 | AI 默认间距太大 | 百分比定位 + "COMPACT" + "CLOSE together" |
| 图例只占中间一小段 | 项目太少或未强调全宽 | 分两行 + 11 项 + "MUST stretch full width" |
| 节点文字像代码 | prompt 里写了代码表达式 | 改为动词短语 + 组件缩写 |
| Phase 分隔不明显 | 用了虚线 | 改用实线 #AAAAAA 1.5pt |
| 彩色背景不好看 | 颜色不够淡 / 风格不匹配 | 不用背景色，白底 + 分隔线 |
| nano-banana-pro 不可用 | API 间歇性故障 | 等待 + 重试，或用 nano-banana 出草稿验证布局 |

---

## 7. 后续 Fig C-G 应遵循的风格

1. **白色背景** + 实线分隔区域
2. **节点文字 3-8 词/行，最多两行**
3. **图例铺满底部全宽**（分两行，凑够 10+ 项）
4. **配色对齐本文 §3.2 表格**
5. **百分比定位布局**，两列 gap ≤ 8%
6. **拼写词典**永远在 prompt 最前
7. **优先用 nano-banana-pro**，宕机时 nano-banana 出草稿
