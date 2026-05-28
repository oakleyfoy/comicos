# P41 Recovery Architecture

## Purpose

P41-04 adds the deterministic retry, failure recovery, dead-letter, and replay-recovery layer for ComicOS automation. This phase preserves immutable job and worker lineage while giving operations a replay-safe path to retry failed work, quarantine exhausted jobs, recover stale executions, and track failure escalation without hidden retries.

## Retry philosophy

- Retry decisions are explicit and policy-driven.
- Policies are immutable snapshots with deterministic policy checksums.
- Backoff timing is deterministic and uses no jitter.
- Recovery runs record what happened rather than mutating or hiding prior failures.

## Dead-letter model

- Jobs enter dead-letter only after explicit transfer or retry exhaustion.
- The original job record is preserved and never deleted.
- Dead-letter records capture failure count, source checksum, dead-letter checksum, and immutable metadata.
- Replay recovery can resolve dead-letter records while preserving the original failure lineage.

## Replay recovery model

- Replay recovery reuses the original immutable payload snapshot.
- Replayed jobs keep original job references through `parent_job_id`, `source_record_type`, and `source_checksum`.
- Recovery manifests preserve both the original job checksum and the replay job checksum.
- Dead-letter lineage remains visible even after replay recovery succeeds.

## Deterministic retry ordering

- Retry delay is computed from immutable policy configuration and current attempt count.
- Supported modes are fixed delay, linear backoff, exponential backoff, and manual-only.
- Recovery runs are ordered deterministically by per-job recovery rank.
- Identical retry input produces the same recovery checksum and the same manifest content.

## Failure lineage model

- Failure events capture immutable snapshots of job or execution failure context.
- Recovery runs reference failure events rather than overwriting them.
- Recovery issues and history are append-only.
- Critical failures remain queryable for ops diagnostics and owner-facing visibility.

## Replay-safe recovery guarantees

- No random jitter
- No hidden retries
- No destructive cleanup of original jobs
- No mutation of immutable payload snapshots
- No mutation of append-only recovery history
- Stable artifact storage under `automation-recovery/{recovery_type}/{recovery_run_id}/...`

## Non-goals

- Distributed retry orchestration
- Autoscaling retry workers
- External queue systems
- Randomized retry optimization
- ML-driven retry policies
- Automatic dead-letter replay
- Distributed replay recovery
