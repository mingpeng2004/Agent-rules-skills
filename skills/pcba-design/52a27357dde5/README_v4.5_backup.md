# PCBA Skill v4.1 — 跨项目使用指南

> **位置**: `d:\000_VSCode\000_Rule_setup\skills\pcba-design\`
> **首次实战验证**: CS5552-CONNECT-BD / GH1.25-6PWBPZ SPI 转接板 (2026-07-07)
> **核心改进 v4.0 → v4.1**: 引入 [KiCad](https://www.kicad.org/) 主路径解决 .eprj2 空壳问题

---

## 📦 包含文件

| 文件 | 作用 |
|---|---|
| [SKILL.md](SKILL.md) | ⭐ 主文档：9 阶段 SOP + 四条产物路径 |
| [build_kicad.py](build_kicad.py) | 🆕 KiCad 项目生成器（Path K 推荐） |
| [generate_gerber.py](generate_gerber.py) | Gerber-only 路径（Path A 简单项目） |
| [Hand_Draw_Guide.html](Hand_Draw_Guide.html) | 手绘指南模板（Path M 其他 EDA） |
| [README.md](README.md) | 本文件 |

---

## 🚀 4 条产物路径快速选择

| 场景 | 推荐路径 | 自动化程度 |
|---|---|---|
| **默认（所有项目）** | **Path K (KiCad)** | 🟢 100% 自动 |
| 用户已在 JLC EDA Pro 中打开 .eprj2 | Path J (applySource) | 🟡 半自动（需用户在 EDA 中） |
| 纯转接板 / LED 板（≤3 元件） | Path A (Gerber-only) | 🟢 100% 自动 |
| Altium / Eagle 等其他 EDA | Path M (手绘) | 🔴 手动 30-60 分钟 |

---

## 🎯 路径 K（KiCad 主路径）— 推荐

### 一次性环境配置

```bash
# 1. 安装 KiCad 9+
# Windows: 从 https://www.kicad.org/download/ 下载安装
# 验证安装:
"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe" --version

# 2. 安装 Python 绑定 (KiCad 9 自带)
py -c "import pcbnew; print('OK')"
```

### 在新 PCB 项目中 3 步使用

```bash
# Step 1: 复制 Skill 资产
cd /d/002_Another_PCB_Project
cp /d/000_VSCode/000_Rule_setup/skills/pcba-design/SKILL.md ./
cp /d/000_VSCode/000_Rule_setup/skills/pcba-design/build_kicad.py ./scripts/

# Step 2: 启动 Claude AI 会话
# 「请使用 d:\000_VSCode\000_Rule_setup\skills\pcba-design\SKILL.md 设计我的项目。PRD 如下: <你的 PRD>」

# Step 3: AI 跑完 8 阶段后, 你运行
py scripts/build_kicad.py
# 输出: dist/<project>.kicad_pcb + dist/manufacturing/*.gbr
```

### 填写 build_kicad.py 数据

AI 会把 Phase 3-5 DSL 转换成 build_kicad.py 顶部的：
- `COMPONENTS` 元件列表
- `ROUTES` 走线路径
- `SILKSCREEN` 丝印文本

---

## 🛠️ 在 JLC EDA Pro 中查看 KiCad 文件

1. **JLC EDA Pro → 文件 → 打开**
2. 选择 `<project>.kicad_pcb`
3. JLC EDA Pro **支持 KiCad 导入**（File → Import → KiCad PCB）

或直接在 KiCad 中打开：
1. **KiCad → File → Open** → `<project>.kicad_pcb`
2. 查看 3D 预览
3. Run DRC → 应 0 error

---

## 🔄 v4.0 → v4.1 关键改进

### v4.0 的问题（实战发现）

CS5552-CONNECT-BD 项目实战中，Phase 6 (.eprj2 回写) 反复失败：
1. `.eprj2` 默认是空壳
2. `history_data` BLOB 格式未知（gzip/brotli 全部失败）
3. `eda.pcb_Primitive*.create(t,i,n,r,s,a,o,l)` 8 个位置参数无法推断
4. `getAll()` 返回 null

### v4.1 的解决方案

**改用 [KiCad pcbnew](https://dev-docs.kicad.org/zh-cn/apis-and-binding/pcbnew/index.html) 作为主路径**：
- ✅ 100% 自动化（无空壳问题）
- ✅ 开源、跨平台
- ✅ Python API 完整成熟
- ✅ .kicad_pcb 可在 KiCad 中打开
- ✅ 可导出为嘉立创兼容格式

**保留 JLC EDA Pro 作为备用**（通过 `api('applySource')`）

---

## 📚 调研发现的资源

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
- [AI 设计 Agent Skill 直接起飞](https://new.qq.com/rain/a/20260204A02HZ400) — Agent Skill 趋势
- [PCB 产业 AI 驱动增长](https://www.donews.com/news/detail/8/6518329.html) — 行业背景

---

## 🐛 14 条已知踩坑（来自 CS5552-CONNECT-BD 实战）

| # | 现象 | 解决方案 |
|---|---|---|
| 1 | .eprj2 默认空壳 | **改用 KiCad 主路径** |
| 2 | history_data BLOB 格式未知 | 不逆向，改用 KiCad |
| 3 | documents.dataStr 不被读取 | 改用 KiCad 或 applySource |
| 4 | AI 无 LCSC 实时库存 | 提供 ≥2 备选 + 标"待用户确认" |
| 5 | Python3 命令 Windows 不存在 | 用 `py` 替代 |
| 6 | GBK 编码 Unicode 报错 | 用 `[OK]` 替代 |
| 7 | Gerber 精度格式 | `%FSLAX46Y46*%` |
| 8 | J2 vs H1/H2 几何冲突 | J2 中心 y 上移至 2.5mm |
| 9 | 丝印必须在 Phase 3 输出 | Layout_Plan.json 必含 silkscreen_layer |
| 10 | `pcb_Primitive*.create()` 是 minified 位置参数 | 改用 KiCad 或 applySource |
| 11 | `pcb_PrimitiveLine.create` 8 参数无法推断 | 改用 pcbnew TRACK |
| 12 | `dmt_Pcb.getCurrent()` 是错误 API 名 | 正确是 `getCurrentPcbInfo()` |
| 13 | `getAll()` 返回 null 说明文档未激活 | 必须先 `activateDocument` |
| 14 | `Component.create` 返回 null 缺 footprint | 改用 KiCad FootprintLoad |

---

## 📝 修订记录

| 版本 | 日期 | 主要变更 |
|---|---|---|
| v1.0 | 2026-07-07 | 初版（仅 JSON DSL 中间态） |
| v3.0 | 2026-07-07 | 实战测试 + 7 阶段 SOP |
| v4.0 | 2026-07-10 | Phase 6/7 (.eprj2 + Gerber) |
| **v4.1** | **2026-07-10** | **KiCad 主路径 + applySource 备用 + 14 条踩坑库 + build_kicad.py 模板** |
| v4.2 (规划) | — | 集成 Flux.ai / Quilter / LLM-EDA 工具 |