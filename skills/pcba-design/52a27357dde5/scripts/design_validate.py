#!/usr/bin/env python3
"""
PCBA Skill v5.0 — 输入门禁（design_validate.py）

用 KiCad 自带 Python 运行：
  python.exe design_validate.py --design design.json [--report out.json]

检查项（I 层，全部真实验证）：
  I-01 design.json 结构完整（meta/board/components/nets 必填字段）
  I-02 单位与数值域合法（mm，坐标 |v| ≤ 500）
  I-03 每个 footprint 在 KiCad 库中真实存在（FootprintLoad 试加载）
  I-04 封装焊盘数 ≥ 网络中引用的最大焊盘编号
  I-05 位号唯一、值非空
  I-06 网络名合法（无空白字符/保留字）
退出码：0 = 全 PASS，1 = 有 FAIL
"""
import argparse
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import kicad_env  # noqa: E402

import pcbnew  # noqa: E402

REQUIRED_TOP = ['meta', 'board', 'components', 'nets']
VALID_NET_NAME = re.compile(r'^[A-Za-z0-9_+\-./]+$')


def fail(results, cid, evidence):
    results.append({'id': cid, 'result': 'FAIL', 'evidence': evidence})


def passed(results, cid, evidence):
    results.append({'id': cid, 'result': 'PASS', 'evidence': evidence})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--design', required=True)
    ap.add_argument('--report', default=None)
    args = ap.parse_args()

    results = []

    # I-01 结构
    try:
        with open(args.design, 'r', encoding='utf-8') as f:
            d = json.load(f)
    except Exception as e:
        fail(results, 'I-01', f'design.json 解析失败: {e}')
        return emit(results, args.report)
    missing = [k for k in REQUIRED_TOP if k not in d]
    comp_bad = []
    for i, c in enumerate(d.get('components', [])):
        for k in ('ref', 'footprint', 'value', 'x', 'y'):
            if k not in c:
                comp_bad.append(f'components[{i}] 缺 {k}')
    if missing or comp_bad:
        fail(results, 'I-01', f'缺顶层字段: {missing}; 组件字段问题: {comp_bad[:5]}')
    else:
        passed(results, 'I-01', f'结构完整: {REQUIRED_TOP} + {len(d["components"])} 元件')

    if missing:
        return emit(results, args.report)

    # I-02 数值域
    bad = []
    for c in d['components']:
        for k in ('x', 'y'):
            v = c.get(k)
            if not isinstance(v, (int, float)) or abs(v) > 500:
                bad.append(f'{c.get("ref", "?")}.{k}={v}')
    bw = d['board'].get('width_mm', 0)
    bh = d['board'].get('height_mm', 0)
    if not (1 <= bw <= 500 and 1 <= bh <= 500):
        bad.append(f'board {bw}x{bh} 超出合理范围')
    if bad:
        fail(results, 'I-02', '; '.join(bad[:8]))
    else:
        passed(results, 'I-02', f'全部坐标/尺寸在合法域内 (板 {bw}x{bh}mm)')

    # I-03/I-04 封装真实存在 + 焊盘数
    lib = kicad_env.find_footprint_lib()
    fp_errors = []
    pad_counts = {}
    for c in d['components']:
        fpid = c['footprint']
        lib_dir, _, fp_name = fpid.partition(':')
        fp_path = os.path.join(lib, lib_dir + '.pretty')
        try:
            fp = pcbnew.FootprintLoad(fp_path, fp_name)
        except Exception as e:
            fp = None
            fp_errors.append(f'{c["ref"]}: 加载异常 {e}')
        if fp is None:
            fp_errors.append(f'{c["ref"]}: {fpid} 不存在')
        else:
            pad_counts[c['ref']] = len(list(fp.Pads()))
    if fp_errors:
        fail(results, 'I-03', '; '.join(fp_errors[:8]))
    else:
        passed(results, 'I-03', f'{len(pad_counts)} 个封装全部试加载成功')

    # I-04 引用的焊盘编号 ≤ 封装焊盘数
    ref_pad_max = {}
    for r in d.get('routes', []):
        for p in r.get('points', []):
            if isinstance(p, dict) and 'pad' in p:
                ref, _, num = p['pad'].partition('.')
                try:
                    n = int(num)
                except ValueError:
                    continue
                ref_pad_max[ref] = max(ref_pad_max.get(ref, 0), n)
    bad_pads = [f'{ref}: 引用 pad {n} > 封装焊盘数 {pad_counts.get(ref, 0)}'
                for ref, n in ref_pad_max.items() if n > pad_counts.get(ref, 0)]
    if bad_pads:
        fail(results, 'I-04', '; '.join(bad_pads))
    else:
        passed(results, 'I-04', f'{len(ref_pad_max)} 个元件的焊盘引用全部在封装范围内')

    # I-05 位号唯一
    refs = [c['ref'] for c in d['components']]
    dup = [r for r in set(refs) if refs.count(r) > 1]
    empty_val = [c['ref'] for c in d['components'] if not str(c.get('value', '')).strip()]
    if dup or empty_val:
        fail(results, 'I-05', f'重复位号: {dup}; 空 value: {empty_val}')
    else:
        passed(results, 'I-05', f'{len(refs)} 个位号唯一且 value 非空')

    # I-06 网络名
    bad_nets = [n['name'] for n in d.get('nets', [])
                if not VALID_NET_NAME.match(n.get('name', '')) or n.get('name', '') in ('', '0')]
    route_nets = {r['net'] for r in d.get('routes', [])}
    declared = {n['name'] for n in d.get('nets', [])}
    undeclared = sorted(route_nets - declared)
    if bad_nets or undeclared:
        fail(results, 'I-06', f'非法网络名: {bad_nets}; 未声明的布线网络: {undeclared}')
    else:
        passed(results, 'I-06', f'{len(declared)} 个网络名合法，布线网络全部已声明')

    return emit(results, args.report)


def emit(results, report_path):
    n_fail = len([r for r in results if r['result'] == 'FAIL'])
    out = {'gate': 'I (input)', 'fails': n_fail, 'checks': results,
           'verdict': 'PASS' if n_fail == 0 else 'FAIL'}
    text = json.dumps(out, indent=2, ensure_ascii=False)
    if report_path:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(text)
    print(text)
    return 1 if n_fail else 0


if __name__ == '__main__':
    sys.exit(main())
