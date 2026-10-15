# kicad-cli 速查（PCBA Skill v5.0 验证基线：KiCad 10.0.4 / Windows）

> 所有检查必须走 CLI 真实执行，禁止"模拟 DRC/ERC"。
> 探测路径：`scripts/kicad_env.py`（禁止硬编码 `C:\Program Files\KiCad\...`）

## 版本与探测
```bash
kicad-cli version                     # 门禁 E-01
```

## DRC（R 层门禁）
```bash
kicad-cli pcb drc board.kicad_pcb \
  --format json --severity-all --units mm \
  --refill-zones --save-board \
  --exit-code-violations \
  --output drc.json
# --refill-zones --save-board：回填铺铜并持久化（ZONE 检查前置）
# --exit-code-violations：有违规时退出码 ≠ 0，可直接做门禁
# --schematic-parity：PCB↔原理图一致性（有 .kicad_sch 时加）
```

## ERC（S 层门禁）
```bash
kicad-cli sch erc board.kicad_sch \
  --format json --severity-all --units mm \
  --exit-code-violations \
  --output erc.json
```

## 制造输出（O 层）
```bash
# Gerber（JLC 标准层组）
kicad-cli pcb export gerbers board.kicad_pcb \
  --layers "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts" \
  --no-protel-ext --check-zones --output mfg/
# --no-protel-ext：全部输出 .gbr（JLC 接受）；--check-zones：导出前回填铺铜

# 钻孔（Excellon，mm 单位，绝对原点）
kicad-cli pcb export drill board.kicad_pcb \
  --format excellon --drill-origin absolute --excellon-units mm --output mfg/

# 贴片坐标
kicad-cli pcb export pos board.kicad_pcb \
  --format csv --units mm --side both --smd-only --output mfg/board-pos.csv

# 3D 模型（结构核对）
kicad-cli pcb export step board.kicad_pcb --output mfg/board.step
```

## 视觉渲染（V 层门禁）
```bash
kicad-cli pcb render board.kicad_pcb --side top    --quality high --width 1600 --height 1200 -o top.png
kicad-cli pcb render board.kicad_pcb --side bottom --quality high -o bottom.png
kicad-cli pcb render board.kicad_pcb --rotate "-45,0,45" --perspective --quality high -o iso.png
# side 可选：top/bottom/left/right/front/back
```

## 其他
```bash
kicad-cli pcb export stats board.kicad_pcb --output stats.json   # 板统计
kicad-cli sch export bom board.kicad_sch --output bom.csv        # 从原理图出 BOM
kicad-cli fp export ...   # 封装库操作（较少用）
```

## 踩坑记录（实测）
| 坑 | 解法 |
|---|---|
| `PCB_VIA::GetWidth()` 无参调用触发 assert | 必须带层参 `via.GetWidth(pcbnew.F_Cu)` |
| `ZONE::GetFilledPolysList(layer)` 无该层填充时 assert | 先 `HasFilledPolysForLayer(layer)` 守卫 |
| KiCad 10 默认网络类间距 0.2mm | `ds.m_NetSettings.GetDefaultNetclass().SetClearance()` 显式写入 |
| 网络类设置在 `board.Save()` 时持久化到 `.kicad_pro` | 先写 pro 模板，再保存板 |
| `--no-protel-ext` 后所有层都是 `.gbr` | 按**层名子串**匹配文件，不要按扩展名 |
| `footprint.GetBoundingBox()` 包含飘远的文本 | DFM 测量用**焊盘 bbox**（run_checks._fp_pads_bbox） |
| Git Bash 的 `/tmp` ≠ Windows 的 `%TEMP%` | 跨工具传文件用项目内路径 |
