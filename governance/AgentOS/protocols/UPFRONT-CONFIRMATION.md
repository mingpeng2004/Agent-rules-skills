# Upfront Confirmation and Iteration Protocol v1.3

Purpose: settle the development framework and the software framework once, with the
user, before implementation; then keep later requirements consistent by iterating the
same contract instead of re-opening settled questions.

This protocol governs how the agent interacts with the user. It does not replace
project SSOT, the registered engineering Skill FRAMEWORK layer, or the safety and
authorization rules in APPROVAL-SCOPE.md.

## 1. Three confirmation tiers

| Tier | What it covers | How it is resolved | Timeout |
|---|---|---|---|
| contract | The 12 domains below: framework-level intent | Explicit user confirmation recorded with a source reference | Never |
| preference | Detail choices inside confirmed domains | Notified recommendation, 300 s delegated default | Yes, 300 s |
| routine | Implementation, tests, docs, refactors inside the contract | Proceed directly | Not applicable |

Never use the preference timeout to confirm a contract domain. Never use a routine
decision to change a confirmed domain; that is an amendment.

## 2. The twelve domains (comprehensive upfront coverage)

Each domain must end as confirmed, not_applicable, or deferred with an explicit
owner waiver reference before the contract can be sealed.

1. product_goal - who the user is, the value delivered, the north star, the success
   condition in one sentence.
2. scope_and_non_goals - included surface, explicitly excluded surface, expansion rules.
3. quality_bar - what "production-grade" means for this deliverable: evidence levels,
   performance, reliability, maintainability targets.
4. tech_stack - languages, frameworks, runtime, build chain, package sources, host OS
   and hardware constraints, licensing and cost.
5. architecture - layering, module boundaries, dependency direction, data flow, state
   ownership, extension points, the framework the software is built on.
6. interfaces_contracts - public APIs, protocols, schemas, versioning and compatibility
   policy, locked contracts and their change path.
7. data_and_storage - data model, persistence, schema and migration policy, backup and
   restore, retention, integrity checks.
8. ui_and_interaction - information architecture, interaction model, design language,
   design tokens, component inventory, states, accessibility, embedded GUI constraints.
9. safety_and_hardware - physical and electrical boundaries, actuators, motion, power,
   fail-safe behavior, forbidden parameters, no-workpiece conditions, hardware gates.
10. security_and_privacy - trust boundaries, credentials, secrets handling, attack
    surface, network exposure, ACLs, audit, third-party supply chain.
11. ops_and_maintenance - deployment, observability, alerting, rollback, backup and
    restore drills, maintenance windows, unattended operation boundaries.
12. acceptance_and_delivery - delivery artifacts, release process, who accepts, what
    evidence closes acceptance, and which items stay pending real user or device sign-off.

## 3. Run the upfront packet once

Before implementation of a new project or a major framework change:

1. Read the project SSOT first: AGENTS.md, constitution, north star, design goal,
   contracts, DEC registry, existing architecture and interface documents.
2. Seed every domain that those files already decide, recording
   source_type=project_ssot with the file path. Do not ask the user about them.
3. Build one packet from templates/CONFIRMATION-PACKET.md that contains, per domain:
   the current or proposed decision, the source, the recommendation, scope, impact,
   rollback, and the explicit question confirm / modify / defer.
4. Ask only the unresolved domains, in one message. Keep it short enough to answer.
5. Record every answer with a real reference (message id, document section, or
   user-stated note) through bin/AgentOS-Contract.ps1. Never invent a reference.
6. Seal the contract with `confirm` when no required domain is pending. A deferred
   domain needs an owner waiver reference and stays visibly deferred.

Efficiency rules: one packet, no repeated questions, no per-file confirmations,
reuse of recorded decisions, and no re-asking after an answer is recorded.

## 4. Iterate later requirements as amendments

New requirements arrive during execution. Treat them as amendments, not as silent
scope growth:

- Classify the amendment: contract (changes a confirmed domain, framework, safety,
  data, interface, acceptance or quality bar) or preference (detail inside a domain).
- Contract amendments require explicit user confirmation. They never time out.
- Preference amendments use the 300-second delegated default and are recorded as
  delegated_default.
- On apply, the contract version increments and the changed domains are recorded in
  history with before/after values and the deciding source.
- Any active task whose in-scope domains intersect the changed domains becomes stale
  and must re-read the contract before continuing.

## 5. Enforce intent across long-horizon tasks

File-driven enforcement points:

- Each task records contract_version and contract_sections_in_scope.
- At every Unit boundary, resume and before any contract-dependent action, run
  `AgentOS-Contract.ps1 check`. A stale task or pending amendment is blocking.
- Checkpoints record the contract version, unresolved domains and pending amendments.
- Working memory carries the current contract version so a new session resumes against
  the same intent instead of conversation memory.
- The evidence ledger records the contract version used for each verified claim when
  the claim depends on framework intent.

## 5.1 Command reference and exit codes

    bin/AgentOS-Contract.ps1 -Command init
    bin/AgentOS-Contract.ps1 -Command set -ProjectRoot P -Domain D -Decision "..." -State confirmed -SourceType user|project_ssot -SourceRef "reference"
    bin/AgentOS-Contract.ps1 -Command confirm -ProjectRoot P -WaiverRef "owner-ref"   # only when a domain is intentionally deferred
    bin/AgentOS-Contract.ps1 -Command amend-propose -ProjectRoot P -AmendmentId A -AmendmentPath proposal.json
    bin/AgentOS-Contract.ps1 -Command amend-notify  -ProjectRoot P -AmendmentId A -NoticeRef "actual notice"
    bin/AgentOS-Contract.ps1 -Command amend-respond -ProjectRoot P -AmendmentId A -Response approve -ResponseRef "actual user message"
    bin/AgentOS-Contract.ps1 -Command amend-evaluate -ProjectRoot P -AmendmentId A
    bin/AgentOS-Contract.ps1 -Command check  -ProjectRoot P    # exit 0 pass, exit 2 blocking drift
    bin/AgentOS-Contract.ps1 -Command status -ProjectRoot P    # read-only

Only check uses process exit codes; every other command returns a JSON result
document. When the script is invoked in-process, do not read $LASTEXITCODE for
non-check commands: it may hold a value from an earlier native call. Run check in a
separate process when a hard gate is required.

## 6. Production-grade and efficient

Production-grade is an evidence property, not an interaction volume. Apply
protocols/QUALITY-GATE.md: applicable gates green with real evidence, no synthetic
substitution, independent verification, truthful delivery states. Efficiency comes
from the tiers: routine work is silent, preference work is batched and time-boxed,
contract work is confirmed once and then enforced automatically.

## 7. Boundaries

- This protocol cannot authenticate the user, force a client dialog, or create a
  scheduler. It records intent and blocks drift in files and prompts.
- Same-permission agents can bypass local files; hard enforcement needs a host-owned
  gateway.
- Do not use confirmation to manufacture acceptance: machine-verifiable deliverables
  can be delivered and verified, while real user or device acceptance stays pending.
- External design references are method sources, not dependencies. See
  protocols/DESIGN-CONSISTENCY.md for the boundary on fetching or embedding assets.