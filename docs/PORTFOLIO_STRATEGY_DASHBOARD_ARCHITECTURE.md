# Portfolio strategy dashboard (P38-07)

## Philosophy

ComicOS treats the portfolio strategy dashboard as a deterministic command center, not an autonomous manager:

- consolidate persisted P38 portfolio-intelligence layers into one strategic cockpit
- surface explainable strategic KPIs, alerts, and feed events without inventing a second hidden decision engine
- keep the dashboard observational only; it never rebalances portfolios, mutates FMV, changes recommendations, or executes acquisitions

### Non-goals

- predictive portfolio strategy, AI portfolio management, or hidden scoring models
- automated liquidation, autonomous buying, or background portfolio optimization
- silent mutation of `Portfolio`, `InventoryCopy`, FMV ledgers, listings, or realized-sales records

---

## Models

- `PortfolioStrategyDashboardSnapshot`
  - current owner-level strategic rollup for `(owner_user_id, replay_key)`
- `PortfolioStrategyDashboardMetric`
  - persisted metric ledger attached to one snapshot for denser operational drill-down
- `PortfolioStrategyDashboardAlert`
  - deterministic observational alerts keyed by a stable replay hash
- `PortfolioStrategyDashboardFeedEvent`
  - append-safe strategic feed items keyed by deterministic source signatures

Supported alert types:

- `OVEREXPOSURE`
- `DEAD_CAPITAL`
- `DUPLICATE_RISK`
- `LIQUIDITY_IMBALANCE`
- `CONCENTRATION_CRITICAL`
- `WEAK_DIVERSIFICATION`
- `HIGH_RISK_HOLDING`
- `ACQUISITION_GAP`

Supported feed event types:

- `PORTFOLIO_CREATED`
- `EXPOSURE_GENERATED`
- `DUPLICATE_CLUSTER_CREATED`
- `HOLD_RECOMMENDATION_CREATED`
- `SELL_RECOMMENDATION_CREATED`
- `CONCENTRATION_ALERT`
- `ACQUISITION_OPPORTUNITY`
- `LIQUIDITY_WARNING`

---

## Aggregation inputs

The dashboard uses persisted deterministic rows only:

- current active `Portfolio` registry rows
- latest owner-wide `PortfolioAllocationSnapshot`
- latest owner-wide `PortfolioLiquiditySnapshot`
- latest duplicate batch from `DuplicateCluster`
- current active `PortfolioRecommendation` rows
- latest owner-wide `ConcentrationRiskSnapshot` signature
- latest owner-wide `AcquisitionPrioritySnapshot` signature
- current active `GradingCandidate` rows
- `PortfolioLifecycleEvent` creation rows for feed events
- recorded `SaleRecord` totals as a fallback when an allocation snapshot is absent

If a supporting layer has not been generated yet, the strategy dashboard degrades gracefully and leaves those strategic fields empty or zeroed instead of mutating anything upstream.

---

## Deterministic dashboard aggregation

All snapshot values are computed with explicit formulas only:

- money values quantize to `0.01`
- score / percentage values quantize to `0.01`
- hashes use canonical JSON with sorted keys and normalized decimal/date formatting
- latest source rows use stable ordering on `snapshot_date DESC`, `created_at DESC`, then `id DESC`

Primary snapshot fields:

- `portfolio_count`
  - active non-archived portfolios for the owner
- `total_portfolio_value`, `total_cost_basis`, `total_realized_sales`
  - latest owner-wide allocation snapshot values, with inventory / sales fallbacks if allocation has not run
- `diversification_score`
  - average latest concentration `diversification_score`
- `concentration_risk_score`
  - average latest concentration `concentration_score`
- `liquidity_efficiency_score`, `dead_capital_estimate`
  - latest owner-wide portfolio-liquidity snapshot
- `duplicate_cluster_count`
  - cluster count in the latest duplicate batch
- `hold_recommendation_count`, `sell_recommendation_count`, `reduce_exposure_count`
  - current active recommendation actions
- `acquisition_opportunity_count`, `elite_acquisition_count`
  - latest acquisition signature counts
- `liquid_inventory_percentage`, `illiquid_inventory_percentage`
  - latest owner-wide portfolio-liquidity bucket counts

Metrics are persisted as a denser read model for the operations page. They include aggregation version, counts, capital-release totals, duplicate hotspot metadata, and acquisition-focus metadata.

### Engine dependency graph

The dashboard depends on persisted ledger outputs only, in this order:

1. `Portfolio` / portfolio lifecycle registry from P38-01
2. owner-wide allocation snapshots from P38-01
3. latest duplicate batch from P38-02
4. owner-wide liquidity snapshot from P38-03
5. latest recommendation signature from P38-04
6. latest concentration signature from P38-05
7. latest acquisition signature from P38-06
8. strategy aggregation snapshot / metrics / alerts / feed from P38-07

To keep this inspectable in production, the metrics ledger now persists `source_engine_versions` and `source_dependency_graph` rows that expose the upstream snapshot ids, checksums, and version tags consumed by the latest strategy snapshot.

### Deterministic guarantees

- dashboard metrics default to the latest materialized strategy snapshot for the requested owner scope, so KPI drill-down stays aligned with the visible snapshot
- recommendation-derived counts are computed from the latest deterministic recommendation signature, not from an unbounded history scan
- alert rows and feed rows are canonically sorted before checksum generation and persistence
- owner/ops list ordering is stable on explicit business keys rather than relying on insertion order alone
- append-safe alert/feed persistence batches existing-key checks to avoid per-row query drift while preserving replay safety

---

## Alert logic

Alerts are observational only and deduplicated by a stable replay hash of their explicit fields.

### `OVEREXPOSURE`

Generated for latest concentration rows whose status is `OVEREXPOSED` or `CRITICAL`.

### `DEAD_CAPITAL`

Generated when the latest owner-wide portfolio-liquidity snapshot reports a positive `dead_capital_estimate`.

### `DUPLICATE_RISK`

Generated for latest duplicate clusters whose posture is `REDUNDANT` or `OVEREXPOSED`.

### `LIQUIDITY_IMBALANCE`

Generated when owner-wide liquidity posture is `IMBALANCED` or `CRITICAL`.

### `CONCENTRATION_CRITICAL`

Generated when average diversification drops below `45`.

### `WEAK_DIVERSIFICATION`

Generated when average diversification is below `60` but not yet critical.

### `HIGH_RISK_HOLDING`

Generated for active `HOLD` recommendations that still carry `HIGH` risk.

### `ACQUISITION_GAP`

Generated for high/elite acquisition rows in `PORTFOLIO_GAP`, `LOW_EXPOSURE_CATEGORY`, or `DIVERSIFICATION`.

---

## Feed behavior

The strategic feed is append-safe and keyed by stable source signatures:

- portfolio lifecycle `CREATED` rows -> `PORTFOLIO_CREATED`
- latest owner-wide allocation snapshot -> `EXPOSURE_GENERATED`
- latest duplicate batch checksum -> `DUPLICATE_CLUSTER_CREATED`
- latest recommendation signature -> `HOLD_RECOMMENDATION_CREATED` / `SELL_RECOMMENDATION_CREATED`
- latest concentration signature -> `CONCENTRATION_ALERT`
- latest liquidity warning snapshot -> `LIQUIDITY_WARNING`
- latest acquisition signature -> `ACQUISITION_OPPORTUNITY`

Feed ordering is deterministic by `created_at DESC, id DESC`.

---

## Replay safety

- snapshot replay identity is `(owner_user_id, replay_key)` when a replay key is supplied
- identical same-day regenerations reuse the existing latest snapshot when the checksum matches
- metrics are written once per snapshot via `(dashboard_snapshot_id, metric_key)`
- alerts are append-safe through `(owner_user_id, alert_replay_key)`
- feed events are append-safe through `(owner_user_id, deterministic_key)`

The dashboard never updates or supersedes upstream intelligence rows. It only reads them and persists its own strategic ledger.

## Stabilization notes

P38-08 hardens the aggregation layer without adding any new intelligence:

- snapshot generation remains read-only against upstream engines
- snapshot + metrics + alerts + feed now persist in a single transaction boundary so partial strategy writes are avoided
- generation logs include `snapshot_id`, `checksum`, engine-version metadata, and inserted alert/feed counts
- alert persistence logs include `alert_type` and `severity`
- feed persistence logs include total vs inserted event counts
- frontend strategy surfaces tolerate partial API failures by rendering the snapshot when available and degrading missing alerts/feed/metrics safely

---

## Owner and ops APIs

### Owner routes

- `GET /portfolio-strategy-dashboard`
- `POST /portfolio-strategy-dashboard/generate`
- `GET /portfolio-strategy-dashboard/metrics`
- `GET /portfolio-strategy-dashboard/alerts`
- `GET /portfolio-strategy-dashboard/feed`

Owner filters:

- alerts: `severity`, `alert_type`, `created_from`, `created_to`
- feed: `event_type`, `created_from`, `created_to`
- metrics: `dashboard_snapshot_id`

### Ops routes

- `GET /ops/portfolio-strategy-dashboard`
- `GET /ops/portfolio-strategy-dashboard/metrics`
- `GET /ops/portfolio-strategy-dashboard/alerts`
- `GET /ops/portfolio-strategy-dashboard/feed`

Ops routes are read-only mirrors and add optional `owner_user_id` filtering.

The owner and ops contracts intentionally expose the same response schemas. Ops differs only by access control and optional owner scoping.

---

## Strategic workflow

Recommended usage:

1. generate or refresh the underlying P38 engines
2. generate the strategy dashboard
3. review snapshot KPIs for portfolio health
4. inspect alerts for urgent posture problems
5. inspect feed events for recent strategic changes
6. use lower-level P38 ops tables to drill into the source ledgers

The strategy dashboard is intentionally a consolidation layer, not a replacement for the underlying deterministic evidence.

---

## UI surfaces

- `DashboardPage`
  - unified strategic command-center section with overview, exposure/diversification, liquidity, duplicates, hold/sell, acquisition, alerts, and feed
- `OperationsPage`
  - strategic KPI cards plus metrics, alerts, and feed tables
- `InventoryDetailPage`
  - continues to rely on the existing lightweight teaser stack (duplicate, liquidity, acquisition, concentration, recommendation) as the inventory-level strategic hint rail

## Known limitations

- the strategy dashboard remains explicitly pull-based; there is no realtime websocket feed
- ops without an explicit owner filter still shows a latest snapshot header plus cross-owner alert/feed history, so operators should apply `owner_user_id` when reviewing one owner in depth
- the dashboard relies on upstream ledgers having already been generated; if a supporting engine has not run, the dashboard degrades to null/zero fields rather than synthesizing missing evidence
- logging is intentionally structural and lightweight; there is no dedicated metrics/trace pipeline for dashboard generation yet

---

## Implementation references

- `apps/api/app/models/portfolio_strategy_dashboard.py`
- `apps/api/app/schemas/portfolio_strategy_dashboard.py`
- `apps/api/app/services/portfolio_strategy_dashboard.py`
- `apps/api/app/main.py`
- `apps/api/tests/test_portfolio_strategy_dashboard.py`
- `apps/web/src/api/client.ts`
- `apps/web/src/pages/DashboardPage.tsx`
- `apps/web/src/pages/OperationsPage.tsx`
