# AgentOS Next-Session Import Contract v1.4

This file is the short, portable import contract for every new AgentOS
conversation. MiniMax Code, Kimi Code, VS Code agents and delegated agents
must read it before doing work.

## Mandatory load order

1. The project's AGENTS.md and its stated SSOT files.
2. The AgentOS root from AGENTOS_HOME.
3. AgentOS/runtime/BOOT.md.
4. AgentOS/constitution/AGENTOS-CONSTITUTION.md.
5. AgentOS/protocols/TRUTH-AND-EVIDENCE.md.
6. AgentOS/protocols/TASK-PROTOCOL.md and
   AgentOS/protocols/RECURSIVE-PLANNING.md.
7. AgentOS/protocols/CONTEXT-PIPELINE.md,
   AgentOS/protocols/HARNESS-ENHANCEMENTS.md,
   AgentOS/protocols/LONG-HORIZON.md, AgentOS/protocols/QUALITY-GATE.md
   and AgentOS/protocols/MEMORY.md.
8. The project's .agentos/project.json, active task and latest checkpoint.
9. The project's .agentos/evidence/claims.jsonl, when present.
10. AgentOS/protocols/DELEGATED-AUTONOMY.md,
    AgentOS/policies/DECISION-POLICY.json and project .agentos/decisions/.
11. When the project has a contract: AgentOS/protocols/UPFRONT-CONFIRMATION.md,
    AgentOS/policies/INTERACTION-POLICY.json and project .agentos/contract/contract.json.
12. For complex engineering work: protocols/SKILL-MATRIX.md and the matching
    capability contracts in policies/SKILL-REGISTRY.json. Load one primary
    provider and up to two necessary constraints, not the whole skills library.
    Candidate or absent capabilities remain blocked. Route/gate reports index
    the existing task and evidence ledger without replacing them.

## Import acknowledgement

The agent must internally establish these facts before acting:

- Governance version loaded from AgentOS/VERSION.
- Project root and project SSOT identified.
- Current task, checkpoint and unknowns identified.
- Evidence ledger path identified.
- The structured task contract and recursive planning rules are loaded.
- Authorized routine work proceeds without repeated questions. Notified ordinary
  preferences default after 300 seconds under existing delegation, never inferred
  user approval. Safety, unknown facts, native approvals and user acceptance do
  not default. New feedback is ingested before evaluating saved deadlines.
- No material claim will be presented as verified without a source and a
  validation record.
- User-stated, model-derived, assumed and synthetic values will remain
  explicitly labeled.
- Conflicting, stale, failed, timed-out or truncated evidence blocks delivery.
- Framework-level domains are confirmed once by the user and enforced by the contract;
  routine work inside the contract proceeds without questions.

If a required file cannot be read, the agent must report that limitation and
use the state unknown. It must not fill the gap with plausible data.

## New-conversation operating loop

Software/firmware engineering and engineering-Skill maintenance additionally
load protocols/FILE-DRIVEN-ENGINEERING.md and its project-registered Skill
entry. This extension defines MD/DOCX guidance and cross-client file-driven
closure; existing authorization, SSOT and evidence requirements retain priority.

Plan one Unit, execute it, capture complete evidence, record the claim, validate
the ledger, update the task and checkpoint, then select one next action.
At response time, run the truth preflight: separate verified facts from
observations, assumptions, proposals and unknowns.
At Unit boundaries and resume, use bin/AgentOS-Decision.ps1 evaluate after recording
actual new feedback; continue independent ready Units during preference waits.

## Portable client rule

The client skill or overlay is only an entry point. The files under the
AgentOS root are the single source of truth. If a client does not expose a
session-level approval control, AgentOS cannot pretend that such a control
exists; it must state the limitation and preserve the safety gate.

