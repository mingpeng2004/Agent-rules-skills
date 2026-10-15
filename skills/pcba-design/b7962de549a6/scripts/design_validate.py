#!/usr/bin/env python3
"""Design-data gate (I layer). Validates design.json before anything is
generated from it -- catching structural problems here is far cheaper than
finding them after they've propagated into a schematic and a PCB.

Usage: python design_validate.py <path-to-design.json>
Exit code 0 = all checks passed. Non-zero = see printed FAIL lines.
"""
import json
import re
import sys


REQUIRED_TOP_KEYS = ["meta", "board", "components", "nets"]


def check(design):
    problems = []

    # I-01: structural completeness
    for key in REQUIRED_TOP_KEYS:
        if key not in design:
            problems.append(f"I-01 missing top-level key: {key}")

    if "board" in design:
        b = design["board"]
        for k in ("width_mm", "height_mm", "layers"):
            if k not in b:
                problems.append(f"I-01 board missing key: {k}")

    components = design.get("components", [])
    refs = [c.get("ref") for c in components]

    # I-05: reference designator uniqueness + non-empty value
    seen = set()
    for c in components:
        ref = c.get("ref")
        if not ref:
            problems.append(f"I-05 component missing ref: {c}")
            continue
        if ref in seen:
            problems.append(f"I-05 duplicate ref: {ref}")
        seen.add(ref)
        if not c.get("value"):
            problems.append(f"I-05 component {ref} has empty value")
        if not c.get("footprint"):
            problems.append(f"I-02 component {ref} missing footprint")

    # I-06: net name legality + pad reference format "REF.PIN"
    ref_set = set(refs)
    pad_pattern = re.compile(r"^[A-Za-z0-9_]+\.[A-Za-z0-9_]+$")
    net_names = set()
    for n in design.get("nets", []):
        name = n.get("name", "")
        if not name or not re.match(r"^[A-Za-z0-9_+\-]+$", name):
            problems.append(f"I-06 illegal net name: {name!r}")
        if name in net_names:
            problems.append(f"I-06 duplicate net declaration: {name}")
        net_names.add(name)

        for pad in n.get("pads", []):
            if not pad_pattern.match(pad):
                problems.append(f"I-04 malformed pad reference in net {name}: {pad!r}")
                continue
            ref = pad.split(".")[0]
            if ref not in ref_set and ref_set:
                problems.append(f"I-04 net {name} references unknown component: {ref}")

    return problems


def main():
    if len(sys.argv) != 2:
        print("usage: design_validate.py <design.json>")
        return 2

    with open(sys.argv[1], encoding="utf-8") as f:
        design = json.load(f)

    problems = check(design)
    if problems:
        print(f"FAIL: {len(problems)} problem(s)")
        for p in problems:
            print(" -", p)
        return 1

    n_components = len(design.get("components", []))
    n_nets = len(design.get("nets", []))
    print(f"PASS: {n_components} components, {n_nets} nets, structure OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
