# HBM 带宽利用率随时间变化（plot_bandwidth_over_time.py）

这个脚本用来把 Accel-Sim 输出的 CSV 里的 **HBM/DRAM 带宽利用率**（`hbm_occupancy`）沿着程序运行的 `cycle` 画成图（折线/填充两种风格），默认输出 **PNG**（也可选 SVG），便于观察 memory-bound 场景下带宽占用率是否提升（例如验证 prefetch 的效果）。

输出图片默认写到：

`accel-sim-framework/result/issue_trace/plot/result/bandwidth/`

> 运行方式：请使用 `python3 plot_bandwidth_over_time.py ...`（本环境里 `python` 可能是 2.7）。

> 默认输出为 **PNG**（便于直接预览/分享）。如果你只想要 SVG，可用 `--format svg`。

## 输入 CSV 要求

脚本需要 CSV 里包含以下列（列名大小写不敏感）：

- `cycle`
- `hbm_bw_GBps`：该时刻观测到的 HBM 带宽（GB/s）
- `hbm_occupancy`：带宽占用率（0~1，= `hbm_bw / theoretical_bw`）

说明：

- Issue trace CSV（`*_issue.csv`）通常每个 cycle 有多行，而且 **文件整体并不是按 cycle 全局排序的**（因为不同 SM 的 buffer flush 会交错写入）。  
  为了得到正确的“随时间变化”的曲线，脚本会先 **按 cycle 全局去重**（每个 cycle 只保留一条 `hbm_bw_GBps/hbm_occupancy`），再按 `cycle` 排序后画图。
- L1 trace CSV 也可以作为输入，但它的记录可能很稀疏（只在有 L1 事件时写一行），因此曲线可能不连续。

### unique_cycles 是什么

脚本输出里的 `unique_cycles` 指：**去重后的唯一 cycle 数量**。

- issue trace 里同一个 `cycle` 会对应多个 row（不同 SM / scheduler / warp 的事件），但 `hbm_bw_GBps/hbm_occupancy` 是全局值，所以按 `cycle` 去重后每个 cycle 只保留一条样本。

## 图的含义

图中默认会同时画 **折线** 和 **浅色阴影**：

- **折线（实线）**：每个 smoothing window 内 `hbm_occupancy` 的 **均值**（更适合看趋势）
- **浅色阴影**：每个 window 内 `hbm_occupancy` 的 **最小值~最大值范围**（用来表达波动/噪声幅度）

如果你只想要一条趋势折线，不想要阴影范围，可以加 `--no-range`。

虽然图只画 `hbm_occupancy`，但标题下方会保留：

- `avg_bw / peak_bw`：实际带宽的均值/峰值（GB/s）
- `theory≈...`：理论带宽（用 `hbm_bw_GBps / hbm_occupancy` 反推得到；因为 simulator 里 `occupancy = bw/theory`，所以这个反推值应接近常数）

## 参数说明

下面只解释参数含义（具体用法示例请看 `--help` 的 Examples）。

### 选择输入

- `positional_csvs`（位置参数）
  - 直接在命令末尾写一个或多个 CSV 路径。
  - 这是最推荐的方式：不需要 `--csv`。
- `--csv <path>`（可重复）
  - 显式指定输入 CSV 路径，可以重复传多个。
- `--stem <name>`（可重复）
  - 从 `accel-sim-framework/result/issue_trace/` 里按文件名 stem 选择。
  - 例如 `--stem pathfinder_issue` 会选择 `.../result/issue_trace/pathfinder_issue.csv`。
- `--all`
  - 把 `accel-sim-framework/result/issue_trace/` 目录下的所有候选 CSV 都画一遍。

如果以上都不提供，脚本会自动从 `accel-sim-framework/result/issue_trace/` 中挑选“最新且包含带宽列”的 CSV 作为默认输入。

### 平滑/采样

- `--points N`
  - 目标绘制点数（默认 2000）。脚本会根据去重后的 `unique_cycles` 估算 window 大小，使最终点数接近 N。
- `--window W`
  - 直接指定 smoothing window 的大小（按“去重后的 unique cycle 样本数”计数），会覆盖 `--points`。
- `--smooth K`
  - 在 window 之后再对折线做一次 **K 点移动平均**（K 越大折线越平滑；默认 1 表示关闭）。
- `--no-range`
  - 关闭浅色阴影（min~max 范围），只画均值折线。

### 图类型与格式

- `--fill`
  - 开关：启用“填充/柱体”风格图（把每个 window 画成实心柱体，并叠加一条平滑折线，便于看趋势）。
  - 不加 `--fill` 时默认输出折线图（带可选阴影带）。
- `--format {png,svg,both}`
  - 输出格式（默认 `png`）。
  - 对于每个输入 CSV：
    - 折线图输出：`*_bandwidth.png`（或 `.svg`）
    - `--fill` 时输出：`*_bandwidth_fill.png`（或 `.svg`）
- `--dpi`
  - PNG 分辨率参数（默认 100），一般不需要改。

### 输出与画布

- `--out-dir <path>`
  - 输出目录（默认：`accel-sim-framework/result/issue_trace/plot/result/bandwidth/`）
- `--width / --height`
  - 画布大小（像素），对 PNG/SVG 都生效

## PNG 依赖说明

PNG 输出需要 `matplotlib + numpy`。如果你的环境没有这些包：

- 最简单：用 `--format svg` 先生成 SVG；
- 或者安装到脚本目录的 `_pydeps/`（不污染系统环境），例如：

`TMPDIR=/data00/shn/workbench/.tmp PIP_CACHE_DIR=/data00/shn/workbench/.pip_cache pip3 install --no-cache-dir --target accel-sim-framework/result/issue_trace/plot/script/_pydeps numpy==1.19.5 matplotlib==3.2.2`
