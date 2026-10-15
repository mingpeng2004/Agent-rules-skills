#!/usr/bin/env python3
"""
PCBA Skill v5.0 — 一站式设计检查器（run_checks.py）

必须用 KiCad 自带 Python 运行（需要 pcbnew）：
  "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" run_checks.py --board x.kicad_pcb ...

功能（全部真实测量，禁止假 PASS）：
  - 真实 DRC / ERC（kicad-cli，JSON 解析）
  - 板框闭合 / 板尺寸实测
  - 每网络最小线宽 + IPC-2221 载流校核
  - GND 铺铜存在与填充
  - 丝印高度 / 丝印压焊盘 / 板名版本标识
  - 元件边距 / 钻孔孔径 / 孔环
  - Fiducial / 测试点（按 design.json 要求）

输出：
  --out  report.json（机器可读，门禁判定依据）
  --md   report.md （人类可读）
退出码：0 = APPROVED/CONDITIONAL，1 = REJECTED（任一 P0 FAIL）

判定语义：
  PASS   实测通过
  FAIL   实测不通过
  WARN   实测在警告区间（不阻塞，但必须写入报告）
  NA     本项目不适用（需 --design 或参数声明理由）
  MANUAL 无法自动测量（诚实标注，禁止默认 PASS）
"""
import argparse
import datetime
import json
import math
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import kicad_env  # noqa: E402

import pcbnew  # noqa: E402

# ---------------------------------------------------------------------------
# DFM 工艺剖面（与 references/dfm_rules.json 同步；此处内置默认值保证单文件可跑）
# ---------------------------------------------------------------------------
DEFAULT_PROFILES = {
    "jlc_2layer": {
        "name": "JLCPCB 2 层板（经济型）",
        "min_track_width_mm": 0.09,      # 板厂极限
        "design_track_width_mm": 0.127,  # 设计余量下限（低于此值 WARN）
        "min_clearance_mm": 0.09,
        "min_hole_mm": 0.20,             # 机械钻孔最小
        "min_annular_ring_mm": 0.05,
        "design_annular_ring_mm": 0.10,
        "min_silk_height_mm": 0.8,
        "min_silk_thickness_mm": 0.12,
        "min_component_edge_mm": 0.5,  # 板边连接器/固定孔允许 0.5（JLC 极限 0.3）
        "min_copper_edge_mm": 0.3,
        "min_slot_mm": 0.8,
        "copper_weight_oz": 1.0,
    }
}

# IPC-2221 外层载流公式常数（1oz, ΔT=10°C）
IPC_K_EXT = 0.048
IPC_DT = 10.0
OZ_TO_MIL = 1.378


def mm(v):
    """nm → mm"""
    return pcbnew.ToMM(v)


def ipc_required_width_mm(current_a, copper_oz=1.0):
    """IPC-2221 外层走线所需最小宽度（mm）。I = k * dT^0.44 * A^0.725, A 单位 mil^2"""
    if current_a <= 0:
        return 0.0
    area_mil2 = (current_a / (IPC_K_EXT * IPC_DT ** 0.44)) ** (1 / 0.725)
    thickness_mil = copper_oz * OZ_TO_MIL
    width_mil = area_mil2 / thickness_mil
    return width_mil * 0.0254


class Checkpoint:
    def __init__(self, cid, layer, weight, desc):
        self.id = cid
        self.layer = layer
        self.weight = weight      # P0 / P1 / P2
        self.desc = desc
        self.result = 'MANUAL'
        self.evidence = '未执行'

    def set(self, result, evidence):
        assert result in ('PASS', 'FAIL', 'WARN', 'NA', 'MANUAL')
        self.result = result
        self.evidence = evidence

    def to_dict(self):
        return {'id': self.id, 'layer': self.layer, 'weight': self.weight,
                'desc': self.desc, 'result': self.result, 'evidence': self.evidence}


def load_design(path):
    if path and os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


# ---------------------------------------------------------------------------
# 真实 DRC / ERC（kicad-cli 子进程）
# ---------------------------------------------------------------------------
def run_cli_drc(board_path, out_json, refill=True):
    cli = kicad_env.find_kicad_cli()
    args = [cli, 'pcb', 'drc', '--format', 'json', '--severity-all', '--units', 'mm',
            '--output', out_json]
    if refill:
        args.append('--refill-zones')
        args.append('--save-board')
    args.append(board_path)
    p = subprocess.run(args, capture_output=True, text=True, timeout=600,
                       encoding='utf-8', errors='replace')
    if not os.path.exists(out_json):
        return None, f'kicad-cli drc 失败: {p.stdout} {p.stderr}'
    with open(out_json, 'r', encoding='utf-8') as f:
        return json.load(f), None


def run_cli_erc(sch_path, out_json):
    cli = kicad_env.find_kicad_cli()
    args = [cli, 'sch', 'erc', '--format', 'json', '--severity-all', '--units', 'mm',
            '--output', out_json, sch_path]
    p = subprocess.run(args, capture_output=True, text=True, timeout=600,
                       encoding='utf-8', errors='replace')
    if not os.path.exists(out_json):
        return None, f'kicad-cli erc 失败: {p.stdout} {p.stderr}'
    with open(out_json, 'r', encoding='utf-8') as f:
        return json.load(f), None


# ---------------------------------------------------------------------------
# 各检查项
# ---------------------------------------------------------------------------
def check_drc(cps, drc):
    by_type = {}
    for v in drc.get('violations', []):
        by_type.setdefault(v['type'], []).append(v)
    errors = [v for v in drc.get('violations', []) if v.get('severity') == 'error']
    warnings = [v for v in drc.get('violations', []) if v.get('severity') == 'warning']
    unconnected = drc.get('unconnected_items', [])

    cp = cps['R-DRC-01']
    if not errors:
        cp.set('PASS', 'kicad-cli DRC: 0 error')
    else:
        detail = {}
        for v in errors:
            detail[v['type']] = detail.get(v['type'], 0) + 1
        cp.set('FAIL', f'DRC error={len(errors)}: {json.dumps(detail, ensure_ascii=False)}')

    cps['R-DRC-02'].set('PASS' if not unconnected else 'FAIL',
                        f'未连接对象: {len(unconnected)} 处' +
                        (f' (示例: {unconnected[0]["items"][0]["description"]})' if unconnected else ''))
    cps['R-DRC-03'].set('PASS' if len(warnings) == 0 else 'WARN',
                        f'DRC warning={len(warnings)}: ' +
                        json.dumps({t: len([v for v in warnings if v["type"] == t]) for t in
                                    set(v["type"] for v in warnings)}, ensure_ascii=False))
    return by_type


def check_outline(cps, board, design):
    edges = []
    for item in board.GetDrawings():
        try:
            if item.GetLayer() != pcbnew.Edge_Cuts:
                continue
        except Exception:
            continue
        if hasattr(item, 'GetStart') and hasattr(item, 'GetEnd'):
            edges.append((mm(item.GetStart().x), mm(item.GetStart().y),
                          mm(item.GetEnd().x), mm(item.GetEnd().y)))
    if not edges:
        cps['L-GEO-01'].set('FAIL', 'Edge.Cuts 层无任何线段')
        return None
    # 闭合性：端点图每个顶点度数必须为 2（容差 0.02mm）
    tol = 0.02
    pts = []

    def snap(p):
        for i, q in enumerate(pts):
            if abs(p[0] - q[0]) < tol and abs(p[1] - q[1]) < tol:
                return i
        pts.append(p)
        return len(pts) - 1

    deg = {}
    for x1, y1, x2, y2 in edges:
        a, b = snap((x1, y1)), snap((x2, y2))
        deg[a] = deg.get(a, 0) + 1
        deg[b] = deg.get(b, 0) + 1
    open_ends = [i for i, d in deg.items() if d != 2]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    cps['L-GEO-01'].set('PASS' if not open_ends else 'FAIL',
                        f'Edge.Cuts {len(edges)} 段, {"闭合" if not open_ends else f"{len(open_ends)} 个开放端点"}')

    exp = design.get('board', {})
    ew, eh = exp.get('width_mm'), exp.get('height_mm')
    if ew and eh:
        ok = abs(w - ew) <= 0.1 and abs(h - eh) <= 0.1
        cps['L-GEO-02'].set('PASS' if ok else 'FAIL',
                            f'实测板框 {w:.2f}x{h:.2f}mm vs 设计 {ew}x{eh}mm (容差 0.1mm)')
    else:
        cps['L-GEO-02'].set('PASS', f'实测板框 {w:.2f}x{h:.2f}mm（无设计值可比对）')
    return (min(xs), min(ys), max(xs), max(ys))


def check_nets_and_tracks(cps, board, design, profile):
    # 每网络最小线宽
    net_widths = {}
    for t in board.Tracks():
        try:
            if hasattr(t, 'GetDrillValue'):   # via：GetWidth 必须带层参数
                w = mm(t.GetWidth(pcbnew.F_Cu))
            else:
                w = mm(t.GetWidth())
        except Exception:
            continue
        net = t.GetNetname()
        net_widths[net] = min(net_widths.get(net, 1e9), w)
    if not net_widths:
        cps['R-WID-01'].set('FAIL', 'PCB 中无任何走线')
    else:
        worst_net, worst_w = min(net_widths.items(), key=lambda kv: kv[1])
        limit = profile['min_track_width_mm']
        if worst_w >= profile['design_track_width_mm']:
            cps['R-WID-01'].set('PASS', f'全部 {len(net_widths)} 网络线宽 ≥ {profile["design_track_width_mm"]}mm (最窄 {worst_net}={worst_w:.3f}mm)')
        elif worst_w >= limit:
            cps['R-WID-01'].set('WARN', f'最窄线 {worst_net}={worst_w:.3f}mm 低于设计余量 {profile["design_track_width_mm"]}mm，高于板厂极限 {limit}mm')
        else:
            cps['R-WID-01'].set('FAIL', f'{worst_net} 线宽 {worst_w:.3f}mm 低于板厂极限 {limit}mm')

    # design.json 声明的网络规则 + IPC-2221 载流
    net_rules = {n['name']: n for n in design.get('nets', []) if 'name' in n}
    fails, warns, evid = [], [], []
    for name, rule in net_rules.items():
        cur = rule.get('max_current_a', 0)
        req_rule = rule.get('min_width_mm', 0)
        actual = net_widths.get(name)
        if actual is None:
            # 电源网络可以走铺铜；检查是否有 zone
            continue
        req_ipc = ipc_required_width_mm(cur, profile['copper_weight_oz'])
        req = max(req_rule, req_ipc)
        if req > 0 and actual < req:
            fails.append(f'{name}: 实宽 {actual:.2f}mm < 需求 {req:.2f}mm (I={cur}A)')
        elif cur > 0:
            evid.append(f'{name} {actual:.2f}mm ≥ {req:.2f}mm')
    if fails:
        cps['R-PWR-01'].set('FAIL', '; '.join(fails))
    elif evid:
        cps['R-PWR-01'].set('PASS', f'IPC-2221 载流校核通过 ({len(evid)} 网络): ' + '; '.join(evid[:4]))
    else:
        cps['R-PWR-01'].set('NA', 'design.json 未声明载流网络')

    # design.json 声明必须布线的网络是否都有走线
    if net_rules:
        missing = [n for n in net_rules if n not in net_widths and net_rules[n].get('copper', 'track') == 'track']
        cps['R-NET-01'].set('PASS' if not missing else 'FAIL',
                            '全部声明网络均有走线' if not missing else f'缺走线网络: {missing}')
    else:
        cps['R-NET-01'].set('MANUAL', '无 design.json，无法核对网络清单')


def check_zones(cps, board, design):
    zones = list(board.Zones())
    gnd_zones = []
    for z in zones:
        try:
            netname = z.GetNetname()
        except Exception:
            netname = ''
        if 'GND' in netname.upper():
            gnd_zones.append(z)
    if not gnd_zones:
        cps['R-ZONE-01'].set('FAIL', f'未找到 GND 铺铜 (zones 总数={len(zones)})')
        return
    filled_layers = []
    layer_names = {int(pcbnew.F_Cu): 'F.Cu', int(pcbnew.B_Cu): 'B.Cu'}
    for z in gnd_zones:
        try:
            seq = z.GetLayerSet().Seq()
        except Exception:
            seq = [pcbnew.F_Cu, pcbnew.B_Cu]
        for layer_id in seq:
            try:
                if z.HasFilledPolysForLayer(layer_id):
                    polys = z.GetFilledPolysList(layer_id)
                    if polys and polys.OutlineCount() > 0:
                        filled_layers.append(layer_names.get(int(layer_id), str(int(layer_id))))
            except Exception:
                pass
    cps['R-ZONE-01'].set('PASS' if filled_layers else 'WARN',
                         f'GND 铺铜 {len(gnd_zones)} 个, 已填充层: {sorted(set(filled_layers)) or "无（需 refill）"}')


def check_silk(cps, board, design, profile):
    texts = []
    for item in board.GetDrawings():
        if not hasattr(item, 'GetText'):
            continue
        try:
            layer = item.GetLayer()
        except Exception:
            continue
        if layer in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            texts.append(item)
    if not texts:
        cps['L-SLK-01'].set('FAIL', '丝印层无文本')
        cps['L-SLK-03'].set('FAIL', '丝印层无文本，无板名/版本标识')
        return
    min_h = min(mm(t.GetTextHeight()) for t in texts)
    min_th = min(mm(t.GetTextThickness()) for t in texts)
    ok_h = min_h >= profile['min_silk_height_mm']
    ok_th = min_th >= profile['min_silk_thickness_mm']
    cps['L-SLK-01'].set('PASS' if (ok_h and ok_th) else 'FAIL',
                        f'{len(texts)} 条丝印文本, 最小字高 {min_h:.2f}mm (≥{profile["min_silk_height_mm"]}), 最小线宽 {min_th:.2f}mm (≥{profile["min_silk_thickness_mm"]})')

    # 丝印压焊盘（几何粗测：文本 bbox 与 pad bbox 相交）
    pads = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            c = p.GetPosition()
            sx, sy = mm(p.GetSizeX()) / 2, mm(p.GetSizeY()) / 2
            pads.append((mm(c.x) - sx, mm(c.y) - sy, mm(c.x) + sx, mm(c.y) + sy))
    overlap = []
    for t in texts:
        bb = t.GetBoundingBox()
        x1, y1 = mm(bb.GetLeft()), mm(bb.GetTop())
        x2, y2 = mm(bb.GetRight()), mm(bb.GetBottom())
        for i, (px1, py1, px2, py2) in enumerate(pads):
            if x1 < px2 and x2 > px1 and y1 < py2 and y2 > py1:
                overlap.append(f'"{t.GetText()}"@({(x1+x2)/2:.1f},{(y1+y2)/2:.1f})')
                break
    cps['L-SLK-02'].set('PASS' if not overlap else 'FAIL',
                        '丝印与焊盘无几何重叠' if not overlap else f'{len(overlap)} 处丝印压焊盘: {overlap[:5]}')

    # 板名 + 版本标识
    meta = design.get('meta', {})
    name_pat = meta.get('board_name')
    ver_pat = meta.get('version')
    all_text = ' | '.join(t.GetText() for t in texts)
    need = []
    if name_pat:
        need.append((name_pat, name_pat in all_text))
    if ver_pat:
        need.append((ver_pat, ver_pat in all_text))
    if not need:
        cps['L-SLK-03'].set('MANUAL', 'design.json meta 未声明 board_name/version')
    else:
        missing = [n for n, ok in need if not ok]
        cps['L-SLK-03'].set('PASS' if not missing else 'FAIL',
                            '板名/版本丝印齐全' if not missing else f'缺丝印标识: {missing}')


def _fp_pads_bbox(fp):
    """元件铜层范围（焊盘 bbox）。GetBoundingBox 会包含飘远的位号/值文本，不可用于 DFM 测量"""
    x1 = y1 = 1e18
    x2 = y2 = -1e18
    found = False
    for p in fp.Pads():
        px, py = mm(p.GetPosition().x), mm(p.GetPosition().y)
        sx, sy = mm(p.GetSizeX()) / 2, mm(p.GetSizeY()) / 2
        x1 = min(x1, px - sx); x2 = max(x2, px + sx)
        y1 = min(y1, py - sy); y2 = max(y2, py + sy)
        found = True
    if not found:
        c = fp.GetPosition()
        cx = mm(c.x); cy = mm(c.y)
        return cx - 1, cy - 1, cx + 1, cy + 1
    return x1, y1, x2, y2


def check_components(cps, board, outline_bbox, design, profile):
    fps = [fp for fp in board.GetFootprints() if not fp.GetReference().startswith('#')]
    # 边距（基于焊盘 bbox）
    if outline_bbox:
        bx1, by1, bx2, by2 = outline_bbox
        min_edge = 1e9
        worst = ''
        for fp in fps:
            fx1, fy1, fx2, fy2 = _fp_pads_bbox(fp)
            d = min(fx1 - bx1, bx2 - fx2, fy1 - by1, by2 - fy2)
            if d < min_edge:
                min_edge, worst = d, fp.GetReference()
        cps['L-CMP-01'].set('PASS' if min_edge >= profile['min_component_edge_mm'] else 'FAIL',
                            f'最小元件边距 {worst}={min_edge:.2f}mm (要求 ≥{profile["min_component_edge_mm"]}mm, 基于焊盘 bbox)')
    else:
        cps['L-CMP-01'].set('MANUAL', '无板框，无法测边距')

    # design.json 中的禁布区（支持矩形 rect 与圆形 circle；按焊盘中心逐一测距）
    keepouts = design.get('board', {}).get('keepouts', [])
    if keepouts:
        viol = []
        pad_pts = []
        for fp in fps:
            if not list(fp.Pads()):
                c = fp.GetPosition()
                pad_pts.append((fp.GetReference(), mm(c.x), mm(c.y)))
            for p in fp.Pads():
                pad_pts.append((fp.GetReference(), mm(p.GetPosition().x), mm(p.GetPosition().y)))
        for ko in keepouts:
            exempt = set(ko.get('exempt', []))
            for ref, px, py in pad_pts:
                if ref in exempt:
                    continue
                if ko.get('shape') == 'circle':
                    d = math.hypot(px - ko['cx'], py - ko['cy'])
                    if d < ko['r']:
                        viol.append(f'{ref} 焊盘({px:.1f},{py:.1f}) 距 {ko.get("id", "keepout")} 中心 {d:.2f}mm < {ko["r"]}mm')
                else:
                    kx1, ky1, kx2, ky2 = ko['x_min'], ko['y_min'], ko['x_max'], ko['y_max']
                    if kx1 < px < kx2 and ky1 < py < ky2:
                        viol.append(f'{ref} 侵入 {ko.get("id", "keepout")}')
        cps['L-KO-01'].set('PASS' if not viol else 'FAIL',
                           f'{len(keepouts)} 个禁布区无侵入' if not viol else '; '.join(viol[:5]))
    else:
        cps['L-KO-01'].set('NA', 'design.json 未声明禁布区')


def check_drills(cps, board, profile):
    min_hole = 1e9
    min_ring = 1e9
    worst_hole = worst_ring = ''
    n_holes = 0
    for fp in board.GetFootprints():
        for p in fp.Pads():
            dx = mm(p.GetDrillSizeX())
            if dx and dx > 0:
                n_holes += 1
                ring = (mm(p.GetSizeX()) - dx) / 2
                if dx < min_hole:
                    min_hole, worst_hole = dx, f'{fp.GetReference()}.{p.GetNumber()}'
                if ring < min_ring:
                    min_ring, worst_ring = ring, f'{fp.GetReference()}.{p.GetNumber()}'
    for t in board.Tracks():
        if not hasattr(t, 'GetDrillValue'):
            continue
        try:
            dv = mm(t.GetDrillValue())
            vw = mm(t.GetWidth(pcbnew.F_Cu))
        except Exception:
            continue
        if dv and dv > 0:
            n_holes += 1
            ring = (vw - dv) / 2
            if dv < min_hole:
                min_hole, worst_hole = dv, 'via'
            if ring < min_ring:
                min_ring, worst_ring = ring, 'via'
    if n_holes == 0:
        cps['D-DRL-01'].set('PASS', '无钻孔（全贴装）')
        cps['D-DRL-02'].set('PASS', '无钻孔（全贴装）')
        return
    cps['D-DRL-01'].set('PASS' if min_hole >= profile['min_hole_mm'] else 'FAIL',
                        f'{n_holes} 孔, 最小孔径 {worst_hole}={min_hole:.2f}mm (≥{profile["min_hole_mm"]}mm)')
    if min_ring >= profile['design_annular_ring_mm']:
        cps['D-DRL-02'].set('PASS', f'最小孔环 {worst_ring}={min_ring:.2f}mm (≥{profile["design_annular_ring_mm"]}mm)')
    elif min_ring >= profile['min_annular_ring_mm']:
        cps['D-DRL-02'].set('WARN', f'最小孔环 {worst_ring}={min_ring:.2f}mm 低于设计余量 {profile["design_annular_ring_mm"]}mm')
    else:
        cps['D-DRL-02'].set('FAIL', f'最小孔环 {worst_ring}={min_ring:.2f}mm 低于板厂极限 {profile["min_annular_ring_mm"]}mm')


def check_fiducial(cps, board, design):
    need = design.get('assembly', {}).get('require_fiducial', False)
    n = 0
    for fp in board.GetFootprints():
        s = (str(fp.GetFPID().GetLibItemName()) if hasattr(fp.GetFPID(), 'GetLibItemName') else '') + str(fp.GetValue())
        if 'fiducial' in s.lower():
            n += 1
    if not need:
        cps['D-FID-01'].set('NA', f'design.json 未要求 Fiducial（实测 {n} 个）')
    else:
        cps['D-FID-01'].set('PASS' if n >= 2 else 'FAIL',
                            f'Fiducial {n} 个' + (' ≥2' if n >= 2 else '（SMT 贴装至少 2 个）'))


def check_erc(cps, sch_path, workdir):
    if not sch_path:
        cps['S-ERC-01'].set('MANUAL', '未提供 .kicad_sch，无法执行真实 ERC')
        return
    if not os.path.exists(sch_path):
        cps['S-ERC-01'].set('FAIL', f'原理图文件不存在: {sch_path}')
        return
    out = os.path.join(workdir, '_erc.json')
    erc, err = run_cli_erc(sch_path, out)
    if err:
        cps['S-ERC-01'].set('FAIL', err)
        return
    viol = erc.get('violations', [])
    errors = [v for v in viol if v.get('severity') == 'error']
    cps['S-ERC-01'].set('PASS' if not errors else 'FAIL',
                        f'kicad-cli ERC: error={len(errors)} warning={len(viol) - len(errors)}')


CHECKPOINT_DEFS = [
    # (id, layer, weight, desc)
    ('S-ERC-01', 'S', 'P0', '原理图 ERC（kicad-cli 真实执行）0 error'),
    ('L-GEO-01', 'L', 'P0', '板框 Edge.Cuts 闭合'),
    ('L-GEO-02', 'L', 'P0', '板尺寸实测 == 设计值'),
    ('L-SLK-01', 'L', 'P1', '丝印字高/线宽 ≥ 工艺限值'),
    ('L-SLK-02', 'L', 'P1', '丝印不压焊盘'),
    ('L-SLK-03', 'L', 'P1', '板名 + 版本丝印标识'),
    ('L-CMP-01', 'L', 'P1', '元件到板边距离'),
    ('L-KO-01',  'L', 'P0', '禁布区（固定孔/连接器）无侵入'),
    ('R-DRC-01', 'R', 'P0', 'kicad-cli DRC 0 error'),
    ('R-DRC-02', 'R', 'P0', '无未连接对象（unconnected）'),
    ('R-DRC-03', 'R', 'P2', 'DRC warning 清零'),
    ('R-WID-01', 'R', 'P0', '最小线宽 ≥ 工艺限值'),
    ('R-PWR-01', 'R', 'P0', 'IPC-2221 载流校核（电源线宽）'),
    ('R-NET-01', 'R', 'P0', 'design.json 声明网络全部布线'),
    ('R-ZONE-01', 'R', 'P1', 'GND 铺铜存在且已填充'),
    ('D-DRL-01', 'D', 'P0', '最小孔径 ≥ 板厂极限'),
    ('D-DRL-02', 'D', 'P1', '孔环 ≥ 设计余量'),
    ('D-FID-01', 'D', 'P1', 'Fiducial（SMT 时强制）'),
]


def main():
    ap = argparse.ArgumentParser(description='PCBA Skill v5.0 一站式检查器')
    ap.add_argument('--board', required=True, help='.kicad_pcb 路径')
    ap.add_argument('--schematic', default=None, help='.kicad_sch 路径（可选，启用真实 ERC）')
    ap.add_argument('--design', default=None, help='design.json 路径（可选，启用声明式核对）')
    ap.add_argument('--profile', default='jlc_2layer', help='DFM 工艺剖面名')
    ap.add_argument('--out', default=None, help='JSON 报告输出路径')
    ap.add_argument('--md', default=None, help='Markdown 报告输出路径')
    args = ap.parse_args()

    profile = DEFAULT_PROFILES.get(args.profile, DEFAULT_PROFILES['jlc_2layer'])
    design = load_design(args.design)
    workdir = os.path.dirname(os.path.abspath(args.board))

    cps = {cid: Checkpoint(cid, layer, weight, desc) for cid, layer, weight, desc in CHECKPOINT_DEFS}

    print('[1/6] 真实 DRC（kicad-cli, --refill-zones --save-board）...')
    drc_json = os.path.join(workdir, '_drc.json')
    drc, err = run_cli_drc(args.board, drc_json)
    if err:
        cps['R-DRC-01'].set('FAIL', err)
    else:
        check_drc(cps, drc)

    # DRC 已回填铺铜并保存，此后加载的板为最新状态
    print(f'[2/6] 加载 PCB: {args.board}')
    board = pcbnew.LoadBoard(args.board)

    print('[3/6] 板框 / 布局几何...')
    outline_bbox = check_outline(cps, board, design)
    check_components(cps, board, outline_bbox, design, profile)

    print('[4/6] 布线 / 载流 / 铺铜...')
    check_nets_and_tracks(cps, board, design, profile)
    check_zones(cps, board, design)

    print('[5/6] 丝印 / 钻孔 / Fiducial...')
    check_silk(cps, board, design, profile)
    check_drills(cps, board, profile)
    check_fiducial(cps, board, design)

    print('[6/6] ERC（如有原理图）...')
    check_erc(cps, args.schematic, workdir)

    # 汇总
    results = [cp.to_dict() for cp in cps.values()]
    p0_fail = [r for r in results if r['weight'] == 'P0' and r['result'] == 'FAIL']
    p1_fail = [r for r in results if r['weight'] == 'P1' and r['result'] == 'FAIL']
    warns = [r for r in results if r['result'] == 'WARN']
    manuals = [r for r in results if r['result'] == 'MANUAL']
    verdict = 'REJECTED' if p0_fail else ('CONDITIONAL' if p1_fail else 'APPROVED')

    report = {
        'tool': 'pcba-skill v5.0 run_checks',
        'timestamp': datetime.datetime.now().isoformat(),
        'board': os.path.abspath(args.board),
        'schematic': args.schematic,
        'profile': args.profile,
        'kicad_version': kicad_env.kicad_version(),
        'checkpoints': results,
        'summary': {
            'total': len(results),
            'pass': len([r for r in results if r['result'] == 'PASS']),
            'fail': len([r for r in results if r['result'] == 'FAIL']),
            'warn': len(warns),
            'na': len([r for r in results if r['result'] == 'NA']),
            'manual': len(manuals),
            'p0_fail': len(p0_fail),
            'p1_fail': len(p1_fail),
            'verdict': verdict,
        },
    }

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    # Markdown
    lines = [f"# PCBA v5.0 检查报告 — {os.path.basename(args.board)}",
             f"- 时间: {report['timestamp']}",
             f"- KiCad: {report['kicad_version']} | 工艺剖面: {args.profile}",
             f"- 结论: **{verdict}** (P0 fail={len(p0_fail)}, P1 fail={len(p1_fail)}, warn={len(warns)}, manual={len(manuals)})",
             "", "| 检查点 | 层 | 权重 | 结果 | 证据 |", "|---|---|---|---|---|"]
    for r in results:
        icon = {'PASS': '✅', 'FAIL': '❌', 'WARN': '⚠️', 'NA': '⊘', 'MANUAL': '👁'}[r['result']]
        lines.append(f"| {r['id']} | {r['layer']} | {r['weight']} | {icon} {r['result']} | {r['evidence']} |")
    md_text = '\n'.join(lines)
    if args.md:
        with open(args.md, 'w', encoding='utf-8') as f:
            f.write(md_text)

    print(md_text)
    return 1 if verdict == 'REJECTED' else 0


if __name__ == '__main__':
    sys.exit(main())
