---
name: pcba-design
description: >-
  Agent 驱动的 KiCad 全自动 PCB 设计闭环（v5.2）。从 PRD 到可打样 Gerber：design.json 单一事实源 →
  pcbnew 建板/建原理图 → Freerouting 工业级自动布线（Specctra DSN/SES） →
  kicad-cli 真实 DRC/ERC/几何/DFM/电气审查 → 自修复回路 →
  Gerber/钻孔/坐标/STEP 输出与回读验证 → JLCPCB 标准打样包生成 → AI 视觉复检。
  10+1 层检查点（E/I/S/L/R/D/O/V/F/ELEC/JLC），
  禁止假 PASS，所有检查真实测量。
  触发场景：PCB设计、PCBA、画板、帮我画/设计一块板、电路设计、原理图、布线、Layout、封装、
  嘉立创、JLC、KiCad、pcbnew、kicad-cli、Gerber、出打样文件、DFM、转接板、接口板、
  硬件开发、BOM、贴片、SMT、验收、打样、PCB 审查/评审。
whenToUse: >-
  只要对话涉及"设计/修改/审查一块电路板或从需求生成制造文件"就自动使用，无需用户点名。
type: prompt
disableModelInvocation: false
version: 5.2.0
author: AI Skill Lab (Ming)
target_platform: KiCad 9/10（kicad-cli + pcbnew）+ Freerouting 2.2.4 + JLCPCB 下单链路
trigger_keywords: [PCB设计, PCBA, 画板, 电路设计, 嘉立创, EDA, 硬件开发, Gerber, 转接板, 接口板, KiCad, pcbnew, kicad-cli, DFM, 验收, vibe coding]
parent_governance: ${USER_HOME}\.claude\CLAUDE.md v3.0.0+
project_validation: CS5552_WCD_V4.1（2026-07-23，DRC 0→0 全闭环收敛：0 短路/0 间距/0 交叉/0 未布线，20×22mm 4 层板，26 轮迭代收敛，Freerouting 工业级布线 + 手术式修复）
---

# PCBA 全自动设计闭环 Skill v5.2 — Agent 驱动 KiCad + Freerouting

> **核心目标**：从 PRD 出发，AI 无人工干预完成「设计 → 建板 → Freerouting 自动布线 → DRC 审查 → 手术式修复 → 制造输出」全闭环，
> 交付**可直接打样的量产级 Gerber 包 + JLCPCB 下单文件 + KiCad 源工程**，每一项目检都有机器证据。

## v5.1 → v5.2 关键升级（CS5552_WCD_V4.1 实战驱动，D16-D22）

| 维度 | v5.1（旧） | v5.2（新） |
|---|---|---|
| **布线引擎** | AI 手写 design.json routes/自研 router_ortho.py | **工业级 Freerouting 2.2.4**（Specctra DSN 导出 → 批处理自动布线 → SES 导回） |
| **布线收敛** | 26 轮脚本迭代未突破 DRC ~140（18×22mm） | **板宽 18→20mm + Freerouting → 首轮即达 DRC 0** |
| **自主修复** | 改 design.json → 重建板（慢，且改一引十） | **手术式修复**：移除冲突走线段 → 局部补线（不改全板） |
| **引脚映射验证** | 信任 design.json | **逐引脚核对数据手册原列**（发现 QFN20/SOP16 列混淆严重 bug） |
| **原理图验证** | 生成即信任 | 逐元件逐引脚核对标签位置（发现 127 引脚全部错位） |
| **板尺寸弹性** | 固定 | **Freerouting 首轮未布线数<3 时可微扩板宽 1-2mm 换取完全收敛** |
| **JLCPCB 交付** | 通用 Gerber | **两级交付**：Tier1 裸板打样包 + Tier2 PCBA 全贴装包（BOM+CPL+LCSC） |
| **检查点体系** | 9+1 层 | **10+1 层**（新增 JLC 层：嘉立创格式合规 + LCSC 料号覆盖率） |

## v4.5 → v5.0 根本升级

| 维度 | v4.5（旧） | v5.0（新） |
|---|---|---|
| 验证方式 | **JSON DSL 上"模拟 DRC"+ 硬编码 PASS**（v6 报告 100% PASS，实测 129 条违规） | **kicad-cli/pcbnew 真实测量**，退出码即门禁 |
| 检查清单 | 199 项，大量假 PASS、无证据 | 9 层 50+ 检查点，每项有自动测量方法；测不了标 MANUAL |
| 原理图 | 不生成（无 ERC 对象） | build_schematic.py 生成真实 .kicad_sch，kicad-cli ERC 实测 |
| 布线 | 端点手填坐标（v6 短路/未连接的根因） | **焊盘吸附**：端点写 `{"pad":"J1.3"}`，坐标取真实焊盘中心 |
| 网络表 | 无（焊盘无网络，DRC 误报短路） | design.json `nets[].pads` 显式赋网，连通性可验证 |
| 铺铜 | 画矩形假铺铜（v6 无 GND 层） | 真实 ZONE + ZONE_FILLER 填充 + DRC 回填 |
| 铺铜填充持久化 | 无 | `--refill-zones --save-board` 固化 |
| 网络类间距 | 不设（KiCad 默认 0.2mm 误杀设计） | 显式写入 .kicad_pro（0.15mm 可配） |
| 视觉验证 | 无 | kicad-cli render → AI 逐张看图（机器 DRC 查不出的"看着不对"） |
| 输出验证 | 信任导出日志 | verify_output.py **回读 Gerber/钻孔文件实测** |
| 自主性 | 每阶段等用户确认 | 自动门禁 + 自修复回路，仅 F 层终审交付用户 |

---

## 0. 铁律（违反 = 交付无效）

| # | 铁律 |
|---|---|
| R-01 | **禁止假 PASS**：每个检查点必须有机器证据（文件/退出码/测量值）；测不了的标 `MANUAL`，禁止默认通过 |
| R-02 | **唯一事实源**：全部设计数据在 `design.json`；脚本只读它，不内嵌设计数据 |
| R-03 | **真实工具链**：DRC/ERC/渲染/导出只用 kicad-cli；几何测量只用 pcbnew；禁止"模拟 DRC" |
| R-04 | **焊盘吸附**：走线端点一律 `{"pad":"REF.N"}`，禁止手填焊盘坐标 |
| R-05 | **先验证环境再动手**：每个会话先跑 `kicad_env.py`（E 层门禁） |
| R-06 | **自修复有熔断**：同一门禁 FAIL 连续 3 轮未收敛 → 停止，输出"跳出反思报告"（宪法 §8.4） |
| R-07 | **输出不信日志**：Gerber/钻孔/坐标文件必须回读实测（O 层门禁） |
| R-08 | **治理对接**：状态变更写 PROJECT_GOVERNANCE.md / status.md / decisions.log（宪法 §14/§15） |

---

## 1. 闭环状态机（FSM）v5.2

```
[E] 环境自检
  └─> [I] 输入门禁（design_validate.py）
        └─> [DESIGN] AI 编写 design.json（单一事实源）
              └─> [BUILD] build_board.py + build_schematic.py
                    └─> [ROUTE] **Freerouting 工业级自动布线**（v5.2 新增）
                    │     ├─ KiCad Specctra DSN 导出
                    │     ├─ Freerouting 2.2.4 批处理（--de/--do）
                    │     ├─ SES 导回 KiCad
                    │     └─ 手术式修复 Freerouting 缺陷 + finish_gaps 收尾
                    └─> [CHECK] run_checks.py（18 检查点）
                          │  FAIL → [FIX] 读 DRC 报告定位违规 → 局部移除/补线 → 回到 CHECK
                          │  （同一检查点 3 轮不收敛 → 熔断，考虑板尺寸微调）
                          └─> [EXPORT] export_mfg.py（Gerber/钻孔/坐标/STEP/zip/README）
                                └─> [JLC] export_jlcpcb.py（嘉立创标准打样包，v5.2 新增）
                                      └─> [OUT] verify_output.py（6 项回读实测）
                                            └─> [ELEC] elec_review.py（电气审查 8 项）
                                                  └─> [VISUAL] visual_review.py → AI 看图复检
                                                        └─> [FINAL] 终审报告 + 治理归档 → 交付用户
```

**关键新增（v5.2）**：
- **[ROUTE] 放弃手写路由**：26 轮设计迭代确认脚本坐标布线无法在密集板上收敛到 DRC=0。改用工业级 Freerouting 2.2.4（Specctra DSN→批处理自动布线→SES 导回），首轮即达 0 短路/0 间距/0 交叉。
- **[JLC] 嘉立创标准打样包**：Tier1 裸板 Gerber（Protel 扩展名+X2 格式+合并钻孔） + Tier2 PCBA 全贴装（BOM+CPL+LCSC 料号匹配）。
- **板尺寸弹性**：若 Freerouting 首轮残留飞线 ≤3 条，可微扩板宽 1-2mm 换取完全收敛（本案 18→20mm，用户确认）。

**每个门禁失败时的自修复纪律**：
1. 读证据（报告里的违规坐标/对象），定位根因，**改 design.json，不改生成物**；
2. 重新 BUILD + CHECK；
3. 修复必须使失败项变 PASS 且不引入新 FAIL，否则回滚该次修改换方案；
4. 第 3 次失败 → 熔断：列出 3 次尝试、根因假设、最小绕行方案，上报用户。

---

## 2. 检查点体系（9 层 50+ 项，全表见 references/checkpoints_v5.yaml）

| 层 | 名称 | 工具 | 关键项 | 一票否决项（P0） |
|---|---|---|---|---|
| E | 环境 | kicad_env.py | kicad-cli/pcbnew/库路径 | 全部 |
| I | 输入 | design_validate.py | 结构/数值域/封装真实存在/焊盘数/位号/网络名 | I-01~I-06 |
| S | 原理图 | kicad-cli sch erc | **真实 ERC 0 error** | S-ERC-01 |
| L | 布局 | pcbnew 实测 | 板框闭合/板尺寸/禁布区/丝印/边距 | L-GEO-01/02, L-KO-01 |
| R | 布线 | kicad-cli pcb drc | **真实 DRC 0 error**/0 未连接/线宽/载流 | R-DRC-01/02, R-WID-01, R-PWR-01, R-NET-01 |
| D | DFM | run_checks.py | 孔径/孔环/Fiducial/JLC 工艺对照 | D-DRL-01 |
| O | 输出 | verify_output.py | Gerber 层齐/钻孔/板框实测/三方一致/zip | O-01~O-05 |
| ELEC | 电气 | elec_review.py | 连通性/引脚映射/去耦/端接/阻抗/回流/压降/SPICE | E1-CONN, E1-PINMAP, E2-DECAP, E4-RETURN |
| V | 视觉 | kicad-cli render + AI 看图 | 布局观感/铺铜/丝印可读/3D 干涉 | （P1 级） |
| **JLC** | **嘉立创** | **export_jlcpcb.py** | **Tier1裸板格式合规 / Tier2 BOM的LCSC料号覆盖率 / CPL旋转校正** | **JLC-01/02/03** |
| V | 视觉 | kicad-cli render + AI 看图 | 布局观感/铺铜/丝印可读/3D 干涉 | （P1 级） |
| F | 终审 | AI 汇总 | PRD ✅ 清单映射实证/版本一致/治理归档 | F-01/F-02 |

**判定**：`REJECTED`=任一 P0 FAIL；`CONDITIONAL`=有 P1 FAIL 待用户签豁免；`APPROVED`=仅 WARN/MANUAL/NA。

---

## 3. 脚本清单（scripts/，全部项目无关、跨项目复用）

| 脚本 | 运行环境 | 作用 | 退出码 |
|---|---|---|---|
| `kicad_env.py` | 任意 Python | E 层：环境探测自检 | 0/1 |
| `design_validate.py` | KiCad Python | I 层：design.json 结构 + 封装试加载 | 0/1 |
| `build_board.py` | KiCad Python | design.json → .kicad_pcb（焊盘赋网/吸附走线/真铺铜/BOM） | 0 |
| `build_schematic.py` | KiCad Python | design.json → .kicad_sch（内嵌库符号，可过 ERC） | 0 |
| `run_checks.py` | KiCad Python | S/L/R/D 18 检查点 → check_report.json+md | 0=通过 1=REJECTED |
| `export_mfg.py` | 任意 Python | Gerber+钻孔+坐标+STEP+zip+下单 README | 0/1 |
| `verify_output.py` | KiCad Python | O 层：回读 Gerber/钻孔实测 + 三方一致 | 0/1 |
| `elec_review.py` | KiCad Python | ELEC 层：连通性/拓扑/SI/回流/压降/ngspice 8 项 | 0/1 |
| `visual_review.py` | 任意 Python | 渲染 top/bottom/front/iso PNG 供 AI 看图 | 0/1 |
| `silk_placer.py` | KiCad Python | **v5.3 新增**：丝印安全放置（预计算 BBox 碰撞检测 + 字号自动降级 0.8→0.6mm + design.json 同步） | 0/1 |
| **`router_ortho.py`** | KiCad Python | **v5.2 新增**：正交路由引擎（空间网格碰撞检测+分层总线），供 Freerouting 失败的 fallback | 0/1 |
| **`export_jlcpcb.py`** | 任意 Python | **v5.2 新增**：嘉立创标准打样包（Tier1 裸板+Tier2 PCBA），BOM中的LCSC料号匹配，缺料号诊断 | 0/1 |

**外部工具依赖（v5.2）**：
- **Freerouting 2.2.4**：`java -jar freerouting.jar -de <dsn> -do <ses>` 批处理自动布线（工业级，Specctra DSN 输入/SES 输出）
- DSN 导出：`pcbnew.ExportSpecctraDSN(board, dsn_path)`
- SES 导入：`pcbnew.ImportSpecctraSES(board, ses_path)`

**KiCad Python 路径**：`C:\Program Files\KiCad\<ver>\bin\python.exe`（由 kicad_env.py 探测，禁止硬编码）。

---

## 4. design.json 契约（templates/design.schema.json + design.example.json）

骨架（完整示例 = templates/design.example.json，即 CS5552 v7 实战版）：

```json
{
  "meta": {"project": "xxx", "board_name": "丝印板名", "version": "V1.0"},
  "dfm_profile": "jlc_2layer",
  "rules": {"clearance_mm": 0.15},
  "board": {"width_mm": 30, "height_mm": 20, "keepouts": [
    {"id": "KO_H1", "shape": "circle", "cx": 11.5, "cy": 6.5, "r": 5, "exempt": ["H1"]}]},
  "components": [
    {"ref": "J1", "footprint": "Connector_JST:JST_GH_...", "value": "GH1.25-6P",
     "x": -9.5, "y": 1.0, "rotation": 90, "lcsc": "C262522"}],
  "nets": [
    {"name": "+5V", "class": "power", "min_width_mm": 0.5, "max_current_a": 1.0,
     "pads": ["J1.1", "J2.1", "C1.1"]}],
  "vias": [{"net": "GND", "x": -6.1, "y": 2.875}],
  "routes": [
    {"net": "+5V", "width_mm": 0.5, "layer": "F.Cu",
     "points": [{"pad": "J1.1"}, {"x": -8.6, "y": 4.125}]}],
  "zones": [{"net": "GND", "layer": "B.Cu", "margin_mm": 0.5}],
  "silkscreen": [{"text": "VCC", "x": -6.2, "y": 4.125, "size_mm": 0.8, "rotation": 90}],
  "assembly": {"require_fiducial": false}
}
```

**关键语义**：
- `nets[].pads` 是**网络表**（焊盘赋网依据）——没有它焊盘无网络，DRC 全报短路；
- 走线端点 `{"pad":"J1.1"}` = 吸附真实焊盘中心（旋转/偏移怎么变都不会脱焊盘）；
- `max_current_a` 触发 IPC-2221 载流校核（R-PWR-01）；
- 元件 `rotation` 语义 = KiCad `SetOrientationDegrees`（实测：rot90 坐标映射 (x,y)→(y,−x)）。

---

## 5. 标准执行流程（AI 照此执行）

```bash
SK=/path/to/skills/pcba-design/scripts
KPY=$(kicad_env.py 探测的 KiCad Python)

# 0. E 层
python $SK/kicad_env.py                                   # 环境门禁

# 1. AI 从 PRD 提炼 design.json（内部思辨 → 落 JSON）
# 2. I 层
"$KPY" $SK/design_validate.py --design design.json

# 3. BUILD + CHECK 自修复回路（熔断：同一 FAIL 3 轮）
"$KPY" $SK/build_board.py      --design design.json --outdir dist
"$KPY" $SK/build_schematic.py  --design design.json --outdir dist
"$KPY" $SK/run_checks.py --board dist/X.kicad_pcb \
       --schematic dist/X.kicad_sch --design design.json \
       --out dist/check_report.json --md dist/check_report.md
#   退出码 1 → 读报告修 design.json → 回到上一步

# 4. EXPORT + OUT + VISUAL
"$KPY" $SK/export_mfg.py --board dist/X.kicad_pcb --outdir dist/mfg \
       --zip --step --order-readme --order-params '{"layers":2,...}'
"$KPY" $SK/verify_output.py --board dist/X.kicad_pcb --mfg dist/mfg --design design.json
"$KPY" $SK/elec_review.py --board dist/X.kicad_pcb --design design.json \
       --report dist/elec_review.json --md dist/elec_review.md   # 电气审查（v5.1）
python $SK/visual_review.py --board dist/X.kicad_pcb --outdir dist/review
#   → AI 逐张读 dist/review/*.png（V 层）

# 5. F 层：汇总两份门禁 JSON + 视觉结论 → 终审报告 → 治理归档 → 交付
```

---

## 5b. Freerouting 自动布线工作流（v5.2 新增，核心路由方案）

```python
# === ROUTE 阶段：Freerouting 工业级自动布线 ===
import pcbnew, subprocess, os

# 0. 前置条件：BUILD 阶段已完成（板上有封装+zone+网络），清除旧走线
board = pcbnew.LoadBoard(board_path)

# 1. KiCad → Specctra DSN 导出
dsn_path = os.path.join(workdir, "board.dsn")
pcbnew.ExportSpecctraDSN(board, dsn_path)

# 2. Freerouting 2.2.4 批处理
ses_path = os.path.join(workdir, "board.ses")
freerouting_jar = "path/to/freerouting-2.2.4.jar"
subprocess.run([
    "java", "-jar", freerouting_jar,
    "-de", dsn_path,       # 输入 DSN
    "-do", ses_path,       # 输出 SES
    "--gui.enabled=false"  # 无界面批处理
], check=True, timeout=300)

# 3. SES 导回 KiCad
pcbnew.ImportSpecctraSES(board, ses_path)

# 4. 重铺铜 + 保存
from pcbnew import ZONE_FILLER
zf = ZONE_FILLER(board)
zf.Fill(board.Zones())
board.Save(board_path)

# 5. DRC 检查
# kicad-cli pcb drc ...
```

**Freerouting 常见问题处理**：
| 问题 | 处理方式 |
|---|---|
| 首轮残留 1-3 条飞线 | `finish_gaps.py` 或手术式局部补线 |
| 相邻引脚缠绕短路 | 移除冲突区域走线段 → 局部补线（不重布整网） |
| 密集区找不到路径 | 微扩板宽 1-2mm 重新 Freerouting（板尺寸弹性） |
| 对已布线板"续跑" | **禁止**：Freerouting 续跑会让结果变差，必须清空重新布线 |

## 6. 实战踩坑库（v5.0~v5.2 新增，全部血泪实测）

| # | 坑 | 解法 |
|---|---|---|
| 15 | 走线端点手填坐标 → 旋转后脱焊盘/短路 | `{"pad":"REF.N"}` 吸附（build_board._resolve_point） |
| 16 | 焊盘不赋网 → DRC 把同网接触报 shorting | `nets[].pads` 显式赋网（build_board.assign_pad_nets） |
| 17 | KiCad 10 默认网络类间距 0.2mm 误杀 0.15 设计 | `m_NetSettings.GetDefaultNetclass().SetClearance()`，且**先写 pro 模板再 Save** |
| 18 | 元件 bbox 用 GetBoundingBox → 文本飘远误报边距 | 用焊盘 bbox（run_checks._fp_pads_bbox） |
| 19 | 铺铜画了矩形 SHAPE → 不是铜 | 真 ZONE + ZONE_FILLER；DRC `--refill-zones --save-board` 固化 |
| 20 | via.GetWidth() 无参 / zone.GetFilledPolysList 无守卫 → KiCad assert 崩 | 带层参 / 先 HasFilledPolysForLayer |
| 21 | PinHeader 焊盘排不居中（pad1 在原点） | 布局前**实测封装焊盘坐标**（probe 脚本打印）再定元件原点 |
| 22 | 0603 旋转后 pad1/pad2 上下易搞反 | 同 #21，实测为准；网络映射按实测写 |
| 23 | PTH 排针焊盘 Ø1.7 间距 2.54 → 行间垂直走线必碰邻盘 | 底层走线先到 y=-6.5 再**沿焊盘自身中轴**进入 |
| 24 | 丝印文本 bbox 比字高大 ~1.7 倍 | 丝印-焊盘间距按 bbox 实测留 ≥0.3mm（L-SLK-02 实测兜底） |
| 25 | GH/Molex 类连接器带 MP 机械焊盘 → 禁布区/间距误判 | 禁布区按**焊盘中心测距**且 circle 优先于矩形 |
| 26 | `--no-protel-ext` 后全是 .gbr | 输出检查按层名子串匹配（verify_output.O-01） |
| 27 | 丝印标签直接放焊盘上方必压盘 | 放焊盘排外侧或板空区；放不下的用针号+图例 |
| **28** | **脚本手写坐标布线：26 轮迭代无法突破 DRC~140**（18×22mm/37 器件） | **放弃手写方案，改用工业级 Freerouting 2.2.4 DSN/SES 批处理** |
| **29** | **QFN20/SOP16 多封装芯片的引脚号取错列**（CH32V003 有 4 种封装，数据手册合并表有多列）| **逐引脚核对数据手册该封装列**，不可信任单一数字；用 WebSearch 独立源交叉验证 |
| **30** | **原理图标签 100% 错位**（build_schematic 按 nets 出现顺序摆放而非按引脚号查表）| **重写标签生成逻辑**：从符号库提取精确引脚坐标公式，删旧标、按 design.json 权威网络表重新生成 |
| **31** | **Freerouting 自身也会产生短路**（U3 相邻引脚 0.65mm 间距处 9V/NRSS 缠绕）| **不能盲目信任任何单一工具输出**，必须过 DRC 复核；发现后手术式修复（只移除冲突区走线段+局部补线，不重布整网）|
| **32** | **对已布线板"续跑"Freerouting 越修越差** | 必须从空白重新布线（`--de/--do` 全新会话） |
| **33** | **密集板上对单网"重新布线"极易找不到路径** | 不重布整网；先精确定位问题区域，只移除该区走线，再局部补线（手术式修复） |
| **34** | **板尺寸微调可换取布线完全收敛**（18mm→19mm→20mm，Freerouting 残留飞线 7→3→1）| 若 Freerouting 首轮残留 ≤3 条，提案微扩板宽 1-2mm 给用户确认 |

---

## 7. 与治理体系对接（宪法 §14/§15）

- L3 任务映射：SPEC(design.json 冻结) → BUILD → CHECK → FIX(回路) → EXPORT → OUT → VISUAL → FINAL，每个对应 tasks/task_*.md；
- 门禁通过 = 状态可转 R；用户确认 = L；
- 熔断/豁免/工艺偏差 → decisions.log；
- `context/design/design.json` 是唯一设计事实源，修改必须走版本（v1, v2...）并留 changelog。

## 8. 终止标志（全部满足才算 COMPLETED）

- [ ] E/I/S/L/R/D 门禁：run_checks.py 退出码 0（APPROVED 或 CONDITIONAL+用户签豁免）
- [ ] O 门禁：verify_output.py 退出码 0
- [ ] ELEC 门禁：elec_review.py 退出码 0（连通性/引脚映射/回流路径等 8 项实测）
- [ ] V 门禁：AI 逐张看图无 P1 问题
- [ ] F 门禁：终审报告生成（含 MANUAL 项结论）、PRD ✅ 清单映射实证、治理文件已更新

---

## 8b. 丝印安全放置协议（v5.3 新增）

1. **采集焊盘 BBox**：所有焊盘 `GetBoundingBox()` + 0.2mm 安全边距
2. **预计算文本尺寸**：`silk_placer.py` 内置常见文本在不同字号的实测 BBox
3. **网格搜索安全位**：0.5mm 步进，距板边 ≥0.3mm
4. **字号自动降级**：优先 0.8mm（JLC 建议）→ 无安全位则 0.6mm（JLC 制造极限）
5. **放置验证**：放置后立即跑 DRC 确认 L-SLK-02 PASS

**层序标准（KiCad 10）**：
```
Board → F.Cu(0) → F.Mask(1) → F.SilkS(5)
丝印是最外层（物理上印在阻焊绿油之上）
```

**KiCad 2D 渲染可能显示丝印"在铜下方"**——这是渲染层序问题，非制造层序。Gerber 中各层独立，PCB 厂按标准工艺处理。

## 9. 修订记录

| 版本 | 日期 | 主要变更 |
|---|---|---|
| v1.0~v4.1 | 2026-07-07~10 | DSL 阶段化；KiCad 主路径（见 SKILL_v4.5_backup.md） |
| v4.5 | 2026-07-11 | 199 项清单（后被证实含大量假 PASS） |
| **v5.0** | **2026-07-20** | **真实工具链验证（kicad-cli DRC/ERC/render + pcbnew 实测）；9 层检查点体系；design.json 单一事实源 + 焊盘吸附 + 焊盘赋网；自修复回路 + 熔断；CS5552 v7 实战 DRC 129→0 全闭环 APPROVED** |
| **v5.1** | **2026-07-20** | **新增 ELEC 电气审查层（elec_review.py）：BFS 连通性核对/引脚功能映射/去耦/端接/IPC-2141 阻抗/回流缝隙实测/压降/ngspice 引擎；skill 注册为系统级** |
| **v5.2** | **2026-07-23** | **重大升级（CS5552_WCD_V4.1 26轮迭代实战驱动）：① Freerouting 工业级自动布线替代手写路由（DSN/SES 批处理，首轮即达 DRC 0）；② 10+1 层检查点（新增 JLC 嘉立创层）；③ router_ortho.py（正交引擎 fallback）+ export_jlcpcb.py（两级打样包）；④ 板尺寸弹性策略；⑤ 引脚映射逐列核对协议；⑥ 原理图标签重建协议；⑦ 7 条新踩坑录（#28~#34）** |

**配套模板仓库**：`d:\000_VSCode\000_Rule_setup`
**实战验证**：CS5552_WCD_V4.1（20×22mm 4 层板，0 短路/0 间距/0 交叉/0 未布线，嘉立创 Tier1 包就绪）
