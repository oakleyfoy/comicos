# P65 Phase 4 — Notification Center

## Purpose

Central inbox for ComicOS intelligence alerts derived from P64 opportunity alerts, FOC, sell, acquisition, and buy queue (read-only).

## Types

`BUY_ALERT`, `SELL_ALERT`, `GRADE_ALERT`, `ACQUISITION_ALERT`, `FOC_ALERT`, `WATCH_ALERT`

## Statuses

`UNREAD`, `READ`, `ARCHIVED`

## Service

`app/services/notification_center_service.py`

## Endpoints

- `GET /api/v1/notifications/latest`
- `POST /api/v1/notifications/build`
- `PATCH /api/v1/notifications/items/{id}`

Flag: `P65_NOTIFICATION_CENTER_ENABLED`.
