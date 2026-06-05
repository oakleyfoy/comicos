# P65 Phase 1 — Collector Workspace

## Purpose

Action center aggregating BUY, SELL, GRADE, ACQUIRE, WATCH, and REVIEW tasks from read-only P62/P63/P64 outputs and P64 assistant lanes.

## Service

`CollectorWorkspaceService` → `app/services/collector_workspace_service.py`

## Endpoints

- `GET /api/v1/collector-workspace/tasks/latest?task_type=`
- `POST /api/v1/collector-workspace/tasks/build`
- `GET /api/v1/collector-workspace/tasks/history`
- `PATCH /api/v1/collector-workspace/tasks/{id}`
- `PATCH /api/v1/collector-workspace/tasks/bulk`

Status values: `NEW`, `IN_PROGRESS`, `COMPLETED`, `DISMISSED`. Prior statuses carry forward on rebuild via stable source keys.
