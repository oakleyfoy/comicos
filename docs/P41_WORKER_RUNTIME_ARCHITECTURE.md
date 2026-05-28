# P41 worker runtime architecture

## Purpose

P41-02 adds the deterministic worker runtime that safely acquires queue jobs, records worker heartbeats, preserves execution lineage, and finalizes jobs without introducing scheduling or distributed orchestration.

## Worker runtime philosophy

- Workers are durable ledger records, not ephemeral hidden processes.
- Reservations and executions must be tied to explicit worker ownership.
- Heartbeats are append-only observations that support stale detection without realtime sockets.
- Execution snapshots are immutable and checksummed.
- Failures are recorded as issues and history events instead of being silently repaired.

## Lease model

- Lease acquisition reuses the deterministic queue ordering defined in P41-01.
- Each lease is identified by a required reservation token.
- Leases expire at an explicit timestamp and can be renewed only while active.
- Expired leases are released in deterministic order by `lease_expires_at`, then `id`.
- Lease conflicts and expiration events are preserved in append-only worker history and issue ledgers.

## Heartbeat model

- Workers append heartbeat rows instead of overwriting runtime traces.
- `last_heartbeat_at` is updated for fast stale checks, while the detailed history remains preserved in heartbeat rows.
- Heartbeat statuses support `HEALTHY`, `DEGRADED`, `OVERLOADED`, and `LOST`.
- Stale detection is based on deterministic timestamp comparisons rather than sockets or push channels.

## Execution lineage model

Execution lineage is preserved as:

`job_checksum` -> lease metadata -> execution snapshot -> execution manifest -> execution_checksum -> stored artifact refs

Each execution snapshot includes:

- worker identity and scope
- lease metadata
- job lineage metadata
- execution rank
- runtime metadata

## Deterministic reservation model

The worker runtime does not invent its own queue ordering. It relies on the queue foundation ordering:

1. priority descending
2. deterministic rank ascending
3. available time ascending
4. created time ascending
5. id ascending

This ensures that lease acquisition remains replay-safe and stable across identical queue states.

## Concurrency model

- Each worker advertises `max_concurrency`.
- Active leases plus active executions cannot exceed that limit.
- Concurrency overage attempts are rejected and preserved as runtime issues.
- The runtime does not autoscale, rebalance, or shard work in this phase.

## Replay-safe execution guarantees

- execution snapshots are immutable once written
- execution checksums are derived from stable ordered payloads
- worker history is append-only
- runtime issues are append-only
- lease release is explicit and auditable
- owner views are isolated to workers connected to that owner's jobs
- ops runtime routes are the only mutation surface

## Non-goals

This phase explicitly does not include:

- scheduling
- distributed orchestration
- realtime websocket workers
- distributed locking
- autoscaling
- Kubernetes runtime management
- queue sharding
- dynamic concurrency tuning
- external execution engines
