---
name: design-gate
description: 设计意图驱动的阶段门禁体系：设计意图评估 → 选型锁定 → 原理图/布局/布线冻结 → 制造/组装发布 → 验收落地。每个阶段有标准检查清单与证据要求，机器可核验（gate.py），关键交付文件以 release_manifest.json 哈希锁定，确保设计落地可查、可回溯、不可带病发布。
license: 项目内部标准
metadata:
  version: "1.0"
  created: "2026-09-21"
  authority_files: [standards/design_intent.yaml, standards/stage_gates.yaml]
---

# Design Gate · 设计意图门禁体系

> 核心哲学：**意图先行、证据门禁、级联失效、哈希锁定**。
> 不信任任何工具的绿色指示灯（ERC/DRC 只查一致性，不查意图——v3.1 的 127 引脚错位教训）；
> 每个阶段通过的唯一标准是"清单全勾 + 证据落盘"。

## 标准文件布局（单一事实源）

```
standards/
├── design_intent.yaml      # 意图登记册：NS 硬约束 + G1~G5 验收指标 + EI 工程意图
├── stage_gates.yaml        # S0~S7 门禁定义：准入/证据/通过规则/级联失效
└── checklists/S*.md        # 每门禁一份检查清单（含一票否决项标注）
.claude/skills/design-gate/scripts/gate.py   # 执行器
outputs/release/            # 每次发布的门禁报告与文件清单（哈希锁定）
```

## 全流程（设计意图 → 合格落地）

```
S0 设计意图评估 ─→ S1 选型锁定 ─→ S2 原理图冻结 ─→ S3 布局冻结
     ─→ S4 布线闭合 ─→ S5 制造发布 ─→ S6 组装发布 ─→ S7 验收落地出证
```

每个阶段：
1. **读清单**：`standards/checklists/<阶段>.md`，逐条执行，每条留证据（文件/命令输出/截图）；
2. **查否决项**：清单中标注【一票否决】的条目失败即整门 FAIL，不得 WAIVED；
3. **跑执行器**：`gate.py run` 核验证据文件存在并计算 SHA-256；
4. **记决策**：通过/豁免/失败处置写入 `context/decisions.log`（豁免必须注明理由+批准人）。

## 执行器用法

```bash
# 1. 意图登记册完整性校验（S0 的机器化部分）
python .claude/skills/design-gate/scripts/gate.py intent-check

# 2. 全门禁执行：核验证据文件 + 生成发布清单与报告
python .claude/skills/design-gate/scripts/gate.py run
#    → outputs/release/release_manifest.json（关键交付文件 + sha256）
#    → outputs/release/gate_report.md（每门 PASS/FAIL）

# 3. 版本一致性核验（下单前/复跑后，清单 F-08/A-08）
python .claude/skills/design-gate/scripts/gate.py verify
#    磁盘文件哈希与 manifest 比对，任何漂移立即报警
```

## 铁律

1. **禁止假 PASS**：证据缺失 = FAIL；`gate.py verify` 哈希不一致 = 立即作废本次发布。
2. **级联失效**：上游任何变更按 `stage_gates.yaml` 的 invalidation_cascade 重跑下游门禁。
3. **旧版隔离**：被取代的制造文件移入 `_superseded_<日期>/` 并标注禁止上传，禁止原地删除（可追溯）。
4. **审批分离**：S6 的价格/贴装/支付三项审批互相独立；AI 可准备材料，不得代按支付。
5. **AI 产出必过门禁**：无论 KiCad 脚本、自动布线还是 easyeda-agent 的 typed action，写入后一律回读对账 + DRC + `gate.py verify`。
6. **条件达标必须转正**：G1/G2 等 conditional-pass 项在 S7 实测完成前，对外口径不得称"全指标达标"。
