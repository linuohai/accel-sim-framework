"""Compute sim-vs-real MAPE for v2 smoke configs.

For each cfg in configs.csv (or filtered by argv id list):
  1. Parse sim log → gpu_tot_sim_cycle, WINSN_TOTAL, gpu_tot_sim_insn,
     and sum DRAM Read/Write 32B-sector counts across partitions.
  2. Parse NCU CSV, filter rows by configs.csv kernel_regex (decisive: NCU
     records all kernels; we keep only target).
  3. Compute MAPE on cycle / warp_insn / warp_IPC / dram_util.
  4. dram_util on sim side falls back to rd+wr × 32B / runtime / 1555 GB/s
     because GPGPU-Sim's dram_util_bins[] never gets incremented.
"""
import argparse
import csv
import os
import re
import sys

A100_CLOCK_HZ = 1.41e9
A100_NUM_SM = 108
A100_SCHEDULERS_PER_SM = 4
A100_DRAM_PEAK_GBPS = 1555


def parse_sim_log(path):
    """L2_total_cache_misses (32B sectors) is the source of truth for bytes
    going to DRAM — L2 hits don't reach HBM. Per-partition Read=/Write= lines
    are accumulated across kernel-end dumps and would double-count."""
    m = {"sim_cycle": 0, "sim_insn": 0, "sim_ipc_thread": 0.0,
         "sim_winsn": 0, "sim_l2_misses": 0, "sim_l2_bw_gbps": 0.0}
    with open(path) as f:
        for line in f:
            s = line.strip()
            if s.startswith("gpu_tot_sim_cycle "):
                m["sim_cycle"] = int(s.split("=")[1].strip())
            elif s.startswith("gpu_tot_sim_insn "):
                m["sim_insn"] = int(s.split("=")[1].strip())
            elif s.startswith("gpu_tot_ipc "):
                m["sim_ipc_thread"] = float(s.split("=")[1].strip())
            elif s.startswith("WINSN_TOTAL:"):
                m["sim_winsn"] = int(s.split(":")[1].strip())
            elif s.startswith("L2_total_cache_misses "):
                m["sim_l2_misses"] = int(s.split("=")[1].strip())
            elif s.startswith("L2_BW_total "):
                m["sim_l2_bw_gbps"] = float(s.split("=")[1].strip().split()[0])
    return m


def to_f(v):
    if v is None or v == "":
        return 0.0
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return 0.0


def weighted_avg(vals, weights):
    sw = sum(weights)
    if sw == 0:
        return 0.0
    return sum(v * w for v, w in zip(vals, weights)) / sw


def parse_ncu_csv(path, kernel_regex):
    pat = re.compile(kernel_regex)
    target = []
    all_kernels = []
    with open(path) as f:
        for r in csv.DictReader(f):
            kn = r.get("Kernel Name", "") or ""
            # Skip the unit-row immediately under the header
            if r.get("ID", "") == "":
                continue
            all_kernels.append(kn)
            if pat.search(kn):
                target.append(r)

    if not target:
        return None, all_kernels

    times = [to_f(r.get("gpu__time_duration.sum")) for r in target]
    return {
        "matched_count": len(target),
        "matched_names": [r["Kernel Name"][:80] for r in target],
        "ncu_time_us": sum(times),
        "ncu_winsn_sum": sum(to_f(r.get("smsp__inst_executed.sum")) for r in target),
        "ncu_gpc_cycles_avg_sum": sum(to_f(r.get("gpc__cycles_elapsed.avg")) for r in target),
        "ncu_warp_ipc_active": weighted_avg(
            [to_f(r.get("smsp__inst_executed.avg.per_cycle_active")) for r in target], times),
        "ncu_sm_thru_pct": weighted_avg(
            [to_f(r.get("sm__throughput.avg.pct_of_peak_sustained_elapsed")) for r in target], times),
        "ncu_dram_thru_pct": weighted_avg(
            [to_f(r.get("dram__throughput.avg.pct_of_peak_sustained_elapsed")) for r in target], times),
    }, all_kernels


def mape(sim, ncu):
    if ncu == 0:
        return None
    return abs(sim - ncu) / ncu * 100.0


def fmt_mape(x):
    return f"{x:6.1f}%" if x is not None else "    N/A"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg-csv", default="/workspace/prefetch/result/sim_vs_real_mape_v2/scripts/configs.csv")
    ap.add_argument("--sim-dir", default="/workspace/prefetch/result/sim_vs_real_mape_v2/sim_logs")
    ap.add_argument("--ncu-dir", default="/workspace/prefetch/result/sim_vs_real_mape_v2/ncu_out")
    ap.add_argument("ids", nargs="*", default=["F3", "D3", "G4", "R2"])
    args = ap.parse_args()

    cfgs = {row["id"]: row for row in csv.DictReader(open(args.cfg_csv))}

    print(f"{'cfg':<5} {'cycle_sim':>12} {'cycle_ncu':>12} {'cyc%':>8} "
          f"{'winsn_sim':>12} {'winsn_ncu':>12} {'win%':>8} "
          f"{'dram_sim%':>10} {'dram_ncu%':>10} {'dram%':>8}")
    print("-" * 130)

    for cid in args.ids:
        if cid not in cfgs:
            print(f"{cid}: not in configs.csv")
            continue
        cfg = cfgs[cid]
        cfg_tag = cfg["cfg_tag"]
        kregex = cfg["kernel_regex"]

        sim_log = os.path.join(args.sim_dir, f"{cfg_tag}.log")
        ncu_csv = os.path.join(args.ncu_dir, f"{cfg_tag}.csv")
        if not os.path.exists(sim_log):
            print(f"{cid}: sim log missing → {sim_log}")
            continue
        if not os.path.exists(ncu_csv):
            print(f"{cid}: ncu csv missing → {ncu_csv}")
            continue

        sim = parse_sim_log(sim_log)
        ncu_res = parse_ncu_csv(ncu_csv, kregex)
        if ncu_res[0] is None:
            print(f"\n{cid} ({cfg_tag}): regex '{kregex}' matched 0 of {len(ncu_res[1])} NCU kernels")
            for k in ncu_res[1]:
                print(f"    NCU saw: {k[:80]}")
            continue
        ncu, _all = ncu_res

        # Cycle: prefer ncu_gpc_cycles_avg_sum, fallback to time × clock
        ncu_cycle = ncu["ncu_gpc_cycles_avg_sum"]
        cycle_src = "gpc"
        if ncu_cycle == 0:
            ncu_cycle = ncu["ncu_time_us"] * 1e-6 * A100_CLOCK_HZ
            cycle_src = "time×freq"
        cycle_mape = mape(sim["sim_cycle"], ncu_cycle)

        # Warp insn (NCU smsp__inst_executed.sum vs sim WINSN_TOTAL)
        winsn_mape = mape(sim["sim_winsn"], ncu["ncu_winsn_sum"])

        # DRAM util: L2 misses × 32B / runtime / 1555 GB/s
        # (L2 hits don't reach HBM; SC.3 fallback because dram_util_bins[] is
        # never incremented in GPGPU-Sim source.)
        runtime_s = sim["sim_cycle"] / A100_CLOCK_HZ
        bytes_to_dram = sim["sim_l2_misses"] * 32
        sim_dram_util = (bytes_to_dram / runtime_s / (A100_DRAM_PEAK_GBPS * 1e9) * 100) if runtime_s > 0 else 0
        dram_mape = mape(sim_dram_util, ncu["ncu_dram_thru_pct"])

        # Warp IPC per scheduler (elapsed)
        sim_warp_ipc = sim["sim_winsn"] / sim["sim_cycle"] / (A100_NUM_SM * A100_SCHEDULERS_PER_SM)
        ncu_warp_ipc = (ncu["ncu_winsn_sum"] / ncu_cycle / (A100_NUM_SM * A100_SCHEDULERS_PER_SM)
                        if ncu["ncu_winsn_sum"] > 0 and ncu_cycle > 0 else 0)
        ipc_mape = mape(sim_warp_ipc, ncu_warp_ipc) if ncu_warp_ipc > 0 else None

        print(f"{cid:<5} {sim['sim_cycle']:>12,} {ncu_cycle:>12,.0f} {fmt_mape(cycle_mape):>8} "
              f"{sim['sim_winsn']:>12,} {ncu['ncu_winsn_sum']:>12,.0f} {fmt_mape(winsn_mape):>8} "
              f"{sim_dram_util:>9.2f}% {ncu['ncu_dram_thru_pct']:>9.2f}% {fmt_mape(dram_mape):>8}")

    print("\n--- per-cfg detail ---")
    for cid in args.ids:
        if cid not in cfgs:
            continue
        cfg = cfgs[cid]
        cfg_tag = cfg["cfg_tag"]
        kregex = cfg["kernel_regex"]
        ncu_csv = os.path.join(args.ncu_dir, f"{cfg_tag}.csv")
        if not os.path.exists(ncu_csv):
            continue
        ncu_res = parse_ncu_csv(ncu_csv, kregex)
        if ncu_res[0] is None:
            continue
        ncu, all_k = ncu_res
        print(f"\n  {cid} ({cfg_tag}) regex='{kregex}'")
        print(f"    NCU total kernel rows: {len(all_k)}, matched: {ncu['matched_count']}")
        for n in ncu["matched_names"]:
            print(f"      target: {n}")
        nontarget = [k for k in all_k if not re.compile(kregex).search(k)]
        for n in nontarget[:5]:
            print(f"      NOISE : {n[:80]}")


if __name__ == "__main__":
    main()
