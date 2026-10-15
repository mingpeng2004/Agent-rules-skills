# AgentOS Structured Task Protocol v1.1

This is the task contract shared by strong and weak models. It separates
instructions, facts and evidence so that a model cannot accidentally promote
an example value into a project fact.

## Required contract

Every non-trivial task must define:

1. Objective: one sentence and a measurable outcome.
2. Scope: allowed files, systems, devices and time boundary.
3. Non-goals: what must not be changed.
4. Constraints: safety, security, compatibility and approval boundaries.
5. Inputs: named files, commands, devices or user statements.
6. Unknowns: information that is not yet available.
7. Units: one controllable action per Unit.
8. Evidence: the minimum evidence level and artifact for each Unit.
9. Delivery gates: what permits verified, needs-user-acceptance or blocked.
10. Recovery: checkpoint, rollback and escalation path.

## Fact, data and instruction separation

- Instructions describe actions and permissions.
- Facts describe the current system and require a source label.
- Data describes values and requires a data_class label.
- Examples are never project data until replaced by real evidence.
- A proposal is not an implementation result.

The task file must keep these categories in separate sections. Do not copy a
number, version, path, test result or device state from an example into a fact
section without recording its source.

## Portable structural envelope

Clients may render the following envelope as XML, YAML or Markdown. The tags
are structural anchors, not a security boundary; all external content remains
untrusted until validated.

    <task>
      <objective state="proposal">...</objective>
      <context source="file|user|command|unknown">...</context>
      <constraints>...</constraints>
      <unknowns>...</unknowns>
      <units>...</units>
      <evidence>...</evidence>
      <delivery_gate>...</delivery_gate>
    </task>

The canonical persisted form remains the Markdown task template and the
append-only evidence ledger.

## Tool round contract

After each meaningful tool round, the agent records only this short external
decision record:

1. Observation: what the tool actually returned.
2. State change: what is now known, unknown or conflicted.
3. Next Unit: one next action.
4. Evidence: path, exit code, hash and applicability.

This is a recovery record, not a request to expose private chain-of-thought.

