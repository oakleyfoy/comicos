# Market Intelligence Dashboard UI (P39-08)

This document describes how the Comic OS web app composes the deterministic P39 market-intelligence stack (P39-01 through P39-06) into a **single owner dashboard** plus **ops diagnostics**, while keeping all reads on the **P39-07 standardized API envelope** (`{ data, meta }` under `/api/v1/market/*`).

---

## UI architecture model

| Surface | Responsibility | Data access |
| ------- | -------------- | ----------- |
| **`MarketIntelligenceDashboard`** | Owner-facing unified intelligence: overview plus six isolated panels | `GET` owner routes only (`/market-ingestion/*`, `/market-normalization/*`, `/market-scoring/*`, `/market-signal-snapshots`, `/market-opportunities/*`, `/market-portfolio-coupling/*`) via `fetchMarketV1Envelope` |
| **`MarketIntelligenceOpsDiagnostics`** | Checksum/trace matrix for ops and dashboard parity QA | Parallel `GET` `/ops/market-*` lists (`limit=1`) with optional `owner_user_id` scoped to ops portfolio owner filter |
| **`InventoryDetailPage` teasers** | Single-row highlights for scoring, signal, opportunity, coupling | Supplied only by inventory read models (no P39 graph fetch storm) |

No component in this phase introduces scoring, normalization, ingestion, coupling, signal, or opportunity **logic**. All computations remain server-side in P39 engines.

---

## Panel isolation rules

1. **One hook, many slices**: `useMarketIntelligencePanels` owns six independent `{ loading, error, data, meta }` records. Updating one slice must not wipe others unless the authenticated owner changes (`ownerUserId`).
2. **Per-panel skeleton, error state, retry**: Each panel renders its own `StatusBanner`, `PanelSkeleton`, and footer action that triggers only that panel's loader (`reloadPanel(layer)`).
3. **Envelope-only reads**: Owner dashboard calls `fetchMarketV1Envelope` so every successful response carries `MarketApiV1Meta` for snapshot and trace hints.
4. **No duplicated fetch helpers inside panels**: Memoized shells (`memo`) receive immutable props from the dashboard parent to avoid cascading paints when unrelated slices mutate.

---

## Snapshot-driven rendering

- **Deterministic lineage**: Latest rows from scoring, signals, opportunities, and coupling snapshots expose foreign keys (`market_acquisition_score_snapshot_id`, `market_acquisition_signal_snapshot_id`, `market_acquisition_opportunity_snapshot_id`). `buildMarketSnapshotChainIssues` surfaces mismatches without blocking unrelated panels (warning banner).
- **`meta.snapshot_id` and `meta.checksum`**: Standard list responses often omit anchored checksum metadata; authoritative checksums typically live on row payloads (`checksum`, `snapshot_checksum`, `batch_checksum`, …). Panels render shortened row checksums and envelope parity guidance.
- **`dedupedFlight` gate**: Uses `p39mi:${ownerUserId}:${layer}` keys to suppress duplicate simultaneous calls (React Strict Mode and rapid churn). This is concurrency coalescing, not a TTL cache replacement.

Partial loads remain safe when only a subset of layers succeeds.

---

## API dependency mapping (dashboard)

| Panel | Representative owner `GET` |
| ----- | ------------------------- |
| Ingestion | `/market-ingestion/batches` |
| Normalization | `/market-normalization/runs` |
| Scoring | `/market-scoring/snapshots?limit=1` |
| Signals | `/market-signal-snapshots?limit=1` |
| Opportunities | `/market-opportunities/snapshots?limit=1` |
| Coupling | `/market-portfolio-coupling/snapshots?limit=1` |

Heavy list endpoints (`/market-scoring/scores`, `/market-opportunities` item grids, coupling edges tables) remain in **Operations**.

---

## Performance model

- Initial loads enqueue in microtask bursts to smooth scheduling while preserving parallel retrieval.
- `React.memo` around each panel minimizes paint churn as slices resolve.
- No durable client cache beyond in-flight dedupe; see TECH_DEBT for deferred streaming and caching enhancements.

---

## Non-goals (P39-08)

- New intelligence logic or backend engine edits.
- Bypassing envelopes for the unified dashboard loader.
- Real-time streaming, personalization, speculative UI ranking, websocket sync beyond what TECH_DEBT defers.
