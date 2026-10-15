# AgentOS Context Pipeline and Recovery v1.1

## Durable state first

The durable project state is authoritative:

- .agentos/project.json
- .agentos/status.json
- .agentos/working-memory.json
- .agentos/tasks/
- .agentos/checkpoints/
- .agentos/evidence/claims.jsonl

Conversation history is a cache. A new conversation must be able to resume
from the durable files alone.

## Working memory fields

working-memory.json contains only a compact, current projection:

- objective and active task
- current Phase/Task/Unit
- verified claim IDs and evidence references
- open unknowns and conflicts
- rejected assumptions
- last checkpoint
- one next action
- updated_at

It must never contain a copied test result without its claim ID and source.
When a claim changes, append to the evidence ledger first, then refresh this
projection.

## Context pressure policy

When a client exposes a context limit or overflow event:

1. Persist the current state and complete tool outputs to files.
2. Keep objective, constraints, current Unit, unknowns, conflicts and the
   latest evidence references in the active prompt.
3. Evict bulky tool output only after its artifact path and SHA256 are saved.
4. Reload from the durable files and validate the ledger.
5. Resume from the last verified boundary, never from an imagined memory.

If the client has no compaction hook, agents must perform this protocol at
every checkpoint and before a long response. AgentOS cannot claim that it has
performed automatic token eviction unless the client reports that event.

## External feedback

The verifier, test runner, compiler, device and user acceptance are external
feedback channels. Model self-consistency is not a substitute for them.
Failed, missing or contradictory feedback keeps the task in failed, unknown,
conflicted or blocked state.

