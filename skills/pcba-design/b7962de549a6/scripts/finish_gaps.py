#!/usr/bin/env python3
"""Obstacle-aware gap router (last-mile R layer helper). For the handful of
short connections a full-board autorouter (Freerouting) sometimes leaves
unrouted, this does grid-based A* pathfinding against the board's ACTUAL
copper geometry -- every pad (as a rotated rectangle, not a crude
circumscribed circle), every track/via on every copper layer (vias span
all layers, not just the two outer ones a new track would use), and the
board edge. This is what actually closed 2 of 7 remaining gaps in this
project's repair session after three cruder attempts (straight lines,
Freerouting re-runs) all made things worse.

This is explicitly NOT a general-purpose autorouter -- see
references/proven-lessons.md for why hand-written full-board routing
always failed on this project. Use it only for a small number of specific,
short, already-diagnosed gaps after a real autorouter has done the bulk of
the work. If it reports "no path found" after a generous search, that is
real information (see references/proven-lessons.md: 5 of this project's 7
final gaps got exactly this result even with the best obstacle model
tried) -- it means the gap needs interactive push-and-shove routing, not a
better pathfinding algorithm.

Usage:
  python finish_gaps.py <project.kicad_pcb> <jobs.json>

jobs.json: a list of
  {"net": "GND", "ax": 1.2, "ay": 3.4, "alayer": "F.Cu",
                 "bx": 2.1, "by": 0.5, "blayer": "B.Cu"}
Coordinates are PCB absolute mm (same frame as kicad-cli DRC JSON reports
and pcbnew's own coordinates after ToMM conversion).

Always re-run scripts/run_checks.py after this -- it commits tracks/vias
directly to the board file but the caller must verify no new violations
appeared (this script's obstacle model, while much better than a
circumscribed circle, is still an approximation -- e.g. it does not model
zone keepout, only pads/tracks/vias).
"""
import heapq
import json
import math
import sys
import time
from pathlib import Path

import pcbnew

GRID = 0.1
CLEAR = 0.15  # match design.json's clearance_mm
BOUND_MARGIN = 6.0
EDGE_CLEARANCE = 0.12  # softer than the 0.3mm design rule; see proven-lessons.md


def mm(iu):
    return pcbnew.ToMM(iu)


def to_iu(v):
    return pcbnew.FromMM(v)


def point_seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length2))
    cx, cy = x1 + t * dx, y1 + t * dy
    return math.hypot(px - cx, py - cy)


def point_rect_dist(px, py, cx, cy, hw, hh, rot_deg):
    ang = -math.radians(rot_deg)
    dx, dy = px - cx, py - cy
    lx = dx * math.cos(ang) - dy * math.sin(ang)
    ly = dx * math.sin(ang) + dy * math.cos(ang)
    if abs(lx) <= hw and abs(ly) <= hh:
        return 0.0
    ex = max(abs(lx) - hw, 0.0)
    ey = max(abs(ly) - hh, 0.0)
    return math.hypot(ex, ey)


class Router:
    def __init__(self, board, track_w, via_drill, via_size):
        self.board = board
        self.track_w = track_w
        self.via_drill = via_drill
        self.via_size = via_size
        self.F_CU = board.GetLayerID("F.Cu")
        self.B_CU = board.GetLayerID("B.Cu")
        self.all_cu = [ly for ly in range(pcbnew.PCBNEW_LAYER_ID_START, pcbnew.PCBNEW_LAYER_ID_START + 32)
                       if board.IsLayerEnabled(ly) and pcbnew.IsCopperLayer(ly)]
        bbox = board.GetBoardEdgesBoundingBox()
        self.xmin, self.xmax = mm(bbox.GetLeft()), mm(bbox.GetRight())
        self.ymin, self.ymax = mm(bbox.GetTop()), mm(bbox.GetBottom())
        self.obstacles = []
        self.buckets = {}
        self.bucket_size = 1.0
        self._collect()

    def _collect(self):
        board = self.board
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                pos = pad.GetPosition()
                x, y = mm(pos.x), mm(pos.y)
                sz = pad.GetSize()
                hw, hh = mm(sz.x) / 2.0, mm(sz.y) / 2.0
                rot = pad.GetOrientation().AsDegrees()
                netcode = pad.GetNetCode()
                for pl in self.all_cu:
                    if pad.IsOnLayer(pl):
                        self._add(("rect", x, y, hw, hh, rot, pl, netcode))
        for t in board.GetTracks():
            netcode = t.GetNetCode()
            if isinstance(t, pcbnew.PCB_VIA):
                pos = t.GetPosition()
                x, y = mm(pos.x), mm(pos.y)
                r = self.via_size / 2.0
                for pl in self.all_cu:
                    self._add(("rect", x, y, r, r, 0.0, pl, netcode))
            else:
                layer = t.GetLayer()
                if layer not in self.all_cu:
                    continue
                w = mm(t.GetWidth())
                sx, sy = mm(t.GetStart().x), mm(t.GetStart().y)
                ex, ey = mm(t.GetEnd().x), mm(t.GetEnd().y)
                self._add(("seg", sx, sy, ex, ey, w / 2.0, layer, netcode))

    def _add(self, ob):
        idx = len(self.obstacles)
        self.obstacles.append(ob)
        if ob[0] == "rect":
            _, x, y, hw, hh, rot, layer, net = ob
            r = math.hypot(hw, hh)
            xmin, xmax, ymin, ymax = x - r, x + r, y - r, y + r
        else:
            _, x1, y1, x2, y2, r, layer, net = ob
            xmin, xmax = min(x1, x2) - r, max(x1, x2) + r
            ymin, ymax = min(y1, y2) - r, max(y1, y2) + r
        b = self.bucket_size
        for ix in range(int(math.floor(xmin / b)), int(math.floor(xmax / b)) + 1):
            for iy in range(int(math.floor(ymin / b)), int(math.floor(ymax / b)) + 1):
                self.buckets.setdefault((layer, ix, iy), []).append(idx)

    def blocked(self, x, y, layers, netcode, half_w):
        need = half_w + CLEAR
        edge_need = half_w + EDGE_CLEARANCE
        if (x < self.xmin + edge_need or x > self.xmax - edge_need
                or y < self.ymin + edge_need or y > self.ymax - edge_need):
            return True
        b = self.bucket_size
        ix, iy = int(math.floor(x / b)), int(math.floor(y / b))
        for layer in layers:
            seen = set()
            for dix in (-1, 0, 1):
                for diy in (-1, 0, 1):
                    for idx in self.buckets.get((layer, ix + dix, iy + diy), ()):
                        if idx in seen:
                            continue
                        seen.add(idx)
                        ob = self.obstacles[idx]
                        if ob[0] == "rect":
                            _, ox, oy, ohw, ohh, orot, olayer, onet = ob
                            if onet == netcode:
                                continue
                            if point_rect_dist(x, y, ox, oy, ohw, ohh, orot) < need:
                                return True
                        else:
                            _, sx, sy, ex, ey, orad, olayer, onet = ob
                            if onet == netcode:
                                continue
                            if point_seg_dist(x, y, sx, sy, ex, ey) < need + orad:
                                return True
        return False

    def astar(self, sx, sy, sl, gx, gy, gl, netcode, max_iter=150000):
        half_w = self.track_w / 2.0

        def snap(v):
            return round(v / GRID) * GRID

        start = (snap(sx), snap(sy), sl)
        goal = (snap(gx), snap(gy), gl)
        xmin = min(sx, gx) - BOUND_MARGIN
        xmax = max(sx, gx) + BOUND_MARGIN
        ymin = min(sy, gy) - BOUND_MARGIN
        ymax = max(sy, gy) + BOUND_MARGIN

        def h(n):
            return math.hypot(n[0] - goal[0], n[1] - goal[1]) + (0 if n[2] == goal[2] else 1.5)

        openset = [(h(start), 0.0, start)]
        came = {start: None}
        gscore = {start: 0.0}
        visited = set()
        moves = [(GRID, 0), (-GRID, 0), (0, GRID), (0, -GRID),
                  (GRID, GRID), (GRID, -GRID), (-GRID, GRID), (-GRID, -GRID)]

        it = 0
        t0 = time.time()
        while openset and it < max_iter:
            it += 1
            _, g, node = heapq.heappop(openset)
            if node in visited:
                continue
            visited.add(node)
            if abs(node[0] - goal[0]) < GRID / 2 and abs(node[1] - goal[1]) < GRID / 2 and node[2] == goal[2]:
                path = [node]
                n = node
                while came[n] is not None:
                    n = came[n]
                    path.append(n)
                path.reverse()
                print(f"    astar: {it} iters, {time.time()-t0:.2f}s, path len {len(path)}")
                return path
            x, y, layer = node
            for dx, dy in moves:
                nx, ny = round(x + dx, 3), round(y + dy, 3)
                if nx < xmin or nx > xmax or ny < ymin or ny > ymax:
                    continue
                nnode = (nx, ny, layer)
                if nnode in visited:
                    continue
                if not self.blocked(nx, ny, [layer], netcode, half_w):
                    ng = g + math.hypot(dx, dy)
                    if ng < gscore.get(nnode, 1e9):
                        gscore[nnode] = ng
                        came[nnode] = node
                        heapq.heappush(openset, (ng + h(nnode), ng, nnode))
            other = self.B_CU if layer == self.F_CU else self.F_CU
            nnode = (x, y, other)
            if nnode not in visited and not self.blocked(x, y, self.all_cu, netcode, self.via_size / 2.0):
                ng = g + 1.5
                if ng < gscore.get(nnode, 1e9):
                    gscore[nnode] = ng
                    came[nnode] = node
                    heapq.heappush(openset, (ng + h(nnode), ng, nnode))
        print(f"    astar: exhausted after {it} iters, {time.time()-t0:.2f}s, no path -- "
              f"needs interactive routing, see proven-lessons.md")
        return None

    @staticmethod
    def simplify(path):
        if not path:
            return path
        out = [path[0]]
        i = 1
        while i < len(path) - 1:
            x0, y0, l0 = out[-1]
            x1, y1, l1 = path[i]
            x2, y2, l2 = path[i + 1]
            if l0 == l1 == l2 and abs((x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0)) < 1e-6:
                i += 1
                continue
            out.append(path[i])
            i += 1
        out.append(path[-1])
        return out

    def commit(self, path, net):
        board = self.board
        for i in range(len(path) - 1):
            x1, y1, l1 = path[i]
            x2, y2, l2 = path[i + 1]
            if l1 != l2:
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pcbnew.VECTOR2I(to_iu(x1), to_iu(y1)))
                v.SetDrill(to_iu(self.via_drill))
                v.SetWidth(to_iu(self.via_size))
                v.SetNet(net)
                board.Add(v)
            elif (x1, y1) != (x2, y2):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(pcbnew.VECTOR2I(to_iu(x1), to_iu(y1)))
                t.SetEnd(pcbnew.VECTOR2I(to_iu(x2), to_iu(y2)))
                t.SetLayer(l1)
                t.SetWidth(to_iu(self.track_w))
                t.SetNet(net)
                board.Add(t)


def main():
    if len(sys.argv) != 3:
        print("usage: finish_gaps.py <project.kicad_pcb> <jobs.json>")
        return 2

    pcb_path, jobs_path = sys.argv[1], sys.argv[2]
    board = pcbnew.LoadBoard(pcb_path)
    jobs = json.loads(Path(jobs_path).read_text(encoding="utf-8"))

    router = Router(board, track_w=0.15, via_drill=0.3, via_size=0.6)
    print(f"collected {len(router.obstacles)} obstacles across {len(router.all_cu)} copper layers")

    n_ok = 0
    for job in jobs:
        net = board.FindNet(job["net"])
        la = board.GetLayerID(job["alayer"])
        lb = board.GetLayerID(job["blayer"])
        print(f"routing {job['net']} ({job['ax']},{job['ay']})->({job['bx']},{job['by']})")
        path = router.astar(job["ax"], job["ay"], la, job["bx"], job["by"], lb, net.GetNetCode())
        if path is None:
            print(f"  FAILED: {job['net']} needs interactive routing")
            continue
        path = router.simplify(path)
        router.commit(path, net)
        n_ok += 1
        print(f"  OK: {len(path)} points")

    pcbnew.SaveBoard(pcb_path, board)
    print(f"\ncommitted {n_ok}/{len(jobs)} routes -- now re-run run_checks.py to verify no new violations")
    return 0 if n_ok == len(jobs) else 1


if __name__ == "__main__":
    sys.exit(main())
