# 工具链参考（Toolchain）

> 每条工具：用途 / 关键命令 / 已知坑。新案子按此配置，不重蹈环境坑。

## 1. KiCad 10（原理图/PCB 权威源）

- **kicad-cli**（Windows 路径 `C:\Program Files\KiCad\10.0\bin\kicad-cli.exe`）：
  - `pcb drc --output report.txt board.kicad_pcb` → 人读报告（注意 KiCad 10 默认输出文本报告，非 JSON）
  - `pcb export gerbers --layers F.Cu,...,Edge.Cuts --output <dir> board.kicad_pcb`
  - `pcb export drill --format excellon --drill-origin absolute --excellon-units mm <同上>`
  - `pcb export pos --format csv --units mm --side both` → CPL 源数据
  - `sch erc` → ERC
- **pcbnew Python**（`...\bin\python.exe`）：脚本化编辑 .kicad_pcb（本项目 D23 修复方式）。
  - 坑：内存泄漏告警（swig）无害；SHAPE_POLY_SET 无 GetX/BoundingBox（用 Iterate/Outline）；板层编号 F.Cu=0, In1.Cu=4, In2.Cu=6, B.Cu=2（以文件 (layers) 段为准）。
- **坑**：Git Bash 下 `PROGRAMFILES` 环境变量可能缺失，脚本探测 KiCad 需回退绝对路径。

## 2. 嘉立创EDA Pro + easyeda-agent（嘉立创原生通路）

- 部署见 `tools/easyeda-agent/INSTALL_STATUS.md`（v1.5.1 已部署）。
- 新会话第一条：`easyeda update --check --exit-code`（版本门禁）。
- 常用：`easyeda health` / `sch check` / `pcb check` / `sch|pcb drc`。
- **能力边界**（官方声明）：稠密整板布线需外接 Freerouting；无编程式 undo；阻抗参数读不全，不能自动声称阻抗合格。
- 导入外部工程（KiCad/Altium）走 EasyEDA Pro GUI，导入后用 typed action 读取核验。

## 3. Freerouting（自动布线）

- 适合中低密度板；**输出必须全量 DRC**（B4 事故）。
- 流程：KiCad 导出 .dsn → Freerouting → .ses 导回 → DRC。

## 4. JLCPCB / LCSC（打样与供应链）

- **Tier1 裸板**：Gerber zip（Protel 扩展名）上传；4 层板厚 1.6mm 默认参数即可。
- **Tier2 PCBA**：BOM（Comment,Designator,Footprint,LCSC,Quantity）+ CPL；**料号 100% 覆盖否则自动核对失败**；CPL 方向在网站预览人工核对。
- **选型核验**：lcsc.com 产品页核对 MPN/封装/参数/库存；引用料号必须来自实际页面，禁止凭记忆。
- 镜像：GitHub 下载走 gh-proxy.com 回退 + sha256 校验。

## 5. 项目内脚本资产

| 脚本 | 用途 |
|---|---|
| `.claude/skills/pcba-design/scripts/export_jlcpcb.py` | JLCPCB 分级导出（Tier1 Gerber+钻孔 / Tier2 BOM+CPL），料号不全时列缺料清单并非零退出 |
| `.claude/skills/pcba-design/scripts/kicad_env.py` | KiCad 环境探测（需 PROGRAMFILES 环境变量） |
| `.claude/skills/pcba-system/scripts/pcba_gate.py` | 通用门禁引擎（intent-check/run/verify + 声明式检查） |
| `.claude/skills/design-gate/scripts/gate.py` | CS5552 案专用门禁（本项目实例） |
