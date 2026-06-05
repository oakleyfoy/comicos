# P64 Phase A — Deterministic Collector Assistant MVP

**Status:** Implemented.

**Goal:** Owner-scoped collector guidance from P61–P63 snapshots without LLM narration or upstream mutation.

---

## Persistence

| Model | Table |
|-------|--------|
| `CollectorAssistantRun` | `collector_assistant_run` |
| `CollectorBriefingSnapshot` | `collector_briefing_snapshot` |
| `CollectorRecommendationSnapshot` | `collector_recommendation_snapshot` |
| `CollectorRecommendationItem` | `collector_recommendation_item` |
| `CollectorHealthSnapshot` | `collector_health_snapshot` |
| `CollectorOpportunityAlertSnapshot` | `collector_opportunity_alert_snapshot` |
| `CollectorOpportunityAlert` | `collector_opportunity_alert` |
| `CollectorExecutiveBundle` | `collector_executive_bundle` |

Migration: `20260609_0224_add_p64_collector_assistant_phase_a.py`

---

## Services

| Service | Role |
|---------|------|
| `collector_assistant_context_service` | Read-only load of P62/P63 latest snapshots + inventory gate |
| `collector_lane_builder_service` | Deterministic lane drafts, briefing JSON, health, alerts |
| `collector_assistant_orchestrator` | `run_collector_assistant_build(scope=full\|lanes)` |
| `collector_assistant_certification_service` | Platform cert + upstream non-mutation check |

---

## Readiness (`NOT_READY`)

- Owner with inventory but no P63 portfolio snapshot
- Owner with inventory but no P63 sell snapshot
- Empty owner (no inventory and no P62/P63 snapshots)

---

## API

Base: `/api/v1/collector-assistant`

| Method | Path |
|--------|------|
| `GET` | `/briefing/latest` |
| `POST` | `/briefing/build` (full platform build) |
| `GET` | `/recommendations/latest` |
| `POST` | `/recommendations/build` (lanes only) |
| `GET` | `/health/latest` |
| `GET` | `/alerts/latest` |
| `GET` | `/dashboard/latest` |
| `POST` | `/platform/build` |
| `GET` | `/platform/certification` |

---

## Feature flags

| Flag | Default |
|------|---------|
| `P64_COLLECTOR_ASSISTANT_ENABLED` | `true` |
| `P64_LLM_NARRATION_ENABLED` | `false` |

---

## Tests

`apps/api/tests/test_p64_collector_assistant.py`
