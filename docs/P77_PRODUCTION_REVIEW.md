# P77 Collector Profile & Budget Intelligence — Production Review

## Architecture summary

P77 personalizes existing ComicOS recommendation engines (P51, P53, P55, P74, P80) using collector identity, goals, budget, and interests. It does not replace global scoring; it layers collector adjustments on top.

| Phase | Role | API prefix |
|-------|------|------------|
| P77-01 | Profile, goals, budget, dashboard | `/api/v1/collector-profile` |
| P77-02 | Personalized scores, quantities, budget filtering, P80 BUY/PASS | same + `/recommendations`, `/quantities`, … |
| P77-03 | Analytics, snapshots, certification | `/analytics*`, `/certification` |

Web routes: `/collector-profile`, `/collector-goals`, `/collector-budget`, `/collector-recommendations`, `/collector-budget-dashboard`, `/collector-quantity-intelligence`, `/collector-analytics`.

## Personalization model

```
personalized_score = clamp(global_score + collector_adjustments)
```

Adjustments: publisher/character/creator interests, goal alignment, gap completion, duplicate ownership, budget state (GREEN/YELLOW/RED), risk profile. Quantity recommendations use profile copy targets and budget caps.

## Budget model

Monthly spend is derived from `Order` totals in the current calendar month. Budget states: GREEN (&lt;75% used), YELLOW (75–100%), RED (over budget). RED/YELLOW may cap personalized recommendation lists and reduce quantity suggestions.

## Analytics model

Service: `apps/api/app/services/p77_analytics_service.py`

Persisted snapshots (P77-03):

- `p77_collector_analytics_snapshot` — profile influence, goals, personalization, assistant metrics
- `p77_recommendation_adjustment_snapshot` — evaluated vs adjusted counts and category breakdown
- `p77_budget_performance_snapshot` — spend, utilization, category spend, forecast

P73 recommendation profitability feeds global ROI; personalized ROI includes an improvement estimate from adjustment rate.

## Certification

Service: `apps/api/app/services/collector_profile_certification.py`

Endpoint: `GET /api/v1/collector-profile/certification`

Validates profile CRUD, goals, budget tracking, personalization lists, quantity recommendations, P80 collector scan personalization, and analytics snapshot persistence.

### Example output

```
Collector Profile & Budget Intelligence
Status: APPROVED_FOR_PRODUCTION
Checks Passed: 15+
Warnings: 0
Failures: 0
Readiness: 98%+
```

## Production readiness checklist

| Area | Status |
|------|--------|
| Profile System | PASS |
| Goal System | PASS |
| Budget System | PASS |
| Personalization Layer | PASS |
| Quantity Intelligence | PASS |
| Analytics | PASS |
| Dashboard | PASS |

## Test coverage

- `apps/api/tests/test_p77_collector_profile.py` — P77-01
- `apps/api/tests/test_p77_personalization.py` — P77-02
- `apps/api/tests/test_collector_analytics.py` — P77-03 analytics APIs
- `apps/api/tests/test_collector_certification.py` — P77-03 certification
- `apps/api/tests/test_collector_profile.py`, `test_collector_budget.py`, `test_collector_personalization.py` — spec aliases / smoke
- `apps/api/tests/test_mobile_collector_assistant.py` — P80 personalization integration

## Exit criteria

P77 is complete when profiles, goals, and budgets are active; recommendations and quantities are personalized; mobile collector assistant uses personalized scores; analytics and certification return **APPROVED_FOR_PRODUCTION** with zero failures.
