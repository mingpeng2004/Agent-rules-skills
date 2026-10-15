# Confirmation Packet - {{PROJECT_NAME}} - {{DATE}}

> One packet, asked once, before implementation. Answer with confirm / modify / defer
> per line. Items already decided by project files are marked "seeded" and need no
> answer unless you disagree. Silence never confirms a framework-level item.

Contract version: draft | Contract file: .agentos/contract/contract.json
Protocol: protocols/UPFRONT-CONFIRMATION.md | Policy: policies/INTERACTION-POLICY.json

## How to answer

- confirm: keep the recommendation as the contract decision
- modify: state the change; it is recorded as your decision with this message as source
- defer: state the reason; the domain stays open and dependent work is blocked

Unknowns are shown as unknown. They are not filled with defaults.

## Contract-level items (explicit confirmation, no timeout)

| # | Domain | Seeded / proposed decision | Source | Recommendation and why | Impact if changed | Rollback | Your answer |
|---|---|---|---|---|---|---|---|
| 1 | product_goal | | | | | | |
| 2 | scope_and_non_goals | | | | | | |
| 3 | quality_bar | | | | | | |
| 4 | tech_stack | | | | | | |
| 5 | architecture | | | | | | |
| 6 | interfaces_contracts | | | | | | |
| 7 | data_and_storage | | | | | | |
| 8 | ui_and_interaction | | | | | | |
| 9 | safety_and_hardware | | | | | | |
| 10 | security_and_privacy | | | | | | |
| 11 | ops_and_maintenance | | | | | | |
| 12 | acceptance_and_delivery | | | | | | |

## Open questions (only these need an answer)

- Q1:
- Q2:

## What happens after you answer

1. Answers are recorded in the contract with this message as the source reference.
2. Deferred items stay visibly deferred and block the tasks that depend on them.
3. Later requirements come back as amendments against this contract, not as new
   questions about settled domains.
4. Routine implementation inside confirmed items proceeds without further questions.

## Not covered by this packet

- Preference-level detail choices during implementation (handled by the 300-second
  delegated default).
- Safety approvals for concrete actions (always explicit, never timed).
- Real user or device acceptance (recorded from actual evidence only).