# L1/L2 Cache 状态随时间变化（plot_l1_status_over_time.py）

这个脚本用于把 Accel-Sim 输出的 L1/L2 cache trace CSV 按 `cycle` 做时间分桶，然后画出 **status stack（堆叠面积图）**，用来观察运行过程中缓存状态的组成变化（HIT / MISS / RESERVATION_FAIL 等），便于定位压力突发区间与热点。

默认输出目录：

`accel-sim-framework/result/L1cache_trace/plot/result/l1_cache/`

运行方式（推荐用 `python3`）：

`python3 plot_l1_status_over_time.py ...`

默认输出为 **PNG**。如果你只想要 SVG，可用 `--format svg`（或 `--format both`）。

## 输入 CSV 要求

必需列（列名大小写不敏感）：

- `cycle`
- `l1_status`（或 `l2_status`）

可选列（用于过滤）：

- `op`（LD / ST）
- `space`（GLOBAL / LOCAL / SHARED / CONST / ...）

说明：

- CSV **不要求按 cycle 排序**。脚本会按 `cycle` 区间分桶后统计每个桶内各类 status 的计数，再绘图。

## 图的含义（Status Stack）

这张图把每个时间窗口里的 cache 事件按 `status` 做堆叠，能直观看到：

- MISS/SECTOR_MISS 是否在运行中出现“突发段”
- RESERVATION_FAIL 是否在某些区间显著抬升（通常代表 L1 侧背压/资源紧张）
- prefetch 之后是否把一部分 MISS 转化为 HIT/MSHR_HIT，或降低 RESERVATION_FAIL 占比

## 参数说明

### 选择输入

- 位置参数：直接在命令末尾写一个或多个 CSV 路径（最推荐）
- `--csv <path>`：显式指定输入 CSV 路径（可重复）
- `--stem <name>`：从 `result/L1cache_trace/` 里按 stem 选择（可重复），例如 `--stem bfs_web_l1`
- `--all`：把 `result/L1cache_trace/` 下所有 CSV 都画一遍

如果以上都不提供，脚本会从 `result/L1cache_trace/` 中自动挑选“最新且包含必要列”的 CSV。

### 分桶与平滑

- `--points N`
  - 目标绘制点数（默认 2000）。脚本会根据 cycle 范围估算窗口大小，使最终点数接近 N。
- `--window W`
  - 直接指定窗口大小（单位：cycle），会覆盖 `--points`。
- `--smooth K`
  - 对绘制点再做一次 K 点移动平均（默认 1 表示关闭）。
- `--per-cycle`
  - 把“每个 window 的事件数”除以窗口 span，变成“每 cycle 的事件率”（不同 window 配置更容易对比）。
- `--normalize`
  - 把堆叠图归一化到 0~1（每个窗口显示各 status 的比例，而不是绝对计数）。

### 过滤（建议用来聚焦 IMA 负载）

- `--op LD` / `--op ST`
- `--space GLOBAL` / `--space LOCAL`
- 多个值可用逗号分隔，或重复传参（例如 `--space GLOBAL --space LOCAL`）。

### 输出

- `--format {png,svg,both}`（默认 png）
- `--out-dir <path>`
- `--width / --height`：画布大小（像素）

## 示例

```bash
python3 plot_l1_status_over_time.py
python3 plot_l1_status_over_time.py ../../bfs_web_l1.csv
python3 plot_l1_status_over_time.py --stem bfs_web_l1
python3 plot_l1_status_over_time.py --op LD --space GLOBAL
python3 plot_l1_status_over_time.py --window 50000 --per-cycle
python3 plot_l1_status_over_time.py --normalize --format svg
```
