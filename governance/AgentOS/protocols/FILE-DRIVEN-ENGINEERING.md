# File-Driven Engineering Adapter

This protocol connects AgentOS to the registered authored
`embedded-software-engineering` Skill, version 1.1.0 or a validated compatible
revision. It adds no executable runtime and does not change AgentOS VERSION.
Project rules, locked requirements and explicit user instructions retain priority.

## Resolve the engineering core

Locate the Skill through the current client's installed catalog or the project's
registered authored source. Read its `SKILL.md` and
`references/file-driven-governance.md`; use `references/client-adapters.md` when
client discovery or capabilities differ. Do not hardcode a user's host path,
silently install a Skill, fetch an external repository, or copy a second version
of its core rules into AgentOS. If unavailable, record the limitation and continue
only work supported by existing project/AgentOS contracts; do not claim this
adapter was applied or invent the missing content.

The core document graph is:

    GOALS -> FRAMEWORK/contracts -> DEVELOPMENT_PLAN (Phase/Task/Unit)
          -> ACCEPTANCE/evidence -> PROJECT_STATE/checkpoint

Map these logical roles to existing project SSOT paths before creating files.

Also apply the Skill's references/records-lifecycle.md and token-efficiency.md
when managing historical noise or engineering resource budgets: refresh one
current projection, invalidate superseded evidence, archive with references and
hashes, delete only an explicitly approved index, and use selective context and
validated reuse without reducing quality/safety gates. No raw evidence deletion
or measured Token savings is implied by this extension.

For cross-model capability claims also load the Skill capability-assurance
reference. Use a registered tools/engineering_gate.py when available to check
authoritative document hashes and required evidence before closure; absent
tools or missing observations remain unknown/blocked. This read-only gate adds
no permission and does not make same-permission local files tamper-proof.
MiniMax/Codex/Kimi parity requires matched-task runs with actual model/client
versions, outputs, quality and Token telemetry; no parity is presumed here.
Do not rewrite constitutions or locked requirements, and do not maintain a
second status source. Lightweight changes can use one existing task record.

## Map existing AgentOS state

Read `<project>/.agentos/project.json` and resolve its declared `status_file`,
`task_dir`, `checkpoint_dir`, `working_memory`, `evidence_ledger` and
`decisions_dir` where present. Consult the import contract for missing fields;
do not guess schema or duplicate the task/evidence ledger. PROJECT_STATE is an
index into those paths unless the project explicitly designates it otherwise.

Use AgentOS TASK-PROTOCOL, TRUTH-AND-EVIDENCE, QUALITY-GATE and
DELEGATED-AUTONOMY for task records, claims, gates and authorization. After an
approved scope/plan, continue authorized implementation, checks, fixes and
engineering closure without repeated approvals. New safety actions and changed
locked scope remain gated. Hardware/user acceptance needs its actual evidence;
software checks and successful flashing do not close those gates.

Default Markdown execution SSOT and Word review snapshots follow the Skill's
hash/version association, stale snapshot and reviewed merge rules. Preserve any
user-mandated original Word SSOT. Render snapshots at approved baselines,
milestones and handoff rather than on every tool round. This adapter creates no
renderer, background timer, service, scheduler or client-native approval control.
