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

## P33 — Inventory Intelligence closeout (2026-05-24)

- Intelligence reads (risks, action center, timelines, duplication, run gaps, reconciliation summaries) remain **mutation-free** on the dedicated read paths.
- Portfolio FMV dashboards stay separate from deterministic intelligence panels; CSV/JSON snapshots omit FMV where schemas allow (`reports_export`).
- Extending intelligence or exports should preserve explicit tuple sort keys and regression tests rather than ad-hoc nondeterministic ordering.
- New caches or async mutation on intelligence/export code paths need an explicit design note plus tests for ordering, filters, and scope (owner vs ops).