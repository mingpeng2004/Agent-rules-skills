#!/usr/bin/env python3
"""
PCBA Skill v5.0 — 视觉复检渲染（visual_review.py）

任意 Python 可运行：
  python visual_review.py --board dist_v7/x.kicad_pcb --outdir dist_v7/review

产出 top/bottom/left/right/perspective 多张 PNG，供 AI 用视觉能力复检
（丝印可读性、元件方向、明显错位——机器 DRC 查不出的"看着不对"）。
退出码：0 = 至少 top+bottom 成功
"""
import argparse
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import kicad_env  # noqa: E402

VIEWS = [
    ('top', []),
    ('bottom', []),
    ('front', []),
    ('iso', ['--rotate', '-45,0,45', '--perspective']),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--board', required=True)
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--width', type=int, default=1600)
    ap.add_argument('--height', type=int, default=1200)
    args = ap.parse_args()

    cli = kicad_env.find_kicad_cli()
    if not cli:
        print('[FAIL] 未找到 kicad-cli')
        return 1
    os.makedirs(args.outdir, exist_ok=True)
    name = os.path.splitext(os.path.basename(args.board))[0]

    ok = []
    for view, extra in VIEWS:
        out = os.path.join(args.outdir, f'{name}_{view}.png')
        cmd = [cli, 'pcb', 'render',
               '--width', str(args.width), '--height', str(args.height),
               '--quality', 'high',
               '--output', out]
        if view == 'iso':
            cmd += extra
        else:
            cmd += ['--side', view]
        cmd.append(args.board)
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                           encoding='utf-8', errors='replace')
        if p.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 1000:
            ok.append(out)
            print(f'  [OK] {out}')
        else:
            print(f'  [WARN] {view} 渲染失败: {(p.stdout or p.stderr)[:150]}')
    if len(ok) >= 2:
        print(f'[DONE] {len(ok)} 张渲染图，请 AI 逐张视觉复检')
        return 0
    print('[FAIL] 渲染成功数 <2')
    return 1


if __name__ == '__main__':
    sys.exit(main())
