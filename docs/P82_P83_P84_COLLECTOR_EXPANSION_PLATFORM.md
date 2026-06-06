# P82 / P83 / P84 — Collector Expansion Platform

Combined ComicOS workflow layer for marketplace acquisition intelligence, advanced collection valuation, and proactive notifications/briefings.

## Architecture

| Layer | Platform | Primary services |
|--------|----------|------------------|
| Deals | P82 | `marketplace_acquisition_service.py` |
| Portfolio | P83 | `collection_valuation_service.py`, `collection_scenario_service.py` |
| Proactive | P84 | `collector_notification_service.py`, `collector_briefing_service.py` |
| Unified | P82–P84 | `collector_command_center_service.py`, `collector_expansion_certification.py` |

Reuses P68 FMV snapshots, P77 personalization, P78 sell queue, and P81 discovery/future pull without duplicating those engines.

## Models (tables)

- `p82_marketplace_acquisition_opportunity`, `p82_marketplace_acquisition_snapshot`
- `p83_collection_valuation_snapshot`, `p83_collection_risk_snapshot`, `p83_collection_scenario_run`
- `p84_collector_notification`, `p84_collector_briefing`

Migration: `20260607_0254_add_p82_p84_collector_expansion.py`

## APIs

| Router prefix | Endpoints |
|---------------|-----------|
| `/api/v1/marketplace-acquisition` | `GET /opportunities`, `GET /opportunities/{id}`, `POST /scan`, `GET /dashboard` |
| `/api/v1/collection-valuation` | `GET /forecast`, `GET /risk`, `POST /scenario`, `GET /optimization`, `GET /dashboard` |
| `/api/v1/notifications` | `GET /`, `PUT /{id}`, `GET /dashboard` |
| `/api/v1/briefings` | `GET /daily`, `GET /weekly`, `POST /generate` |
| `/api/v1/collector-command-center` | `GET /` |
| `/api/v1/collector-expansion/certification` | `GET /certification` |

Scan API engine keys: `marketplace_acquisition` (P82), `collection_valuation` (P83), `collector_notifications` (P84), `collector_command_center` / `collector_expansion_certification` (P82–P84).

## Workflows

1. **Acquisition** — Ingest or `POST /scan` listing payloads; score vs FMV, liquidity, P77 profile; persist opportunities and dashboard snapshots.
2. **Valuation** — Forecast 30d–12mo horizons, risk factors, optimization (sell/grade/buy), scenario runs.
3. **Notifications** — Refresh derives marketplace deals, budget, and portfolio risk alerts; lifecycle UNREAD → READ / DISMISSED / SAVED.
4. **Briefings** — Daily (actions today) and weekly (FMV, budget, missed deals) persisted per owner/date.
5. **Command center** — Single payload aggregating all major signals.

## Web dashboards

- `/collector-command-center`
- `/marketplace-opportunities`, `/marketplace-opportunity/:id`, `/marketplace-acquisition-dashboard`
- `/collection-forecast`, `/collection-risk`, `/collection-scenarios`, `/collection-optimization`, `/collection-valuation-dashboard`
- `/notifications`, `/notification-dashboard`, `/daily-briefing`, `/weekly-briefing`

## Certification

`GET /api/v1/collector-expansion/certification` runs end-to-end checks (scan, forecast, risk, scenario, notifications, briefings, command center). Expected status: **APPROVED_FOR_PRODUCTION**.

## Tests

- `tests/test_p82_marketplace_acquisition.py` (P82; distinct from legacy P55 `test_marketplace_acquisition.py`)
- `tests/test_collection_valuation.py`, `tests/test_collection_scenarios.py`
- `tests/test_collector_notifications.py`, `tests/test_collector_briefings.py`
- `tests/test_collector_command_center.py`, `tests/test_collector_expansion_certification.py`

## Production readiness checklist

- [ ] Migration `0254` applied
- [ ] Scan metadata keys present in `/api/v1` envelope
- [ ] Certification returns `APPROVED_FOR_PRODUCTION` for seeded owner
- [ ] Web nav links resolve (command center + required routes)
- [ ] No automatic purchasing or payment flows (out of scope)
