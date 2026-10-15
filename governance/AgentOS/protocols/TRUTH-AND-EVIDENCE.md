# AgentOS Truth and Evidence Protocol v1.1

## 1. Purpose

This protocol is a system-level hard gate for every AgentOS client, including
MiniMax Code, Kimi Code, VS Code integrations, software projects, firmware
projects and hardware-in-the-loop work.

The governing rule is:

> A statement without a traceable source is not a fact. It must be labeled
> unknown, assumption, proposal, user-stated or derived. It must not be
> presented as verified.

Agent memory, model prior knowledge, plausible values, screenshots without a
source, unfinished command output and expected results are not machine
evidence.

## 2. Claim states

Every material statement that affects a plan, implementation, safety decision,
test result, delivery decision or user-facing answer belongs to one of these
states:

| State | Meaning | Can satisfy a delivery gate |
|---|---|---|
| verified | A source exists, the evidence was checked, the hash matches, it is fresh and no conflict is active | Yes, subject to the required level |
| observed | Directly observed from a named source but not independently verified | Only where the task explicitly allows observation |
| derived | Reproducibly calculated from identified evidence | Only with the parent evidence and calculation recorded |
| user-stated | Supplied by the user; useful context, not machine verification | No |
| assumption | Working premise that has not been proven | No |
| proposal | Suggested future action or design | No |
| synthetic | Mock, demo, sample, generated, simulated or placeholder data | Never for real-world gates |
| unknown | Evidence is absent, insufficient, failed or unavailable | No |
| conflicted | Two or more applicable sources disagree | No |
| stale | Evidence existed but is outside its freshness window | No |

The label belongs next to the claim in the task, checkpoint, report and final
answer. Do not write a bare PASS, version, device state, performance number or
acceptance result without its state and evidence reference.

## 3. Source and evidence requirements

The append-only ledger is:

    <project>/.agentos/evidence/claims.jsonl

Each claim event must contain:

- claim_id and claim_text
- event type and state
- source and source_type
- observed_at and validated_at
- validation_method
- evidence_level
- artifact_path when an artifact exists
- SHA256 of the artifact when an artifact exists
- data_class: real, synthetic, mixed or unknown
- applicability and freshness/expiration
- reason or conflict detail when relevant

Allowed source types are file, command, test, device, user, url, model,
synthetic and none.

Rules:

1. verified requires a non-empty source, a permitted source type, a validation
   method, an evidence level above E0 and a current hash when an artifact is
   used.
2. model, none and user sources can never produce verified machine facts.
3. A command is evidence only when its complete output, exit code and time are
   saved as an artifact. A timeout, failure, truncated output or disconnected
   device is a failed/unknown result.
4. A URL is evidence only through a saved snapshot or downloaded artifact whose
   hash is recorded. AgentOS does not silently fetch or trust a remote page.
5. User statements remain user-stated unless a separate machine source verifies
   them.
6. A derived claim must name its parent claim IDs and the calculation method.
7. A high-risk or externally visible claim needs two independent evidence
   sources, or one reproducible primary source explicitly marked as such.
8. A claim about real hardware, user acceptance or real-world motion requires
   E4. E2/E3, simulation and generated values cannot be promoted to E4.
9. Synthetic or mixed data must be visibly labeled and isolated from real
   evidence. Synthetic data cannot satisfy real-device, user-acceptance,
   production-performance or safety gates.
10. Conflicting evidence blocks verified status. Do not choose a convenient
    source silently; record the conflict and escalate.
11. Dynamic facts must have a freshness window. Expired evidence is stale until
    re-observed and re-verified.
12. Evidence files are append-only. A correction adds an invalidation,
    conflict or new verification event; it does not rewrite history.

## 4. Evidence levels

| Level | Minimum meaning |
|---|---|
| E0 | Model reasoning or no machine evidence |
| E1 | Static file, configuration or source inspection |
| E2 | Unit test, compile or deterministic local check |
| E3 | Integration, simulator, hardware-in-loop, performance or long-run check |
| E4 | Real device behavior, real deployment or explicit user acceptance |

E3 means the integration or simulation actually ran and its complete evidence
exists. It does not mean that a simulator is a real device.

## 5. Answer preflight

Before an Agent answers:

1. Extract material factual claims from the planned answer.
2. Find the ledger event or source for each claim.
3. Re-check freshness and hash for dynamic or high-risk claims.
4. Label every unresolved claim as unknown, assumption, proposal, user-stated,
   synthetic, conflicted or stale.
5. Refuse to manufacture missing values. Say what is missing and how to obtain
   it.
6. Do not say completed, passed, installed, connected, flashed, accepted or
   verified unless the applicable gate is satisfied.

## 6. Agent handoff

At the start of every new conversation, read runtime/AGENT-IMPORT.md and then
runtime/BOOT.md. A new model or client inherits the protocol from these files;
it does not inherit unrecorded claims from the previous conversation.

