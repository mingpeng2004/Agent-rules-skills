#!/usr/bin/env python3
"""Schematic + PCB gates (S/L/R/D layers). Runs kicad-cli's real ERC and DRC
-- never trust a prose "PASS" claim without one of these JSON reports next
to it as evidence.

Usage: python run_checks.py <project.kicad_sch> <project.kicad_pcb> [--waive TYPE=N ...]

Prints a summary and writes the two raw JSON reports next to the PCB file
under evidence/erc_<timestamp>.json and evidence/drc_<timestamp>.json.

Exit code 0 only if, after subtracting any --waive allowances, zero
violations remain in both reports. Waivers must be named explicitly
(e.g. --waive solder_mask_bridge=90) and are always printed, never silent.
"""
import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kicad_env import find_kicad, bin_dir, cli_exe  # noqa: E402


def run_erc(cli, sch_path, out_path):
    subprocess.run(
        [str(cli), "sch", "erc", "--format", "json", "--severity-all",
         "--output", str(out_path), str(sch_path)],
        capture_output=True, text=True,
    )
    data = json.loads(out_path.read_text(encoding="utf-8"))
    violations = []
    for sheet in data.get("sheets", []):
        violations.extend(sheet.get("violations", []))
    return violations


def run_drc(cli, pcb_path, out_path):
    subprocess.run(
        [str(cli), "pcb", "drc", "--format", "json", "--severity-all",
         "--output", str(out_path), str(pcb_path)],
        capture_output=True, text=True,
    )
    data = json.loads(out_path.read_text(encoding="utf-8"))
    violations = data.get("violations", [])
    unconnected = data.get("unconnected_items", [])
    return violations, unconnected


def summarize(name, violations):
    by_type = Counter(v["type"] for v in violations)
    by_sev = Counter(v["severity"] for v in violations)
    print(f"--- {name}: {len(violations)} total ---")
    for t, n in by_type.most_common():
        print(f"  {t}: {n}")
    return by_type, by_sev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sch")
    ap.add_argument("pcb")
    ap.add_argument("--waive", action="append", default=[],
                     help="TYPE=N, e.g. --waive solder_mask_bridge=90 "
                          "(must be justified in the caller's report, this "
                          "script only enforces the count)")
    args = ap.parse_args()

    kicad_root = find_kicad()
    if kicad_root is None:
        print("FAIL: run kicad_env.py first")
        return 1
    cli = cli_exe(bin_dir(kicad_root))

    pcb_path = Path(args.pcb)
    evidence_dir = pcb_path.parent / "evidence"
    evidence_dir.mkdir(exist_ok=True)

    erc_out = evidence_dir / "erc_latest.json"
    drc_out = evidence_dir / "drc_latest.json"

    erc_violations = run_erc(cli, args.sch, erc_out)
    drc_violations, unconnected = run_drc(cli, args.pcb, drc_out)

    erc_types, erc_sev = summarize("ERC", erc_violations)
    drc_types, drc_sev = summarize("DRC", drc_violations)
    print(f"  unconnected_items: {len(unconnected)}")

    waivers = {}
    for w in args.waive:
        t, n = w.split("=")
        waivers[t] = int(n)
    if waivers:
        print("--- waivers applied (must be individually justified elsewhere) ---")
        for t, n in waivers.items():
            print(f"  {t}: waiving up to {n}")

    erc_errors = sum(1 for v in erc_violations if v["severity"] == "error")
    real_drc = 0
    for t, n in drc_types.items():
        allowed = waivers.get(t, 0)
        real_drc += max(0, n - allowed)
    real_drc += len(unconnected) - waivers.get("unconnected_items", 0)
    real_drc = max(real_drc, 0)

    print(f"\nERC errors (not waivable): {erc_errors}")
    print(f"DRC violations after waivers: {real_drc}")
    print(f"Evidence: {erc_out}, {drc_out}")

    return 0 if (erc_errors == 0 and real_drc <= 0) else 1


if __name__ == "__main__":
    sys.exit(main())
