# P67 Portfolio Analytics Platform

Transforms ComicOS collector intelligence (P61–P66) into an **investment analytics layer** without mutating demand, recommendation, or variant scoring tables.

## Phases

| Phase | Doc | Service | API prefix |
|-------|-----|---------|------------|
| P67-01 Portfolio Performance | [P67_PHASE_1_PORTFOLIO_PERFORMANCE.md](P67_PHASE_1_PORTFOLIO_PERFORMANCE.md) | `portfolio_analytics_service` | `/api/v1/portfolio-analytics` |
| P67-02 Collection Analytics | [P67_PHASE_2_COLLECTION_ANALYTICS.md](P67_PHASE_2_COLLECTION_ANALYTICS.md) | `collection_analytics_service` | `/api/v1/collection-analytics` |
| P67-03 Recommendation Performance | [P67_PHASE_3_RECOMMENDATION_PERFORMANCE.md](P67_PHASE_3_RECOMMENDATION_PERFORMANCE.md) | `recommendation_performance_service` | `/api/v1/recommendation-performance` |
| P67-04 Grading Analytics | [P67_PHASE_4_GRADING_ANALYTICS.md](P67_PHASE_4_GRADING_ANALYTICS.md) | `grading_analytics_service` | `/api/v1/grading-analytics` |
| P67-05 Investor Dashboard | [P67_PHASE_5_INVESTOR_DASHBOARD.md](P67_PHASE_5_INVESTOR_DASHBOARD.md) | `investor_dashboard_service` | `/api/v1/investor-dashboard` |

## Data sources (read-only)

- **Inventory / FMV:** `inventory_copy.current_fmv`, `market_intelligence_inventory` helpers; P66 `market_price_observation` stub FMV when copy FMV missing.
- **Recommendations:** `cross_system_recommendation` (P62 output).
- **Variant / grading context:** P66 `variant_decision_*` snapshots.
- **No writes** to P61 demand, P62 ranking, P66 decision engines.

## Orchestration

- `POST /api/v1/portfolio-analytics/platform/build` — runs all five builders + investor dashboard.
- `GET /api/v1/portfolio-analytics/platform/certification` — owner-scoped readiness checks.

## Models

Tables prefixed `p67_*` in `app/models/portfolio_analytics_platform.py` (migration `20260613_0228`).

## Frontend

Route: `/portfolio-analytics` — `PortfolioAnalyticsPage.tsx`, API helper `apps/web/src/api/p67PortfolioAnalytics.ts`.

## Feature flags (default `true`)

`P67_PORTFOLIO_ANALYTICS_ENABLED`, `P67_COLLECTION_ANALYTICS_ENABLED`, `P67_RECOMMENDATION_PERFORMANCE_ENABLED`, `P67_GRADING_ANALYTICS_ENABLED`, `P67_INVESTOR_DASHBOARD_ENABLED`.

## Tests

`tests/test_portfolio_analytics.py`, `test_collection_analytics.py`, `test_recommendation_performance.py`, `test_grading_analytics.py`, `test_investor_dashboard.py`, `test_p67_portfolio_analytics_platform.py`.
