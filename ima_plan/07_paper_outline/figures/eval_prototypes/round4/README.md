# Round 4 §5 Evaluation Layout Prototypes

> 生成日期: 2026-04-08
> Plan 文件: `.claude/plans/enchanted-stargazing-hennessy.md`
> 下一阶段: 用户从每个子节的备选中选 1 个 → Round 5 精炼

## 背景

经过 Round 1-2 的 27 张独立原型探索和 Round 3 的 palette/reduction 对比，本轮（Round 4）目标是**把散落的原型组合成可直接插入论文的"子节级布局"**。每个子节有 2-3 个备选布局，用户从中每节选 1 个进入 Round 5。

**§5 大纲（简化后，5 子节）**：
```
§5.1 Setup & Methodology Recap         (≈0.2 页，无图)
§5.2 IPC Speedup vs SOTA [A+D 合并]    (≈0.8 页，1 fig)
§5.3 Quality + Mechanism [B+C 合并]    (≈1.0 页，1-2 fig)
§5.4 Sensitivity + Ablation [E+F]      (≈0.8 页，1 fig)
§5.5 Hardware Cost [G]                 (≈0.3 页，1 table)
```

全局约束：
- 无 Ideal L1D bar（Round 4 用户决定删除）
- `PALETTE_TOL_BRIGHT`（避开 §2-§4 已用的 blue/orange）
- `HATCHES_DENSE`（密集 hatching 便于 B&W 打印）
- Subplot labels (a)(b)(c) **放在轴下方**（`subplot_label()` helper）
- Scripts 深度 `parents[5]`（因为 `round4/` 比 `eval_prototypes/` 深一级）

---

## §5.2 — IPC Speedup vs SOTA (3 备选)

**数据**：27 workloads × 4 方案 (Snake, CAPS, Spare Register, GRASP)，NoPF=1.0× baseline。
**Geomean**：Snake 1.018×, CAPS 0.989×, Spare Reg 1.043×, **GRASP 1.182×**

| ID | 文件 | 描述 | 尺寸 | 特点 |
|:--:|------|------|:----:|------|
| **L-5.2-A** | `proto_r4_52_A.py` | 单行 grouped bar，27 wkl × 4 方案 + GMEAN，NoPF=1.0 虚线 | 7.0×2.9 | 最经典，密度适中 |
| **L-5.2-B** | `proto_r4_52_B.py` | 2 行：row1=per-wkl bar，row2=按 7 算法 box plot (4 方案 × 8 group) | 7.0×4.5 | 既有细节又有分布 |
| **L-5.2-C** | `proto_r4_52_C.py` | 1×2：左=全量 27 wkl × 4 方案，右=按 8 算法 GMEAN bar | 7.0×2.9 | 左右对比 per-wkl vs per-alg |

**建议查看顺序**：先看 A（基线），再看 B（信息最全），最后看 C（可能折中选择）

---

## §5.3 — Quality + Mechanism Effectiveness (3 备选，4 文件)

**数据**：27 workloads × 6 指标
- Quality: Index Cov (21.6% avg), Data Cov (20.4% avg), Timeliness (82.7% avg)
- Mechanism: IMA Miss Reduction (20.0% avg), Pipeline Delivered (40.6% avg), CT Entry Reuse (~166K geomean)

| ID | 文件 | 描述 | 尺寸 | Panel 数 |
|:--:|------|------|:----:|:-------:|
| **L-5.3-A** | `proto_r4_53_A.py` | 2×3 merged：row1=Quality 3 panel (Idx Cov/Data Cov/Timeliness)，row2=Mechanism 3 panel (Miss Red/Funnel/CT Reuse) | 7.0×5.0 | 6 |
| **L-5.3-B** | `proto_r4_53_B_qual.py` + `proto_r4_53_B_mech.py` | 2 张独立 fig: quality 1×3 + mechanism 1×3 | 2×(7.0×2.2) | 3+3 |
| **L-5.3-C** | `proto_r4_53_C.py` | 2×2 精简：Idx Cov / Timeliness / Miss Red / Funnel (丢 Data Cov 和 CT Reuse) | 7.0×3.5 | 4 |

**重要 caveat**：所有脚本用 `ima_total_reduction_pct`（IMA-only miss reduction）而非全 L1 miss reduction，后者被非-IMA traffic 稀释。Round 5 要确认论文里的措辞。

**建议查看顺序**：A（最全）→ C（最省空间）→ B（最灵活可拆）

---

## §5.4 — Sensitivity + Ablation (3 备选，4 文件)

**数据**：8-workload 核心集（consistent with Round 2 s1/s2/s3/a1 脚本）
- Distance sweep：D=1 最优（geomean 1.346×）
- Storage sweep：S1=712B 已饱和（只 SpM-wg 受益更大）
- Throttle sweep：D5b balance (39.2% speedup / 19.3% useless PF)
- Component ablation：**Full=+34.6% > Index-Only(+12.8%) + Data-Only(+17.3%) = 30.1%** → super-additive synergy

| ID | 文件 | 描述 | 尺寸 | Panel 数 |
|:--:|------|------|:----:|:-------:|
| **L-5.4-A** | `proto_r4_54_A.py` | 2×2 grid: distance / storage / throttle / ablation | 7.0×4.5 | 4 |
| **L-5.4-B** | `proto_r4_54_B.py` | 1×4 horizontal row: distance / storage / throttle / ablation | 7.0×2.4 | 4 |
| **L-5.4-C** | `proto_r4_54_C_sens.py` + `proto_r4_54_C_abl.py` | 2 张独立: sensitivity 1×3 + ablation 单栏 | 7.0×2.5 + 3.5×2.7 | 3+1 |

**建议查看顺序**：A（最紧凑）→ B（更扁平）→ C（最灵活）

---

## §5.5 — Hardware Cost (2 备选)

**数据**（来自 paper_structure.md + `grasp_config_t`）：
| Component | Entries × Size | Bytes |
|-----------|:--------------:|:-----:|
| CD FIFO | 20 × 16B | 320 |
| CT | 32 × 16B | 512 |
| TT | 8 × 8B | 64 |
| IST | 64 × 16B | 1024 |
| PRB | 32 × 8B | 256 |
| Misc | — | ~100 |
| **Total** | | **2276 B ≈ 2.3 KB/SM** |

Per-warp: **GRASP 36 B/warp** vs Snake 12 B/warp vs IMP/DMP 900 B/core.

| ID | 文件 | 描述 | 尺寸 |
|:--:|------|------|:----:|
| **L-5.5-A** | `proto_r4_55_A.tex` | LaTeX `\input{}`-able 表格片段（booktabs + caption + comparison footnote） | 3.5 文本宽 |
| **L-5.5-B** | `proto_r4_55_B.py` | 2-panel：(a) horizontal stacked bar breakdown，(b) log-scale comparison vs IMP/DMP/Tyche/Snake/GRASP | 3.5×3.3 |

**注意**：代码 `prb_capacity=1024`（Phase 1 large probe），但论文用 32-entry/256B 推荐值。Round 5 需确认最终数字。

---

## 用户选择清单

从每个子节的备选中选 **1 个** 进入 Round 5：

- [ ] §5.2: **A** / **B** / **C**
- [ ] §5.3: **A** / **B**（两张独立）/ **C**（精简 2×2）
- [ ] §5.4: **A**（2×2）/ **B**（1×4）/ **C**（两张独立）
- [ ] §5.5: **A**（表格）/ **B**（可视化）/ **两者都要**

---

## 文件清单

### §5.2 Speedup
- `proto_r4_52_A.{py,pdf,svg}` — Single row 27×4 grouped bar
- `proto_r4_52_B.{py,pdf,svg}` — 2-row (bar + box plot)
- `proto_r4_52_C.{py,pdf,svg}` — 1×2 (per-wkl + per-alg)

### §5.3 Quality+Mechanism
- `proto_r4_53_A.{py,pdf,svg}` — 2×3 merged
- `proto_r4_53_B_qual.{py,pdf,svg}` — Quality 1×3 standalone
- `proto_r4_53_B_mech.{py,pdf,svg}` — Mechanism 1×3 standalone
- `proto_r4_53_C.{py,pdf,svg}` — 2×2 compact

### §5.4 Sens+Ablation
- `proto_r4_54_A.{py,pdf,svg}` — 2×2 grid
- `proto_r4_54_B.{py,pdf,svg}` — 1×4 row
- `proto_r4_54_C_sens.{py,pdf,svg}` — Sensitivity 1×3
- `proto_r4_54_C_abl.{py,pdf,svg}` — Ablation standalone

### §5.5 Hardware Cost
- `proto_r4_55_A.tex` — LaTeX table fragment
- `proto_r4_55_B.{py,pdf,svg}` — Stacked bar + comparison

**Round 4 共产出**：13 个源文件（12 .py + 1 .tex）+ 24 渲染文件（12 .pdf + 12 .svg） = **37 个文件**。

---

## Round 5 待决定

用户选完布局后，Round 5 需要：
1. **最终 palette 选择**（已有 6 个 Round 3 变体）
2. **Annotation 策略**（outlier-only vs full labels）
3. **Legend 位置细节**（检查不遮挡数据）
4. **Caption 文案**
5. **§5.3 的 "IMA miss reduction" vs "L1 miss reduction" 措辞**（关键！）
6. **§5.5 硬件开销最终数字**（确认 PRB=32 vs 1024）
7. **LaTeX 集成**（插入 main.tex，验证 §5 页面布局不超 3.5 页）
