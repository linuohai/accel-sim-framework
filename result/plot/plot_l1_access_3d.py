#!/usr/bin/env python3
import argparse
import csv
import math
from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch


def _parse_int(value):
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return int(value, 0)
    except ValueError:
        return None


def _resolve_field(fieldnames, candidates):
    for cand in candidates:
        if cand in fieldnames:
            return cand
    return None


def _parse_ops(value):
    if not value:
        return set()
    parts = [part.strip().upper() for part in value.split(",")]
    return {part for part in parts if part}


def load_l1_trace(
    path: Path,
    op_filter,
    sample_every: int,
    max_rows: int,
):
    cycles = []
    sms = []
    warps = []
    addrs = []
    ops = []
    statuses = []

    with path.open() as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        cycle_key = _resolve_field(fieldnames, ("cycle", "cycles"))
        sm_key = _resolve_field(fieldnames, ("sm_id", "sm"))
        warp_key = _resolve_field(fieldnames, ("warp_id", "warp"))
        addr_key = _resolve_field(fieldnames, ("address", "addr", "mem_addr"))
        op_key = _resolve_field(fieldnames, ("op", "opcode"))
        status_key = _resolve_field(fieldnames, ("l1_status", "status"))

        required = {"cycle": cycle_key, "sm_id": sm_key, "warp_id": warp_key, "address": addr_key}
        missing = [name for name, key in required.items() if key is None]
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(missing)}")

        if sample_every < 1:
            sample_every = 1

        for idx, row in enumerate(reader):
            if sample_every > 1 and idx % sample_every != 0:
                continue

            op = ""
            if op_key:
                op = row.get(op_key, "").strip().upper()
                if op_filter and op not in op_filter:
                    continue

            cycle = _parse_int(row.get(cycle_key))
            sm = _parse_int(row.get(sm_key))
            warp = _parse_int(row.get(warp_key))
            addr = _parse_int(row.get(addr_key))
            if cycle is None or sm is None or warp is None or addr is None:
                continue

            cycles.append(cycle)
            sms.append(sm)
            warps.append(warp)
            addrs.append(addr)
            ops.append(op)
            if status_key:
                status_value = row.get(status_key, "").strip()
                if status_value.upper() == "RESERVATION_FAIL":
                    continue
                statuses.append(status_value or "UNKNOWN")
            else:
                statuses.append("UNKNOWN")

            if max_rows > 0 and len(cycles) >= max_rows:
                break

    return {
        "cycle": np.asarray(cycles, dtype=np.int64),
        "sm": np.asarray(sms, dtype=np.int64),
        "warp": np.asarray(warps, dtype=np.int64),
        "addr": np.asarray(addrs, dtype=np.int64),
        "op": np.asarray(ops, dtype=object),
        "status": np.asarray(statuses, dtype=object),
    }


def build_x(sm, warp, layout):
    if layout == "grid":
        max_sm = int(np.max(sm)) if sm.size else 0
        max_warp = int(np.max(warp)) if warp.size else 0
        warp_stride = max_warp + 1
        x = sm * warp_stride + warp
        return x, warp_stride, max_sm
    pairs = list(zip(sm.tolist(), warp.tolist()))
    unique_pairs = sorted(set(pairs))
    mapping = {pair: idx for idx, pair in enumerate(unique_pairs)}
    x = np.asarray([mapping[pair] for pair in pairs], dtype=np.int64)
    return x, None, None


def auto_figure_size(
    data,
    x_layout,
    warp_stride,
    max_sm,
    max_sm_ticks,
    min_width,
    min_height,
    max_width,
    max_height,
):
    point_count = int(data["cycle"].size)
    if x_layout == "grid" and warp_stride and max_sm is not None:
        sm_count = max_sm + 1
        if max_sm_ticks and max_sm_ticks > 0:
            tick_count = min(sm_count, max_sm_ticks)
        else:
            tick_count = sm_count
        width_target = 8.0 + 0.4 * tick_count
    else:
        combined = (data["sm"].astype(np.int64) << 32) | data["warp"].astype(np.int64)
        pair_count = int(np.unique(combined).size) if combined.size else 1
        if max_sm_ticks and max_sm_ticks > 0:
            tick_count = min(pair_count, max_sm_ticks)
        else:
            tick_count = pair_count
        width_target = 8.0 + 0.4 * math.sqrt(tick_count)

    height_target = 6.0 + 0.012 * math.sqrt(max(point_count, 1))

    max_width = max(max_width, min_width)
    max_height = max(max_height, min_height)
    width = max(min_width, min(max_width, width_target))
    height = max(min_height, min(max_height, height_target))
    return width, height


def transform_addresses(addr, quant, line_size, transform):
    addr = addr.astype(np.int64, copy=False)
    if quant == "line":
        if line_size <= 0:
            raise ValueError("line_size must be > 0 for line quantization")
        addr = addr // line_size
        base_label = f"Line address (line={line_size}B)"
    else:
        base_label = "Address"

    if transform == "raw":
        return addr.astype(np.float64), base_label

    min_val = int(np.min(addr)) if addr.size else 0
    max_val = int(np.max(addr)) if addr.size else 0
    if transform == "minmax":
        if max_val == min_val:
            return np.zeros_like(addr, dtype=np.float64), f"{base_label} (minmax)"
        scaled = (addr - min_val) / (max_val - min_val)
        return scaled.astype(np.float64), f"{base_label} (minmax)"

    if transform == "log":
        shifted = (addr - min_val).astype(np.float64)
        logged = np.log1p(shifted)
        if logged.size and np.max(logged) > 0:
            logged = logged / np.max(logged)
        return logged, f"{base_label} (log1p, normalized)"

    if transform == "rank":
        unique_vals = np.unique(addr)
        mapping = {val: idx for idx, val in enumerate(unique_vals)}
        ranked = np.asarray([mapping[val] for val in addr], dtype=np.float64)
        if ranked.size and np.max(ranked) > 0:
            ranked = ranked / np.max(ranked)
        return ranked, f"{base_label} (rank, normalized)"

    raise ValueError(f"Unsupported address transform: {transform}")


def build_color_mapping(color_by, data):
    if color_by == "sm":
        values = data["sm"].astype(np.float64)
        vmin = float(np.min(values)) if values.size else 0.0
        vmax = float(np.max(values)) if values.size else 1.0
        if vmin == vmax:
            vmax = vmin + 1.0
        norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
        return {
            "values": values,
            "cmap": "turbo",
            "norm": norm,
            "cbar_label": "SM id",
            "legend": None,
        }

    if color_by == "status":
        categories = sorted(set(data["status"].tolist()))
        cmap = plt.get_cmap("tab20", len(categories))
        mapping = {cat: cmap(i) for i, cat in enumerate(categories)}
        colors = [mapping[val] for val in data["status"]]
        legend = [Patch(color=mapping[cat], label=str(cat)) for cat in categories]
        return {
            "values": np.asarray(colors),
            "legend": legend,
            "legend_title": "L1 status",
            "cbar_label": None,
        }

    if color_by == "op":
        categories = sorted(set(data["op"].tolist()))
        cmap = plt.get_cmap("tab10", len(categories))
        mapping = {cat: cmap(i) for i, cat in enumerate(categories)}
        colors = [mapping[val] for val in data["op"]]
        legend = [Patch(color=mapping[cat], label=str(cat)) for cat in categories]
        return {
            "values": np.asarray(colors),
            "legend": legend,
            "legend_title": "Op",
            "cbar_label": None,
        }

    raise ValueError(f"Unsupported color_by: {color_by}")


def plot_static(
    data,
    x,
    z,
    z_label,
    out_path,
    title,
    color_info,
    marker_size,
    alpha,
    fig_width,
    fig_height,
    elev,
    azim,
    x_layout,
    warp_stride,
    max_sm,
    max_sm_ticks,
    use_tight_layout,
    label_size,
    tick_size,
    title_size,
    bbox_tight,
    bbox_pad,
    x_tick_rotation,
    x_tick_align,
    label_pad,
    tick_pad,
    x_label_pad,
    title_pad,
):
    fig = plt.figure(figsize=(fig_width, fig_height))
    ax = fig.add_subplot(111, projection="3d")
    ax.view_init(elev=elev, azim=azim)

    use_colorbar = bool(color_info.get("cmap"))
    if use_colorbar:
        ax.set_position([0.04, 0.07, 0.82, 0.88])
        cax = fig.add_axes([0.88, 0.14, 0.02, 0.72])
    else:
        ax.set_position([0.04, 0.07, 0.92, 0.88])
        cax = None

    if color_info.get("cmap"):
        scatter = ax.scatter(
            x,
            data["cycle"],
            z,
            s=marker_size,
            c=color_info["values"],
            cmap=color_info["cmap"],
            norm=color_info["norm"],
            alpha=alpha,
            linewidths=0,
        )
        cbar = fig.colorbar(scatter, cax=cax)
        cbar.set_label(color_info["cbar_label"] or "")
    else:
        scatter = ax.scatter(
            x,
            data["cycle"],
            z,
            s=marker_size,
            c=color_info["values"],
            alpha=alpha,
            linewidths=0,
        )
        legend = color_info.get("legend")
        if legend:
            ax.legend(
                handles=legend,
                title=color_info.get("legend_title", "Category"),
                loc="upper right",
            )

    x_pad = x_label_pad if x_label_pad is not None else label_pad
    ax.set_xlabel("SM/warp index", fontsize=label_size, labelpad=x_pad)
    ax.set_ylabel("Cycle", fontsize=label_size, labelpad=label_pad)
    ax.set_zlabel(z_label, fontsize=label_size, labelpad=label_pad)
    if title:
        ax.set_title(title, fontsize=title_size, pad=title_pad)
    ax.tick_params(axis="x", labelsize=tick_size, pad=tick_pad)
    ax.tick_params(axis="y", labelsize=tick_size, pad=tick_pad)
    ax.tick_params(axis="z", labelsize=tick_size, pad=tick_pad)

    if x_layout == "grid" and warp_stride:
        sm_count = max_sm + 1
        if sm_count > 0:
            step = 1
            if max_sm_ticks:
                step = max(1, math.ceil(sm_count / max_sm_ticks))
            tick_sms = list(range(0, sm_count, step))
            tick_pos = [sm * warp_stride + (warp_stride - 1) / 2 for sm in tick_sms]
            ax.set_xticks(tick_pos)
            ax.set_xticklabels(
                [f"SM{sm}" for sm in tick_sms],
                fontsize=tick_size,
                rotation=x_tick_rotation,
                ha=x_tick_align,
            )

    if use_tight_layout:
        fig.tight_layout()

    save_kwargs = {}
    if bbox_tight:
        save_kwargs["bbox_inches"] = "tight"
        save_kwargs["pad_inches"] = bbox_pad
    fig.savefig(out_path, **save_kwargs)
    print(f"Saved figure to {out_path}")


def plot_interactive(
    data,
    x,
    z,
    z_label,
    out_path,
    title,
    color_by,
    marker_size,
    alpha,
):
    try:
        import plotly.graph_objects as go
    except ImportError:
        raise SystemExit("plotly is not installed; please install it or run without --interactive.")

    if color_by == "sm":
        fig = go.Figure(
            data=[
                go.Scatter3d(
                    x=x,
                    y=data["cycle"],
                    z=z,
                    mode="markers",
                    marker=dict(
                        size=marker_size,
                        color=data["sm"],
                        colorscale="Turbo",
                        opacity=alpha,
                        colorbar=dict(title="SM id"),
                    ),
                )
            ]
        )
    elif color_by in ("status", "op"):
        fig = go.Figure()
        categories = sorted(set(data[color_by].tolist()))
        cmap = plt.get_cmap("tab20", len(categories))
        for idx, cat in enumerate(categories):
            mask = data[color_by] == cat
            color_hex = mcolors.to_hex(cmap(idx))
            fig.add_trace(
                go.Scatter3d(
                    x=x[mask],
                    y=data["cycle"][mask],
                    z=z[mask],
                    mode="markers",
                    name=str(cat),
                    marker=dict(size=marker_size, color=color_hex, opacity=alpha),
                )
            )
    else:
        raise ValueError(f"Unsupported color_by for interactive output: {color_by}")

    fig.update_layout(
        title=title or "",
        scene=dict(
            xaxis_title="SM/warp index",
            yaxis_title="Cycle",
            zaxis_title=z_label,
        ),
    )
    fig.write_html(out_path)
    print(f"Saved interactive figure to {out_path}")


def derive_out_path(csv_path, out_path, suffix, interactive):
    if out_path is None:
        out_dir = Path(__file__).resolve().parent / "output" / "3d_pattern"
        ext = "html" if interactive else "png"
        name = f"{csv_path.stem}{suffix}.{ext}"
        return out_dir / name

    ext = "html" if interactive else "png"
    if out_path.suffix.lower() != f".{ext}":
        out_path = out_path.with_suffix(f".{ext}")
    if suffix:
        out_path = out_path.with_name(f"{out_path.stem}{suffix}{out_path.suffix}")
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Plot a 3D L1 access pattern: X=(SM,warp), Y=cycle, Z=address."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("../L1cache_trace/bfs_web_l1.csv"),
        help="Path to L1 cache trace CSV.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output file path (png or html). If omitted, output/3d_pattern/ next to the script is used.",
    )
    parser.add_argument(
        "--op",
        default="LD",
        help="Comma-separated ops to include (default: LD). Example: LD,ST",
    )
    parser.add_argument(
        "--split-rw",
        action="store_true",
        help="Output separate plots for LD and ST (ignores --op).",
    )
    parser.add_argument(
        "--addr-quant",
        choices=("raw", "line"),
        default="line",
        help="Quantize address to raw or L1 line address.",
    )
    parser.add_argument(
        "--line-size",
        type=int,
        default=128,
        help="Line size in bytes when --addr-quant=line.",
    )
    parser.add_argument(
        "--addr-transform",
        choices=("raw", "minmax", "log", "rank"),
        default="minmax",
        help=(
            "Address transform after quantization: raw, minmax (preserve gaps), "
            "log (compress), or rank (max compression)."
        ),
    )
    parser.add_argument(
        "--color-by",
        choices=("sm", "status", "op"),
        default="sm",
        help="Color points by SM id, L1 status, or op type.",
    )
    parser.add_argument(
        "--sample-every",
        type=int,
        default=1,
        help="Keep every Nth row (default: 1, no sampling).",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=0,
        help="Stop after this many rows (0 = no limit).",
    )
    parser.add_argument(
        "--x-layout",
        choices=("grid", "dense"),
        default="grid",
        help="X axis layout: grid keeps SM blocks, dense packs used (SM,warp) only.",
    )
    parser.add_argument(
        "--max-sm-ticks",
        type=int,
        default=16,
        help="Maximum number of SM tick labels on the X axis.",
    )
    parser.add_argument("--marker-size", type=float, default=2.0)
    parser.add_argument("--alpha", type=float, default=0.6)
    parser.add_argument(
        "--fig-width",
        type=float,
        default=12.0,
        help="Figure width in inches (minimum when --auto-size is enabled).",
    )
    parser.add_argument(
        "--fig-height",
        type=float,
        default=8.0,
        help="Figure height in inches (minimum when --auto-size is enabled).",
    )
    auto_size_group = parser.add_mutually_exclusive_group()
    auto_size_group.add_argument(
        "--auto-size",
        dest="auto_size",
        action="store_true",
        default=True,
        help="Auto scale the figure size based on trace size (default: enabled).",
    )
    auto_size_group.add_argument(
        "--no-auto-size",
        dest="auto_size",
        action="store_false",
        help="Disable auto scaling and use --fig-width/--fig-height as-is.",
    )
    parser.add_argument(
        "--max-fig-width",
        type=float,
        default=48.0,
        help="Upper bound for auto-scaled figure width (inches).",
    )
    parser.add_argument(
        "--max-fig-height",
        type=float,
        default=20.0,
        help="Upper bound for auto-scaled figure height (inches).",
    )
    layout_group = parser.add_mutually_exclusive_group()
    layout_group.add_argument(
        "--tight-layout",
        dest="tight_layout",
        action="store_true",
        default=False,
        help="Enable matplotlib tight_layout (may warn for dense 3D plots).",
    )
    layout_group.add_argument(
        "--no-tight-layout",
        dest="tight_layout",
        action="store_false",
        help="Disable tight_layout and use fixed margins (default).",
    )
    parser.add_argument(
        "--label-size",
        type=float,
        default=12.0,
        help="Axis label font size.",
    )
    parser.add_argument(
        "--tick-size",
        type=float,
        default=11.0,
        help="Tick label font size.",
    )
    parser.add_argument(
        "--title-size",
        type=float,
        default=20.0,
        help="Title font size.",
    )
    parser.add_argument(
        "--x-tick-rotation",
        type=float,
        default=28.0,
        help="Rotation angle for X tick labels (degrees).",
    )
    parser.add_argument(
        "--x-tick-align",
        choices=("left", "center", "right"),
        default="right",
        help="Horizontal alignment for rotated X tick labels.",
    )
    parser.add_argument(
        "--label-pad",
        type=float,
        default=12.0,
        help="Padding between axis labels and the axes.",
    )
    parser.add_argument(
        "--tick-pad",
        type=float,
        default=8.0,
        help="Padding between tick labels and the axes.",
    )
    parser.add_argument(
        "--x-label-pad",
        type=float,
        default=25.0,
        help="Padding between the X label and the X axis.",
    )
    parser.add_argument(
        "--title-pad",
        type=float,
        default=1.0,
        help="Padding between the title and the axes.",
    )
    bbox_group = parser.add_mutually_exclusive_group()
    bbox_group.add_argument(
        "--bbox-tight",
        dest="bbox_tight",
        action="store_true",
        default=True,
        help="Trim outer whitespace when saving (default: enabled).",
    )
    bbox_group.add_argument(
        "--no-bbox-tight",
        dest="bbox_tight",
        action="store_false",
        help="Disable whitespace trimming when saving.",
    )
    parser.add_argument(
        "--bbox-pad",
        type=float,
        default=0.2,
        help="Padding (inches) when --bbox-tight is enabled.",
    )
    parser.add_argument("--view-elev", type=float, default=20.0)
    parser.add_argument("--view-azim", type=float, default=-60.0)
    parser.add_argument(
        "--title",
        default=None,
        help="Custom plot title. Defaults to the CSV filename.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Write an interactive HTML plot (requires plotly).",
    )
    args = parser.parse_args()

    if not args.csv.is_file():
        raise SystemExit(f"Input CSV not found: {args.csv}")

    def run_for_ops(ops, suffix):
        data = load_l1_trace(args.csv, ops, args.sample_every, args.max_rows)
        if data["cycle"].size == 0:
            print("No data to plot after filtering.")
            return

        x, warp_stride, max_sm = build_x(data["sm"], data["warp"], args.x_layout)
        z, z_label = transform_addresses(
            data["addr"], args.addr_quant, args.line_size, args.addr_transform
        )
        color_info = build_color_mapping(args.color_by, data)

        out_path = derive_out_path(args.csv, args.out, suffix, args.interactive)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        title = args.title or f"{args.csv.name} L1 access pattern"
        if args.interactive:
            plot_interactive(
                data,
                x,
                z,
                z_label,
                out_path,
                title,
                args.color_by,
                args.marker_size,
                args.alpha,
            )
        else:
            fig_width = args.fig_width
            fig_height = args.fig_height
            if args.auto_size:
                fig_width, fig_height = auto_figure_size(
                    data,
                    args.x_layout,
                    warp_stride,
                    max_sm,
                    args.max_sm_ticks,
                    args.fig_width,
                    args.fig_height,
                    args.max_fig_width,
                    args.max_fig_height,
                )
            plot_static(
                data,
                x,
                z,
                z_label,
                out_path,
                title,
                color_info,
                args.marker_size,
                args.alpha,
                fig_width,
                fig_height,
                args.view_elev,
                args.view_azim,
                args.x_layout,
                warp_stride,
                max_sm,
                args.max_sm_ticks,
                args.tight_layout,
                args.label_size,
                args.tick_size,
                args.title_size,
                args.bbox_tight,
                args.bbox_pad,
                args.x_tick_rotation,
                args.x_tick_align,
                args.label_pad,
                args.tick_pad,
                args.x_label_pad,
                args.title_pad,
            )

    base_suffix = "_3d"
    if args.split_rw:
        run_for_ops({"LD"}, f"_ld{base_suffix}")
        run_for_ops({"ST"}, f"_st{base_suffix}")
    else:
        op_filter = _parse_ops(args.op)
        suffix = base_suffix if args.out is None else ""
        run_for_ops(op_filter, suffix)


if __name__ == "__main__":
    main()
