# Proven lessons (from this project's actual repair session, 2026-07-23)

Each entry is a fact that was verified, not assumed. Update this file when
a new lesson is confirmed; delete an entry only if it's later proven wrong
(and say why).

## The two catastrophic bugs, and how they were found

**Bug 1: 100% of the schematic's 127 pin labels were in the wrong position.**
Whatever generated the schematic (`generator "pcba_skill_v5"` in the file
header) placed net labels in the *order nets appeared in design.json*
instead of computing each pin's real coordinate. R/C/L 2-pin parts had a
regular Pin1<->Pin2 swap; the 10/8/5/4/3-pin connectors had labels scattered
essentially at random relative to their true pins. `kicad-cli sch erc` did
not catch this -- every pin had *some* label touching it, so ERC's
`pin_not_connected` check was satisfied even though the labels were wrong.
**Found by**: writing a script that computes each pin's real-world
coordinate from the symbol library's own `lib_symbols` pin-offset
definitions, then checking whether the label actually sitting there matches
design.json's declared net for that ref+pin. This is exactly what
`scripts/elec_review.py` now automates.

**Bug 2: a QFN20 part's pin numbers were read from its datasheet's SOP16
column.** The MCU (CH32V003F4U6) ships in 4 packages; its datasheet prints
one merged table with a column per package. design.json's pin numbers for
9 different signals (NRST, 3V3/VDD, 4x SPI, SWIO, UART TX/RX) were taken
from the wrong column, 100% consistently -- checked by testing "does adding
+3 to the pin number reach the SOP16 value" against all 9 signals; it did,
every time. If shipped as-is, the chip's real NRST pin (QFN20 pin 4) would
have been wired the same as GND (design.json's wrong "pin 1"), permanently
holding the MCU in reset. **Found by**: independently verifying the QFN20
pin table two ways -- (a) reading the datasheet's own merged
TSSOP20/QFN20/SOP16/SOP8 table row by row and testing column-order
hypotheses against known-good anchors, (b) a web search for the QFN20
pinout from an independent source, then cross-checking both agreed on all
20 pins before trusting either.

**Takeaway that generalizes**: kicad-cli's ERC/DRC only prove *internal*
consistency of a file. They cannot prove the file matches your *intent*.
Only a script that reads design.json and checks against it (or a human
reading the datasheet) can catch a systematically-wrong-but-internally-
consistent error. Do this check every time, not just when something looks
suspicious -- both bugs above were completely invisible from a normal
ERC/DRC-green report.

## Environment

- A fresh KiCad 10 install on Windows has **no global sym-lib-table /
  fp-lib-table** until the GUI is launched once. Headless/CLI-only usage
  never triggers KiCad's first-run setup. Result: every ERC/DRC run
  produces ~100+ `lib_symbol_issues`/`footprint_link_issues` warnings that
  look like design defects but are pure environment noise. Fix: generate
  the tables yourself from `<kicad_root>/share/kicad/{symbols,footprints}/`
  (see `scripts/kicad_env.py`) before trusting any ERC/DRC count.
- `kicad-cli.exe` and the bundled `python.exe`/`pythonw.exe` under
  `<kicad_root>/bin/` are Windows-native executables -- they don't
  understand POSIX-style `/tmp/...` paths from a POSIX shell (git-bash/MSYS).
  Always pass Windows-style paths (or paths relative to the CWD) when
  invoking them from a POSIX shell wrapper.

## Freerouting (autorouting)

- Freerouting 2.2.x needs **JRE 21+** (ships class file version 69 = Java
  25; JRE 21 = class version 65 and fails with `UnsupportedClassVersionError`
  even though the docs say 21 is the minimum -- in practice **JRE 25**
  is what actually worked). A portable JRE zip from Adoptium/Temurin
  (`https://api.adoptium.net/v3/assets/latest/25/hotspot?image_type=jre&os=windows&architecture=x64`)
  needs no install/admin rights.
- Headless invocation that works:
  `java -Djava.awt.headless=true -jar freerouting.jar --gui.enabled=false -de in.dsn -do out.ses -mp 200 -mt 4`
- On a genuinely dense board (this project: 37 components in 18x22mm, 4
  layers), a single Freerouting pass took ~25 seconds for 83 nets, converged
  to 0 shorts/crossings/clearance violations, with ~6-7 nets left unrouted
  after the score stopped improving across several passes. This was
  dramatically better than 14 hand-written routing scripts had achieved
  across many prior attempts on the same board (best prior result: ~130-190
  violations, none of them shorts-free).
- **Re-running Freerouting on a partially-routed board to finish the
  remainder made things worse, not better**, in three independent attempts:
  (a) re-exporting DSN with zones filled -- regressed from 6 to 11
  unrouted, stuck after 1 pass; (b) same but with zones explicitly
  unfilled before export -- regressed to 13 unrouted, still stuck after 1
  pass; (c) hand-placing straight tracks/vias at the reported gap
  coordinates -- introduced 14 new shorts by cutting through existing
  copper, even for a single well-understood case retried with a deliberate
  jog around a known obstacle. **Conclusion: always route the full board
  fresh from a completely ripped-up state in one Freerouting invocation.
  Do not try to "continue" or "top up" a mostly-routed board this way** --
  if a few nets remain, they need either a fresh full re-route attempt
  (different pass/thread settings, may or may not help) or a real
  interactive push-and-shove router (KiCad GUI), not scripted continuation.

## Board size vs. routability: a real, measurable relationship

When a dense board has persistent unrouted gaps after autorouting, and the
board size is negotiable at all, **test enlarging it empirically before
assuming more clever routing algorithms will help**. On this project (37
components, started at 18x22mm), each +1mm of width produced a measurable,
monotonic drop in Freerouting's first-pass unrouted count: 18mm -> 6-7
unrouted, 19mm -> 2-3 unrouted, 20mm -> 1 unrouted (out of 83 nets each
time). This is a much higher-leverage lever than tuning pathfinding
parameters once a board is this dense. Test methodology: resize the board
outline + zone outlines (keep the same 0.3mm zone-to-edge margin), rip up
all copper, re-export DSN, run Freerouting fresh, compare. Takes a few
minutes per size point and gives a real number instead of a guess.

**Do not trust even a "correct" autorouter's output without DRC.** At
20mm, Freerouting's deterministic first-pass output (only 1 net left
unrouted, looked like a near-perfect result) actually contained a real
short: two nets (9V, NRSS) tangled into overlapping copper near a part
with 0.65mm pin pitch. This was the first time in this project's entire
history that a *correctly configured, industry-standard tool* produced a
short, as opposed to a hand-written script. Always run the DRC gate after
autorouting, full stop, regardless of how trustworthy the tool is.

**Fixing a localized autorouter defect on an otherwise-complete board:
surgical removal, not net-wide re-route.** Once 82+ of 83 nets are
routed, there is very little free channel space left -- re-routing an
entire net from scratch (even a previously-working one) frequently finds
*no path at all*, not even a worse one, because the rest of the board's
copper has consumed the available room. What worked: identify the exact
bounding box of the defect from the DRC violation coordinates, remove only
the track segments whose endpoints fall inside that box (preserving the
rest of the net's routing, e.g. a long trunk from a connector across the
board), then use `finish_gaps.py` to reconnect the resulting small local
gap. This succeeded where "rip up the whole net and re-route" failed
outright on the same board.

## Length matching / meander insertion: measured but not yet automated safely

Tried to add matched-length meanders (see `finish_gaps.py`'s `blocked()`
obstacle model, reused for this) to bring two paired nets to equal length
after routing. The specific attempt (scan the net's tracks for the longest
axis-aligned straight segment, insert perpendicular out-and-back "finger"
detours along it until the length deficit is covered, checking each
finger tip for clearance) **hung without completing or erroring** on a
fully-routed 20mm board -- no output, no crash, did not return within
several minutes. Root cause not identified; suspect pcbnew's internal
connectivity/ratsnest recalculation cost on repeated `board.Add()`/
`Remove()` calls against an already-dense board, but this is a guess, not
a verified diagnosis. The script was killed before `pcbnew.SaveBoard()`
ran, so the board file was never touched -- always structure a script this
way (mutate in memory, save only once at the very end) so a hang or crash
mid-run cannot corrupt the last good state.

**Before retrying this**: (1) verify termination speed on a much smaller
scope first (e.g. print progress after every single finger placement,
not just at the end, so a hang is diagnosable rather than silent); (2)
consider KiCad's own native interactive "Tune Length" tool instead of
scripting it -- it exists precisely for this purpose and does not carry
the same pcbnew-scripting-performance unknowns; (3) if scripting it again,
verify each finger's DRC impact immediately after adding it rather than
adding several before checking, matching the same one-at-a-time discipline
that worked for `finish_gaps.py`.

Measured mismatches on this project as of the last successful measurement
(20mm board, fully routed): S_A vs S_B differential pair, 1.59mm; CAP_A vs
CAP_B pair, 1.82mm. Whoever picks this up next has these numbers as a
starting point without needing to re-measure.

## Silkscreen visibility after SMT assembly is a real, DRC-invisible gate

kicad-cli's DRC has no rule for "is this reference designator physically
under the part after assembly" -- `silk_overlap`/`silk_over_copper` only
catch a reference overlapping its own outline graphic or clipping a pad,
which is a narrower condition. A reference can sit fully inside its own
part's (or a neighbor's) real pad footprint and pass DRC clean the whole
time. On a real 37-component board, 6 of 37 references had exactly this
problem, invisible to every automated gate run up to that point. Check
this explicitly (`scripts/check_silkscreen.py`) whenever a user reviews a
board visually and flags readability, or proactively as part of the L
(placement) review -- don't wait to be asked.

**Debugging note that generalizes beyond this specific script**: a
geometry helper (`pad_extent()`) returned a tuple in `(xmin, xmax, ymin,
ymax)` order while the function consuming it (`overlaps()`) expected
`(x1, y1, x2, y2)` = `(xmin, ymin, xmax, ymax)` -- silently swapping xmax
and ymin in every comparison. This did not crash or throw; it just made
every overlap check subtly wrong in a way that happened to report "PASS"
on the exact test board being used to validate the script, so it looked
correct until tested against a *forced* known-bad case. **Whenever you
write a geometry/collision-check helper, test it against a deliberately
constructed positive case (something you know must overlap) before
trusting a clean report on real data** -- a false "PASS" from a
mismatched tuple order is much harder to notice than a crash, and a
clean-looking real board is not evidence the checker itself is correct.

**Also verify pcbnew API compatibility issues don't silently produce
wrong-but-plausible results.** `pcbnew.GetBoardEdgesBoundingBox()` +
`.GetLeft()`/`.GetRight()` raised a clean `AttributeError` in one script
this session but worked fine when called the identical way in another
script in the same environment -- root cause not fully identified, but
the practical lesson is: if a pcbnew call fails inconsistently across
otherwise-similar scripts, don't assume the API is simply broken and
hardcode a workaround (a hardcoded board-size fallback caused an
unrelated silent hang in this session, wasting significant time) --
prefer a from-scratch, independently-verifiable derivation (e.g. parsing
`Edge.Cuts` coordinates directly from the file, or comparing against a
board size you've already confirmed another way) over guessing.

## Verifying electrical performance without SPICE models

A user asked to "simulate and confirm electrical performance" for a
precision analog board. No vendor SPICE models were available locally for
any of the three key ICs (a common situation for budget/regional parts,
and even for parts that do have vendor models, getting them plus a
working simulator onto a machine mid-session can fail -- an ngspice
binary download stalled and was abandoned after several minutes this
session). Substituting a **datasheet-parameter analytical verification**
(exact net-topology tracing from design.json + real datasheet numbers for
PSRR/regulation/noise/dropout, worked by hand/Python for a linear
regulator + RC network system) produced a genuinely useful, numerically
grounded answer -- including finding a concrete, quantified risk
(discrete resistor-pair ratio tracking vs. a matched network resistor)
that a simulation might not have surfaced any more clearly than the
analytical approach did. The key discipline: **say explicitly that a
transistor-level simulation did not happen and why**, rather than letting
"I did an analysis" imply more rigor than was actually applied. See
`docs/ELECTRICAL_ANALYSIS.md` in this project for the full worked example.

## Optimizing a design after routing is already fully closed: know when NOT to act

After achieving a hard-won zero-DRC-violation routing state, a follow-up
request ("optimize the design, if margin is insufficient") identified a
real, quantified risk (see above) with two textbook hardware fixes
(move components for better thermal tracking; swap to a matched-network
resistor footprint). Both were evaluated and **deliberately not
implemented**, because both require re-routing on a board already proven
fragile to any component move (see the routing section above -- re-routing
a single net on a saturated board frequently finds no path at all, not
just a worse one). The lower-risk mitigation actually applied (a GND
copper pour, which also happened to help the thermal-tracking concern
indirectly by improving heat spreading) was implemented and verified
clean; the higher-risk options were documented as a decision for the next
PCB revision, gated on real test data (thermal cycling) rather than
applied speculatively. **"Optimize the design" does not always mean
"make every change you can identify"** -- when every implementation path
for a specific finding carries a real chance of undoing verified work,
document the tradeoff and defer, rather than gambling a known-good state
against a marginal, unverified improvement.

## Closing the last few gaps after Freerouting: what actually worked

After Freerouting's single full-board pass left 7 short connections
unrouted (out of 83 nets), four approaches were tried in order:

1. **Straight-line tracks/vias at the reported gap coordinates** --
   introduced 14 new shorts. Rejected.
2. **Re-feeding the mostly-routed board back through Freerouting** (both
   with zones filled and unfilled before re-export) -- made things worse
   both times (6 unrouted became 11, then 13; the router got stuck after a
   single pass). Freerouting is good at routing a board from a clean slate,
   not at "topping up" a mostly-done one. Rejected.
3. **A custom grid-based A\* pathfinder, first version**: modeled every pad
   as a circumscribed circle (radius = max(width,height)/2). This is safe
   but badly over-conservative for oblong pads (several parts on this
   board use ~1.5-1.9mm x ~0.4-0.5mm pads, whose circumscribed-circle
   radius is 2-4x their actual half-width in the tight direction) -- it
   found paths for only 2 of 7 gaps, and one of those two still introduced
   new violations because it didn't check via placement against the
   inner copper layers (see below).
4. **Same A\* pathfinder, corrected**: modeled pads as their actual rotated
   rectangles (point-to-rotated-rect distance, not point-to-circle), and
   checked via placement against clearance on **all 4 copper layers**, not
   just the two outer ones a new track would run on -- because a via
   physically passes through every layer, and this board's In1.Cu/In2.Cu
   are not pure planes: they carry real signal traces (SWIO, 5VA, S_A were
   found there) mixed in with the GND/power pours. This version routed 2
   of the remaining 6 gaps cleanly (verified: 0 new shorts/clearance/
   crossing violations). A soft board-edge margin (0.12mm, between "no
   margin" which put new copper at 0.025mm from the edge, and the full
   0.3mm design rule which blocked every viable path near edge-adjacent
   parts) was needed to get a usable result without either extreme.

**Final result: 2 of 7 gaps closed automatically (GND, UART_RX); 5 confirmed
via exhaustive search (accurate geometry, 6mm search radius, 150,000
iteration budget, multiple track-width and edge-margin variants tried) to
have no static path at all in the current placement.** These 5 need either
interactive push-and-shove routing (which can temporarily nudge a
neighboring track out of the way -- something a fixed-obstacle pathfinder
fundamentally cannot do) or a small placement adjustment. This is captured
as `scripts/finish_gaps.py` -- use it for the same purpose on a future
board, but expect it to report some gaps as unsolvable, and trust that
result rather than trying yet another straight-line hack when it does.

## Design conventions observed in this project (context, not universal rules)

- Generic connector placeholder symbols (e.g. `Conn_02x10_Odd_Even` used to
  represent a 20-pin SSOP ADC) are workable for netlist correctness but
  sacrifice schematic readability -- a human can't tell which pin is which
  function by looking at the symbol. If asked to make a schematic more
  readable, this is the first thing to fix (see the Keitark
  "schematic-humanizer" idea in `keitark-checklist.md`).
- A part left No-Connect should have a *documented reason* traceable to the
  datasheet (e.g. "datasheet says do not route this pin to any electrical
  net, not even GND or IN" vs. "unused GPIO, no functional requirement" vs.
  "second ADC channel not used in a single-channel design"). "No net found
  in design.json" alone is not a justification -- it might mean "forgot to
  wire this," not "intentionally unused." Check the datasheet before
  marking anything No-Connect.
