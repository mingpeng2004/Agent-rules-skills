#!/usr/bin/env python3
"""
PCBA Skill v5.0 — 原理图生成器（build_schematic.py）

用 KiCad 自带 Python 运行：
  python.exe build_schematic.py --design design.json --outdir dist_v7 [--name PROJECT]

从 design.json 生成最小但合法的 .kicad_sch（KiCad 9/10 格式）：
  - lib_symbols 从 KiCad 安装库实时提取并内嵌（不依赖手写符号图形）
  - 元件按网格摆放，引脚位置从符号定义中真实解析
  - 每个引脚放一个网络标签（label 落在引脚端点上 = 真实电气连接）
  - Footprint 属性与 design.json 一致 → kicad-cli 可做 schematic-parity 校验

design.json 中元件可显式指定 "symbol": "Device:R"；缺省时按封装名推断：
  Capacitor_* → Device:C    Resistor_* → Device:R
  Connector_PinHeader_*_1xNN → Connector_Generic:Conn_01xNN
  MountingHole* → Mechanical:MountingHole
"""
import argparse
import json
import os
import re
import sys
import uuid as uuidlib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import kicad_env  # noqa: E402

SCH_VERSION = '20250114'  # KiCad 9/10 兼容；ERC 实测校准


def gen_uuid():
    return str(uuidlib.uuid4())


def extract_symbol_block(lib_path, symbol_name):
    """从 .kicad_sym 提取 (symbol "NAME" ...) 完整块（平衡括号扫描）"""
    with open(lib_path, 'r', encoding='utf-8') as f:
        text = f.read()
    m = re.search(r'\(symbol\s+"' + re.escape(symbol_name) + r'"', text)
    if not m:
        return None
    depth = 0
    i = m.start()
    in_str = False
    while i < len(text):
        ch = text[i]
        if ch == '"':
            in_str = not in_str
        elif not in_str:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    return text[m.start():i + 1]
        i += 1
    return None


def parse_pins(symbol_block):
    """从符号定义块解析 引脚号 → (x, y)。引脚定义在 *_1_1 子符号中"""
    pins = {}
    for m in re.finditer(r'\(pin\s', symbol_block):
        start = m.start()
        depth = 0
        i = start
        in_str = False
        while i < len(symbol_block):
            ch = symbol_block[i]
            if ch == '"':
                in_str = not in_str
            elif not in_str:
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                    if depth == 0:
                        break
            i += 1
        block = symbol_block[start:i + 1]
        at = re.search(r'\(at\s+(-?[\d.]+)\s+(-?[\d.]+)', block)
        num = re.search(r'\(number\s+"([^"]+)"', block)
        if at and num:
            pins[num.group(1)] = (float(at.group(1)), float(at.group(2)))
    return pins


def infer_symbol(footprint):
    fp = footprint.lower()
    if 'capacitor' in fp or fp.split(':')[-1].startswith('c_'):
        return 'Device:C'
    if 'resistor' in fp or fp.split(':')[-1].startswith('r_'):
        return 'Device:R'
    m = re.search(r'pinheader_1x(\d+)', fp)
    if m:
        return f'Connector_Generic:Conn_01x{int(m.group(1)):02d}'
    if 'mountinghole' in fp:
        return 'Mechanical:MountingHole'
    return None


def build_lib_symbols(needed, sym_root):
    """needed: {lib_id: (lib_file, symbol_name)} → (lib_symbols 段文本, 引脚表)"""
    blocks = []
    pin_tables = {}
    for lib_id, (lib_file, sym_name) in sorted(needed.items()):
        path = os.path.join(sym_root, lib_file + '.kicad_sym')
        block = extract_symbol_block(path, sym_name)
        if block is None:
            raise FileNotFoundError(f'符号 {sym_name} 不在 {path}')
        pin_tables[lib_id] = parse_pins(block)
        # 重命名为 lib:symbol 形式（子符号名保持不变）
        block = block.replace(f'(symbol "{sym_name}"', f'(symbol "{lib_id}"', 1)
        blocks.append(block)
    indent = '\t'
    body = ('\n' + indent).join(b.replace('\n', '\n' + indent) for b in blocks)
    return f'(lib_symbols\n{indent}{body}\n)', pin_tables


def fmt(x):
    v = f'{x:.4f}'.rstrip('0').rstrip('.')
    return v if v else '0'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--design', required=True)
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--name', default=None)
    args = ap.parse_args()

    with open(args.design, 'r', encoding='utf-8') as f:
        d = json.load(f)
    name = args.name or d.get('meta', {}).get('project', 'pcb_project')
    os.makedirs(args.outdir, exist_ok=True)

    # 元件 → 符号映射
    comp_symbols = {}
    needed = {}
    for c in d['components']:
        sym = c.get('symbol') or infer_symbol(c['footprint'])
        if sym is None:
            print(f'  [FAIL] {c["ref"]}: 无法从封装 {c["footprint"]} 推断符号，请在 design.json 显式指定 "symbol"')
            return 1
        comp_symbols[c['ref']] = sym
        lib_name, _, sym_name = sym.partition(':')
        needed[sym] = (lib_name, sym_name)

    sym_root = kicad_env.find_symbol_lib()
    lib_symbols_text, pin_tables = build_lib_symbols(needed, sym_root)

    # 网络表: (REF.PIN) → net
    pin_net = {}
    for n in d.get('nets', []):
        for pref in n.get('pads', []):
            pin_net[pref] = n['name']

    # 布局：网格摆放
    cols = max(1, int(len(d['components']) ** 0.5 + 0.999))
    pitch_x, pitch_y = 40.0, 30.0
    sch_uuid = gen_uuid()

    sym_items = []
    label_items = []
    for idx, c in enumerate(d['components']):
        ref = c['ref']
        lib_id = comp_symbols[ref]
        gx = (idx % cols) * pitch_x + 50.0
        gy = (idx // cols) * pitch_y + 40.0
        pins = pin_tables[lib_id]
        pin_uuids = []
        for pnum, (px, py) in sorted(pins.items(), key=lambda kv: kv[0]):
            ax, ay = gx + px, gy + py
            net = pin_net.get(f'{ref}.{pnum}')
            if net:
                label_items.append(
                    f'(label "{net}" (at {fmt(ax)} {fmt(ay)} 0) '
                    f'(effects (font (size 1.27 1.27)) (justify left bottom)) '
                    f'(uuid {gen_uuid()}))')
            pin_uuids.append((pnum, gen_uuid()))
        props = [
            ('Reference', ref, gy - 8, False),
            ('Value', str(c['value']), gy + 8, False),
            ('Footprint', c['footprint'], gy, True),
            ('Datasheet', '~', gy, True),
        ]
        prop_text = '\n\t\t'.join(
            f'(property "{k}" "{v}" (at {fmt(gx)} {fmt(y)} 0) '
            f'(effects (font (size 1.27 1.27)){" hide" if hide else ""}))'
            for k, v, y, hide in props)
        pin_text = '\n\t\t'.join(f'(pin "{p}" (uuid {u}))' for p, u in pin_uuids)
        sym_items.append(
            f'(symbol (lib_id "{lib_id}") (at {fmt(gx)} {fmt(gy)} 0) (unit 1) '
            f'(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) '
            f'(fields_autoplaced yes) (uuid {gen_uuid()})\n'
            f'\t\t{prop_text}\n'
            f'\t\t{pin_text}\n'
            f'\t\t(instances (project "{name}" (path "/{sch_uuid}" (reference "{ref}") (unit 1)))))')

    body = '\n\t'.join(sym_items + label_items)
    sch = (
        f'(kicad_sch (version {SCH_VERSION}) (generator "pcba_skill_v5") (generator_version "1.0")\n'
        f'\t(uuid {sch_uuid})\n'
        f'\t(paper "A4")\n'
        f'\t{lib_symbols_text}\n'
        f'\t{body}\n'
        f'\t(sheet_instances (path "/" (page "1")))\n'
        f')\n'
    )
    out = os.path.join(args.outdir, f'{name}.kicad_sch')
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(sch)
    print(f'[DONE] {out}  ({len(d["components"])} 符号, {len(label_items)} 网络标签)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
