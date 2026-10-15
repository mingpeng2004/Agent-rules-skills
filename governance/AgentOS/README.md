# Agent Governance OS

## Capability contracts and skill routing (1.4.0)

The 63-capability matrix is mapped to existing methods and explicit candidate
gaps in policies/SKILL-REGISTRY.json. Read protocols/SKILL-MATRIX.md. The stdlib
CLI bin/agentos_skills.py validates contracts, selects one primary capability
with up to two constraints, checks input/source bindings, gates actual outputs
against current evidence and records lessons proposed for review. Python 3.9+
is required for this inspector; no dependency/runtime is installed automatically.
The reusable production-skill-routing skill ships in the transparent installer.
Candidate methods are not installed specialist skills or certified capabilities.

## Goal/file driven autonomy (1.2.0)

This release extends the existing AgentOS. Routine authorized development
continues immediately; ordinary preference recommendations default after
300 seconds from actual notification under the user's delegation. Persistent
decisions live in .agentos/decisions and bind proposal/source/policy hashes.
Safety, unknown facts, native tool approvals and real acceptance never default.
Use bin/AgentOS-Decision.ps1; the protocol is protocols/DELEGATED-AUTONOMY.md.
The resume protocol evaluates existing deadlines without resetting them, after
actual new feedback is recorded. A live host loop is required for unattended progress;
no scheduler/service is installed. Local files cannot compel a same-permission
agent to comply. No model-capability parity claim has been measured.

## Truth and evidence gate

Version 1.1 adds a system-wide truth gate. The append-only project ledger is
project/.agentos/evidence/claims.jsonl. Use bin/AgentOS-Evidence.ps1 to record,
verify, invalidate and validate claims. A claim with no source is not verified.
User statements, model reasoning and synthetic data remain explicitly labeled.
The next-session import contract is runtime/AGENT-IMPORT.md.

Agent Governance OS (AgentOS) 是 Minimax Code、Kimi Code 以及其他代码智能体共用的系统级任务治理层。

它把长期执行能力拆成五个可以检查的部分：

1. 目标与验收：先写清楚什么叫完成。
2. 任务状态：把阶段、依赖、阻塞、下一步写入磁盘。
3. 执行控制：让模型一次只做一个可验证单元，并在失败后升级策略。
4. 证据门禁：测试、编译、实测和安全检查必须留下证据。
5. 适配层：不同客户端只负责加载同一套系统规则。

## 目录

| 目录 | 用途 |
|---|---|
| `constitution/` | AgentOS 的优先级、权限和安全宪法 |
| `runtime/` | 每次会话都能快速加载的短启动协议 |
| `protocols/` | 长程任务、模型降级、项目接入协议 |
| `policies/` | 授权域和风险分级策略 |
| `templates/` | 任务单、检查点和项目入口模板 |
| `adapters/` | MiniMax Code、Kimi Code 的客户端适配内容 |
| `profiles/` | STM32/嵌入式等项目类型的专项前置和证据链 |
| `bin/` | 安装、注册、诊断、恢复工具 |
| `reports/` | AgentOS 自身的诊断和安装报告 |

## 当前接入方式

- MiniMax Code：全局 Mavis overlay + 全局 `agent-governance-os` skill。
- Kimi Code：用户 skill + 项目根 `AGENTS.md` 托管入口。Kimi CLI 也可以通过 `--skills-dir` 显式指定 AgentOS。
- 项目：根 `AGENTS.md` 只增加一个带标记的 AgentOS 托管段，项目原有规则继续作为项目层约束。

## 常用命令

在 PowerShell 中运行：

```powershell
$env:AGENTOS_HOME = '${AGENTOS_HOME}'
& "$env:AGENTOS_HOME\bin\AgentOS.ps1" install
& "$env:AGENTOS_HOME\bin\AgentOS.ps1" diagnose
& "$env:AGENTOS_HOME\bin\AgentOS.ps1" register -ProjectRoot 'D:\path\to\project'
& "$env:AGENTOS_HOME\bin\AgentOS.ps1" new-task -ProjectRoot 'D:\path\to\project' -TaskId 'task_001' -Title '任务标题'
& "$env:AGENTOS_HOME\bin\AgentOS.ps1" resume -ProjectRoot 'D:\path\to\project'
```

`install` 不安装外部依赖，不创建计划任务，不关闭安全控制，也不改变项目代码。它只建立 AgentOS 目录、接入两个客户端、设置用户级 `AGENTOS_HOME` 并注册已知项目。

授权域默认是当前会话：普通读写、测试、编译和日志操作可以连续执行；删除、凭据、网络、远程、服务、真实硬件和烧录动作仍逐次确认。该策略不会强行修改客户端原生权限弹窗。

进入新项目时运行一次 `register`，之后直接在 MiniMax Code 或 Kimi Code 打开该项目即可触发入口规则。已有项目的原始 `AGENTS.md` 仍是项目事实源，AgentOS 托管段可以被脚本按版本更新。

## 规则优先级

用户明确目标与最终验收 > 操作系统和安全边界 > 项目自己的 SSOT/AGENTS/契约 > AgentOS 默认流程 > 客户端默认行为。

项目规则可以收紧 AgentOS 的约束，不能放松安全边界。AgentOS 不会替项目臆造硬件状态、测试结果或用户验收。

## 版本与迁移

AgentOS 的可迁移单元是整个目录。迁移到另一台电脑后，设置 `AGENTOS_HOME` 指向新目录，再运行 `AgentOS.ps1 install`；随后为目标项目运行 `register`。客户端适配器不保存凭据，凭据继续由各客户端自己的安全存储管理。

## 已知边界

MiniMax 的 Mavis overlay 支持系统级自动注入。Kimi Code 扩展没有暴露可由本地文件直接设置的全局 system prompt，因此 Kimi 的可靠接入由全局 skill、项目 `AGENTS.md` 入口和可选 CLI wrapper 共同完成。诊断报告会把加载路径和接入状态明确列出。
