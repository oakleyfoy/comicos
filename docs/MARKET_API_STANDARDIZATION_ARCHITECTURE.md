# Market API standardization architecture (P39-07)

## Purpose

Expose all P39 market intelligence modules (**ingestion, normalization, scoring, signals, opportunities, coupling**) behind a single **versioned** HTTP surface with a **deterministic envelope** and **explicit owner vs ops** separation — without changing ranking, aggregation, checksum, or security logic inside engine services.

## Design philosophy

- **Thin adapter layer.** `/api/v1/market/*` routes call the same service functions as the legacy unversioned paths; normalization is limited to envelopes, pagination, errors, logging, and OpenAPI tagging.
- **Contracts over convenience.** Stable JSON shapes and stable ordering semantics are prioritized so replays and UI consumers can rely on checksum-stable snapshots unchanged from P39-01→06.
- **Security parity.** Owners authenticate as themselves; ops routes require ops admin eligibility and expose **only** read paths P39 historically exposed as ops-safe. Mutation and generation endpoints are **never** mirrored under `/api/v1/market/ops/…`.

## Versioning (`/api/v1/market`)

- All standardized P39 HTTP entry points live under **`/api/v1/market`** plus the same suffix as before (e.g. `/api/v1/market/market-ingestion/batch`, `/api/v1/market/ops/market-ingestion/batches`).
- **Legacy unversioned routes remain** for backwards compatibility outside the SPA; clients should converge on **`v1`** for new development.
- **P40+** features must introduce new prefixes or majors without mutating **`v1`** response contracts.

## Response envelope

Every successful `v1` response body:

```json
{
  "data": {},
  "meta": {
    "owner_user_id": "123",
    "snapshot_id": "456",
    "checksum": "…",
    "generated_at": "2026-05-26T12:34:56Z",
    "engine_versions": {
      "ingestion": "P39-01",
      "normalization": "P39-02",
      "scoring": "P39-03",
      "signals": "P39-04",
      "opportunity": "P39-05",
      "coupling": "P39-06"
    }
  }
}
```

- **`data`** — domain payload. Lists nest rows under **`data.items`** and attach **`data.pagination`** (see below).
- **`meta.owner_user_id`** — stringified tenant context (`null` when not scoped).
- **`meta.snapshot_id` / `checksum`** — populated when a primary snapshot artifact exists on the underlying read model; optional on list endpoints.
- **`generated_at`** — UTC ISO instant when the envelope was assembled (replay may return the same **`data`** with a new generated instant).

### List pagination (`data.pagination`)

Standard fields:

| Field           | Meaning                                      |
|-----------------|-----------------------------------------------|
| `total_count`   | Total rows matching filters (same as legacy `total_items`) |
| `limit` / `offset` | Page window                              |
| `has_next`      | `offset + len(items) < total_count`          |
| `next_cursor`   | Reserved (`null`); cursor mode not used yet |

Extra list keys (for example ingestion **`status_counts`**, normalization **`health`**) remain alongside **`items`** and **`pagination`** inside **`data`**.

## Errors

For paths under **`/api/v1/market`** only, validation and HTTP failures return:

```json
{
  "error": {
    "code": "HTTP_404",
    "message": "...",
    "details": null
  }
}
```

Other API prefixes keep FastAPI’s default `{ "detail": ... }` envelope until migrated.

## Owner vs ops

| Capability        | Owner (`/api/v1/market/…`) | Ops (`/api/v1/market/ops/…`)      |
|-------------------|----------------------------|------------------------------------|
| Read list/detail  | Yes                        | Yes (with optional `owner_user_id` filters) |
| Writes / generates| Yes where legacy allowed   | **No** generation or batch writes in v1 |

## Deterministic guarantees

- **Replay safety** and row ordering are inherited from underlying services unchanged.
- **`data`** payloads are **`model_dump(mode="json")`** from existing Pydantic schemas so field names and nesting match legacy APIs.
- **Envelope `meta.generated_at`** is not part of persisted snapshot checksum contracts.

## Observability

Structured log lines (**`p39.market.<phase>`**) are emitted on successful POST-style engine actions routed through **`v1`**: ingestion batch accept, normalization run, scoring run, signal/opportunity/coupling generation. Extra keys include **`owner_user_id`**, snapshot/checksum identifiers when applicable, and the envelope **`generated_at`**.

## Non-goals

- No new ranking, signal weighting, or coupling heuristics.
- No consolidation of **`/market-sales`**, **`/market-fmv`**, trends, comps, review queue, etc. inside this standardization phase (distinct product surfaces).
- No GraphQL, streaming subscriptions, federation, codegen, or third-party proxies (see TECH_DEBT **P39-07 deferred**).

## Implementation map

| Module        | Routes (relative to `/api/v1/market`) |
|---------------|----------------------------------------|
| Ingestion     | `/market-ingestion/*`, `/ops/market-ingestion/*` |
| Normalization | `/market-normalization/*`, `/ops/market-normalization/*` |
| Scoring       | `/market-scoring/*`, `/ops/market-scoring/*` |
| Signals       | `/market-signals*`, `/market-signal-*`, `/ops/market-*` parallels |
| Opportunities | `/market-opportunities/*`, `/ops/market-opportunities/*` |
| Coupling      | `/market-portfolio-coupling/*`, `/ops/market-portfolio-coupling/*` |

Python: `apps/api/app/api/market_v1_layer.py`, envelope helpers `apps/api/app/schemas/market_api_v1.py`. Frontend: **`requestMarketV1`** and updated list typings in **`apps/web/src/api/client.ts`**.
