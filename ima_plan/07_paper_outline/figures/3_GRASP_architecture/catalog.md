# §3 GRASP 架构图 — 结构×配色探索目录

> 更新时间: 2026-04-05
> Pipeline: Gemini-3.1-Pro (布局) → Gemini-3.1-Pro (风格) → nano-banana-pro (渲染)
> 总图片数: 45（7 图 × 2-3 结构 × 3 配色）
> 旧探索图: old_exploration/ 子目录（51 张）

---

## 探索矩阵

| 图 | 结构变体 | × 配色 | = 小计 |
|----|---------|--------|--------|
| Fig A 总体架构 | dmp / vertical / symmetric | × 3 | 9 |
| Fig B Pipeline 流程图 | twocol / numbered | × 3 | 6 |
| Fig C CD 链检测 | contrast / steps | × 3 | 6 |
| Fig D CT/TT 表结构 | fanmap / threecol | × 3 | 6 |
| Fig E 预取时序 | threescene / pipeline | × 3 | 6 |
| Fig F Throttle Control | statemachine / decision | × 3 | 6 |
| Fig G BFS 实例 | fivepanel / sixpanel | × 3 | 6 |
| **合计** | **15 结构** | **× 3** | **45** |

### 3 套配色

| 代号 | Storage | Logic | Key | Success | 风格特征 |
|------|---------|-------|-----|---------|---------|
| blue_purple | #4472C4 蓝 | #7B68AE 紫 | #D4A843 琥珀 | #5AA469 绿 | 中性专业 |
| navy_steel | #1B4F72 深蓝 | #5B9BD5 钢蓝 | #F0B429 暖金 | #27AE60 翡翠 | 高对比沉稳 |
| sage_terracotta | #6B8E6B 鼠尾草 | #C0714A 陶土 | #5B7DB1 雾蓝 | #3A7D44 森林 | 温暖大地色 |

---

## Fig A — 总体架构框图（3 结构 × 3 配色 = 9）

| 结构 | blue_purple | navy_steel | sage_terracotta |
|------|------------|-----------|----------------|
| **dmp** (左cache右GRASP) | a_dmp_blue_purple | a_dmp_navy_steel | a_dmp_sage_terracotta |
| **vertical** (上下堆叠) | a_vertical_blue_purple | a_vertical_navy_steel | a_vertical_sage_terracotta |
| **symmetric** (CT/TT居中对称) | a_symmetric_blue_purple | a_symmetric_navy_steel | a_symmetric_sage_terracotta |

Agent 评价: dmp 结构最清晰，vertical 次之，symmetric 渲染偏小。blue_purple 在 dmp 上效果最好。

## Fig B — 两步 Pipeline 流程图（2 × 3 = 6）

| 结构 | blue_purple | navy_steel | sage_terracotta |
|------|------------|-----------|----------------|
| **twocol** (左训练右预取) | b_twocol_blue_purple | b_twocol_navy_steel | b_twocol_sage_terracotta |
| **numbered** (6步蛇形) | b_numbered_blue_purple | b_numbered_navy_steel | b_numbered_sage_terracotta |

Agent 评价: twocol 三个配色都 Excellent。numbered 结构描述更丰富。

## Fig C — CD 链检测（2 × 3 = 6）

| 结构 | blue_purple | navy_steel | sage_terracotta |
|------|------------|-----------|----------------|
| **contrast** (上噪声下干净) | c_contrast_blue_purple | c_contrast_navy_steel | c_contrast_sage_terracotta |
| **steps** (4步分镜) | c_steps_blue_purple | c_steps_navy_steel | c_steps_sage_terracotta |

Agent 评价: contrast 对比效果直观。steps 教学性更强。blue_purple 最干净。

## Fig D — CT/TT 表结构（2 × 3 = 6）

| 结构 | blue_purple | navy_steel | sage_terracotta |
|------|------------|-----------|----------------|
| **fanmap** (扇入/扇出) | d_fanmap_blue_purple | d_fanmap_navy_steel | d_fanmap_sage_terracotta |
| **threecol** (内存→表→预取) | d_threecol_blue_purple | d_threecol_navy_steel | d_threecol_sage_terracotta |

Agent 评价: threecol blue_purple 最佳 — 3列端到端流清晰。fanmap 三配色等效。

## Fig E — 预取时序（2 × 3 = 6）

| 结构 | blue_purple | navy_steel | sage_terracotta |
|------|------------|-----------|----------------|
| **threescene** (三情景递进) | e_threescene_blue_purple | e_threescene_navy_steel | e_threescene_sage_terracotta |
| **pipeline** (多iteration重叠) | e_pipeline_blue_purple | e_pipeline_navy_steel | e_pipeline_sage_terracotta |

Agent 评价: threescene blue_purple 最佳 — 1120→580→0 递进清晰。pipeline 展示流水线重叠效果。

## Fig F — Throttle Control（2 × 3 = 6）

| 结构 | blue_purple | navy_steel | sage_terracotta |
|------|------------|-----------|----------------|
| **statemachine** (双状态机) | f_statemachine_blue_purple | f_statemachine_navy_steel | f_statemachine_sage_terracotta |
| **decision** (决策流程+指标) | f_decision_blue_purple | f_decision_navy_steel | f_decision_sage_terracotta |

Agent 评价: statemachine 最简洁。decision 信息量更大（含效果指标）。

## Fig G — BFS Worked Example（2 × 3 = 6）

| 结构 | blue_purple | navy_steel | sage_terracotta |
|------|------------|-----------|----------------|
| **fivepanel** (DMP式5子图) | g_fivepanel_blue_purple | g_fivepanel_navy_steel | g_fivepanel_sage_terracotta |
| **sixpanel** (2×3六面板) | g_sixpanel_blue_purple | g_sixpanel_navy_steel | g_sixpanel_sage_terracotta |

Agent 评价: fivepanel 更紧凑。sixpanel 内容更完整（含 stride learning）。navy_steel 对比度最高。

---

## 下一步

用户 review 后选择：
1. 每张图选定 1 种结构 + 1 种配色
2. 用完整 pipeline 精修到 score ≥ 9
3. 升级到 2K 分辨率出 camera-ready 版
