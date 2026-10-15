#!/usr/bin/env python3
"""JLCPCB (嘉立创) standard submission package export (O layer, JLCPCB-specific).

Produces TWO independent tiers -- read them separately, they have different
completeness requirements:

  Tier 1 -- bare PCB fab (always produceable from a DRC-clean board):
    <stem>_JLC_Gerber.zip   Gerbers (RS-274X, Protel extensions, kicad-cli
                            default -- this is what JLCPCB's own KiCad 9/10
                            guide verifies against) + merged Excellon drill.
  Tier 2 -- PCBA assembly service add-on (requires 100% LCSC part-number
            coverage in design.json -- JLCPCB's own automated BOM/CPL
            check rejects any line missing a part number):
    <stem>_JLC_BOM.csv     Comment,Designator,Footprint,LCSC Part# --
                           identical (value+footprint+LCSC) parts merged
                           into one row, designators comma-joined.
    <stem>_JLC_CPL.csv     Designator,Mid X,Mid Y,Layer,Rotation -- built
                           from the ACTUAL final PCB placement (kicad-cli
                           pos export), not from design.json (design.json
                           has no layout data; the pcb file is ground truth
                           for position/rotation).

Tier 2 is gated on LCSC coverage: if any component in design.json has an
empty "lcsc" field, this script still writes the BOM/CPL files (so you can
see exactly which rows are incomplete) but exits non-zero and prints which
refs are missing -- do NOT upload an incomplete BOM to JLCPCB's PCBA order
flow, it will fail their own automated part-matching check.

Rotation caveat (see references/bouni-fab-details.md): JLCPCB's
pick-and-place rotation convention does not always match KiCad's for
polarized/asymmetric footprints. This script does NOT apply a rotation-
correction table (no verified JLCPCB rotation DB is vendored in this repo
-- fabricating offsets without a verified source would be worse than not
guessing). Before confirming a PCBA order, visually check part orientation
in JLCPCB's own CPL preview step in their web order flow -- this is
JLCPCB's own recommended verification step, not a workaround for a gap in
this script.

Usage:
  python export_jlcpcb.py <project.kicad_pcb> <design.json> <out_dir>
"""
import csv
import json
import subprocess
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kicad_env import find_kicad, bin_dir, cli_exe  # noqa: E402

# Layers JLCPCB needs for a 4-layer board fab order. Do NOT include F.Fab/
# B.Fab (assembly-drawing-only layers some fabs choke on) or User.* layers.
GERBER_LAYERS = ("F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,"
                  "F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(" ".join(str(c) for c in cmd))
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
    return r.returncode == 0


def export_tier1_gerbers(cli, pcb, out_dir, stem):
    gerber_dir = out_dir / "gerbers_tmp"
    gerber_dir.mkdir(exist_ok=True)
    ok = run([cli, "pcb", "export", "gerbers", "--layers", GERBER_LAYERS,
              "--output", f"{gerber_dir}/", pcb])
    # kicad-cli defaults: Protel extensions ON (no --no-protel-ext passed),
    # X2 format ON (no --no-x2 passed) -- this matches JLCPCB's own current
    # KiCad 9/10 guide, verified via kicad-cli --help against this exact
    # install (no --use-protel-extensions flag exists in kicad-cli; Protel
    # naming is the tool's default and --no-protel-ext is the opt-OUT).
    ok &= run([cli, "pcb", "export", "drill", "--format", "excellon",
               "--drill-origin", "absolute", "--excellon-units", "mm",
               "--excellon-zeros-format", "decimal",
               "--output", f"{gerber_dir}/", pcb])
    files = list(gerber_dir.iterdir())
    zip_path = out_dir / f"{stem}_JLC_Gerber.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, f.name)
    for f in files:
        f.unlink()
    gerber_dir.rmdir()
    print(f"Tier 1: {len(files)} files zipped -> {zip_path}")
    return ok, zip_path, len(files)


def export_tier2_bom_cpl(cli, pcb, design_json_path, out_dir, stem):
    pos_csv = out_dir / f"{stem}_pos_raw.csv"
    ok = run([cli, "pcb", "export", "pos", "--output", str(pos_csv),
              "--format", "csv", "--units", "mm", "--side", "both", pcb])
    if not ok:
        return False, [], 0

    with open(design_json_path, encoding="utf-8") as f:
        design = json.load(f)
    comps = design.get("components", [])
    ref_key = "ref" if comps and "ref" in comps[0] else "designator"
    lcsc_by_ref = {c[ref_key]: c.get("lcsc", "") for c in comps}
    total = len(comps)
    missing = sorted(r for r, v in lcsc_by_ref.items() if not v)

    with open(pos_csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    pos_csv.unlink()

    # CPL: rename KiCad's columns to JLCPCB's expected header names.
    cpl_path = out_dir / f"{stem}_JLC_CPL.csv"
    with open(cpl_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for row in rows:
            layer = "Top" if row["Side"].strip().lower() == "top" else "Bottom"
            w.writerow([row["Ref"], row["PosX"], row["PosY"], layer, row["Rot"]])
    print(f"Tier 2: CPL written -> {cpl_path} ({len(rows)} placements)")

    # BOM: group by (Value, Footprint, LCSC), merge designators into one
    # comma-joined cell, split any group whose designator string would
    # exceed ~2048 chars (JLCPCB's known row-length limit, see
    # references/bouni-fab-details.md) into multiple rows under the same
    # LCSC part number.
    groups = defaultdict(list)
    for row in rows:
        ref = row["Ref"]
        key = (row["Val"], row["Package"], lcsc_by_ref.get(ref, ""))
        groups[key].append(ref)

    bom_path = out_dir / f"{stem}_JLC_BOM.csv"
    with open(bom_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part#"])
        for (val, footprint, lcsc), refs in sorted(groups.items()):
            refs = sorted(refs)
            chunk, chunk_len, chunks = [], 0, []
            for r in refs:
                add = len(r) + 2
                if chunk and chunk_len + add > 2000:
                    chunks.append(chunk)
                    chunk, chunk_len = [], 0
                chunk.append(r)
                chunk_len += add
            if chunk:
                chunks.append(chunk)
            for c in chunks:
                w.writerow([val, ",".join(c), footprint, lcsc])
    print(f"Tier 2: BOM written -> {bom_path} ({len(groups)} distinct parts, "
          f"{sum(len(v) for v in groups.values())} placements)")

    if missing:
        missing_path = out_dir / f"{stem}_JLC_MISSING_LCSC.txt"
        missing_path.write_text(
            "以下位号在 design.json 中缺少 LCSC 料号，PCBA(SMT组装)订单会在"
            "嘉立创自动核对阶段失败；仅裸板打样(Gerber+钻孔)不受影响。\n\n"
            + "\n".join(missing), encoding="utf-8")
        print(f"WARN: {len(missing)}/{total} components missing LCSC part# "
              f"-> see {missing_path}")

    return ok, missing, total


def main():
    if len(sys.argv) != 4:
        print("usage: export_jlcpcb.py <project.kicad_pcb> <design.json> <out_dir>")
        return 2

    pcb, design_json_path, out_dir = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(pcb).stem

    kicad_root = find_kicad()
    if kicad_root is None:
        print("FAIL: run kicad_env.py first")
        return 1
    cli = str(cli_exe(bin_dir(kicad_root)))

    ok1, zip_path, n_files = export_tier1_gerbers(cli, pcb, out_dir, stem)
    ok2, missing, total = export_tier2_bom_cpl(cli, pcb, design_json_path, out_dir, stem)

    print()
    print(f"Tier 1 (裸板打样): {'PASS' if ok1 else 'FAIL'} -- {zip_path.name}, {n_files} 个文件")
    if missing:
        print(f"Tier 2 (PCBA组装): 文件已生成，但 {len(missing)}/{total} 个元件缺 LCSC 料号 -- "
              f"组装下单前必须补全")
    else:
        print(f"Tier 2 (PCBA组装): PASS -- {total}/{total} 个元件均有 LCSC 料号，BOM/CPL 可直接提交")

    if not ok1:
        return 1
    return 0 if not missing else 3  # 3 = tier1 ok, tier2 incomplete (not a hard failure)


if __name__ == "__main__":
    sys.exit(main())
