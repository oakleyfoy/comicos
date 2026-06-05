# P65 Collector Experience Certification Report

**Status:** Certified (automated test suite)  
**Date:** 2026-06-03  
**Source version:** P65  
**Migration:** `20260610_0225`

## Scope

Verifies P65 action layer on top of P61–P64 without mutating upstream intelligence tables.

## Checks

| Check | Method |
|-------|--------|
| Task generation | `POST /tasks/build` + `GET /tasks/latest` |
| Status updates | `PATCH /tasks/{id}` |
| Notifications | `POST /notifications/build` + status patch |
| Narratives | `POST /collector-narratives/build` |
| Automation | `POST /collector-automation/run/DAILY_OPPORTUNITY_DIGEST` |
| Owner isolation | Second owner has no task snapshot |
| Non-mutation | Global counts of `BuyQueueSnapshot`, `PortfolioPerformanceSnapshot`, `CollectorAssistantRun` unchanged during certification build |

## API certification

`GET /api/v1/collector-workspace/platform/certification` returns `certified`, `platform_ready`, `checks`, and `non_mutation`.

## Tests executed

```
pytest tests/test_collector_workspace.py \
  tests/test_collector_narratives.py \
  tests/test_collector_automation.py \
  tests/test_notification_center.py \
  tests/test_p65_collector_experience.py
```

**Result:** 8 passed (local SQLite test harness).

## Production note

Run `alembic upgrade head` through `20260610_0225` on Render Postgres before enabling routes in production. Re-run certification per owner after upstream P62–P64 builds are fresh.

## Feature flags (production defaults)

- `P65_COLLECTOR_WORKSPACE_ENABLED=true`
- `P65_LLM_NARRATION_ENABLED=false`
- `P65_AUTOMATION_ENABLED=true`
- `P65_NOTIFICATION_CENTER_ENABLED=true`
