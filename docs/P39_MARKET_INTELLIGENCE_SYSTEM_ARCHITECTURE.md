# P39 Market Intelligence System Architecture

P39-01 through P39-10 form a closed, deterministic Market Intelligence System.

## Freeze Statement

P39 is frozen.

Rules:

- No feature expansion.
- No architecture rewrites.
- No API contract breaks.
- No schema redesigns.
- Future work must happen in P40+ or additive extension layers only.

## Full Pipeline Map

P39-01 Ingestion -> P39-02 Normalization -> P39-03 Scoring -> P39-04 Signals -> P39-05 Opportunities -> P39-06 Coupling -> P39-09 Feed -> P39-10 Determinism

P39-07 provides the versioned API envelope across the whole pipeline.
P39-08 provides dashboard and UI support surfaces for the market system.

## Layer Descriptions

### P39-01 Ingestion

Deterministic append-only intake of external market records. The ingestion ledger preserves raw payloads, raw hashes, batch checksums, and append-only batch events.

### P39-02 Normalization

Canonicalizes intake rows into stable normalized candidates and tracks normalization runs, issues, and replay-safe events. Same inputs must always produce the same canonical keys.

### P39-03 Scoring

Converts normalized candidates into deterministic acquisition scores and score snapshots. Score rows remain pure read-derived outputs over persisted upstream context.

### P39-04 Signals

Classifies score rows into deterministic market signals with stable signal checksums and evidence rows. It is a read-only interpreter over scoring outputs.

### P39-05 Opportunities

Aggregates deterministic signals into opportunity snapshots and line items. Ordering, weights, and checksum payloads are stable and replay-safe.

### P39-06 Coupling

Builds the read-only bridge between portfolio state and opportunity rows. Coupling edges and alignment metrics are deterministic and append-safe.

### P39-07 API Layer

Exposes the entire market stack through `/api/v1/market` using the standard envelope, stable pagination, explicit owner/ops routes, and consistent error shapes.

### P39-08 Dashboard Layer

Provides the dashboard orchestration and UI support utilities that render the market stack in compact, read-only summary form.

### P39-09 Feed Layer

Records significant P39 outputs in an append-only market feed with sequence ordering, replay-safe snapshots, and owner/ops read surfaces.

### P39-10 Determinism Layer

Validates checksum lineage, replay stability, ordering guarantees, and invariant compliance across the entire pipeline. It writes only to the P39-10 ledger.

## Determinism Guarantees

- Replay safety: repeated validations reuse identical results instead of mutating upstream rows.
- Checksum lineage: each layer’s stored checksum is validated against canonical recomputation.
- Append-only guarantees: validation findings are written as new rows.
- Ordering guarantees: list endpoints and replay checks use explicit stable ordering before hashing or rendering.

## API Standard

- Every market v1 read surface uses the `{ data, meta }` envelope.
- Pagination is returned in `data.pagination`.
- `meta.engine_versions` exposes the layer map, including `determinism: P39-10`.
- Owner and ops routes stay explicitly separated.
- Errors use `{ error: { code, message, details } }`.

## UI Architecture

- Dashboard: compact orchestration summaries and deterministic integrity badges.
- Operations: deep read-only diagnostics, including feed, coupling, and determinism drill-downs.
- Inventory detail: lightweight teaser surfaces only, never full diagnostics consoles.

## Deployment Model

- Source of truth is GitHub `main`.
- Render auto-deploys production services from `main`.
- Alembic migrations advance sequentially and must remain on a single head.
- Production validation requires both API and web services to be deployed from the frozen `main` branch.

## Non-Goals

P39 intentionally does not include:

- websocket streaming
- Kafka or any event bus
- AI prediction
- ML anomaly detection
- distributed replay validation
- external marketplace sync automation

