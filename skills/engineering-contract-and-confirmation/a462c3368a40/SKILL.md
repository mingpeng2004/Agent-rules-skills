---
name: engineering-contract-and-confirmation
description: "开工前与用户一次性定调开发框架与软件框架（12 域契约），后续需求以修订迭代，用版本绑定与漂移检查保证设计意图在长程任务中贯彻；同时给出生产级交付定义、效率规则与 UI 设计一致性方法。适用于新项目启动、重大框架变更、长期迭代项目接手、界面一致性治理。AgentOS 提供强制协议与工具，本 Skill 提供操作方法与范式。"
metadata:
  version: "1.0.0"
---

# 工程契约与前期定调

让弱模型也能稳定执行：框架一次性定调、需求以修订迭代、意图以版本绑定贯彻。

AgentOS 是协议与工具的单一事实源（`$env:AGENTOS_HOME`）。本 Skill 只讲**怎么做**，
不复述规范条文；需要条文时读 AgentOS 的对应文件。

## 1. 何时触发

- 新项目开工，或既有项目要做重大框架/架构变更
- 接手一个正在迭代、需求不断增加的长期项目
- 界面/交互需要保持一致，或设计语言尚未定调
- 长任务中出现"重复确认""方向漂移""改了就忘"

不触发：单文件小改、纯查询、已有确认契约内的常规实现。

## 2. 三层确认（决定了问不问、问多久）

| 层 | 覆盖 | 规则 |
|---|---|---|
| 契约层 | 12 个框架域 | 用户明确确认，**永不超时** |
| 偏好层 | 契约内的细节选择 | 通知后 300 秒无反馈按推荐默认，记录 delegated_default |
| 常规层 | 契约内的实现/测试/文档 | 直接执行，不询问 |

判断口：这件事改变的是"系统是什么"→ 契约层；只是"这次选哪个"→ 偏好层。

## 3. 十二个框架域

product_goal / scope_and_non_goals / quality_bar / tech_stack / architecture /
interfaces_contracts / data_and_storage / ui_and_interaction / safety_and_hardware /
security_and_privacy / ops_and_maintenance / acceptance_and_delivery

每个域最终必须是 confirmed、not_applicable 或 deferred（带所有者豁免引用）。
未决域不能靠"合理默认"填平。

## 4. 操作顺序（关键：先播种，再提问）

1. **读项目事实**：AGENTS.md、constitution、北极星、设计目标、契约、决策登记、既有架构文档。
2. **播种**：文件已经决定的域，直接以 project_ssot 登记并附文件路径。**不要问用户。**
3. **调研缺口**：只对确实没有文件依据的域做实际调查（读代码、检索配置、核对现状）。
4. **出包**：用 [references/confirmation-packet.md](references/confirmation-packet.md) 生成一份确认包，
   未决域逐条给出：现状事实 / 来源 / 推荐 / 影响 / 回滚 / 你的答复方式。
5. **记录**：按用户答复登记，来源写实际答复引用。绝不代答。
6. **封版**：全域解析后 seal 契约。

> 效率来自第 2 步。成熟项目通常 10 个以上域能由文件播种，用户只需回答 1-3 个真问题。

## 5. 风险不夹带、只登记

确认过程中发现的真实问题，**默认不在定调阶段动手改**：

- 与本次确认相关的 → 在确认包里作为"需要你判断的风险"列出，标明是否改变产品行为
- 与本次确认无关的 → 登记为独立待办（含 owner、DoD、约束），排进后续任务

这样封版过程不会夹带行为变更，也不会让发现的风险被遗忘。

## 6. 后续需求走修订

- 判定：改动已确认域/框架/安全/数据/接口/验收 → 契约修订（需明确确认）；
  域内细节 → 偏好修订（300 秒默认）
- 应用后契约版本递增，触及域的任务自动判为 stale 并阻断
- 方案快照被改动 → 该修订失效，须重新提案

详见 [references/amendment-and-drift.md](references/amendment-and-drift.md)。

## 7. 长任务中的贯彻点

- 任务文件记录 contract_version 与 contract_sections_in_scope
- Unit 边界 / 恢复点 / 契约相关动作前跑 check（exit 2 = 阻断）
- 检查点记录契约版本、未决域、待处理修订
- 工作记忆携带契约版本，新会话据此恢复而不是靠对话记忆

## 8. 生产级 + 高效

生产级是**证据属性**，不是提问数量的体现：适用门禁全绿、真实证据、独立验证、
如实声明交付状态。效率来自去掉仪式感：一次成包、已确认域不再问、按需求批量修订、
验证只跑一次并独立复核、证据在有效期内复用。

两种失败同等阻断：什么都确认了但没有证据；有证据但契约没确认。

## 9. 界面一致性

外部 UI 参考是**方法来源，不是依赖**：真实产品库研究信息架构、参考库建设计契约、
模式库转成验证清单。先定契约（DESIGN.md + 设计令牌）再做细节，界面漂移多半源于跳过契约。
详见 [references/design-consistency.md](references/design-consistency.md)。

## 10. 边界

本 Skill 与 AgentOS 都只是文件与提示层：同权限智能体可以绕过；没有经过认证的用户通道、
没有客户端原生确认弹窗、没有后台调度器。测试里的时间与用户反馈是隔离夹具，不是验收证据。

## 参考

- [references/confirmation-packet.md](references/confirmation-packet.md) — 确认包怎么写、怎么答
- [references/amendment-and-drift.md](references/amendment-and-drift.md) — 修订、版本绑定、漂移检查
- [references/design-consistency.md](references/design-consistency.md) — 界面契约与一致性检查
- [assets/templates/CONFIRMATION-PACKET.md](assets/templates/CONFIRMATION-PACKET.md)
- [assets/templates/AMENDMENT.json](assets/templates/AMENDMENT.json)