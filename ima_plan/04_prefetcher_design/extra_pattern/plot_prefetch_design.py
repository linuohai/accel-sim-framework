#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


plt.rcParams["svg.fonttype"] = "none"
plt.rcParams["axes.spines.top"] = False
plt.rcParams["axes.spines.right"] = False

WORKLOAD_ORDER = [
    "bfs_ima_small",
    "sssp_ima_small",
    "spmv_ima_small",
    "cc_ima_small",
    "bc_ima_small_forward",
    "bc_ima_small_reverse",
]

DISPLAY_NAME = {
    "bfs_ima_small": "BFS",
    "sssp_ima_small": "SSSP",
    "spmv_ima_small": "SpMV",
    "cc_ima_small": "CC",
    "bc_ima_small_forward": "BC-F",
    "bc_ima_small_reverse": "BC-R",
}

STATUS_COLORS = {
    "MISS": "#c44536",
    "HIT_RESERVED": "#f6b93b",
    "MSHR_HIT": "#8854d0",
    "HIT": "#2d98da",
    "RESFAIL": "#6c5ce7",
    "UNKNOWN": "#7f8c8d",
}


def parse_int(text: str) -> int | None:
    raw = (text or "").strip()
    return int(raw) if raw else None


def parse_float(text: str) -> float:
    raw = (text or "").strip()
    return float(raw) if raw else 0.0


def load_csv_row(path: Path) -> dict[str, str]:
    with path.open(newline="") as handle:
        return next(csv.DictReader(handle))


def load_role_rows(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            rows[row["scope"]] = row
    return rows


def load_event_status_counts(path: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row["role"] == "data_load":
                counts[row["first_status"]] += 1
    return counts


def load_chain_distributions(path: Path) -> dict[str, list[int]]:
    values = {
        "index_issue_to_refill": [],
        "refill_to_data_issue": [],
        "data_issue_to_refill": [],
    }
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("complete_flag") != "1":
                continue
            for key in values:
                parsed = parse_int(row.get(key, ""))
                if parsed is not None:
                    values[key].append(parsed)
    return values


def build_records(root: Path, scheduler_label: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for workload in WORKLOAD_ORDER:
        workload_dir = root / workload
        summary_path = workload_dir / f"ima_chain_summary_{scheduler_label}.csv"
        role_path = workload_dir / f"ima_window_role_breakdown_{scheduler_label}.csv"
        l2_summary_path = workload_dir / f"ima_l2_window_summary_{scheduler_label}.csv"
        chain_path = workload_dir / f"ima_chain_latency_{scheduler_label}.csv"
        events_path = workload_dir / f"warp_load_events_{scheduler_label}.csv"
        if not (summary_path.exists() and role_path.exists() and chain_path.exists() and events_path.exists()):
            continue

        summary = load_csv_row(summary_path)
        role_rows = load_role_rows(role_path)
        data_row = role_rows["data_load"]
        index_row = role_rows["index_load"]
        l2_rows = load_role_rows(l2_summary_path) if l2_summary_path.exists() else {}
        data_l2_row = l2_rows.get("data_load", {})
        index_l2_row = l2_rows.get("index_load", {})
        chain_count = int(summary["chain_count"])
        complete_chain_count = int(summary["complete_chain_count"])
        orphan_index_count = int(summary["orphan_index_count"])
        orphan_data_count = int(summary["orphan_data_count"])
        record: dict[str, object] = {
            "workload": workload,
            "display_name": DISPLAY_NAME.get(workload, workload),
            "window_start": int(summary["window_start"]),
            "window_end": int(summary["window_end"]),
            "chain_count": chain_count,
            "complete_chain_count": complete_chain_count,
            "complete_ratio": (complete_chain_count / chain_count) if chain_count else 0.0,
            "orphan_index_count": orphan_index_count,
            "orphan_index_ratio": (orphan_index_count / chain_count) if chain_count else 0.0,
            "orphan_data_count": orphan_data_count,
            "orphan_data_ratio": (orphan_data_count / chain_count) if chain_count else 0.0,
            "fill_observed": int(summary["fill_observed"]),
            "bad_order_count": int(summary["bad_order_count"]),
            "index_issue_to_refill_p50": parse_float(summary["index_issue_to_refill_p50"]),
            "index_issue_to_refill_p90": parse_float(summary["index_issue_to_refill_p90"]),
            "index_issue_to_refill_p99": parse_float(summary["index_issue_to_refill_p99"]),
            "refill_to_data_issue_p50": parse_float(summary["refill_to_data_issue_p50"]),
            "refill_to_data_issue_p90": parse_float(summary["refill_to_data_issue_p90"]),
            "refill_to_data_issue_p99": parse_float(summary["refill_to_data_issue_p99"]),
            "index_issue_to_data_issue_p50": parse_float(summary["index_issue_to_data_issue_p50"]),
            "index_issue_to_data_issue_p90": parse_float(summary["index_issue_to_data_issue_p90"]),
            "index_issue_to_data_issue_p99": parse_float(summary["index_issue_to_data_issue_p99"]),
            "data_issue_to_refill_p50": parse_float(summary["data_issue_to_refill_p50"]),
            "data_issue_to_refill_p90": parse_float(summary["data_issue_to_refill_p90"]),
            "data_issue_to_refill_p99": parse_float(summary["data_issue_to_refill_p99"]),
            "index_access_count": int(index_row["access_count"]),
            "index_hit_rate": parse_float(index_row["hit_rate"]),
            "index_hit_reserved_rate": (
                int(index_row["hit_reserved_count"]) / int(index_row["access_count"])
                if int(index_row["access_count"])
                else 0.0
            ),
            "index_miss_rate": parse_float(index_row["miss_like_rate"]),
            "data_access_count": int(data_row["access_count"]),
            "data_hit_rate": parse_float(data_row["hit_rate"]),
            "data_hit_reserved_rate": (
                int(data_row["hit_reserved_count"]) / int(data_row["access_count"])
                if int(data_row["access_count"])
                else 0.0
            ),
            "data_miss_rate": parse_float(data_row["miss_like_rate"]),
            "index_l2_access_count": int(index_l2_row["access_count"]) if index_l2_row else 0,
            "index_l2_hit_path_rate": parse_float(index_l2_row.get("l2_hit_path_rate", "0")),
            "index_l2_miss_path_rate": parse_float(index_l2_row.get("l2_miss_path_rate", "0")),
            "index_l2_hbm_bw_GBps": parse_float(index_l2_row.get("avg_hbm_bw_GBps", "0")),
            "index_l2_hbm_occupancy": parse_float(index_l2_row.get("avg_hbm_occupancy", "0")),
            "index_l2_sm_alu_utilization": parse_float(index_l2_row.get("avg_sm_alu_utilization", "0")),
            "data_l2_access_count": int(data_l2_row["access_count"]) if data_l2_row else 0,
            "data_l2_hit_path_rate": parse_float(data_l2_row.get("l2_hit_path_rate", "0")),
            "data_l2_miss_path_rate": parse_float(data_l2_row.get("l2_miss_path_rate", "0")),
            "data_l2_hbm_bw_GBps": parse_float(data_l2_row.get("avg_hbm_bw_GBps", "0")),
            "data_l2_hbm_occupancy": parse_float(data_l2_row.get("avg_hbm_occupancy", "0")),
            "data_l2_sm_alu_utilization": parse_float(data_l2_row.get("avg_sm_alu_utilization", "0")),
            "chain_path": chain_path,
            "events_path": events_path,
        }
        records.append(record)
    return records


def write_plot_summary(path: Path, records: list[dict[str, object]]) -> None:
    fieldnames = [
        "workload",
        "display_name",
        "window_start",
        "window_end",
        "chain_count",
        "complete_chain_count",
        "complete_ratio",
        "orphan_index_count",
        "orphan_index_ratio",
        "orphan_data_count",
        "orphan_data_ratio",
        "fill_observed",
        "bad_order_count",
        "index_issue_to_refill_p50",
        "index_issue_to_refill_p90",
        "index_issue_to_refill_p99",
        "refill_to_data_issue_p50",
        "refill_to_data_issue_p90",
        "refill_to_data_issue_p99",
        "index_issue_to_data_issue_p50",
        "index_issue_to_data_issue_p90",
        "index_issue_to_data_issue_p99",
        "data_issue_to_refill_p50",
        "data_issue_to_refill_p90",
        "data_issue_to_refill_p99",
        "index_access_count",
        "index_hit_rate",
        "index_hit_reserved_rate",
        "index_miss_rate",
        "data_access_count",
        "data_hit_rate",
        "data_hit_reserved_rate",
        "data_miss_rate",
        "index_l2_access_count",
        "index_l2_hit_path_rate",
        "index_l2_miss_path_rate",
        "index_l2_hbm_bw_GBps",
        "index_l2_hbm_occupancy",
        "index_l2_sm_alu_utilization",
        "data_l2_access_count",
        "data_l2_hit_path_rate",
        "data_l2_miss_path_rate",
        "data_l2_hbm_bw_GBps",
        "data_l2_hbm_occupancy",
        "data_l2_sm_alu_utilization",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({key: record[key] for key in fieldnames})


def plot_latency_overview(records: list[dict[str, object]], out_path: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.8), sharey=True, constrained_layout=True)
    metric_specs = [
        ("index_issue_to_refill", "Index Miss Wait", "#3867d6"),
        ("refill_to_data_issue", "Intra-chain Gap", "#20bf6b"),
        ("data_issue_to_refill", "Data Miss Wait", "#eb3b5a"),
    ]
    y = list(range(len(records)))
    labels = [record["display_name"] for record in records]
    legend_handles = [
        Line2D([0], [0], color="black", marker="o", linewidth=2, label="p50"),
        Line2D([0], [0], color="black", marker="s", linewidth=2, linestyle="--", label="p90"),
    ]
    for ax, (prefix, title, color) in zip(axes, metric_specs):
        p50_key = f"{prefix}_p50"
        p90_key = f"{prefix}_p90"
        x_min = min(max(float(record[p50_key]), 1.0) for record in records) * 0.7
        x_max = max(float(record[p90_key]) for record in records) * 1.35
        for idx, record in enumerate(records):
            p50 = max(float(record[p50_key]), 1.0)
            p90 = max(float(record[p90_key]), 1.0)
            ax.plot([p50, p90], [idx, idx], color=color, linewidth=2.6, alpha=0.85)
            ax.scatter([p50], [idx], color=color, s=42, zorder=3)
            ax.scatter([p90], [idx], color=color, marker="s", s=36, zorder=3)
        ax.set_title(title)
        ax.set_xscale("log")
        ax.set_xlim(max(x_min, 1), x_max)
        ax.grid(axis="x", linestyle=":", alpha=0.35)
        ax.set_xlabel("cycles")
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(labels)
    axes[0].invert_yaxis()
    axes[0].set_ylabel("Workload / Phase")
    axes[-1].legend(handles=legend_handles, loc="lower right", frameon=False)
    fig.suptitle("IMA Window Latency Overview", fontsize=13, y=1.02)
    fig.savefig(out_path, format=out_path.suffix.lstrip("."))
    plt.close(fig)


def plot_window_vs_cost(records: list[dict[str, object]], out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.8, 5.2), constrained_layout=True)
    x = [max(float(record["refill_to_data_issue_p50"]), 1.0) for record in records]
    y = [float(record["data_issue_to_refill_p50"]) for record in records]
    sizes = [60 + float(record["chain_count"]) * 0.08 for record in records]
    colors = [float(record["data_miss_rate"]) for record in records]
    scatter = ax.scatter(x, y, c=colors, s=sizes, cmap="YlOrRd", edgecolor="black", linewidth=0.6)
    for xi, yi, record in zip(x, y, records):
        ax.annotate(record["display_name"], (xi, yi), xytext=(6, 5), textcoords="offset points", fontsize=9)
    ax.set_xscale("log")
    ax.grid(linestyle=":", alpha=0.35)
    ax.set_xlabel("refill_to_data_issue p50 (cycles)")
    ax.set_ylabel("data_issue_to_refill p50 (cycles)")
    ax.set_title("Prefetch Window vs Data-Miss Cost")
    colorbar = fig.colorbar(scatter, ax=ax, pad=0.02)
    colorbar.set_label("data miss rate")
    fig.savefig(out_path, format=out_path.suffix.lstrip("."))
    plt.close(fig)


def plot_index_vs_data_pressure(records: list[dict[str, object]], out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9.8, 4.8), constrained_layout=True)
    x = list(range(len(records)))
    width = 0.34
    index_miss = [float(record["index_miss_rate"]) for record in records]
    data_miss = [float(record["data_miss_rate"]) for record in records]
    index_reserved = [float(record["index_hit_reserved_rate"]) for record in records]
    data_reserved = [float(record["data_hit_reserved_rate"]) for record in records]
    ax.bar([i - width / 2 for i in x], index_miss, width, label="index miss rate", color="#4b7bec")
    ax.bar([i + width / 2 for i in x], data_miss, width, label="data miss rate", color="#eb3b5a")
    ax2 = ax.twinx()
    ax2.plot(x, index_reserved, color="#f7b731", marker="o", linewidth=2.0, label="index hit_reserved rate")
    ax2.plot(x, data_reserved, color="#a55eea", marker="s", linewidth=2.0, linestyle="--", label="data hit_reserved rate")
    ax.set_xticks(x)
    ax.set_xticklabels([record["display_name"] for record in records])
    ax.set_ylim(0, 1.05)
    all_reserved = index_reserved + data_reserved
    ax2.set_ylim(0, max(all_reserved + [0.1]) * 1.25)
    ax.set_ylabel("miss rate")
    ax2.set_ylabel("hit_reserved rate")
    ax.set_title("Index vs Data Pressure")
    ax.grid(axis="y", linestyle=":", alpha=0.35)
    handles1, labels1 = ax.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(handles1 + handles2, labels1 + labels2, loc="upper left", frameon=False)
    fig.savefig(out_path, format=out_path.suffix.lstrip("."))
    plt.close(fig)


def plot_chain_completeness(records: list[dict[str, object]], out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.2, 4.6), constrained_layout=True)
    y = list(range(len(records)))
    complete = [float(record["complete_ratio"]) for record in records]
    orphan_index = [float(record["orphan_index_ratio"]) for record in records]
    orphan_data = [float(record["orphan_data_ratio"]) for record in records]
    ax.barh(y, complete, color="#20bf6b", label="complete")
    ax.barh(y, orphan_index, left=complete, color="#3867d6", label="orphan index")
    left2 = [a + b for a, b in zip(complete, orphan_index)]
    ax.barh(y, orphan_data, left=left2, color="#eb3b5a", label="orphan data")
    ax.set_yticks(y)
    ax.set_yticklabels([record["display_name"] for record in records])
    ax.invert_yaxis()
    ax.set_xlim(0, 1.0)
    ax.set_xlabel("fraction of recovered chains")
    ax.set_title("Chain Completeness Overview")
    ax.grid(axis="x", linestyle=":", alpha=0.35)
    ax.legend(loc="lower right", frameon=False)
    fig.savefig(out_path, format=out_path.suffix.lstrip("."))
    plt.close(fig)


def plot_l1_miss_path_breakdown(records: list[dict[str, object]], out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 5.0), constrained_layout=True)
    x = list(range(len(records)))
    width = 0.34
    index_hit = [float(record["index_l2_hit_path_rate"]) for record in records]
    index_miss = [float(record["index_l2_miss_path_rate"]) for record in records]
    data_hit = [float(record["data_l2_hit_path_rate"]) for record in records]
    data_miss = [float(record["data_l2_miss_path_rate"]) for record in records]
    ax.bar([i - width / 2 for i in x], index_hit, width, color="#4b7bec", label="index: L2 hit-path")
    ax.bar([i - width / 2 for i in x], index_miss, width, bottom=index_hit, color="#a55eea", label="index: L2 miss-path")
    ax.bar([i + width / 2 for i in x], data_hit, width, color="#20bf6b", label="data: L2 hit-path")
    ax.bar([i + width / 2 for i in x], data_miss, width, bottom=data_hit, color="#eb3b5a", label="data: L2 miss-path")
    ax.set_xticks(x)
    ax.set_xticklabels([record["display_name"] for record in records])
    ax.set_ylim(0, 1.02)
    ax.set_ylabel("fraction of L1-miss issues")
    ax.set_title("Where Do L1 Misses Go Next?")
    ax.grid(axis="y", linestyle=":", alpha=0.35)
    ax.legend(loc="upper left", frameon=False, ncol=2)
    fig.savefig(out_path, format=out_path.suffix.lstrip("."))
    plt.close(fig)


def plot_l2_context_vs_chain_cost(records: list[dict[str, object]], out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.0, 5.2), constrained_layout=True)
    x = [max(float(record["data_l2_miss_path_rate"]), 1e-4) for record in records]
    y = [float(record["data_issue_to_refill_p50"]) for record in records]
    sizes = [60 + float(record["chain_count"]) * 0.08 for record in records]
    colors = [float(record["data_l2_hbm_occupancy"]) for record in records]
    scatter = ax.scatter(x, y, c=colors, s=sizes, cmap="YlGnBu", edgecolor="black", linewidth=0.6)
    for xi, yi, record in zip(x, y, records):
        ax.annotate(record["display_name"], (xi, yi), xytext=(6, 5), textcoords="offset points", fontsize=9)
    ax.set_xlabel("data L1-miss -> L2 miss-path rate")
    ax.set_ylabel("data_issue_to_refill p50 (cycles)")
    ax.set_title("L2 Context vs Data-Miss Cost")
    ax.grid(linestyle=":", alpha=0.35)
    cbar = fig.colorbar(scatter, ax=ax, pad=0.02)
    cbar.set_label("avg HBM occupancy during data L1 misses")
    fig.savefig(out_path, format=out_path.suffix.lstrip("."))
    plt.close(fig)


def plot_window_chain_profile(record: dict[str, object], out_path: Path) -> None:
    distributions = load_chain_distributions(Path(record["chain_path"]))
    status_counts = load_event_status_counts(Path(record["events_path"]))
    fig, axes = plt.subplots(
        2,
        1,
        figsize=(7.2, 5.8),
        gridspec_kw={"height_ratios": [3.4, 1.4]},
        constrained_layout=True,
    )

    metric_labels = [
        ("index_issue_to_refill", "idx->refill"),
        ("refill_to_data_issue", "refill->data"),
        ("data_issue_to_refill", "data->refill"),
    ]
    data = [distributions[key] for key, _ in metric_labels]
    valid_positions = [idx + 1 for idx, values in enumerate(data) if values]
    valid_data = [values for values in data if values]
    valid_labels = [label for (_, label), values in zip(metric_labels, data) if values]
    if valid_data:
        box = axes[0].boxplot(valid_data, positions=valid_positions, patch_artist=True, widths=0.55)
        palette = ["#3867d6", "#20bf6b", "#eb3b5a"]
        for patch, color in zip(box["boxes"], palette):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        for median in box["medians"]:
            median.set_color("black")
            median.set_linewidth(1.4)
        axes[0].set_xticks(valid_positions)
        axes[0].set_xticklabels(valid_labels)
        axes[0].set_yscale("log")
        axes[0].set_ylabel("cycles")
        axes[0].grid(axis="y", linestyle=":", alpha=0.35)
    axes[0].set_title(
        f"{record['display_name']} Window Chain Profile\n"
        f"complete={record['complete_chain_count']}/{record['chain_count']} "
        f"({float(record['complete_ratio']):.1%})"
    )

    total = sum(status_counts.values()) or 1
    left = 0.0
    for status in ["MISS", "HIT_RESERVED", "HIT", "RESFAIL", "UNKNOWN"]:
        value = status_counts.get(status, 0)
        if value == 0:
            continue
        frac = value / total
        axes[1].barh([0], [frac], left=[left], color=STATUS_COLORS[status], label=status)
        if frac >= 0.06:
            axes[1].text(left + frac / 2, 0, f"{status}\n{frac:.0%}", ha="center", va="center", fontsize=8)
        left += frac
    axes[1].set_xlim(0, 1.0)
    axes[1].set_yticks([])
    axes[1].set_xlabel("data_load issue share")
    axes[1].grid(axis="x", linestyle=":", alpha=0.35)
    axes[1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.28), ncol=5, frameon=False)
    fig.savefig(out_path, format=out_path.suffix.lstrip("."))
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot workload-level prefetch design figures from small IMA windows")
    parser.add_argument("--root", required=True, type=Path, help="Root directory containing per-workload outputs")
    parser.add_argument("--scheduler-label", default="lrr", help="Scheduler label suffix used in filenames")
    parser.add_argument("--format", default="svg", choices=["svg", "png", "pdf"], help="Output figure format")
    args = parser.parse_args()

    records = build_records(args.root, args.scheduler_label)
    if not records:
        raise SystemExit("No workload records found")

    figures_dir = args.root / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.root / f"prefetch_plot_summary_{args.scheduler_label}.csv"
    write_plot_summary(summary_path, records)

    suffix = args.format
    plot_latency_overview(records, figures_dir / f"prefetch_latency_overview.{suffix}")
    plot_window_vs_cost(records, figures_dir / f"prefetch_window_vs_cost.{suffix}")
    plot_index_vs_data_pressure(records, figures_dir / f"index_vs_data_pressure.{suffix}")
    plot_chain_completeness(records, figures_dir / f"chain_completeness_overview.{suffix}")
    plot_l1_miss_path_breakdown(records, figures_dir / f"l1_miss_path_breakdown.{suffix}")
    plot_l2_context_vs_chain_cost(records, figures_dir / f"l2_context_vs_chain_cost.{suffix}")
    for record in records:
        plot_window_chain_profile(record, figures_dir / f"window_chain_profile_{record['workload']}.{suffix}")

    print(f"Saved: {summary_path}")
    print(f"Saved figures under: {figures_dir}")


if __name__ == "__main__":
    main()
