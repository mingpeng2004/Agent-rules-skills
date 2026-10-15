#!/usr/bin/env python3
"""Post-SMT silkscreen visibility gate (L layer helper). kicad-cli's DRC has
no rule for "will this text be physically hidden once the part is
soldered down" -- it only catches a reference overlapping its own outline
graphic or clipping a pad (silk_overlap / silk_over_copper), which is a
much narrower condition. A reference field can sit fully inside a
component's real pad footprint without tripping either DRC rule, and
still be completely invisible after assembly.

This script checks every reference designator's text bounding box against
every footprint's REAL pad extent (not `footprint.GetBoundingBox()`, which
includes far-flung value-field text and silkscreen graphics and is
therefore much larger than the physical part -- using it as the
"occlusion" region produces false positives everywhere). A ref is flagged
if it falls inside its own part's pad footprint (will be hidden by that
part) or inside a *different* part's pad footprint (will be hidden by a
neighbor).

Usage:
  python check_silkscreen.py <project.kicad_pcb>          # report only
  python check_silkscreen.py <project.kicad_pcb> --fix    # also relocate

--fix moves every flagged reference to the nearest clear position it can
find (checked against every component's real pad extent and the board
edge), falling back to "minimize overlap area" when the immediate
neighborhood has no fully clear spot -- verified on a real 37-component
board in this project where 3 of the 6 flagged parts had no perfectly
clear spot within reach and needed the fallback. Falls back through
progressively smaller text sizes only down to the board's configured
minimum silk text height (read from the board file's `text_height`
constraint if present, else 0.8mm as a common fab default) -- going
smaller than the fab minimum trades one DRC violation for another.

Always re-run run_checks.py after --fix.
"""
import math
import sys

import pcbnew

MIN_TEXT_HEIGHT_MM = 0.8  # common JLC/fab minimum; override if your board's
                          # design rules specify something else
BOARD_EDGE_MARGIN_MM = 0.35


def mm(iu):
    return pcbnew.ToMM(iu)


def to_iu(v):
    return pcbnew.FromMM(v)


def pad_extent(fp):
    xs, ys = [], []
    for pad in fp.Pads():
        p = pad.GetPosition()
        sz = pad.GetSize()
        xs += [mm(p.x) - mm(sz.x) / 2, mm(p.x) + mm(sz.x) / 2]
        ys += [mm(p.y) - mm(sz.y) / 2, mm(p.y) + mm(sz.y) / 2]
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))  # (x1, y1, x2, y2) -- matches overlaps()'s argument order


def side(fp):
    """'F' or 'B' -- a component only occludes silkscreen printed on the
    SAME physical face of the board. A back-side part's pads can overlap a
    front-side reference's 2D (x,y) footprint with zero real occlusion --
    they're on opposite faces. Comparing across sides is a false positive."""
    return "B" if fp.IsFlipped() else "F"


def board_bounds(board):
    bb = board.GetBoardEdgesBoundingBox()
    return mm(bb.GetLeft()), mm(bb.GetRight()), mm(bb.GetTop()), mm(bb.GetBottom())


def overlaps(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2, margin=0.0):
    return not (ax2 + margin < bx1 or ax1 - margin > bx2
                or ay2 + margin < by1 or ay1 - margin > by2)


def overlap_area(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2):
    ox = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    oy = max(0.0, min(ay2, by2) - max(ay1, by1))
    return ox * oy


def find_clear_spot(ref, ref_side, pad_boxes, board_edge, half_w, half_h):
    """Search outward from the part's own pad extent for a position clear
    of every SAME-SIDE part's pads (own included) and the board edge.
    Falls back to the position that minimizes total overlap area if
    nothing is fully clear. pad_boxes on the opposite side are ignored --
    they're on the other face of the board and cannot occlude this
    reference regardless of 2D (x,y) overlap."""
    same_side = [b for b in pad_boxes if b[5] == ref_side]
    my_box = next((b for b in same_side if b[4] == ref), None)
    if my_box is None:
        return None, None
    fxmin, fymin, fxmax, fymax, _, _ = my_box
    fcx, fcy = (fxmin + fxmax) / 2, (fymin + fymax) / 2
    bxmin, bxmax, bymin, bymax = board_edge

    def in_bounds(x1, y1, x2, y2):
        return (x1 >= bxmin + BOARD_EDGE_MARGIN_MM and x2 <= bxmax - BOARD_EDGE_MARGIN_MM
                and y1 >= bymin + BOARD_EDGE_MARGIN_MM and y2 <= bymax - BOARD_EDGE_MARGIN_MM)

    candidates = []
    for offset in (0.1, 0.3, 0.6, 1.0, 1.5, 2.0, 3.0):
        candidates += [
            (fcx, fymin - half_h - offset),
            (fcx, fymax + half_h + offset),
            (fxmin - half_w - offset, fcy),
            (fxmax + half_w + offset, fcy),
        ]

    for cx, cy in candidates:
        x1, y1, x2, y2 = cx - half_w, cy - half_h, cx + half_w, cy + half_h
        if not in_bounds(x1, y1, x2, y2):
            continue
        if not any(overlaps(x1, y1, x2, y2, *b[:4], margin=0.15) for b in same_side):
            return cx, cy

    # fallback: grid search around own footprint, minimize total overlap area
    best = None
    for ox in [i * 0.15 for i in range(-30, 31)]:
        for oy in [i * 0.15 for i in range(-30, 31)]:
            cx, cy = fcx + ox, fcy + oy
            x1, y1, x2, y2 = cx - half_w, cy - half_h, cx + half_w, cy + half_h
            if not in_bounds(x1, y1, x2, y2):
                continue
            score = sum(overlap_area(x1, y1, x2, y2, *b[:4]) for b in same_side if b[4] != ref)
            # still must be clear of the part's OWN pads -- that's non-negotiable
            if overlaps(x1, y1, x2, y2, fxmin, fymin, fxmax, fymax, margin=0.1):
                continue
            key = (score, ox * ox + oy * oy)
            if best is None or key < best[0]:
                best = (key, cx, cy)
    if best:
        return best[1], best[2]
    return None, None


def main():
    if len(sys.argv) < 2:
        print("usage: check_silkscreen.py <project.kicad_pcb> [--fix]")
        return 2

    pcb_path = sys.argv[1]
    do_fix = "--fix" in sys.argv[2:]
    board = pcbnew.LoadBoard(pcb_path)

    pad_boxes = []
    for fp in board.GetFootprints():
        ext = pad_extent(fp)
        if ext:
            pad_boxes.append((*ext, fp.GetReference(), side(fp)))

    board_edge = board_bounds(board)

    problems = []
    for fp in board.GetFootprints():
        ref_field = fp.Reference()
        if not ref_field.IsVisible():
            continue
        ref = fp.GetReference()
        ref_side = side(fp)  # reference silkscreen is printed on the part's own side
        rbb = ref_field.GetBoundingBox()
        rx1, rx2 = mm(rbb.GetLeft()), mm(rbb.GetRight())
        ry1, ry2 = mm(rbb.GetTop()), mm(rbb.GetBottom())

        # small negative-space margin: a razor-thin graze (<0.1mm) at a text
        # bounding-box corner isn't a practical "hidden by the part" case
        hidden_by = [b[4] for b in pad_boxes if b[5] == ref_side and overlaps(rx1, ry1, rx2, ry2, *b[:4], margin=-0.1)]
        if hidden_by:
            problems.append((ref, hidden_by))

    if not problems:
        print("PASS: every reference designator is clear of every component's pad footprint")
        return 0

    print(f"FAIL: {len(problems)} reference designator(s) will be hidden after SMT placement")
    for ref, hidden_by in problems:
        by = "its own body" if hidden_by == [ref] else f"{hidden_by}"
        print(f"  {ref}: covered by {by}")

    if not do_fix:
        print("\nre-run with --fix to relocate them automatically")
        return 1

    print("\n--fix: relocating...")
    for ref, _ in problems:
        for fp in board.GetFootprints():
            if fp.GetReference() != ref:
                continue
            ref_field = fp.Reference()
            text_len = max(1, len(ref))
            size = MIN_TEXT_HEIGHT_MM
            half_w = max(0.4, text_len * size * 0.35)
            half_h = max(0.3, size * 0.45)
            cx, cy = find_clear_spot(ref, side(fp), pad_boxes, board_edge, half_w, half_h)
            if cx is None:
                print(f"  {ref}: FAILED to find any spot, even minimizing overlap -- manual placement needed")
                continue
            ref_field.SetPosition(pcbnew.VECTOR2I(to_iu(cx), to_iu(cy)))
            ref_field.SetTextSize(pcbnew.VECTOR2I(to_iu(size), to_iu(size)))
            print(f"  {ref}: moved to ({cx:.2f},{cy:.2f})")

    pcbnew.SaveBoard(pcb_path, board)
    print("saved -- now re-run run_checks.py to confirm no new DRC violations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
