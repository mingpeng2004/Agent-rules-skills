#!/usr/bin/env python3
"""
PCBA Skill v4.0 — Gerber / Drill / BOM / PickAndPlace 生成器模板
用法: 复制此脚本到项目 scripts/ 目录, 填写 COMPONENTS / ROUTES / SILKSCREEN,
      然后运行 py scripts/generate_gerber.py
"""
import os, json, zipfile
from datetime import datetime

OUT = "dist/manufacturing"
os.makedirs(OUT, exist_ok=True)
os.makedirs("dist", exist_ok=True)

# ============================================================
# TODO: 用户填入 Phase 3 坐标 + Phase 4 走线
# ============================================================
COMPONENTS = {
    # "J1": {"type": "SMD_CONN_6P", "x": 0, "y": -7.0, "pads": [...]},
}

ROUTES = [
    # ("+5V", "top", 0.5, [(x1, y1), (x2, y2), ...]),
]

SILKSCREEN = [
    # {"type": "text", "x": -3.125, "y": -8.5, "text": "VCC", "h": 1.0},
]

BOARD_W = 14.0
BOARD_H = 20.0

# ============================================================
# Gerber RS-274X 生成核心 (无需修改)
# ============================================================
def mm_to_gerber(mm, decimals=4):
    return int(round(mm * 10**decimals))

def gerber_header(title):
    return [
        "%FSLAX46Y46*%",
        "%MOMM*%",
        "%LPD*%",
        f"G04 {title}*",
        f"G04 Generated: {datetime.now().isoformat()}*",
    ]

def gerber_aperture_circle(dia_mm, d_code):
    return f"%ADD{d_code}C,{dia_mm:.4f}*%"

def gerber_aperture_rect(w_mm, h_mm, d_code):
    return f"%ADD{d_code}R,{w_mm:.4f}X{h_mm:.4f}*%"

def draw_rect_pad_flash(x, y, w, h, d_code):
    cx, cy = mm_to_gerber(x), mm_to_gerber(y)
    return [f"D{d_code}*", f"X{cx}Y{cy}D03*"]

def draw_circle_pad_flash(x, y, dia, d_code):
    cx, cy = mm_to_gerber(x), mm_to_gerber(y)
    return [f"D{d_code}*", f"X{cx}Y{cy}D03*"]

def draw_polyline(points, d_code):
    if not points: return []
    out = [f"D{d_code}*", f"X{mm_to_gerber(points[0][0])}Y{mm_to_gerber(points[0][1])}D02*"]
    for x, y in points[1:]:
        out.append(f"X{mm_to_gerber(x)}Y{mm_to_gerber(y)}D01*")
    return out

def gerber_footer():
    return ["M02*"]

# ============================================================
# 7 个 Gerber 文件生成函数
# ============================================================
def gen_copper_top():
    lines = gerber_header("Top Copper Layer")
    lines.append(gerber_aperture_rect(0.6, 1.5, 10))
    lines.append(gerber_aperture_rect(1.0, 1.2, 11))
    lines.append(gerber_aperture_rect(0.8, 0.9, 12))
    lines.append(gerber_aperture_circle(2.5, 14))
    lines.append(gerber_aperture_circle(5.0, 15))
    # TODO: 遍历 COMPONENTS 写入焊盘 flash + 走线 LINE
    for ref, comp in COMPONENTS.items():
        for p in comp["pads"]:
            if comp["type"] in ("SMD_CONN_6P",):
                lines.extend(draw_rect_pad_flash(p["x"], p["y"], p["w"], p["h"], 10))
            elif comp["type"] in ("CAP_0805",):
                lines.extend(draw_rect_pad_flash(p["x"], p["y"], p["w"], p["h"], 11))
            elif comp["type"] in ("CAP_0603", "RES_0603"):
                lines.extend(draw_rect_pad_flash(p["x"], p["y"], p["w"], p["h"], 12))
            elif comp["type"] in ("PTH_ARRAY_6P",):
                lines.extend(draw_circle_pad_flash(p["x"], p["y"], p["outer"], 14))
            elif comp["type"] in ("MOUNT_HOLE_PTH",):
                lines.extend(draw_circle_pad_flash(comp["x"], comp["y"], comp["outer"], 15))
    for net, layer, width, points in ROUTES:
        if layer == "top" and len(points) >= 2:
            lines.extend(draw_polyline(points, 13))
    lines.extend(gerber_footer())
    return "\n".join(lines)

def gen_copper_bottom():
    lines = gerber_header("Bottom Copper Layer (GND Pour)")
    lines.append(gerber_aperture_rect(13.0, 19.0, 30))
    lines.append("D30*")
    lines.append(f"X{mm_to_gerber(0)}Y{mm_to_gerber(0)}D03*")
    lines.extend(gerber_footer())
    return "\n".join(lines)

def gen_soldermask_top():
    lines = gerber_header("Top Soldermask Layer")
    lines.append(gerber_aperture_rect(0.8, 1.7, 10))
    lines.append(gerber_aperture_rect(1.2, 1.4, 11))
    lines.append(gerber_aperture_rect(1.0, 1.1, 12))
    lines.append(gerber_aperture_circle(2.7, 14))
    lines.append(gerber_aperture_circle(5.2, 15))
    for ref, comp in COMPONENTS.items():
        for p in comp["pads"]:
            if comp["type"] == "SMD_CONN_6P":
                lines.extend(draw_rect_pad_flash(p["x"], p["y"], 0.8, 1.7, 10))
            elif comp["type"] == "CAP_0805":
                lines.extend(draw_rect_pad_flash(p["x"], p["y"], 1.2, 1.4, 11))
            elif comp["type"] in ("CAP_0603", "RES_0603"):
                lines.extend(draw_rect_pad_flash(p["x"], p["y"], 1.0, 1.1, 12))
            elif comp["type"] == "PTH_ARRAY_6P":
                lines.extend(draw_circle_pad_flash(p["x"], p["y"], 2.7, 14))
            elif comp["type"] == "MOUNT_HOLE_PTH":
                lines.extend(draw_circle_pad_flash(comp["x"], comp["y"], 5.2, 15))
    lines.extend(gerber_footer())
    return "\n".join(lines)

def gen_soldermask_bottom():
    lines = gerber_header("Bottom Soldermask Layer (mirror of top)")
    lines.append("M02*")
    return "\n".join(lines)

def gen_silkscreen_top():
    lines = gerber_header("Top Silkscreen Layer")
    lines.append(gerber_aperture_circle(0.15, 50))
    for s in SILKSCREEN:
        if s["type"] == "text":
            x, y, h = s["x"], s["y"], s["h"]
            lines.extend([
                f"D50*",
                f"X{mm_to_gerber(x - h*0.8)}Y{mm_to_gerber(y)}D02*",
                f"X{mm_to_gerber(x + h*0.8)}Y{mm_to_gerber(y)}D01*",
            ])
    lines.extend(gerber_footer())
    return "\n".join(lines)

def gen_outline():
    lines = gerber_header(f"Board Outline ({BOARD_W}mm x {BOARD_H}mm)")
    lines.append(gerber_aperture_circle(0.1, 60))
    w, h = BOARD_W/2, BOARD_H/2
    lines.extend([
        "D60*",
        f"X{mm_to_gerber(-w)}Y{mm_to_gerber(-h)}D02*",
        f"X{mm_to_gerber( w)}Y{mm_to_gerber(-h)}D01*",
        f"X{mm_to_gerber( w)}Y{mm_to_gerber( h)}D01*",
        f"X{mm_to_gerber(-w)}Y{mm_to_gerber( h)}D01*",
        f"X{mm_to_gerber(-w)}Y{mm_to_gerber(-h)}D01*",
    ])
    lines.extend(gerber_footer())
    return "\n".join(lines)

def gen_paste_top():
    lines = gerber_header("Top Solder Paste Layer")
    lines.append(gerber_aperture_rect(0.6, 1.5, 10))
    lines.append(gerber_aperture_rect(1.0, 1.2, 11))
    lines.append(gerber_aperture_rect(0.8, 0.9, 12))
    for ref, comp in COMPONENTS.items():
        if comp["type"] not in ("SMD_CONN_6P", "CAP_0805", "CAP_0603", "RES_0603"):
            continue
        d = 10 if comp["type"] == "SMD_CONN_6P" else (11 if comp["type"] == "CAP_0805" else 12)
        for p in comp["pads"]:
            lines.extend(draw_rect_pad_flash(p["x"], p["y"], p["w"], p["h"], d))
    lines.extend(gerber_footer())
    return "\n".join(lines)

def gen_drill():
    lines = ["M48", "; FILE_FORMAT=2:0", "; Generated by PCBA Skill v4.0",
             f"; Date: {datetime.now().isoformat()}",
             "FMAT,2", "METRIC,TZ",
             "T1C1.000", "T2C2.500", "T3C0.300", "%",
             "G90", "G05"]
    for ref, comp in COMPONENTS.items():
        if comp["type"] == "PTH_ARRAY_6P":
            lines.append("T1")
            for p in comp["pads"]:
                lines.append(f"X{p['x']*1000:.0f}Y{p['y']*1000:.0f}")
        elif comp["type"] == "MOUNT_HOLE_PTH":
            lines.append("T2")
            lines.append(f"X{comp['x']*1000:.0f}Y{comp['y']*1000:.0f}")
    # GND 缝合孔 (示例: H1/H2 各 4 个, 半径 1.5mm)
    lines.append("T3")
    vias = [(-5.0 + 1.5, 8.0), (-5.0 - 1.5, 8.0), (-5.0, 8.0 + 1.5), (-5.0, 8.0 - 1.5),
            ( 5.0 + 1.5, 8.0), ( 5.0 - 1.5, 8.0), ( 5.0, 8.0 + 1.5), ( 5.0, 8.0 - 1.5)]
    for vx, vy in vias:
        lines.append(f"X{vx*1000:.0f}Y{vy*1000:.0f}")
    lines.append("M30")
    return "\n".join(lines)

def gen_bom():
    rows = [["Comment", "Designator", "Footprint", "LCSC#", "Manufacturer", "Qty", "Unit Price (CNY)"]]
    for ref, comp in COMPONENTS.items():
        rows.append([comp.get("value", ref), ref, comp["type"], comp.get("lcsc", "N/A"),
                     comp.get("manufacturer", ""), "1", str(comp.get("price", 0))])
    return "\n".join(",".join(row) for row in rows)

def gen_pickplace():
    rows = [["Designator", "Comment", "Footprint", "Center-X(mm)", "Center-Y(mm)", "Layer", "Rotation", "Side"]]
    for ref, comp in COMPONENTS.items():
        if comp["type"] not in ("SMD_CONN_6P", "CAP_0805", "CAP_0603", "RES_0603"):
            continue
        rows.append([ref, comp.get("value", ""), comp["type"], f"{comp['x']:.4f}",
                     f"{comp['y']:.4f}", "F.Cu", "0", "top"])
    return "\n".join(",".join(row) for row in rows)

def main():
    files = {
        "Gerber_Copper_Top.gbr": gen_copper_top(),
        "Gerber_Copper_Bottom.gbr": gen_copper_bottom(),
        "Gerber_Soldermask_Top.gbr": gen_soldermask_top(),
        "Gerber_Soldermask_Bottom.gbr": gen_soldermask_bottom(),
        "Gerber_Silkscreen_Top.gbr": gen_silkscreen_top(),
        "Gerber_Outline.gbr": gen_outline(),
        "Gerber_Paste_Top.gbr": gen_paste_top(),
        "NC_Drill.drl": gen_drill(),
        "BOM.csv": gen_bom(),
        "PickAndPlace.csv": gen_pickplace(),
    }
    for fname, content in files.items():
        with open(os.path.join(OUT, fname), "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  [OK] {os.path.join(OUT, fname)}")
    zip_path = "dist/<PROJECT>_Gerber_Package.zip".replace("<PROJECT>", os.path.basename(os.getcwd()))
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in files:
            zf.write(os.path.join(OUT, fname), fname)
    print(f"\n  [ZIP] {zip_path}")
    print("\n[DONE] 9 manufacturing files + ZIP package")

if __name__ == "__main__":
    main()