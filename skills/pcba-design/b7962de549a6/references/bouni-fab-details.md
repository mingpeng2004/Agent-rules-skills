# Manufacturing-output format details (distilled from Bouni/kicad-jlcpcb-tools)

Full analysis: `context/reference_bouni_kicad_jlcpcb_tools_analysis.md`.
This file extracts the actionable checklist for the O (manufacturing
export) gate; read the full analysis for code-level detail if implementing
any of these from scratch.

## P0 -- will actually cause a failed/wrong assembly if skipped

- **CPL/pick-and-place rotation correction.** JLCPCB's pick-and-place
  machine's rotation/origin convention for a given footprint does not
  always match KiCad's. If you're generating a CPL for SMT assembly (not
  just a bare-board Gerber order), check known rotation-correction tables
  (e.g. JLCKicadTools' `cpl_rotations_db.csv`) before trusting the exported
  rotation angle, especially for polarized/asymmetric parts. This project's
  `scripts/export_mfg.py` exports a plain KiCad position file -- if you add
  SMT-assembly ordering on top of it, add rotation correction before
  trusting the CPL.
- **BOM line-length limit.** JLCPCB rejects a BOM CSV row whose designator
  list exceeds roughly 2048 characters (a single LCSC part number shared
  by 100+ reference designators can hit this). If any one design has an
  unusually large group of identical parts, split the designator list into
  multiple rows under the same LCSC part number rather than one giant row.
- **Gerber filename convention.** Confirm the exported filenames match
  what your fab's upload parser expects (this varies by fab) before
  assuming a zip that opens fine locally will also parse correctly on the
  fab's side.

## P1 -- meaningfully improves quality, not launch-blocking

- **BOM part-consistency check**: flag if the same LCSC/manufacturer part
  number is assigned different `Value` fields across the design (usually a
  copy-paste error, e.g. a 10k and a 100k resistor both accidentally
  pointing at the same part number).
- **Assembly metadata**: pad count, through-hole vs. SMT, assembly process
  (useful for cost estimation and DFM review, not required for a bare Gerber
  order).
- **Gerber plot parameter checklist** -- confirm these match your fab's
  expectations before trusting a "looks right" Gerber:
  - plot component values/references on silkscreen or not (your call, but
    be deliberate)
  - subtract soldermask from silkscreen (avoids silkscreen printing over
    exposed pads)
  - use auxiliary origin
  - Gerber X2 format + net info included (helps some fabs' automated
    checking, harmless otherwise)
  - drill mark style, NPTH pad handling, tented-via settings

## P2 -- nice to have, not required for a working order

- Offline component database / local part cache (relevant only if building
  a sourcing/selection tool, not for a single design's fabrication).
- Pre/post generation hook scripts (e.g. auto git-commit after a
  successful export -- this project's git workflow does the commit
  manually per phase instead, which is equivalent for a single-designer
  session).
- Generation counter / "which attempt is this" tracking -- useful across a
  long iteration history; this project's `context/decisions.log` D-numbered
  entries serve the same purpose.

## Where this project stands today

`scripts/export_mfg.py` + `scripts/verify_output.py` cover the general
KiCad manufacturing export and verify layer count + row-count consistency
against design.json. `scripts/export_jlcpcb.py` (added 2026-07-23) covers
the **JLCPCB-specific** package: correct Protel-extension Gerbers, merged
Excellon drill, and a properly-columned BOM/CPL built from design.json's
LCSC field + the PCB's actual final placement. BOM line-splitting (the
~2048-char limit above) is implemented. **Rotation correction is
deliberately NOT implemented** -- no verified JLCPCB rotation-offset
database is vendored in this repo, and fabricating offset numbers without
a verified source would silently corrupt a real assembly order. Tell the
user to use JLCPCB's own CPL-preview step in their web order flow as the
verification gate instead.

## JLCPCB-specific naming/format facts (verified 2026-07-23 against this
project's KiCad 10.0.5 install + JLCPCB's own current help-center docs)

- **kicad-cli's Gerber export defaults already match what JLCPCB wants**:
  Protel filename extensions (`.gtl/.gbl/.g1/.g2/.gts/.gbs/.gto/.gbo/.gm1`
  etc.) and Gerber X2 format are both **on by default** -- you'd have to
  pass `--no-protel-ext`/`--no-x2` to turn them off. Confirmed via
  `kicad-cli pcb export gerbers --help` on this machine; do not add those
  flags for a JLCPCB order.
- **Drill file**: `--format excellon --drill-origin absolute
  --excellon-units mm --excellon-zeros-format decimal`, and do NOT pass
  `--excellon-separate-th` -- JLCPCB's standard multi-layer service wants
  PTH+NPTH merged into one file (separate files are for blind/buried-via
  boards, which their standard service doesn't support anyway; if DRC
  reports blind/buried vias, that's a stackup bug to fix first).
- **kicad-cli's raw `pos` export columns** (verified by running it):
  `Ref,Val,Package,PosX,PosY,Rot,Side` with `Side` values lowercase
  `top`/`bottom`. JLCPCB's CPL wants **different header names and a
  capitalized Layer value** -- `Designator,Mid X,Mid Y,Layer,Rotation`
  with `Layer` = `Top`/`Bottom`. This is a pure rename/reformat, not a
  data transformation, but it's easy to ship the wrong headers if you
  just point JLCPCB at KiCad's raw pos.csv -- `export_jlcpcb.py` does the
  rename.
- **JLCPCB's required BOM columns**: `Comment,Designator,Footprint,LCSC
  Part#`, with identical (value+footprint+LCSC) parts merged into one row
  and a comma-joined designator list -- not one row per component.
- **Gerber layer set for a JLCPCB order**: every copper layer used in the
  stackup (`F.Cu,In1.Cu,In2.Cu,...,B.Cu`) + `F.Paste,B.Paste` (needed only
  if ordering a stencil, harmless to always include) + `F.Silkscreen,
  B.Silkscreen` + `F.Mask,B.Mask` + `Edge.Cuts`. Excluding `F.Fab`/`B.Fab`
  (KiCad's assembly-drawing layers) and `User.*` layers from the
  submission set avoids confusing the fab's automated layer-count
  detection.
- Source: JLCPCB's own "How To Export BOM and CPL Files From KiCad 10"
  and "How to generate Gerber and Drill files in KiCad 9/10" help-center
  articles, plus this project's own `kicad-cli --help` output (2026-07-23).
