# PCBA Skill v5.1 — Agent 驱动 KiCad 全自动设计闭环 + 电气审查

> **位置**: `d:\000_VSCode\000_Rule_setup\skills\pcba-design\`
> **实战验证**: CS5552-CONNECT-BD v7（2026-07-20，真实 DRC 129→0 errors，18 检查点 APPROVED）
> **核心升级 v4.5 → v5.0**: 从「JSON DSL 模拟验证 + 硬编码 PASS」到「kicad-cli/pcbnew 真实测量 + 自修复回路」

---

## 📦 目录结构

```
pcba-design/
├── SKILL.md                      # ⭐ 主文档：FSM + 9 层检查点 + 执行流程 + 踩坑库
├── README.md                     # 本文件
├── scripts/                      # 全部项目无关，跨项目复用
│   ├── kicad_env.py              # E 层：环境探测（kicad-cli/KiCad Python/库路径）
│   ├── design_validate.py        # I 层：design.json 结构 + 封装真实存在性
│   ├── build_board.py            # design.json → .kicad_pcb（焊盘赋网/吸附走线/真铺铜）
│   ├── build_schematic.py        # design.json → .kicad_sch（可过真实 ERC）
│   ├── run_checks.py             # S/L/R/D 18 检查点（真实 DRC/ERC + 几何实测）
│   ├── export_mfg.py             # Gerber/钻孔/坐标/STEP/zip/下单 README
│   ├── verify_output.py          # O 层：回读 Gerber/钻孔实测 + 三方一致
│   ├── elec_review.py            # ELEC 层：连通性/引脚映射/SI/回流/压降/ngspice（v5.1）
│   └── visual_review.py          # 渲染多角度 PNG 供 AI 视觉复检
├── references/
│   ├── checkpoints_v5.yaml       # 9 层 50+ 检查点定义（ID/权重/方法/判定）
│   ├── jlc_capabilities.yaml     # 嘉立创工艺能力参数（DFM 阈值源）
│   └── kicad_cli_cheatsheet.md   # kicad-cli 命令速查 + 踩坑表
├── templates/
│   ├── design.schema.json        # design.json 契约（单一设计事实源）
│   └── design.example.json       # CS5552 v7 实战完整示例
├── acceptance_checklist_v3.yaml  # （历史保留）v4.5 的 199 项清单
├── SKILL_v4.5_backup.md          # v4.5 备份
└── archive_v45/                  # v4.5 老脚本（build_eprj2/generate_gerber 等）
```

---

## 🚀 在新项目中使用（AI 视角）

**前置**：安装 KiCad 9+（验证基线 10.0.4）。无需 pip 安装任何东西——用 KiCad 自带 Python。

把本 skill 目录路径告诉 AI，然后说：

> 「按 `d:\000_VSCode\000_Rule_setup\skills\pcba-design\SKILL.md` 的 v5.0 闭环设计这块板。PRD 如下：……」

AI 会执行：

```bash
SK=<skill目录>/scripts
KPY="C:/Program Files/KiCad/10.0/bin/python.exe"   # 由 kicad_env.py 探测

python "$SK/kicad_env.py"                          # 0. 环境门禁
# AI 编写 design.json（唯一事实源）
"$KPY" "$SK/design_validate.py" --design design.json          # 1. 输入门禁
"$KPY" "$SK/build_board.py"     --design design.json --outdir dist  # 2. 建板
"$KPY" "$SK/build_schematic.py" --design design.json --outdir dist  # 3. 原理图
"$KPY" "$SK/run_checks.py" --board dist/X.kicad_pcb \
  --schematic dist/X.kicad_sch --design design.json \
  --out dist/check_report.json --md dist/check_report.md      # 4. 全量检查
#   退出码≠0 → AI 读报告 → 修 design.json → 回到 2（自修复回路，3 次熔断）
"$KPY" "$SK/export_mfg.py" --board dist/X.kicad_pcb --outdir dist/mfg \
  --zip --step --order-readme                                  # 5. 制造输出
"$KPY" "$SK/verify_output.py" --board dist/X.kicad_pcb \
  --mfg dist/mfg --design design.json                          # 6. 输出回读
"$KPY" "$SK/elec_review.py" --board dist/X.kicad_pcb \
  --design design.json --report dist/elec.json --md dist/elec.md  # 6.5 电气审查
python "$SK/visual_review.py" --board dist/X.kicad_pcb --outdir dist/review
#   → AI 逐张看图（视觉门禁）                                   # 7. 视觉复检
```

**最终交付**：`dist/` 下 = .kicad_pcb/.kicad_sch（可双击打开）+ `mfg/`（Gerber.zip 可直接上传 JLC 下单）+ check_report.md + 渲染图。

---

## 🛡️ v5.0 与 v4.5 的本质区别

v4.5 的「100% PASS」是**假的**：review_checklist.py 大量硬编码 PASS（如"KiCad 默认生成 3 个 Fiducial"、"孔环 0.75mm"），从不打开板子测量。CS5552 v6 实战：报告 51/51 PASS，真实 DRC **129 条违规 + 2 处未连接**（J2 排针转出板外、无 GND 铺铜、5 处短路）。

v5.0 每个检查点都绑定**机器可执行的测量方法**，测不了的诚实标 `MANUAL`。
判定语义：`APPROVED`（无 P0/P1 FAIL）/ `CONDITIONAL`（P1 待豁免）/ `REJECTED`（P0 一票否决）。

---

## 📝 修订记录

| 版本 | 日期 | 主要变更 |
|---|---|---|
| v1.0~v4.5 | 2026-07 | DSL 阶段化 + KiCad 主路径 + 199 项清单（已证伪） |
| **v5.0** | **2026-07-20** | **真实工具链验证 + 9 层检查点 + design.json 契约 + 自修复回路；CS5552 v7 全闭环 APPROVED** |
| **v5.1** | **2026-07-20** | **ELEC 电气审查层（连通性/引脚映射/SI/回流/压降/ngspice）+ 系统级注册（Claude/Kimi 用户目录）** |
