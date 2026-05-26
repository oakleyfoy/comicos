# Concentration risk engine (P38-05)

## Philosophy

ComicOS treats concentration risk as a deterministic portfolio-intelligence lane, not an execution engine:

- translate current exposure into explicit concentration posture across publishers, titles, eras, variant families, grading posture, liquidity posture, and acquisition channels
- persist evidence, weighted factors, and append-safe history so every concentration row can be replayed and audited
- keep the engine observational only; it never rebalances portfolios, mutates FMV, auto-lists books, or changes inventory state

### Non-goals

- predictive diversification modeling, ML/AI scoring, or hidden threshold tuning
- autonomous liquidation, portfolio auto-rebalancing, or capital-allocation automation
- silent mutation of `InventoryCopy`, `Portfolio`, `Listing`, FMV ledgers, or realized-sales ledgers

---

## Models

- `ConcentrationRiskSnapshot`
  - current deterministic concentration row for `(owner, portfolio, concentration_type, concentration_key, snapshot_date, replay_key)`
- `ConcentrationRiskEvidence`
  - evidence spine linking registry, liquidity, duplicate, sales, grading, and listing posture into one auditable row
- `ConcentrationRiskFactor`
  - persisted 0..100 factor rows with explicit weights
- `ConcentrationRiskHistory`
  - append-safe history checkpoints written only when a regenerated checksum changes

Supported concentration types:

- `publisher`
- `character`
- `title`
- `creator`
- `era`
- `variant_family`
- `grading_status`
- `liquidity_status`
- `acquisition_source`

Placeholder contract:

- `character` and `creator` remain observational `unknown` buckets until real attribution lands, matching the P38-01 dimensional contract

---

## Inputs

The engine uses persisted deterministic facts only:

- owner-scope inventory ordered by `InventoryCopy.id ASC`
- latest `InventoryLiquiditySnapshot` per inventory item
- latest `PortfolioAllocationSnapshot` and `PortfolioLiquiditySnapshot` for the requested scope when available
- latest `PortfolioExposureSnapshot` batch for the requested scope when available
- duplicate teaser posture for each inventory item
- latest grading recommendation / grading-risk rows when available
- realized sales totals per inventory item
- listing intelligence posture and active-listing counts when available

`variant_family` is derived from the existing inventory -> issue -> variant joins and keyed from title, issue number, and the most specific variant anchor available (`variant_type`, `cover_name`, `ratio`, `printing`, then variant id fallback).

---

## Deterministic scoring

All numeric values use explicit formulas only:

- money values quantize to `0.01`
- percentage-like values quantize to `0.01`
- scores clamp to `[0, 100]`
- checksums hash canonical JSON with sorted keys and normalized decimal/date formatting

### Primary share

For each `(scope, concentration_type, concentration_key)` row:

- `fmv_share_pct = percentage of scope FMV * 100` when scope FMV exists
- `count_share_pct = percentage of scope item count * 100`
- `primary_share_pct = fmv_share_pct` when present, else `count_share_pct`

### Liquidity-weighted concentration

Each category row computes a liquidity-weighted portfolio share using item-level risk weights:

- `HIGH = 0.25`
- `MODERATE = 0.50`
- `LOW = 0.75`
- `ILLIQUID = 1.00`
- missing = `0.60`

Formula:

`sum(category_item_value * liquidity_weight) / scope_total_fmv * 100`

If FMV is absent at scope level, the engine falls back to count-weighted normalization.

### Factors

Persisted factor rows:

- `fmv_dependence`
  - `primary_share_pct`
- `liquidity_fragility`
  - `100 * low_or_illiquid_category_value / category_value`
  - count basis fallback when category value is absent
- `duplicate_overlap`
  - `100 * duplicate_overlap_items / category_item_count`
- `grading_overlap`
  - `100 * graded_or_grading_candidate_items / category_item_count`
- `sales_dependence`
  - `100 * category_realized_sales / scope_realized_sales`
  - `0` when scope sales are absent
- `category_fragility`
  - average of `liquidity_fragility`, `duplicate_overlap`, and `grading_overlap`

Explicit weights:

- `fmv_dependence = 0.35`
- `liquidity_fragility = 0.25`
- `duplicate_overlap = 0.15`
- `grading_overlap = 0.10`
- `sales_dependence = 0.10`
- `category_fragility = 0.05`

### Final scores

- `concentration_score = weighted_sum(factors)`
- `diversification_score = 100 - concentration_score`

Exposure-status bands:

- `HEALTHY < 20`
- `WATCH 20 - < 35`
- `CONCENTRATED 35 - < 50`
- `OVEREXPOSED 50 - < 70`
- `CRITICAL >= 70`

Hard-upgrade rule:

- a row is forced to at least `CRITICAL` when `primary_share_pct >= 55`
- a row is also forced to at least `CRITICAL` when `liquidity_weighted_concentration >= 45`

---

## Replay safety and append-safe history

- generation identity is `(owner_user_id, portfolio_id, snapshot_date, replay_key)` plus the concentration row key
- if the same tuple regenerates with identical ordered checksums, the request is treated as a replay and existing rows are returned
- if the same tuple regenerates with changed checksums, current rows for that tuple are delete-replaced and new history checkpoints append only for changed checksums
- history is keyed by `(owner_user_id, portfolio_id, concentration_type, concentration_key, snapshot_date, checksum)` so identical content does not double-append

Evidence payload JSON is normalized before persistence so decimal-bearing facts remain replay-safe and JSON serializable.

---

## Owner and ops APIs

### Owner routes

- `POST /concentration-risk/generate`
- `GET /concentration-risk`
- `GET /concentration-risk/{id}`
- `GET /concentration-risk-evidence`
- `GET /concentration-risk-factors`
- `GET /concentration-risk-history`

Supported owner filters:

- `portfolio_id`
- `concentration_type`
- `concentration_key`
- `exposure_status`
- `date_from`
- `date_to`

### Ops routes

- `GET /ops/concentration-risk`
- `GET /ops/concentration-risk/{id}`
- `GET /ops/concentration-risk-evidence`
- `GET /ops/concentration-risk-factors`
- `GET /ops/concentration-risk-history`

Ops routes are read-only mirrors and add optional `owner_user_id` filtering for cross-owner inspection.

---

## UI surfaces

- `DashboardPage`
  - lightweight concentration rollup cards and explicit generate button
- `OperationsPage`
  - concentration table plus selected detail, evidence, factor, and history views
- `InventoryDetailPage`
  - compact teaser showing the worst matching `ALL_INVENTORY` concentration posture for the item

The teaser stays observational and uses the same placeholder-dimension rules as the engine. It does not imply any automatic action.

---

## Implementation references

- `apps/api/app/models/concentration_risk.py`
- `apps/api/app/schemas/concentration_risk.py`
- `apps/api/app/services/concentration_risk.py`
- `apps/api/app/main.py`
- `apps/web/src/api/client.ts`
- `apps/web/src/pages/DashboardPage.tsx`
- `apps/web/src/pages/OperationsPage.tsx`
- `apps/web/src/pages/InventoryDetailPage.tsx`
