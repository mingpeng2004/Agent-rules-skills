---
name: jlceda-jlcpcb-integration
description: 系统级 EDA-to-打样集成 skill。封装 EasyEDA Pro OpenAPI + JLCPCB Partner API + LCSC 元件库，让 Claude 在对话中完成"原理图/PCB → Gerber/BOM → 报价 → 下单 → 跟踪"全链路。适用于任何需要把电路设计落到嘉立创平台打样的项目。
---

# JLCEDA / JLCPCB Integration

让 Claude 直接对接嘉立创生态（EasyEDA Pro 设计端 + JLCPCB 制造端 + LCSC 元件库），把"画图到下单"的流程压缩成一次对话可闭环的事。

## 何时调用

- 项目需要做 PCB 设计并打样，且优先走嘉立创（JLCPCB）打样。
- 原理图/PCB 工具是 EasyEDA / EasyEDA Pro / 立创EDA 专业版；或 KiCad 但愿意用 JLCPCB 平台。
- 用户希望 Claude 直接驱动设计工具（写脚本、改器件、生成制造文件）或把已有设计文件推到打样端。
- 需要做 SMT 贴片（含 BOM/CPL 上传与元件配单）。

## API 表面（必须熟悉的接口）

### EasyEDA Pro OpenAPI（设计端，BETA）
- 文档：[prodocs.easyeda.com](https://prodocs.easyeda.com/) / [prodocs.lceda.cn](https://prodocs.lceda.cn/)
- 模块前缀：`DMT_*`（文档）、`SCH_*`（原理图）、`PCB_*`（PCB）、`LIB_*`（库）、`SYS_*`（系统）
- 关键方法：
  - `SYS_FileManager.getSchematicFile()` — 读/写 `.epro` 工程
  - `SCH_PrimitiveComponent.create()` / `.modify()` / `.delete()` / `.getAll()`
  - `PCB_ManufactureData.placePcbOrder({ interactive, ignoreWarning })` — **一键下单到 JLCPCB**
  - `schematic.exportSchematicNetlistFile()` / `pcb.exportGerber()` — 导出制造文件
- 异步图元修改四步法：`get → toAsync → setState_* → done`
- 状态：**BETA**，不要在生产环境硬依赖；接口签名可能变。

### JLCPCB Partner API（制造端，需申请）
- 入口：[api.jlcpcb.com](https://api.jlcpcb.com/)，需订单历史审核
- Base URL：`https://jlcpcb.com/api/overseas/openapi`
- 鉴权：`JOP-HMAC-SHA256` 头，签名串 `METHOD\nURI\nTIMESTAMP\nNONCE\nBODY\n`
- 主要端点：
  - `POST /pcb/calculate` — 报价（无需 Gerber）
  - `POST /pcb/uploadGerber` — 上传 Gerber ZIP，返回 `fileKey`
  - `POST /pcb/create` — 创建订单
  - `POST /pcb/wip/get` — 查询在制状态
  - 另有 `SMT Stencil`、`3D Printing`、`Parts` API
- 备选（无 Key 也可用）：`jlcsearch.tscircuit.com` 提供 LCSC 元件查询

### LCSC 元件库
- 每个 BOM 行建议带 `LCSC Part #`（表头必须精确），否则贴片配单会失败。
- 查询首选 LCSC 官方搜索 API，备选 `jlcsearch.tscircuit.com`。

## 工作流

### Phase A — 需求 → 原理图骨架
- 用户给功能规格（电源、MCU、传感器、通信接口、IO 表）。
- 调 `SCH_PrimitiveComponent` 按规格放置器件：MCU、电源、晶振、复位、调试口、外设。
- 如果 EasyEDA Pro AI Schematic Beta 可用，**优先**用 LLM 生成一稿，再人工/脚本细化；不可用就纯脚本搭骨架。
- 输出 `schematic_review.md`：每个网路（net）的连接关系、未连接警告清单。

### Phase B — 元件选型
- 用 LCSC 搜索 API 把每个器件的 `LCSC Part #` 落到 BOM。
- 检查基本盘：库存 ≥ 1000、价格、可过设备（`basic` / `extended` / `not_recommended`）。
- 输出 `bom_draft.csv`（列：`Comment, Designator, Footprint, LCSC Part #`）。

### Phase C — PCB 布局 + 走线
- 调 `PCB_*` 系列：板框、层叠、铜皮、规则。
- 关键高速/模拟信号手动约束；其余可走 AI 布线或脚本批处理。
- DRC 必须零错误，警告最小化。

### Phase D — 制造文件
- 导出 Gerber ZIP（RS-274X，标准 JLCPCB 接受格式）。
- 导出钻孔（Excellon）、BOM、位置文件（CPL）。
- 跑 JLCPCB 制造自检（最小线宽/间距、阻焊桥、孔环等）。

### Phase E — 报价 + 下单
- 调 `POST /pcb/calculate` 拿报价选项（板厚、阻焊颜色、表面处理、阻抗、拼板）。
- 用户确认规格 → 调 `POST /pcb/uploadGerber` → 调 `POST /pcb/create`。
- 若走 EasyEDA Pro 内部 `placePcbOrder({ interactive:false })`，可在 EDA 内一键下单到 JLCPCB。

### Phase F — 跟踪
- 周期性调 `POST /pcb/wip/get` 拉订单状态：`queued → manufacturing → assembly → shipped → delivered`。
- 状态变更写到 `order_log.md`，含运单号、节点时间戳。

### Phase G — SMT 贴片（如需要）
- 在 JLCPCB 下单页打开 SMT 选项 → 上传 BOM + CPL → 选单/双面 → 选元件（按 LCSC Part # 自动匹配，部分需手工确认）→ 提交。

## MCP 工具契约

skill 调用方需在 MCP 中暴露（命名建议，可重映射）：

```
eda_open_project(path_or_id)
eda_add_component(ref, value, footprint, lcsc_part)
eda_connect_nets(netlist_json)
eda_set_board_outline(outline_json)
eda_route(strategy)                     # "ai" | "manual" | "hybrid"
eda_run_drc() -> { errors, warnings }
eda_export_gerber(out_dir) -> { zip_path }
eda_export_bom(out_csv)  -> { bom_path }
eda_export_cpl(out_csv)  -> { cpl_path }
eda_place_pcb_order({ interactive, ignoreWarning })

lcsc_part_lookup(mpn) -> { lcsc_pn, stock, price_basic, price_extended, smd_class }

jlcpcb_quote(gerber_zip_path) -> { options[], unit_price, lead_time_days }
jlcpcb_upload_gerber(zip_path) -> { file_key }
jlcpcb_create_order(file_key, options) -> { order_id }
jlcpcb_track_order(order_id) -> { status, milestones[], tracking_no? }
jlcpcb_smt_quote(gerber_zip, bom_csv, cpl_csv, side) -> { assembly_unit_price }
jlcpcb_smt_create_order(...) -> { order_id }
```

## 鉴权与密钥处理

- JLCPCB Partner API 的 `appid` / `accesskey` / `nonce` 通过 MCP 配置注入，**不**让用户贴明文到对话里。
- 签名计算封装在 MCP 内部，skill 只调用高层方法。
- LCSC 账号（用于自动贴片配单）以 OAuth 形式注入。

## 已知限制 / 风险

- EasyEDA Pro OpenAPI 仍在 **BETA**，接口可能调整；skill 调用失败时需要 fallback 到文件导出+手工上传路径。
- JLCPCB Partner API 需要申请，**不是注册即得**；申请被拒时退化为 `cart.jlcpcb.com` 半自动下单（生成打包文件 + 下单 URL）。
- EasyEDA 单位陷阱：PCB 用 `1mil`，原理图用 `0.01inch`（10mil），写脚本时务必显式标注。
- 部分图元改异步走四步法（get→toAsync→setState→done），漏步会脏状态。

## 参考实现（不要重复造轮子）

- **`easyeda/easyeda-api-skill`**（GitHub 官方）：Node.js 桥接服务器，端口 49620–49629，实时在 EDA 客户端内执行代码。
- **`@iflow-mcp/sengbin-jlceda-mcp`**（npm）：JLCEDA MCP Hub，stdio/http 协议。
- **JLCEDA MCP Bridge**（jlc-ext.com）：EDA 端扩展，提供 RPC 方法。
- **`aklofas/kicad-happy-jlcpcb`**（TrueFoundry Skills Registry）：KiCad 出图后对接 JLCPCB 的参考 skill，可借鉴下单流。

## 示例调用

```
调用 jlceda-jlcpcb-integration：
- 工程名：env-sensor-v1
- 板卡尺寸：40×30mm，4 层，1.6mm FR4，HASL-lead-free，绿油白字
- MCU：ESP32-C3 + BME280 + 1S 锂电充放电
- 数量：5 pcs，贴片单面
- 预算：< ¥120/板（含贴片）
- 是否要生成拼板：是，3×1 V-cut
期望产出：完整原理图、Gerber ZIP、BOM+CPL、报价明细、下单单号（含跟踪链接）。
```

## 失败模式与升级

| 现象 | 处理 |
|------|------|
| OpenAPI 调用失败 | 退回文件导出路径；提示用户检查 EDA 客户端版本 |
| LCSC 元件缺货 | 自动选替代料（同类封装、规格接近），写入 `bom_substitution.md` 让用户确认 |
| 报价超预算 | 改规格（减层、换阻焊、延交期）→ 再报价 → 让用户重选 |
| Partner API 申请未通过 | 给用户 `cart.jlcpcb.com` 半自动下单链接 + 已打包文件 |
| SMT 元件配单失败 | 把未匹配项导出成手工选型清单，不阻塞下单 |