# AgentOS Harness Enhancement Review v1.1

This protocol records which ideas from the user-supplied reference report are
adopted and which remain hypotheses.

## Adopted controls

| Reference idea | AgentOS implementation | Boundary |
|---|---|---|
| Structured task protocol | TASK-PROTOCOL.md and task template | Structure does not validate facts by itself |
| Separate facts, data and instructions | Truth labels plus task sections | Every factual claim still needs a source |
| XML or tagged anchors | Portable structural envelope | Tags are not a security boundary |
| Durable working memory | .agentos/working-memory.json and checkpoints | Projection is not the evidence ledger |
| Context compaction and overflow recovery | CONTEXT-PIPELINE.md and resume flow | Automatic eviction depends on client APIs |
| Recursive planning and refine | RECURSIVE-PLANNING.md | One ready Unit at a time |
| Partial harness | Explicit gates plus bounded worker autonomy | High-risk actions remain constrained |
| Interleaved execution | Observe/decide/act/verify record | Hidden chain-of-thought is not requested |
| External verifier | Quality gate, evidence validation and role router | Same-source self-approval is insufficient |

## Not accepted as facts

The reference report's percentages, named research outcomes, model capability
claims and performance improvements have not been independently verified in
this environment. They are hypotheses or user-provided recommendations until
an experiment records source, setup, data, artifact and result in the evidence
ledger. They must not appear as guaranteed AgentOS performance.

## Experiment rule

Any claim that the new harness improves pass rate, token use, recovery time or
long-run completion must be tested against a named baseline with:

- identical task set and acceptance criteria
- recorded model/client versions
- real command logs and complete outputs
- separate training/demo/synthetic data labels
- reproducible analysis code
- at least one independent review

Until then, use the language "design hypothesis" or "proposed control".

