<!-- AGENTOS:BEGIN managed v1.4.0 -->
## AgentOS 系统治理入口

AGOS-SKILLS：复杂任务读取 protocols/SKILL-MATRIX.md；通过 agentos_skills.py 选一个
主能力和必要约束，核对输入，验证产出与当前证据。候选技能不冒充已部署；不预载全部。

本项目接入 `Agent Governance OS`。开始复杂任务前读取：

1. `AGENTS.md`、项目需求/契约 SSOT 和当前状态文件。
2. `${AGENTOS_HOME}\runtime\BOOT.md`（或 `$env:AGENTOS_HOME\runtime\BOOT.md`）。
3. 项目 `.agentos\project.json`、当前任务和最近 checkpoint。

复杂任务必须外置任务状态、逐 Unit 验证并留下证据。没有测试、编译、实测或审计证据，不得声明完成；同类问题第二次失败换路，第三次列根因表，第四次升级。

AGOS-CONFIRM：开工前先用 protocols/UPFRONT-CONFIRMATION.md 一次性定调开发与软件框架（12 域，需用户明确确认，不超时），落盘 .agentos\contract；后续需求以修订迭代，任务绑定 contract_version 并跑 AgentOS-Contract.ps1 check。

AGOS-AUTO：已授权普通工作直接推进。完整推荐方案落盘并实际通知后，普通偏好 300 秒无反馈按既有委托采用，记录 delegated_default。安全、未知事实、锁定 SSOT、宿主权限和真实验收不超时放行。每个 Unit/恢复点先记录反馈，再 evaluate .agentos/decisions；等待期间推进独立工作。该明确用户授权更新旧的非安全无限等待规则。读取 protocols/DELEGATED-AUTONOMY.md。

AgentOS 目录：`$env:AGENTOS_HOME`。客户端适配器、长程协议和安全宪法均以该目录为单一事实源。
<!-- AGENTOS:END managed -->
