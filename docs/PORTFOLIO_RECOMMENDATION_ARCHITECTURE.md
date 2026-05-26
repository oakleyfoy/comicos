# Portfolio recommendation engine (P38-04)

## Philosophy

ComicOS treats portfolio recommendations as a deterministic strategic intelligence layer, not an execution engine:

- Translate existing portfolio, duplicate, liquidity, grading, risk, listing, and sales ledgers into explainable `HOLD`, `SELL`, `REDUCE_EXPOSURE`, `GRADE_THEN_SELL`, `CONSOLIDATE`, and `WATCH` calls.
- Persist evidence, scenarios, and append-safe history so every recommendation can be replayed and audited.
- Keep the engine strictly observational. It never auto-sells inventory, auto-lists books, mutates FMV, changes portfolios, or performs hidden rebalancing.

### Non-goals

- Predictive market timing, ML/AI portfolio management, or stochastic recommendation modeling.
- Autonomous liquidation, brokerage integrations, or automated tax-aware disposal.
- Silent mutation of `InventoryCopy`, `Portfolio`, `Listing`, FMV snapshots, or sales ledgers.

---

## Models

| Model | Role |
| --- | --- |
| `PortfolioRecommendation` | Current deterministic recommendation snapshot for an owner/inventory/portfolio/date/replay tuple. |
| `PortfolioRecommendationEvidence` | Evidence spine referencing duplicate, liquidity, grading, risk, listing, sales, market sale, and exposure inputs. |
| `PortfolioRecommendationScenario` | Deterministic `pessimistic`, `baseline`, and `optimistic` projections for capital release, liquidity gain, and portfolio impact. |
| `PortfolioRecommendationHistory` | Append-safe history checkpoint written only when a newly generated recommendation checksum changes. |

Statuses:

- Actions: `HOLD`, `SELL`, `REDUCE_EXPOSURE`, `GRADE_THEN_SELL`, `CONSOLIDATE`, `WATCH`
- Strength: `WEAK`, `MODERATE`, `STRONG`, `ELITE`
- Confidence: `LOW`, `MEDIUM`, `HIGH`
- Risk: `LOW`, `MEDIUM`, `HIGH`
- Row status: `ACTIVE`, `SUPERSEDED`, `ARCHIVED`

Generation scopes:

- `ALL_INVENTORY`
- `PORTFOLIO_{id}`

---

## Inputs

The engine consumes persisted deterministic facts only:

- latest `InventoryLiquiditySnapshot` per inventory item
- latest `GradingRecommendation` and `GradingRiskSnapshot` per inventory item
- latest `ListingIntelligenceSnapshot` per inventory item
- latest duplicate teaser derived from the active duplicate batch
- latest portfolio exposure and allocation snapshots for the selected generation scope
- realized sales totals and latest sale / market sale links when available
- inventory FMV or acquisition-cost fallback for capital math

No external APIs, no hidden feature flags, and no probabilistic weights are consulted.

---

## Deterministic scoring

All numeric recommendation math is derived from fixed additive modifiers and then clamped:

- money values quantize to `0.01`
- percentage-like score values quantize to `0.01`
- score bands clamp to `[0, 100]`
- checksums hash canonical JSON with sorted keys and normalized decimal/date formatting

### Strength score

Base score starts at `45` and adds/subtracts explicit bonuses from:

- portfolio liquidity bucket
- duplicate posture
- grading recommendation posture
- listing intelligence posture
- exposure posture
- grading-risk penalties

Strength bands:

- `ELITE`: `>= 78`
- `STRONG`: `>= 58`
- `MODERATE`: `>= 35`
- `WEAK`: otherwise

### Confidence score

Base score starts at `28` and increases from evidence coverage:

- scope liquidity snapshot present: `+8`
- grading recommendation present: `+8`
- grading risk snapshot present: `+8`
- duplicate teaser present: `+6`
- listing intelligence present: `+6`
- realized sale total present: `+6`
- exposure rows present: `+6`
- scope allocation snapshot present: `+4`

Then subtract `4` points for each accumulated risk point across liquidity, duplicates, grading, risk engine, listing, and exposure.

Confidence bands:

- `HIGH`: `>= 75`
- `MEDIUM`: `>= 50`
- `LOW`: otherwise

### Risk classification

Risk points accumulate deterministically from:

- weak or missing liquidity
- duplicate redundancy / overexposure
- unfavorable or missing grading posture
- grading risk level, low confidence, thin evidence, weak stability
- weak or missing listing intelligence
- concentrated or overexposed portfolio posture

Risk bands:

- `HIGH`: `>= 6`
- `MEDIUM`: `>= 3`
- `LOW`: otherwise

---

## Recommendation rules

Action selection uses explicit ordered rules:

1. `SELL`
   - duplicate posture is bad and this is not the strongest copy, or
   - liquidity is `LOW` / `ILLIQUID` and sell pressure is negative, or
   - liquidity is weak and overall risk is `HIGH`
2. `CONSOLIDATE`
   - duplicate posture is bad, this is the strongest copy, and exposure is also concentrated, or
   - duplicate posture remains bad after higher-priority rules do not trigger
3. `GRADE_THEN_SELL`
   - grading recommendation is favorable (`GRADE` or ROI at least `0.35`)
   - liquidity bucket is `HIGH` or `MEDIUM`
   - risk is not `HIGH`
   - confidence score is at least `50`
4. `REDUCE_EXPOSURE`
   - exposure is `CONCENTRATED` / `OVEREXPOSED`, especially when duplicates confirm the posture
5. `WATCH`
   - confidence score under `40`, or
   - risk is `HIGH`, or
   - liquidity is weak without a cleaner sell/consolidate path
6. `HOLD`
   - remaining healthy liquidity / exposure / duplicate posture cases

### Supporting posture rules

- Liquidity buckets:
  - `HIGH` -> `HIGH`
  - `MODERATE` -> `MEDIUM`
  - `LOW` -> `LOW`
  - `ILLIQUID` -> `ILLIQUID`
  - missing -> neutral `MEDIUM` fallback with warning flags
- Sell pressure adds positive points for realized sales and active listings, and subtracts for weak sell-through (`< 18`) and stale listing pressure (`>= 70`).
- Exposure warnings intensify when portfolio share is high, especially at `>= 40`.

---

## Capital-release and scenario modeling

Recommendation rows persist deterministic observational estimates only:

- `SELL`
  - `estimated_capital_release = 1.00 * base_fmv`
  - `estimated_liquidity_impact = 1.00 * base_fmv`
- `REDUCE_EXPOSURE`
  - capital release `= 0.50 * base_fmv`
  - liquidity impact `= 0.40 * base_fmv`
- `GRADE_THEN_SELL`
  - capital release `= 0.80 * base_fmv`
  - liquidity impact `= 0.60 * base_fmv`
- `CONSOLIDATE`
  - capital release `= 0.65 * base_fmv`
  - liquidity impact `= 0.55 * base_fmv`
- `HOLD` / `WATCH`
  - both values remain `null`

`base_fmv` is `InventoryCopy.current_fmv` when present, otherwise acquisition cost.

`estimated_portfolio_efficiency_gain` is:

\[
100 \times \frac{\text{estimated\_capital\_release}}{\text{scope total FMV}}
\]

when scope FMV is positive; otherwise `null`.

Scenario multipliers:

- `pessimistic`: `0.85x`
- `baseline`: `1.00x`
- `optimistic`: `1.15x`

No forecasting engine, Monte Carlo simulation, or market prediction is used.

---

## Replay safety and append-safe history

- Generation identity is `(owner_user_id, portfolio_id, inventory_item_id, snapshot_date, replay_key)`.
- Recommendation checksum is SHA-256 over the ordered recommendation payload, including action, levels, estimated impacts, warning flags, scope key, and replay key.
- If a row already exists for the tuple and the checksum matches:
  - generation is treated as a replay
  - the existing recommendation is returned
  - no new history row is appended
- If the tuple exists but the checksum changes:
  - the prior row is marked `SUPERSEDED`
  - a new `ACTIVE` recommendation row is written
  - history appends only if the new history checksum is new for that scope/action/date signature

Evidence payload JSON is normalized before persistence so decimal-bearing facts remain replay-safe and JSON serializable.

---

## Owner and ops APIs

### Owner routes

- `POST /portfolio-recommendations/generate`
- `GET /portfolio-recommendations`
- `GET /portfolio-recommendations/{id}`
- `GET /portfolio-recommendation-evidence`
- `GET /portfolio-recommendation-history`

Supported owner filters:

- `portfolio_id`
- `inventory_item_id`
- `recommendation_action`
- `recommendation_strength`
- `confidence_level`
- `risk_level`
- `date_from`
- `date_to`

### Ops routes

- `GET /ops/portfolio-recommendations`
- `GET /ops/portfolio-recommendations/{id}`
- `GET /ops/portfolio-recommendation-evidence`
- `GET /ops/portfolio-recommendation-history`

Ops routes are read-only mirrors and add optional `owner_user_id` filtering for cross-owner inspection.

---

## UI surfaces

- `DashboardPage`
  - lightweight hold/sell intelligence rollup cards and explicit generate button
- `OperationsPage`
  - recommendation table plus selected detail/evidence/history/scenario views
- `InventoryDetailPage`
  - compact teaser with action, strength, confidence, risk, rationale, and estimated impacts

All UI remains observational and lightweight. No workflow button performs an inventory mutation.

---

## Implementation reference

- Service: `apps/api/app/services/portfolio_recommendation.py`
- Models: `apps/api/app/models/portfolio_recommendation.py`
- Schemas: `apps/api/app/schemas/portfolio_recommendation.py`
- Tests: `apps/api/tests/test_portfolio_recommendation.py`
