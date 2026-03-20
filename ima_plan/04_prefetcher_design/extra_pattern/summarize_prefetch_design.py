#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Dict, Iterable, List, Sequence, Tuple


MISS_LIKE = {"MISS"}


def percentile(values: Sequence[int], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    idx = round((len(ordered) - 1) * pct)
    return float(ordered[idx])


def parse_int(raw: str) -> int | None:
    text = (raw or "").strip()
    if not text:
        return None
    return int(text)


def role_stats(events_path: Path) -> Dict[str, Dict[str, object]]:
    rows_by_role: Dict[str, List[dict[str, str]]] = defaultdict(list)
    with events_path.open() as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows_by_role[row["role"]].append(row)

    result: Dict[str, Dict[str, object]] = {}
    for role, rows in rows_by_role.items():
        counts = Counter(row["first_status"] for row in rows)
        refill_cycles = [value for row in rows if (value := parse_int(row["issue_to_refill"])) is not None]
        sectors_per_issue = [int(row["sector_addr_count"]) for row in rows]
        total = len(rows)
        result[role] = {
            "issue_count": total,
            "hit_count": counts["HIT"],
            "hit_reserved_count": counts["HIT_RESERVED"],
            "miss_like_count": counts["MISS"],
            "resfail_count": counts["RESFAIL"],
            "unknown_count": counts["UNKNOWN"],
            "hit_rate": (counts["HIT"] / total) if total else 0.0,
            "hit_reserved_rate": (counts["HIT_RESERVED"] / total) if total else 0.0,
            "miss_like_rate": (counts["MISS"] / total) if total else 0.0,
            "service_p50": median(refill_cycles) if refill_cycles else 0.0,
            "service_p90": percentile(refill_cycles, 0.90),
            "service_max": max(refill_cycles) if refill_cycles else 0.0,
            "sector_count_p50": median(sectors_per_issue) if sectors_per_issue else 0.0,
            "sector_count_p90": percentile(sectors_per_issue, 0.90),
        }
    return result


def sector_stats(sectors_path: Path) -> Dict[str, Dict[str, float]]:
    per_issue: Dict[Tuple[str, str, str], Dict[str, int]] = {}
    total_counts: Dict[str, Counter[str]] = defaultdict(Counter)
    total_sectors: Counter[str] = Counter()

    with sectors_path.open() as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            role = row["role"]
            key = (role, row["warp_id"], row["issue_seq"])
            issue = per_issue.setdefault(key, {"total": 0, "miss_like": 0})
            issue["total"] += 1
            if row["initial_l1_status"] in MISS_LIKE:
                issue["miss_like"] += 1
                total_counts[role]["miss_like"] += 1
            total_sectors[role] += 1

    result: Dict[str, Dict[str, float]] = {}
    issue_groups: Dict[str, List[Dict[str, int]]] = defaultdict(list)
    for (role, _, _), values in per_issue.items():
        issue_groups[role].append(values)

    for role, issues in issue_groups.items():
        total = len(issues)
        partial = sum(1 for issue in issues if 0 < issue["miss_like"] < issue["total"])
        full = sum(1 for issue in issues if issue["total"] > 0 and issue["miss_like"] == issue["total"])
        result[role] = {
            "sector_miss_rate": (total_counts[role]["miss_like"] / total_sectors[role]) if total_sectors[role] else 0.0,
            "partial_miss_issue_rate": (partial / total) if total else 0.0,
            "full_miss_issue_rate": (full / total) if total else 0.0,
        }
    return result


def load_window_meta(summary_path: Path) -> dict[str, str]:
    with summary_path.open() as handle:
        reader = csv.DictReader(handle)
        return next(reader)


def focus_label(index_stats: Dict[str, object], data_stats: Dict[str, object]) -> str:
    index_miss = float(index_stats.get("miss_like_rate", 0.0))
    data_miss = float(data_stats.get("miss_like_rate", 0.0))
    data_reserved = float(data_stats.get("hit_reserved_rate", 0.0))
    if data_miss >= index_miss + 0.10 or data_reserved >= 0.10:
        return "data_load"
    if index_miss >= data_miss + 0.10:
        return "index_load"
    return "mixed"


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate workload-level prefetch design signals from warp load tables")
    parser.add_argument("--root", required=True, type=Path, help="Root directory containing per-workload outputs")
    parser.add_argument("--scheduler-label", default="lrr", help="Scheduler label suffix used in filenames")
    args = parser.parse_args()

    out_csv = args.root / f"prefetch_design_summary_{args.scheduler_label}.csv"
    out_md = args.root / f"prefetch_design_summary_{args.scheduler_label}.md"

    rows: List[List[object]] = []
    for workload_dir in sorted(path for path in args.root.iterdir() if path.is_dir()):
        workload = workload_dir.name
        events_path = workload_dir / f"warp_load_events_{args.scheduler_label}.csv"
        sectors_path = workload_dir / f"warp_load_sectors_{args.scheduler_label}.csv"
        summary_path = workload_dir / f"ima_window_summary_{args.scheduler_label}.csv"
        if not (events_path.exists() and sectors_path.exists() and summary_path.exists()):
            continue

        by_role = role_stats(events_path)
        by_sector = sector_stats(sectors_path)
        meta = load_window_meta(summary_path)
        index_stats = by_role.get("index_load", {})
        data_stats = by_role.get("data_load", {})
        index_sector = by_sector.get("index_load", {})
        data_sector = by_sector.get("data_load", {})

        rows.append(
            [
                workload,
                meta["window_start"],
                meta["window_end"],
                meta["all_ld_accesses_in_window"],
                meta["hit_rate"],
                index_stats.get("issue_count", 0),
                f"{float(index_stats.get('hit_rate', 0.0)):.4f}",
                f"{float(index_stats.get('hit_reserved_rate', 0.0)):.4f}",
                f"{float(index_stats.get('miss_like_rate', 0.0)):.4f}",
                f"{float(index_stats.get('service_p50', 0.0)):.1f}",
                f"{float(index_stats.get('service_p90', 0.0)):.1f}",
                f"{float(index_stats.get('service_max', 0.0)):.1f}",
                f"{float(index_sector.get('sector_miss_rate', 0.0)):.4f}",
                data_stats.get("issue_count", 0),
                f"{float(data_stats.get('hit_rate', 0.0)):.4f}",
                f"{float(data_stats.get('hit_reserved_rate', 0.0)):.4f}",
                f"{float(data_stats.get('miss_like_rate', 0.0)):.4f}",
                f"{float(data_stats.get('service_p50', 0.0)):.1f}",
                f"{float(data_stats.get('service_p90', 0.0)):.1f}",
                f"{float(data_stats.get('service_max', 0.0)):.1f}",
                f"{float(data_sector.get('sector_miss_rate', 0.0)):.4f}",
                f"{float(data_sector.get('partial_miss_issue_rate', 0.0)):.4f}",
                f"{float(data_sector.get('full_miss_issue_rate', 0.0)):.4f}",
                focus_label(index_stats, data_stats),
            ]
        )

    with out_csv.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "workload",
                "window_start",
                "window_end",
                "all_ld_accesses_in_window",
                "all_ld_hit_rate",
                "index_issue_count",
                "index_hit_rate",
                "index_hit_reserved_rate",
                "index_miss_like_rate",
                "index_issue_to_refill_p50",
                "index_issue_to_refill_p90",
                "index_issue_to_refill_max",
                "index_sector_miss_rate",
                "data_issue_count",
                "data_hit_rate",
                "data_hit_reserved_rate",
                "data_miss_like_rate",
                "data_issue_to_refill_p50",
                "data_issue_to_refill_p90",
                "data_issue_to_refill_max",
                "data_sector_miss_rate",
                "data_partial_miss_issue_rate",
                "data_full_miss_issue_rate",
                "suggested_focus",
            ]
        )
        writer.writerows(rows)

    with out_md.open("w") as handle:
        handle.write(f"# Prefetch Design Summary ({args.scheduler_label})\n\n")
        handle.write("聚焦字段：`data_load` 是否明显比 `index_load` 更差、`HIT_RESERVED` 是否偏高、以及 miss 是少量关键 sector 还是整条 issue 普遍 miss。\n\n")
        for row in rows:
            handle.write(
                f"- `{row[0]}`: focus={row[-1]}, "
                f"index_miss={row[8]}, data_miss={row[16]}, "
                f"data_hit_reserved={row[15]}, data_partial_miss={row[21]}, data_full_miss={row[22]}\n"
            )

    print(f"Saved: {out_csv}")
    print(f"Saved: {out_md}")


if __name__ == "__main__":
    main()
