---
name: plan-before-execute
description: Create and obtain approval for a complete, evidence-driven plan before executing any non-trivial change or external action. Use for code edits, configuration changes, document creation, tests, builds, hardware motion, flashing, DOE, deployment, production parameter changes, and other work that changes state.
---

# Plan Before Execute

Use this skill for every non-trivial task. The purpose is to make the intended
work concrete, reviewable, and recoverable before changing state.

## When to apply

Apply the full workflow to code changes, configuration changes, document
creation, test or build runs that are part of delivery, hardware actions,
flashing, DOE, deployment, production parameter changes, and other stateful
work.

Use the lightweight path for simple questions, one-line read-only queries,
status checks, translations, and explanations that do not change state.

Higher-priority system instructions, project rules, safety controls, and the
user's latest request always take precedence over this skill.

## Phase 1 Gather facts

Before asking the user questions:

1. Read the applicable project rules, source-of-truth documents, current task
   state, recent checkpoints, and relevant evidence.
2. Inspect the repository, interfaces, configuration, and runtime state that
   can resolve uncertainty without changing state.
3. Separate user requirements, verified facts, observed data, derived results,
   assumptions, proposals, unknowns, and conflicts.
4. Identify safety boundaries, permissions, irreversible effects, and external
   dependencies.

Do not infer facts from filenames, screenshots, stale notes, expected output,
or an interrupted process. Do not claim that background work is running unless
its current process and evidence are directly verified.

## Phase 2 Clarify intent

Ask only questions whose answers can change the goal, scope, acceptance
criteria, safety boundary, implementation path, or rollout. Group related
questions and provide a recommended default when useful.

Before finalizing the plan, establish:

- the objective and measurable success criteria;
- the intended audience or consumer of the result;
- the in-scope and out-of-scope systems and files;
- safety, compatibility, timing, and approval constraints;
- the current state and important unknowns;
- the preferred tradeoffs when more than one implementation is viable.

## Phase 3 Write the plan

Output one complete plan inside `<proposed_plan>` and `</proposed_plan>`.
The plan must be decision-complete: an implementer should not need to invent
the workflow, interfaces, gates, or recovery behavior.

Use this structure:

```markdown
<proposed_plan>
# Title

## Summary
Goal, current state, and intended outcome.

## Scope and constraints
Allowed systems and files, non-goals, safety and compatibility limits.

## Phases and Units
Ordered phases with one controllable action per Unit and explicit dependencies.

## Interfaces and outputs
Inputs, files, commands, schemas, artifacts, and data flow.

## Verification and acceptance
Tests, evidence level, success criteria, and delivery gates.

## Failure and recovery
Stop conditions, rollback, checkpoint, escalation, and replan triggers.

## Assumptions
Explicit defaults and unresolved unknowns.
</proposed_plan>
```

Keep the plan concise enough to review, but include enough detail to prevent
unsafe or ambiguous execution. State estimated duration and log or artifact
locations when the task is long-running.

## Approval gate

For every non-trivial task, stop after presenting the plan. Wait for explicit user confirmation before execution, editing files, or taking external action.
Silence, elapsed time, a vague acknowledgement, or a previous unrelated
approval is not confirmation.

Hardware motion, flashing, power changes, production configuration, external
messages, irreversible actions, and user acceptance require their own explicit
authorization and all applicable on-site or safety preconditions even after a
plan is approved.

If the user changes the objective, scope, constraints, or acceptance criteria,
pause dependent work and produce a replacement plan before continuing.

## Execute one Unit at a time

After approval:

1. Select exactly one Unit whose dependencies are satisfied.
2. Record the intended action, scope, expected result, and rollback before
   executing it.
3. Perform the Unit and capture complete output, exit code, timestamps, and
   relevant artifact hashes.
4. Verify the Unit against its acceptance condition.
5. Update the task state and checkpoint with the result, remaining unknowns,
   and next ready Unit.
6. Re-evaluate the plan before starting the next Unit.

Do not silently broaden scope or continue through a safety failure. Do not promote a candidate into production before the stated acceptance gate passes.

## Truthful reporting

Label material claims as `verified`, `observed`, `derived`, `user-stated`,
`assumption`, `proposal`, `synthetic`, `unknown`, `conflicted`, `stale`, or
`failed` when the distinction matters. A plan is not execution evidence.
Synthetic, simulated, stale, failed, truncated, or disconnected evidence cannot
satisfy a real-device, safety, production-performance, or user-acceptance gate.

Report what changed, why it changed, how it was tested, which gates passed,
which remain open, and where the evidence is stored. Never describe a planned,
partial, or background action as completed.

## Trigger examples

- "Fix the parser" -> inspect first, write a complete plan, wait for approval,
  then implement one ready Unit.
- "Create a project report" -> plan the document structure, source evidence,
  render or export checks, and output location before creating the file.
- "Run a hardware DOE" -> plan factors, safety limits, stop conditions,
  operator prerequisites, per-round evidence, and promotion gates before any
  initialization or motion.
- "What is the current version?" -> use the lightweight read-only path.
