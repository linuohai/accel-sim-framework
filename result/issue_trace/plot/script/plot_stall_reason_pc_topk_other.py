#!/usr/bin/env python3
"""
STALL reason -> top-K PC + OTHER (stacked bar).

Supported inputs:

  A) Lightweight stats (recommended; warp-event / stall_warp_events accounting)
     - stall_reason_pc_hist.csv
     - stall_reason_pc_topk_other.csv

  B) Legacy issue-trace (stall_rows + sample-PC accounting; hotspot proxy)
     - <log>_issue.csv[.gz/.zst]

For (A), the plotted metric aligns with the breakdown CSV (warp-event counts).
For (B), the plotted metric is *stall rows* keyed by STALL sample-PC and does
not strictly align with warp-event breakdown totals.

Issue-trace accounting matches the stall-breakdown script:
  - Only consume rows with event == STALL.
  - Skip STALL rows where all stall counters are zero (commonly warp=-1, pc=NA),
    because they typically mean "no candidate warp" rather than a true stall.

Outputs (single directory):
  - <out-dir>/<stem>_stall_reason_pc_counts.csv         (issue-trace cache only; reason,pc,stall_rows)
  - <out-dir>/<stem>_stall_reason_pc_topk_other.csv     (topK + OTHER summary; metric depends on input)
  - <out-dir>/<stem>_stall_reason_pc_topk_other.svg     (stacked bars)
  - <out-dir>/<stem>_stall_reason_pc_topk_other.png     (when --format png|both)
"""

from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
PLOT_DIR = SCRIPT_DIR.parent
DEFAULT_OUT_DIR = PLOT_DIR / "result" / "stall_reason_pc"

# Default ordering for known reasons.
WAIT_SPLIT_STALL_REASONS: Tuple[str, ...] = (
    "MEM_WAIT",
    "REG_WAIT",
    "IBUFFER_EMPTY",
    "WAIT_CTA_BARRIER",
    "WAIT_MEMBAR",
    "WAIT_ATOMIC",
    "WAIT_LDGSTS",
    "WAIT_DONE",
    "CONTROL_HAZARD",
    "PIPE_BUSY",
    "DUAL_ISSUE_RESTRICT",
)

# Legacy issue-trace used a single "BARRIER" bucket for all waiting() cases.
LEGACY_STALL_REASONS: Tuple[str, ...] = (
    "MEM_WAIT",
    "REG_WAIT",
    "IBUFFER_EMPTY",
    "BARRIER",
    "CONTROL_HAZARD",
    "PIPE_BUSY",
    "DUAL_ISSUE_RESTRICT",
)

# Segment colors for ranks 1..K; OTHER uses grey.
RANK_COLORS: Tuple[str, ...] = (
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
)
OTHER_COLOR = "#d0d0d0"


def _norm_header(name: str) -> str:
    return name.strip().lower()


def _safe_int(text: Optional[str]) -> int:
    if text is None:
        return 0
    s = text.strip()
    if not s or s.upper() == "NA":
        return 0
    try:
        return int(s, 0)
    except ValueError:
        try:
            return int(s)
        except ValueError:
            return 0


@dataclass(frozen=True)
class Segment:
    label: str  # pc or "OTHER"
    rank: int  # 1..K for PCs; 0 for OTHER
    count: int
    frac: float
    color: str


def _svg_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _which_any(names: Sequence[str]) -> Optional[str]:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def _read_header_fields(path: Path) -> List[str]:
    """
    Returns the first CSV header row (lower-cased field names).
    Skips leading comment lines starting with '#'.
    """
    if path.suffix.lower() in {".gz", ".zst"}:
        # Issue-trace inputs are often compressed; treat as issue-trace.
        return ["event"]

    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        while True:
            pos = handle.tell()
            line = handle.readline()
            if not line:
                raise SystemExit(f"empty csv: {path}")
            if line.lstrip().startswith("#"):
                continue
            handle.seek(pos)
            reader = csv.reader(handle)
            header = next(reader)
            return [_norm_header(name) for name in header]


def _detect_input_kind(path: Path) -> str:
    """
    Returns one of:
      - issue_trace
      - stats_hist
      - stats_topk_other
      - summary_topk_other (legacy summary CSV)
    """
    fields = set(_read_header_fields(path))
    if "event" in fields:
        return "issue_trace"
    if {"reason", "pc", "stall_warp_events"}.issubset(fields):
        return "stats_hist"
    if {"reason", "segment", "rank", "stall_warp_events"}.issubset(fields):
        return "stats_topk_other"
    if {"reason", "segment", "rank", "stall_rows"}.issubset(fields):
        return "summary_topk_other"
    raise SystemExit(f"unrecognized input CSV format: {path}")


def _issue_stem(path: Path) -> str:
    # Path.stem on "foo.csv.gz" returns "foo.csv", so peel multiple suffixes.
    name = path.name
    for ext in (".gz", ".zst"):
        if name.lower().endswith(ext):
            name = name[: -len(ext)]
            break
    if name.lower().endswith(".csv"):
        name = name[: -len(".csv")]
    return Path(name).name


def _decompress_cmd(path: Path) -> Optional[List[str]]:
    suffix = path.suffix.lower()
    if suffix == ".gz":
        gzip_bin = _which_any(["gzip"])
        if not gzip_bin:
            raise SystemExit("gzip input detected but `gzip` is not in PATH")
        return [gzip_bin, "-dc", str(path)]
    if suffix == ".zst":
        zstd_bin = _which_any(["zstd"])
        if zstd_bin:
            return [zstd_bin, "-dc", str(path)]
        try:
            import zstandard  # type: ignore  # noqa: F401
        except Exception:
            raise SystemExit(
                "zstd input detected but no decompressor is available.\n"
                "Install either:\n"
                "  - the `zstd` command (recommended), or\n"
                "  - the Python `zstandard` module.\n"
            )
        return None
    return None


def _run_awk_reason_pc_counts(issue_csv: Path, *, include_zero_counts: bool) -> Tuple[Dict[str, Dict[str, int]], Dict[str, int]]:
    """
    Returns:
      - counts_by_reason_pc: reason -> pc -> stall_rows
      - metrics: basic scan counters (STALL_ROWS_TOTAL/USED/ZERO/PC_NA)
    """
    awk_bin = _which_any(["mawk", "gawk", "awk"])
    if not awk_bin:
        raise SystemExit("no awk implementation found (need mawk/gawk/awk in PATH)")

    include_zero_flag = 1 if include_zero_counts else 0

    awk_program = rf"""
BEGIN {{
  FS = ",";
  # Avoid scientific notation for large integers.
  CONVFMT = "%.0f";
  OFMT = "%.0f";

  include_zero = {include_zero_flag};
  stall_total = 0;
  stall_used = 0;
  stall_zero = 0;
  used_pc_na = 0;

  event_i = 0;
  pc_i = 0;
  mem_i = 0;
  reg_i = 0;
  ibuf_i = 0;
  bar_i = 0;
  wcta_i = 0;
  wmembar_i = 0;
  watomic_i = 0;
  wldgsts_i = 0;
  wdone_i = 0;
  ctrl_i = 0;
  pipe_i = 0;
  dual_i = 0;
}}

function bump(reason, pc) {{
  key = reason SUBSEP pc;
  cnt[key] += 1;
}}

NR == 1 {{
  for (i = 1; i <= NF; i++) {{
    name = tolower($i);
    gsub(/\r/, "", name);
    if (name == "event") event_i = i;
    else if (name == "pc") pc_i = i;
    else if (name == "mem_wait") mem_i = i;
    else if (name == "reg_wait") reg_i = i;
    else if (name == "ibuffer_empty") ibuf_i = i;
    else if (name == "barrier") bar_i = i;
    else if (name == "wait_cta_barrier") wcta_i = i;
    else if (name == "wait_membar") wmembar_i = i;
    else if (name == "wait_atomic") watomic_i = i;
    else if (name == "wait_ldgsts") wldgsts_i = i;
    else if (name == "wait_done") wdone_i = i;
    else if (name == "control_hazard") ctrl_i = i;
    else if (name == "pipe_busy") pipe_i = i;
    else if (name == "dual_issue_restrict") dual_i = i;
  }}
  if (event_i == 0 || pc_i == 0) {{
    print "ERROR,missing required columns (need event,pc)" > "/dev/stderr";
    exit 2;
  }}
  if (mem_i == 0 || reg_i == 0 || ibuf_i == 0 || ctrl_i == 0 || pipe_i == 0 || dual_i == 0) {{
    print "ERROR,missing stall reason columns (need MEM_WAIT,REG_WAIT,IBUFFER_EMPTY,CONTROL_HAZARD,PIPE_BUSY,DUAL_ISSUE_RESTRICT)" > "/dev/stderr";
    exit 2;
  }}
  if (bar_i == 0 && wcta_i == 0 && wmembar_i == 0 && watomic_i == 0 && wldgsts_i == 0 && wdone_i == 0) {{
    print "ERROR,missing waiting columns (need either BARRIER or WAIT_*)" > "/dev/stderr";
    exit 2;
  }}
  next;
}}

{{
  if ($1 ~ /^#/) next;
  if (event_i > NF) next;
  if ($event_i != "STALL") next;
  stall_total++;

  mem = (mem_i <= NF) ? ($mem_i + 0) : 0;
  reg = (reg_i <= NF) ? ($reg_i + 0) : 0;
  ibuf = (ibuf_i <= NF) ? ($ibuf_i + 0) : 0;
  bar = (bar_i <= NF) ? ($bar_i + 0) : 0;
  wcta = (wcta_i <= NF) ? ($wcta_i + 0) : 0;
  wmembar = (wmembar_i <= NF) ? ($wmembar_i + 0) : 0;
  watomic = (watomic_i <= NF) ? ($watomic_i + 0) : 0;
  wldgsts = (wldgsts_i <= NF) ? ($wldgsts_i + 0) : 0;
  wdone = (wdone_i <= NF) ? ($wdone_i + 0) : 0;
  ctrl = (ctrl_i <= NF) ? ($ctrl_i + 0) : 0;
  pipe = (pipe_i <= NF) ? ($pipe_i + 0) : 0;
  dual = (dual_i <= NF) ? ($dual_i + 0) : 0;

  nonzero = (mem != 0 || reg != 0 || ibuf != 0 || bar != 0 || wcta != 0 || wmembar != 0 || watomic != 0 || wldgsts != 0 || wdone != 0 || ctrl != 0 || pipe != 0 || dual != 0);
  if (!nonzero) {{
    stall_zero++;
    if (!include_zero) next;
  }} else {{
    stall_used++;
  }}

  pc = (pc_i <= NF) ? $pc_i : "NA";
  gsub(/\r/, "", pc);
  if (pc == "NA" || pc == "") {{
    used_pc_na++;
    next;
  }}

  # nonzero mode: a row can contribute to multiple reasons.
  if (mem > 0) bump("MEM_WAIT", pc);
  if (reg > 0) bump("REG_WAIT", pc);
  if (ibuf > 0) bump("IBUFFER_EMPTY", pc);
  if (bar > 0) bump("BARRIER", pc);
  if (wcta > 0) bump("WAIT_CTA_BARRIER", pc);
  if (wmembar > 0) bump("WAIT_MEMBAR", pc);
  if (watomic > 0) bump("WAIT_ATOMIC", pc);
  if (wldgsts > 0) bump("WAIT_LDGSTS", pc);
  if (wdone > 0) bump("WAIT_DONE", pc);
  if (ctrl > 0) bump("CONTROL_HAZARD", pc);
  if (pipe > 0) bump("PIPE_BUSY", pc);
  if (dual > 0) bump("DUAL_ISSUE_RESTRICT", pc);
}}

END {{
  for (key in cnt) {{
    split(key, parts, SUBSEP);
    reason = parts[1];
    pc = parts[2];
    print reason "," pc "," cnt[key];
  }}
  print "STALL_ROWS_TOTAL," stall_total > "/dev/stderr";
  print "STALL_ROWS_USED," stall_used > "/dev/stderr";
  print "STALL_ROWS_ZERO_COUNTS," stall_zero > "/dev/stderr";
  print "STALL_ROWS_USED_PC_NA," used_pc_na > "/dev/stderr";
}}
"""

    decompress_cmd = _decompress_cmd(issue_csv)
    if issue_csv.suffix.lower() == ".zst" and decompress_cmd is None:
        import zstandard as zstd  # type: ignore

        awk_proc = subprocess.Popen(
            [awk_bin, awk_program],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert awk_proc.stdin is not None
        assert awk_proc.stdout is not None
        assert awk_proc.stderr is not None

        with issue_csv.open("rb") as raw:
            with zstd.ZstdDecompressor().stream_reader(raw) as reader:
                while True:
                    chunk = reader.read(1 << 20)
                    if not chunk:
                        break
                    awk_proc.stdin.write(chunk)
        awk_proc.stdin.close()
        out_b = awk_proc.stdout.read()
        err_b = awk_proc.stderr.read()
        ret = awk_proc.wait()
        proc = subprocess.CompletedProcess(
            args=[awk_bin, awk_program],
            returncode=ret,
            stdout=out_b.decode("utf-8", errors="replace"),
            stderr=err_b.decode("utf-8", errors="replace"),
        )
    elif decompress_cmd is None:
        proc = subprocess.run(
            [awk_bin, awk_program, str(issue_csv)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    else:
        decomp = subprocess.Popen(
            decompress_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert decomp.stdout is not None
        proc = subprocess.run(
            [awk_bin, awk_program],
            check=False,
            stdin=decomp.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        decomp.stdout.close()
        decomp_stderr = b""
        if decomp.stderr is not None:
            decomp_stderr = decomp.stderr.read()
            decomp.stderr.close()
        decomp_ret = decomp.wait()
        if decomp_ret != 0:
            msg = decomp_stderr.decode("utf-8", errors="replace").strip()
            raise SystemExit(f"decompress failed (exit {decomp_ret}) for {issue_csv}: {msg}")

    if proc.returncode != 0:
        raise SystemExit(
            f"awk scan failed (exit {proc.returncode}) for {issue_csv}:\n{proc.stderr.strip()}"
        )

    counts_by_reason_pc: Dict[str, Dict[str, int]] = {}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",", 2)]
        if len(parts) != 3:
            continue
        reason, pc, count_s = parts
        try:
            count = int(count_s, 10)
        except ValueError:
            continue
        counts_by_reason_pc.setdefault(reason, {})[pc] = count

    metrics: Dict[str, int] = {
        "STALL_ROWS_TOTAL": 0,
        "STALL_ROWS_USED": 0,
        "STALL_ROWS_ZERO_COUNTS": 0,
        "STALL_ROWS_USED_PC_NA": 0,
    }
    for line in proc.stderr.splitlines():
        line = line.strip()
        if not line or "," not in line:
            continue
        k, v = (p.strip() for p in line.split(",", 1))
        if k in metrics:
            try:
                metrics[k] = int(v, 10)
            except ValueError:
                metrics[k] = 0
    return counts_by_reason_pc, metrics


def _parse_reason_list(items: Optional[List[str]]) -> Optional[List[str]]:
    if not items:
        return None
    out: List[str] = []
    for item in items:
        for part in item.split(","):
            name = part.strip()
            if not name:
                continue
            out.append(name.upper())
    seen = set()
    uniq: List[str] = []
    for r in out:
        if r in seen:
            continue
        seen.add(r)
        uniq.append(r)
    return uniq


def _default_reason_order(reasons_present: Iterable[str]) -> List[str]:
    present = {r.strip().upper() for r in reasons_present if r}
    if any(r.startswith("WAIT_") for r in present):
        order = WAIT_SPLIT_STALL_REASONS
    else:
        order = LEGACY_STALL_REASONS

    ordered = [r for r in order if r in present]
    if ordered:
        return ordered
    return sorted(present)


def _safe_frac(num: int, denom: int) -> float:
    if denom <= 0:
        return 0.0
    return num / denom


def build_topk_other_from_counts(
    counts_by_reason_pc: Dict[str, Dict[str, int]],
    reasons: Sequence[str],
    *,
    top_k: int,
) -> Dict[str, List[Segment]]:
    out: Dict[str, List[Segment]] = {}
    for reason in reasons:
        pc_counts = counts_by_reason_pc.get(reason, {})
        if not pc_counts:
            continue
        items = sorted(pc_counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
        total = sum(v for _pc, v in items)
        if total <= 0:
            continue

        top = items[: max(0, top_k)]
        sum_top = sum(v for _pc, v in top)
        other = max(0, total - sum_top)

        segs: List[Segment] = []
        for idx, (pc, count) in enumerate(top, 1):
            color = RANK_COLORS[(idx - 1) % len(RANK_COLORS)]
            segs.append(
                Segment(label=pc, rank=idx, count=count, frac=_safe_frac(count, total), color=color)
            )
        if other > 0:
            segs.append(
                Segment(label="OTHER", rank=0, count=other, frac=_safe_frac(other, total), color=OTHER_COLOR)
            )
        out[reason] = segs
    return out


def read_stats_hist(path: Path) -> Dict[str, Dict[str, int]]:
    if not path.is_file():
        raise SystemExit(f"missing input: {path}")
    counts: Dict[str, Dict[str, int]] = {}
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SystemExit(f"empty csv: {path}")
        need = {"reason", "pc", "stall_warp_events"}
        header = {_norm_header(name) for name in reader.fieldnames if name}
        missing = sorted(need - header)
        if missing:
            raise SystemExit(f"missing columns in {path}: {missing}")
        for row in reader:
            reason = (row.get("reason") or "").strip().upper()
            pc = (row.get("pc") or "").strip()
            count = _safe_int(row.get("stall_warp_events"))
            if not reason or not pc or count <= 0:
                continue
            counts.setdefault(reason, {})[pc] = count
    return counts


def read_stats_topk_other(path: Path) -> Dict[str, List[Segment]]:
    if not path.is_file():
        raise SystemExit(f"missing input: {path}")
    rows: Dict[str, List[Tuple[int, str, int]]] = {}
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SystemExit(f"empty csv: {path}")
        need = {"reason", "segment", "rank", "stall_warp_events"}
        header = {_norm_header(name) for name in reader.fieldnames if name}
        missing = sorted(need - header)
        if missing:
            raise SystemExit(f"missing columns in {path}: {missing}")
        for row in reader:
            reason = (row.get("reason") or "").strip().upper()
            seg = (row.get("segment") or "").strip()
            if not reason or not seg:
                continue
            rank = _safe_int(row.get("rank"))
            count = _safe_int(row.get("stall_warp_events"))
            if count <= 0:
                continue
            rows.setdefault(reason, []).append((rank, seg, count))

    out: Dict[str, List[Segment]] = {}
    for reason, entries in rows.items():
        # Prefer rank order; keep OTHER (rank=0) last.
        entries.sort(key=lambda item: (item[0] == 0, item[0] if item[0] != 0 else 10**9))
        total = sum(c for _rank, _seg, c in entries) or 1
        segs: List[Segment] = []
        for rank, seg, count in entries:
            is_other = seg.upper() == "OTHER" or rank == 0
            color = OTHER_COLOR if is_other else RANK_COLORS[(rank - 1) % len(RANK_COLORS)]
            segs.append(
                Segment(
                    label="OTHER" if is_other else seg,
                    rank=0 if is_other else rank,
                    count=count,
                    frac=_safe_frac(count, total),
                    color=color,
                )
            )
        out[reason] = segs
    return out


def maybe_trim_topk(segs_by_reason: Dict[str, List[Segment]], *, top_k: int) -> Dict[str, List[Segment]]:
    """
    If the input is already a topK+OTHER summary and the user requests a smaller
    K, merge the extra ranks into OTHER.
    """
    if top_k <= 0:
        return segs_by_reason
    out: Dict[str, List[Segment]] = {}
    for reason, segs in segs_by_reason.items():
        top: List[Segment] = []
        other_count = 0
        for s in segs:
            if s.rank == 0 or s.label.upper() == "OTHER":
                other_count += s.count
            elif s.rank <= top_k:
                top.append(s)
            else:
                other_count += s.count
        total = sum(s.count for s in top) + other_count
        if total <= 0:
            continue
        rebuilt: List[Segment] = []
        for idx, s in enumerate(sorted(top, key=lambda x: x.rank), 1):
            color = RANK_COLORS[(idx - 1) % len(RANK_COLORS)]
            rebuilt.append(
                Segment(label=s.label, rank=idx, count=s.count, frac=_safe_frac(s.count, total), color=color)
            )
        if other_count > 0:
            rebuilt.append(
                Segment(
                    label="OTHER",
                    rank=0,
                    count=other_count,
                    frac=_safe_frac(other_count, total),
                    color=OTHER_COLOR,
                )
            )
        out[reason] = rebuilt
    return out


def write_counts_cache(
    out_csv: Path,
    issue_csv: Path,
    counts_by_reason_pc: Dict[str, Dict[str, int]],
    metrics: Dict[str, int],
    *,
    include_zero_counts: bool,
) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        f.write(f"# source={issue_csv}\n")
        f.write("# metric=stall_rows\n")
        f.write("# reason_mode=nonzero\n")
        f.write(f"# include_zero_count_stalls={1 if include_zero_counts else 0}\n")
        for k in ("STALL_ROWS_TOTAL", "STALL_ROWS_USED", "STALL_ROWS_ZERO_COUNTS", "STALL_ROWS_USED_PC_NA"):
            f.write(f"# {k}={metrics.get(k, 0)}\n")
        writer = csv.writer(f)
        writer.writerow(["reason", "pc", "stall_rows"])
        for reason in sorted(counts_by_reason_pc.keys()):
            for pc, count in sorted(counts_by_reason_pc[reason].items(), key=lambda kv: (kv[1], kv[0]), reverse=True):
                writer.writerow([reason, pc, count])


def read_counts_cache(path: Path) -> Tuple[Dict[str, Dict[str, int]], Dict[str, int], Dict[str, str]]:
    counts: Dict[str, Dict[str, int]] = {}
    metrics: Dict[str, int] = {}
    meta: Dict[str, str] = {}
    with path.open(newline="") as f:
        # Parse header comments for metrics, then CSV body.
        pos = f.tell()
        line = f.readline()
        while line and line.startswith("#"):
            text = line[1:].strip()
            if "=" in text:
                k, v = (p.strip() for p in text.split("=", 1))
                meta[k] = v
                if k in {"STALL_ROWS_TOTAL", "STALL_ROWS_USED", "STALL_ROWS_ZERO_COUNTS", "STALL_ROWS_USED_PC_NA"}:
                    try:
                        metrics[k] = int(v, 10)
                    except ValueError:
                        metrics[k] = 0
            pos = f.tell()
            line = f.readline()
        f.seek(pos)
        reader = csv.DictReader(f)
        for row in reader:
            reason = (row.get("reason") or "").strip().upper()
            pc = (row.get("pc") or "").strip()
            if not reason or not pc:
                continue
            try:
                count = int(row.get("stall_rows") or "0", 10)
            except ValueError:
                continue
            counts.setdefault(reason, {})[pc] = count
    return counts, metrics, meta


def write_topk_other_csv(
    out_csv: Path,
    stem: str,
    segs_by_reason: Dict[str, List[Segment]],
    *,
    metric_col: str,
    frac_col: str,
    total_col: str,
) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "reason",
                "segment",
                "rank",
                metric_col,
                frac_col,
                total_col,
                "topk_share",
                "input_stem",
            ]
        )
        for reason in sorted(segs_by_reason.keys()):
            segs = segs_by_reason[reason]
            total = sum(s.count for s in segs)
            top_share = sum(s.frac for s in segs if s.label != "OTHER")
            for s in segs:
                writer.writerow(
                    [
                        reason,
                        s.label,
                        s.rank,
                        s.count,
                        f"{s.frac:.8f}",
                        total,
                        f"{top_share:.8f}",
                        stem,
                    ]
                )


def write_stacked_svg(
    out_svg: Path,
    title: str,
    segs_by_reason: Dict[str, List[Segment]],
    *,
    bar_width: int = 820,
    width: Optional[int] = None,
    reasons_order: Optional[Sequence[str]] = None,
    note: str = "",
) -> None:
    left_margin = 30
    right_margin = 30
    top_margin = 80
    bar_h = 24
    row_gap = 18
    bottom_margin = 56

    if reasons_order:
        reasons = [r for r in reasons_order if r in segs_by_reason]
    else:
        reasons = _default_reason_order(segs_by_reason.keys())

    reason_labels: List[str] = []
    for reason in reasons:
        segs = segs_by_reason[reason]
        total = sum(s.count for s in segs) or 1
        top_share = sum(s.count for s in segs if s.label != "OTHER") / total
        reason_labels.append(f"{reason}  (total={total}  topK={top_share*100.0:.2f}%)")

    # Roughly estimate label width (SVG has no easy text measurement).
    max_chars = max((len(s) for s in reason_labels), default=0)
    label_w = max(160, int(max_chars * 7.2 + 16))
    chart_x = left_margin + label_w
    if width is None:
        width = left_margin + label_w + bar_width + right_margin

    height = top_margin + len(reasons) * (bar_h + row_gap) + bottom_margin

    lines: List[str] = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">')
    lines.append('<rect x="0" y="0" width="100%" height="100%" fill="white"/>')
    lines.append(
        f'<text x="{left_margin}" y="{left_margin + 5}" font-size="22" font-family="sans-serif">{_svg_escape(title)}</text>'
    )
    subtitle = "Stacked bar per stall reason: top-K PCs + OTHER (normalized within each reason)."
    lines.append(
        f'<text x="{left_margin}" y="{left_margin + 30}" font-size="12" fill="#444" font-family="sans-serif">{_svg_escape(subtitle)}</text>'
    )

    y = top_margin
    for reason, reason_label in zip(reasons, reason_labels):
        segs = segs_by_reason[reason]
        total = sum(s.count for s in segs) or 1
        lines.append(
            f'<text x="{chart_x - 10}" y="{y + bar_h - 6}" font-size="13" fill="#111" text-anchor="end" font-family="sans-serif">{_svg_escape(reason_label)}</text>'
        )

        # Background.
        lines.append(
            f'<rect x="{chart_x}" y="{y}" width="{bar_width}" height="{bar_h}" fill="#f5f5f5" stroke="#e0e0e0" stroke-width="1"/>'
        )

        x = chart_x
        # Draw segments; last segment snaps to end to avoid rounding gaps.
        for idx, s in enumerate(segs):
            if idx == len(segs) - 1:
                seg_w = chart_x + bar_width - x
            else:
                seg_w = int(round(bar_width * (s.count / total)))
                seg_w = max(0, min(seg_w, chart_x + bar_width - x))
            if seg_w <= 0:
                continue
            lines.append(
                f'<rect x="{x}" y="{y}" width="{seg_w}" height="{bar_h}" fill="{s.color}"/>'
            )

            # Label inside segment if there is space.
            frac_pct = (s.count / total) * 100.0
            if s.label == "OTHER":
                text = f"OTHER {frac_pct:.1f}%"
            else:
                text = f"{s.label} {frac_pct:.1f}%"
            if seg_w >= 60:
                tx = x + 6
                lines.append(
                    f'<text x="{tx}" y="{y + bar_h - 7}" font-size="11" fill="#111" font-family="sans-serif">{_svg_escape(text)}</text>'
                )
            elif seg_w >= 38 and s.label != "OTHER":
                tx = x + 4
                lines.append(
                    f'<text x="{tx}" y="{y + bar_h - 7}" font-size="11" fill="#111" font-family="sans-serif">{_svg_escape(s.label)}</text>'
                )

            x += seg_w

        y += bar_h + row_gap

    # X-axis ticks 0..100%.
    axis_y = height - bottom_margin + 10
    lines.append(
        f'<line x1="{chart_x}" y1="{axis_y}" x2="{chart_x + bar_width}" y2="{axis_y}" stroke="#bbb" stroke-width="1"/>'
    )
    for tick in range(0, 101, 20):
        tx = chart_x + int(bar_width * (tick / 100.0))
        lines.append(
            f'<line x1="{tx}" y1="{axis_y}" x2="{tx}" y2="{axis_y + 6}" stroke="#bbb" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{tx}" y="{axis_y + 22}" font-size="11" fill="#444" text-anchor="middle" font-family="sans-serif">{tick}%</text>'
        )

    # Footer note.
    if note:
        lines.append(
            f'<text x="{left_margin}" y="{height - 14}" font-size="11" fill="#444" font-family="sans-serif">{_svg_escape(note)}</text>'
        )

    lines.append("</svg>")
    out_svg.parent.mkdir(parents=True, exist_ok=True)
    out_svg.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _require_matplotlib() -> "tuple[Any, Any]":
    try:
        import matplotlib  # type: ignore

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore

        return matplotlib, plt
    except Exception as exc:  # pragma: no cover
        raise SystemExit(
            "PNG output requires matplotlib.\n"
            "Install matplotlib (and numpy if needed) or use --format svg.\n"
            f"Original error: {exc}"
        )


def write_stacked_png(
    out_png: Path,
    title: str,
    segs_by_reason: Dict[str, List[Segment]],
    *,
    dpi: int = 120,
    reasons_order: Optional[Sequence[str]] = None,
) -> None:
    _, plt = _require_matplotlib()

    if reasons_order:
        reasons = [r for r in reasons_order if r in segs_by_reason]
    else:
        reasons = _default_reason_order(segs_by_reason.keys())

    labels: List[str] = []
    for reason in reasons:
        segs = segs_by_reason[reason]
        total = sum(s.count for s in segs) or 1
        top_share = sum(s.count for s in segs if s.label != "OTHER") / total
        labels.append(f"{reason}  (total={total}  topK={top_share*100.0:.2f}%)")

    fig_h = max(2.6, 0.9 + 0.55 * len(reasons))
    fig, ax = plt.subplots(figsize=(13.0, fig_h), dpi=dpi)
    ax.set_title(title)
    ax.set_xlim(0.0, 1.0)
    ax.set_xlabel("fraction within reason")

    y_pos = list(range(len(reasons)))
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()

    for idx, reason in enumerate(reasons):
        segs = segs_by_reason[reason]
        total = sum(s.count for s in segs) or 1
        left = 0.0
        for s in segs:
            width = s.count / total
            if width <= 0:
                continue
            ax.barh(idx, width, left=left, height=0.62, color=s.color)
            if width >= 0.10:
                label = "OTHER" if s.label.upper() == "OTHER" else s.label
                ax.text(left + 0.01, idx, f"{label} {width*100:.1f}%", va="center", fontsize=8)
            left += width

    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot per-stall-reason top-K PC distribution (topK+OTHER) from stats or issue-trace CSV."
    )
    parser.add_argument(
        "input_csv",
        type=Path,
        help="Path to input CSV: stall_reason_pc_hist.csv / stall_reason_pc_topk_other.csv / <log>_issue.csv[.gz/.zst].",
    )
    parser.add_argument(
        "-o",
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUT_DIR}).",
    )
    parser.add_argument(
        "--out-name",
        default=None,
        help="Output base name (default: derived from input filename).",
    )
    parser.add_argument(
        "--reasons",
        action="append",
        default=None,
        help="Comma-separated stall reason list to include (default: all). Example: MEM_WAIT,WAIT_ATOMIC,PIPE_BUSY",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Top K PCs per reason (default: 5).",
    )
    parser.add_argument(
        "--include-zero-count-stalls",
        action="store_true",
        help="Include STALL rows where all stall counters are zero (usually warp=-1).",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Re-scan the issue CSV even if a cache exists.",
    )
    parser.add_argument(
        "--format",
        choices=("svg", "png", "both"),
        default="svg",
        help="Output format (default: %(default)s).",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=120,
        help="PNG DPI (default: %(default)s).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_csv: Path = args.input_csv
    if not input_csv.is_file():
        raise SystemExit(f"input not found: {input_csv}")

    requested_reasons = _parse_reason_list(args.reasons)
    kind = _detect_input_kind(input_csv)
    if args.out_name:
        stem = args.out_name
    elif kind == "issue_trace":
        stem = _issue_stem(input_csv)
    else:
        # Stats CSVs have fixed names; prefer the directory name as a stem.
        stem = input_csv.parent.name or input_csv.stem
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    metric_col = "stall_rows"
    frac_col = "fraction_of_reason_stall_rows"
    total_col = "total_reason_stall_rows"
    note = "Note: PC is STALL sample warp PC (hotspot proxy)."

    counts_cache = out_dir / f"{stem}_stall_reason_pc_counts.csv"
    metrics: Dict[str, int] = {}
    if kind == "issue_trace":
        if counts_cache.is_file() and not args.no_cache:
            counts_by_reason_pc, metrics, meta = read_counts_cache(counts_cache)
            want_zero = "1" if args.include_zero_count_stalls else "0"
            if meta.get("include_zero_count_stalls") not in {None, want_zero}:
                counts_by_reason_pc, metrics = _run_awk_reason_pc_counts(
                    input_csv, include_zero_counts=args.include_zero_count_stalls
                )
                write_counts_cache(
                    counts_cache,
                    input_csv,
                    counts_by_reason_pc,
                    metrics,
                    include_zero_counts=args.include_zero_count_stalls,
                )
        else:
            counts_by_reason_pc, metrics = _run_awk_reason_pc_counts(
                input_csv, include_zero_counts=args.include_zero_count_stalls
            )
            write_counts_cache(
                counts_cache,
                input_csv,
                counts_by_reason_pc,
                metrics,
                include_zero_counts=args.include_zero_count_stalls,
            )

        if requested_reasons is None:
            filtered_reasons = _default_reason_order(counts_by_reason_pc.keys())
        else:
            filtered_reasons = [r for r in requested_reasons if r in counts_by_reason_pc]
        segs_by_reason = build_topk_other_from_counts(
            counts_by_reason_pc, filtered_reasons, top_k=args.top_k
        )
    elif kind == "stats_hist":
        metric_col = "stall_warp_events"
        frac_col = "fraction_of_reason_stall_warp_events"
        total_col = "total_reason_stall_warp_events"
        note = "Note: PC is the blocked instruction PC (CONTROL_HAZARD uses real next PC)."

        counts_by_reason_pc = read_stats_hist(input_csv)
        if requested_reasons is None:
            filtered_reasons = _default_reason_order(counts_by_reason_pc.keys())
        else:
            filtered_reasons = [r for r in requested_reasons if r in counts_by_reason_pc]
        segs_by_reason = build_topk_other_from_counts(
            counts_by_reason_pc, filtered_reasons, top_k=args.top_k
        )
    elif kind == "stats_topk_other":
        metric_col = "stall_warp_events"
        frac_col = "fraction_of_reason_stall_warp_events"
        total_col = "total_reason_stall_warp_events"
        note = "Note: PC is the blocked instruction PC (CONTROL_HAZARD uses real next PC)."

        segs_by_reason = read_stats_topk_other(input_csv)
        segs_by_reason = maybe_trim_topk(segs_by_reason, top_k=args.top_k)
        if requested_reasons is not None:
            segs_by_reason = {
                r: segs_by_reason[r] for r in requested_reasons if r in segs_by_reason
            }
    elif kind == "summary_topk_other":
        # Legacy summary CSV from issue-trace mode.
        segs_by_reason = {}
        with input_csv.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise SystemExit(f"empty csv: {input_csv}")
            need = {"reason", "segment", "rank", "stall_rows"}
            header = {_norm_header(name) for name in reader.fieldnames if name}
            missing = sorted(need - header)
            if missing:
                raise SystemExit(f"missing columns in {input_csv}: {missing}")
            tmp: Dict[str, List[Tuple[int, str, int]]] = {}
            for row in reader:
                reason = (row.get("reason") or "").strip().upper()
                seg = (row.get("segment") or "").strip()
                if not reason or not seg:
                    continue
                rank = _safe_int(row.get("rank"))
                count = _safe_int(row.get("stall_rows"))
                if count <= 0:
                    continue
                tmp.setdefault(reason, []).append((rank, seg, count))
        for reason, entries in tmp.items():
            entries.sort(key=lambda item: (item[0] == 0, item[0] if item[0] != 0 else 10**9))
            total = sum(c for _rank, _seg, c in entries) or 1
            segs: List[Segment] = []
            for rank, seg, count in entries:
                is_other = seg.upper() == "OTHER" or rank == 0
                color = OTHER_COLOR if is_other else RANK_COLORS[(rank - 1) % len(RANK_COLORS)]
                segs.append(
                    Segment(
                        label="OTHER" if is_other else seg,
                        rank=0 if is_other else rank,
                        count=count,
                        frac=_safe_frac(count, total),
                        color=color,
                    )
                )
            segs_by_reason[reason] = segs
        segs_by_reason = maybe_trim_topk(segs_by_reason, top_k=args.top_k)
        if requested_reasons is not None:
            segs_by_reason = {
                r: segs_by_reason[r] for r in requested_reasons if r in segs_by_reason
            }
    else:  # pragma: no cover
        raise SystemExit(f"unhandled input kind: {kind}")

    out_summary = out_dir / f"{stem}_stall_reason_pc_topk_other.csv"
    out_svg = out_dir / f"{stem}_stall_reason_pc_topk_other.svg"
    out_png = out_dir / f"{stem}_stall_reason_pc_topk_other.png"
    write_topk_other_csv(
        out_summary,
        stem,
        segs_by_reason,
        metric_col=metric_col,
        frac_col=frac_col,
        total_col=total_col,
    )

    if requested_reasons is None:
        plot_reasons = _default_reason_order(segs_by_reason.keys())
    else:
        plot_reasons = [r for r in requested_reasons if r in segs_by_reason]

    title = f"{stem}: STALL reason -> top{args.top_k} PCs + OTHER ({metric_col})"
    if args.format in ("svg", "both"):
        write_stacked_svg(
            out_svg, title, segs_by_reason, reasons_order=plot_reasons, note=note
        )
    if args.format in ("png", "both"):
        write_stacked_png(
            out_png, title, segs_by_reason, dpi=args.dpi, reasons_order=plot_reasons
        )

    print(f"input: {input_csv}")
    print(f"output dir: {out_dir}")
    print(f"summary:    {out_summary}")
    if args.format in ("svg", "both"):
        print(f"plot svg:   {out_svg}")
    if args.format in ("png", "both"):
        print(f"plot png:   {out_png}")
    if kind == "issue_trace":
        print(f"cache csv:  {counts_cache}")
        if metrics:
            print(
                "STALL rows (total/used/zero/pc_na): "
                f"{metrics.get('STALL_ROWS_TOTAL', 0)}/"
                f"{metrics.get('STALL_ROWS_USED', 0)}/"
                f"{metrics.get('STALL_ROWS_ZERO_COUNTS', 0)}/"
                f"{metrics.get('STALL_ROWS_USED_PC_NA', 0)}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
