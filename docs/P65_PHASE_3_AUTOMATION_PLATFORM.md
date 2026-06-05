# P65 Phase 3 — Automation Platform

## Purpose

Deliver intelligence on schedules via in-app, email, or digest delivery types (in-app/digest wired; email is subscription metadata only).

## Kinds

- `WEEKLY_BRIEFING` — builds narratives
- `DAILY_OPPORTUNITY_DIGEST` — rebuilds tasks + notifications
- `FOC_REMINDER`, `SELL_SIGNAL_REMINDER`, `ACQUISITION_REMINDER` — notification refresh

## Service

`app/services/collector_automation_service.py`

## Endpoints

- `GET /api/v1/collector-automation/subscriptions`
- `GET /api/v1/collector-automation/runs/latest`
- `POST /api/v1/collector-automation/run/{automation_kind}`
- `POST /api/v1/collector-automation/run-all`

Flag: `P65_AUTOMATION_ENABLED`.
