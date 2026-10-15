#!/usr/bin/env python3
"""Electrical review (ELEC layer) -- the check that would have caught the
worst bug found in this project's history: design.json declaring a net on
one pin number while the schematic/PCB actually wired a different pin.

kicad-cli's ERC/DRC only verify *internal* consistency (does every pin have
*some* label attached) -- they cannot know whether that label is the
*correct* one, because they don't cross-reference your design intent
(design.json). This script does that cross-reference directly:

1. PCB pad-net audit: for every footprint pad, does its `(net "NAME")`
   clause match what design.json declares for that ref+pin? (Catches wrong
   net assignments regardless of geometry -- this is the fast, reliable
   check, since PCB pads are looked up by pad number, not coordinates.)

2. Schematic label-position audit: for symbol types with a known pin
   geometry table (see PIN_TABLES below), computes each pin's real-world
   coordinate from the symbol's lib_symbols definition and checks whether
   a label with the correct net name sits exactly there. Unknown symbol
   types are skipped with a warning, not silently assumed correct.

Usage: python elec_review.py <design.json> <project.kicad_pcb> [project.kicad_sch]
Exit code 0 = no mismatches found.
"""
import re
import sys
import json
from pathlib import Path


# Local pin-offset tables (mm, symbol-local coordinates before placement).
# Extend this as new symbol types are used. Missing a type here just means
# the schematic-side geometry check is skipped for it -- it does NOT skip
# the (more important) PCB pad-net check, which needs no geometry at all.
PIN_TABLES = {
    "Conn_01x03": {1: (-5.08, 2.54), 2: (-5.08, 0), 3: (-5.08, -2.54)},
    "Conn_01x04": {1: (-5.08, 2.54), 2: (-5.08, 0), 3: (-5.08, -2.54), 4: (-5.08, -5.08)},
    "Conn_02x04_Odd_Even": {
        1: (-5.08, 2.54), 2: (7.62, 2.54), 3: (-5.08, 0), 4: (7.62, 0),
        5: (-5.08, -2.54), 6: (7.62, -2.54), 7: (-5.08, -5.08), 8: (7.62, -5.08),
    },
    "Conn_02x05_Odd_Even": {
        1: (-5.08, 5.08), 2: (7.62, 5.08), 3: (-5.08, 2.54), 4: (7.62, 2.54),
        5: (-5.08, 0), 6: (7.62, 0), 7: (-5.08, -2.54), 8: (7.62, -2.54),
        9: (-5.08, -5.08), 10: (7.62, -5.08),
    },
    "Conn_02x10_Odd_Even": {
        1: (-5.08, 10.16), 2: (7.62, 10.16), 3: (-5.08, 7.62), 4: (7.62, 7.62),
        5: (-5.08, 5.08), 6: (7.62, 5.08), 7: (-5.08, 2.54), 8: (7.62, 2.54),
        9: (-5.08, 0), 10: (7.62, 0), 11: (-5.08, -2.54), 12: (7.62, -2.54),
        13: (-5.08, -5.08), 14: (7.62, -5.08), 15: (-5.08, -7.62), 16: (7.62, -7.62),
        17: (-5.08, -10.16), 18: (7.62, -10.16), 19: (-5.08, -12.7), 20: (7.62, -12.7),
    },
    "R": {1: (0, 3.81), 2: (0, -3.81)},
    "C": {1: (0, 3.81), 2: (0, -3.81)},
    "L": {1: (0, 3.81), 2: (0, -3.81)},
}


def load_pinmap(design):
    pinmap = {}
    for n in design["nets"]:
        for pad in n["pads"]:
            ref, pin = pad.split(".")
            pinmap[(ref, pin)] = n["name"]
    return pinmap


def block_span(text, start):
    depth = 0
    i = start
    in_str = False
    while i < len(text):
        c = text[i]
        if c == '"':
            in_str = not in_str
        elif not in_str:
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    raise RuntimeError("unbalanced parens")


def audit_pcb_pads(pcb_text, pinmap):
    problems = []
    for fm in re.finditer(r'\(footprint "', pcb_text):
        fp_start = fm.start()
        fp_end = block_span(pcb_text, fp_start)
        fp_block = pcb_text[fp_start:fp_end]
        refm = re.search(r'\(property "Reference" "([^"]+)"', fp_block)
        if not refm:
            continue
        ref = refm.group(1)
        for pm in re.finditer(r'\(pad "(\w+)" ', fp_block):
            pin = pm.group(1)
            if pin == "":
                continue
            pad_start = pm.start()
            pad_end = block_span(fp_block, pad_start)
            pad_block = fp_block[pad_start:pad_end]
            netm = re.search(r'\(net "([^"]*)"\)', pad_block)
            current = netm.group(1) if netm else None
            desired = pinmap.get((ref, pin))
            if current != desired:
                problems.append(
                    f"PCB pad {ref}.{pin}: has net {current!r}, design.json wants {desired!r}"
                )
    return problems


def audit_schematic_labels(sch_text, pinmap):
    problems = []
    skipped_types = set()

    instances = {}
    pat = re.compile(
        r'\(symbol \(lib_id "([^"]+)"\) \(at ([\-\d.]+) ([\-\d.]+) (\d+)\)'
        r'[\s\S]*?\(property "Reference" "([^"]+)"'
    )
    for m in pat.finditer(sch_text):
        lib, x, y, rot, ref = m.groups()
        libtype = lib.split(":")[-1]
        if libtype not in PIN_TABLES:
            skipped_types.add(libtype)
            continue
        if rot != "0":
            problems.append(f"schematic symbol {ref} has rotation {rot}, geometry check assumes 0 -- skipping")
            continue
        instances[ref] = (libtype, float(x), float(y))

    labels = {}
    for m in re.finditer(r'\(label "([^"]+)" \(at ([\-\d.]+) ([\-\d.]+)', sch_text):
        name, x, y = m.group(1), round(float(m.group(2)), 2), round(float(m.group(3)), 2)
        labels.setdefault((x, y), []).append(name)

    for ref, (libtype, ox, oy) in instances.items():
        for pin, (lx, ly) in PIN_TABLES[libtype].items():
            wx, wy = round(ox + lx, 2), round(oy - ly, 2)
            found = labels.get((wx, wy), [])
            desired = pinmap.get((ref, str(pin)))
            ok = (desired in found) if desired else (not found)
            if not ok:
                problems.append(
                    f"schematic {ref} pin {pin} @({wx},{wy}): has {found}, design.json wants {desired!r}"
                )

    if skipped_types:
        print(f"NOTE: schematic geometry check skipped for symbol types with no pin table: {sorted(skipped_types)}")
        print("      (add them to PIN_TABLES in this script -- extract from the .kicad_sch lib_symbols block)")

    return problems


def main():
    if len(sys.argv) < 3:
        print("usage: elec_review.py <design.json> <project.kicad_pcb> [project.kicad_sch]")
        return 2

    design = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    pinmap = load_pinmap(design)
    pcb_text = Path(sys.argv[2]).read_text(encoding="utf-8")

    problems = audit_pcb_pads(pcb_text, pinmap)
    print(f"--- PCB pad-net audit: {len(problems)} mismatch(es) ---")
    for p in problems:
        print(" -", p)

    if len(sys.argv) > 3:
        sch_text = Path(sys.argv[3]).read_text(encoding="utf-8")
        sch_problems = audit_schematic_labels(sch_text, pinmap)
        print(f"--- Schematic label-position audit: {len(sch_problems)} mismatch(es) ---")
        for p in sch_problems:
            print(" -", p)
        problems += sch_problems

    if problems:
        print(f"\nFAIL: {len(problems)} electrical mismatch(es) between design.json and the actual files")
        return 1

    print("\nPASS: every pad/pin matches design.json's declared net")
    return 0


if __name__ == "__main__":
    sys.exit(main())
