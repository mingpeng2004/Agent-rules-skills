# Agent rules and skills

Portable AgentOS governance, reusable Skill variants and verification evidence.
An owner-authorized weekly workflow collects lessons from local projects,
checks their evidence, integrates relevant improvements and publishes reviewed
changes to this repository. Local project records and machine configuration
are not part of the public package.

## Layout

- `governance/AgentOS/`: authoritative portable governance runtime and protocols.
- `skills/`: unique reviewed Skill variants, each with provenance in catalog.json.
- `catalog.json`: every discovered Skill identity, exported variants or explicit
  reference-only/excluded status, normalized hashes and source category.
- `evidence/`: sanitized actual validation output and publication manifests.
- `tools/weekly_learning.py`: reproducible scan/stage/validate/prepare/publish.
- `docs/weekly-workflow.md`: cadence, review, privacy, recovery and limitations.

Preserve the original license/attribution of third-party materials. A directory
entry does not establish a redistribution right, tool availability or model
capability. Vendor-bundled skills without reviewed redistribution rights are
indexed only. Similar names with different contents are preserved as distinct
variants; client priorities and safety constraints remain explicit.

The local machine's native weekly scheduler operates outside this repository.
A configured schedule is not evidence that a future run has fired. No promise
of model parity, standards certification or uninterrupted execution is made.
