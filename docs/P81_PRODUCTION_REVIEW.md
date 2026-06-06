# P81 Future Release Discovery Intelligence — Production Review

## Architecture summary

P81 identifies and personalizes future comic opportunities before they enter standard buying workflows.

| Phase | Role | API prefix |
|-------|------|------------|
| P81-01 | Ingestion, scoring, registry, global feed | `/api/v1/discovery/feed`, `/opportunities` |
| P81-02 | P77 personalization, watchlists, alerts, future pull list | `/personalized`, `/watchlists`, `/alerts`, `/future-pull-list` |
| P81-03 | Analytics snapshots, ROI, certification | `/analytics*`, `/certification` |

Upstream: P50 Lunar releases, P74 release monitoring, external catalog. Personalization: P77 collector profile engine (no duplicate recommendation engine).

## Discovery engine (P81-01)

- Registry states: `DISCOVERED` → `QUALIFIED` → `SCORED` → `PUBLISHED`
- Global score 0–100 with categories `MUST_WATCH`, `HIGH_OPPORTUNITY`, `WATCH`, `LOW_PRIORITY`
- Signals: #1, milestone, anniversary, creators, franchises, variant ratios

## Personalization (P81-02)

```text
personalized_score = min(110, discovery_score + collector_adjustments)
```

Categories: `MUST_BUY`, `HIGH_PRIORITY`, `WATCH`, `LOW_PRIORITY`, `IGNORE`

Auto-watchlists from P77 publishers, characters, creators, and goal titles. Alerts prioritized `CRITICAL` / `HIGH` / `NORMAL` / `LOW`. Future pull pipeline: `DISCOVERED` → `WATCHING` → `ANNOUNCED` → `FOC` → `PURCHASED`.

## Analytics (P81-03)

Persisted snapshots:

- `p81_discovery_analytics_snapshot` — activity (discovered, published, viewed, saved, purchased)
- `p81_discovery_opportunity_performance_snapshot` — category conversion
- `p81_discovery_alert_performance_snapshot` — sent, opened, clicked, converted
- `p81_discovery_roi_snapshot` — FMV growth highlights, portfolio ROI

Dashboard: `GET /api/v1/discovery/analytics-dashboard` — activity, opportunity performance, alerts, watchlists, future pull accuracy, ROI, personalization impact.

## Certification

Service: `apps/api/app/services/discovery_certification.py`  
Endpoint: `GET /api/v1/discovery/certification`

Validates ingestion, registry, scoring, feed, personalization, watchlists, alerts, future pull list, and analytics persistence.

### Production readiness checklist

| Area | Status |
|------|--------|
| Discovery Feed | PASS |
| Discovery Scoring | PASS |
| Watchlists | PASS |
| Alerts | PASS |
| Future Pull List | PASS |
| Analytics | PASS |

## Test coverage

- `test_discovery_feed.py`, `test_discovery_scoring.py`, `test_discovery_ingestion.py`, `test_discovery_opportunity_detection.py`
- `test_discovery_personalization.py`, `test_discovery_watchlists.py`, `test_discovery_alerts.py`, `test_future_pull_list.py`
- `test_discovery_analytics.py`, `test_discovery_certification.py`, `test_discovery_dashboard.py`

## Web routes

`/discovery-feed`, `/discovery-dashboard`, `/discovery-opportunities`, `/discovery-analytics`, `/future-pull-list`, `/discovery-watchlists`, `/discovery-alerts`

## Exit criteria

ComicOS discovers future opportunities, scores and personalizes them, maintains watchlists and alerts, tracks future pull recommendations, measures discovery and ROI performance, and passes `discovery-certification` for production use.
