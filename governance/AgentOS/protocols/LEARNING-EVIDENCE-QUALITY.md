# Lessons integrated from verified project failures

These controls generalize observed failure modes. Their source bindings and
counterexample results are held privately by the weekly-learning workflow.
They do not assert a root cause for any specific production incident.

## Read-state is part of every observation

Represent collection as observed_nonempty, observed_empty, unreadable,
not_inspected or failed. Count zero is valid only after successful collection
with known scope; denied access, missing schema and failed worker execution
must not be coerced into zero. A negative inventory statement needs its method,
observation time and a bounded recheck interval.

## Observation versus evidence availability

An event's occurrence and the availability of its evidence are independent
facts. Missing evidence does not prove no event; an error event alone does not
prove evidence loss when the expected artifact exists. Correlated traces,
repeated offsets or an apparent suspect do not establish causation. Preserve
raw values, alternatives and the falsifying observation for each hypothesis.

## Coverage and counterexamples before a pass

An inspector reports actual files/records enumerated, attempted, readable,
skipped and failed; a configured directory list is not inspected coverage.
Run a known failing example and require the expected rejection, then a valid
case. A zero exit code without actual records/output is insufficient.
Review the test's own parameters, discovery count and independent preconditions
before treating all-red or all-green results as implementation evidence.

## Historical data remains visible

When adding an optional field, old records must neither crash parsing nor
silently vanish from aggregation. Read missing fields safely and recompute
derived labels from authoritative raw fields. Report disagreements rather
than rewrite append-only history. New derived statistics do not reset original
run counters or replace the evidence they are intended to diagnose.

## Scope and recovery

Apply only to the relevant pipeline; do not impose a full diagnostic procedure
on every small edit. Each lesson names its actual source, affected workflow,
counterexample and verification, and is reviewed before shared publication.
Public review uses sanitized methodology and real test outcomes only.
