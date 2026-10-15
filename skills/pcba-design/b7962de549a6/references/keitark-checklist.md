# Evidence-gate and review checklists (distilled from Keitark/pcba-design-skills)

Full analysis: `context/reference_keitark_pcba_skills_analysis.md`. This file
extracts the actionable checklist items; read the full analysis for the
reasoning behind them.

## Evidence-gate discipline (the core idea worth adopting everywhere)

- Every stage's result must be **PASS / BLOCKED / USER_REVIEW**, never a
  bare "looks fine" -- and PASS must cite the artifact that proves it.
- Don't trust the EDA tool's own "no errors" report in isolation; do an
  independent cross-check against your stated design intent
  (`scripts/elec_review.py` in this skill is exactly that independent
  check for pin/net correctness).
- Any upstream change (netlist, MPN/package, footprint, placement)
  invalidates specific downstream gates -- re-run them, don't assume
  they're still valid. Concretely for this project: changing
  `design.json` invalidates schematic labels, PCB pad nets, routing, and
  manufacturing exports -- re-run `elec_review.py` and `run_checks.py`
  after any design.json edit, not just at the end.

## Circuit/schematic review checklist

- Trace system boundaries: sources, sinks, connectors, functional blocks,
  data flow.
- For each power/reset/programming state the board can be in (power-up,
  shutdown, reset, programming, normal run, sleep, fault, partial-power):
  what owns each shared bus/pin in that state? Is there a hardware-enforced
  break-before-make where two drivers could contend?
- Check absolute max ratings and VIH/VIL/VOH/VOL margins for every
  cross-IC signal, not just the "does it connect" question.
- Unpowered-input tolerance: can a pin see a voltage while its own supply
  rail is off (e.g. during sequencing) without damage?
- Clock/timing: fanout, topology, stub length, edge rate vs. the receiving
  device's setup/hold requirements -- for anything above a few MHz or a
  few cm of trace.

## Placement/layout review checklist (7-pass structure)

1. **Architecture**: connector -> protection -> conversion -> processing
   -> memory -> output, laid out as a flow, not scattered.
2. **Critical local decoupling**: decoupling caps sit in the power pin's
   escape path, not routed around to reach it; regulator feedback/compensation
   loops are physically tight.
3. **Layer and reference strategy**: does every signal have a continuous
   return path on an adjacent plane layer? Any layer transition that breaks
   the return path needs a stitching via nearby.
4. **Routing**: no stubs on high-speed nets; matched pairs/groups only
   where a timing budget actually requires it (don't over-constrain nets
   that don't need it).
5. **Power and zones**: verify every power rail and every GND pad actually
   reaches its intended plane/zone -- don't assume a zone pour connects
   everything of its net automatically without checking thermal reliefs
   and isolated islands.
6. **Manufacturing**: compare actual trace/space, annular ring, drill
   sizes, and via types against your fab's stated capability, not just
   against KiCad's default DRC rules.
7. **Independent visual pass**: render the board and actually look at it --
   overlapping silkscreen, floating labels, obviously-wrong component
   orientation. A DRC-clean board can still be visually broken in ways DRC
   doesn't check.

## Connector maturity gate (5 levels, useful when a design's connector choice matters)

1. Electrical mapping only (pin count, pitch, numbering, net per contact).
2. Orderable MPN confirmed (exact manufacturer drawing matches pin 1,
   origin, body, contacts).
3. Footprint geometry matches the drawing (pads, holes, courtyard, mating
   face, 3D model).
4. Mating system verified (mating card thickness/edge geometry, insertion
   depth, retention/extraction force, housing stack-up).
5. Physical proof (an actual sample or controlled mechanical part has been
   measured and test-fit).

Most quick designs only need level 1-2; call out explicitly which level a
given connector has reached rather than assuming level 5 confidence when
you've only done level 1 checking.

## What NOT to copy from Keitark

Their system assumes a human-in-the-loop for every approval boundary
(sourcing substitution, assembly placement, final price, payment) and a
much slower, more manual pace than an AI-driven closed loop wants. Keep the
*evidence discipline*, not the *approval-latency*. An AI agent can and
should still run every check automatically and present the evidence in one
shot -- just don't let "PASS" mean "I didn't check."
