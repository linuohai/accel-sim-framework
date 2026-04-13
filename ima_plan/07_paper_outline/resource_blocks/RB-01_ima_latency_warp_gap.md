# RB-01: IMA 延时与 Warp 需求缺口

> 创建: 2026-04-04
> 最近更新: 2026-04-05

## 核心想法

IMA 的 index→data 串行依赖链导致有效内存延时远超 GPU warp 调度能力的隐藏上限，这是 IMA 在 GPU 上成为性能瓶颈的**根本物理原因**。

## 要素

### 1. 术语定义

- **IMA index load**: `A[B[i]]` 中的 `B[i]` — 加载索引值（内层访存）
- **IMA data load**: `A[B[i]]` 中的 `A[·]` — 用索引值作为地址，加载最终数据（外层访存）
- 二者存在**严格数据依赖**：data load 的地址 = index load 的返回值 → 无法并行、无法乱序

### 2. 延时统计

#### 实测数据（BFS, 1SM, 逐迭代跟踪）

来源：`05_implementation/debug/bfs_1sm_postfix/analysis/event_timeline_warp0.txt`

| 场景 | Index L1 状态 | Data L1 状态 | Index 延时 | Data 延时 | 链总延时 |
|------|-------------|-------------|-----------|----------|---------|
| 冷启动（首次访问） | MISS | MISS | ~443c | ~443c | **933c** |
| 热态（index 命中） | HIT | MISS | ~45c | ~443c | **487-488c** |
| Sector miss | SECTOR_MISS | MISS | ~423c | ~443c | **913c** |

#### Cache 延时参数

| 参数 | 值 | 来源 |
|------|-----|------|
| L1 hit latency | ~34 cycles | gpgpusim.config |
| L1 miss → L2 hit fill | ~443 cycles | 实测 (issue → fill) |
| L2 miss → HBM | ~500+ cycles | DRAM timing model |
| IMA L1 miss rate | 70-77% | `01_ima_characterization/l1_miss_breakdown/` |

### 3. Little's Law 推导

#### 公式

$$N_{required} \times C \geq L_{eff}$$

其中：
- $N_{required}$：隐藏延时所需的 warp 数
- $C$：循环体计算周期（IMA 循环体极短，$C \approx 3$ cycles）
- $L_{eff}$：有效内存延时

#### IMA 链延时计算

$$L_{chain} = L_{index} + L_{data}$$

- L2 hit 场景（主体）：$L_{chain} \approx 443 + 443 = 886$ cycles
- 混合场景（考虑 ~25% index hit rate）：$L_{chain} \approx 0.75 \times 443 + 0.25 \times 34 + 443 \approx 784$ cycles
- 实测中位数：487-933 cycles

#### Warp 需求

$$N_{required} = \frac{L_{chain}}{C} = \frac{784}{3} \approx 261$$

- A100 SM 物理上限：$N_{max} = 64$ warps
- **缺口倍数**：$261 / 64 \approx 4.1\times$
- 即使取最乐观的 $L_{chain} = 487$：$N = 162$，仍是 $64$ 的 $2.5\times$

### 4. 结论

- GPU warp latency hiding 的设计前提在 IMA 下被根本性打破
- 不是 "性能不够好"，而是 **架构机制的结构性失效**
- → 必须引入 prefetching 来主动缩短 $L_{eff}$

### 5. Issue Stall 验证（静态统计）

#### 多算法 Stall 分布（统一数据集：web-Google, symmetric）

| 算法 | MEM_WAIT | WAIT_ATOMIC | PIPE_BUSY | 其他 |
|------|----------|-------------|-----------|------|
| CC | 97.2% | 0.0% | 2.6% | 0.2% |
| BC | 73.3% | 20.8% | 5.2% | 0.7% |
| SpMV | 71.3% | 0.0% | 27.5% | 1.2% |
| BFS | 64.6% | 30.4% | 4.9% | 0.1% |
| VC | 58.5% | 0.3% | 40.5% | 0.7% |
| SSSP | 49.2% | 24.9% | 25.9% | 0.0% |
| [PLACEHOLDER] | — | — | — | 待补充正在跑的实验 |

数据来源：`result/issue_trace/stall_reason_pc_stats/*_baseline/`（web_sym 变体）

### 6. 动态执行时间线 [DEFERRED]

已验证数据可行性（见下方数据接口说明），脚本框架在 `scripts/plot_execution_timeline.py`，待后续调整可视化风格后完成。

## 候选位置

| 论文章节 | 使用方式 |
|---------|---------|
| **§2.3 Motivation**（主选） | 完整推导 + 全部图表 |
| **§1.1 ¶2**（辅选） | 仅引用结论数据（~900c, ~261 warps, 4.1× gap） |

## 已完成的图

| 图 | 文件 | 脚本 |
|----|------|------|
| Fig A: IMA 延时 K 线图 | `figures/rb01/rb01_latency_candlestick.svg` | `scripts/plot_ima_latency_dist.py` |
| Fig B: Warp Gap | `figures/rb01/rb01_warp_gap.svg` | `scripts/plot_warp_gap.py` |
| Fig C: Stall Breakdown | `figures/rb01/rb01_stall_breakdown.svg` | `scripts/plot_stall_breakdown.py` |

---

## 绘图数据接口说明

以下说明每张图的数据来源、数据格式、以及如何新增/修改数据。

### Fig A: IMA 延时 K 线图 (`plot_ima_latency_dist.py`)

**数据方式**：脚本内硬编码 dict，**非**读取文件。

**数据位置**：脚本第 35-52 行 `ALGORITHMS` dict。

```python
ALGORITHMS = {
    "BFS":  {"chain_low": 860, "chain_med": 910, "chain_high": 940,
             "p25": 890, "p75": 935},
    ...
}
```

**字段含义**：
- `chain_low`: miss-only 链延时最小值（cycles）
- `chain_high`: miss-only 链延时最大值
- `chain_med`: 中位数
- `p25` / `p75`: 25/75 分位数（box 的上下边界）

**如何新增算法**：在 `ALGORITHMS` dict 中加一行即可，X 轴会自动扩展。

**如何用实测数据替换**：如果后续有 per-algorithm 的实测延时分布，替换 dict 中的值。数据来源参考 `05_implementation/debug/bfs_1sm_postfix/analysis/event_timeline_warp0.txt` 的格式（逐迭代的 `--- latency (idx→data served): NNNc` 行）。

---

### Fig B: Warp Gap (`plot_warp_gap.py`)

**数据方式**：脚本内硬编码 dict。

**数据位置**：脚本第 36-43 行 `WORKLOADS` dict。

```python
WORKLOADS = {
    "CC":   {"L_chain": 786, "C": 3},
    "BC":   {"L_chain": 786, "C": 5},
    ...
}
```

**字段含义**：
- `L_chain`: 加权平均 IMA 链延时（cycles）。当前统一用 786c（0.75×886 + 0.25×487）
- `C`: 循环体计算周期（cycles）。不同算法不同：BFS/SSSP/CC ~3, SpMV ~4, BC ~5

**计算逻辑**：`N_required = L_chain / C`，与 `N_MAX = 64`（A100 SM 上限）对比。

**如何新增算法**：在 `WORKLOADS` dict 加一行。

**如何更精确**：如果后续用仿真实测了 per-algorithm 的 L_chain 和 C，替换 dict 值。C 可以从 SASS 指令数推算。

---

### Fig C: Stall Breakdown (`plot_stall_breakdown.py`)

**数据方式**：从 CSV 文件读取（**非硬编码**）。

**数据位置**：`result/issue_trace/stall_reason_pc_stats/{dir_name}/{dir_name}_stall_reason_breakdown.csv`

**CSV 格式**（每行一个 stall reason）：
```csv
reason,stall_warp_events,fraction_of_stall_warp_events
MEM_WAIT,10295108446,0.97153168
PIPE_BUSY,275393621,0.02598842
...
```

**脚本中的映射**（第 27-34 行）：
```python
ALGORITHMS = {
    "CC":   "cc_web_sym_baseline",        # → 读取 cc_web_sym_baseline/ 目录
    "BC":   "bc_web_sym_baseline",
    "SpMV": "spmv_web_sym_baseline",
    "BFS":  "bfs_web_sym_baseline",
    "VC":   "vc_ima_med_baseline",        # ima_med = web_sym
    "SSSP": "sssp_web_sym_baseline",
}
```

**如何新增算法**：
1. 确保已跑完 baseline 仿真并用 stall 分析脚本生成了 `{name}_stall_reason_breakdown.csv`
2. 在 `ALGORITHMS` dict 加一行：`"NewAlg": "newalg_web_sym_baseline"`
3. 重新运行脚本

**X 轴顺序**：脚本第 60 行硬编码为穿插顺序（非单调递减），当前为 `["CC", "BFS", "SpMV", "SSSP", "BC", "VC"]`。新增算法需手动插入。

**Stall 分析脚本位置**：`result/issue_trace/plot/script/plot_stall_reason_pc_topk_other.py`

---

### Fig D: Timeline [DEFERRED] (`plot_execution_timeline.py`)

**数据方式**：从 gzipped issue trace 读取。

**数据源**：`result/issue_trace/bfs_web_issue.csv.gz`（953M, 108 SM BFS on web-Google）

**已验证的最佳窗口**：
- SM 0, cycle 1386000-1446000: 22726 ISSUE events, 40 warps (0-39)
- IMA index: 820 events, IMA data: 855 events
- Kernel launch at cycle ~1386260: 40 warps 同步从 PC=0x0 开始

**IMA PC 列表**（BFS golden chain）：
- INDEX: `{0x00c0, 0x01d0, 0x0640, 0x09a0, 0x0d00, 0x1060}`
- DATA: `{0x00f0, 0x0100, 0x0200, 0x0670, 0x09d0, 0x0d30, 0x1090}`

**如何换算法/数据集**：需要对应算法的 issue trace，且需更新 IMA PC 列表（从 golden chain CSV 中查找对应算法的 PCs）。

---

## 通用规范

所有绘图脚本共享以下约定：

```python
# 1. 路径计算
_REPO = Path(__file__).resolve().parents[4]  # → /workspace/prefetch
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))

# 2. 样式
from plot_util import apply_style, save_fig, CB10
apply_style()  # 加载 academic.mplstyle

# 3. 输出
OUT_DIR = Path(__file__).resolve().parent.parent / "figures" / "rb01"
save_fig(fig, "rb01_xxx", OUT_DIR, formats=("svg",))  # 只输出 SVG

# 4. 运行
python3 ima_plan/07_paper_outline/resource_blocks/scripts/plot_xxx.py
```

## 依赖与约束

| 项目 | 状态 |
|------|------|
| 延时实测数据 | **已有**（bfs_1sm_postfix） |
| Stall 分布（6 算法） | **已有**（web_sym 统一数据集） |
| BFS issue trace | **已有**（bfs_web_issue.csv.gz, 953M） |
| Golden chain CSV | **已有**（7 BFS chains） |
| 待补充算法 stall 数据 | **[PLACEHOLDER]** |
| Golden Rule 关联 | "字字有关联" — §1 引用的数据，§2.3 必须有推导 |
