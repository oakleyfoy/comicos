# P73-02 Recommendation Performance Analytics

## Purpose

P73-01 records **what happened** after a recommendation (outcomes and events). P73-02 measures **how well** those recommendations perform using read-only aggregates. This phase does **not** change recommendation scores, rankings, generation, or model training.

## Metric definitions

| Metric | Definition |
|--------|------------|
| Recommendations generated | Count of `p73_recommendation_outcome` rows for the owner |
| Viewed / Purchased / … | Distinct outcomes with at least one matching `p73_recommendation_action_event` |
| View rate | `VIEWED` outcomes ÷ generated × 100 |
| Purchase rate | `PURCHASED` outcomes ÷ generated × 100 |
| Watchlist rate | `WATCHLISTED` outcomes ÷ generated × 100 |
| Grade rate | `GRADED` outcomes ÷ generated × 100 |
| Sell rate | `SOLD` outcomes ÷ generated × 100 |
| Success rate | Share of outcomes with `attribution_accurate = true` when attribution applies |
| Failure rate | Share with `attribution_accurate = false` |
| Win / loss rate | Share of outcomes with positive / negative `actual_roi_pct` |
| Category success | Per normalized type (`BUY`, `GRADE`, `SELL`, `WATCH`), attribution success rate |

## ROI formulas

- **Expected ROI %** — arithmetic mean of `expected_roi_pct` on outcomes where set.
- **Actual ROI %** — arithmetic mean of `actual_roi_pct` where set.
- **Expected profit** — sum of `expected_profit`.
- **Actual profit** — sum of `actual_profit`.

Event metadata may update profit fields on append:

- `expected_profit`, `actual_profit`, `expected_roi_pct`, `actual_roi_pct` in `metadata_json` on `POST .../event`.

## Attribution logic

`recommendation_category` groups attribution analytics:

- `FIRST_APPEARANCE`, `VARIANT`, `KEY_ISSUE`, `PUBLISHER_EVENT`, `CREATOR_EVENT`, `GENERAL`

For each category the service counts outcomes and events (`PURCHASED`, `GRADED`, `SOLD`) and sums `actual_profit`.

## APIs

| Method | Path |
|--------|------|
| GET | `/api/v1/recommendation-feedback/analytics` |
| GET | `/api/v1/recommendation-feedback/performance` |
| GET | `/api/v1/recommendation-feedback/profitability` |
| GET | `/api/v1/recommendation-feedback/categories` |
| GET | `/api/v1/recommendation-feedback/dashboard` |

`analytics`, `performance`, and `dashboard` persist snapshot rows (`p73_recommendation_performance_snapshot`, profitability and category child tables).

## UI

- `/recommendation-analytics` — performance summary, adoption, ROI, category table, top/worst highlights.

## Known limitations

- Profit and ROI depend on explicit outcome fields or event metadata; there is no automatic join to P72 grading outcomes unless copied into metadata.
- Publisher / character / creator breakdowns use outcome columns only (not catalog enrichment).
- Multiple API calls each create a new snapshot (no deduplication by day).
- P67 `recommendation-performance` snapshots remain separate from P73 analytics tables.

## Verification

```bash
pytest tests/test_recommendation_analytics.py -v
pytest tests/test_recommendation_profitability.py -v
pytest tests/test_recommendation_performance.py -v
pytest tests/test_recommendation_categories.py -v
pytest tests/test_recommendation_dashboard.py -v
python -c "from app.main import app; print('app import ok')"
cd apps/web && npm run build
```
