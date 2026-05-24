# Reconciliation Architecture

P32 closes the matching and reconciliation layer as a deterministic, review-first system.

## Core boundaries

- Deterministic only: relationship graphing, duplicate-scan clustering, variant-family clustering, canonical suggestions, conflict detection, and replay diffs must be reproducible from persisted state.
- Human review stays authoritative: approved, rejected, acknowledged, dismissed, and resolved states are explicit user or ops actions, not inferred corrections.
- No automatic linking: reconciliation surfaces may suggest, rank, cluster, or warn, but they must not create or revert relationship decisions without an explicit review action.
- No metadata mutation: reconciliation logic must not rewrite canonical metadata, identity keys, inventory state, or cover ownership as a side effect of analysis.

## Inventory intelligence reads

Canonical suggestions, conflicts, duplicate clustering, scans, OCR, timelines, exports, collection analytics, duplicate ownership intelligence, action center, inventory risks, and run detection summaries are deterministic **projections** layered on persisted facts. Outside explicit review or write APIs, Intelligence must not coerce metadata, holdings, reconciliation artifacts, OCR rows, exports, conflict rows, or cover ownership as a hidden side-effect of analysis (details: [`INVENTORY_INTELLIGENCE_ARCHITECTURE.md`](./INVENTORY_INTELLIGENCE_ARCHITECTURE.md)).

## Safety surfaces

### Relationship conflicts

Relationship conflicts persist contradictions between deterministic signals and human decisions. They are an audit/review layer only:

- conflicts are keyed deterministically for idempotent reruns
- stale conflicts are marked resolved instead of deleted
- lifecycle changes only affect the conflict row and audit trail

### Relationship replays

Relationship replays provide regression visibility without mutating source data:

- baseline snapshots are captured when a replay run is created
- deterministic services are rerun later against the same covers
- compact diffs are stored on replay items
- replay execution must never overwrite human decisions, inventory, canonical metadata, or conflict state

## Operational expectation

The Operations dashboard should surface counts and recent review artifacts so humans can decide what to inspect next, while the detailed panels remain the place for evidence, context, and explicit review actions.
