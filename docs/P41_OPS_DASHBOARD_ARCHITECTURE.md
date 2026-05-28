# P41 Ops Automation Dashboard Architecture

## Philosophy

P41-07 introduces a deterministic, replay-safe operational visibility layer for ComicOS automation infrastructure. Ops snapshots, metrics, audits, and controls are append-only: nothing mutates historical payloads or erases lineage.

## System health model

`AutomationOpsSnapshot` rows aggregate queue depth, worker runtime, workflow activity, failed jobs, dead-letter backlog, replay warnings, and checksum warnings. Snapshot status derives deterministically from aggregated counts (`HEALTHY` → `CRITICAL`).

Snapshot types include `SYSTEM_HEALTH`, `WORKER_RUNTIME`, `QUEUE_STATE`, `RECOVERY_STATE`, `BATCH_STATE`, `NOTIFICATION_STATE`, and `REPLAY_STATE`.

## Deterministic metrics model

Metrics are materialized per snapshot with stable ordering:

1. `metric_category` ascending  
2. `metric_rank` ascending  
3. `metric_key` ascending  

Each metric carries an immutable checksum over its canonical payload.

## Audit model

Ops audits (`QUEUE_AUDIT`, `WORKER_AUDIT`, `REPLAY_AUDIT`, `STORAGE_AUDIT`, `CHECKSUM_AUDIT`, `DEAD_LETTER_AUDIT`, `NOTIFICATION_AUDIT`) produce immutable `audit_result_json` and `audit_checksum` values. Audits are replay-key idempotent.

## Safe admin control model

Allowed controls: pause/resume queue, pause/resume workflow, acknowledge alert/failure, replay verify, maintenance lock. Destructive controls (delete queue, purge dead letter, force replay overwrite) are rejected.

Controls record `control_snapshot_json` and append history events; they do not bypass replay integrity.

## Replay-safe ops guarantees

- Snapshot checksum incorporates manifest checksum lineage (metrics, audits, controls, issues, artifacts).  
- Repeated identical inputs yield identical snapshot rows (owner + snapshot key replay).  
- Artifacts stored under `automation-ops/{snapshot_type}/{snapshot_id}/{artifact_type}.{ext}`.

## Non-goals

- Destructive admin tooling  
- Realtime websockets / streaming telemetry  
- Distributed ops coordination or autoscaling control planes  
- ML anomaly detection or external observability backends  
