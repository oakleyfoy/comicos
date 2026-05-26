# Dealer Dashboard / Dealer OS Architecture (P36-07)

## Purpose

The dealer dashboard is a **Bloomberg-terminal-style operational cockpit** — dense, deterministic, and read-only toward external truth tables.  
It merges listing registry snapshots, deterministic exports, liquidity evidence, convention operations, ledger sales rollups, and listing intelligence completeness into:

- Persisted **`DealerDashboardSnapshot`** rows (`append-safe`, keyed by deterministic checksums plus optional replay keys).
- **`DealerDashboardMetric`** rows documenting explainable rollup metadata (scores, percentages, versioning labels).
- **`DealerDashboardAlert`** rows emitting **observational** anomalies (no remediation, routing, staffing, CRM, predictive AI).
- **`DealerDashboardFeedEvent`** rows forming an **`append-safe` operational ticker** keyed by deterministic event identities.

Everything is grounded in ComicsOS invariants:

- deterministic first
- owner / ops isolation
- no hidden mutations of listings, inventory, exports, liquidity, conventions, ledger data, intelligence rows
- explainable payloads that hash to reproducible checksums

## Snapshot generation

`POST /dealer-dashboard/generate` invokes `services/dealer_dashboard.generate_dealer_dashboard`:

1. **Replay guard** — if `replay_key` collides under `uq_dealer_dashboard_snapshot_owner_replay`, the existing persisted snapshot returns unchanged (replay-safe regeneration).
2. **Payload assembly (`_compute_payload`)** aggregates **pure reads** scoped to `(owner_user_id, snapshot_date)`:
   - **Active listings** — `Listing.status == ACTIVE`.
   - **Listing intelligence snapshots** anchored to **`snapshot_date`** for export-ready, incomplete posture, staleness overlays, completeness averages (only rows that exist—no hallucinated intelligence).
   - **Staleness** — union of deterministic `ListingStalenessEvent` evidence (`STALE_CONFIRMED`, `LONG_RUNNING`) for ACTIVE/READY listings plus intelligence `stale_risk_flag`.
   - **Convention** — ACTIVE conventions, ACTIVE assignments without `removed_at`, OPEN sessions joined to ACTIVE events.
   - **Sales (30 trailing calendar days ending `snapshot_date`)** — summed `RECORDED` `SaleRecord` gross/net/profit totals.
   - **Liquidity (same `snapshot_date`)** — DISTINCT `inventory_copy_id` counts for HIGH vs LOW / ILLIQUID statuses; overlaps drop from both buckets to avoid double counting ambiguous rows.
   - **Exports — trailing 30d window on `ListingExportRun.created_at`** counting total runs vs **degraded runs** (`error_count > 0` **or** `status != COMPLETED`).
3. **Checksum** — `sha256(sorted JSON)` over `_json_safe` payload (decimals → strings). Any schema expansion must bump `AGGREGATION_VERSION`.
4. **Metrics** rows — lexical sort on `metric_key` for deterministic insert order (`aggregation_label`, completeness averages, INTEL counts…).
5. **Alerts** — deterministic `SHA256(snapshot_id:type:foreign keys…)` uniqueness under `uq_dealer_dashboard_alert_owner_replay_key`.
6. **Feed** events — keyed by `deterministic_key` (`LISTING_CREATED:lifecycle_event:{id}` etc.) with **`owner_user_id` scoped uniqueness**. Existing rows are skipped silently to ensure append-safe replays across dashboard generations without duplicating deterministic evidence.

Alerts + feed rows **never** mutate upstream ledgers—they only ingest evidence.

### Alert taxonomy (launch set)

| type | deterministic trigger | severity |
| --- | --- | --- |
| **STALE_LISTING** | Staleness telemetry or intelligence stale flag union | warning |
| **EXPORT_FAILURE** | Any degraded export attempts in trailing 30d window | critical |
| **LOW_COMPLETENESS** | `ListingIntelligenceSnapshot` with evidence + completeness `< 65` (ADEQUATE floor) | warning |
| **LOW_LIQUIDITY** | Liquidity snapshots mark inventory tied to ACTIVE listing as LOW / ILLIQUID | warning |
| **CONVENTION_PRICING_MISSING** | ACTIVE assignment lacks `local_price_amount` | warning |
| **MISSING_PRIMARY_IMAGE** | ACTIVE listing has gallery rows yet none flagged `PRIMARY` (`role.casefold() == primary`) | warning |

No autofix workflows run here.

### Feed taxonomy

Operational evidence types:

`LISTING_CREATED`, `LISTING_SOLD`, `EXPORT_COMPLETED`, `EXPORT_FAILED`, `SALE_RECORDED`, `STALE_DETECTED`, `CONVENTION_ASSIGNED`, `LIQUIDITY_UPDATED`

Feeds sort server-side **`ORDER BY created_at DESC, id DESC`** guaranteeing stable paging.

## Owner vs Ops APIs

| Owner surface | Ops surface | Notes |
| --- | --- | --- |
| `GET /dealer-dashboard` | `GET /ops/dealer-dashboard` | Latest snapshot envelope (may be `{snapshot:null}`) |
| `POST /dealer-dashboard/generate` | — | Only owners materialize dashboards (deterministic ingestion) |
| `GET /dealer-dashboard/metrics` | `GET /ops/dealer-dashboard/metrics` | Default to latest dashboard id; Ops may filter mismatched IDs out |
| `GET /dealer-dashboard/alerts` | `GET /ops/dealer-dashboard/alerts` | Severity / type filters + bounded date window |
| `GET /dealer-dashboard/feed` | `GET /ops/dealer-dashboard/feed` | Ops supports `owner_user_id` telescope |

Ops routes reuse `ensure_ops_admin_access`; they never escalate to mutate inventory.

## Frontend philosophy

- **Dashboard SPA** lays out Sections A–G as dense stat matrices + textual evidence (deterministic overlays only).
- **Operations SPA** publishes drill-down ASCII tables scoped by optional numeric owner filter.
- **Inventory detail badges** summarise intel / liquidity / convention lanes without spawning new ingestion jobs.

### Non-goals (hard stops)

Predictive repricing, sell/hold “AI”, portfolio recommendations, websocket push, notification routers, staffing/task queues, background workers for dashboard refresh, benchmarking across owners without explicit deterministic exports—these violate the observational charter and remain **out-of-scope**.

## Replay + append contracts

| Artifact | Replay behavior |
| --- | --- |
| `DealerDashboardSnapshot` | `replay_key UNIQUE per owner`; duplicates short-circuit before writes |
| `DealerDashboardMetric` | UNIQUE `(snapshot_id, metric_key)` |
| `DealerDashboardAlert` | UNIQUE `(owner_user_id, alert_replay_key)` |
| `DealerDashboardFeedEvent` | UNIQUE `(owner_user_id, deterministic_key)` — dedup skips when identical evidence already anchored |

Combined, these guarantee **replay-safe deterministic rebuilds**, **checksum stability**, and **no phantom mutation**.

---

For adjoining systems (exports, liquidity, conventions, intelligence) see companion architecture docs cited in TECH_DEBT (P36-02 … P36-06 suites).
