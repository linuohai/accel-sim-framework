#!/usr/bin/env python3
"""Extract GRASP effectiveness metrics for the 28 paper workloads into JSON.

Parses baseline and GRASP simulation logs plus stall_reason_breakdown CSVs,
then emits a single ``effectiveness_data.json`` with:

  - Baseline IPC / cycles / L1D / IMA demand / stall breakdown
  - GRASP IPC / cycles / L1D / IMA demand / stall breakdown
  - GRASP-only: funnel, storage peaks, effect (pf_useful/useless/late),
    rfail breakdown, IMA timeliness
  - Derived: speedup %, cycle reduction %, IMA miss reduction %,
    MEM_WAIT stall reduction %, CT reuse ratio, etc.

Usage:
    python extract_effectiveness.py                      # all 28
    python extract_effectiveness.py --workloads bfs_web_sym sssp_web_sym
    python extract_effectiveness.py --output /tmp/out.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "ima_plan/07_paper_outline/plot_style"))
from workload_names import ORDERED_28, SHORT_NAME  # noqa: E402

LOG_DIR = REPO / "result" / "log"
STALL_DIR = REPO / "result" / "issue_trace" / "stall_reason_pc_stats"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "effectiveness_data.json"


# ── LOG_MAPPING: workload_key -> (baseline_log_name, grasp_log_name) ──────────
LOG_MAPPING: Dict[str, Tuple[str, str]] = {
    # cit-Patents (directed for BFS/SSSP/BC, sym for CC/SpMV/VC)
    "bfs_cit_dir":     ("bfs_cit_dir_baseline",  "bfs_cit_dir_g_D5b"),
    "sssp_cit_dir":    ("sssp_cit_dir_baseline", "sssp_cit_dir_g_D5b"),
    "bc_cit_dir":      ("bc_cit_dir_baseline",   "bc_cit_dir_g_D5b"),
    "cc_cit_sym":      ("cc_cit_sym_baseline",   "cc_cit_sym_g_D5b"),    # newer log w/ IMA_DEMAND
    "spmv_cit_sym":    ("spmv_cit_sym_baseline", "spmv_cit_sym_g_D5b"),  # newer log w/ IMA_DEMAND
    "vc_cit_sym":      ("vc_ima_high_baseline",  "vc_cit_sym_g_D5b"),
    # web-Google (all sym)
    "bfs_web_sym":     ("bfs_web_sym_baseline",  "bfs_web_sym_g_D5b"),   # newer log w/ IMA_DEMAND
    "sssp_web_sym":    ("sssp_web_sym_baseline", "sssp_web_sym_g_D5b"),  # newer log w/ IMA_DEMAND
    "bc_web_sym":      ("bc_web_sym_baseline",   "bc_web_sym_g_D5b"),    # newer log w/ IMA_DEMAND
    "cc_web_sym":      ("cc_web_sym_baseline",   "cc_web_sym_g_D5b"),    # newer log w/ IMA_DEMAND
    "spmv_web_sym":    ("spmv_web_sym_baseline", "spmv_web_sym_g_D5b"),  # newer log w/ IMA_DEMAND
    "vc_web_sym":      ("vc_ima_med_baseline",   "vc_web_sym_g_D5b"),
    # flickr (all sym, no VC)
    "bfs_flickr_sym":  ("bfs_flickr_sym_baseline",  "bfs_flickr_sym_g_D5b"),
    "sssp_flickr_sym": ("sssp_flickr_sym_baseline", "sssp_flickr_sym_g_D5b"),
    "bc_flickr_sym":   ("bc_flickr_sym_baseline",   "bc_flickr_sym_g_D5b"),
    "cc_flickr_sym":   ("cc_flickr_baseline",       "cc_flickr_sym_g_D5b"),
    "spmv_flickr_sym": ("spmv_flickr_baseline",     "spmv_flickr_sym_g_D5b"),
    # roadNet-CA (all sym)
    "bfs_road_sym":    ("bfs_road_sym_baseline",    "bfs_road_sym_g_D5b"),
    "sssp_road_sym":   ("sssp_road_sym_baseline",   "sssp_road_sym_g_D5b"),
    "bc_road_sym":     ("bc_road_sym_baseline",     "bc_road_sym_g_D5b"),
    "cc_road_sym":     ("cc_road_baseline",         "cc_road_sym_g_D5b"),
    "spmv_road_sym":   ("spmv_road_baseline",       "spmv_road_sym_g_D5b"),
    "vc_road_sym":     ("vc_road_sym_baseline_v2",  "vc_road_sym_g_D5b"),
    # soc-LiveJournal1
    "bfs_socLJ_sym":   ("bfs_socLJ_sym_baseline",   "bfs_socLJ_sym_g_D5b"),
    "spmv_socLJ_sym":  ("spmv_socLJ_baseline",      "spmv_socLJ_sym_g_D5b"),
    # Extended (Pannotia + LonestarGPU)
    "pann_mis_flickr": ("pann_mis_flickr_baseline_v2", "pann_mis_flickr_grasp2"),  # v2 has IMA_DEMAND
    "pann_color_eco":  ("pann_color_eco_baseline",  "pann_color_eco_grasp"),
    "ls_mst_rmat12":   ("ls_mst_rmat12_baseline",   "ls_mst_rmat12_grasp"),
}

assert set(LOG_MAPPING.keys()) == set(ORDERED_28), "LOG_MAPPING does not cover ORDERED_28"


# ── Regex (compiled once) ────────────────────────────────────────────────────
_RE_SUMMARY = re.compile(
    r"=== EXPERIMENT SUMMARY ===(?P<body>.*?)=== END SUMMARY ===", re.S
)
_RE_FINAL_IPC = re.compile(r"^final_ipc=([\d.]+)", re.M)
_RE_FINAL_CYCLES = re.compile(r"^final_cycles=(\d+)", re.M)
_RE_STATUS = re.compile(r"^status=(\w+)", re.M)
_RE_KERNELS_EXP = re.compile(r"^expected_kernels=(\d+)", re.M)
_RE_KERNELS_DONE = re.compile(r"^completed_kernels=(\d+)", re.M)

_RE_OLD_IPC = re.compile(r"gpu_tot_ipc\s*=\s*([\d.]+)")
_RE_OLD_CYCLE = re.compile(r"gpu_tot_sim_cycle\s*=\s*(\d+)")

_RE_L1D_MISS = re.compile(r"^\s*L1D_total_cache_misses\s*=\s*(\d+)", re.M)
_RE_L1D_PHIT = re.compile(r"^\s*L1D_total_cache_pending_hits\s*=\s*(\d+)", re.M)

_RE_IMA_DEMAND = re.compile(
    r"IMA_DEMAND:\s*"
    r"total_reads=(\d+)\s+total_misses=(\d+)\s+"
    r"index_reads=(\d+)\s+index_hits=(\d+)\s+index_hit_reserved=(\d+)\s+index_misses=(\d+)\s+"
    r"data_reads=(\d+)\s+data_hits=(\d+)\s+data_hit_reserved=(\d+)\s+data_misses=(\d+)"
)
_RE_IMA_TIMELINESS = re.compile(
    r"(?:IMA_TIMELINESS:\s*)?index=([\d.]+)%\s+data=([\d.]+)%"
)

# GRASP summary block pieces (inside EXPERIMENT SUMMARY only)
_RE_EFFECT = re.compile(
    r"effect:\s*pf_useful=(\d+)\s+pf_useless=(\d+)\s+pf_late=(\d+)"
    r"(?:\s+accuracy=([\d.]+)%)?"
)
_RE_STORAGE = re.compile(
    r"storage(?:\(max\))?:\s*"
    r"prb=(\d+)/(\d+)\(([\d.]+)%\)\s+"
    r"ct=(\d+)/(\d+)\(([\d.]+)%\)\s+"
    r"cd_fifo=(\d+)/(\d+)\(([\d.]+)%\)\s+"
    r"pf_queue_peak=(\d+)"
)
_RE_RFAIL = re.compile(
    r"rfail:\s*total=(\d+)"
    r"(?:\s+line_alloc=([\d.]+)%\s+missq=([\d.]+)%\s+mshr_entry=([\d.]+)%\s+"
    r"mshr_merge=([\d.]+)%\s+rw_pending=([\d.]+)%)?"
)
_RE_FUNNEL = re.compile(
    r"funnel:\s*idx_attempted=(\d+)\s+idx_rfail=(\d+)\(([\d.]+)%\)\s+idx_got_data=(\d+)"
    r"\s*\|\s*data_enqueued=(\d+)\s+data_throttled=(\d+)\s+data_attempted=(\d+)"
    r"\s+data_rfail=(\d+)\(([\d.]+)%\)\s+data_got_data=(\d+)"
)


def _last_int(pattern: re.Pattern, text: str) -> Optional[int]:
    matches = pattern.findall(text)
    if not matches:
        return None
    return int(matches[-1])


def _last_float(pattern: re.Pattern, text: str) -> Optional[float]:
    matches = pattern.findall(text)
    if not matches:
        return None
    return float(matches[-1])


def _parse_ima_demand(line_text: str) -> Optional[Dict[str, int]]:
    """Parse a single IMA_DEMAND line into a dict of counts."""
    m = _RE_IMA_DEMAND.search(line_text)
    if not m:
        return None
    g = m.groups()
    return {
        "total_reads": int(g[0]),
        "total_misses": int(g[1]),
        "index_reads": int(g[2]),
        "index_hits": int(g[3]),
        "index_hit_reserved": int(g[4]),
        "index_misses": int(g[5]),
        "data_reads": int(g[6]),
        "data_hits": int(g[7]),
        "data_hit_reserved": int(g[8]),
        "data_misses": int(g[9]),
    }


def extract_log_metrics(logfile: Path, is_grasp: bool) -> Optional[Dict]:
    """Parse a simulation log and return a metrics dict.

    Returns ``None`` on I/O error. Missing individual metrics become ``None``.
    """
    if not logfile.exists():
        return None
    try:
        text = logfile.read_text(errors="ignore")
    except OSError as e:
        print(f"  [error] cannot read {logfile.name}: {e}", file=sys.stderr)
        return None

    result: Dict[str, Optional[object]] = {
        "log_file": logfile.name,
        "status": None,
        "ipc": None,
        "final_cycles": None,
        "expected_kernels": None,
        "completed_kernels": None,
        "l1_misses": None,
        "l1_pending_hits": None,
        "ima_demand": None,
        "ima_timeliness": None,
    }

    # Prefer EXPERIMENT SUMMARY if present
    summary_match = _RE_SUMMARY.search(text)
    if summary_match:
        body = summary_match.group("body")
        m = _RE_STATUS.search(body)
        result["status"] = m.group(1) if m else None
        m = _RE_FINAL_IPC.search(body)
        if m:
            result["ipc"] = float(m.group(1))
        m = _RE_FINAL_CYCLES.search(body)
        if m:
            result["final_cycles"] = int(m.group(1))
        m = _RE_KERNELS_EXP.search(body)
        if m:
            result["expected_kernels"] = int(m.group(1))
        m = _RE_KERNELS_DONE.search(body)
        if m:
            result["completed_kernels"] = int(m.group(1))

        # IMA_DEMAND from summary (any occurrence in body — usually 1)
        result["ima_demand"] = _parse_ima_demand(body)

        # GRASP-only fields
        if is_grasp:
            effect_m = _RE_EFFECT.search(body)
            if effect_m:
                pf_u, pf_ul, pf_l, acc = effect_m.groups()
                result["grasp_effect"] = {
                    "pf_useful": int(pf_u),
                    "pf_useless": int(pf_ul),
                    "pf_late": int(pf_l),
                    "accuracy_pct": float(acc) if acc is not None else None,
                }
            storage_m = _RE_STORAGE.search(body)
            if storage_m:
                g = storage_m.groups()
                result["grasp_storage"] = {
                    "prb_peak": int(g[0]),
                    "prb_max": int(g[1]),
                    "prb_pct": float(g[2]),
                    "ct_peak": int(g[3]),
                    "ct_max": int(g[4]),
                    "ct_pct": float(g[5]),
                    "cd_peak": int(g[6]),
                    "cd_max": int(g[7]),
                    "cd_pct": float(g[8]),
                    "pf_queue_peak": int(g[9]),
                }
            rfail_m = _RE_RFAIL.search(body)
            if rfail_m:
                g = rfail_m.groups()
                result["grasp_rfail"] = {
                    "total": int(g[0]),
                    "line_alloc_pct": float(g[1]) if g[1] is not None else None,
                    "missq_pct": float(g[2]) if g[2] is not None else None,
                    "mshr_entry_pct": float(g[3]) if g[3] is not None else None,
                    "mshr_merge_pct": float(g[4]) if g[4] is not None else None,
                    "rw_pending_pct": float(g[5]) if g[5] is not None else None,
                }
            funnel_m = _RE_FUNNEL.search(body)
            if funnel_m:
                g = funnel_m.groups()
                idx_attempted = int(g[0])
                idx_rfail = int(g[1])
                idx_got_data = int(g[3])
                data_got_data = int(g[9])
                result["grasp_funnel"] = {
                    "idx_attempted": idx_attempted,
                    "idx_rfail": idx_rfail,
                    "idx_rfail_pct": float(g[2]),
                    "idx_got_data": idx_got_data,
                    "data_enqueued": int(g[4]),
                    "data_throttled": int(g[5]),
                    "data_attempted": int(g[6]),
                    "data_rfail": int(g[7]),
                    "data_rfail_pct": float(g[8]),
                    "data_got_data": data_got_data,
                    "end_to_end_conv_pct": (
                        (data_got_data / idx_attempted * 100.0)
                        if idx_attempted > 0
                        else None
                    ),
                }
            tml_m = _RE_IMA_TIMELINESS.search(body)
            if tml_m:
                result["ima_timeliness"] = {
                    "index_pct": float(tml_m.group(1)),
                    "data_pct": float(tml_m.group(2)),
                }
    else:
        # Old-format log: no EXPERIMENT SUMMARY. Fall back to classic stats.
        result["status"] = "COMPLETE_OLD"
        ipc = _last_float(_RE_OLD_IPC, text)
        cycles = _last_int(_RE_OLD_CYCLE, text)
        if ipc is not None:
            result["ipc"] = ipc
        if cycles is not None:
            result["final_cycles"] = cycles
        # IMA_DEMAND / timeliness may still be present in body
        all_demands = list(_RE_IMA_DEMAND.finditer(text))
        if all_demands:
            # Take the last one (cumulative at end)
            result["ima_demand"] = _parse_ima_demand(all_demands[-1].group(0))
        tml_m = list(_RE_IMA_TIMELINESS.finditer(text))
        if tml_m:
            last = tml_m[-1]
            result["ima_timeliness"] = {
                "index_pct": float(last.group(1)),
                "data_pct": float(last.group(2)),
            }

    # L1D stats are in standard GPGPU-Sim output — take last occurrence
    # (cumulative at end of final kernel)
    result["l1_misses"] = _last_int(_RE_L1D_MISS, text)
    result["l1_pending_hits"] = _last_int(_RE_L1D_PHIT, text)

    return result


def extract_stall_breakdown(log_name: str) -> Optional[Dict[str, Dict[str, float]]]:
    """Read a stall_reason_breakdown.csv and return reason -> {events, fraction}."""
    csv_path = STALL_DIR / log_name / f"{log_name}_stall_reason_breakdown.csv"
    if not csv_path.exists():
        return None
    out: Dict[str, Dict[str, float]] = {}
    try:
        with csv_path.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                reason = row.get("reason", "").strip()
                if not reason:
                    continue
                try:
                    events = int(row["stall_warp_events"])
                    frac = float(row["fraction_of_stall_warp_events"])
                except (KeyError, ValueError):
                    continue
                out[reason] = {"events": events, "fraction": frac}
    except OSError as e:
        print(f"  [warn] cannot read stall CSV {csv_path.name}: {e}", file=sys.stderr)
        return None
    return out or None


def _pct_reduction(base: Optional[float], new: Optional[float]) -> Optional[float]:
    """Return (base - new) / base * 100, or None if inputs invalid."""
    if base is None or new is None:
        return None
    if base <= 0:
        return None
    return (base - new) / base * 100.0


def compute_derived(
    baseline: Dict,
    grasp: Dict,
    base_stall: Optional[Dict],
    grasp_stall: Optional[Dict],
) -> Dict[str, Optional[float]]:
    derived: Dict[str, Optional[float]] = {}

    b_ipc = baseline.get("ipc")
    g_ipc = grasp.get("ipc")
    if b_ipc and g_ipc and b_ipc > 0:
        derived["speedup_pct"] = (g_ipc - b_ipc) / b_ipc * 100.0
    else:
        derived["speedup_pct"] = None

    b_cyc = baseline.get("final_cycles")
    g_cyc = grasp.get("final_cycles")
    derived["cycle_reduction_pct"] = _pct_reduction(b_cyc, g_cyc)

    b_ima = baseline.get("ima_demand")
    g_ima = grasp.get("ima_demand")
    if b_ima and g_ima:
        derived["ima_idx_reduction_pct"] = _pct_reduction(
            b_ima.get("index_misses"), g_ima.get("index_misses")
        )
        derived["ima_data_reduction_pct"] = _pct_reduction(
            b_ima.get("data_misses"), g_ima.get("data_misses")
        )
        b_total = (b_ima.get("index_misses") or 0) + (b_ima.get("data_misses") or 0)
        g_total = (g_ima.get("index_misses") or 0) + (g_ima.get("data_misses") or 0)
        derived["ima_total_reduction_pct"] = _pct_reduction(b_total, g_total)
    else:
        derived["ima_idx_reduction_pct"] = None
        derived["ima_data_reduction_pct"] = None
        derived["ima_total_reduction_pct"] = None

    # L1 miss reduction
    derived["l1_miss_reduction_pct"] = _pct_reduction(
        baseline.get("l1_misses"), grasp.get("l1_misses")
    )

    # MEM_WAIT stall reduction (primary target — main memory stall)
    def _events(stall: Optional[Dict], reason: str) -> Optional[int]:
        if stall and reason in stall:
            return stall[reason].get("events")
        return None

    b_mw = _events(base_stall, "MEM_WAIT")
    g_mw = _events(grasp_stall, "MEM_WAIT")
    derived["memwait_reduction_pct"] = _pct_reduction(b_mw, g_mw)

    # CT reuse per entry: pf_useful / ct_peak (how many useful prefetches per
    # tracked CT entry — a measure of storage efficiency)
    g_effect = grasp.get("grasp_effect") or {}
    g_storage = grasp.get("grasp_storage") or {}
    pf_useful = g_effect.get("pf_useful")
    ct_peak = g_storage.get("ct_peak")
    if pf_useful is not None and ct_peak is not None and ct_peak > 0:
        derived["ct_reuse_per_entry"] = pf_useful / ct_peak
    else:
        derived["ct_reuse_per_entry"] = None

    return derived


def process_workload(key: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Return (result_dict, reason_if_skipped)."""
    if key not in LOG_MAPPING:
        return None, "not in LOG_MAPPING"
    base_log_name, grasp_log_name = LOG_MAPPING[key]
    base_path = LOG_DIR / f"{base_log_name}.log"
    grasp_path = LOG_DIR / f"{grasp_log_name}.log"

    missing = []
    if not base_path.exists():
        missing.append(f"baseline log {base_path.name}")
    if not grasp_path.exists():
        missing.append(f"grasp log {grasp_path.name}")
    if missing:
        return None, "; ".join(missing)

    base_metrics = extract_log_metrics(base_path, is_grasp=False)
    grasp_metrics = extract_log_metrics(grasp_path, is_grasp=True)
    if base_metrics is None or grasp_metrics is None:
        return None, "log parse failed"

    base_stall = extract_stall_breakdown(base_log_name)
    grasp_stall = extract_stall_breakdown(grasp_log_name)

    # Attach stall breakdown into the side dicts for output
    base_out = _flatten_side(base_metrics, base_log_name, base_stall)
    grasp_out = _flatten_side(grasp_metrics, grasp_log_name, grasp_stall)

    derived = compute_derived(base_metrics, grasp_metrics, base_stall, grasp_stall)

    return {
        "short_name": SHORT_NAME.get(key, key),
        "baseline": base_out,
        "grasp": grasp_out,
        "derived": derived,
    }, None


def _flatten_side(
    metrics: Dict, log_name: str, stall: Optional[Dict]
) -> Dict:
    """Assemble the baseline/grasp side of the output dict."""
    ima = metrics.get("ima_demand") or {}
    out: Dict[str, object] = {
        "log_file": log_name,
        "status": metrics.get("status"),
        "ipc": metrics.get("ipc"),
        "final_cycles": metrics.get("final_cycles"),
        "expected_kernels": metrics.get("expected_kernels"),
        "completed_kernels": metrics.get("completed_kernels"),
        "l1_misses": metrics.get("l1_misses"),
        "l1_pending_hits": metrics.get("l1_pending_hits"),
        "ima_total_reads": ima.get("total_reads"),
        "ima_total_misses": ima.get("total_misses"),
        "ima_idx_reads": ima.get("index_reads"),
        "ima_idx_hits": ima.get("index_hits"),
        "ima_idx_hit_reserved": ima.get("index_hit_reserved"),
        "ima_idx_misses": ima.get("index_misses"),
        "ima_data_reads": ima.get("data_reads"),
        "ima_data_hits": ima.get("data_hits"),
        "ima_data_hit_reserved": ima.get("data_hit_reserved"),
        "ima_data_misses": ima.get("data_misses"),
        "ima_timeliness": metrics.get("ima_timeliness"),
        "stall_breakdown": stall,
    }
    # Pass through GRASP-specific blocks if present
    for k in ("grasp_funnel", "grasp_storage", "grasp_effect", "grasp_rfail"):
        if k in metrics:
            out[k] = metrics[k]
    return out


def _geomean(values: List[float]) -> Optional[float]:
    """Geometric mean of positive numbers. Input values in multiplicative form (e.g. 1.14 = +14%)."""
    filtered = [v for v in values if v is not None and v > 0]
    if not filtered:
        return None
    log_sum = sum(math.log(v) for v in filtered)
    return math.exp(log_sum / len(filtered))


def _mean(values: List[float]) -> Optional[float]:
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    return sum(filtered) / len(filtered)


def compute_summary(results: Dict[str, Dict]) -> Dict:
    speedups_mult = []
    cycle_reds = []
    memwait_reds = []
    ima_idx_reds = []
    ima_data_reds = []

    for entry in results.values():
        d = entry.get("derived", {}) or {}
        sp = d.get("speedup_pct")
        if sp is not None:
            speedups_mult.append(1.0 + sp / 100.0)
        if d.get("cycle_reduction_pct") is not None:
            cycle_reds.append(d["cycle_reduction_pct"])
        if d.get("memwait_reduction_pct") is not None:
            memwait_reds.append(d["memwait_reduction_pct"])
        if d.get("ima_idx_reduction_pct") is not None:
            ima_idx_reds.append(d["ima_idx_reduction_pct"])
        if d.get("ima_data_reduction_pct") is not None:
            ima_data_reds.append(d["ima_data_reduction_pct"])

    gm = _geomean(speedups_mult)
    return {
        "n_workloads_with_data": len(results),
        "geomean_speedup_pct": ((gm - 1.0) * 100.0) if gm is not None else None,
        "mean_cycle_reduction_pct": _mean(cycle_reds),
        "mean_memwait_reduction_pct": _mean(memwait_reds),
        "mean_ima_idx_reduction_pct": _mean(ima_idx_reds),
        "mean_ima_data_reduction_pct": _mean(ima_data_reds),
    }


def print_summary_table(results: Dict[str, Dict], missing: List[Tuple[str, str]]) -> None:
    print("\n=== Extraction Summary Table ===\n")
    hdr = (
        f"{'Workload':<18} {'Short':<10} {'Speedup':>9} {'CycRed':>8} "
        f"{'IdxRed':>8} {'DataRed':>8} {'MemWait':>9} {'CTreuse':>9}"
    )
    print(hdr)
    print("-" * len(hdr))
    for key in ORDERED_28:
        if key not in results:
            continue
        entry = results[key]
        d = entry.get("derived", {}) or {}
        short = entry.get("short_name", "?")
        def fmt(val, suffix="%"):
            if val is None:
                return "—"
            return f"{val:+.1f}{suffix}" if suffix == "%" else f"{val:.1f}"
        print(
            f"{key:<18} {short:<10} "
            f"{fmt(d.get('speedup_pct')):>9} "
            f"{fmt(d.get('cycle_reduction_pct')):>8} "
            f"{fmt(d.get('ima_idx_reduction_pct')):>8} "
            f"{fmt(d.get('ima_data_reduction_pct')):>8} "
            f"{fmt(d.get('memwait_reduction_pct')):>9} "
            f"{fmt(d.get('ct_reuse_per_entry'), ''):>9}"
        )
    print()
    if missing:
        print(f"Missing ({len(missing)}):")
        for k, reason in missing:
            print(f"  {k}: {reason}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--workloads",
        nargs="+",
        default=None,
        help="Subset of workload keys (default: all 28)",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output JSON path (default: {DEFAULT_OUTPUT})",
    )
    args = ap.parse_args()

    targets = args.workloads if args.workloads else list(ORDERED_28)
    # Validate
    invalid = [w for w in targets if w not in LOG_MAPPING]
    if invalid:
        print(f"ERROR: unknown workload keys: {invalid}", file=sys.stderr)
        sys.exit(2)

    print(f"Extracting data for {len(targets)} workload(s)...")
    results: Dict[str, Dict] = {}
    missing: List[Tuple[str, str]] = []

    for key in targets:
        entry, reason = process_workload(key)
        if entry is None:
            missing.append((key, reason or "unknown"))
            print(f"  [skip] {key}: {reason}")
            continue
        results[key] = entry

    summary = compute_summary(results)

    # Assemble final JSON payload. Preserve canonical order for results.
    ordered_results = {k: results[k] for k in ORDERED_28 if k in results}
    payload = {
        "workloads": ordered_results,
        "missing": [
            {"key": k, "reason": r} for (k, r) in missing
        ],
        "summary": summary,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nWrote {args.output}")

    print_summary_table(results, missing)

    print("\n=== Aggregate ===")
    for k, v in summary.items():
        if v is None:
            print(f"  {k}: —")
        elif isinstance(v, float):
            print(f"  {k}: {v:+.2f}")
        else:
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
