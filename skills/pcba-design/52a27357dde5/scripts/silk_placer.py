#!/usr/bin/env python3
"""
PCBA Skill v5.3 — 丝印安全放置工具 (silk_placer.py)

功能:
  1. 读取 PCB，采集所有焊盘 BBox（含 0.2mm 安全边距）
  2. 对指定文本，计算不同字号的预计算 BBox 尺寸
  3. 在网格上搜索无干涉位置
  4. 若无 0.8mm 安全位，自动降级尝试 0.6mm（JLC 制造极限）
  5. 放置丝印并写回 PCB + design.json

用法:
  KiCad-python silk_placer.py --board board.kicad_pcb --design design.json [--apply]
"""

import pcbnew
import json
import math
import os
import sys
import argparse
import collections

# ===== 预计算文本 BBox 表 =====
# 在不同字号下测量（KiCad 10.0.5, 线宽 0.12mm）
# 格式: (width_mm, height_mm)
TEXT_SIZES = {
    # Common board names
    'CS5552-WCD-V4': {0.8: (10.8, 1.4), 0.6: (8.2, 1.1)},
    'WCD-V4':        {0.8: ( 5.2, 1.4), 0.6: (4.0, 1.1)},
    'CS5552':        {0.8: ( 5.8, 1.4), 0.6: (4.4, 1.1)},
    # Short labels
    'V4.1':          {0.8: ( 3.2, 1.4), 0.6: (2.4, 1.1)},
    'V1.0':          {0.8: ( 3.2, 1.4), 0.6: (2.4, 1.1)},
    '2026':          {0.8: ( 3.6, 1.4), 0.6: (2.8, 1.1)},
    # Pin-1 markers
    '1':             {0.8: ( 0.8, 1.4), 0.6: (0.6, 1.1)},
}
# Default for unknown text: estimate as 0.6 * len(text) x 1.4 (0.8mm) or 0.45 * len(text) x 1.1 (0.6mm)

def estimate_bbox(text, size_mm):
    """Estimate bbox for text not in TEXT_SIZES table"""
    if text in TEXT_SIZES and size_mm in TEXT_SIZES[text]:
        return TEXT_SIZES[text][size_mm]
    # Fallback estimation
    if size_mm <= 0.6:
        return (0.45 * len(text) + 0.3, 1.1)
    return (0.6 * len(text) + 0.5, 1.4)

# ===== 采集焊盘 BBox =====
def collect_pad_bboxes(board, clearance_mm=0.2):
    """返回所有焊盘的 (x0, y0, x1, y1) 带安全边距"""
    bboxes = []
    mm = lambda v: v / 1e6
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            x0 = mm(bb.GetLeft())   - clearance_mm
            x1 = mm(bb.GetRight())  + clearance_mm
            y0 = mm(bb.GetTop())    # larger y
            y1 = mm(bb.GetBottom()) # smaller y
            if y0 < y1:
                y0, y1 = y1, y0
            bboxes.append((x0, y1, x1, y0))  # x0,x1,y_lo,y_hi
    return bboxes

# ===== 碰撞检测 =====
def has_overlap(bx0, bx1, by0, by1, pad_bboxes, margin=0.15):
    """检查文本 BBox 是否与任何焊盘 BBox 重叠"""
    bx0 -= margin
    bx1 += margin
    by0 -= margin
    by1 += margin
    for px0, py0, px1, py1 in pad_bboxes:
        if bx0 < px1 and bx1 > px0 and by0 < py1 and by1 > py0:
            return True
    return False

# ===== 安全位置搜索 =====
def find_safe_position(text, size_mm, pad_bboxes, board_width=20.0, board_height=22.0,
                       grid_step=0.5, margin=0.3, copper_edge=0.3):
    """在板上搜索丝印安全位置。返回 [(x, y), ...] 按位置质量排序。

    关键策略: 板边绝缘带 (copper_edge_clearance zone) 是铜禁区但丝印可去,
    放在 y > board_height/2 - copper_edge 或 y < -board_height/2 + copper_edge 的区域。
    """
    bw, bh = estimate_bbox(text, size_mm)
    half_w, half_h = board_width/2, board_height/2
    candidates = []

    # 优先搜索板边绝缘带: y 在 [half_h - copper_edge, half_h] 或 [-half_h, -half_h + copper_edge]
    edge_y_top = half_h - copper_edge / 2  # 板边内 0.15mm
    edge_y_bot = -half_h + copper_edge / 2
    edge_ys = [edge_y_top, edge_y_bot]

    for edge_y in edge_ys:
        for x in [round(i * grid_step, 1) for i in range(
                int((-half_w + bw/2 + margin) / grid_step),
                int((half_w - bw/2 - margin) / grid_step) + 1)]:
            bx0 = x - bw/2; bx1 = x + bw/2
            by0 = edge_y - bh/2; by1 = edge_y + bh/2
            if not has_overlap(bx0, bx1, by0, by1, pad_bboxes):
                candidates.append((999, x, edge_y))  # highest priority

    # 若板边无位，网格全板搜索
    if not candidates:
        for x in [round(i * grid_step, 1) for i in range(
                int((-half_w + bw/2 + margin) / grid_step),
                int((half_w - bw/2 - margin) / grid_step) + 1)]:
            for y in [round(i * grid_step, 1) for i in range(
                    int((-half_h + bh/2 + margin) / grid_step),
                    int((half_h - bh/2 - margin) / grid_step) + 1)]:
                bx0 = x - bw/2; bx1 = x + bw/2
                by0 = y - bh/2; by1 = y + bh/2
                if not has_overlap(bx0, bx1, by0, by1, pad_bboxes):
                    edge_score = max(abs(y) - half_h + 2, 0) + max(abs(x) - half_w + 2, 0)
                    candidates.append((edge_score, x, y))

    candidates.sort(key=lambda c: -c[0])
    return [(c[1], c[2]) for c in candidates]

# ===== 放置丝印 =====
def place_silk(board, text, x, y, size_mm, layer=pcbnew.F_SilkS, mirrored=False):
    """在 PCB 上放置丝印文本"""
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size_mm), pcbnew.FromMM(size_mm)))
    t.SetLayer(layer)
    t.SetTextThickness(pcbnew.FromMM(0.12))
    if mirrored:
        t.SetMirrored(True)
    board.Add(t)

def remove_all_silk(board):
    """移除所有丝印"""
    removed = 0
    for d in list(board.GetDrawings()):
        if d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            board.Remove(d)
            removed += 1
    return removed

# ===== 主流程 =====
def place_all_silk(board, texts, design_json_path=None):
    """
    texts: list of dicts with keys:
      - 'text': str (required)
      - 'size': float or None (auto-select if None)
      - 'layer': 'F' or 'B' (default 'F')
      - 'mirrored': bool (default False for F, True for B)

    Returns: list of placed items with positions
    """
    pad_bboxes = collect_pad_bboxes(board)
    remove_all_silk(board)

    placed = []
    for item in texts:
        text = item['text']
        pref_size = item.get('size', None)
        layer = pcbnew.F_SilkS if item.get('layer', 'F') == 'F' else pcbnew.B_SilkS
        mirrored = item.get('mirrored', layer == pcbnew.B_SilkS)

        # Try preferred size, fall back to 0.6mm
        for sz in ([pref_size] if pref_size else [0.8, 0.6]):
            if sz is None:
                continue
            candidates = find_safe_position(text, sz, pad_bboxes)
            if candidates:
                x, y = candidates[0]
                place_silk(board, text, x, y, sz, layer, mirrored)
                placed.append({'text': text, 'x': x, 'y': y, 'size': sz,
                               'layer': item.get('layer', 'F')})
                break
        else:
            # No safe position found — place at board edge as last resort
            x, y = 0.0, 10.5
            sz = 0.6
            place_silk(board, text, x, y, sz, layer, mirrored)
            placed.append({'text': text, 'x': x, 'y': y, 'size': sz,
                           'layer': item.get('layer', 'F'), 'fallback': True})

    # Sync to design.json if provided
    if design_json_path and os.path.exists(design_json_path):
        d = json.load(open(design_json_path, encoding='utf-8'))
        d['silkscreen'] = [{
            'text': p['text'],
            'x': round(p['x'], 1),
            'y': round(p['y'], 1),
            'size_mm': p['size'],
            'layer': p['layer']
        } for p in placed]
        json.dump(d, open(design_json_path, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)

    return placed

# ===== CLI =====
if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='PCBA Skill v5.3 丝印安全放置')
    ap.add_argument('--board', required=True, help='.kicad_pcb 路径')
    ap.add_argument('--design', default=None, help='design.json 路径（可选，用于同步）')
    ap.add_argument('--texts', default=None, help='JSON: [{\"text\":\"...\",\"size\":0.8,\"layer\":\"F\"}]')
    ap.add_argument('--apply', action='store_true', help='实际写入（否则仅预览）')
    args = ap.parse_args()

    board = pcbnew.LoadBoard(args.board)

    # Default texts if none provided
    if args.texts:
        texts = json.loads(args.texts)
    else:
        # Try to read from design.json meta
        d = json.load(open(args.design, encoding='utf-8')) if args.design and os.path.exists(args.design) else {}
        board_name = d.get('meta', {}).get('board_name', 'PCB')
        version = d.get('meta', {}).get('version', 'V1.0')
        texts = [
            {'text': board_name, 'size': None, 'layer': 'F'},
            {'text': version, 'size': None, 'layer': 'F'},
        ]

    if args.apply:
        placed = place_all_silk(board, texts, args.design)
        board.Save(args.board)
        print(f'Placed {len(placed)} silk items:')
        for p in placed:
            fb = 'fallback' if p.get('fallback') else 'OK'
            txt = p['text']; px = p['x']; py = p['y']; sz = p['size']; ly = p['layer']
            print(f'  \"{txt}\" @({px},{py}) {sz}mm {ly}Silk [{fb}]')
    else:
        pad_bboxes = collect_pad_bboxes(board)
        print(f'Board: {len(pad_bboxes)} pad bboxes')
        for item in texts:
            text = item['text']
            print(f'  \"{text}\":')
            for sz in [0.8, 0.6]:
                candidates = find_safe_position(text, sz, pad_bboxes)
                print(f'    @{sz}mm: {len(candidates)} safe spots')
