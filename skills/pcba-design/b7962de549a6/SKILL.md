---
name: pcba-design
description: Closed-loop KiCad PCBA design workflow (design.json -> schematic -> layout -> routing -> manufacturing) with real, run-it-yourself evidence gates. Use whenever creating, reviewing, or finishing a KiCad-based PCB design -- especially when asked to verify a design's readiness for fabrication ("能不能打样", "DRC 过了吗", "check the layout"), when a design.json / schematic / PCB net mismatch is suspected, or when a board needs autorouting.
---

# pcba-design

## Why this file exists (read this first)

This skill replaces a version ("pcba-design skill v5.1") that was referenced
throughout this project's `docs/` and `context/decisions.log` but **never
actually existed in this repository**. It lived only on a different
machine/user account. Every "PASS" claim produced by that missing skill was
unverifiable here, and a from-scratch audit found that its output was
wrong in ways that would have bricked the board (see
`references/proven-lessons.md` for the full story). This rewrite fixes the
root cause: **the skill now lives in the project repo, next to the design it
governs, with runnable scripts instead of a description of scripts that
don't exist.**

## The one rule that matters more than any other

**Never state a gate result without the command you ran to get it.**
"ERC passes" is not a finding. `kicad-cli sch erc --format json --output
evidence/erc.json ...` followed by "0 errors, evidence at evidence/erc.json"
is a finding. If you catch yourself writing "引脚映射已核对" or "PASS" without
a script output or a specific datasheet page next to it, stop and go run the
check. This project's own history is the cautionary tale: a prior session's
schematic had **100% of its 127 pin labels in the wrong position** and a
critical IC's pin numbers came from the wrong column of its own datasheet --
both invisible to a human skimming the file, both caught only by actually
running the cross-check scripts below.

## Environment setup (run once per machine)

```
python scripts/kicad_env.py
```

Finds KiCad 10+, verifies `kicad-cli` works, and initializes the global
`sym-lib-table`/`fp-lib-table` if this is a fresh KiCad install that's never
been launched through the GUI (headless-only usage never triggers KiCad's
own first-run setup, and every ERC/DRC run before this fix produces ~100
bogus `lib_symbol_issues`/`footprint_link_issues` warnings that look like
design defects but are pure environment noise). Idempotent -- safe to run
every session.

## The closed loop

```
I  design.json gate        scripts/design_validate.py
S  schematic ERC           scripts/run_checks.py (sch half)
L  placement (manual/AI)   -- no script, see references/keitark-checklist.md
R  routing + DRC           scripts/run_checks.py (pcb half) + Freerouting (below)
ELEC  cross-check          scripts/elec_review.py   <- the gate that catches wrong-pin bugs
O  manufacturing export    scripts/export_mfg.py + scripts/verify_output.py
O.JLC  JLCPCB submission    scripts/export_jlcpcb.py (fab-specific, two gated tiers)
F  final report            write it by hand, cite every evidence file
```

### I -- design.json is the single source of truth

Schema: `{meta, board, components, nets, ...}`. Every net's `pads` list is an
array of `"REF.PIN"` strings using **the pin numbers of the package actually
being used** (see the QFN20/SOP16 warning below -- this is the single most
consequential thing to get right).

```
python scripts/design_validate.py context/design/design.json
```

Checks structural completeness, ref uniqueness, footprint presence, and pad
reference validity (I-01 through I-06). This does NOT check that pin numbers
are electrically correct against a datasheet -- that's a human/AI judgment
call informed by the datasheet, see below.

**Multi-package datasheets are a trap.** If an IC ships in more than one
package (e.g. TSSOP20 / QFN20 / SOP16 / SOP8 for the same die), its datasheet
often prints one merged pin table with a column per package. It is very easy
to read the wrong column, especially when the columns aren't clearly
labeled or the OCR/extraction of a scanned datasheet has garbled the layout.
**Before trusting any pin number for a multi-package part, verify which
package is actually ordered (check the footprint name, e.g.
`VQFN-20-1EP_...`) and cross-reference the pin count/column against an
independent source (official pinout diagram image, or a second web source)
-- do not trust a single merged table read in isolation.** This exact
mistake (CH32V003 SOP16 column used for a QFN20 part) would have tied the
MCU's real NRST pin to GND, permanently holding it in reset.

### S -- schematic ERC

```
python scripts/run_checks.py project.kicad_sch project.kicad_pcb --waive TYPE=N ...
```

Runs `kicad-cli sch erc --severity-all` and `kicad-cli pcb drc
--severity-all`, parses both, and only exits 0 if unwaived violations are
zero. **Waivers must be passed explicitly and by type+count** -- the script
prints them so they're visible in the transcript/report, never silently
absorbed. A waiver is not "ignore this category forever"; it's "I looked at
these N specific items and they're acceptable, here's why" written in your
final report.

Generic connector placeholder symbols (`Conn_02x10_Odd_Even` etc. used to
represent an IC's pins without drawing a proper library symbol) are an
acceptable shortcut for netlist correctness, but every pin still needs
either a correctly-named net label at its exact coordinate or an explicit
no-connect flag -- ERC's `pin_not_connected` exists precisely to catch the
ones you forgot.

### L -- placement

No script here for the placement decision itself; this is a design
judgment call. See `references/keitark-checklist.md` for a placement
review checklist (architecture -> critical local decoupling -> layer
strategy -> power planes -> manufacturing -> visual pass) distilled from a
much more checklist-driven sibling project. Key structural fact learned
this session: **a board's schematic can pass ERC perfectly while every
single pin is wired to the wrong physical location**, because ERC only
checks internal consistency of the schematic file, not whether it matches
your design intent. Placement/labeling correctness must be checked
against design.json directly -- see the ELEC gate below, don't skip it
because ERC was green.

**There IS a script for one specific, easy-to-miss placement defect:**
whether a component's own reference designator text will be physically
hidden under itself (or a neighbor) once the part is soldered down.
kicad-cli's DRC has no rule for this -- `silk_overlap`/`silk_over_copper`
only catch a reference overlapping its own outline graphic or clipping a
pad, a much narrower condition than "sits inside the part's real
footprint." On a real 37-component board, 6 references were sitting fully
inside their own part's body and would have been unreadable after
assembly -- DRC was clean the whole time.

```
python scripts/check_silkscreen.py project.kicad_pcb          # report
python scripts/check_silkscreen.py project.kicad_pcb --fix    # relocate
```

Run this whenever placement changes, not just once at the end -- a
component move that clears one collision can create another. `--fix`
falls back to "minimize overlap area" on a dense board where no position
is perfectly clear (verified: 3 of 6 flagged parts on the reference board
needed this fallback); always re-run `run_checks.py` afterward since
relocating text can graze a neighbor's silkscreen outline (a much more
minor, cosmetic-only DRC item, not a "hidden identifier" problem).

### R -- routing

Do not hand-write a routing algorithm. Every attempt at that in this
project's history (14 separate scripts: A*, Manhattan, corridor, safe-via-
grid, chain routing, ...) failed to converge on a board denser than roughly
20x20mm with modern fine-pitch parts. Use a real autorouter:

**If a board has persistent unrouted gaps and the board outline is
negotiable, test enlarging it before spending more effort on routing
algorithms.** On this project each +1mm of board width produced a
measurable, monotonic drop in unrouted nets (18mm: 6-7 unrouted, 19mm:
2-3, 20mm: 1, out of 83 nets) -- a far higher-leverage lever than tuning a
router once a board is already this dense. Test empirically (resize
outline + zone outlines keeping the same edge margin, rip up, re-route,
compare) rather than guessing; it takes minutes per size point. This is a
constraint-negotiation question for the user, not a decision to make
alone -- board size is very often a locked/hard requirement (check
`context/origin.md` / `context/north_star.md` before assuming it's
negotiable), and changing it requires the same architecture-review
discipline as any other hard-constraint change.

**Never trust even a "correct" autorouter's output without running the
DRC gate.** On this project, Freerouting's own deterministic output once
produced a real short between two nets on a fine-pitch part (0.65mm pin
pitch) despite looking like a near-perfect result (only 1 net left
unrouted). This was the first short in the project's history produced by
a properly-configured industry tool rather than a hand-written script --
proof that "used the right tool" is not a substitute for checking the
result.

**Fixing a localized defect on an otherwise fully-routed board: surgical
removal, not a net-wide re-route.** Once the vast majority of nets are
routed, very little free channel space remains -- re-routing an entire
net from scratch (even one that worked before) often finds *no path at
all*. Instead: use the DRC violation coordinates to find the defect's
bounding box, remove only the track segments inside it (preserving the
rest of that net's routing), then use `finish_gaps.py` to reconnect the
resulting small local gap.

```
# 1. rip up existing copper (keep footprint placement + zone definitions)
#    then export while zones are UNFILLED (filled zones confuse Freerouting's
#    obstacle map and make re-routing attempts worse, not better -- verified
#    empirically this session)
python -c "import pcbnew; b=pcbnew.LoadBoard('project.kicad_pcb'); [z.UnFill() for z in b.Zones()]; pcbnew.ExportSpecctraDSN(b, 'project.dsn')"

# 2. route (headless, no GUI needed)
java -Djava.awt.headless=true -jar freerouting.jar --gui.enabled=false \
     -de project.dsn -do project.ses -mp 200 -mt 4

# 3. import back and refill zones
python -c "import pcbnew; b=pcbnew.LoadBoard('project.kicad_pcb'); pcbnew.ImportSpecctraSES(b,'project.ses'); pcbnew.SaveBoard('project.kicad_pcb', b)"
python -c "import pcbnew; b=pcbnew.LoadBoard('project.kicad_pcb'); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); pcbnew.SaveBoard('project.kicad_pcb', b)"
```

Freerouting needs **JRE 21+** (v2.2.x ships class files JRE 21 can't load;
JRE 25 is what was verified working this session). A portable JRE zip
(no install/admin needed) plus `freerouting-<ver>.jar` from GitHub Releases
is sufficient -- see `references/proven-lessons.md` for exact download
commands.

**If a handful of nets remain unrouted after Freerouting converges**
(it prints "auto-router cannot make further progress" or the score stops
improving across several passes), do not try to close them with hand-placed
straight tracks/vias at the reported coordinates -- on a dense board this
reliably introduces new shorts (verified: straight lines and two different
Freerouting "continue" strategies all made things worse on this project).

Instead try `scripts/finish_gaps.py`, an obstacle-aware A* router built and
verified this session:

```
python scripts/finish_gaps.py project.kicad_pcb gaps.json
```

where `gaps.json` is a list of `{"net", "ax","ay","alayer", "bx","by","blayer"}`
(coordinates in PCB mm, same frame as kicad-cli's DRC JSON). It models every
pad as its actual rotated rectangle (not a crude circumscribed circle) and
checks via placement against all 4 copper layers (vias span every layer,
and inner layers on a real board may carry signal traces mixed with plane
pours, not just pure fill). On this project it closed 2 of 7 remaining gaps
cleanly. **Always re-run `run_checks.py` afterward** -- commit only the
gaps it actually reports success on.

If it reports "no path found" after its search, that's a real, trustworthy
result (verified against 5 gaps on this project that stayed unroutable even
with a 6mm search radius and 150,000 iterations) -- it means the gap needs
either (a) a real interactive push-and-shove router (KiCad GUI, `X` key,
Shove mode, which can temporarily nudge a neighboring track out of the way)
or (b) a placement adjustment. Accept that and document it precisely
(exact coordinates, exact blocking geometry) as a handoff item. Silently
declaring victory or blindly scripting a "fix" that introduces new shorts
is not acceptable -- see `references/proven-lessons.md` for the full
progression of what was tried and why each step improved on the last.

### ELEC -- the cross-check gate (do not skip this one)

```
python scripts/elec_review.py context/design/design.json project.kicad_pcb project.kicad_sch
```

This is the gate that actually catches wrong-pin-number bugs, because it's
the only one that compares the PCB/schematic against your stated design
intent (design.json) rather than just checking internal file consistency.
Two independent checks:
1. **PCB pad-net audit** (fast, geometry-free): for every footprint pad,
   does its `(net "NAME")` match what design.json declares for that ref+pin?
2. **Schematic label-position audit**: computes each pin's real-world
   coordinate from the symbol library's own pin-offset table and checks a
   correctly-named label sits exactly there.

Run this **every time design.json changes**, and definitely before ever
writing "引脚映射已核对" in a report. `PIN_TABLES` in the script only covers
symbol types seen in this project so far -- extend it (extract local pin
offsets from the `.kicad_sch` file's own `lib_symbols` block, formula is
`world = symbol_origin + local_offset` with Y negated) before trusting the
schematic-side check on a new symbol type; the PCB-side check needs no
extension and always works.

**Verifying electrical performance (voltage stability, noise, drift) when
you don't have SPICE models.** A user may ask you to "simulate" and
confirm things like voltage stability or a drift-mitigation strategy.
True transistor-level SPICE needs vendor models that usually don't exist
for cheaper/regional parts (no public SPICE model for a lot of
budget ADCs/LDOs), and even when a model exists (e.g. TI parts), getting
it and a working ngspice binary onto a fresh machine mid-session can
easily fail or stall. Rather than skip the request or silently produce a
low-confidence answer, do a **datasheet-parameter analytical
verification** instead, and say explicitly that's what you did (don't
imply a simulation ran when it didn't):

1. Trace the actual power/reference net topology from design.json (which
   pins share which rail) -- this is exact, not an approximation, and
   often the most important finding (e.g., confirming a ratiometric
   reference actually shares a rail with the excitation it's supposed to
   track, at the netlist level, not just in the design doc's prose).
2. Pull the specific numbers you need from the datasheets already in
   `archive/datasheets/` -- PSRR, line/load regulation, dropout, output
   noise, internal reference tolerance. These are real measured
   specifications, not guesses, and let you compute headroom, ripple
   attenuation, and noise budgets by hand/Python for a linear system
   (regulators + resistor/cap networks have no large-signal nonlinearity
   worth a transient sim for this purpose).
3. For a ratiometric or matched-pair architecture specifically, the
   dominant residual error source is almost always **ratio tracking**
   (how well two components' temperature coefficients track EACH OTHER),
   not either part's individual tolerance -- an individually-specified
   "5ppm/°C" resistor tells you nothing about how two of them track
   relative to each other unless they're sold as a matched network with
   its own tracking spec (often ±1ppm/°C or better on a purpose-built
   network vs. unspecified, commonly 1-3ppm/°C in practice, for two
   discrete parts from the same batch). If a matched network was
   downgraded to discrete parts for a supply-chain reason (check
   `context/decisions.log` for exactly this kind of compromise), flag it
   by name and quantify the estimated residual error against the
   project's actual acceptance target, not just qualitatively.
4. Recommend the review of a decision, not just a fix: your options are
   usually (a) revert to the better part now if it doesn't disrupt
   anything already locked in, (b) flag the relevant test (temperature
   cycling, etc.) as the deciding gate before deciding whether a hardware
   change is even needed, (c) firmware/software compensation as a fallback
   that doesn't require a hardware change. Present these with their real
   tradeoffs (a firmware fix needs the error characterized first via
   testing; a hardware fix on an already-fully-routed dense board risks
   the routing itself, see the R section above) rather than picking one
   silently.

### Ground/copper pour as a standard finishing step

A 4-layer board with inner GND/power planes can still have bare substrate
on the outer (F.Cu/B.Cu) layers outside the routed traces -- the inner
planes don't automatically extend outward. For EMI/anti-interference,
pour GND zones on every layer that doesn't already have a dedicated plane,
not just the inner ones. This is safe to do **after** routing is complete
and verified (KiCad's zone filler automatically keeps the pour clear of
all non-GND copper with the configured clearance, verified on a real
board: 0 new DRC violations before/after adding two new GND zones to an
already fully-routed board). Match the new zone's clearance/thermal-relief
settings to any existing plane zones so behavior is consistent across
layers.

**Do not add a dense stitching-via grid in the same pass without careful
margin accounting.** A quick attempt to also add a regular via grid to tie
the new outer pours to the inner planes introduced board-edge-clearance
and hole-to-hole violations from insufficient margin in the placement
check -- the pour itself (which already grounds through every existing
GND pad and via) is the safe, valuable deliverable; a proper stitching
pass needs the same rigor as any other via placement (see
`references/proven-lessons.md`'s obstacle-aware routing lessons) and is
worth doing as its own separate, verified step, not bundled in.

### O -- manufacturing export + verification

```
python scripts/export_mfg.py project.kicad_pcb project.kicad_sch out_dir/
python scripts/verify_output.py context/design/design.json out_dir/ project_stem
```

`export_mfg.py` wraps `kicad-cli pcb export {gerbers,drill,pos,step,pdf}` +
BOM + zip with the flags verified to actually work (the PDF export in
particular needs an explicit `--layers` list, unlike gerbers). Never trust
the exporter's exit code alone -- `verify_output.py` re-reads the outputs
and checks layer count / BOM row count / position-file row count against
design.json.

### O.JLC -- JLCPCB (嘉立创) standard submission package

If the target fab is JLCPCB specifically (very common for this skill's
users), "manufacturing export" is not one deliverable, it's **two
independently-gated tiers** -- do not conflate them:

**Tier 1 -- bare PCB fab (always producible once DRC is clean):**
- One zip containing Gerbers (RS-274X, Protel filename extensions,
  X2 attributes) for every copper/mask/silk layer + Edge.Cuts, plus a
  merged Excellon drill file (PTH+NPTH together unless the board actually
  uses blind/buried vias, which JLCPCB's standard 2/4/6-layer service does
  not support -- if DRC ever reports blind/buried vias, that's a stackup
  error to fix, not a file-format choice).
- kicad-cli's **defaults already match JLCPCB's own published KiCad 9/10
  guide**: Protel extensions and X2 format are both ON by default; you'd
  have to pass `--no-protel-ext`/`--no-x2` to turn them off, which you
  should NOT do for JLCPCB. Verified against this project's kicad-cli
  10.0.5 install (`kicad-cli pcb export gerbers --help`).
- Gerber layer list for a JLCPCB order: `F.Cu,In1.Cu,In2.Cu,...,B.Cu,
  F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts`.
  Do **not** include `F.Fab`/`B.Fab` (assembly-drawing-only layers, not
  a fab input) or `User.*` layers in the submitted Gerber set.

**Tier 2 -- PCBA assembly service add-on (has a hard completeness gate):**
- `BOM.csv` columns exactly: `Comment,Designator,Footprint,LCSC Part#`
  (JLCPCB's own required minimum set). Merge identical
  (value+footprint+LCSC) parts into one row with a comma-joined
  designator list -- do not emit one row per component, JLCPCB's
  assembly pricing and part-matching both key off this grouping.
- `CPL.csv` (Centroid/pick-and-place) columns exactly: `Designator,Mid X,
  Mid Y,Layer,Rotation`, values in **mm**, `Layer` as the literal strings
  `Top`/`Bottom` (not KiCad's lowercase `top`/`bottom`). Build this from
  the **actual final PCB placement** (`kicad-cli pcb export pos`), not
  from design.json -- design.json has no layout/rotation data, the .kicad_pcb
  file is the only ground truth for where a part actually ended up.
- **Hard gate: every BOM line needs a real LCSC part number.** JLCPCB's
  own automated PCBA order flow rejects/holds any line without one --
  there is no partial-credit path. If design.json has components with an
  empty `lcsc` field, Tier 2 is **not ready**, full stop -- don't round
  this up to "mostly done" in a report. Print/report the exact missing
  refs so the user can go source them; do not guess a placeholder part
  number.
- **Rotation is not auto-corrected by this skill.** JLCPCB's
  pick-and-place convention doesn't always match KiCad's for
  polarized/asymmetric footprints, and this skill does not vendor a
  verified rotation-correction database (fabricating offset numbers
  without a verified source is worse than leaving it to the user).
  Tell the user to visually check part orientation in JLCPCB's own CPL
  preview step during their web order flow before confirming -- that's
  JLCPCB's own recommended verification step, use it.
- BOM row designator lists have a length limit (~2048 chars per JLCPCB's
  own upload parser) -- split an unusually large identical-part group
  (100+ references sharing one LCSC part) across multiple rows under the
  same part number rather than emitting one oversized row.

```
python scripts/export_jlcpcb.py project.kicad_pcb context/design/design.json out_dir/
```

Produces `<stem>_JLC_Gerber.zip` (Tier 1, always), `<stem>_JLC_BOM.csv` +
`<stem>_JLC_CPL.csv` (Tier 2, gated), and `<stem>_JLC_MISSING_LCSC.txt`
listing any refs blocking Tier 2 completeness. Exit code distinguishes
"Tier 1 failed" (1) from "Tier 1 OK, Tier 2 incomplete" (3) from full
success (0) -- check which one you got before telling the user the
package is ready.

See `references/bouni-fab-details.md` for the full researched detail this
section summarizes (naming conventions, plot-parameter checklist, the
BOM-consistency check).

### F -- final report

Write `docs/FINAL_REPORT.md` by hand. Every PASS line must name the evidence
file (`evidence/erc_*.json`, `evidence/drc_*.json`, or a specific datasheet
page) that backs it. No exceptions -- this is the single practice that would
have prevented every false claim found in this project's prior history.

## References

- `references/proven-lessons.md` -- concrete, hard-won facts from this
  project's actual repair session (routing convergence limits, environment
  gotchas, Freerouting version requirements, the two catastrophic bugs and
  how they were found)
- `references/keitark-checklist.md` -- evidence-gate discipline and
  placement/circuit-review checklists distilled from a more
  checklist-driven sibling methodology
- `references/bouni-fab-details.md` -- manufacturing-output format details
  (CPL rotation correction, BOM line-length limits, Gerber parameter
  checklist) distilled from a KiCad/JLCPCB tooling project
