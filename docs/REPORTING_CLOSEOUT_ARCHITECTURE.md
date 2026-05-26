# Operational reporting closeout architecture (P36-08)

## Purpose

Finalize the deterministic **commerce operations layer** (listings → exports → sales → liquidity → conventions → intelligence → dealer dashboard) with explicit, append-safe **operational CSV reports**.

This track is intentionally **descriptive bookkeeping**: deterministic reads, reproducible hashing, lineage rows, replay keys, UTF-8 CSV exports — **no corrective automation**, predictive analytics, outbound notifications, or hidden mutation.

## Persistence model (`OperationalReport*`)

Tables (see Alembic `20260525_0060_add_operational_reporting.py`, models in `apps/api/app/models/operational_reporting.py`):

- **`OperationalReportRun`** — one generation attempt per logical report for an owner. Fields:
  - `report_type` ∈ `listing_summary | sales_summary | liquidity_summary | convention_summary | export_summary | dealer_dashboard_summary | inventory_health_summary`
  - `status` ∈ `DRAFT | RUNNING | COMPLETED | FAILED` (generation currently uses `RUNNING` → `COMPLETED` / `FAILED`)
  - `replay_key` + `UniqueConstraint(owner_user_id, replay_key)` for idempotent replays
  - `generation_params_json` — normalized filter payload (sorted keys, ISO dates, `generator_version`)
  - `checksum` — SHA-256 of the UTF-8 CSV body at completion
  - `csv_row_count` — row count including stable sorted metric rows
  - Timestamps: `created_at`, `started_at`, `completed_at`, optional `failure_reason`
- **`OperationalReportFile`** — CSV artifact metadata (`file_name`, `storage_path` relative to root, `checksum`, `row_count`, `file_type` = `csv`).
- **`OperationalReportItem`** — per-row lineage (`lineage_domain`, `lineage_key`, `lineage_json`, `row_checksum`, monotonic `row_number`).

### Storage layout

Default root: `data/operational_reports/` (override with `OPERATIONAL_REPORTS_STORAGE_ROOT`).

Relative path pattern: `{owner_user_id}/{run_id}/comic_os_{report_slug}_{YYYY-MM-DD}_run_{run_id}.csv`

Download resolution mirrors listing exports: resolve → `Path.relative_to(root)` guard → `FileResponse`.

## Deterministic generation

Service: `apps/api/app/services/operational_reporting.py`

- **No writes** to listing, export, sales, liquidity, convention, intelligence, or dealer rows.
- Each `report_type` builds a **stable header tuple** and **metric rows** sourced from existing services + SQL aggregates.
- Rows are **lexicographically sorted** by their CSV tuple before rendering to guarantee stable ordering.
- `render_csv` (shared helper in `reports_export.py`) emits UTF-8 with `\n` terminators.

### Highlights by report

| Report | Reads (high level) |
| --- | --- |
| `listing_summary` | Listing status counts + `build_listing_intelligence_dashboard_summary` rollups |
| `sales_summary` | `SaleRecord` aggregates + per-channel counts (optional `sale_date_from/to` filters) |
| `liquidity_summary` | Liquidity dashboard + latest liquidity snapshot statuses + velocity medians/averages |
| `convention_summary` | Convention dashboard + wall/showcase/bin slot counts + OPEN/CLOSED sale sessions |
| `export_summary` | Listing export dashboard + replay usage + deterministic channel completion grid |
| `dealer_dashboard_summary` | Latest dealer snapshot scalars / metrics + rolling 90-day alert & feed totals |
| `inventory_health_summary` | Cross-layer deterministic health signals (images, pricing, intel, liquidity, convention stale linkage) |

## HTTP surface

Owner:

- `GET /reports/dashboard-rollups` — recent + failed fingerprints for dashboards
- `GET /reports` — filter by `report_type`, `status`, `created_from`, `created_to`
- `POST /reports/generate` — idempotent (`replay_key`); `201` on first completion, `200` on replay
- `GET /reports/{report_id}`
- `GET /reports/{report_id}/download?file_id=…` (`COMPLETED` only)

Ops (mirrors + cross-owner downloads, `OPS_ADMIN_EMAILS` gated):

- `GET /ops/reports` — optional `owner_user_id`
- `GET /ops/reports/{report_id}`
- `GET /ops/reports/{report_id}/download`
- `GET /ops/reports/dashboard-rollups?owner_user_id=` — empty when `owner_user_id` omitted (forces explicit scoping)

## Web surfaces

- **Dashboard** (`DashboardPage`): lightweight “Operational reporting” strip (recent runs, failed runs, checksum preview, quick CSV download for last completed rows).
- **Operations** (`OperationsPage`): `operational-reporting-ops` table with type/status/row counts/checksums/download buttons.

## Invariants

1. **Deterministic first** — identical database state + identical `generation_params_json` ⇒ identical CSV + checksum.
2. **Replay-safe** — duplicate `replay_key` returns the original `OperationalReportRun` without regenerating CSV.
3. **Append-safe registry** — new runs accumulate; reruns reuse replay rows instead of mutating artifacts.
4. **Explainability** — `OperationalReportItem` rows document aggregation domains/sources (JSON is sorted at persistence time).
5. **Owner / ops isolation** — owner routes strictly scope `current_user.id`; ops uses explicit allowances with audit-friendly read-only crosses.

## Testing

Focused coverage in `apps/api/tests/test_operational_reporting.py`:

- Replay + checksum stability
- Stable CSV ordering (header lexical contract)
- Owner download isolation vs outsiders
- Ops route `403` for non-admin
- Listing-count immutability across `inventory_health_summary` generation

Also keep green regression slices for sibling P36 modules (`listing_export`, `sales_ledger`, `liquidity_engine`, `listing_intelligence`, `dealer_dashboard`, etc.) whenever generation logic taps their services.

## Explicit non-goals (post-P36)

- Streaming report generation, websocket fan-out
- Predictive dealer intelligence / acquisition optimization / portfolio forecasting
- Grading ROI, recommendation surfaces, staffing workflows
- Automated notifications or third-party sinks
- Auto repair / auto reconcile behavior on CSV output
