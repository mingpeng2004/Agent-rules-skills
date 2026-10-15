#!/usr/bin/env python3
"""
PCBA Skill v5.0 — 制造文件导出（export_mfg.py）

任意 Python 可运行（仅封装 kicad-cli 子进程）：
  python export_mfg.py --board dist_v7/x.kicad_pcb --outdir dist_v7/mfg [--zip] [--order-readme]

产出（JLC 打样标准包）：
  Gerber×N（F/B Cu、Mask、Silkscreen、Paste、Edge.Cuts + job file）
  Excellon 钻孔（.drl）
  贴片坐标（.csv, JLC 列格式）
  3D STEP（可选 --step）
  下单参数 README（可选 --order-readme）
退出码：0 = 全部导出成功
"""
import argparse
import json
import os
import subprocess
import sys
import zipfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import kicad_env  # noqa: E402

GERBER_LAYERS = 'F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts'


def run(args_list, timeout=600):
    p = subprocess.run(args_list, capture_output=True, text=True, timeout=timeout,
                       encoding='utf-8', errors='replace')
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--board', required=True)
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--zip', action='store_true', help='打包 Gerber+钻孔为 *_Gerber.zip')
    ap.add_argument('--step', action='store_true', help='额外导出 STEP 3D 模型')
    ap.add_argument('--order-readme', action='store_true', help='生成下单参数 README')
    ap.add_argument('--order-params', default=None,
                    help='下单参数 JSON 字符串, 如 {"layers":2,"thickness":1.6,"surface":"HASL","copper_oz":1}')
    ap.add_argument('--inner-cu', default='',
                    help='内电层（多层板），如 "In1.Cu,In2.Cu"；2 层板留空')
    args = ap.parse_args()

    cli = kicad_env.find_kicad_cli()
    if not cli:
        print('[FAIL] 未找到 kicad-cli')
        return 1
    os.makedirs(args.outdir, exist_ok=True)
    board_name = os.path.splitext(os.path.basename(args.board))[0]
    fails = []

    gerber_layers = GERBER_LAYERS + ((',' + args.inner_cu) if args.inner_cu else '')
    print('[1/4] Gerber...')
    code, log = run([cli, 'pcb', 'export', 'gerbers',
                     '--layers', gerber_layers,
                     '--no-protel-ext',
                     '--check-zones',
                     '--output', args.outdir + os.sep,
                     args.board])
    if code != 0:
        fails.append(f'gerbers: {log[:300]}')
    else:
        print('  [OK] Gerber 导出完成')

    print('[2/4] 钻孔...')
    code, log = run([cli, 'pcb', 'export', 'drill',
                     '--format', 'excellon',
                     '--drill-origin', 'absolute',
                     '--excellon-units', 'mm',
                     '--output', args.outdir + os.sep,
                     args.board])
    if code != 0:
        fails.append(f'drill: {log[:300]}')
    else:
        print('  [OK] Excellon 钻孔导出完成')

    print('[3/4] 贴片坐标...')
    pos_path = os.path.join(args.outdir, f'{board_name}-pos.csv')
    code, log = run([cli, 'pcb', 'export', 'pos',
                     '--format', 'csv', '--units', 'mm', '--side', 'both',
                     '--smd-only',
                     '--output', pos_path,
                     args.board])
    if code != 0:
        fails.append(f'pos: {log[:300]}')
    else:
        print('  [OK] 坐标文件导出完成')

    if args.step:
        print('[4/4] STEP...')
        code, log = run([cli, 'pcb', 'export', 'step',
                         '--output', os.path.join(args.outdir, f'{board_name}.step'),
                         args.board])
        if code != 0:
            print(f'  [WARN] STEP 导出失败（非致命）: {log[:200]}')
        else:
            print('  [OK] STEP 导出完成')

    zip_path = None
    if args.zip:
        zip_path = os.path.join(args.outdir, f'{board_name}_Gerber.zip')
        exts = ('.gtl', '.gbl', '.gto', '.gbo', '.gts', '.gbs', '.gtp', '.gbp',
                '.gm1', '.gbr', '.drl', '.gbrjob')
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for fn in sorted(os.listdir(args.outdir)):
                if fn.lower().endswith(exts) and not fn.endswith('.zip'):
                    zf.write(os.path.join(args.outdir, fn), fn)
        print(f'  [OK] Gerber 打包: {zip_path}')

    if args.order_readme:
        params = {'layers': 2, 'thickness_mm': 1.6, 'surface': 'HASL(with lead)',
                  'copper_oz': 1, 'soldermask': 'Green', 'silkscreen': 'White'}
        if args.order_params:
            params.update(json.loads(args.order_params))
        readme = os.path.join(args.outdir, 'ORDER_README.md')
        with open(readme, 'w', encoding='utf-8') as f:
            f.write(f'# 下单参数 — {board_name}\n\n')
            f.write('| 参数 | 值 |\n|---|---|\n')
            for k, v in params.items():
                f.write(f'| {k} | {v} |\n')
            f.write(f'\nGerber 包: `{os.path.basename(zip_path) if zip_path else "见本目录"}`\n')
            f.write('贴片文件: BOM + pos.csv（SMT 订单时上传）\n')
        print(f'  [OK] 下单 README: {readme}')

    if fails:
        print('[FAIL] ' + '; '.join(fails))
        return 1
    print('[DONE] 制造文件导出完成')
    return 0


if __name__ == '__main__':
    sys.exit(main())
