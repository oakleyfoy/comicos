# Acquisition priority engine (P38-06)

## Philosophy

ComicOS treats acquisition priority as a deterministic portfolio-expansion and gap-analysis lane, not a buying engine:

- translate current owner inventory into explicit acquisition opportunities using only persisted portfolio, concentration, liquidity, duplicate, grading, recommendation, listing, and sales signals
- persist evidence, scenarios, and append-safe history so every acquisition row can be replayed and audited
- keep the engine observational only; it never auto-buys inventory, mutates FMV, changes portfolios, or triggers autonomous rebalancing

### Non-goals

- predictive market timing, AI portfolio management, or hidden scoring models
- autonomous buying, brokerage integrations, or auction automation
- silent mutation of `InventoryCopy`, `Portfolio`, listings, FMV ledgers, or recommendation state

---

## Models

- `AcquisitionPrioritySnapshot`
  - current deterministic acquisition row for `(owner, canonical_comic_issue_id, acquisition_category, snapshot_date, replay_key)`
- `AcquisitionPriorityEvidence`
  - evidence spine linking exposure, concentration, liquidity, duplicate, grading, listing, and sales posture
- `AcquisitionPriorityScenario`
  - deterministic `pessimistic`, `baseline`, and `optimistic` projections for liquidity, diversification, and portfolio-efficiency impact
- `AcquisitionPriorityHistory`
  - append-safe history checkpoints written only when a regenerated checksum changes

Supported categories:

- `DIVERSIFICATION`
- `LIQUIDITY_IMPROVEMENT`
- `GRADING_OPPORTUNITY`
- `KEY_ISSUE`
- `PORTFOLIO_GAP`
- `LOW_EXPOSURE_CATEGORY`
- `CONVENTION_STOCK`
- `SALES_VELOCITY`

Priority bands:

- `LOW`
- `MEDIUM`
- `HIGH`
- `ELITE`

---

## Inputs

The engine uses persisted deterministic facts only:

- owner inventory ordered by `InventoryCopy.id ASC`
- latest `PortfolioExposureSnapshot` rows in `ALL_INVENTORY`
- latest `ConcentrationRiskSnapshot` rows in `ALL_INVENTORY`
- latest `PortfolioLiquiditySnapshot`
- latest `InventoryLiquiditySnapshot` per owned copy
- duplicate teaser posture per owned copy
- latest grading recommendation and grading-risk rows per owned copy
- latest portfolio recommendation rows per owned copy
- latest listing-intelligence rows plus active-listing counts
- realized sales totals per owned copy

The engine currently models acquisition opportunities from the owner’s existing issue universe and category posture. It does not invent external candidate issues or scrape market catalogs.

---

## Deterministic scoring

All numeric values use explicit formulas only:

- money values quantize to `0.01`
- percentage-like values quantize to `0.01`
- scores clamp to `[0, 100]`
- checksums hash canonical JSON with sorted keys and normalized decimal/date formatting

### Issue aggregation

Each acquisition row is built from a deterministic issue aggregate:

- owned copies grouped by `canonical_comic_issue_id`
- stable ordering by `InventoryCopy.id ASC`
- latest per-copy support rows loaded first, then reduced into issue-level aggregates

### Core outputs

- `diversification_impact`
  - average inverse exposure share across publisher, title, era, and acquisition-source buckets
- `concentration_reduction_score`
  - average inverse concentration score across publisher, title, and era buckets
- `liquidity_impact`
  - average of:
    - issue-level liquidity opportunity score
    - owner-level liquidity-need score from `PortfolioLiquiditySnapshot`
- `grading_upside_score`
  - fixed additive points from grading recommendation action, strength, ROI, liquidity-adjusted ROI, and grading-risk penalties
- `duplication_risk`
  - duplicate-overlap percentage plus explicit penalties for multiple owned copies and sell/consolidate recommendation posture
- `estimated_capital_efficiency`
  - average of liquidity impact, grading upside, and sales velocity, then reduced by duplicate-risk penalty

### Portfolio impact score

`portfolio_impact_score` uses explicit fixed weights:

- `diversification_impact * 0.28`
- `liquidity_impact * 0.22`
- `grading_upside_score * 0.18`
- `concentration_reduction_score * 0.20`
- `estimated_capital_efficiency * 0.12`
- minus `duplication_risk * 0.20`

### Priority and strength bands

Priority:

- `ELITE >= 80`
- `HIGH >= 60`
- `MEDIUM >= 35`
- `LOW < 35`

Recommendation strength:

- `ELITE >= 85`
- `STRONG >= 65`
- `MODERATE >= 40`
- `WEAK < 40`

### Confidence and risk

Confidence is derived from explicit evidence depth:

- exposure support present
- concentration support present
- portfolio liquidity snapshot present
- per-copy liquidity rows present
- realized sales present
- active listings present
- grading support present
- portfolio recommendation support present
- stale-listing penalties applied directly

Risk is derived from explicit risk points:

- low / illiquid posture
- weak sell-through
- stale-listing pressure
- high duplicate overlap
- weak concentration reduction
- thin market activity

Bands:

- confidence: `HIGH >= 75`, `MEDIUM >= 50`, else `LOW`
- risk: `HIGH >= 5 points`, `MEDIUM >= 3`, else `LOW`

---

## Category classification rules

Category selection is ordered and deterministic:

1. `CONVENTION_STOCK`
   - acquisition-source label includes convention/show/vendor-style language
   - liquidity impact is at least `60`
2. `GRADING_OPPORTUNITY`
   - grading upside is at least `75`
   - duplicate risk is below `60`
3. `DIVERSIFICATION`
   - diversification impact is at least `80`
   - concentration reduction is at least `60`
4. `LIQUIDITY_IMPROVEMENT`
   - liquidity impact is at least `75`
5. `SALES_VELOCITY`
   - sales velocity is at least `75`
   - liquidity impact is at least `60`
6. `LOW_EXPOSURE_CATEGORY`
   - diversification impact is at least `68`
   - concentration reduction is at least `55`
7. `KEY_ISSUE`
   - total owned issue value is at least `100`
   - duplicate risk is below `50`
8. `PORTFOLIO_GAP`
   - default fallback for rows that remain useful but do not match a higher-priority category

Rows with high duplicate risk or weak impact naturally fall to lower acquisition-priority bands, which is how redundant or low-value opportunities are surfaced.

---

## Replay safety and append-safe history

- generation identity is `(owner_user_id, canonical_comic_issue_id, acquisition_category, snapshot_date, replay_key)`
- if the same tuple regenerates with identical ordered checksums, the request is treated as a replay and existing rows are returned
- if the same tuple regenerates with changed checksums, current rows for that generation tuple are delete-replaced and history appends only for changed checksums
- history is keyed by `(owner_user_id, canonical_comic_issue_id, acquisition_category, snapshot_date, checksum)` so identical content does not double-append

Evidence payload JSON is normalized before persistence so decimal-bearing facts remain replay-safe and JSON serializable.

---

## Owner and ops APIs

### Owner routes

- `POST /acquisition-priorities/generate`
- `GET /acquisition-priorities`
- `GET /acquisition-priorities/{id}`
- `GET /acquisition-priority-evidence`
- `GET /acquisition-priority-history`

Supported owner filters:

- `acquisition_category`
- `acquisition_priority`
- `recommendation_strength`
- `confidence_level`
- `risk_level`
- `date_from`
- `date_to`

### Ops routes

- `GET /ops/acquisition-priorities`
- `GET /ops/acquisition-priorities/{id}`
- `GET /ops/acquisition-priority-evidence`
- `GET /ops/acquisition-priority-history`

Ops routes are read-only mirrors and add optional `owner_user_id` filtering for cross-owner inspection.

---

## UI surfaces

- `DashboardPage`
  - high-priority acquisition counts, elite counts, diversification counts, liquidity-improvement counts, and grading-opportunity counts
- `OperationsPage`
  - acquisition table plus selected detail, evidence, scenarios, and history
- `InventoryDetailPage`
  - compact teaser showing how that issue currently scores as an acquisition opportunity, including diversification, liquidity, and overlap hints

The UI stays read-only and never implies autonomous acquisition execution.

---

## Deferred scope

- external candidate-issue universe generation beyond the owner’s current issue graph
- autonomous buying or portfolio auto-expansion
- predictive market timing, probabilistic demand forecasting, or AI acquisition ranking
- brokerage integrations, auction automation, and execution tooling
- automatic portfolio mutation driven by acquisition signals

---

## Implementation references

- `apps/api/app/models/acquisition_priority.py`
- `apps/api/app/schemas/acquisition_priority.py`
- `apps/api/app/services/acquisition_priority.py`
- `apps/api/app/main.py`
- `apps/web/src/api/client.ts`
- `apps/web/src/pages/DashboardPage.tsx`
- `apps/web/src/pages/OperationsPage.tsx`
- `apps/web/src/pages/InventoryDetailPage.tsx`
