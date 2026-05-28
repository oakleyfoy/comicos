# P41 automation queue architecture

## Purpose

P41-01 introduces the deterministic, replay-safe automation job ledger that future workers, schedulers, batch systems, replay pipelines, and notifications will build on top of. This phase creates the durable queue foundation only. It does not execute jobs, schedule work, open sockets, or introduce worker runtime behavior.

## Queue philosophy

- Jobs are append-only ledger records, not mutable worker commands.
- Payload snapshots are stored immutably and checksummed at creation time.
- Queue ordering is deterministic and stable for identical inputs.
- History is preserved as discrete events so reservation, failure, release, and completion activity stays auditable.
- The system records issues and failures rather than silently repairing or suppressing them.

## Deterministic ordering model

Reservation selection follows a fixed ordering contract:

1. `priority` descending
2. `deterministic_rank` ascending
3. `available_at` ascending
4. `created_at` ascending
5. `id` ascending

This guarantees that repeated queue reads over the same ledger state pick the same candidate job for reservation.

## Reservation model

- Jobs move through a constrained state machine.
- Reservations require a caller-supplied token.
- Reserved jobs store both `reservation_token` and `reserved_until`.
- Reservation release is explicit and recorded in append-only history.
- The queue foundation prevents double reservation by refusing conflicting reservation state rather than overwriting it.

## Dependency model

- Dependencies are represented as explicit directed edges between jobs.
- Dependency edges are immutable once written in this phase.
- Direct cycles are rejected.
- Dependency ordering is stable by `depends_on_job_id` then `id`.
- The dependency graph is included in the deterministic manifest exported for each job.

## Replay-safe lineage model

Each job preserves deterministic lineage in the following shape:

`source_checksum` optional -> `payload_checksum` -> `job_manifest_checksum` -> `job_checksum` -> attempt metadata -> artifact checksums

The initial `job_checksum` is derived from immutable creation inputs only, which allows repeated identical creation requests to resolve to the same ledger record.

## Artifact model

Jobs support append-only artifacts with deterministic storage paths:

`automation-jobs/{queue_key}/{job_id}/{artifact_type}.{ext}`

Initial foundation artifacts:

- `JOB_PAYLOAD_SNAPSHOT`
- `JOB_MANIFEST`
- `JOB_DEBUG_PREVIEW`

Future worker/runtime phases can add execution and failure artifacts without changing the storage contract introduced here.

## Append-only guarantees

- Job history is append-only.
- Payload snapshots are immutable.
- Artifact files are written once and preserved.
- Issues are recorded as separate immutable rows.
- Queue inspection does not mutate job state.

## State transition rules

Allowed transitions in the foundation layer:

- `PENDING -> AVAILABLE`
- `AVAILABLE -> RESERVED`
- `RESERVED -> AVAILABLE`
- `RESERVED -> RUNNING`
- `RUNNING -> COMPLETED`
- `RUNNING -> FAILED`
- `FAILED -> RETRY_PENDING`
- `RETRY_PENDING -> AVAILABLE`
- `FAILED -> DEAD_LETTER`
- `AVAILABLE -> CANCELLED`

Transitions outside this set are rejected.

## Owner and org isolation

- Jobs are owner-scoped at the API layer.
- `organization_id` is stored as future-ready tenant metadata.
- Owner routes only expose records belonging to the authenticated owner.
- Ops routes are read-only and intended for diagnostics, queue health, and failure visibility.

## Non-goals

This phase explicitly does not include:

- Worker execution runtime
- Scheduler logic
- Hidden retries
- Realtime websockets
- Distributed locks
- Marketplace workflows
- Background orchestration
- Queue autoscaling
- Priority aging
