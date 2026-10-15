# Capability contracts and operation

## Discovery and route

The registry maps capabilities to methods, not to imaginary independent agents.
`mapped` means existing authored guidance; `protocol` means the workflow below;
`candidate` means a missing specialist deployment. None implies verified project
results. Actual providers are resolved at route time (project, current client,
bundled fallback), read and hashed. The selected provider's identity must match.
Only the chosen resources enter the context pack. Installed file parity is not
proof that a client/model automatically invoked the skill.

```powershell
python "$env:AGENTOS_HOME\bin\agentos_skills.py" validate
python "$env:AGENTOS_HOME\bin\agentos_skills.py" catalog
python "$env:AGENTOS_HOME\bin\agentos_skills.py" route --project $project --client minimax --task 'Review this skill registry change' --capability meta-skill-registry --constraint qa-fmea --input task=.agentos/tasks/task-id.md --input goals=AGENTS.md --input constraints=AGENTS.md --result .agentos/reports/registry-review.md --risk software --save .agentos/skill-runs/route-id.json
python "$env:AGENTOS_HOME\bin\agentos_skills.py" gate --project $project --plan $route --claim claim-id --verifier .agentos/reports/review-id.json --save .agentos/skill-runs/gate-id.json
```

CLI reports are create-only in the private `.agentos/skill-runs/` directory.
Exit 0 confirms the named inspection completed, exit 2 means blocked. A route
does not execute anything. Existing task/project locks and approval controls
remain necessary. An upstream edge tells the Coordinator which missing input
to obtain; the CLI does not silently execute that skill or invent its output.

Inputs are verified files plus existing governance/contract bindings. If a
file changes, obtain a new route after re-aligning the affected task. Outputs
cannot overwrite an input or ledger. Latest claim events must match required
level, applicability, freshness, data class, actual artifact hash and Unit.
Record claims using the existing evidence tool, after the actual work succeeds.

Risk classes: static=E1; software=E2 unit/compile; integration=E3 integration;
physical=E4 real-device/safety; production=E4 real-device/user-acceptance.
Risk is declared from the task; these defaults cannot lower any project gate.
Simulation output remains simulation and cannot satisfy physical/production.
The CLI refuses synthetic/mixed evidence at this delivery gate. Synthetic test
inputs are legitimate when clearly labeled and used to verify software behavior.

Verifier JSON (real filled values required, not the placeholders below):

```json
{
  "route_id": "ID from the saved route",
  "output_sha256": "current result digest",
  "reviewer": "actual distinct reviewer/tool",
  "producer": "actual implementation producer",
  "checks": [{"criterion": "task DoD item", "result": "pass", "evidence": "actual test artifact/ref"}],
  "reviewed_at": "actual timezone-aware timestamp"
}
```

Checkers require distinct, nonempty producer/reviewer identifiers, a result
hash and concrete checks. Caller-supplied identifiers are not authenticated.
Optional same-permission tools are bypassable; do not claim host isolation.

## Requirements, planning and graph

Map each requirement ID to an interface/design decision, current Unit and
acceptance claim. The project remains the SSOT. Freeze source hashes and known
constraints, preserving unknowns. Build WBS/Phase/Task/Unit dependencies, plan
the next ready Unit in detail, and roll forward after evidence. Parallelize
independent files/resources only. Do not create roles for their own sake.
Factual estimates, cost, probability and timing require a source; unknown
numbers are not replaced by made-up RPNs or delivery dates.

## qa-fmea / plan-risk

Use `templates/ENGINEERING-REVIEW.md` in AgentOS, or an existing project format.
For each safety/data/availability failure, record the effect, cause hypothesis,
actual observation, detection, containment, responsible owner and verification
case. Distinguish known incidents from hypotheses. Use probability/severity
scales only if project-defined with evidence; otherwise order by concrete
consequence and uncertainty. Tie each mitigation to a negative test or real
device test, never mark residual risk accepted without authority.

## qa-vmodel / qa-review-checklist

Pair each design level with its verification: user requirement -> user/device
acceptance; system/interface -> integration/compatibility; module -> unit or
compile/static checks. Name the exact commands, inputs and artifacts from the
project. Tests must exercise the contract: known bad result rejected, not just
a key present in a file. Review scope and counterexamples independently of the
implementation; author self-assertion is not a reviewer.

## plan-gate

Use an applicable gate, not all four ceremonies for a one-line edit:
SRR -> goal/requirements/acceptance trace; PDR -> architecture/interfaces/risk;
CDR -> design/budgets/implementation checks; TRR -> test prerequisites/recovery
and authorized operation. Each gate records pass/fail/unknown, unmet criteria,
evidence and allowed next phase. Unknown prerequisites block dependent work.
These are internal review names, not standards compliance certifications.

## mfg-change

Use change ID, reason, baseline hash, impacted requirement/contract/interface,
scope, compatibility/migration, safety preconditions, rollback and test plan.
User decisions and existing approvals are reused within scope. Apply the
existing amendment protocol if a confirmed framework changes. After verification,
update only the authoritative baseline and invalidate affected stale evidence.
This method does not implement PPAP, NPI, SPC or certify production hardware.

## km-postmortem / km-lessons

Capture observed incident separately from evidence availability and inferred
cause. Preserve raw history. When aggregating old records, safely read missing
fields and recompute derived labels from original values; missing data is
unknown, not zero or absence. Feed a reproducible counterexample into a specific
checklist/tool change, then verify it catches the known failure.

```powershell
python "$env:AGENTOS_HOME\bin\agentos_skills.py" feedback --project $project --capability meta-qc-gate --source .agentos/reports/actual-review.md --summary 'Document the observed false pass and the proposed negative check' --save .agentos/skill-runs/lesson-id.json
```

72-hour `review_due_at` is an auditable target. Actual scheduling, notifications,
shared-skill modification and publication require existing authorized workflows.
Do not auto-install new dependencies, promote every anecdote to a universal
rule, or claim a lesson was deployed because a proposal file exists.
