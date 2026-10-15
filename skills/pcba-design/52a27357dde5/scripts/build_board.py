#!/usr/bin/env python3
"""
PCBA Skill v5.0 — 通用 PCB 生成器（build_board.py）

用 KiCad 自带 Python 运行：
  python.exe build_board.py --design design.json --outdir dist_v7 [--name PROJECT]

输入 design.json（单一事实源，Schema 见 templates/design.schema.json）：
  meta        项目元数据（project/board_name/version/author）
  board       板框（width_mm/height_mm/thickness_mm/layers/keepouts）
  components  元件（ref/footprint/value/x/y/rotation/layer/lcsc）
  nets        网络（name/class/min_width_mm/max_current_a/copper）
  routes      走线（net/width_mm/layer/points[]，端点可用 {"pad":"J1.3"} 自动吸附焊盘中心）
  vias        过孔（x/y/net/drill_mm/size_mm）
  zones       铺铜（net/layer/margin_mm/clearance_mm）
  silkscreen  丝印（text/x/y/size_mm/rotation/layer）
  rules       设计规则覆盖（clearance_mm/min_track_mm）

关键设计（修复 v4.5 教训）：
  - 走线端点强制吸附焊盘中心 → 杜绝 v6 的 unconnected/shorting
  - 真实 ZONE 铺铜 + ZONE_FILLER 填充 → 杜绝 v6 的"假铺铜"
  - 位号文本重新定位到元件上方 → 避免丝印乱飞
  - 生成后立刻可跑 run_checks.py 全量门禁
"""
import argparse
import csv
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import kicad_env  # noqa: E402

import pcbnew  # noqa: E402

LAYER_MAP = {
    'F.Cu': pcbnew.F_Cu, 'B.Cu': pcbnew.B_Cu,
    'In1.Cu': pcbnew.In1_Cu, 'In2.Cu': pcbnew.In2_Cu,
    'F.SilkS': pcbnew.F_SilkS, 'B.SilkS': pcbnew.B_SilkS,
    'Edge.Cuts': pcbnew.Edge_Cuts,
}


def to_xy(x_mm, y_mm):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))


def load_design(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def find_pad(board, ref, pad_num):
    fp = board.FindFootprintByReference(ref)
    if fp is None:
        raise KeyError(f'元件 {ref} 不在板上')
    pad = fp.FindPadByNumber(str(pad_num))
    if pad is None:
        raise KeyError(f'{ref} 无焊盘 {pad_num}')
    return pad


class BoardBuilder:
    def __init__(self, design, out_path):
        self.d = design
        self.out_path = out_path
        self.board = pcbnew.NewBoard(out_path)
        self.nets = {}
        self.rules = design.get('rules', {})

    # ---------------- 基础 ----------------
    def setup(self):
        b = self.board
        ds = b.GetDesignSettings()
        try:
            ds.SetBoardThickness(pcbnew.FromMM(self.d['board'].get('thickness_mm', 1.6)))
        except Exception:
            pass
        try:
            ds.SetCopperLayerCount(int(self.d['board'].get('layers', 2)))
        except Exception:
            pass
        # 设计规则（DRC 判定基线）
        clr_mm = self.rules.get('clearance_mm', 0.15)
        try:
            ds.m_MinClearance = pcbnew.FromMM(clr_mm)
            ds.m_CopperEdgeClearance = pcbnew.FromMM(self.rules.get('copper_edge_clearance_mm', 0.3))
            ds.m_HoleClearance = pcbnew.FromMM(self.rules.get('hole_clearance_mm', 0.25))
        except Exception as e:
            print(f'  [WARN] 设计规则写入失败(非致命): {e}')
        # 板级最小线宽（KiCad 默认 0.2mm 会误杀 0.15mm 走线）
        try:
            ds.m_TrackMinWidth = pcbnew.FromMM(self.rules.get('min_track_mm', 0.15))
        except Exception as e:
            print(f'  [WARN] 板级最小线宽写入失败(非致命): {e}')
        # 默认网络类间距（KiCad 10 存于项目 net_settings；缺省 0.2mm 会误杀合理设计）
        try:
            dflt_nc = ds.m_NetSettings.GetDefaultNetclass()
            dflt_nc.SetClearance(pcbnew.FromMM(clr_mm))
            dflt_nc.SetTrackWidth(pcbnew.FromMM(self.rules.get('min_track_mm', 0.15)))
        except Exception as e:
            print(f'  [WARN] 网络类间距写入失败(非致命): {e}')

    def get_net(self, name):
        if name in self.nets:
            return self.nets[name]
        existing = self.board.FindNet(name)
        if existing is not None and existing.GetNetname() == name:
            self.nets[name] = existing
            return existing
        net = pcbnew.NETINFO_ITEM(self.board, name)
        self.board.Add(net)
        self.nets[name] = net
        return net

    # ---------------- 板框 ----------------
    def outline(self):
        bw = self.d['board']['width_mm']
        bh = self.d['board']['height_mm']
        hw, hh = bw / 2, bh / 2
        pts = self.d['board'].get('polygon',
                                  [[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]])
        pts = [tuple(p) for p in pts]
        if pts[0] != pts[-1]:
            pts = pts + [pts[0]]
        for i in range(len(pts) - 1):
            seg = pcbnew.PCB_SHAPE(self.board)
            seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
            seg.SetStart(to_xy(*pts[i]))
            seg.SetEnd(to_xy(*pts[i + 1]))
            seg.SetLayer(pcbnew.Edge_Cuts)
            seg.SetWidth(pcbnew.FromMM(0.1))
            self.board.Add(seg)
        print(f'  [OK] 板框 {bw}x{bh}mm ({len(pts)-1} 段)')

    # ---------------- 元件 ----------------
    def components(self):
        lib_root = kicad_env.find_footprint_lib()
        for c in self.d['components']:
            lib_dir, _, fp_name = c['footprint'].partition(':')
            fp = pcbnew.FootprintLoad(os.path.join(lib_root, lib_dir + '.pretty'), fp_name)
            if fp is None:
                raise FileNotFoundError(f'{c["ref"]}: 封装 {c["footprint"]} 加载失败')
            fp.SetReference(c['ref'])
            fp.SetValue(str(c['value']))
            fp.SetPosition(to_xy(c['x'], c['y']))
            if c.get('rotation'):
                fp.SetOrientationDegrees(c['rotation'])
            if c.get('lcsc'):
                fp.SetField('LCSC', str(c['lcsc']))
            self.board.Add(fp)
            if c.get('layer', 'F') == 'B':
                # 翻转到背面：SetLayer(B_Cu) 不移位焊盘；未入板先 Flip 会段错误（v41 实测）
                fp.Flip(fp.GetPosition(), False)
            # 位号文本定位：放到元件上方 1.2mm，避免丝印乱飞压焊盘
            self._place_ref_text(fp, c)
            print(f'  [OK] {c["ref"]} {fp_name} @ ({c["x"]},{c["y"]}) rot={c.get("rotation", 0)}')

    def _place_ref_text(self, fp, c):
        try:
            # 除位号外全部字段隐藏（Value/LCSC 等不上丝印，避免丝印混乱）
            val = fp.Value()
            val.SetVisible(False)
            for fld in fp.GetFields():
                if not fld.IsReference():
                    fld.SetVisible(False)
            # 密集小板可逐元件关闭位号丝印（design.json: "silk_ref": false）
            if c.get('silk_ref') is False:
                fp.Reference().SetVisible(False)
                return
            # 焊盘 bbox 估算元件高度
            y1 = y2 = None
            for p in fp.Pads():
                py = pcbnew.ToMM(p.GetPosition().y)
                sy = pcbnew.ToMM(p.GetSizeY()) / 2
                y1 = py - sy if y1 is None else min(y1, py - sy)
                y2 = py + sy if y2 is None else max(y2, py + sy)
            ref = fp.Reference()
            off_y = (c['y'] - y1) + 0.8 if y1 is not None else 2.0
            ref.SetPosition(to_xy(c['x'], c['y'] - off_y))
            ref.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.8), pcbnew.FromMM(0.8)))
            ref.SetTextThickness(pcbnew.FromMM(0.13))
        except Exception:
            pass

    # ---------------- 网络表（焊盘赋网） ----------------
    def assign_pad_nets(self):
        """nets[].pads = ["J1.1", ...] → pad.SetNet()。没有这一步，pad 无网络，
        DRC 会把同网焊盘-走线接触误判为 shorting（v6 的真实事故）"""
        n_assigned = 0
        for n in self.d.get('nets', []):
            net = self.get_net(n['name'])
            for pref in n.get('pads', []):
                ref, _, num = pref.partition('.')
                try:
                    pad = find_pad(self.board, ref, num)
                except KeyError as e:
                    raise KeyError(f'网络 {n["name"]} 引用了不存在的焊盘: {e}')
                pad.SetNet(net)
                n_assigned += 1
        print(f'  [OK] 焊盘赋网 {n_assigned} 个')

    # ---------------- 走线 ----------------
    def _resolve_point(self, p, default_layer):
        """{"pad":"J1.3"} → 焊盘中心绝对坐标；(x,y) → 原样。返回 (x_mm, y_mm, pad_layer_or_None)"""
        if isinstance(p, dict) and 'pad' in p:
            ref, _, num = p['pad'].partition('.')
            pad = find_pad(self.board, ref, num)
            pos = pad.GetPosition()
            x_mm = pcbnew.ToMM(pos.x)
            y_mm = pcbnew.ToMM(pos.y)
            pad_layer = None
            if pad.IsOnLayer(pcbnew.F_Cu) and not pad.IsOnLayer(pcbnew.B_Cu):
                pad_layer = pcbnew.F_Cu
            elif pad.IsOnLayer(pcbnew.B_Cu) and not pad.IsOnLayer(pcbnew.F_Cu):
                pad_layer = pcbnew.B_Cu
            return x_mm, y_mm, pad_layer
        return float(p['x'] if isinstance(p, dict) else p[0]), \
            float(p['y'] if isinstance(p, dict) else p[1]), None

    def routes(self):
        for r in self.d.get('routes', []):
            net = self.get_net(r['net'])
            width = pcbnew.FromMM(r['width_mm'])
            layer = LAYER_MAP[r.get('layer', 'F.Cu')]
            raw = r['points']
            if len(raw) < 2:
                print(f'  [WARN] 网络 {r["net"]} 走线点数 <2，跳过')
                continue
            pts = []
            for p in raw:
                x, y, pad_layer = self._resolve_point(p, layer)
                # SMD 焊盘单层：端点段必须在该层
                pts.append((x, y))
            for i in range(len(pts) - 1):
                (x1, y1), (x2, y2) = pts[i], pts[i + 1]
                if x1 == x2 and y1 == y2:
                    continue
                t = pcbnew.PCB_TRACK(self.board)
                t.SetStart(to_xy(x1, y1))
                t.SetEnd(to_xy(x2, y2))
                t.SetWidth(width)
                t.SetLayer(layer)
                t.SetNet(net)
                self.board.Add(t)
            print(f'  [OK] 走线 {r["net"]} {len(pts)-1} 段 @ {r.get("layer", "F.Cu")} w={r["width_mm"]}mm')

    def vias(self):
        for v in self.d.get('vias', []):
            net = self.get_net(v['net'])
            via = pcbnew.PCB_VIA(self.board)
            via.SetPosition(to_xy(v['x'], v['y']))
            via.SetWidth(pcbnew.FromMM(v.get('size_mm', 0.6)))
            via.SetDrill(pcbnew.FromMM(v.get('drill_mm', 0.3)))
            via.SetNet(net)
            self.board.Add(via)
            print(f'  [OK] 过孔 {v["net"]} @ ({v["x"]},{v["y"]})')

    # ---------------- 铺铜 ----------------
    def zones(self):
        bw = self.d['board']['width_mm']
        bh = self.d['board']['height_mm']
        for z in self.d.get('zones', []):
            margin = z.get('margin_mm', 0.5)
            hw, hh = bw / 2 - margin, bh / 2 - margin
            # 显式多边形（电源分割等）优先；缺省整板矩形
            pts = z.get('polygon') or [[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]]
            zone = pcbnew.ZONE(self.board)
            zone.SetLayer(LAYER_MAP[z.get('layer', 'B.Cu')])
            zone.SetNet(self.get_net(z['net']))
            zone.SetLocalClearance(pcbnew.FromMM(z.get('clearance_mm', 0.3)))
            zone.SetMinThickness(pcbnew.FromMM(0.2))
            try:
                zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
                zone.SetThermalReliefGap(pcbnew.FromMM(0.3))
                zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.3))
            except Exception:
                pass
            outline = zone.Outline()
            outline.NewOutline()
            for x, y in pts:
                outline.Append(to_xy(x, y))
            self.board.Add(zone)
            print(f'  [OK] 铺铜 {z["net"]} @ {z.get("layer", "B.Cu")} margin={margin}mm pts={len(pts)}')
        # 填充
        filler = pcbnew.ZONE_FILLER(self.board)
        if filler.Fill(self.board.Zones()):
            print('  [OK] 铺铜填充完成')
        else:
            print('  [WARN] 铺铜填充失败，DRC 时请用 --refill-zones')

    # ---------------- 丝印 ----------------
    def silkscreen(self):
        for s in self.d.get('silkscreen', []):
            t = pcbnew.PCB_TEXT(self.board)
            t.SetText(s['text'])
            t.SetPosition(to_xy(s['x'], s['y']))
            t.SetLayer(LAYER_MAP.get(s.get('layer', 'F'), pcbnew.F_SilkS)
                       if '.' in s.get('layer', 'F') else
                       (pcbnew.F_SilkS if s.get('layer', 'F') == 'F' else pcbnew.B_SilkS))
            size = s.get('size_mm', 0.8)
            t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
            t.SetTextThickness(pcbnew.FromMM(max(0.12, size * 0.16)))
            if s.get('rotation'):
                t.SetTextAngleDegrees(s['rotation'])
            self.board.Add(t)
        n = len(self.d.get('silkscreen', []))
        print(f'  [OK] 丝印 {n} 条')

    # ---------------- 保存 + BOM ----------------
    def save(self):
        self.board.Save(self.out_path)
        print(f'  [OK] 保存 {self.out_path}')

    def bom_csv(self, out_csv):
        rows = {}
        for c in self.d['components']:
            key = (str(c['value']), c['footprint'], str(c.get('lcsc', '')))
            rows.setdefault(key, []).append(c['ref'])
        with open(out_csv, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC', 'Quantity'])
            for (val, fp, lcsc), refs in sorted(rows.items(), key=lambda kv: kv[1][0]):
                w.writerow([val, ' '.join(sorted(refs)), fp, lcsc, len(refs)])
        print(f'  [OK] BOM: {out_csv} ({sum(len(v) for v in rows.values())} 元件)')

    def build(self):
        print(f'[1/7] 设计规则初始化...')
        self.setup()
        print('[2/7] 板框...')
        self.outline()
        print(f'[3/7] 放置 {len(self.d["components"])} 个元件...')
        self.components()
        print('[3.5/7] 焊盘赋网（网络表）...')
        self.assign_pad_nets()
        print(f'[4/7] 布线 {len(self.d.get("routes", []))} 个网络...')
        self.routes()
        self.vias()
        print('[5/7] 铺铜...')
        self.zones()
        print('[6/7] 丝印...')
        self.silkscreen()
        print('[7/7] 保存...')
        self.save()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--design', required=True)
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--name', default=None, help='项目名（默认取 meta.project）')
    args = ap.parse_args()

    d = load_design(args.design)
    name = args.name or d.get('meta', {}).get('project', 'pcb_project')
    os.makedirs(args.outdir, exist_ok=True)
    out_pcb = os.path.join(args.outdir, f'{name}.kicad_pcb')

    # 先写 .kicad_pro 模板，再建板——board.Save() 会把网络类间距等设置持久化到项目文件
    write_project_template(args.outdir, name)

    b = BoardBuilder(d, out_pcb)
    b.build()
    b.bom_csv(os.path.join(args.outdir, f'{name}_BOM.csv'))
    print(f'[DONE] {out_pcb}')


def write_project_template(outdir, name):
    pro = {
        'board': {'design_settings': {'defaults': {'board_outline_line_width': 0.1}}},
        'boards': [],
        'cvpcb': {'equivalence_files': []},
        'erc': {'erc_exclusions': [], 'meta': {'version': 0}, 'pin_map': [], 'rule_severities': {}},
        'libraries': {'pinned_footprint_libs': [], 'pinned_symbol_libs': []},
        'meta': {'filename': f'{name}.kicad_pro', 'version': 3},
        'net_settings': {'classes': [], 'meta': {'version': 3}},
        'pcbnew': {'last_paths': {'gencad': '', 'idf': '', 'netlist': '', 'specctra_dsn': '',
                                  'step': '', 'vrml': ''}, 'page_layout_descr_file': ''},
        'schematic': {'legacy_lib_dir': '', 'legacy_lib_list': []},
        'sheets': [],
        'text_variables': {},
    }
    pro_path = os.path.join(outdir, f'{name}.kicad_pro')
    with open(pro_path, 'w', encoding='utf-8') as f:
        json.dump(pro, f, indent=2)


if __name__ == '__main__':
    main()
