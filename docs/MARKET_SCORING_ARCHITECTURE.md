# Market scoring architecture (P39-03)

## Philosophy

ComicOS market scoring is the first deterministic intelligence layer on top of P39 market normalization.

Hard boundaries:

- no ML, AI inference, randomness, or probabilistic weighting
- no external APIs or live market lookups
- no mutation of ingestion or normalization rows
- no autonomous buying, selling, or portfolio actions

The scorer is a pure reader over:

- P39-02 normalized candidates
- P38 portfolio context snapshots

Identical inputs must always produce identical per-candidate checksums, recommendation labels, and owner snapshot checksums.

## Ledger

The scoring lane persists four tables:

- `MarketAcquisitionScoreSnapshot`: owner-scoped snapshot summary for one deterministic scoring pass
- `MarketAcquisitionScore`: one scored row per normalized candidate within a snapshot
- `MarketAcquisitionScoreEvidence`: append-safe evidence rows grouped by scored candidate
- `MarketAcquisitionScoreHistory`: append-safe score history for trend inspection and replay protection

`MarketAcquisitionScore` rows reference both the normalized candidate and, when resolvable through deterministic title/publisher/issue matching, the internal `comic_issue` record used to join P38 context.

## Deterministic matching and context

The scorer never fuzzy-matches. It only resolves a normalized candidate to an internal issue when all of the following line up deterministically:

1. canonical publisher matches a normalized publisher registry row
2. canonical title matches the deterministic title normalization of an internal comic title
3. canonical issue number matches exactly

When an exact internal issue match exists, the scorer reads the latest owner-scoped P38 evidence from:

- `AcquisitionPrioritySnapshot`
- `PortfolioLiquiditySnapshot` (`ALL_INVENTORY`)
- `PortfolioExposureSnapshot`
- `ConcentrationRiskSnapshot`

It also checks current inventory holdings for duplicate overlap on the matched issue.

If no internal issue match exists, the scorer degrades gracefully to normalized-candidate-only signals plus broad portfolio liquidity/exposure context. That fallback is still deterministic and intentionally conservative.

## Score model

Component scores are all clamped to `0..100`:

- `portfolio_fit_score`
- `liquidity_score`
- `grading_upside_score`
- `diversification_score`
- `concentration_reduction_score`
- `risk_penalty_score`

Final rank formula:

```text
final_rank_score =
  portfolio_fit_score * 0.25 +
  liquidity_score * 0.20 +
  grading_upside_score * 0.20 +
  diversification_score * 0.15 +
  concentration_reduction_score * 0.10 +
  (100 - risk_penalty_score) * 0.10
```

Recommendation thresholds are fixed:

- `85..100` -> `STRONG_BUY`
- `70..84.99` -> `BUY`
- `50..69.99` -> `WATCH`
- `<50` -> `IGNORE`

Confidence and risk bands are likewise deterministic buckets derived from evidence coverage, canonical issue resolution, normalization status, and accumulated penalty pressure.

## Evidence

Each scored row records a stable evidence bundle:

- `PORTFOLIO_STATE`
- `CONCENTRATION_RISK`
- `DUPLICATE_INTELLIGENCE`
- `LIQUIDITY_ENGINE`
- `NORMALIZATION_LAYER`

Evidence rows are descriptive only. They exist to explain why a deterministic score was produced, not to mutate upstream ledgers.

## Replay safety

- Per-score checksum hashes the ordered normalized candidate signature plus the exact upstream context checksums/values used for scoring.
- Snapshot checksum hashes the ordered list of scored-row checksums for that owner/date.
- Replaying `POST /market-scoring/run` with unchanged inputs returns the existing snapshot and does not duplicate score, evidence, or history rows.
- If normalized inputs or upstream P38 context change, a new snapshot checksum is produced and history appends cleanly.

## API surface

### Owner routes

- `POST /market-scoring/run`
- `GET /market-scoring/scores`
- `GET /market-scoring/scores/{id}`
- `GET /market-scoring/snapshots`
- `GET /market-scoring/history`

### Ops routes

- `GET /ops/market-scoring/scores`
- `GET /ops/market-scoring/scores/{id}`
- `GET /ops/market-scoring/snapshots`
- `GET /ops/market-scoring/history`

Owner and ops reads share the same schema contract; ops adds optional owner scoping.

## UI surfaces

- `DashboardPage`: score distribution and score-health snapshot cards
- `OperationsPage`: scoring snapshot table, top-score drill-down, evidence preview, recent history
- `InventoryDetailPage`: lightweight market-score teaser for matching issue candidates only

None of these views execute scoring automatically; they remain read-only over persisted scoring snapshots.

## Non-goals

- predictive pricing
- ML ranking models
- autonomous recommendation tuning
- external signal weighting
- buy execution or auto-allocation
- mutation of inventory, normalization, or ingestion layers
