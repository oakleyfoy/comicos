# P74 Release Monitoring & FOC Intelligence — Production Review

## Status

| Phase | Scope | Status |
|-------|--------|--------|
| P74-01 | Release intelligence monitoring | **COMPLETE** |
| P74-02 | FOC & purchase intelligence | **COMPLETE** |
| P74-03 | Release analytics & certification | **COMPLETE** |

**Platform status:** `APPROVED_FOR_PRODUCTION`

P74-03 does **not** place orders, modify retailer carts, retrain recommendation engines, or add autonomous purchasing.

## Architecture

```
Release import (P50) ──► Monitoring (P74-01) ──► Change history / watchlists
                              │
                              ▼
                    FOC & purchase intel (P74-02)
                              │
                              ▼
              Outcome sync + analytics snapshots (P74-03)
                              │
                              ▼
         Certification + analytics dashboard + REST APIs
```

### Key modules

| Layer | Module |
|-------|--------|
| Outcomes | `release_outcome_service.py` |
| Analytics | `release_analytics_service.py` |
| Certification | `release_intelligence_certification.py` |
| Snapshots | `P74ReleaseAnalyticsSnapshot`, `P74FocPerformanceSnapshot`, `P74QuantityRecommendationSnapshot`, `P74ReleaseCategorySnapshot` |

## Release lifecycle

1. **Discover** — feed import creates/updates `ReleaseIssue` / variants; P74-01 records events and changes.
2. **Advise** — P74-02 generates FOC watch, purchase actions (BUY / WATCH / PASS), and quantity recommendations.
3. **Measure** — P74-03 syncs outcomes from latest purchase recommendations vs ordered/owned proxies.
4. **Certify** — production checklist validates monitoring, change detection, FOC, purchase, analytics, dashboard, and performance persistence.

## FOC methodology

- FOC accuracy uses outcome **SUCCESS** rate across synced release outcomes.
- Upgrade/downgrade accuracy uses `P74RecommendationChangeEvent` rows (`UPGRADED` / `DOWNGRADED`).
- Missed opportunity rate: failures where a positive quantity was recommended but not purchased.

## Quantity methodology

- Success/failure derived from recommended vs actual purchased quantity and purchase action (PASS/WATCH success when zero purchase is intended).
- ROI/profit are **estimated** from priority score and fill rate (proxy until live market settlement is wired).
- Actions rolled up: BUY 2, BUY 4, WATCH, PASS via `by_action_json` on quantity snapshots.

## Category analytics

Categories include: `NUMBER_ONE`, `VARIANT`, `RATIO_VARIANT`, `MILESTONE_ISSUE`, `FIRST_APPEARANCE`, `CREATOR_EVENT`, `PUBLISHER_LAUNCH`, `SERIES_RELAUNCH` (from issue signals, variants, and series metadata).

## APIs (v1)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/release-monitoring/analytics` | Latest analytics snapshot summary |
| `GET /api/v1/release-monitoring/performance` | Combined performance + recent outcomes |
| `GET /api/v1/release-monitoring/foc-accuracy` | FOC accuracy metrics |
| `GET /api/v1/release-monitoring/categories` | Category performance list |
| `GET /api/v1/release-monitoring/certification` | Production certification |
| `GET /api/v1/release-monitoring/analytics-dashboard` | P74-03 analytics dashboard |

P74-01 monitoring dashboard remains at `GET /api/v1/release-monitoring/dashboard`.

## Certification results

`run_release_intelligence_certification` validates:

- Monitoring snapshot
- Change detection pipeline
- FOC intelligence snapshot
- Purchase/outcome sync
- Analytics snapshot persistence
- Dashboard/analytics persistence
- Performance metrics

All checks must pass for `approved_for_production: true`.

## Known limitations

- Ordered/owned quantities are proxies (pull list / collection), not retailer POS data.
- Market and inventory performance percentages mirror estimated ROI, not live sales velocity.
- Category buckets depend on import richness (signals, variants).
- No automatic order placement or cart integration (by design).

## UI

- **Release Monitoring** — `/release-monitoring` (P74-01)
- **FOC & Purchase Intel** — `/foc-purchase-intelligence` (P74-02)
- **Release Analytics** — `/release-intelligence-analytics` (P74-03)

## Verification

```bash
pytest apps/api/tests/test_release_analytics.py -v
pytest apps/api/tests/test_foc_accuracy.py -v
pytest apps/api/tests/test_quantity_accuracy.py -v
pytest apps/api/tests/test_release_categories.py -v
pytest apps/api/tests/test_release_dashboard.py -v
pytest apps/api/tests/test_p74_production_review.py -v
python -c "from app.main import app; print('app import ok')"
cd apps/web && npm run build
```
