#!/usr/bin/env python3
"""
PCBA Skill v4.2 — V3 格式 .eprj2 重建脚本
基于官方 V3 格式规范 (lceda-pro-file-format-v3_2025.10.21)

.eprj2 = ZIP 包含:
  - *.epru (主 PCB 内容, 明文 JSON Lines)
  - project2.json (项目元数据)
  - IMAGE/ (可选预览图)

关键技术:
  - JSON Lines 格式: {"type":"XXX","ticket":N,"id":"ID"}||{...data...}|
  - DOCHEAD 起始, M02 结束
  - 坐标单位: mm
"""
import os
import json
import zipfile
import shutil
import time
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(PROJECT_ROOT, "CS5552_CONN_BD_20260707.eprj2")
BACKUP = os.path.join(PROJECT_ROOT, "CS5552_CONN_BD_20260707.backup.v2.eprj2")

# 备份现有 .eprj2 (V2 格式)
if os.path.exists(TARGET) and not os.path.exists(BACKUP):
    shutil.copy2(TARGET, BACKUP)
    print(f"[BACKUP] {BACKUP}")

# ============================================================
# 元数据 (从原 .eprj2 提取)
# ============================================================
with open(TARGET, "rb") as f:
    pass  # SQLite, 用之前的 Python 脚本提取

# 简化: 用之前提取的 UUID
PROJECT_UUID = "726c0637bb774cddfc43d436a608cc325845ae310f0b07b9530aa344f282cf93"
BRANCH_UUID = "cd64d2c2d8b241349f1b8f27689cfc12"
PROJECT_NAME = "CS5552_CONN_BD_20260707"

# ============================================================
# 生成 PCB .epru 内容 (V3 格式 JSON Lines)
# ============================================================
eid = 1
def next_id():
    global eid
    eid += 1
    return f"e{eid-1}"

z = 1.0

def z_next():
    global z
    z += 0.001
    return round(z, 3)

# 注意: 坐标单位是 mm, 但 V3 用的是 0.01 inch 基础单位?
# 查看 sample: canvas.gridXSize=10 表示 10 个单位, snap=0.5 表示 0.5 单位
# 看 layer 颜色用 #ff0000, 实际坐标值用纯数字 (mm 假设)
# 从 sample 看 {"originX":0,"originY":0,"unit":"mm"} - 是 mm

epru_lines = []

# 1. DOCHEAD
epru_lines.append('{"type":"DOCHEAD","ticket":1}||{"docType":"PCB","uuid":"' + PROJECT_NAME + '_PCB","client":"AI-Skill-v4.2","version":"' + str(int(time.time()*1000)) + '","user":{"uuid":"' + PROJECT_UUID + '"}}|')

# 2. CANVAS
epru_lines.append('{"type":"CANVAS","ticket":1,"id":"CANVAS"}||{"originX":0,"originY":0,"unit":"mm","gridXSize":10,"gridYSize":10,"snapXSize":0.5,"snapYSize":0.5,"altSnapXSize":1,"altSnapYSize":1,"gridType":"NONE","multiGridType":"NONE","multiGridRatio":5,"highlightValue":0.5}|')

# 3. LAYER 配置 (2 层板)
layers = [
    (1, 'TOP',                'Top Layer'),
    (2, 'BOTTOM',             'Bottom Layer'),
    (3, 'TOP_SILK',           'Top Silkscreen Layer'),
    (4, 'BOT_SILK',           'Bottom Silkscreen Layer'),
    (5, 'TOP_SOLDER_MASK',    'Top Solder Mask Layer'),
    (6, 'BOT_SOLDER_MASK',    'Bottom Solder Mask Layer'),
    (7, 'TOP_PASTE_MASK',     'Top Paste Mask Layer'),
    (11, 'OUTLINE',           'Board Outline Layer'),
    (12, 'MULTI',             'Multi-Layer'),
]
for lid, ltype, lname in layers:
    epru_lines.append(f'{{"type":"LAYER","ticket":{lid+10},"id":"[\\"LAYER\\",{lid}]"}}||{{"layerType":"{ltype}","layerName":"{lname}","use":true,"show":true,"locked":false,"activeColor":"#ff0000","activateTransparency":1,"inactiveColor":"#7f0000","inactiveTransparency":1}}|')

# 4. ACTIVE_LAYER
epru_lines.append('{"type":"ACTIVE_LAYER","ticket":100}||{"layerId":1}|')

# 5. 板框 (14x20mm)
hw, hh = 7.0, 10.0
corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh), (-hw, -hh)]
for i in range(len(corners) - 1):
    x1, y1 = corners[i]
    x2, y2 = corners[i+1]
    eid_str = next_id()
    epru_lines.append(f'{{"type":"LINE","id":"{eid_str}","ticket":{i+200}}}||{{"partitionId":null,"groupId":0,"locked":1,"zIndex":{z_next()},"netName":null,"layerId":11,"startX":{x1},"startY":{y1},"endX":{x2},"endY":{y2},"width":0.1}}|')

# 6. 9 个元件 (COMPONENT)
components = [
    ('J1', 0.0, -7.0, 1, 'GH1.25-6PWBPZ'),       # 顶层 SMD
    ('C1', -2.6, -4.5, 1, '10uF'),               # 顶层 0805
    ('C2', -2.6, -3.0, 1, '0.1uF'),              # 顶层 0603
    ('R1', -0.625, -1.0, 1, '22R'),              # 顶层 0603
    ('R2', 0.625, -1.0, 1, '22R'),               # 顶层 0603
    ('R3', 1.875, -1.0, 1, '22R'),               # 顶层 0603
    ('J2', 0.0, 2.5, 12, 'PTH-1x6-1.25mm'),      # 多层 PTH
    ('H1', -5.0, 8.0, 12, 'M2.5 PTH'),          # 多层 PTH
    ('H2', 5.0, 8.0, 12, 'M2.5 PTH'),           # 多层 PTH
]
for ref, x, y, layer_id, value in components:
    eid_str = next_id()
    epru_lines.append(f'{{"type":"COMPONENT","id":"{eid_str}","ticket":300}}||{{"partitionId":null,"groupId":0,"locked":1,"zIndex":{z_next()},"layerId":{layer_id},"positionX":{x},"positionY":{y},"angle":0,"attrs":{{"Designator":"{ref}","Value":"{value}"}}}}|')

# 7. 9 条走线 (LINE on Top Layer)
routes = [
    ('+5V', 0.5, [(-3.125, -7), (-3.125, -3), (-3.0, -3), (-3.0, -3), (-3.1, -4.5), (-3.1, -4.5), (-3.125, 2.5)]),
    ('GND', 0.5, [(-1.875, -7), (-1.875, -3), (-2.2, -3), (-2.2, -3), (-2.1, -4.5), (-2.1, -4.5), (-1.875, 2.5)]),
    ('SPI_SCK', 0.3, [(-0.625, -7), (-0.625, -1), (-1.025, -1)]),
    ('SPI_SCK_OUT', 0.3, [(-0.225, -1), (-0.625, 2.5)]),
    ('SPI_MOSI', 0.3, [(0.625, -7), (0.625, -1), (0.225, -1)]),
    ('SPI_MOSI_OUT', 0.3, [(1.025, -1), (0.625, 2.5)]),
    ('SPI_MISO', 0.3, [(1.875, -7), (1.875, -1), (1.475, -1)]),
    ('SPI_MISO_OUT', 0.3, [(2.275, -1), (1.875, 2.5)]),
    ('SPI_CS', 0.25, [(3.125, -7), (3.125, 2.5)]),
]
for net, w, points in routes:
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i+1]
        if x1 == x2 and y1 == y2:
            continue
        eid_str = next_id()
        epru_lines.append(f'{{"type":"LINE","id":"{eid_str}","ticket":400}}||{{"partitionId":null,"groupId":0,"locked":1,"zIndex":{z_next()},"netName":"{net}","layerId":1,"startX":{x1},"startY":{y1},"endX":{x2},"endY":{y2},"width":{w}}}|')

# 8. 底层 GND 铺铜 (POLY on Bottom Layer)
eid_str = next_id()
gnd_poly_path = f'[[{-hw+0.5},{-hh+0.5},"L",{hw-0.5},{-hh+0.5},"L",{hw-0.5},{hh-0.5},"L",{-hw+0.5},{hh-0.5},"L",{-hw+0.5},{-hh+0.5}]]'
epru_lines.append(f'{{"type":"POLY","id":"{eid_str}","ticket":500}}||{{"partitionId":null,"groupId":0,"locked":1,"zIndex":{z_next()},"netName":"GND","layerId":2,"width":0.3,"path":{gnd_poly_path}}}|')

# 9. 丝印文字 (STRING on Top Silk Layer)
silks = [
    ('VCC', -3.125, -8.5), ('GND', -1.875, -8.5),
    ('SCK', -0.625, -8.5), ('MOSI', 0.625, -8.5),
    ('MISO', 1.875, -8.5), ('CS', 3.125, -8.5),
    ('VCC', -3.125, 4.3), ('GND', -1.875, 4.3),
    ('SCK', -0.625, 4.3), ('MOSI', 0.625, 4.3),
    ('MISO', 1.875, 4.3), ('CS', 3.125, 4.3),
    ('V1.0', -6.0, -9.0), ('CS5552-CONNECT-BD', 0.0, -9.0),
    ('Φ2.5 GND', -5.0, 4.7), ('Φ2.5 GND', 5.0, 4.7),
    ('J1', -1.0, -6.0), ('C1', -1.5, -3.7),
    ('C2', -1.5, -2.3), ('R1', -1.0, -0.4),
    ('R2', 0.3, -0.4), ('R3', 1.6, -0.4),
    ('J2', -1.0, 3.0), ('H1', -5.5, 9.0), ('H2', 4.5, 9.0),
]
for text, x, y in silks:
    eid_str = next_id()
    # STRING 在 V3 格式中 (需要用正确的 schema)
    epru_lines.append(f'{{"type":"STRING","id":"{eid_str}","ticket":600}}||{{"partitionId":null,"groupId":0,"locked":1,"zIndex":{z_next()},"layerId":3,"positionX":{x},"positionY":{y},"text":"{text}","fontFamily":"Verdana","fontSize":1.0,"strokeWidth":0.15,"bold":0,"italic":0,"origin":4,"angle":0,"reverse":0,"reverseExpansion":0,"mirror":0,"width":null,"height":null,"path":null}}|')

# 10. J1 Pin1 三角 (用 3 条 LINE 简化)
tri_x, tri_y, tri_s = -4.5, -7.0, 0.6
tri_points = [(tri_x - tri_s/2, tri_y - tri_s*0.4),
              (tri_x + tri_s/2, tri_y - tri_s*0.4),
              (tri_x,            tri_y + tri_s*0.5),
              (tri_x - tri_s/2, tri_y - tri_s*0.4)]
for i in range(len(tri_points) - 1):
    eid_str = next_id()
    x1, y1 = tri_points[i]
    x2, y2 = tri_points[i+1]
    epru_lines.append(f'{{"type":"LINE","id":"{eid_str}","ticket":700}}||{{"partitionId":null,"groupId":0,"locked":1,"zIndex":{z_next()},"netName":null,"layerId":3,"startX":{x1},"startY":{y1},"endX":{x2},"endY":{y2},"width":0.15}}|')

# 11. END
epru_lines.append('M02|')

# 拼接 .epru 内容
EPRU_CONTENT = '\n'.join(epru_lines) + '\n'

# ============================================================
# project2.json (项目元数据)
# ============================================================
project2 = {
    "title": PROJECT_NAME,
    "cbb_project": False,
    "editorVersion": "",
    "introduction": "",
    "description": "GH1.25-6PWBPZ 6Pin SPI Adapter Board\nAuto-generated by PCBA Skill v4.2\nPhase 0-5 SOP closed loop completed",
    "tags": ["SPI", "Adapter", "AI-Generated"],
    "private": False,
    "updateTime": int(time.time() * 1000),
    "createTime": int(time.time() * 1000),
    "user": {
        "uuid": PROJECT_UUID,
        "username": "AI-Skill",
        "nickname": "PCBA Skill v4.2"
    },
    "boards": {},
    "schematic": {
        "name": "Schematic1",
        "board": "",
        "source": "",
        "version": ""
    }
}

# ============================================================
# 组装 .eprj2 (ZIP)
# ============================================================
EPRU_FILENAME = f"{PROJECT_NAME}_PCB.epru"  # V3 标准命名

with zipfile.ZipFile(TARGET, 'w', zipfile.ZIP_DEFLATED) as zf:
    # 1. 写入 project2.json
    zf.writestr('project2.json', json.dumps(project2, indent=2, ensure_ascii=False))
    print(f'[WRITE] project2.json ({len(json.dumps(project2))} chars)')

    # 2. 写入 .epru (主 PCB 内容)
    zf.writestr(EPRU_FILENAME, EPRU_CONTENT)
    print(f'[WRITE] {EPRU_FILENAME} ({len(EPRU_CONTENT)} chars, {len(epru_lines)} lines)')

    # 3. 写入 IMAGE/ (空目录占位)
    zf.writestr('IMAGE/.gitkeep', '')
    print(f'[WRITE] IMAGE/.gitkeep')

print(f'\n[OK] New .eprj2 (V3 format) saved: {TARGET}')
print(f'     File size: {os.path.getsize(TARGET)} bytes')

# 验证
print(f'\n[VERIFY] Opening as ZIP and listing contents...')
with zipfile.ZipFile(TARGET, 'r') as zf:
    for info in zf.infolist():
        print(f'  {info.filename:40s} {info.file_size:>8d} bytes')

# 验证 .epru 可读
print(f'\n[VERIFY] First 3 lines of .epru:')
with zipfile.ZipFile(TARGET, 'r') as zf:
    with zf.open(EPRU_FILENAME) as f:
        for i, line in enumerate(f):
            if i >= 3: break
            print(f'  {line.decode("utf-8").strip()[:200]}')