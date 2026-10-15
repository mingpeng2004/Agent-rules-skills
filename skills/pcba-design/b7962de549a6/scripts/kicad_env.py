#!/usr/bin/env python3
"""Environment gate (E layer). Locates KiCad 10+, verifies kicad-cli works,
and initializes the global sym-lib-table/fp-lib-table if this is the first
time KiCad has run on this machine (a first-run KiCad install has no global
library tables, which pollutes every later ERC/DRC run with ~100+ bogus
lib_symbol_issues/footprint_link_issues warnings that look like design
defects but are pure environment noise).

Exit code 0 = ready to proceed. Non-zero = fix printed problem first.
"""
import json
import os
import platform
import subprocess
import sys
from pathlib import Path


def find_kicad_windows():
    candidates = []
    for base in (
        os.environ.get("LOCALAPPDATA", ""),
        os.environ.get("PROGRAMFILES", ""),
        os.environ.get("PROGRAMFILES(X86)", ""),
    ):
        if not base:
            continue
        p = Path(base) / "Programs" / "KiCad"
        if p.is_dir():
            candidates.append(p)
        p2 = Path(base) / "KiCad"
        if p2.is_dir():
            candidates.append(p2)
    versions = []
    for c in candidates:
        for child in c.glob("*"):
            if (child / "bin" / "kicad-cli.exe").exists():
                versions.append(child)
    return sorted(versions, reverse=True)


def find_kicad():
    system = platform.system()
    if system == "Windows":
        found = find_kicad_windows()
        return found[0] if found else None
    for p in ("/usr/bin", "/usr/local/bin", "/Applications/KiCad/KiCad.app/Contents/MacOS"):
        if (Path(p) / "kicad-cli").exists():
            return Path(p).parent
    return None


def bin_dir(kicad_root):
    system = platform.system()
    if system == "Windows":
        return kicad_root / "bin"
    return kicad_root


def cli_exe(bindir):
    system = platform.system()
    return bindir / ("kicad-cli.exe" if system == "Windows" else "kicad-cli")


def python_exe(bindir):
    system = platform.system()
    return bindir / ("python.exe" if system == "Windows" else "python3")


def ensure_global_lib_tables(kicad_root, bindir):
    """First-run KiCad installs on Windows do not auto-populate
    %APPDATA%/kicad/<ver>/sym-lib-table + fp-lib-table until the GUI is
    launched once. Headless/CLI-only usage never triggers that, so we
    build correct tables ourselves from the bundled symbol/footprint dirs.
    """
    system = platform.system()
    if system != "Windows":
        return True, "not Windows, skipping (assumes tables already exist)"

    version = kicad_root.name  # e.g. "10.0"
    cfg_dir = Path(os.environ["APPDATA"]) / "kicad" / version
    sym_table = cfg_dir / "sym-lib-table"
    fp_table = cfg_dir / "fp-lib-table"
    if sym_table.exists() and fp_table.exists():
        # sanity: must actually list "Device" and not just be a stub
        content = sym_table.read_text(encoding="utf-8", errors="ignore")
        if '"Device"' in content:
            return True, "already initialized"

    sym_dir = kicad_root / "share" / "kicad" / "symbols"
    fp_dir = kicad_root / "share" / "kicad" / "footprints"
    if not sym_dir.is_dir() or not fp_dir.is_dir():
        return False, f"cannot find bundled libraries under {kicad_root}/share/kicad/"

    cfg_dir.mkdir(parents=True, exist_ok=True)
    sym_libs = sorted(f.stem for f in sym_dir.glob("*.kicad_sym"))
    fp_libs = sorted(f.stem for f in fp_dir.glob("*.pretty"))

    with open(sym_table, "w", encoding="utf-8") as f:
        f.write("(sym_lib_table\n  (version 7)\n")
        for name in sym_libs:
            f.write(
                f'  (lib (name "{name}")(type "KiCad")'
                f'(uri "${{KICAD{version.split(".")[0]}_SYMBOL_DIR}}/{name}.kicad_sym")'
                f'(options "")(descr ""))\n'
            )
        f.write(")\n")

    with open(fp_table, "w", encoding="utf-8") as f:
        f.write("(fp_lib_table\n  (version 7)\n")
        for name in fp_libs:
            f.write(
                f'  (lib (name "{name}")(type "KiCad")'
                f'(uri "${{KICAD{version.split(".")[0]}_FOOTPRINT_DIR}}/{name}.pretty")'
                f'(options "")(descr ""))\n'
            )
        f.write(")\n")

    return True, f"initialized {len(sym_libs)} symbol libs + {len(fp_libs)} footprint libs"


def main():
    kicad_root = find_kicad()
    if kicad_root is None:
        print("FAIL: KiCad 10+ not found. Install it, or if it's in a non-standard")
        print("location, edit find_kicad_windows()/find_kicad() in this script.")
        return 1

    bindir = bin_dir(kicad_root)
    cli = cli_exe(bindir)
    py = python_exe(bindir)

    if not cli.exists():
        print(f"FAIL: kicad-cli not found at {cli}")
        return 1

    result = subprocess.run([str(cli), "--version"], capture_output=True, text=True)
    version = result.stdout.strip()
    print(f"OK: kicad-cli {version} at {cli}")

    ok, msg = ensure_global_lib_tables(kicad_root, bindir)
    print(("OK" if ok else "FAIL") + f": global lib tables -- {msg}")
    if not ok:
        return 1

    env = {
        "kicad_root": str(kicad_root),
        "kicad_cli": str(cli),
        "kicad_python": str(py) if py.exists() else None,
        "version": version,
    }
    out_path = Path(__file__).resolve().parent.parent / "kicad_env.json"
    out_path.write_text(json.dumps(env, indent=2), encoding="utf-8")
    print(f"OK: wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
