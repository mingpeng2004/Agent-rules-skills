#!/usr/bin/env python3
"""Manufacturing export (O layer). Wraps the kicad-cli invocations for
Gerbers + drill + pick-and-place + STEP + PDF + BOM, and zips the Gerber
set. Every flag here was verified against a real board in this project --
if you hit "At least one layer must be specified" on the pdf export, it's
because --layers is mandatory (unlike gerbers, which has sane defaults).

Usage: python export_mfg.py <project.kicad_pcb> <project.kicad_sch> <out_dir>
"""
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kicad_env import find_kicad, bin_dir, cli_exe  # noqa: E402

PDF_LAYERS = "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Silkscreen,B.Silkscreen,Edge.Cuts"
GERBER_EXTS = (".gtl", ".gbl", ".g1", ".g2", ".gta", ".gba", ".gtp", ".gbp",
               ".gto", ".gbo", ".gts", ".gbs", ".gm1", ".gbr", ".gbrjob")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(" ".join(str(c) for c in cmd))
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
    return r.returncode == 0


def main():
    if len(sys.argv) != 4:
        print("usage: export_mfg.py <project.kicad_pcb> <project.kicad_sch> <out_dir>")
        return 2

    pcb, sch, out_dir = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(pcb).stem

    kicad_root = find_kicad()
    if kicad_root is None:
        print("FAIL: run kicad_env.py first")
        return 1
    cli = str(cli_exe(bin_dir(kicad_root)))

    ok = True
    ok &= run([cli, "pcb", "export", "gerbers", "--output", f"{out_dir}/", pcb])
    ok &= run([cli, "pcb", "export", "drill", "--output", f"{out_dir}/", pcb])
    ok &= run([cli, "pcb", "export", "pos", "--output", f"{out_dir}/{stem}-pos.csv",
               "--format", "csv", "--units", "mm", pcb])
    ok &= run([cli, "pcb", "export", "step", "--output", f"{out_dir}/{stem}.step", "--force", pcb])
    ok &= run([cli, "pcb", "export", "pdf", "--output", f"{out_dir}/{stem}.pdf",
               "--layers", PDF_LAYERS, pcb])
    ok &= run([cli, "sch", "export", "bom", "--output", f"{out_dir}/{stem}_BOM.csv",
               "--fields", "Reference,Value,Footprint,Datasheet", sch])

    gerber_files = [f for f in out_dir.iterdir() if f.suffix in GERBER_EXTS]
    zip_path = out_dir / f"{stem}_Gerber.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in gerber_files:
            zf.write(f, f.name)
    print(f"zipped {len(gerber_files)} gerber files -> {zip_path}")

    if not ok:
        print("FAIL: one or more export steps failed, see output above")
        return 1
    print(f"PASS: manufacturing outputs written to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
