# P40 Determinism Guarantees

This document defines what P40 guarantees to be deterministic, what may vary, and where replay limitations still exist.

## What is deterministic

- Stable phase ordering across the P40 pipeline
- Stable list ordering for runs, events, issues, checks, discrepancies, and history
- Stable manifest serialization for feed and replay artifacts
- Stable checksum derivation for repeated identical inputs
- Stable owner-scoped and ops-scoped query behavior
- Stable append-only artifact paths
- Stable replay discrepancy ordering

## What is allowed to vary

- Timestamps that reflect true creation time, as long as they do not affect stable sort order or checksum derivation
- Generated primary keys and internal row ids
- The presence or absence of optional phases when the scan workflow does not produce them
- Ops-only diagnostic rollups that summarize stored ledgers without changing those ledgers

## Replay guarantees

- Replay is idempotent for identical inputs and stable lineages
- Replay manifests hash into a stable `replay_checksum`
- Replay does not rewrite upstream artifacts or manifests
- Replay discrepancies are stored as evidence, not repaired away

## Manifest guarantees

- Manifest payloads are ordered before hashing
- Manifest content is derived from stored ledgers only
- Manifest checksums are reproducible for identical stored inputs
- Manifest drift is surfaced as a discrepancy instead of being hidden

## Checksum guarantees

- Upstream phase checksums remain the authoritative values for their phases
- Feed and replay derive new checksums from ordered stored state
- Artifact checksums are compared against stored values instead of being rewritten

## Append-only guarantees

- History rows are append-only
- Feed artifacts are append-only
- Replay artifacts are append-only
- Hardening reports are documentation-only and do not mutate operational ledgers

## Immutability guarantees

- Original scan bytes remain unchanged after downstream processing
- Normalized artifacts remain immutable once written
- Review evidence and replay evidence are never overwritten in place
- Missing or changed artifacts are surfaced as CRITICAL validation outcomes

## Owner isolation guarantees

- Owner routes only return the authenticated owner’s records
- Ops routes are read-only and require configured ops access
- Artifact access follows the owning run’s permissions

## Replay discrepancy philosophy

- Discrepancies are audit evidence, not failures to be “fixed” automatically
- Critical discrepancies must remain visible to ops and owner surfaces
- The system favors explicit gaps over hidden fallback generation

## Known non-deterministic boundaries

- Wall-clock timestamps may differ across runs
- Distinct scans with different source inputs will naturally produce different checksums
- Diagnostic rollups can change when underlying ledgers change, which is expected

