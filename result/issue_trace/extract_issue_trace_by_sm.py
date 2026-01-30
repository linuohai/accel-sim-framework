#!/usr/bin/env python3
"""
Extract per-SM rows from a large issue trace CSV using streaming I/O.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set


def parse_sm_value(value: str) -> Optional[int]:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return int(text, 0)
    except ValueError:
        return None


def parse_sm_list(items: Iterable[str]) -> Set[int]:
    result: Set[int] = set()
    for item in items:
        for part in item.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                start_s, end_s = part.split("-", 1)
                start = int(start_s, 0)
                end = int(end_s, 0)
                if start <= end:
                    result.update(range(start, end + 1))
                else:
                    result.update(range(end, start + 1))
            else:
                result.add(int(part, 0))
    return result


def find_sm_column(header: List[str]) -> Optional[int]:
    for name in ("sm", "sm_id", "SM", "smid"):
        try:
            return header.index(name)
        except ValueError:
            continue
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract per-SM issue trace rows from a CSV."
    )
    parser.add_argument("-i", "--input", required=True, help="Input CSV path.")
    parser.add_argument(
        "--sm",
        action="append",
        required=True,
        help="SM list, e.g. 0,1,2 or 0-3. Can be repeated.",
    )
    parser.add_argument(
        "-o",
        "--out-dir",
        default=None,
        help="Output directory (default: input file directory).",
    )
    parser.add_argument(
        "--pattern",
        default="{stem}_sm{sm}.csv",
        help="Output filename pattern using {stem} and {sm}.",
    )
    parser.add_argument(
        "--allow-short-rows",
        action="store_true",
        help="Keep rows shorter than the header length.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        raise SystemExit(f"input file not found: {input_path}")

    sm_list = parse_sm_list(args.sm)
    if not sm_list:
        raise SystemExit("no SM ids parsed from --sm arguments")

    out_dir = Path(args.out_dir) if args.out_dir else input_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    outputs: Dict[int, Path] = {}
    writers: Dict[int, csv.writer] = {}
    out_files = []
    counts = {sm: 0 for sm in sm_list}
    bad_rows = 0

    with input_path.open(newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            raise SystemExit("input file is empty")

        sm_idx = find_sm_column(header)
        if sm_idx is None:
            raise SystemExit("SM column not found in header")

        for sm in sorted(sm_list):
            out_path = out_dir / args.pattern.format(stem=input_path.stem, sm=sm)
            outputs[sm] = out_path
            out_f = out_path.open("w", newline="")
            out_files.append(out_f)
            writer = csv.writer(out_f)
            writer.writerow(header)
            writers[sm] = writer

        for row in reader:
            if not row:
                continue
            if row[0].lstrip().startswith("#"):
                continue
            if not args.allow_short_rows and len(row) != len(header):
                bad_rows += 1
                continue
            if sm_idx >= len(row):
                bad_rows += 1
                continue
            sm_val = parse_sm_value(row[sm_idx])
            if sm_val is None or sm_val not in sm_list:
                continue
            writers[sm_val].writerow(row)
            counts[sm_val] += 1

    for out_f in out_files:
        out_f.close()

    total = sum(counts.values())
    print(f"processed {input_path}")
    for sm in sorted(sm_list):
        print(f"sm {sm}: {counts[sm]} rows -> {outputs[sm]}")
    if bad_rows:
        print(f"skipped {bad_rows} malformed rows")
    print(f"total rows written: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
