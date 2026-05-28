# P41 Rules Engine Architecture

## Rules philosophy

P41-08 introduces a deterministic, replay-safe automation rules engine for ComicOS. Rules are versioned, evaluations are immutable, action sequencing is stable, and history is append-only. The engine is policy infrastructure, not an adaptive or AI-authored system.

## Deterministic evaluation model

- Rule categories and rule keys define stable ordering across evaluation cycles.
- Rule expressions are parsed with a restricted deterministic expression grammar: equality, inequality, threshold comparisons, and boolean combinations only.
- No arbitrary code execution, dynamic scripting, imports, or runtime callbacks are permitted.
- Repeated identical replay inputs produce the same evaluation checksum and return the same persisted evaluation row.

## Action sequencing model

Actions are normalized and ordered by:

1. `action_rank`
2. `action_type`
3. `target_scope`

Supported actions stay within safe automation boundaries: notification creation, alert creation, workflow execution, queue pause/resume, recovery run creation, batch job creation, alert acknowledgement, and replay verification.

## Replay-safe rule lineage

Each evaluation preserves lineage from:

- rule version checksum
- evaluation input snapshot
- evaluation result snapshot
- deterministic action lineage
- manifest payload
- artifact checksums

Artifacts are stored under `automation-rules/{rule_key}/{evaluation_id}/{artifact_type}.json`.

## Versioning model

- Rules are mutable only at the rule pointer level (`current_version_id`).
- Rule versions are append-only and never overwritten.
- New versions receive monotonically increasing version numbers.
- History records rule creation, version creation, evaluation execution, and action execution.

## Non-goals

- ML-driven rule generation
- Realtime stream processing
- Distributed rule clusters
- Arbitrary scripting engines
- Visual rule builders
- Cloud-scale rule orchestration
- Adaptive automation policies
