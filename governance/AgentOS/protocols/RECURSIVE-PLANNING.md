# AgentOS Recursive Planning Protocol v1.1

## Principle

The coordinator plans the whole shape, but the worker executes only the first
ready Unit. The next plan is refined from observed evidence instead of being
blindly executed from a stale prediction.

## Plan -> execute -> refine

1. Build a Phase/Task/Unit tree with dependencies and a measurable green
   condition.
2. Mark exactly one Unit as ready for the active worker.
3. Execute that Unit and capture complete evidence.
4. Verify the result against the current task contract and truth ledger.
5. Update the parent task with the actual result, newly discovered unknowns and
   changed dependencies.
6. Refine, merge or split remaining Units.
7. Re-inject the parent objective, constraints and delivery gate before the
   next Unit.

A completed Unit does not prove that its parent Task or Phase is complete.
Never mark a predicted result as actual evidence.

## Granularity rule

Split when a Unit has more than one independent green condition, crosses a
permission boundary, touches a different artifact set or cannot be rolled back
as one action. Keep a Unit together when splitting would destroy the evidence
meaning or create coordination overhead without a separate acceptance test.

## Partial-harness rule

The harness fully specifies:

- objective, safety boundary, allowed scope and non-goals
- required evidence, freshness and delivery gate
- stop conditions, approval boundaries and recovery path

The harness intentionally leaves low-risk implementation choices to the
worker. It must not prescribe a long sequence of speculative commands. At
critical transitions, the harness requires a check; between them, the worker
may choose the efficient route and must still record evidence.

## Interleaved execution record

Clients that support reasoning between tool calls should use:

    observe -> decide one Unit -> act -> verify -> checkpoint

Clients that do not expose that control must emulate it through the task file,
checkpoint and evidence ledger. AgentOS does not claim to control hidden model
reasoning.

