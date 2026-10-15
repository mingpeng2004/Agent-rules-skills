# AgentOS Quality Gate v1.1

For routed tasks, also use protocols/SKILL-MATRIX.md and bin/agentos_skills.py
gate to bind declared outputs to current input/policy/provider hashes and
latest evidence plus a distinct verifier's concrete checks. Passing structural
registration or routing is not verified output. Production/device claims retain
their real-world evidence requirement. The local checker cannot authenticate
reviewer identities or replace project acceptance and native safety controls.

## Gate matrix

| Gate | Software | Firmware and hardware | Minimum evidence |
|---|---|---|---|
| Requirement traceability | required | required | E1 |
| Static inspection | required | required | E1 |
| Unit test or compile | applicable | applicable | E2 |
| Integration, simulator or HIL | applicable | applicable | E3 |
| Security audit | required | required | E2 |
| Performance or long run | when claimed | when claimed | E3 |
| Real device behavior | when claimed | required for device claims | E4 |
| User acceptance | when required | when required | E4 |

## Truth conditions

1. A gate is green only when the evidence ledger contains a matching claim,
   source, validation method, applicability, freshness and artifact hash.
2. The claim must meet the minimum evidence level for its applicability.
3. Synthetic, mock, demo or simulated data cannot satisfy real-device,
   production-performance, safety or user-acceptance gates.
4. A failed, timed-out, disconnected or truncated command is not a pass.
5. Conflicted or stale evidence keeps the gate blocked.
6. The verifier must independently inspect the result; repeating the same
   model assertion is not independent evidence.

## Delivery states

- verified: all applicable gates have valid evidence and no blocking conflict.
- needs-user-acceptance: machine gates are complete but explicit user or real
  device acceptance is still required.
- blocked: a prerequisite, approval, device, source or evidence gate is absent.
- failed: a gate ran and did not pass; replan from the failure.
- claimed: implementation or analysis exists but evidence is incomplete.

The allowed transition is planned -> ready -> in_progress -> verifying ->
verified. Exceptions go to blocked, failed or escalated. Do not jump from
planned to delivered or from failed to verified.

## Evidence record

Each result must include:

    [time] [claim_id] [state] [command/action] [exit code/result]
    [artifact path] [SHA256] [applicability] [level] [freshness]

Use bin/AgentOS-Evidence.ps1 and
protocols/TRUTH-AND-EVIDENCE.md. A paraphrase, screenshot without provenance,
truncated output or expected result is not sufficient.

## Production-grade bar

Production-grade is an evidence property of the deliverable, not a measure of how
many questions were asked. A deliverable is production-grade when every applicable
gate above is green with real evidence, plus:

| Aspect | Requirement |
|---|---|
| Correctness | Requirement traceability plus the applicable test/compile gate |
| Failure behavior | Errors are controlled, diagnosable and state is reconstructable |
| Security | Security audit green; no new attack surface; controls respected |
| Operability | Logs, health signals, rollback and recovery path exist |
| Compatibility | Locked contracts unchanged, or changed through a registered decision |
| Documentation | Public interfaces, contracts and the delivery record are current |
| Acceptance | Explicitly stated as verified, needs-user-acceptance or blocked |

Two failures block delivery equally: confirming everything while evidence is missing,
and having evidence while the contract is unconfirmed.

## Efficiency rules

Quality and speed are not opposites. Efficiency comes from removing ceremony, not
removing gates:

- Confirm the framework once, up front, in one packet (UPFRONT-CONFIRMATION.md), then
  execute routine work without further questions.
- Batch amendments per requirement instead of per file or per screen.
- Run verification once per deliverable with an independent check; do not repeat the
  same self-assertion.
- Reuse recorded evidence while it is fresh and its source hash still matches;
  invalidate it when the artifact changes.
- Prefer one authoritative record per fact; refresh a projection instead of appending
  duplicates.
- Keep the number of in-flight unknowns small: finish and record before opening new ones.

## Contract binding

When a project has a confirmed contract, each task records contract_version and
contract_sections_in_scope, and bin/AgentOS-Contract.ps1 check runs at unit
boundaries and on resume. A stale task or a pending contract amendment is blocking.
Claims that depend on framework intent record the contract version they were verified
against.
