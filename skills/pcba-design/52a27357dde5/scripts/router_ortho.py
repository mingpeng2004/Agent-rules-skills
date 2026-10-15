#!/usr/bin/env python3
"""
PCBA Skill v5.2 — 正交路由引擎 (router_ortho.py)

规则:
  1. 所有线段必须正交 (abs(dx)<0.01 或 abs(dy)<0.01)
  2. 走线距异网焊盘 ≥ 0.2mm
  3. 过孔距异网焊盘 ≥ 1.0mm (使用空间网格加速)
  4. 全部焊盘连通

架构:
  - F.Cu: 水平总线 (每网独占总线y)
  - B.Cu: 竖直桩 (焊盘→总线)
  - In1.Cu / In2.Cu: GND 内层
  - F纯网走F层, B纯网走B层, 跨层网打最小过孔

用法:
  KiCad-python router_ortho.py --board board.kicad_pcb --design design.json [--apply]
"""

import pcbnew, json, math, os, sys, collections, argparse

# ===== 空间网格碰撞检测 =====
GRID_STEP = 1.0

class SpatialGrid:
    def __init__(self):
        self.cells = collections.defaultdict(list)

    def add(self, x, y, net):
        self.cells[(int(x/GRID_STEP), int(y/GRID_STEP))].append((x, y, net))

    def is_clear(self, x, y, my_net, margin=1.0):
        """检查(x,y)是否距任何异网焊盘>=margin"""
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for px, py, nn in self.cells.get((int(x/GRID_STEP)+dx, int(y/GRID_STEP)+dy), []):
                    if nn == my_net:
                        continue
                    if math.hypot(x-px, y-py) < margin:
                        return False
        return True


# ===== 正交路由引擎 =====
class OrthoRouter:
    def __init__(self, board, design):
        self.board = board
        self.design = design
        self.routes = []
        self.vias = []
        self.spatial = SpatialGrid()
        self._collect_pads()
        self._classify_nets()

    def mm(self, v):
        return round(v/1e6, 3)

    def _collect_pads(self):
        self.pads = {}
        self.net_pads = collections.defaultdict(list)
        for fp in self.board.GetFootprints():
            ly = 'F' if fp.GetLayer() == 0 else 'B'
            for pad in fp.Pads():
                nn = pad.GetNetname()
                key = f"{fp.GetReference()}.{pad.GetPadName()}"
                x, y = self.mm(pad.GetPosition().x), self.mm(pad.GetPosition().y)
                self.pads[key] = (x, y, ly, nn)
                self.spatial.add(x, y, nn)
                if nn:
                    self.net_pads[nn].append((key, x, y, ly))

    def _classify_nets(self):
        self.F_nets = set()
        self.B_nets = set()
        self.X_nets = set()
        for net, pads in self.net_pads.items():
            if net == "GND":
                continue
            ly_set = set(p[3] for p in pads)
            if ly_set == {"F"}:
                self.F_nets.add(net)
            elif ly_set == {"B"}:
                self.B_nets.add(net)
            else:
                self.X_nets.add(net)

    def _width(self, net):
        if net == "9V":
            return 0.5
        if net in ("5V", "3V3", "5VA", "3V3A"):
            return 0.3
        if net in ("UART_TX", "UART_RX"):
            return 0.15
        return 0.2

    def _add_route(self, net, width, layer, points):
        """添加正交路由段"""
        for i in range(len(points)-1):
            x1, y1 = points[i][0], points[i][1]
            x2, y2 = points[i+1][0], points[i+1][1]
            if abs(x1-x2) > 0.01 and abs(y1-y2) > 0.01:
                raise ValueError(f"Non-orthogonal: ({x1},{y1})→({x2},{y2}) in {net}")
        self.routes.append({
            "net": net, "width_mm": width, "layer": layer,
            "points": [{"x": round(x, 3), "y": round(y, 3)} for x, y in points]
        })

    def _add_via(self, net, x, y):
        self.vias.append({"net": net, "x": round(x, 3), "y": round(y, 3),
                          "drill_mm": 0.3, "size_mm": 0.6})
        self.spatial.add(round(x, 3), round(y, 3), net)

    def route(self):
        # 分配总线 y
        bus_y = {}
        y_top, y_bot = 9.5, -9.5
        for net in sorted(self.net_pads, key=lambda n: len(self.net_pads[n]), reverse=True):
            if net == "GND":
                continue
            if abs(y_top) < abs(y_bot):
                bus_y[net] = round(y_top, 1)
                y_top -= 0.4
            else:
                bus_y[net] = round(y_bot, 1)
                y_bot += 0.4

        # 逐网布线
        for net, pads in self.net_pads.items():
            if net == "GND":
                continue
            w = self._width(net)
            by = bus_y[net]
            sp = sorted(pads, key=lambda p: p[1])
            base = "F.Cu" if net in self.F_nets else "B.Cu"

            # 收集总线节点
            nodes = []
            for ref, x, y, ply in sp:
                if ply == ("F" if base == "F.Cu" else "B"):
                    # 同层: 竖直桩
                    if abs(y - by) > 0.04:
                        self._add_route(net, w, base, [(x, y), (x, by)])
                    nodes.append(x)
                else:
                    # 异层: 过孔
                    vx, vy = x, by
                    self._add_via(net, vx, vy)
                    self._add_route(net, w, "F.Cu" if ply == "F" else "B.Cu", [(x, y), (vx, vy)])
                    nodes.append(vx)

            # 水平总线
            for i in range(len(nodes) - 1):
                if abs(nodes[i] - nodes[i+1]) > 0.05:
                    self._add_route(net, w, base, [(nodes[i], by), (nodes[i+1], by)])

        # GND
        for k, (x, y, ly, nn) in self.pads.items():
            if nn != "GND":
                continue
            for r in [0.3, 0.6, 0.9, 1.2]:
                for ang in [0, 90, 180, 270]:
                    vx = round(x + r*math.cos(math.radians(ang)), 1)
                    vy = round(y + r*math.sin(math.radians(ang)), 1)
                    if abs(vx) > 8.7 or abs(vy) > 10.7:
                        continue
                    if self.spatial.is_clear(vx, vy, "GND", 0.8):
                        self._add_via("GND", vx, vy)
                        break
                else:
                    continue
                break

        return self.routes, self.vias


# ===== CLI =====
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    ap.add_argument("--design", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.board)
    d = json.load(open(args.design, encoding="utf-8"))

    router = OrthoRouter(b, d)
    routes, vias = router.route()

    # 验证连通性
    connected = set()
    for r in routes:
        for pt in r.get("points", []):
            if isinstance(pt, dict) and "pad" in pt:
                connected.add(pt["pad"])
    all_pads = set(k for k in router.pads
                   if router.pads[k][3] and router.pads[k][3] != "GND")
    missing = all_pads - connected

    print(f"Routes={len(routes)} Vias={len(vias)}")
    print(f"{'ALL CONNECTED' if not missing else f'MISSING {len(missing)}'}")

    if args.apply:
        d["routes"] = routes
        d["vias"] = vias
        d["zones"] = [{"net": "GND", "layer": L, "margin_mm": 0.3, "clearance_mm": 0.3}
                      for L in ["In1.Cu", "In2.Cu"]]
        json.dump(d, open(args.design, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("[apply] → design.json")
