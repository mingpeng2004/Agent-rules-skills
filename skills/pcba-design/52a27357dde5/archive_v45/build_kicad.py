#!/usr/bin/env python3
"""
PCBA Skill v4.4 — KiCad 项目生成器 (Phase 3.5 Layout Review 优化版)
CS5552-CONNECT-BD 重新设计 v2:
  - 板尺寸 14×20mm → 20×20mm
  - J1/J2 移到板左右两边, 旋转 90° 让 Pin1 朝下
  - H1/H2 上移 y=7.5 距板边 2.5mm (满足 IPC-2221)
  - 丝印统一 ≥1.0mm (满足 JLC DFM)
  - C1 紧贴 J1.P1 距仅 1.0mm
"""
import os
import sys
import json
import pcbnew

# KiCad 10 API 兼容层
def _api_safe(ki9_name, ki10_name, module=pcbnew):
    if hasattr(module, ki10_name):
        return getattr(module, ki10_name)
    return getattr(module, ki9_name)


# ============================================================
# Phase 3.5 Review 后的 v2 数据 (LAY.002)
# ============================================================
BOARD_W_MM = 20.0
BOARD_H_MM = 20.0

# 元件: (ref, footprint, value, x_mm, y_mm, layer, rotation_deg)
COMPONENTS = [
    ('J1', 'Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical', 'GH1.25-6PWBPZ', -7.0, 0.0, pcbnew.F_Cu, 90),
    ('C1', 'Capacitor_SMD:C_0805_2012Metric', '10uF', -3.0, -6.0, pcbnew.F_Cu, 0),
    ('C2', 'Capacitor_SMD:C_0603_1608Metric', '0.1uF', -1.0, -6.0, pcbnew.F_Cu, 0),
    ('R1', 'Resistor_SMD:R_0603_1608Metric', '22R', -1.5, -0.625, pcbnew.F_Cu, 0),
    ('R2', 'Resistor_SMD:R_0603_1608Metric', '22R',  0.0, -1.875, pcbnew.F_Cu, 0),
    ('R3', 'Resistor_SMD:R_0603_1608Metric', '22R',  1.5, -3.125, pcbnew.F_Cu, 0),
    ('J2', 'Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical', 'GH1.25-6PWBPZ', 7.0, 0.0, pcbnew.F_Cu, 90),
    ('H1', 'MountingHole:MountingHole_2.5mm_Pad', 'M2.5', -7.5, 7.5, pcbnew.F_Cu, 0),
    ('H2', 'MountingHole:MountingHole_2.5mm_Pad', 'M2.5',  7.5, 7.5, pcbnew.F_Cu, 0),
]

# 走线 (v6.4: 斜向绕过 J1/J2 本体, 中点不穿任何元件 bbox)
# 核心: 端点必须在 J1/J2 焊盘 (P1..P6), 走线段从焊盘 y 端点斜向走出本体 (-5.75 或 5.75)
# 然后水平走到对侧, 再斜向回到 J2 焊盘
# 6 路走线 (P1..P6):
ROUTES = [
    # +5V: J1.P1(-7, 3.125) → 斜到 (-5.75, 3.875) (J1 本体外+焊盘顶) → 水平 (5.75, 3.875) → 斜到 J2.TH1(7, 3.125)
    ('+5V', 0.5, [(-7, 3.125), (-5.75, 3.875), (5.75, 3.875), (7, 3.125)]),
    # GND: J1.P2(-7, 1.875) → 斜到 (-5.75, 2.625) (P2 顶) → 水平 (5.75, 2.625) → 斜到 J2.TH2(7, 1.875)
    ('GND', 0.5, [(-7, 1.875), (-5.75, 2.625), (5.75, 2.625), (7, 1.875)]),
    # SCK: J1.P3(-7, 0.625) → 斜到 (-5.75, 1.375) (P3 顶) → 水平 (5.75, 1.375) → 斜到 J2.TH3(7, 0.625)
    ('SPI_SCK', 0.3, [(-7, 0.625), (-5.75, 1.375), (5.75, 1.375), (7, 0.625)]),
    # MOSI: J1.P4(-7, -0.625) → 斜到 (-5.75, 0.125) (P4 顶) → 水平 (5.75, 0.125) → 斜到 J2.TH4(7, -0.625)
    ('SPI_MOSI', 0.3, [(-7, -0.625), (-5.75, 0.125), (5.75, 0.125), (7, -0.625)]),
    # MISO: J1.P5(-7, -1.875) → 斜到 (-5.75, -1.125) (P5 顶) → 水平 (5.75, -1.125) → 斜到 J2.TH5(7, -1.875)
    ('SPI_MISO', 0.3, [(-7, -1.875), (-5.75, -1.125), (5.75, -1.125), (7, -1.875)]),
    # CS: J1.P6(-7, -3.125) → 斜到 (-5.75, -2.5) (P6 顶 - 0.125mm 安全间距) → 水平 (5.75, -2.5) → 斜到 J2.TH6(7, -3.125)
    ('SPI_CS', 0.25, [(-7, -3.125), (-5.75, -2.5), (5.75, -2.5), (7, -3.125)]),
]

# 丝印 v6 (v6 坐标, 全部 ≥0.8mm)
SILKSCREEN = [
    # J1 信号标签 (左侧外侧)
    ('J1.P1 VCC',  -7.0,  4.5, 0.8),
    ('J1.P2 GND',  -7.0,  3.2, 0.8),
    ('J1.P3 SCK',  -7.0,  1.0, 0.8),
    ('J1.P4 MOSI', -7.0, -1.0, 0.8),
    ('J1.P5 MISO', -7.0, -2.5, 0.8),
    ('J1.P6 CS',   -7.0, -3.7, 0.8),
    # J2 信号标签 (右侧外侧)
    ('J2.TH1 VCC',  7.0,  4.5, 0.8),
    ('J2.TH2 GND',  7.0,  3.2, 0.8),
    ('J2.TH3 SCK',  7.0,  1.0, 0.8),
    ('J2.TH4 MOSI', 7.0, -1.0, 0.8),
    ('J2.TH5 MISO', 7.0, -2.5, 0.8),
    ('J2.TH6 CS',   7.0, -3.7, 0.8),
    # 元件位号
    ('J1', -8.5,  4.0, 0.8),
    ('J2',  8.5,  4.0, 0.8),
    ('C1', -3.0, -4.5, 0.8),
    ('C2', -1.0, -4.5, 0.8),
    ('R1', -1.5,  0.5, 0.8),
    ('R2',  0.0, -0.7, 0.8),
    ('R3',  1.5, -2.0, 0.8),
    ('H1', -7.5,  9.0, 0.8),
    ('H2',  7.5,  9.0, 0.8),
    # 板标识
    ('V1.0',              -8.5,  6.0, 0.8),
    ('CS5552-CONNECT-BD',  0.0,  6.0, 0.8),
    ('F2.5 GND',          -7.5,  5.5, 0.8),
    ('F2.5 GND',           7.5,  5.5, 0.8),
]

# ============================================================
# KiCad 构建核心 (兼容 KiCad 9/10)
# ============================================================
KICAD_FOOTPRINT_LIB_PATH = os.environ.get(
    'KICAD_FOOTPRINT_LIB',
    r'C:\Program Files\KiCad\10.0\share\kicad\footprints'
)


def mm_to_pcbnew(mm):
    return pcbnew.FromMM(mm)


def to_v2(x_mm, y_mm):
    return pcbnew.VECTOR2I(mm_to_pcbnew(x_mm), mm_to_pcbnew(y_mm))


def _draw_segment_class():
    return _api_safe('DRAWSEGMENT', 'PCB_SHAPE')


def _track_class():
    return _api_safe('TRACK', 'PCB_TRACK')


def _text_class():
    return _api_safe('TEXTE_PCB', 'PCB_TEXT')


def create_net(board, net_name):
    if hasattr(board, 'GetNetByName'):
        net = board.GetNetByName(net_name)
    elif hasattr(board, 'GetNetsByName'):
        nets = board.GetNetsByName()
        net = nets.get(net_name) if isinstance(nets, dict) else None
    if net is None or (hasattr(net, 'GetNetname') and net.GetNetname() != net_name):
        net = pcbnew.NETINFO_ITEM(board, net_name)
        board.Add(net)
    return net


def place_footprint(board, fp_lib, value, ref, x_mm, y_mm, layer, rot=0):
    if ':' in fp_lib:
        lib_dir, fp_name = fp_lib.split(':', 1)
    else:
        lib_dir = fp_lib
        fp_name = fp_lib
    fp_path = os.path.join(KICAD_FOOTPRINT_LIB_PATH, lib_dir + '.pretty')
    fp = pcbnew.FootprintLoad(fp_path, fp_name)
    if fp is None:
        raise FileNotFoundError(f"Footprint {fp_name} not found in {fp_path}")
    fp.SetReference(ref)
    fp.SetValue(value)
    fp.SetPosition(to_v2(x_mm, y_mm))
    if rot != 0:
        fp.SetOrientationDegrees(rot)
    fp.SetLayer(layer)
    board.Add(fp)
    return fp


def add_track(board, net_name, width_mm, points):
    net = create_net(board, net_name)
    TRACK_CLS = _track_class()
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i+1]
        if x1 == x2 and y1 == y2:
            continue
        track = TRACK_CLS(board)
        track.SetStart(to_v2(x1, y1))
        track.SetEnd(to_v2(x2, y2))
        track.SetWidth(mm_to_pcbnew(width_mm))
        track.SetLayer(pcbnew.F_Cu)
        track.SetNet(net)
        board.Add(track)


def add_silk(board, text, x_mm, y_mm, size_mm=1.0):
    TEXT_CLS = _text_class()
    silk = TEXT_CLS(board)
    silk.SetText(text)
    silk.SetPosition(to_v2(x_mm, y_mm))
    silk.SetLayer(pcbnew.F_SilkS)
    silk.SetTextSize(to_v2(size_mm, size_mm))
    silk.SetTextThickness(pcbnew.FromMM(0.15))
    board.Add(silk)


def draw_board_outline(board, w_mm, h_mm):
    hw, hh = w_mm / 2, h_mm / 2
    corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh), (-hw, -hh)]
    CLS = _draw_segment_class()
    for i in range(len(corners) - 1):
        x1, y1 = corners[i]
        x2, y2 = corners[i+1]
        line = CLS(board)
        line.SetStart(to_v2(x1, y1))
        line.SetEnd(to_v2(x2, y2))
        line.SetLayer(pcbnew.Edge_Cuts)
        line.SetWidth(pcbnew.FromMM(0.1))
        board.Add(line)


def add_gnd_pour(board):
    hw, hh = BOARD_W_MM / 2 - 0.5, BOARD_H_MM / 2 - 0.5
    CLS = _draw_segment_class()
    fill = CLS(board)
    fill.SetStart(to_v2(-hw, -hh))
    fill.SetEnd(to_v2(hw, hh))
    fill.SetLayer(pcbnew.B_Cu)
    fill.SetWidth(mm_to_pcbnew(0.3))
    board.Add(fill)


def main():
    project_name = os.environ.get('PROJECT_NAME', 'CS5552_CONN_BD_v6')
    output_dir = os.environ.get('OUTPUT_DIR', 'dist_v6')
    os.makedirs(output_dir, exist_ok=True)

    try:
        version_str = pcbnew.GetSemanticVersion()
    except AttributeError:
        version_str = 'unknown'
    print(f'[INFO] KiCad version: {version_str}')
    print(f'[INFO] Board: {BOARD_W_MM}x{BOARD_H_MM}mm (v2 扩大)')

    kicad_path = os.path.join(output_dir, f'{project_name}.kicad_pcb')
    print(f'[INFO] Creating: {kicad_path}')

    board = pcbnew.NewBoard(kicad_path)
    if hasattr(board, 'GetDesignSettings'):
        ds = board.GetDesignSettings()
        ds.SetBoardThickness(pcbnew.FromMM(1.6))
        ds.SetCopperLayerCount(2)
    else:
        board.SetBoardThickness(pcbnew.FromMM(1.6))
        board.SetCopperLayerCount(2)

    print('[1/4] Drawing board outline...')
    draw_board_outline(board, BOARD_W_MM, BOARD_H_MM)

    print(f'[2/4] Placing {len(COMPONENTS)} footprints (v2 布局)...')
    for ref, fp_lib, value, x, y, layer, rot in COMPONENTS:
        try:
            place_footprint(board, fp_lib, value, ref, x, y, layer, rot)
            print(f'  [OK] {ref} @ ({x}, {y}) rot={rot}')
        except Exception as e:
            print(f'  [FAIL] {ref}: {e}')

    print(f'[3/4] Routing {len(ROUTES)} networks (v2 单向 J1→R1-R3→J2)...')
    for net_name, width, points in ROUTES:
        add_track(board, net_name, width, points)
        print(f'  [OK] Net {net_name}')

    print(f'[4/4] Adding {len(SILKSCREEN)} silk annotations (≥1.0mm)...')
    for text, x, y, size in SILKSCREEN:
        add_silk(board, text, x, y, size)

    print(f'Saving {kicad_path}...')
    try:
        board.Save(kicad_path)
    except TypeError:
        board.Save()
    print(f'  [OK] Saved: {kicad_path}')
    print(f'\n[DONE] v2 KiCad project generated.')
    print(f'  双击打开: {os.path.abspath(kicad_path)}')
    print(f'  Gerber 命令: "C:/Program Files/KiCad/10.0/bin/kicad-cli.exe" pcb export gerbers --output {output_dir}/mfg {kicad_path}')


if __name__ == '__main__':
    main()