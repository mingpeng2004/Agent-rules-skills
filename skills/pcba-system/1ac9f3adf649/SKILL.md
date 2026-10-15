---
name: pcba-system
description: 系统级 PCBA 开发流程与技能总纲。任何新案子从需求到合格落地一律按 P0~P7 阶段推进：设计意图评估→选型锁定→原理图冻结→布局冻结→布线闭合→制造发布→组装发布→验收落地。每阶段有标准清单、证据要求与机器可核验的门禁引擎（pcba_gate.py）。核心哲学：意图先行、证据门禁、级联失效、哈希锁定、AI 产出必过门禁。适用一切 PCB/PCBA 开发案。
license: 项目内部标准
metadata:
  version: "1.0"
  created: "2026-09-22"
  origin: CS5552_WCD 项目磨合沉淀（v3.1 事故 → D23 修复 → D24 门禁体系）
---

# PCBA-System · 系统级开发流程总纲

> 目标：**任何案子一次性输出高质量的、可直接打样的 PCBA 设计方案**。
> 手段：不靠个人记忆和运气，靠阶段门禁 + 证据链 + 事故经验库。

## 零、铁律（任何案子、任何阶段不可违反）

1. **意图先行**：动手前必须有书面的、可验证的设计意图（量化指标 + 验证方法 + 证据路径）。
2. **证据门禁**：每个阶段通过的唯一标准是"清单全勾 + 证据落盘 + 引擎核验通过"。"看起来 OK"= 不通过。
3. **AI 产出必过门禁**：无论 AI 生成原理图、自动布线还是 typed action 写入，一律回读对账 + ERC/DRC + 引擎核验。工具绿灯不代表意图正确（ERC/DRC 只查一致性）。
4. **级联失效**：上游任何变更，按失效映射表重跑下游门禁，禁止只修不改验。
5. **哈希锁定**：发布物（Gerber/BOM/CPL/文档）计算 SHA-256 写入 manifest；下单前 `verify`，任何漂移 = 本次发布作废。
6. **旧版隔离**：被取代的制造文件移入 `_superseded_<日期>/` 标注禁止上传，禁止原地删除。
7. **审批分离**：代料/贴装/价格/支付四项审批互相独立，AI 准备材料不得代按支付。
8. **条件达标不夸大**：依赖实测或固件配置的指标，在转正前对外口径不得称"达标"。

## 一、主流程 P0~P7（每案必走）

```
P0 需求与意图评估 → P1 选型锁定 → P2 原理图冻结 → P3 布局冻结
   → P4 布线闭合 → P5 制造发布 → P6 组装发布 → P7 验证落地出证
```

| 阶段 | 核心问题 | 准入 | 准出（门禁证据） | 清单 |
|---|---|---|---|---|
| P0 意图评估 | 造什么？如何证明造对了？ | 原始需求 | design_intent.yaml 通过引擎校验 | C0 |
| P1 选型锁定 | 每个料号钉死了吗？ | P0 PASS | BOM 100% 有 MPN+料号+手册证据 | C1 |
| P2 原理图冻结 | 电气连接符合意图吗？ | P1 PASS | ERC 0 error + 引脚映射核对证据 | C2 |
| P3 布局冻结 | 器件摆对了吗？间距可制造？ | P2 PASS | DRC 布局类 0 error + 关键局部审查 | C3 |
| P4 布线闭合 | 全部物理连通？无违规？ | P3 PASS | DRC 0 error / 0 未连接 + 载流校核 | C4 |
| P5 制造发布 | Gerber 能直接下单吗？ | P4 PASS | manifest 哈希一致 + 层数/参数一致 | C5 |
| P6 组装发布 | 能贴片且方向正确吗？ | P5 PASS | 料号 100% 覆盖 + CPL 人工预览 | C6 |
| P7 验证落地 | 实测达标吗？ | 样机 | G 指标测试报告齐全 | C7 |

清单全文：`templates/checklists.md`（八节，含一票否决项标注）。

## 二、新项目启动（10 步）

1. 复制 `templates/design_intent.template.yaml` → 新案 `standards/design_intent.yaml`，填北极星/G 指标/EI 意图
2. 复制 `templates/stage_gates.template.yaml` → `standards/stage_gates.yaml`，改证据路径
3. 跑 `pcba_gate.py intent-check` 校验意图完整性（P0）
4. 选型并锁定（P1）；关键器件手册存 `archive/datasheets/`
5. 原理图 + ERC + **封装列引脚核对**（P2，一票否决）
6. 布局 + 间距规则核对（P3）
7. 布线 + 全量 DRC + 同网多引脚连通抽查（P4，一票否决）
8. 导出制造包 + ORDER_README + `pcba_gate.py run`（P5）
9. 补 LCSC 料号 + CPL 人工预览（P6）
10. 样机实测 G 指标 + 出证（P7）

## 三、门禁引擎

```bash
# 意图登记册完整性（P0）
python .claude/skills/pcba-system/scripts/pcba_gate.py intent-check --root <项目根>

# 全门禁执行 → outputs/release/release_manifest.json + gate_report.md
python .claude/skills/pcba-system/scripts/pcba_gate.py run --root <项目根>

# 版本一致性（每次下单前必跑）
python .claude/skills/pcba-system/scripts/pcba_gate.py verify --root <项目根>
```

引擎支持声明式扩展检查（写在 stage_gates.yaml 的 `checks:` 下）：
- `text_contains`：文本文件必须含某字符串（如 ORDER_README 声明"4 层"）
- `zip_contains`：压缩包必须含某条目（如 Gerber 含 In1_Cu）
- `file_empty`：文件必须为空（如缺料清单）
- `command`：执行命令，退出码必须为 0（如 `kicad-cli pcb drc`）

## 四、设计评审团（多角色专业评审，防漏失的核心机制）

单线程检查必然漏项。每个关键门禁由**评审团**按域清单分角色会审，机制、角色、输出模板见
[review-board.md](references/review-board.md)；专业域清单见 [domain-checklists.md](references/domain-checklists.md)。

- **P2 必到**：R1 原理图审查员 + R2 电源完整性 + R8 可靠性降额
- **P3 必到**：R3 信号完整性 + R4 EMC + R7 热设计 + R5 DFM + R6 可测试性
- **P4 必到**：R3 + R4 + R5，R1 复核连通性
- **P5 必到**：R5 DFM + R6 供应链
- 每个发现的五要素：严重级/置信度/证据/影响/建议；BLOCKER = 门禁 FAIL
- 评审纪要 `reviews/<门禁>_minutes.md` 是门禁证据的一部分

## 五、铁律补充

9. **评审域清单命中即加载**：评审团角色按 domain-checklists 命中的域逐条执行，禁止"凭经验扫一眼"替代域清单。

## 六、参考文档

- [事故与经验库](references/lessons-learned.md)——所有翻车记录与防护条目（每条都对应某清单的否决项）
- [设计评审团机制](references/review-board.md)——R1~R8 角色定义、触发时机、方法纪律、输出模板
- [域清单库](references/domain-checklists.md)——12 个专业域的深度检查清单
- [借鉴来源登记](references/sources.md)——外部来源与链接（可追溯）
- [工具链](references/toolchain.md)——KiCad/kicad-cli/pcbnew、嘉立创EDA+easyeda-agent、Freerouting、JLCPCB/LCSC 的用法与坑
- [JLC 工艺规则](references/jlc-fab-rules.md)——免费工艺边界与下单参数
