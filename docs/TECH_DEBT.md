# Technical debt log

Operational notes for intentional deferrals and known cleanup work. Entries should be actionable when someone has a maintenance window.

## `apps/api/app/main.py` — Ruff / structure (updated 2026-05-23)

Run: `python -m ruff check app/main.py` from `apps/api`.

### Duplicate HTTP handlers

Resolved during P32 closeout. The duplicate registrations for match-confidence regeneration were removed and route-count regression coverage was added in `apps/api/tests/test_ops_admin.py`.

Resolved routes:

| Route | Cleanup |
| --- | --- |
| `POST /cover-images/{cover_image_id}/regenerate-match-confidence` | Reduced to a single handler |
| `POST /ops/cover-images/{cover_image_id}/regenerate-match-confidence` | Reduced to a single handler |
| `GET /ops/cover-images/{cover_image_id}/relationship-graph` | Restored explicit ops route to match the web client |
| `GET /ops/cover-relationship-graph` | Restored explicit query-style ops route for parity |

### Remaining cleanup notes

- **`I001` / `E501`** — `python -m ruff check app/main.py` last cleared on 2026-05-23; new routes should keep decorators wrapped and lines within 100 columns as `main.py` grows.
- **RQ warnings** — Default test runs should remain on `fakeredis`; if new worker/dashboard helpers touch `rq.job.Job`, prefer `job.return_value()` and `job.latest_result()` over deprecated `job.result` / `job.exc_info`.

## P32 closeout notes

- Reconciliation dashboards now expose compact read-only summary counts for conflicts, canonical suggestions, match candidates, duplicate scans, variant families, and replay changes.
- Relationship conflict detection and relationship replay remain strictly non-mutating surfaces. They should continue to log review/audit state only, never automatic relationship or metadata changes.
- The default backend suite should remain independent of an external Redis instance; tests rely on in-memory `fakeredis` wiring in `apps/api/tests/conftest.py`.

## P34 — Scan pipeline / bulk ingest closeout (2026-05-24)

- **Architecture note:** see `docs/SCAN_PIPELINE_ARCHITECTURE.md` for lifecycle boundaries (Fujitsu bulk ingest semantics, Epson high-res escalation lane wording, deterministic QA/routing/replay/dashboard reads without OCR enqueue).

- **Operational surfaces consolidated** (`ScanSessionsPage`, owner dashboard receiving + pipeline rails, Ops **Bulk ingest operations** drawer) prioritize explicit buttons (`Run QA snapshot`, `Generate routing snapshot`, `Queue OCR`) over implicit automation — regression tests cover routing/dashboard non-enqueue guards.

- **Known follow-ups**
  - List endpoints that currently cap at owner-selected limits (scan items `limit=500` in SPA) remain UI-side until product defines shared pagination primitives for ingest queues.
  - FastAPI uniqueness regression only asserts the guarded scan-plane path prefixes enumerated in `test_scan_pipeline_closeout.py`; adding new sibling routers requires extending that registry when paths are logically part of the scan pipeline contract.

## P35 — Market sales foundation closeout (2026-05-24)

- **Architecture note:** market-sale persistence now keeps raw source payloads, ordered image evidence, deterministic issue rows, and stable source registry rows for future comp / FMV work without any live scraping or pricing heuristics.
- **Operational surfaces**: owner reads remain read-only, ops gets the explicit upsert lane, and the dashboard/ops page show compact preview surfaces without mutating inventory metadata.
- **Known follow-ups**
  - Extend market-sales pagination and bulk import ergonomics only when product defines the final ingest workflow.
  - Keep duplicate handling issue-only; no auto-merge or delete paths should be introduced on the sales foundation tables.

## P35-06 — FMV snapshot foundation closeout (2026-05-25)

- **Architecture note:** `market_fmv_snapshot` and `market_fmv_comp_reference` form a separate deterministic ledger sourced only from eligible comps plus approved/high-confidence canonical match state. These rows must stay append-only-or-idempotent snapshot artifacts and must never update `InventoryCopy.current_fmv` or manual `InventoryFmvSnapshot` history.
- **Operational surfaces:** owner dashboard and inventory detail expose read-only FMV snapshot visibility, while ops owns explicit batch generation and comp-reference inspection. Keep all generation semantics currency-specific and deterministic; no FX conversion, prediction, speculation, or recommendation logic should be introduced on this path.
- **Known follow-ups**
  - If snapshot volume grows, move FMV list filtering/aggregation from in-memory service passes to SQL-backed filtering while preserving the current stable sort contract (`snapshot_date`, scope rank, method rank, `id`).
  - If product wants broader graded comp partitioning later, document new scopes explicitly instead of overloading the existing `graded`, `graded_by_company`, and `graded_by_grade` semantics.

## P33 — Inventory Intelligence closeout (2026-05-24)

- Intelligence reads (risks, action center, timelines, duplication, run gaps, reconciliation summaries) remain **mutation-free** on the dedicated read paths.
- Portfolio FMV dashboards stay separate from deterministic intelligence panels; CSV/JSON snapshots omit FMV where schemas allow (`reports_export`).
- Extending intelligence or exports should preserve explicit tuple sort keys and regression tests rather than ad-hoc nondeterministic ordering.
- New caches or async mutation on intelligence/export code paths need an explicit design note plus tests for ordering, filters, and scope (owner vs ops).