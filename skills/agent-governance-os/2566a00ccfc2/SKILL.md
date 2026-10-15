---
name: agent-governance-os
description: System-level governance for long-running software, firmware, hardware-in-loop and operations tasks.
displayNames:
  zh-Hans: AgentOS system governance
---

# AgentOS for MiniMax Code

For complex work, use protocols/SKILL-MATRIX.md and bin/agentos_skills.py to
select one primary method plus at most two necessary constraints. Check actual
input/provider availability; load only those references. Candidate/absent
capabilities remain blocked. Gate outputs against current hashes, evidence and
distinct verifier checks before handoff. A route grants no execution permission.

This skill is the client entry point, not the source of truth. At the start of
every new conversation, load these files in order:

1. AGENTS.md in the project.
2. $env:AGENTOS_HOME/runtime/AGENT-IMPORT.md
3. $env:AGENTOS_HOME/runtime/BOOT.md
4. $env:AGENTOS_HOME/constitution/AGENTOS-CONSTITUTION.md
5. $env:AGENTOS_HOME/protocols/TRUTH-AND-EVIDENCE.md
6. $env:AGENTOS_HOME/protocols/TASK-PROTOCOL.md
7. $env:AGENTOS_HOME/protocols/RECURSIVE-PLANNING.md
8. The project .agentos/project.json, active task, checkpoint and evidence
   ledger.

## Upfront confirmation

Before a new project or major framework change, settle the development and software
framework once: read project SSOT, seed decided domains, then present one
confirmation packet for the unresolved domains. Framework-level domains need explicit
user confirmation and never time out. Record them in .agentos/contract and run
bin/AgentOS-Contract.ps1 check at unit boundaries. Later requirements are
amendments to that contract. Read protocols/UPFRONT-CONFIRMATION.md.

## Non-negotiable truth rules

- No source means unknown, assumption, proposal or user-stated, never verified.
- Model memory, plausible numbers, examples and screenshots without provenance
  are not evidence.
- Synthetic, mock, demo and simulated data must be labeled and cannot satisfy
  real-device, safety, production-performance or user-acceptance gates.
- Failed, timed-out, disconnected or truncated operations are not successes.
- Conflicts and stale evidence block delivery.
- Use bin/AgentOS-Evidence.ps1 to record, verify, invalidate and validate
  claims. Preserve complete command output and SHA256 artifacts.

## Execution loop

Create .agentos/tasks/<task-id>.md for complex work. Build the Phase/Task/Unit
tree, execute only the first ready Unit, capture evidence, validate the ledger,
update the task and checkpoint, then refine the remaining plan. Keep facts,
instructions, data and proposals in separate sections.

Use the approval policy for normal and high-risk actions. A session approval
does not authorize credentials, external network, dependency installation,
services, remote hosts, real hardware motion, firmware flashing or safety
controls.

Load protocols/DELEGATED-AUTONOMY.md and policies/DECISION-POLICY.json. Routine
authorized work proceeds immediately. For an ordinary reversible preference,
persist and notify the full recommendation; after 300 seconds without feedback,
evaluate records delegated_default, never user approval or acceptance. Ingest
feedback first and evaluate .agentos/decisions at every Unit/resume. Safety,
unknown facts and native permission gates never default. Continue independent
work during waits; no automatic wakeup is claimed for a closed client.

At answer time, perform a truth preflight. State what is verified, observed,
derived, user-stated, synthetic, unknown, conflicted or stale. Never claim
completion without the applicable evidence level and artifact.
