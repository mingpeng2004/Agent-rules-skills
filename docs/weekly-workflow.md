# Weekly learning and publication

Run weekly, Sunday 03:00 Asia/Shanghai. The native Codex thread automation holds
the schedule; this repository contains the workflow and portable assets only.
The host app/machine must be available for local execution. Quiet when unchanged;
notify only on meaningful improvement, publication, failure or needed decision.

1. Read local source policy and previous scan receipt. Discover projects from
   the configured project-bearing roots plus current client/project Skill roots.
   Search project rules, decisions, knowledge, postmortems and lesson records;
   skip dependencies/build output. Record inaccessible roots, missing files,
   scan bounds and hashes. Distinguish true zero, unreadable and not inspected.
2. Inspect changed evidence and the current target Skill/governance. An incident
   is separate from evidence availability; a plausible root cause is not proven.
   Propose a narrow reusable lesson, scope, counterexample and verification.
   Integrate only actually supported lessons into corresponding authored sources.
   Keep conflicting or weakly evidenced lessons proposed/blocked. No raw reports
   or measurements enter the repository.
3. Inventory all discovered Skills, preserve variant content and licensing.
   Built-in/plugin/vendor material without established redistribution permission
   remains reference-only with a visible reason; do not silently omit it. Export
   user-managed authored/configured Skills and AgentOS governed source assets.
4. Stage portable copies. Remove machine-private absolute paths and remote/local
   identifiers using explicit normalization; preserve semantics and mark generated
   placeholders in documentation. Reject credentials, PII, raw traces, dumps,
   private state, unexpected extensions, linked/reparse paths and large binaries.
   Original source hashes/paths are private; public evidence uses exported hashes.
5. Validate every export path/content/link/Skill frontmatter and run relevant
   tests. Run the existing SecurityCheck on changed code and inspect actual scan
   counts/findings. A pass on an empty or uninspected scope never counts.
   A real review records the package fingerprint and actual test outputs before
   prepare. Recompute source and package hashes immediately before publishing.
6. Publish only reviewed content to the named repository. Observe its default
   branch, prior managed manifest and exact remote file/blob IDs. Preserve
   unrelated files; concurrent changes block and need review. No force update.
   Read back HEAD/tree/blobs and compare hashes before declaring publication.
   A no-change run must not create a meaningless commit.
7. Save private receipt, source inventory, actual review, publication/readback
   and pending lessons. Update the existing task/checkpoint, not a second project
   status ledger. All original records remain local and unmodified.

## Commands

`python -B tools/weekly_learning.py scan`

Review private scan results and apply approved in-scope lessons to actual sources.

`python -B tools/weekly_learning.py stage --scan <private-scan.json>`

`python -B tools/weekly_learning.py validate --package <staged-root>`

After actual tests/review:

`python -B tools/weekly_learning.py prepare --package <staged-root> --review <review.json>`

`python -B tools/weekly_learning.py publish --ready <ready.json>`

No command infers owner approval from elapsed time. Existing weekly publication
delegation covers reviewed portable assets, never secrets or product data.
Credentials come from existing environment/credential manager, never persisted
or printed. Network errors, redirects, branch protection and failed readback
remain failed/unknown and preserve reconciliation state.
