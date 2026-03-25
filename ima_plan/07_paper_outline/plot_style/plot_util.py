"""
Shared plotting utilities for GRASP paper figures.

Usage:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[N] / "ima_plan/07_paper_outline/plot_style"))
    from plot_util import apply_style, figsize_col, save_fig, CB10
    apply_style()
"""

from pathlib import Path
import matplotlib.pyplot as plt

# ── Style ─────────────────────────────────────────────────────────────────────

_STYLE_PATH = Path(__file__).resolve().parent / "academic.mplstyle"


def apply_style():
    """Apply the academic mplstyle. Call once at script start."""
    plt.style.use(str(_STYLE_PATH))


# ── Figure Sizes (IEEE/ACM double-column) ─────────────────────────────────────

COL_WIDTH = 3.5    # inches — single column
FULL_WIDTH = 7.0   # inches — full page width


def figsize_col(aspect=0.72):
    """Return (width, height) for a single-column figure."""
    return (COL_WIDTH, COL_WIDTH * aspect)


def figsize_full(aspect=0.38):
    """Return (width, height) for a full-width figure."""
    return (FULL_WIDTH, FULL_WIDTH * aspect)


# ── Color Palettes ────────────────────────────────────────────────────────────

# Tableau Colorblind 10 (matches axes.prop_cycle in academic.mplstyle)
CB10 = [
    "#006BA4", "#FF800E", "#ABABAB", "#595959", "#5F9ED1",
    "#C85200", "#898989", "#A2C8EC", "#FFBC79", "#CFCFCF",
]


# B: High contrast — each L1 status has a distinct hue
COLORS_L1_STATUS = {
    "HIT":              "#006BA4",  # blue
    "HIT_RESERVED":     "#5F9ED1",  # light blue
    "MSHR_HIT":         "#2CA02C",  # green
    "MISS":             "#FF800E",  # orange
    "SECTOR_MISS":      "#D62728",  # red
    "RESERVATION_FAIL": "#595959",  # gray
}

# B: Semantic grouping — memory=blue, compute=orange, sync=gray
COLORS_STALL = {
    "MEM_WAIT":            "#006BA4",  # deep blue — primary memory stall
    "WAIT_MEMBAR":         "#5F9ED1",  # mid blue — memory barrier
    "WAIT_LDGSTS":         "#A2C8EC",  # light blue — async copy
    "REG_WAIT":            "#FF800E",  # orange — register dependency
    "PIPE_BUSY":           "#FFBC79",  # light orange — pipeline busy
    "CONTROL_HAZARD":      "#C85200",  # dark orange — control hazard
    "IBUFFER_EMPTY":       "#ABABAB",  # light gray — fetch starvation
    "WAIT_CTA_BARRIER":    "#595959",  # dark gray — CTA sync
    "WAIT_ATOMIC":         "#898989",  # mid gray — atomic ops
    "WAIT_DONE":           "#CFCFCF",  # lightest gray — done wait
}

# B: Blue + red — maximum cold/warm contrast
COLORS_IMA_ROLE = {
    "index_load": "#006BA4",
    "data_load":  "#D62728",
}


# ── Legend Helpers (anti-overlap) ──────────────────────────────────────────────


def legend_outside(ax, ncol=1, loc="upper left", anchor=(1.02, 1.0), **kwargs):
    """Place legend outside the axes (right side by default).

    Requires fig created with constrained_layout=True to allocate space.
    """
    return ax.legend(
        loc=loc, bbox_to_anchor=anchor, ncol=ncol,
        borderaxespad=0, **kwargs,
    )


def legend_below(fig, axes=None, ncol=4, y=-0.05, **kwargs):
    """Place a shared legend below the figure.

    Collects handles from all axes. Requires constrained_layout=True.
    """
    if axes is None:
        axes = fig.get_axes()
    handles, labels = [], []
    seen = set()
    for ax in (axes if hasattr(axes, '__iter__') else [axes]):
        for h, l in zip(*ax.get_legend_handles_labels()):
            if l not in seen:
                handles.append(h)
                labels.append(l)
                seen.add(l)
    return fig.legend(
        handles, labels,
        loc="upper center", bbox_to_anchor=(0.5, y), ncol=ncol,
        frameon=False, **kwargs,
    )


# ── Save Helpers ──────────────────────────────────────────────────────────────


def save_fig(fig, stem, out_dir, formats=("pdf", "svg")):
    """Save figure in multiple formats.

    Args:
        fig: matplotlib Figure
        stem: filename without extension (e.g., "ipc_comparison")
        out_dir: output directory (created if not exists)
        formats: tuple of format strings ("pdf", "svg", "png")
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for fmt in formats:
        path = out_dir / f"{stem}.{fmt}"
        fig.savefig(path, format=fmt)


# ── Bar Chart Helpers ─────────────────────────────────────────────────────────


def annotate_bars(ax, bars, fmt="{:.1f}", fontsize=6, offset=0.5):
    """Add value labels above bar patches.

    Args:
        ax: matplotlib Axes
        bars: BarContainer from ax.bar()
        fmt: format string for values
        fontsize: label font size (default 6pt — smaller than tick labels)
        offset: vertical offset above bar top
    """
    for bar in bars:
        h = bar.get_height()
        if h > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + offset,
                fmt.format(h),
                ha="center",
                va="bottom",
                fontsize=fontsize,
            )
