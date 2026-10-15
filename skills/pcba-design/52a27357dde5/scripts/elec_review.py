#!/usr/bin/env python3
"""
PCBA Skill v5.1 — 电气审查层（elec_review.py）

用 KiCad 自带 Python 运行：
  python.exe elec_review.py --board dist/x.kicad_pcb --design design.json [--report elec.json]

定位：回答"这板子上电能不能工作"，补足 run_checks.py（几何/工艺）之外的电气维度：
  E1  连通性逻辑核对：design.json intent.connections 声明的引脚对必须真实连通
      （穿透 nets[].pads + 元件 passthrough，BFS 验证——抓 MOSI/MISO 接反这类逻辑错）
  E2  拓扑规则审查：去耦电容就位（距离实测）、串联端接阻值、上拉/下拉声明核对
  E3  信号完整性估算：微带线特征阻抗（IPC-2141 公式）+ 临界长度判定
  E4  回流路径：F.Cu 信号线逐段采样，验证 B.Cu GND 铺铜覆盖 + 铺铜孤岛计数
  E5  电源压降：按 design.json 声明电流与实测走线几何算 IR Drop（1oz 铜）
  E6  SPICE 引擎自检：ngspice.dll 冒烟测试（.op 分析），为模拟电路仿真铺路

退出码：0 = APPROVED/CONDITIONAL，1 = REJECTED（任一 P0 FAIL）
"""
import argparse
import ctypes
import json
import math
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import kicad_env  # noqa: E402

import pcbnew  # noqa: E402

CU_RESISTIVITY = 1.724e-8      # 铜电阻率 Ω·m
CU_THICK_M = 35e-6             # 1oz = 35µm
ER_FR4 = 4.4                   # FR4 介电常数（微带线估算）
VP_M_PER_NS = 0.15             # FR4 信号传播速度 m/ns


def mm(v):
    return pcbnew.ToMM(v)


class CP:
    def __init__(self, cid, weight, desc):
        self.id, self.weight, self.desc = cid, weight, desc
        self.result, self.evidence = 'MANUAL', '未执行'

    def set(self, r, e):
        self.result, self.evidence = r, e

    def to_dict(self):
        return {'id': self.id, 'weight': self.weight, 'desc': self.desc,
                'result': self.result, 'evidence': self.evidence}


# ---------------------------------------------------------------------------
# E1 连通性逻辑核对
# ---------------------------------------------------------------------------
def check_e1(cp, design):
    intent = design.get('intent', {})
    conns = intent.get('connections', [])
    if not conns:
        cp.set('MANUAL', 'design.json 未声明 intent.connections，跳过逻辑连通核对')
        return
    # 建图：pad -> net；passthrough 元件内部全连接
    pad_net = {}
    for n in design.get('nets', []):
        for p in n.get('pads', []):
            pad_net[p] = n['name']
    comp_pass = {c['ref'] for c in design.get('components', []) if c.get('passthrough')}

    def reachable(a, b):
        """BFS：net 成员边 + passthrough 元件内部边"""
        graph = {}
        for pad, net in pad_net.items():
            graph.setdefault(pad, set()).add(f'net:{net}')
            graph.setdefault(f'net:{net}', set()).add(pad)
        for pad in pad_net:
            ref = pad.split('.')[0]
            if ref in comp_pass:
                for other in pad_net:
                    if other != pad and other.split('.')[0] == ref:
                        graph[pad].add(other)
                        graph[other].add(pad)
        seen, stack = set(), [a]
        while stack:
            node = stack.pop()
            if node == b:
                return True
            if node in seen:
                continue
            seen.add(node)
            stack.extend(graph.get(node, ()))
        return False

    fails = [f'{a}↔{b}' for a, b in conns if not reachable(a, b)]
    cp.set('PASS' if not fails else 'FAIL',
           f'{len(conns)} 组声明连通全部达成' if not fails else f'{len(fails)} 组不连通: {fails[:6]}')


def check_e1b(cp, design):
    """引脚功能表 vs 实际网络（防 MOSI/MISO 接反）"""
    intent = design.get('intent', {})
    pin_map = intent.get('pin_map', {})
    aliases = intent.get('net_aliases', {})
    if not pin_map:
        cp.set('MANUAL', 'design.json 未声明 intent.pin_map')
        return
    pad_net = {}
    for n in design.get('nets', []):
        for p in n.get('pads', []):
            pad_net[p] = n['name']
    fails = []
    for ref, pins in pin_map.items():
        for pin, func in pins.items():
            net = pad_net.get(f'{ref}.{pin}')
            expected = aliases.get(func, [func])
            # 允许网络名为 SPI_SCK_OUT 这类带 _OUT/_IN 后缀的变体
            ok = net and any(net == a or net.startswith(a + '_') for a in expected)
            if not ok:
                fails.append(f'{ref}.{pin} 应为 {func}({expected})，实为 {net}')
    cp.set('PASS' if not fails else 'FAIL',
           f'{sum(len(p) for p in pin_map.values())} 个引脚功能全部对网正确' if not fails
           else '; '.join(fails[:6]))


# ---------------------------------------------------------------------------
# E2 拓扑规则
# ---------------------------------------------------------------------------
def check_e2_decoupling(cp, design):
    rules = design.get('intent', {}).get('decoupling', [])
    if not rules:
        cp.set('MANUAL', 'design.json 未声明 intent.decoupling')
        return
    comps = {c['ref']: c for c in design.get('components', [])}
    caps = [c for c in design['components'] if c['ref'].startswith('C')]
    fails, notes = [], []
    for r in rules:
        near = comps.get(r['near_ref'])
        if not near:
            fails.append(f"{r['near_ref']} 不存在")
            continue
        max_d = r.get('max_dist_mm', 5.0)
        best = min((math.hypot(c['x'] - near['x'], c['y'] - near['y']) for c in caps),
                   default=None)
        if best is None:
            fails.append(f'{r["net"]} 无去耦电容')
        elif best > max_d:
            fails.append(f'{r["net"]} 最近去耦 {best:.1f}mm > {max_d}mm')
        else:
            notes.append(f"{r['net']} 去耦 {best:.1f}mm ≤ {max_d}mm")
    cp.set('PASS' if not fails else 'FAIL', '; '.join(notes + fails))


def check_e2_termination(cp, design):
    terms = design.get('intent', {}).get('series_termination', {})
    if not terms:
        cp.set('MANUAL', 'design.json 未声明 intent.series_termination')
        return
    comps = {c['ref']: c for c in design.get('components', [])}
    pad_net = {}
    for n in design.get('nets', []):
        for p in n.get('pads', []):
            pad_net[p] = n['name']
    fails, notes = [], []
    for net_name, rule in terms.items():
        want = rule.get('value_ohm', 22)
        # 该网络的 pads 上找 passthrough 的 R 元件
        found = None
        for pad, net in pad_net.items():
            if net != net_name:
                continue
            ref = pad.split('.')[0]
            c = comps.get(ref)
            if c and c.get('passthrough') and ref.startswith('R'):
                val = str(c.get('value', ''))
                import re as _re
                m = _re.search(r'([\d.]+)\s*[RrΩ]?', val)
                if m and abs(float(m.group(1)) - want) <= want * rule.get('tolerance', 0.5):
                    found = f'{ref}={val}'
        if found:
            notes.append(f'{net_name} 端接 {found}')
        else:
            fails.append(f'{net_name} 缺 {want}Ω 串联端接')
    cp.set('PASS' if not fails else 'FAIL', '; '.join(notes + fails))


# ---------------------------------------------------------------------------
# E3 信号完整性估算
# ---------------------------------------------------------------------------
def microstrip_z0(width_mm, height_mm, t_mm=0.035, er=ER_FR4):
    """IPC-2141 微带线近似公式"""
    w = max(width_mm, 0.01)
    return 87.0 / math.sqrt(er + 1.41) * math.log(5.98 * height_mm / (0.8 * w + t_mm))


def check_e3(cp, board, design):
    thick = design.get('board', {}).get('thickness_mm', 1.6)
    h = thick - 0.035                      # 2 层板：顶层到地层介质厚度
    nets_decl = {n['name']: n for n in design.get('nets', [])}
    edge_ns = design.get('intent', {}).get('signal', {}).get('edge_rate_ns', 5.0)
    lcrit_mm = VP_M_PER_NS * edge_ns * 1000 / 6   # 集总 vs 分布临界（经验 1/6 规则）
    # 每网络线长与线宽
    stats = {}
    for t in board.Tracks():
        if hasattr(t, 'GetDrillValue'):
            continue
        net = t.GetNetname()
        seg = mm(t.GetLength())
        w = mm(t.GetWidth())
        s = stats.setdefault(net, {'len': 0.0, 'w': w})
        s['len'] += seg
    rows, warns = [], []
    for net, s in sorted(stats.items()):
        decl = nets_decl.get(net, {})
        cls = decl.get('class', 'signal')
        if cls == 'power':
            continue
        z0 = microstrip_z0(s['w'], h)
        rows.append(f'{net}: {s["len"]:.1f}mm w={s["w"]:.2f} Z0≈{z0:.0f}Ω')
        if s['len'] > lcrit_mm and not decl.get('allow_long'):
            warns.append(f'{net} 长 {s["len"]:.0f}mm 超临界 {lcrit_mm:.0f}mm（边沿 {edge_ns}ns），需端接复核')
    ev = f'临界长度 {lcrit_mm:.0f}mm（Tr={edge_ns}ns）; ' + ' | '.join(rows[:6])
    cp.set('WARN' if warns else 'PASS', ev + (' || ' + '; '.join(warns) if warns else ''))


# ---------------------------------------------------------------------------
# E4 回流路径
# ---------------------------------------------------------------------------
def check_e4(cp, board):
    gnd_zones = [z for z in board.Zones() if 'GND' in (z.GetNetname() or '').upper()]
    if not gnd_zones:
        cp.set('FAIL', '无 GND 铺铜，回流路径无保障')
        return
    zone = gnd_zones[0]
    # 铺铜孤岛
    islands = 0
    try:
        if zone.HasFilledPolysForLayer(pcbnew.B_Cu):
            islands = zone.GetFilledPolysList(pcbnew.B_Cu).OutlineCount()
    except Exception:
        pass
    skip_pts = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            skip_pts.append((mm(p.GetPosition().x), mm(p.GetPosition().y)))
    for t in board.Tracks():
        if hasattr(t, 'GetDrillValue'):
            skip_pts.append((mm(t.GetPosition().x), mm(t.GetPosition().y)))

    def covered(px, py):
        try:
            return zone.HitTestFilledArea(pcbnew.B_Cu,
                                          pcbnew.VECTOR2I(pcbnew.FromMM(px), pcbnew.FromMM(py)),
                                          pcbnew.FromMM(0.05))
        except Exception:
            return False

    # 沿每条 F.Cu 走线采样，统计：(a)总覆盖率 (b)最长连续无铜段（缝隙宽度）
    total, cov = 0, 0
    max_gap = 0.0
    gap_detail = ''
    for t in board.Tracks():
        if hasattr(t, 'GetDrillValue') or t.GetLayer() != pcbnew.F_Cu:
            continue
        x1, y1 = mm(t.GetStart().x), mm(t.GetStart().y)
        x2, y2 = mm(t.GetEnd().x), mm(t.GetEnd().y)
        seg_len = math.hypot(x2 - x1, y2 - y1)
        step = 0.2
        n = max(2, int(seg_len / step))
        run = 0.0
        for i in range(n + 1):
            px = x1 + (x2 - x1) * i / n
            py = y1 + (y2 - y1) * i / n
            if any(math.hypot(px - sx, py - sy) < 0.6 for sx, sy in skip_pts):
                continue
            total += 1
            if covered(px, py):
                cov += 1
                run = 0.0
            else:
                run += step
                if run > max_gap:
                    max_gap = run
                    gap_detail = f'{t.GetNetname()}@({px:.1f},{py:.1f})'
    ratio = cov / total if total else 1.0
    ev = (f'GND 参考覆盖率 {ratio * 100:.1f}%（采样 {total} 点），'
          f'最长连续缝隙 {max_gap:.1f}mm（{gap_detail or "无"}），铺铜区域数 {islands}')
    if islands > 1:
        cp.set('FAIL', ev + ' — 铺铜被割裂成多岛')
    elif max_gap > 2.0:
        cp.set('FAIL', ev + ' — 缝隙 >2mm，高速信号回流路径被切断')
    elif max_gap > 1.0:
        cp.set('WARN', ev + ' — 缝隙 1~2mm，≤50MHz 可接受，>50MHz 建议优化')
    else:
        cp.set('PASS', ev + ' — 缝隙 ≤1mm，10~50MHz SPI 回流路径良好')


# ---------------------------------------------------------------------------
# E5 电源压降
# ---------------------------------------------------------------------------
def check_e5(cp, board, design):
    nets_decl = {n['name']: n for n in design.get('nets', [])}
    rows, fails = [], []
    stats = {}
    for t in board.Tracks():
        if hasattr(t, 'GetDrillValue'):
            continue
        s = stats.setdefault(t.GetNetname(), {'len_mm': 0.0, 'min_w': 1e9})
        s['len_mm'] += mm(t.GetLength())
        s['min_w'] = min(s['min_w'], mm(t.GetWidth()))
    for net, decl in nets_decl.items():
        cur = decl.get('max_current_a', 0)
        if cur <= 0:
            continue
        s = stats.get(net)
        if not s:
            continue
        length_m = s['len_mm'] / 1000.0
        width_m = s['min_w'] / 1000.0
        r = CU_RESISTIVITY * length_m / (width_m * CU_THICK_M)
        vdrop = cur * r
        rail_v = 5.0 if '5' in net else 3.3
        pct = vdrop / rail_v * 100
        rows.append(f'{net}: {s["len_mm"]:.1f}mm w={s["min_w"]:.2f} R={r * 1000:.1f}mΩ ΔV={vdrop * 1000:.1f}mV({pct:.2f}%)')
        if pct > 3:
            fails.append(f'{net} 压降 {pct:.1f}% > 3%')
    cp.set('FAIL' if fails else 'PASS',
           '; '.join(rows + fails) if rows else '无载流网络声明')


# ---------------------------------------------------------------------------
# E6 SPICE 引擎自检
# ---------------------------------------------------------------------------
def check_e6(cp):
    cli_dir = os.path.dirname(kicad_env.find_kicad_cli() or '')
    dll = os.path.join(cli_dir, 'ngspice.dll')
    if not os.path.exists(dll):
        cp.set('MANUAL', 'ngspice.dll 未找到，SPICE 仿真不可用')
        return
    try:
        os.environ['SPICE_LIB_DIR'] = os.path.join(os.path.dirname(cli_dir), 'lib', 'ngspice')
        os.add_dll_directory(cli_dir)
        ng = ctypes.WinDLL(dll)
        MSG = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
        buf = []

        @MSG
        def on_msg(msg, mid, ud):
            if msg:
                buf.append(msg.decode(errors='replace'))

        STAT = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
        @STAT
        def on_stat(s, i, u):
            pass
        EXITF = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_bool, ctypes.c_bool,
                                 ctypes.c_int, ctypes.c_void_p)
        @EXITF
        def on_exit(c, a, b, i, u):
            return 0
        DATA = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p)
        @DATA
        def on_data(d, i, u):
            return 0
        BG = ctypes.CFUNCTYPE(None, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
        @BG
        def on_bg(r, i, u):
            return 0

        ng.ngSpice_Init(on_msg, on_stat, on_exit, on_data, on_data, on_bg, None)
        cir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_spice_smoke.cir')
        with open(cir, 'w') as f:
            f.write('* skill smoke\nv1 1 0 5\nr1 1 0 1k\n.op\n.end\n')
        ng.ngSpice_Command(f'source {cir}'.encode())
        ng.ngSpice_Command(b'run')
        ng.ngSpice_Command(b'print v(1)')
        os.remove(cir)
        out = ''.join(buf)
        if '5.000000e+00' in out:
            cp.set('PASS', 'ngspice-46 引擎可用（.op 冒烟 v(1)=5.0V），支持后续模拟电路仿真')
        else:
            cp.set('WARN', 'ngspice 冒烟结果异常（spinit 缺失可忽略）')
    except Exception as e:
        cp.set('WARN', f'ngspice 调用失败（非致命）: {e}')


CHECKS = [
    ('E1-CONN', 'P0', '声明引脚对全部真实连通（含 passthrough 穿透）', check_e1),
    ('E1-PINMAP', 'P0', '引脚功能表与实际网络一致（防信号接反）', check_e1b),
    ('E2-DECAP', 'P0', '去耦电容就位（距离实测）', check_e2_decoupling),
    ('E2-TERM', 'P1', '串联端接阻值核对', check_e2_termination),
    ('E3-SI', 'P1', '阻抗/临界长度信号完整性估算', check_e3),
    ('E4-RETURN', 'P0', '高速信号回流路径（GND 参考覆盖 + 孤岛）', check_e4),
    ('E5-IRDROP', 'P1', '电源走线压降（1oz 铜实测几何）', check_e5),
    ('E6-SPICE', 'P2', 'ngspice 仿真引擎自检', check_e6),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--board', required=True)
    ap.add_argument('--design', required=True)
    ap.add_argument('--report', default=None)
    ap.add_argument('--md', default=None)
    args = ap.parse_args()

    with open(args.design, 'r', encoding='utf-8') as f:
        design = json.load(f)
    board = pcbnew.LoadBoard(args.board)

    cps = {cid: CP(cid, w, d) for cid, w, d, _fn in CHECKS}
    check_e1(cps['E1-CONN'], design)
    check_e1b(cps['E1-PINMAP'], design)
    check_e2_decoupling(cps['E2-DECAP'], design)
    check_e2_termination(cps['E2-TERM'], design)
    check_e3(cps['E3-SI'], board, design)
    check_e4(cps['E4-RETURN'], board)
    check_e5(cps['E5-IRDROP'], board, design)
    check_e6(cps['E6-SPICE'])

    results = [cp.to_dict() for cp in cps.values()]
    p0_fail = [r for r in results if r['weight'] == 'P0' and r['result'] == 'FAIL']
    p1_fail = [r for r in results if r['weight'] == 'P1' and r['result'] == 'FAIL']
    verdict = 'REJECTED' if p0_fail else ('CONDITIONAL' if p1_fail else 'APPROVED')
    report = {'tool': 'pcba-skill v5.1 elec_review', 'board': os.path.abspath(args.board),
              'checkpoints': results,
              'summary': {'verdict': verdict, 'p0_fail': len(p0_fail), 'p1_fail': len(p1_fail)}}
    if args.report:
        with open(args.report, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    lines = [f'# 电气审查报告 — {os.path.basename(args.board)}', f'- 结论: **{verdict}**', '',
             '| 检查点 | 权重 | 结果 | 证据 |', '|---|---|---|---|']
    icon = {'PASS': '✅', 'FAIL': '❌', 'WARN': '⚠️', 'NA': '⊘', 'MANUAL': '👁'}
    for r in results:
        lines.append(f"| {r['id']} | {r['weight']} | {icon[r['result']]} {r['result']} | {r['evidence']} |")
    md = '\n'.join(lines)
    if args.md:
        with open(args.md, 'w', encoding='utf-8') as f:
            f.write(md)
    print(md)
    return 1 if verdict == 'REJECTED' else 0


if __name__ == '__main__':
    sys.exit(main())
