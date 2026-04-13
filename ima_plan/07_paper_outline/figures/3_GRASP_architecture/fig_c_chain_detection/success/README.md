# Fig C 成果归档 + 经验总结

> 最近更新: 2026-04-05
> 适用范围: GRASP 论文 §3.2 Chain Detection 章节——CD 检测机制图
> 模型: nano-banana-pro (Gemini 3 Pro Image via PoE API)

---

## 1. 迭代概览

| 版本 | 文件 | 解决的问题 | 评分 |
|------|------|-----------|------|
| V1 | `working/figure_v1.png` | 首版三层结构（SASS+Warp+FIFO），但布局元数据泄漏（X:25%, LAYER 1 等） | 5/10 |
| V2 | `working/figure_v2.png` | 清除元数据，但 t1 重复、FIFO 文字小 | 7/10 |
| V3 | `working/figure_v3.png` | 修复时间标记，FIFO 仍偏小 | 7/10 |
| V4 | `working/figure_v4.png` | FIFO 文字放大、箭头增强——**基础版定型** | 8/10 |
| **V5** | **`success/v5_final.png`** | 真实 BFS SASS + 公式 + 双 Warp 追踪 + PC 标注——**最终版** | **8/10** |
| V6 | `working/figure_v6.png` | 全宽布局实验：Warp 占满全宽，但丢失了细节和箭头 | 8/10（布局好但内容不足） |
| V7 | `working/figure_v7.png` | 尝试合并 V5 细节 + V6 布局，效果不及 V5 | 8/10（不如 V5 平衡） |

**完整路径**：v1（元数据泄漏）→ v2（清除）→ v3-v4（渐进优化）→ **v5（重大升级：真实 SASS + 双 Warp FIFO）** → v6-v7（布局实验，但内容密度下降）

**核心教训**：v5 之后的布局优化（v6-v7）虽然修了全宽布局问题，但每次都丢失了细节（箭头、注解、灰色区分）。**内容完整性 > 布局完美**。

---

## 2. Fig C 的设计决策

### 2.1 三层时序图架构

Fig C 是论文中第一个**时序实例图**，与 Fig A（静态结构）和 Fig B（逻辑流程）本质不同：

| 层 | 内容 | 功能 |
|----|------|------|
| Layer 1: SASS 源码 | 真实 BFS SASS 指令 + PC + IMA 标注 | 给读者建立"代码→硬件"映射 |
| Layer 2: Warp 时间线 | 4 个 Warp 的指令交织 | 展示 GPU 多 Warp 执行环境 |
| Layer 3: CD FIFO 状态 | FIFO 推入/匹配/检测全过程 | 展示 CD 检测机制的核心逻辑 |

三层共享**时间轴**（t0→t1→t2→t3），跨层箭头连接代码、运行时、硬件状态。

### 2.2 为什么用真实 BFS SASS

v1-v4 使用的是近似指令（如 `LDG.E R5, [R24]`），v5 改为真实 BFS SASS：

| 字段 | 近似值（v1-v4） | 真实值（v5） |
|------|----------------|-------------|
| Index Load | `LDG.E R5, [R24]` | `LDG.E R0, [R16.64]` (PC 0x0640) |
| Addr Compute | `IMAD.WIDE R2, R5, 8, R0` | `IMAD.WIDE R2, R0, R11, c[0x0][0x178]` (PC 0x0660) |
| Data Load | `LDG.E R3, [R2]` | `LDG.E R4, [R2.64]` (PC 0x0670) |
| Scale 设置 | 无 | `IMAD.MOV.U32 R11, RZ, RZ, 0x4` (PC 0x0650) |

**数据源**：`ima_plan/01_ima_characterization/sass_analysis/core_cases/bfs_linear_base.sm80.sass`

### 2.3 三个 IMA 元素命名

| SASS 指令 | 标签 | 颜色 | 说明 |
|-----------|------|------|------|
| `LDG.E R0, [R16.64]` | IMA Index Load | 蓝 #2B5EA7 | 加载间接索引值 |
| `IMAD.WIDE R2, R0, R11, c[0x178]` | Addr Generation | 紫 #6C3483 | 编码 base+scale×index 映射关系 |
| `LDG.E R4, [R2.64]` | IMA Data Load | 琥珀 #D4A843 | 加载最终数据 |

"Addr Generation" 命名理由：该指令生成间接访问地址，同时暴露 base（c[0x178]）和 scale（R11=4）两个关键参数，是 GRASP 信息提取的核心来源。

### 2.4 双 Warp 追踪（V5 新增）

CD FIFO 同时追踪 2 个 Warp 的指令流。V5 展示的故事：
1. Warp 0 先执行 IMA 链 → FIFO 推入 entries
2. Warp 1 也被追踪 → 推入 FIFO
3. Warp 0 完成检测 → 写 CT/TT
4. Warp 1 的 entries 变为冗余（chain 已知）

FIFO 条目内容：
- LDG 条目：{PC, dst_reg}（如 pc=0x0640, dst=R0）
- IMAD.WIDE 条目：{base_addr, scale}（如 base=c[0x178], scale=4）

---

## 3. Fig C 特有的经验（区别于 Fig A/B）

### 3.1 时序图 vs 结构图/流程图

| 维度 | Fig A/B（静态/流程） | Fig C（时序实例） |
|------|---------------------|------------------|
| 核心挑战 | 组件布局、箭头路由 | **跨层时间轴对齐** |
| 文本精度 | 组件名 3-8 词 | **真实 SASS 指令 + 寄存器名** |
| 状态变化 | 无 | 每个时间步 FIFO 内容不同 |
| 跨层连接 | 单层内箭头为主 | **三层之间必须有箭头**（SASS→Warp→FIFO） |

**关键发现**：时序图的跨层箭头是信息连贯性的关键。v6/v7 丢失了这些箭头后，即使布局更好，图的信息传递也大幅下降。

### 3.2 百分比定位的双刃剑

- V1 使用 Gemini 优化的百分比坐标 → AI 模型将坐标文字渲染到图中（"X: 25%", "LAYER 1"）
- V2 在 prompt 中加 "Do NOT render coordinates" → 解决
- **V6 又犯同样错误**：prompt 写了 "2% to 98%" → 被渲染

**规则**：提示词中的所有数字定位信息，AI 模型可能当作内容渲染。要么不写具体数字，要么加强 "Do NOT render" 指令。

### 3.3 灰色去强调技巧

非关键元素（非 chain 指令、非 tracked Warp）用**浅灰色**渲染：
- SASS 中非 chain 行：灰色文字 #BDC3C7
- Warp 中非 chain 指令块：灰色填充 #BDC3C7
- Warp 2/3 全部灰色：表示不被 CD 追踪

**效果**：chain 指令（蓝/紫/琥珀）在灰色背景中自然"跳出来"，读者一眼就能识别 IMA 链模式。

### 3.4 内容完整性 > 布局完美

这是 Fig C 迭代中**最重要的发现**：

| 版本 | 布局质量 | 内容完整性 | 用户评价 |
|------|---------|-----------|---------|
| V5 | 中（左栏偏空） | **高**（箭头、注解、灰色区分、FIFO 详情） | **合格** |
| V6 | **高**（全宽、紧凑） | 低（丢失箭头、FIFO 缩太小） | 不合格 |
| V7 | 高 | 中（部分恢复） | 不合格 |

**结论**：对于信息密集的时序图，宁可布局不够完美，也不能丢失跨层箭头和注解。布局可以后期手动调整（如在 draw.io 或 SVG 中微调），但信息缺失需要完全重画。

---

## 4. 配色体系（继承 Fig A/B + 新增）

### 4.1 与 Fig A/B 一致的颜色

| 类别 | 颜色 | Hex | 用途 |
|------|------|-----|------|
| Training/Storage | 饱和蓝 | #2B5EA7 | IMA Index Load 指令、FIFO LOAD 条目 |
| Logic/Compute | 饱和紫 | #6C3483 | Addr Generation 指令、FIFO ADDR 条目 |
| Key Output | 琥珀金 | #D4A843 | IMA Data Load 指令、Chain Detected 事件 |
| Skip/Other | 灰 | #BDC3C7 | 非 chain 指令、非 tracked Warp |

### 4.2 Fig C 新增的颜色语义

| 类别 | 颜色 | 用途 |
|------|------|------|
| SASS 代码背景 | 灰 #E0E0E0 | SASS 源码区域 |
| 跨层映射箭头 | 灰虚线 #808080 | SASS → Warp 对应关系 |
| 追踪流箭头 | 黑实线 #2C3E50 | Warp → FIFO 检测流 |
| 匹配注解 | 灰斜体 | "src R0 matches dst R0" |
| CT/TT 写入 | 白底黑框 | Chain 检测结果写入 |

---

## 5. 提示词结构（时序图版）

```
1. 拼写词典（CRITICAL EXACT SPELLING）
2. 一句话概述 + 格式约束（16:9, Times New Roman, NO title）
3. 公式显示（可选，Fig C 有公式在顶部）
4. SASS 源码区域描述（灰色背景、真实指令、内联标签、IMA Chain 花括号）
5. Warp 时间线描述（4 Warp、tracked 标记、每个时间步的指令块 + 颜色）
6. CD FIFO 状态描述（逐时间步：push/match/detect，双 Warp 条目）
7. 跨层箭头描述（SASS→Warp 灰虚线，Warp→FIFO 黑实线，匹配弧线）
8. 图例（可选，Fig C V5 有图例，最终版可去掉以节省空间）
9. 标准风格约束段
```

### 与 Fig A/B 的区别

| 维度 | Fig A (架构图) | Fig B (流程图) | Fig C (时序图) |
|------|--------------|--------------|--------------|
| 核心元素 | 组件框 + 箭头 | 步骤节点 + 判断菱形 | SASS 代码 + Warp 时间线 + FIFO 状态 |
| 时间维度 | 无 | 逻辑顺序 | **真实时间轴 t0-t3** |
| 文本精度 | 组件名（学术英文） | 动作短语 | **真实 SASS + 寄存器 + PC** |
| 跨区连接 | 组件间箭头 | Phase 间箭头 | **三层跨层箭头** |
| 状态变化 | 无 | 无 | **每步 FIFO 内容不同** |
| 灰色去强调 | 无 | Skip/Suppress | **非 chain 指令 + 非 tracked Warp** |
| 数据来源 | 设计文档 | 设计文档 | **真实 SASS dump + trace 数据** |

---

## 6. 常见问题及修复

| 问题 | 原因 | 修复 |
|------|------|------|
| 布局元数据被渲染 ("X:25%", "LAYER 1") | prompt 中写了具体百分比和层标签 | 加 "Do NOT render coordinates/metadata" + 不写具体数字 |
| 时间标记重复 (两个 t1) | prompt 没强调"exactly FOUR" | 明确写 "exactly FOUR: t0, t1, t2, t3" |
| SASS 寄存器名错误 | AI 模型拼写不精确 | 拼写词典 + 用真实 SASS（不要自创指令） |
| 布局优化后丢失内容 | 修改 prompt 时删除了箭头/注解描述 | **每次修改 prompt 时检查是否丢失了信息**，保持核心内容不变 |
| 非 chain 指令不够"灰" | 只写了 "gray" 没强调 | 写 "LIGHT GRAY, de-emphasized, faded appearance" |
| FIFO 区域太小/太大 | 比例描述不当 | 给出百分比但加 "Do NOT render percentages" |
| 全宽布局后 Warp 时间线太空 | 去掉左侧标签列后指令密度不够 | 增加每 Warp 的指令数，或接受左侧标签布局 |

---

## 7. 后续 Fig D-G 应遵循的经验

1. **内容完整性优先**：宁可布局有瑕疵，也不要为了布局丢失跨层箭头和注解
2. **真实数据优先**：使用真实 SASS/trace 数据，不要自创近似值
3. **灰色去强调**：所有非核心元素用浅灰色，让关键信息自然突出
4. **百分比陷阱**：prompt 中的定位数字可能被渲染，始终加 "Do NOT render" 防护
5. **跨层箭头是时序图的生命线**：没有箭头连接，三层就变成三个独立的图
6. **配色对齐本系列色板**：蓝=Storage/Index、紫=Logic/Compute、琥珀=Key Output/Data、灰=Other
7. **迭代时保持 prompt 的增量修改**：不要每次重写整个 prompt，只改需要改的部分，避免无意中删除关键描述
8. **时序图比结构图/流程图更难**：AI 模型对跨层对齐、状态变化的理解较弱，需要更多迭代
