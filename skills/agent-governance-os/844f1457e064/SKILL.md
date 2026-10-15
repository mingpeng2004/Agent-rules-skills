---
name: agent-governance-os
description: Portable AgentOS governance for long-running software, firmware, hardware-in-loop and operations tasks.
displayNames:
  zh-Hans: AgentOS system governance
---

# AgentOS for Kimi Code

For complex work, read protocols/SKILL-MATRIX.md and use bin/agentos_skills.py
to select one primary method and at most two necessary constraints. Load only
matched provider files. Missing inputs/providers and candidate methods block
dependent work. Gate outputs with current source hashes, applicable evidence and
distinct verifier checks. Routing never grants safety or native permissions.

At every new conversation, import the project AGENTS.md and then:

1. $env:AGENTOS_HOME/runtime/AGENT-IMPORT.md
2. $env:AGENTOS_HOME/runtime/BOOT.md
3. $env:AGENTOS_HOME/constitution/AGENTOS-CONSTITUTION.md
4. $env:AGENTOS_HOME/protocols/TRUTH-AND-EVIDENCE.md
5. $env:AGENTOS_HOME/protocols/TASK-PROTOCOL.md
6. $env:AGENTOS_HOME/protocols/RECURSIVE-PLANNING.md
7. $env:AGENTOS_HOME/protocols/CONTEXT-PIPELINE.md
8. Project .agentos state, current task, checkpoint and claims ledger.

## Upfront confirmation

Settle the development and software framework once before implementation: seed
domains from project SSOT, present one confirmation packet for unresolved
domains, and record explicit user confirmation in .agentos/contract. Framework-level
domains never time out. Later requirements are amendments; tasks bind
contract_version and run bin/AgentOS-Contract.ps1 check at unit boundaries and on
resume. Read protocols/UPFRONT-CONFIRMATION.md.

## Truth gate

No traceable source means no verified fact. Keep user-stated information,
model reasoning, assumptions, proposals, synthetic data and observed results
explicitly labeled. Never invent versions, test results, device states,
performance values or acceptance results.

Every command or test used as evidence must have complete output, exit code,
time and a saved artifact hash. A failed, timed-out, truncated or disconnected
operation is failed or unknown. Conflicting or stale evidence blocks delivery.
Synthetic or mixed data cannot satisfy real-device, safety, production or
user-acceptance gates.

## Long-task loop

For complex work, create a task file, define Phase/Task/Unit dependencies and
the evidence level for every DoD item. Execute one ready Unit, validate it
with an external check, record the claim using bin/AgentOS-Evidence.ps1, update
the checkpoint and working memory, and refine the next Unit.

Import protocols/DELEGATED-AUTONOMY.md and policies/DECISION-POLICY.json. Execute
authorized routine work immediately. Persist and actually notify ordinary
reversible preferences; after 300 seconds without feedback, adopt only through
bin/AgentOS-Decision.ps1 evaluate as delegated_default. Record actual user
feedback before deadline evaluation at every Unit/resume. Safety, unknown facts,
native approvals and user acceptance never default. Continue independent Units
while waiting; do not claim a wakeup timer exists when the host has none.

Kimi CLI may load the skill directory explicitly with the client option that
points to $env:AGENTOS_HOME/adapters/kimi. If the client does not expose a
session-scoped approval control or context compaction hook, do not pretend it
does; use the AgentOS ledger and checkpoint protocols and state the limitation.
