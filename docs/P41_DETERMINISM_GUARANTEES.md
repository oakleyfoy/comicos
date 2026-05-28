# P41 Determinism Guarantees

## What P41 guarantees

These guarantees apply when inputs (payloads, replay keys, owner scope, and upstream row sets) are identical.

### Queue / jobs (P41-01)

- Job selection respects queue ordering with `deterministic_rank` and stable tie-breakers (`id`).
- Payload snapshots and `job_checksum` are derived from canonical JSON serialization.
- Job history events are append-only with deterministic `event_checksum` inputs.

### Worker runtime (P41-02)

- Lease tokens and execution ranks produce stable execution checksums for the same worker/job/rank snapshot.
- Heartbeat ordering is time-ordered but checksums exclude nondeterministic wall clock where required by tests.

### Workflow scheduling (P41-03)

- Workflow step ordering by `step_rank`.
- Execution manifests and checksums stable for identical workflow/trigger/schedule inputs.
- Ops processing endpoints use deterministic ordering when selecting due work.

### Retry / recovery (P41-04)

- Retry policies use deterministic backoff when `deterministic_backoff_enabled` (no random jitter in P41).
- Recovery run checksums incorporate policy and job lineage fields.
- Dead-letter promotion is ledger-based, not probabilistic.

### Batch / maintenance (P41-05)

- Chunk partitioning is deterministic for a given item count and partition configuration.
- Chunk and batch checksums stable for identical partition inputs.
- Maintenance results append-only.

### Notifications (P41-06)

- Notification and delivery checksums from canonical payloads.
- Delivery ordering by `delivery_rank`.
- Template resolution is deterministic for the same template key/version checksum.

### Ops dashboard (P41-07)

- Metric ordering: category → rank → key.
- Snapshot idempotency on owner + `snapshot_key`.
- Manifest checksum aggregates ordered child lineage.

### Rules engine (P41-08)

- Expression evaluation via restricted AST (no imports, no calls).
- Action ordering: rank → type → scope.
- Evaluation idempotency on rule version + evaluation inputs + replay key.

### Analytics (P41-09)

- Metric ordering: category → rank → key.
- Trend/comparison ordering documented in analytics architecture.
- Snapshot idempotency on owner + analytics type + replay key.

## Replay-safe assumptions

- Clients supply explicit `replay_key` (or phase-equivalent keys) for idempotent creates.
- Database state for dependent entities (queues, workflows, policies) is unchanged between replay attempts.
- Clock time may appear in `created_at` fields but must not alter idempotent checksum keys used for deduplication.

## What is intentionally deferred

- Randomized retry jitter
- ML-driven routing, prioritization, or rule generation
- Realtime stream processing or websocket ordering
- Distributed locks across nodes
- Autoscaling changing concurrency dynamically
- External cron/event buses replacing internal schedule ledger

## Known limitations

- **Single-node semantics:** leases and workers assume cooperative single-deployment behavior; split-brain across hosts is not solved in P41.
- **Global counts in ops/analytics:** some aggregates scan tables globally then filter by owner via job/snapshot ids—correct for isolation but not optimized for huge multi-tenant scale (P42+).
- **Time-based schedules:** activation depends on `next_run_at` vs current time when ops processing runs—deterministic given a fixed “now” in tests, wall-clock dependent in production unless externally scheduled.
- **Full pytest suite:** market/listing modules may fail independently of P41; use focused automation tests for P41 sign-off.

## Verification

Focused tests under `apps/api/tests/test_automation_*.py` assert checksum stability, ordering, isolation, and idempotent POST behavior. See [P41_HARDENING_REPORT.md](./P41_HARDENING_REPORT.md).
