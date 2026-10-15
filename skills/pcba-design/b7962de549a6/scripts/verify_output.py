#!/usr/bin/env python3
"""Output verification (O layer, read-back half). export_mfg.py's exit code
only tells you kicad-cli didn't crash -- it doesn't tell you the outputs are
actually complete and self-consistent. This script re-reads the generated
files and checks them against design.json and each other.

Usage: python verify_output.py <design.json> <out_dir> <project_stem>
"""
import csv
import json
import sys
import zipfile
from pathlib import Path


def main():
    if len(sys.argv) != 4:
        print("usage: verify_output.py <design.json> <out_dir> <project_stem>")
        return 2

    design = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out_dir = Path(sys.argv[2])
    stem = sys.argv[3]

    problems = []
    n_components = len(design.get("components", []))
    n_layers_expected = design.get("board", {}).get("layers", 4)

    # O-06: zip exists and contains something
    zip_path = out_dir / f"{stem}_Gerber.zip"
    if not zip_path.exists():
        problems.append(f"missing {zip_path}")
    else:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
        cu_layers = [n for n in names if n.endswith((".gtl", ".gbl")) or ".g" in Path(n).suffix and Path(n).suffix[2:].isdigit()]
        print(f"O-06 zip: {len(names)} files, {len(cu_layers)} copper layer(s) (expect {n_layers_expected})")
        if len(cu_layers) < n_layers_expected:
            problems.append(f"O-01 zip has {len(cu_layers)} copper layers, design.json expects {n_layers_expected}")

    # O-02: drill file present and non-trivial
    drl = out_dir / f"{stem}.drl"
    if not drl.exists():
        problems.append(f"missing {drl}")
    elif drl.stat().st_size < 50:
        problems.append(f"{drl} suspiciously small ({drl.stat().st_size} bytes)")

    # O-09: pos csv row count matches component count
    pos_csv = out_dir / f"{stem}-pos.csv"
    if not pos_csv.exists():
        problems.append(f"missing {pos_csv}")
    else:
        with open(pos_csv, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        data_rows = len(rows) - 1  # header
        if data_rows != n_components:
            problems.append(f"O-09 pos.csv has {data_rows} rows, design.json has {n_components} components")

    # O-05: BOM row count matches component count
    bom_csv = out_dir / f"{stem}_BOM.csv"
    if not bom_csv.exists():
        problems.append(f"missing {bom_csv}")
    else:
        with open(bom_csv, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        data_rows = len(rows) - 1
        if data_rows != n_components:
            problems.append(f"O-05 BOM.csv has {data_rows} rows, design.json has {n_components} components")

    # O-07/O-08: STEP and PDF exist and non-trivial
    for ext, min_size in ((".step", 1000), (".pdf", 500)):
        p = out_dir / f"{stem}{ext}"
        if not p.exists():
            problems.append(f"missing {p}")
        elif p.stat().st_size < min_size:
            problems.append(f"{p} suspiciously small ({p.stat().st_size} bytes)")

    if problems:
        print(f"FAIL: {len(problems)} problem(s)")
        for p in problems:
            print(" -", p)
        return 1

    print(f"PASS: manufacturing outputs in {out_dir} are complete and consistent with design.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
