# Embedded and Firmware Project Profile v1.1

## File-driven engineering

For nontrivial engineering, read `protocols/FILE-DRIVEN-ENGINEERING.md` and
resolve the registered/installed engineering Skill core. Map goals, framework,
Phase/Task/Unit plan, acceptance and checkpoint to existing project SSOT and
AgentOS state; do not duplicate state or rewrite locked project rules. Approved
scope drives autonomous engineering closure while physical/user acceptance
remains evidence-bound. Original project rules retain priority.

Engineering governance extension: read `protocols/FILE-DRIVEN-ENGINEERING.md`
and resolve its registered Skill core for goal/framework/plan/acceptance/state
document mapping, MD/DOCX synchronization and cross-client recovery. This adds
guidance only; existing project/AgentOS safety and evidence rules remain in force.

## Required inputs

- MCU, board, clock, toolchain and target hardware identity
- Protocol contract, frame format, byte order, timeout and compatibility rules
- Hardware safety definition, power state, current firmware and host version
- Real trace, build artifact, symbol/map output and reproducible test command

## Truth gates

- A compiler or host test is E2, not a real-device result.
- A simulator or hardware-in-loop run is E3, not a real-device result.
- Flashing, motion, power and user acceptance require E4 evidence.
- Device identity, connection state, firmware version and flash result must
  come from a named device/tool artifact, not model memory or expectation.
- Synthetic sensor values and generated traces must be labeled and cannot
  satisfy safety, production-performance or user-acceptance gates.
- A disconnected, timed-out, partial or truncated trace is failed or unknown.

## Change gates

- Protocol, pin, timing, safety, power and motion changes require an explicit
  decision record and rollback path.
- Verify one protocol or control behavior per Unit. Record time, command,
  device identity, state, exit code, trace path and SHA256.
- Host and firmware changes are separate Units unless their integration
  evidence is explicitly defined.
- Stop before hardware action when the workpiece, power, emergency stop,
  current firmware or target identity is unknown.

## Evidence chain

requirements -> constraints -> unit test -> host/simulation -> integration or
hardware-in-loop -> flash record -> device trace -> version check -> real
device result -> user acceptance

The chain is not complete when an intermediate node is missing. Register each
material statement through bin/AgentOS-Evidence.ps1 and validate the ledger
before delivery.
