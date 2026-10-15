#!/usr/bin/env python3
"""
PCBA Skill v5.0 — 输出终审门禁（verify_output.py）

用 KiCad 自带 Python 运行：
  python.exe verify_output.py --board dist_v7/x.kicad_pcb --mfg dist_v7/mfg --design design.json

原则：不信任导出日志，直接回读文件实测。
  O-01 Gerber 层齐全（Cu/Mask/Silk/Paste/Edge.Cuts）
  O-02 Excellon 钻孔：格式头 M48、工具数、孔数、最小刀径
  O-03 板框尺寸：解析 Edge_Cuts Gerber 坐标实测 == design.json 设计值
  O-04 Gerber 文件完整性：%FS/%MO 头 + M02* 结尾
  O-05 BOM ↔ 坐标 ↔ PCB 三方一致（ref 集合）
  O-06 Gerber.zip 完整性（全部 Gerber+钻孔入内）
退出码：0 = 全 PASS/NA，1 = 有 FAIL
"""
import argparse
import glob
import json
import os
import re
import sys
import zipfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import pcbnew  # noqa: E402

REQUIRED_GERBER = ['F_Cu', 'B_Cu', 'F_Mask', 'B_Mask', 'F_Silkscreen', 'Edge_Cuts']
OPTIONAL_GERBER = ['B_Silkscreen', 'F_Paste', 'B_Paste']
GERBER_EXTS = ('.gbr', '.gtl', '.gbl', '.gts', '.gbs', '.gto', '.gbo', '.gtp', '.gbp', '.gm1')


def parse_excellon(path):
    """返回 (工具数, 孔总数, 最小刀径mm, 错误)"""
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
    except Exception as e:
        return None, None, None, str(e)
    if 'M48' not in text[:200]:
        return None, None, None, '缺少 M48 头'
    tools = re.findall(r'^T(\d+)C([\d.]+)', text, re.M)
    hole_lines = re.findall(r'^X([\d.\-]+)Y([\d.\-]+)\s*$', text, re.M)
    drills = [float(t[1]) for t in tools]
    return len(tools), len(hole_lines), (min(drills) if drills else None), None


def parse_gerber_bbox(path):
    """解析 Gerber 坐标，返回 (w, h, 单位) 或 None"""
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    mo = re.search(r'%MO(IN|MM)\*%', text)
    unit = mo.group(1) if mo else None
    fs = re.search(r'%FS[LT]?[AI]?X(\d)(\d)Y(\d)(\d)\*%', text)
    if not fs:
        return None
    xi, xd = int(fs.group(1)), int(fs.group(2))
    xs, ys = [], []
    for m in re.finditer(r'X(-?\d+)Y(-?\d+)', text):
        xs.append(int(m.group(1)) / (10 ** xd))
        ys.append(int(m.group(2)) / (10 ** xd))
    if not xs:
        return None
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    if unit == 'IN':
        w, h = w * 25.4, h * 25.4
    return w, h, unit


def gerber_sane(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        head = f.read(500)
        f.seek(max(0, os.path.getsize(path) - 100))
        tail = f.read()
    return ('%FS' in head) and ('%MO' in head) and ('M02*' in tail)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--board', required=True)
    ap.add_argument('--mfg', required=True)
    ap.add_argument('--design', default=None)
    ap.add_argument('--report', default=None)
    args = ap.parse_args()

    results = []

    def rec(cid, result, evidence):
        results.append({'id': cid, 'result': result, 'evidence': evidence})
        print(f'  [{result}] {cid}: {evidence}')

    mfg = args.mfg
    files = os.listdir(mfg) if os.path.isdir(mfg) else []
    low = {fn.lower(): fn for fn in files}

    # 提前加载 PCB：按实际铜层数动态确定必需 Gerber 层（4 层板需 In1/In2）
    board = pcbnew.LoadBoard(args.board)
    required = list(REQUIRED_GERBER)
    try:
        n_cu = board.GetCopperLayerCount()
        if n_cu >= 4:
            for i in range(1, n_cu - 1):
                required.append(f'In{i}_Cu')
    except Exception:
        pass

    # O-01 层齐全（按层名匹配，兼容 .gbr 与 Protel 扩展名）
    def is_gerber(fn):
        return fn.lower().endswith(GERBER_EXTS) and 'job' not in fn.lower()

    def find_layer(layer_name):
        for fn in files:
            if is_gerber(fn) and layer_name.lower() in fn.lower():
                return fn
        return None

    missing, present = [], []
    for layer in required + OPTIONAL_GERBER:
        if find_layer(layer):
            present.append(layer)
        elif layer in required:
            missing.append(layer)
    rec('O-01', 'FAIL' if missing else 'PASS',
        f'Gerber 层: 存在 {len(present)} 层' + (f', 缺失必需层 {missing}' if missing else ''))

    # O-02 钻孔
    drl = [fn for fn in files if fn.lower().endswith('.drl')]
    if not drl:
        rec('O-02', 'FAIL', '无 .drl 钻孔文件')
    else:
        tools, holes, mind, err = parse_excellon(os.path.join(mfg, drl[0]))
        if err:
            rec('O-02', 'FAIL', f'{drl[0]}: {err}')
        else:
            rec('O-02', 'PASS', f'{drl[0]}: {tools} 种刀具, {holes} 孔, 最小刀径 {mind}mm')

    # O-03 板框尺寸实测
    edge = None
    for e in ('.gm1', '.gbr'):
        cand = [fn for fn in files if 'edge' in fn.lower() and fn.lower().endswith(e)]
        if cand:
            edge = cand[0]
            break
    exp = {}
    if args.design and os.path.exists(args.design):
        with open(args.design, 'r', encoding='utf-8') as f:
            exp = json.load(f).get('board', {})
    if not edge:
        rec('O-03', 'FAIL', '无 Edge_Cuts Gerber')
    else:
        bbox = parse_gerber_bbox(os.path.join(mfg, edge))
        if not bbox:
            rec('O-03', 'FAIL', f'{edge}: 坐标解析失败')
        else:
            w, h, unit = bbox
            ew, eh = exp.get('width_mm'), exp.get('height_mm')
            if ew and eh:
                ok = abs(w - ew) <= 0.15 and abs(h - eh) <= 0.15
                rec('O-03', 'PASS' if ok else 'FAIL',
                    f'{edge}: 实测 {w:.2f}x{h:.2f}mm vs 设计 {ew}x{eh}mm (unit={unit})')
            else:
                rec('O-03', 'PASS', f'{edge}: 实测 {w:.2f}x{h:.2f}mm (unit={unit})')

    # O-04 文件完整性
    gerbers = [fn for fn in files if fn.lower().endswith(GERBER_EXTS) and 'job' not in fn.lower()]
    bad = [fn for fn in gerbers if not gerber_sane(os.path.join(mfg, fn))]
    rec('O-04', 'FAIL' if bad else 'PASS',
        f'{len(gerbers)} 个 Gerber 头尾完整' if not bad else f'头尾不完整: {bad}')

    # O-05 三方一致（BOM / pos / PCB）
    board = pcbnew.LoadBoard(args.board)
    board_refs = {fp.GetReference() for fp in board.GetFootprints()
                  if not fp.GetReference().startswith('#')}
    bom_files = glob.glob(os.path.join(os.path.dirname(mfg.rstrip('/\\')), '*_BOM.csv')) + \
        glob.glob(os.path.join(mfg, '*BOM*.csv'))
    bom_refs = set()
    if bom_files:
        import csv
        with open(bom_files[0], 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                bom_refs.update(row.get('Designator', '').split())
    pos_files = glob.glob(os.path.join(mfg, '*-pos.csv')) + glob.glob(os.path.join(mfg, '*pos*.csv'))
    pos_refs = set()
    if pos_files:
        import csv
        with open(pos_files[0], 'r', encoding='utf-8-sig') as f:
            head = f.readline()
            f.seek(0)
            if 'Ref' in head:
                for row in csv.DictReader(f):
                    pos_refs.add(row.get('Ref', ''))
            else:
                reader = csv.reader(f)
                for r in reader:
                    if r and not r[0].startswith(('#', 'Ref')):
                        pos_refs.add(r[0])
    pos_refs.discard('')
    smd_refs = {fp.GetReference() for fp in board.GetFootprints()
                for p in fp.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD}
    problems = []
    if bom_files and bom_refs != board_refs:
        problems.append(f'BOM↔PCB 差异: BOM-only={sorted(bom_refs - board_refs)} PCB-only={sorted(board_refs - bom_refs)}')
    if pos_files and not smd_refs.issubset(pos_refs):
        problems.append(f'SMD 元件缺坐标: {sorted(smd_refs - pos_refs)}')
    if not bom_files:
        problems.append('未找到 BOM.csv')
    if not pos_files:
        problems.append('未找到 pos 坐标文件')
    rec('O-05', 'FAIL' if problems else 'PASS',
        '; '.join(problems) if problems else
        f'BOM({len(bom_refs)}) ↔ PCB({len(board_refs)}) ↔ SMD坐标({len(pos_refs)}) 三方一致')

    # O-06 zip 完整性
    zips = glob.glob(os.path.join(mfg, '*Gerber*.zip'))
    if not zips:
        rec('O-06', 'WARN', '未生成 Gerber.zip（若直接传散文件可忽略）')
    else:
        with zipfile.ZipFile(zips[0]) as zf:
            names = set(zf.namelist())
        need = {fn for fn in gerbers} | {fn for fn in files if fn.lower().endswith('.drl')}
        miss = need - names
        rec('O-06', 'FAIL' if miss else 'PASS',
            f'{os.path.basename(zips[0])}: {len(names)} 文件' + (f', 缺 {sorted(miss)}' if miss else '，齐全'))

    n_fail = len([r for r in results if r['result'] == 'FAIL'])
    verdict = 'PASS' if n_fail == 0 else 'FAIL'
    out = {'gate': 'O (output)', 'verdict': verdict, 'fails': n_fail, 'checks': results}
    if args.report:
        with open(args.report, 'w', encoding='utf-8') as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
    print(f'\n[输出门禁] {verdict} (fail={n_fail})')
    return 1 if n_fail else 0


if __name__ == '__main__':
    sys.exit(main())
