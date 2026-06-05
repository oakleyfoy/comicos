# P65 Collector Experience Platform

P65 turns certified P61–P64 intelligence into collector actions. It does **not** add recommendation engines or mutate upstream intelligence rows.

## Components

| Phase | Capability | API prefix |
|-------|------------|------------|
| P65-01 | Collector Workspace (tasks) | `/api/v1/collector-workspace` |
| P65-02 | AI Collector Assistant Phase B (narratives) | `/api/v1/collector-narratives` |
| P65-03 | Automation Platform | `/api/v1/collector-automation` |
| P65-04 | Notification Center | `/api/v1/notifications` |

## Feature flags

| Flag | Default |
|------|---------|
| `P65_COLLECTOR_WORKSPACE_ENABLED` | true |
| `P65_LLM_NARRATION_ENABLED` | false |
| `P65_AUTOMATION_ENABLED` | true |
| `P65_NOTIFICATION_CENTER_ENABLED` | true |

## Data model

- `CollectorTaskSnapshot` / `CollectorTaskItem`
- `CollectorNarrativeSnapshot` / `CollectorNarrativeItem`
- `AutomationSubscription` / `AutomationRun`
- `NotificationSnapshot` / `NotificationItem`

Migration: `20260610_0225_add_p65_collector_experience.py`

## UI

Route: `/collector-workspace` — tasks by lane, notifications, weekly briefing, narratives, opportunity feed.

## Certification

`GET /api/v1/collector-workspace/platform/certification` and `docs/P65_COLLECTOR_EXPERIENCE_CERTIFICATION_REPORT.md`.

Tests: `tests/test_collector_workspace.py`, `test_collector_narratives.py`, `test_collector_automation.py`, `test_notification_center.py`, `test_p65_collector_experience.py`.
