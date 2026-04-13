# Fig A 成果归档 + AI 生图经验总结

> 最近更新: 2026-04-05
> 适用范围: GRASP 论文 §3 Design 章节所有非数据图
> 模型: nano-banana-pro (Gemini 3 Pro Image via PoE API)

---

## 1. 迭代概览

| 版本 | 文件 | 提示词版本 | 解决的问题 |
|------|------|-----------|-----------|
| V1 | `v9_baseline.png` | v9 | 首次使用正确配色 #2B5EA7/#6C3483 + 黑色描边 + 标准风格约束段 |
| V2 | `v10_layout_fix.png` | v10 | GRASP↔L1 位置交换、去掉省略号、L1↔L2 两条箭头、Title Case 标签、IST 紫色 |
| V3 | `v11_label_fix.png` | v11 | 紧凑布局、GRASP Prefetcher 全名、PQ→L1 箭头修正 |
| V4 | `v12_final.png` | v12 | TC 同等大小、TC→PQ→{L1,MSHR} 路径简化、Times New Roman 字体 |
| SVG | `fig_a_editable.svg` | v12 | 可编辑矢量版，每个元素可单独修改 |

提示词文件：`../fig_a_prompt.md`（v12，当前最优版本）
SVG 生成脚本：`gen_fig_a_svg.py`（改参数可重新生成）

---

## 2. 配色配方（最重要的经验）

### 2.1 颜色选择

**必须使用 `figure_prompts.md` 的标准色板**，不要自创配色：

| 类别 | 颜色 | Hex | 用途 |
|------|------|-----|------|
| 存储 | 饱和蓝 | **#2B5EA7** | CT, TT, PRB, IST, PQ |
| 逻辑 | 饱和紫 | **#6C3483** | CD, IPU, DPU, ACU, TC |
| 外部 | 白 | #FFFFFF | SM, L1, L2（边框 #2C3E50） |
| Index PF 箭头 | 绿 | **#27AE60** | IPU→PRB→L1→ACU |
| Data PF 箭头 | 红 | **#C0392B** | ACU→DPU→PQ→L1 |
| TC 控制箭头 | 灰 | **#BDC3C7** | TC→DPU, TC→PQ |
| L1↔L2 箭头 | 深灰 | **#808080** | Req/Rsp（区分 Training Path） |

### 2.2 饱和度 > 亮度

这是本次迭代最核心的发现：

| 配色 | 蓝 | 紫 | 效果 |
|------|---|---|------|
| ~~v3 暗灰~~ | #2B3A67 (S=41%) | #5B3A8C (S=41%) | 阴暗、压抑 |
| ~~v4 中性~~ | #4472C4 (S=47%) | #7B68AE (S=27%) | 平淡、企业PPT感 |
| **v9+ 饱和** | **#2B5EA7 (S=58%)** | **#6C3483 (S=41%)** | **鲜明、高对比、学术感** |

**规律**：AI 生图中，高饱和度 + 中等深度 的颜色在白底上"跳出来"。低饱和度无论深浅都显得平淡。

### 2.3 黑色描边

所有方框必须有 **1-1.5pt 黑色** 描边（`stroke="black"`），不要用边框色匹配填充色。黑色描边让每个元素有清晰的定义感，防止方框在白底上"浮起来"。

---

## 3. 提示词结构配方

### 3.1 整体结构（按顺序）

```
1. 拼写词典（CRITICAL EXACT SPELLING）
2. 一句话概述（Generate a ... block diagram for ...）
3. 整体布局描述（Layout: left side, right side, bottom）
4. 左侧组件（逐个列出，内联标注颜色）
5. 右侧组件（分上下子区域）
6. 箭头流（带编号圈 ①②③...）
7. 图例描述
8. 标准风格约束段（从 figure_prompts.md 逐字复制）
```

### 3.2 关键技巧

1. **拼写词典在最前**：列出所有组件的正确拼写 + 常见错误拼写，已验证可显著减少 AI 拼写错误

2. **每个组件内联标注颜色**：
   ```
   "CD (Chain Detector)" — purple (#6C3483) box, white text, black border
   ```
   不要用抽象规则（"所有逻辑单元用紫色"），AI 模型更可靠地执行内联指令

3. **风格约束不要分离**：把标准风格约束段作为提示词的最后一个段落，不要放在单独的 "Style Block" 中。分离的 Style Block 容易被 AI 忽略

4. **箭头用 "MUST physically reach" 强调**：对于需要跨区域的箭头（如 PRB→L1），必须写明 "This arrow MUST physically reach the L1 box in the SM column"

5. **字体指定 Times New Roman**：学术论文标准字体，明确写入风格约束段

### 3.3 标准风格约束段（逐字复制）

```
Style constraints (MUST follow):
- Academic paper figure style, clean and professional
- White background, no decorative elements or shadows
- Black outlines (1-1.5pt) on all boxes and arrows
- Font: Times New Roman for ALL text (component labels, arrow labels, legend)
- Bold for component abbreviations inside colored blocks
- Italic for arrow labels
- Color palette: use only blue (#2B5EA7), red/dark-red (#C0392B), purple (#6C3483),
  green (#27AE60), and grays (#BDC3C7, #ECF0F1)
- Dashed gray rectangles for grouping/regions, with module name at top-right corner
- All text must be crisp and readable at print size (minimum 8pt equivalent)
- IEEE/ACM double-column paper format, figure width ~7.0in (full width)
- Do NOT include any title or caption in the image
- Do NOT include any text that is not a component name, arrow label, or legend entry
```

---

## 4. 箭头语义规则

| 路径 | 颜色 | 线型 | 含义 | 示例 |
|------|------|------|------|------|
| 训练路径 | 黑 #2C3E50 | 实线 | 指令检测→写表 | Issue→CD→CT→TT |
| Index Prefetch | 绿 #27AE60 | 虚线 | 步骤 1：索引预取 | IPU→PRB→L1→ACU |
| Data Prefetch | 红 #C0392B | 虚线 | 步骤 2：数据预取 | ACU→DPU→PQ→L1 |
| TC 控制 | 灰 #BDC3C7 | 虚线 | 节流控制 | TC→DPU, TC→PQ |
| L1↔L2 | 深灰 #808080 | 实线 | 缓存层级通信 | Req↓ Rsp↑ |

**重要**：灰色虚线箭头**仅限 TC 功能**。其他数据流箭头不要用灰色。

---

## 5. 常见问题及修复

| 问题 | 原因 | 修复方法 |
|------|------|---------|
| 图顶部出现标题 | AI 自动添加 | 在约束段写 "Do NOT include any title or caption" |
| 组件名拼写错误 | AI 生图通病 | 在提示词最前加拼写词典 + NOT 反例 |
| 颜色偏灰/平淡 | 饱和度不够 | 用 #2B5EA7/#6C3483 替代偏灰的 #4472C4/#7B68AE |
| 箭头不到位 | AI 空间推理弱 | 写 "MUST physically reach the X box" |
| 箭头标签像代码 | 用了变量名 | Title Case 正式英文：tt_idx → Target Index |
| 风格不一致 | Style Block 分离 | 风格约束整合在提示词末尾，不分离 |
| prompt 泄漏 | 指令混入内容 | 在约束段写 "Do NOT include any text that is not a component name" |
| 布局太空旷 | 组件间距过大 | 写 "Keep the layout COMPACT with minimal whitespace" |

---

## 6. 工作流

```
1. 写提示词（参考本文档的结构配方）
2. 调 PoE API 生成（nano-banana-pro, 16:9, 1K）
3. 自审：对照检查表逐项验证
4. 迭代：针对具体问题修改提示词，最多 3 轮
5. 用户反馈：展示最佳结果，收集结构/布局调整意见
6. 矢量化：用 SVG 脚本生成可编辑版本，或在 draw.io 中以 AI 图为模板重绘
```

### API 调用模板

```bash
python3 -c "
import json, requests, re, os
prompt = open('prompt.txt').read()
resp = requests.post('https://api.poe.com/v1/chat/completions',
    headers={'Authorization': f'Bearer {os.environ[\"POE_API_KEY\"]}', 'Content-Type': 'application/json'},
    json={'model': 'nano-banana-pro', 'messages': [{'role': 'user', 'content': prompt}],
          'image_only': True, 'aspect_ratio': '16:9', 'image_size': '1K'},
    timeout=90)
url = re.search(r'!\[.*?\]\((https://.*?)\)', resp.json()['choices'][0]['message']['content']).group(1)
open('output.png', 'wb').write(requests.get(url).content)
"
```
