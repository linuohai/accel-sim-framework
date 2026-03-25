"""Generate visual swatches for candidate color palettes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_util import apply_style, FULL_WIDTH

apply_style()

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

OUT_DIR = Path(__file__).resolve().parent / "_preview"
OUT_DIR.mkdir(exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
# Candidate palettes
# ══════════════════════════════════════════════════════════════════════════════

L1_STATUS_OPTIONS = {
    "A: 语义冷暖（蓝=命中, 橙红=未命中）": {
        "HIT":              "#006BA4",  # 深蓝
        "HIT_RESERVED":     "#5F9ED1",  # 中蓝
        "MSHR_HIT":         "#A2C8EC",  # 浅蓝
        "MISS":             "#FF800E",  # 橙
        "SECTOR_MISS":      "#C85200",  # 深橙
        "RESERVATION_FAIL": "#595959",  # 灰
    },
    "B: 高对比度（每个类别独立色相）": {
        "HIT":              "#006BA4",  # 蓝
        "HIT_RESERVED":     "#5F9ED1",  # 浅蓝
        "MSHR_HIT":         "#2CA02C",  # 绿
        "MISS":             "#FF800E",  # 橙
        "SECTOR_MISS":      "#D62728",  # 红
        "RESERVATION_FAIL": "#595959",  # 灰
    },
    "C: 沿用现有脚本配色（plot_ima_timeline.py 风格）": {
        "HIT":              "#93c5fd",  # 浅蓝
        "HIT_RESERVED":     "#38bdf8",  # 天蓝
        "MSHR_HIT":         "#14b8a6",  # 青
        "MISS":             "#f59e0b",  # 琥珀
        "SECTOR_MISS":      "#f97316",  # 橙
        "RESERVATION_FAIL": "#b91c1c",  # 暗红
    },
}

STALL_OPTIONS = {
    "A: CB10 顺序映射（与 mplstyle prop_cycle 一致）": {
        "MEM_WAIT":            "#006BA4",
        "REG_WAIT":            "#FF800E",
        "IBUFFER_EMPTY":       "#ABABAB",
        "WAIT_CTA_BARRIER":    "#595959",
        "WAIT_MEMBAR":         "#5F9ED1",
        "WAIT_ATOMIC":         "#C85200",
        "WAIT_LDGSTS":         "#898989",
        "WAIT_DONE":           "#A2C8EC",
        "CONTROL_HAZARD":      "#FFBC79",
        "PIPE_BUSY":           "#CFCFCF",
    },
    "B: 语义分组（内存=蓝系, 计算=橙系, 同步=灰系）": {
        "MEM_WAIT":            "#006BA4",  # 深蓝 — 主要内存 stall
        "WAIT_MEMBAR":         "#5F9ED1",  # 中蓝 — 内存屏障
        "WAIT_LDGSTS":         "#A2C8EC",  # 浅蓝 — 异步拷贝
        "REG_WAIT":            "#FF800E",  # 橙 — 寄存器依赖
        "PIPE_BUSY":           "#FFBC79",  # 浅橙 — 流水线忙
        "CONTROL_HAZARD":      "#C85200",  # 深橙 — 控制冒险
        "IBUFFER_EMPTY":       "#ABABAB",  # 浅灰 — 取指不足
        "WAIT_CTA_BARRIER":    "#595959",  # 深灰 — CTA 同步
        "WAIT_ATOMIC":         "#898989",  # 中灰 — 原子操作
        "WAIT_DONE":           "#CFCFCF",  # 最浅灰 — 完成等待
    },
    "C: 沿用现有脚本配色（plot_single_issue_breakdown.py）": {
        "MEM_WAIT":            "#1f77b4",
        "REG_WAIT":            "#ff7f0e",
        "IBUFFER_EMPTY":       "#2ca02c",
        "WAIT_CTA_BARRIER":    "#d62728",
        "WAIT_MEMBAR":         "#9467bd",
        "WAIT_ATOMIC":         "#8c564b",
        "WAIT_LDGSTS":         "#e377c2",
        "WAIT_DONE":           "#7f7f7f",
        "CONTROL_HAZARD":      "#bcbd22",
        "PIPE_BUSY":           "#17becf",
    },
}

IMA_ROLE_OPTIONS = {
    "A: 蓝+橙（CB10 前两色，最高对比）": {
        "index_load": "#006BA4",
        "data_load":  "#FF800E",
    },
    "B: 蓝+红（冷暖极端对比）": {
        "index_load": "#006BA4",
        "data_load":  "#D62728",
    },
    "C: 沿用 plot_ima_timeline.py": {
        "index_load": "#4f8ef7",
        "data_load":  "#ff9f43",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# Drawing functions
# ══════════════════════════════════════════════════════════════════════════════

def draw_palette_comparison(options, title, filename, bar_mode="flat"):
    """Draw side-by-side comparison of palette options."""
    n_options = len(options)
    fig, axes = plt.subplots(
        n_options, 1,
        figsize=(FULL_WIDTH, 1.1 * n_options + 0.3),
        squeeze=False,
    )

    for idx, (opt_name, palette) in enumerate(options.items()):
        ax = axes[idx, 0]
        keys = list(palette.keys())
        colors = [palette[k] for k in keys]
        n = len(keys)

        if bar_mode == "stacked":
            # Show as stacked bar to simulate real usage
            left = 0
            for i, (k, c) in enumerate(zip(keys, colors)):
                w = 1.0 / n
                ax.barh(0, w, left=left, color=c, edgecolor="black",
                        linewidth=0.4, height=0.6)
                left += w
            ax.set_xlim(0, 1)
            ax.set_ylim(-0.5, 0.5)
            ax.set_yticks([])
            ax.set_xticks([])
            # Legend below
            patches = [mpatches.Patch(facecolor=c, edgecolor="black",
                                       linewidth=0.4, label=k)
                       for k, c in zip(keys, colors)]
            ax.legend(handles=patches, loc="upper center",
                      bbox_to_anchor=(0.5, -0.15), ncol=min(n, 5),
                      fontsize=5.5, frameon=False, handlelength=1.0,
                      handletextpad=0.3, columnspacing=0.8)
        else:
            # Flat swatches
            for i, (k, c) in enumerate(zip(keys, colors)):
                ax.barh(0, 1, left=i, color=c, edgecolor="black",
                        linewidth=0.4, height=0.7)
                ax.text(i + 0.5, 0, k, ha="center", va="center",
                        fontsize=5, color="white" if _is_dark(c) else "black",
                        fontweight="bold")
            ax.set_xlim(0, n)
            ax.set_ylim(-0.5, 0.5)
            ax.set_yticks([])
            ax.set_xticks([])

        ax.set_title(opt_name, fontsize=7, loc="left", pad=2)
        ax.spines["bottom"].set_visible(False)
        ax.spines["left"].set_visible(False)

    fig.suptitle(title, fontsize=9, fontweight="bold", y=1.0)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(OUT_DIR / f"{filename}.png", dpi=200)
    plt.close(fig)
    print(f"Saved: {OUT_DIR / filename}.png")


def draw_stacked_bar_demo(options, title, filename):
    """Draw a realistic stacked bar chart demo for each option."""
    n_options = len(options)
    fig, axes = plt.subplots(
        1, n_options,
        figsize=(FULL_WIDTH, 2.5),
        sharey=True,
    )
    if n_options == 1:
        axes = [axes]

    # Fake data: 4 workloads
    workloads = ["BFS", "SSSP", "SpMV", "CC"]
    np.random.seed(42)

    for idx, (opt_name, palette) in enumerate(options.items()):
        ax = axes[idx]
        keys = list(palette.keys())
        colors = [palette[k] for k in keys]
        n_cat = len(keys)

        # Generate plausible proportions
        data = np.random.dirichlet(np.ones(n_cat) * 2, size=len(workloads))

        bottom = np.zeros(len(workloads))
        x = np.arange(len(workloads))
        for i, (k, c) in enumerate(zip(keys, colors)):
            ax.bar(x, data[:, i], bottom=bottom, color=c, edgecolor="black",
                   linewidth=0.3, width=0.7)
            bottom += data[:, i]

        ax.set_xticks(x)
        ax.set_xticklabels(workloads, fontsize=6)
        ax.set_ylim(0, 1)
        ax.set_title(opt_name.split(":")[0] + "方案", fontsize=7)

        if idx == 0:
            ax.set_ylabel("Fraction", fontsize=7)

    # Shared legend at bottom
    first_palette = list(options.values())[0]
    patches = [mpatches.Patch(facecolor=c, edgecolor="black", linewidth=0.3,
                               label=k)
               for k, c in first_palette.items()]
    fig.legend(handles=patches, loc="lower center",
               bbox_to_anchor=(0.5, -0.08), ncol=min(len(first_palette), 5),
               fontsize=5.5, frameon=False)

    fig.suptitle(title, fontsize=9, fontweight="bold")
    fig.tight_layout(rect=[0, 0.05, 1, 0.95])
    fig.savefig(OUT_DIR / f"{filename}.png", dpi=200)
    plt.close(fig)
    print(f"Saved: {OUT_DIR / filename}.png")


def _is_dark(hex_color):
    """Check if a hex color is dark (for text contrast)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (0.299 * r + 0.587 * g + 0.114 * b) < 140


# ══════════════════════════════════════════════════════════════════════════════
# Generate all previews
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # 1. L1 Status — flat swatches
    draw_palette_comparison(
        L1_STATUS_OPTIONS,
        "L1 Cache Status 配色方案对比",
        "01_l1_status_swatches",
    )
    # 1b. L1 Status — stacked bar demo
    draw_stacked_bar_demo(
        L1_STATUS_OPTIONS,
        "L1 Status — Stacked Bar 效果预览",
        "02_l1_status_stacked",
    )

    # 2. Stall — flat swatches
    draw_palette_comparison(
        STALL_OPTIONS,
        "Stall Reason 配色方案对比",
        "03_stall_swatches",
    )
    # 2b. Stall — stacked bar demo
    draw_stacked_bar_demo(
        STALL_OPTIONS,
        "Stall Reason — Stacked Bar 效果预览",
        "04_stall_stacked",
    )

    # 3. IMA Role — flat swatches
    draw_palette_comparison(
        IMA_ROLE_OPTIONS,
        "IMA Role 配色方案对比",
        "05_ima_role_swatches",
    )

    print(f"\nAll previews saved to: {OUT_DIR}/")
