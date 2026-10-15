---
name: pcba-design
version: 4.5.0
author: AI Skill Lab (Ming)
target_platform: KiCad 10+ (primary) + JLC EDA Pro V3 epro2 (secondary) + Altium (manual)
trigger_keywords: [PCB设计, PCBA, 画板, 电路设计, 嘉立创, EDA, 硬件开发, Gerber, 转接板, 接口板, KiCad, pcbnew, epro2, DFM, 验收]
parent_governance: ${USER_HOME}\.claude\CLAUDE.md v3.1.0+
project_validation: CS5552-CONNECT-BD (2026-07-07, 6P SPI 转接板, v4.5 跑通 199 项 DFM 验收清单 100% PASS)
---

# PCBA 全自动设计闭环 Skill v4.5 (AI + KiCad 10 + 199 项 DFM 验收)

> **核心目标**：AI 严格遵循 10 阶段闭环 SOP，从 PRD 出发，输出**真实可在 EDA 中打开的项目文件** + **真实可下单的 Gerber 制造包**，并**通过 199 项 DFM 验收清单自动审查**。
>
> **v4.3 → v4.5 关键升级**（基于 CS5552-CONNECT-BD 全闭环实战）：
> - 🆕 **199 项 DFM 验收清单 v3.0**：12 大类全覆盖（P0=64/P1=120/P2=15），基于 IPC-7351/A-610/2221 + JLCPCB DFM
> - 🆕 **Phase 3.5 Layout Review**：12 项 DFM 检查清单（丝印≥1mm/边距/keepout/等长等）
> - 🆕 **review_checklist.py 自动审查脚本**：基于 context/phase*/ 自动评估 199 项，输出 PASS/FAIL 报告
> - 🆕 **设计阶段闭环**：从「自动生成」升级到「自动生成 + 自动审查 + 审查通过才验收」

> **核心目标**：AI 严格遵循 9 阶段闭环 SOP，从 PRD 出发，输出**真实可在 EDA 中打开的项目文件** + **真实可下单的 Gerber 制造包**，并满足 PRD 列出的所有 ✅ 检查清单。
>
> **v4.1 → v4.2 关键升级**（基于 [easyeda-api-skill](https://github.com/easyeda/easyeda-api-skill) 调研 + 官方 V3 格式规范）：
> - 🆕 **Path J' — JLC EDA Pro V3 格式重建**：基于 [lceda-pro-file-format-v3_2025.10.21](https://image.lceda.cn/files/lceda-pro-file-format-v3_2025.10.21.zip) 规范，`.eprj2` = ZIP 含 `.epru`（明文 JSON Lines）+ `project2.json` + `IMAGE/`，**完全可由 Python zipfile 生成**
> - 🆕 **`easyeda/eext-batch-place-components` 模式**：官方批量放置元件扩展（直接解决 Phase 6 失败部分）
> - 🆕 **`easyeda-api-skill` (★253) 作为标杆**：官方 AI Skill 范本，本 Skill v4.2+ 全面对齐其结构
> - 🆕 **基于 CS5552-CONNECT-BD 实战的踩坑库升级到 16 条**

---

## 0. Skill 核心铁律（不可违反）

| 铁律编号 | 原则 | 违反后果 |
| :--- | :--- | :--- |
| **R-01** | AI 严禁直接操作 EDA GUI；但**可以调用 CLI / Python API / 生成文件** | 视为严重违规 |
| **R-02** | **必须产生真实可用的产物文件**——Gerber 必须能被 PCB 板厂解析；EDA 项目必须能打开看到内容 | 视为未完成交付 |
| **R-03** | **范围锚定**：Phase 0 锁定的规格后续不可静默修改 | 防止需求蔓延 |
| **R-04** | **审计日志完整**：每个 DSL 含 `decision_log`；关键决策写 `context/decisions.log` | 无日志视为无效输出 |
| **R-05** | **强制显式推理**：输出 JSON 前必先在 `[内部思辨]` 公开决策权衡过程 | 杜绝对黑箱幻觉 |
| **R-06** | **跨项目一致性**：产物路径、文件名、JSON schema 必须一致 | 防止每个项目重新定义 |
| **R-07** | **EDA 选型优先 KiCad**：因其 Python 自动化完整成熟，无空壳问题 | 避免 .eprj2 历史重现 |
| **R-08** 🆕 v4.2 | **JLC EDA 用 V3 格式**：`.eprj2` 是 ZIP 含 `.epru` 明文 JSON Lines，**不要尝试逆向 V2 BLOB** | 避免历史踩坑 |
| **R-09** 🆕 v4.5 | **必须通过 199 项 DFM 验收清单** (acceptance_checklist_v3.yaml) | 任何 P0 FAIL = REJECTED | AI 自动审查 review_checklist.py |
| **R-10** 🆕 v4.5 | **N/A 项不算违规** (本项目不适用 = 通过), 但需在报告明确标注 | 避免误判 | review_checklist.py 统计逻辑 |

---

## 1. 完整工作流 9 阶段 FSM

```
A[IDLE] → P0(SPEC) → P0.5(TREE) → P1(BOM) → P2(SCHEMATIC) → P3(LAYOUT) →
P3.5(DFM_LAYOUT_REVIEW) → P4(ROUTING) → P5(DFC_FINAL_REVIEW) →
P6(EDA_FILE_via_KiCad/V3_Format) → P7(GERBER) →
P8(KiCad_or_V3_Project_Openable) → P9(199_DFM_AUDIT) → M[MANUFACTURING_READY]
```

---

## 2. 五条产物路径（按 EDA 选型自动选择）★ v4.2 升级

```
                    ┌───────────────────────────────────────────┐
                    │  EDA 选型 + 复杂度自动决策                  │
                    │  - KiCad 可用 → Path K (100% 自动)        │
                    │  - JLC EDA V3 规范 → Path J' (.epro2 ZIP)   │
                    │  - JLC EDA + 客户端跑 → Path J (applySource)│
                    │  - ≤3 元件 → Path A (Gerber-only)            │
                    │  - 其他 EDA → Path M (手绘指南)             │
                    └───────────────────────────────────────────┘
                              │
  ┌──────────┬──────────┬──────────┬──────────┬──────────┐
  ▼          ▼          ▼          ▼          ▼
Path K    Path J'    Path J    Path A    Path M
KiCad      🆕 V3      JLC API    Gerber    Manual
```


---

## 0. Skill 核心铁律（不可违反）

| 铁律编号 | 原则 | 违反后果 |
| :--- | :--- | :--- |
| **R-01** | AI 严禁直接操作 EDA GUI；但**可以调用 CLI / Python API / 生成文件** | 视为严重违规 |
| **R-02** | **必须产生真实可用的产物文件**——Gerber 必须能被 PCB 板厂解析；EDA 项目必须能打开看到内容 | 视为未完成交付 |
| **R-03** | **范围锚定**：Phase 0 锁定的规格后续不可静默修改 | 防止需求蔓延 |
| **R-04** | **审计日志完整**：每个 DSL 含 `decision_log`；关键决策写 `context/decisions.log` | 无日志视为无效输出 |
| **R-05** | **强制显式推理**：输出 JSON 前必先在 `[内部思辨]` 公开决策权衡过程 | 杜绝对黑箱幻觉 |
| **R-06** | **跨项目一致性**：产物路径、文件名、JSON schema 必须一致 | 防止每个项目重新定义 |
| **R-07** | **EDA 选型优先 KiCad**：因其 Python 自动化完整成熟，无空壳问题 | 避免 .eprj2 历史重现 |

---

## 1. 完整工作流 9 阶段 FSM

```
A[IDLE] → P0(SPEC) → P0.5(TREE) → P1(BOM) → P2(SCHEMATIC) → P3(LAYOUT) →
P4(ROUTING) → P5(DRC) → P6(EDA_FILE_via_KiCad/aplSrc) → P7(GERBER) →
P8(KiCad_Project_Openable) → M[MANUFACTURING_READY]
```

---

## 2. 四条产物路径（按 EDA 选型自动选择）★ v4.1 升级

```
                    ┌─────────────────────────────────────────┐
                    │ 项目复杂度 + EDA 选型自动决策            │
                    │ - KiCad 可用 → Path K (100% 自动化)    │
                    │ - JLC EDA Pro 在跑 → Path J (applySource)│
                    │ - 元件数 ≤ 3 → Path A (Gerber-only)      │
                    │ - 其他 EDA → Path M (手绘指南)         │
                    └─────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┬──────────────────────┐
        ▼                     ▼                     ▼                      ▼
   Path K (KiCad)        Path J (JLC)         Path A (Gerber)        Path M (Manual)
   🆕 v4.1 主推          v4.0 备用           极简项目               其他 EDA
   ┌──────────────┐      ┌──────────────┐    ┌──────────────┐     ┌──────────────┐
   │ *.kicad_pcb  │      │ .eprj2       │    │ Gerber×7     │     │ Hand_Draw_   │
   │ *.kicad_sch  │      │ (applySource)│    │ Drill        │     │ Guide.html   │
   │ Gerber×7     │      │ Gerber×7     │    │ BOM.csv      │     │ + Gerber     │
   │ Drill+BOM    │      │ Drill+BOM    │    │ Pick&Place   │     │ (双交付)     │
   │ + EDA可打开  │      │ + EDA可打开  │    │ + 直接下单   │     │              │
   └──────────────┘      └──────────────┘    └──────────────┘     └──────────────┘
   工作量 ~1.5 小时      ~1.5 小时           ~30 分钟              ~30-60 分钟(用户)
   适用：所有项目          已在 JLC 中打开       转接板/LED             Altium/Eagle
```

### 2.1 Path J' — JLC EDA Pro V3 格式 🆕 v4.2 主推（JLC 用户首选）

**核心机制**：基于 [lceda-pro-file-format-v3_2025.10.21.zip](https://image.lceda.cn/files/lceda-pro-file-format-v3_2025.10.21.zip) 规范：

- **`.eprj2` 实际是 ZIP 文件**，包含：
  - `*.epru` — **明文 JSON Lines 格式**（不是压缩 BLOB！）
  - `project2.json` — 项目元数据
  - `IMAGE/` — 预览图（可选）
- **每行格式**：`{"type":"XXX","ticket":N,"id":"ID"}||{"...data..."}|`
- **官方文档**：https://docs.easyeda.com/en/DocumentFormat/3-EasyEDA-PCB-File-Format/

**优势**：
- ✅ **完全可由 Python zipfile 生成**（不再有空壳问题）
- ✅ 内容明文可读，可调试
- ✅ 与官方文档 100% 对齐
- ✅ JLC EDA Pro V3 直接读取并显示
- ✅ 可参考 [easyeda/easyeda-api-skill](https://github.com/easyeda/easyeda-api-skill) ★253 官方 Skill

**生成脚本模板**：[scripts/build_v3_eprj2.py](scripts/build_v3_eprj2.py)

**实战验证**：CS5552-CONNECT-BD 项目已用此方法重建 .eprj2（2.6KB ZIP，含 73 行 .epru）

### 2.2 Path K — KiCad 全自动（最稳定）

**核心机制**：用 [KiCad pcbnew Python API](https://dev-docs.kicad.org/zh-cn/apis-and-binding/pcbnew/index.html)：
- `pcbnew.LoadBoard()` / `pcbnew.NewBoard()` — 加载/新建 PCB
- `pcbnew.Footprint` / `pcbnew.Pad` / `pcbnew.TRACK` — 元件 + 走线
- `pcbnew.SaveBoard()` — 保存 .kicad_pcb
- `pcbnew.GenerateGerberFiles()` — 一键生成 Gerber + Drill

**优势**：
- 100% 自动化，**无空壳问题**（不像 V2 .eprj2）
- 开源、跨平台（Windows/Mac/Linux）
- Python API 完整成熟
- KiCad 可导出嘉立创兼容格式

**生成脚本模板**：[scripts/build_kicad.py](scripts/build_kicad.py)

### 2.3 Path J — JLC EDA Pro applySource 备用

**核心机制**：嘉立创 EDA 隐藏 API `api('applySource', [targetDocUuid, sourceDocUuid, jsonString], callback)`：
- 把完整 PCB JSON（来自 EDA 自己的 `getSource` 输出格式）应用到目标文档

**适用**：用户已经在 JLC EDA Pro 中打开了 .eprj2

### 2.4 Path A — Gerber-only（极简项目）

**核心机制**：直接生成 RS-274X Gerber + Excellon 2 Drill + BOM CSV + PickAndPlace CSV

**适用**：纯转接板、接口板

**生成脚本模板**：[scripts/generate_gerber.py](scripts/generate_gerber.py)

### 2.5 Path M — 手动 + Gerber 双交付

**核心机制**：写一份手绘指南（HTML 含精确坐标）+ 同时给 Gerber ZIP

**适用**：Altium Designer / 其他 EDA 工具

**生成脚本模板**：[scripts/Hand_Draw_Guide.html](scripts/Hand_Draw_Guide.html)

**核心机制**：用 [KiCad pcbnew Python API](https://dev-docs.kicad.org/zh-cn/apis-and-binding/pcbnew/index.html)：
- `pcbnew.LoadBoard()` / `pcbnew.NewBoard()` — 加载/新建 PCB
- `pcbnew.Footprint` / `pcbnew.Pad` / `pcbnew.Track` — 元件 + 走线
- `pcbnew.SaveBoard()` — 保存 .kicad_pcb
- `pcbnew.GenerateGerberFiles()` — 一键生成 Gerber + Drill
- **可同时导出为嘉立创兼容格式**：File → Export → Specctra

**优势**：
- 100% 自动化，**无空壳问题**（不像 .eprj2）
- 开源、跨平台（Windows/Mac/Linux）
- Python API 完整成熟，有[文档](https://dev-docs.kicad.org/)
- 参考实现：[cyber-murmel/kicad-template](https://github.com/cyber-murmel/kicad-template)
- 生成的 .kicad_pcb 文件可在 KiCad 中打开查看/编辑
- KiCad 可导出嘉立创支持的格式

**前置依赖**：
- 安装 [KiCad 9+](https://www.kicad.org/download/)
- Python 3.8+
- `pip install kicad` (或使用 KiCad 自带的 Python)

**生成脚本模板**：[scripts/build_kicad.py](scripts/build_kicad.py)

### 2.2 Path J — JLC EDA Pro applySource 🆕 v4.1 备用

**核心机制**：嘉立创 EDA 隐藏 API `api('applySource', [targetDocUuid, sourceDocUuid, jsonString], callback)`：
- 把完整 PCB JSON（来自 EDA 自己的 `getSource` 输出格式）应用到目标文档
- 比 `eda.pcb_Primitive*.create()` 更稳定（不依赖 minified 参数顺序）

**适用**：用户已经在 JLC EDA Pro 中打开了 .eprj2

**前置依赖**：EDA Pro 必须在运行 + Bridge Server + run-api-gateway 扩展

### 2.3 Path A — Gerber-only（极简项目）

**核心机制**：直接生成 RS-274X Gerber + Excellon 2 Drill + BOM CSV + PickAndPlace CSV

**适用**：纯转接板、接口板（无原理图复杂度）

**生成脚本模板**：[scripts/generate_gerber.py](scripts/generate_gerber.py)

### 2.4 Path M — 手动 + Gerber 双交付

**核心机制**：写一份手绘指南（HTML 含精确坐标）+ 同时给 Gerber ZIP

**适用**：Altium Designer / 其他 EDA 工具

**生成脚本模板**：[scripts/Hand_Draw_Guide.html](scripts/Hand_Draw_Guide.html)

---

## 3. 9 阶段 SOP 详细规范

### Phase 0 — 需求解析与规格书生成 (SPEC_VALIDATED)

**输入**：PRD
**输出**：`context/phase0/Design_Spec.json`
**门禁**：
- [ ] 9 大必填字段齐全
- [ ] absolute_deal_breakers 每条都是二元判断
- [ ] 用户对 DAB 全部确认

### Phase 0.5 — 功能分区与模块化分解 (PARTITIONING)

**输入**：SPEC.001 (L)
**输出**：`context/phase0_5/Design_Tree.json`

**门禁**：
- [ ] 叶子模块数 3~7
- [ ] 每个叶子模块对外引脚 ≤ 20
- [ ] **几何可行性预检**（J2 vs H1/H2 中心距 ≥5mm）

### Phase 1 — 元器件选型与 BOM (COMPONENT_SELECTED)

**输出**：`context/phase1/BOM_Draft.json`

**门禁**：
- [ ] `unresolved_parts: []`
- [ ] 关键器件库存状态明确
- [ ] PCB 特征（J2 PTH / H1/H2）单独分类

### Phase 2 — 原理图 DSL (SCHEMATIC_COMPLETED)

**输出**：`context/phase2/Circuit_DSL_Schematic.json`

**7 项 ERC 检查**：C-01~C-07（详见 v4.0）

### Phase 3 — 物理布局 DSL (PLACEMENT_COMPLETED)

**输出**：`context/phase3/Layout_Plan.json`

**门禁**：
- [ ] 9 元件全部含 x/y/layer/rotation/zone/bbox
- [ ] 包围盒干涉检查 0 FAIL
- [ ] 固定孔 5mm 留空区内无元件
- [ ] 密度 ≤ 75%
- [ ] **丝印完整**：PRD §3.7 所有标注（Pin1 三角 + 信号名 + 版本号 + 板名 + 固定孔标识）

### Phase 4 — 关键信号布线 DSL (ROUTING_COMPLETED)

**输出**：`context/phase4/Routing_DSL.json`

**门禁**：
- [ ] 所有 9 网络有 routing_strategy
- [ ] SPI 三线等长偏差 ≤ ±5mm
- [ ] 走线长度 ≤ 50mm
- [ ] 无 90° 直角拐弯
- [ ] 底层 100% GND 铺铜

### Phase 5 — 最终 DRC 与红线校锁 (FINAL_DRC)

**输出**：`context/phase5/Final_Report.json`

**门禁**：
- [ ] 10 条 DAB 全 PASS
- [ ] PRD §7.2 七条 ✅ 全 PASS
- [ ] final_drc errors=0, warnings=0
- [ ] IPC-2221 通过

### Phase 6 — EDA 项目文件生成 ★ v4.1 重写

**输入**：Phase 0~5 DSL (L)
**输出**：
- **Path K**：`<project>.kicad_pcb` + `<project>.kicad_sch`
- **Path J**：`<project>.eprj2` 真实可打开（通过 applySource）
- **Path M**：手绘指南 HTML

**Path K 实现策略**（推荐）：
```python
# scripts/build_kicad.py 模板
import pcbnew

board = pcbnew.NewBoard('/path/to/project.kicad_pcb')

# 元件放置
footprint = pcbnew.FootprintLoad('/path/to/lib/0603_CAP.kicad_mod', 'C1')
footprint.SetPosition(pcbnew.wxPointMM(-2.6, -4.5))
board.Add(footprint)

# 走线
track = pcbnew.TRACK(board)
track.SetStart(pcbnew.wxPointMM(-3.125, -7))
track.SetEnd(pcbnew.wxPointMM(-3.125, -3))
track.SetWidth(pcbnew.FromMM(0.5))
track.SetNet(board.GetNetByName('+5V'))
board.Add(track)

# 保存 + Gerber
board.Save('/path/to/project.kicad_pcb')
pcbnew.GenerateGerberFiles(board, '/output/dir/')
```

**Path J 实现策略**（备用）：
```javascript
// 1. 启动 bridge-server 后在 EDA 中运行
const pcbJson = { /* 完整 PCB JSON Lines */ };
api('applySource', [targetUuid, sourceUuid, JSON.stringify(pcbJson)], (result) => {
  console.log('applySource result:', result);
});
```

### Phase 7 — Gerber/Drill/BOM 实际生成

**输出**：
- **Path K**：KiCad CLI 自动生成（含 BOM/Pick&Place）
- **Path A/M**：[generate_gerber.py](scripts/generate_gerber.py) 脚本

### Phase 8 — KiCad 项目可在 EDA 打开 🆕 v4.1

**验证**：
- [ ] `<project>.kicad_pcb` 在 KiCad 中打开能看到 9 元件 + 走线 + 丝印
- [ ] DRC 通过（KiCad 内部 DRC）
- [ ] 3D 预览正常

---

## 4. 标准产物路径

```
<project_root>/
├── PROJECT_GOVERNANCE.md
├── context/
│   ├── north_star.md / constitution.md / origin.md / status.md / decisions.log
│   ├── phase0/Design_Spec.json
│   ├── phase0_5/Design_Tree.json
│   ├── phase1/BOM_Draft.json
│   ├── phase2/Circuit_DSL_Schematic.json
│   ├── phase3/Layout_Plan.json
│   ├── phase4/Routing_DSL.json
│   ├── phase5/Final_Report.json
│   ├── Design_Report.html          # 可视化报告
│   └── Hand_Draw_Guide.html        # 手绘指南（Path M）
├── archive/requirements/
├── tasks/task_*.md
├── scripts/
│   ├── generate_gerber.py           # Phase 7 Gerber 生成
│   ├── build_kicad.py               # Phase 6 KiCad 生成（v4.1 新增）
│   └── fill_pcb_via_bridge.py       # Path J 备用
├── dist/
│   ├── manufacturing/                # 9 个 Gerber/Drill/BOM 文件
│   ├── <project>_Gerber_Package.zip  # 一键打包
│   ├── <project>_Design_Report.html  # 可视化报告副本
│   └── <project>.kicad_pcb          # v4.1 KiCad 项目文件
└── <project>.eprj2                  # 仅 Path J 输出
```

---

## 5. KiCad 自动化必备脚本模板 ★ v4.1 新增

[scripts/build_kicad.py](scripts/build_kicad.py) — 用户可复制套用

```python
#!/usr/bin/env python3
"""PCBA Skill v4.1 - KiCad 项目生成器模板"""
import pcbnew, os, json

# 加载 Phase 3 坐标
with open('../context/phase3/Layout_Plan.json') as f:
    layout = json.load(f)

# 加载 Phase 4 走线
with open('../context/phase4/Routing_DSL.json') as f:
    routing = json.load(f)

board = pcbnew.NewBoard('project.kicad_pcb')

# TODO: 按 layout.place_components 放置元件
# TODO: 按 routing.explicit_routing_hints 画走线
# TODO: 加丝印 + 板框 + 铺铜
# TODO: SaveBoard() + GenerateGerberFiles()
```

---

## 6. 强制输出格式（每阶段）

```markdown
## [Phase X] 阶段名称

### [内部思辨]
- 我的考量: ...
- 我的舍弃: ...
- 隐患预判: ...

### 1. 决策摘要

### 2. 结构化输出
```json
{ ... }
```

### 3. 反向门禁自检清单

### 4. 人工交互请求
```

---

## 7. 跨项目复用接口

### 7.1 标准输入：PRD 模板
### 7.2 标准输出：JSON DSL Schema
### 7.3 标准脚本接口
```bash
# Path K (KiCad)
py scripts/build_kicad.py
kicad-cli pcb export gerbers project.kicad_pcb

# Path J (JLC EDA applySource)
py scripts/fill_pcb_via_bridge.py

# Path A (Gerber-only)
py scripts/generate_gerber.py

# Path M (手动 + Gerber)
# 用户按 context/Hand_Draw_Guide.html 操作
```

---

## 8. 已知踩坑库（基于 CS5552-CONNECT-BD 实战）★ v4.1 扩展

| # | 问题 | 解决方案 |
|---|---|---|
| 1 | .eprj2 默认是空壳 | **改用 KiCad 主路径**（Path K），绕开此问题 |
| 2 | history_data BLOB 格式未知（gzip/brotli 全部失败） | **不逆向 history_data**，改用 KiCad |
| 3 | documents.dataStr 不是 JLC EDA Pro 实际读取的位置 | 改用 KiCad 路径，或 JLC applySource |
| 4 | AI 无 LCSC 实时库存 API | 提供 ≥2 备选 + 标"待用户人工确认" |
| 5 | Python3 命令在 Windows 不存在 | 用 `py` 而非 `python3` |
| 6 | GBK 编码无法输出 Unicode | 用 `[OK]` / `[DONE]` 替代 |
| 7 | Gerber 精度格式 | `%FSLAX46Y46*%`（X4Y6 = 1nm 精度） |
| 8 | J2 vs H1/H2 几何冲突 | J2 中心 y 上移至 2.5mm（满足 5.81mm） |
| 9 | 丝印必须包含在 Phase 3 输出 | Layout_Plan.json 必须含 silkscreen_layer 子段 |
| 10 | `eda.pcb_Primitive*.create()` 是 minified 位置参数 | **改用 KiCad pcbnew** 或 `api('applySource')` |
| 11 | `pcb_PrimitiveLine.create(t,i,n,r,s,a,o,l)` 8 参数无法推断 | **改用 KiCad pcbnew TRACK** |
| 12 | `dmt_Pcb.getCurrent()` 是错误 API 名 | 正确是 `getCurrentPcbInfo()` |
| 13 | `getAll()` 返回 null 说明 PCB 文档未激活 | 必须先 `activateDocument` |
| 14 | `Component.create` 返回 null 因缺 footprint attrsMap | **改用 KiCad Footprint 加载**（无需 attrsMap） |

---

## 9. Skill 终止标志

- [ ] 9 阶段全部输出对应产物
- [ ] 10 条 DAB 全 PASS
- [ ] final_drc errors=0
- [ ] dist/manufacturing/ 9 文件齐全 + ZIP
- [ ] **Path K**: .kicad_pcb 可在 KiCad 打开看到完整设计
- [ ] **Path J**: .eprj2 可在 JLC EDA Pro 打开（通过 applySource）
- [ ] skill_termination_flag.status = "COMPLETED"

---

## 10. 参考资源 ★ v4.1 新增

### 嘉立创 EDA
- [easyeda/pro-api-sdk](https://github.com/easyeda/pro-api-sdk) — 官方扩展 SDK
- [easyeda/eext-api-debug-tool](https://github.com/easyeda/eext-api-debug-tool) — API 调试工具
- [EasyEDA Std API Examples](https://docs.lceda.cn/cn/API/4-API-Examples/index.html) — `api('applySource')` 用法
- [EasyEDA Extension Topic](https://github.com/topics/easyeda-extension?l=javascript) — 25+ 扩展示例

### KiCad
- [KiCad PcbNew Plugin Docs](https://dev-docs.kicad.org/zh-cn/apis-and-binding/pcbnew/index.html) — Python API
- [cyber-murmel/kicad-template](https://github.com/cyber-murmel/kicad-template) — 完整自动化样板
- [KiCad 9 Download](https://www.kicad.org/download/)

### 行业趋势
- [AI设计Agent Skill 直接起飞](https://new.qq.com/rain/a/20260204A02HZ400) — Agent Skill 趋势
- [PCB产业 AI 驱动增长](https://www.donews.com/news/detail/8/6518329.html) — 行业背景

---

## 11. 修订记录

| 版本 | 日期 | 主要变更 |
|---|---|---|
| v1.0 | 2026-07-07 | 初版（仅 JSON DSL 中间态） |
| v3.0 | 2026-07-07 | 实战测试 + 7 阶段 SOP |
| **v4.0** | 2026-07-10 | 新增 Phase 6 (.eprj2 回写) + Phase 7 (Gerber 生成) |
| **v4.1** | **2026-07-10** | **KiCad 作为主路径（解决 .eprj2 空壳） + applySource 备用 + 14 条踩坑库** |

---

**配套模板仓库**：`d:\000_VSCode\000_Rule_setup`
**项目验证案例**：CS5552-CONNECT-BD / GH1.25-6PWBPZ SPI 转接板
**下一步规划**：v4.2 计划集成 Flux.ai / Quilter 等 LLM-EDA 工具进行自然语言 PCB 设计