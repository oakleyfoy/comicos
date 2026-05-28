# P41 API Reference

All automation routes live under **`/api/v1`** and use the **Scan API v1 envelope** (`data` + `meta` with `engine_versions`, optional `owner_user_id`, `snapshot_id`, `checksum`, `generated_at`).

## Envelope standard

- Success list responses: `data.items`, `data.pagination` (`total_count`, `limit`, `offset`, `has_next`), plus optional list metadata (e.g. drift counts on analytics lists).
- Success object responses: `data` is the serialized schema; `meta.checksum` often mirrors primary entity checksum.
- Errors on automation paths: `{ "error": { "code", "message", "details" } }` for HTTP and validation failures on automation route prefixes.

## Pagination standard

Query parameters: `limit` (1–500), `offset` (≥ 0). Services clamp via phase-specific `clamp_*_pagination` helpers.

## Mutation boundaries

| Capability | Owner | Ops admin |
| --- | --- | --- |
| Create jobs, schedules, triggers | Yes (where exposed) | Ops listing/diagnostics |
| Worker lease / execution | No | Yes |
| Recovery / dead-letter actions | Read | Yes |
| Batch execute / maintenance | Read | Yes |
| Notification / alert create | Read | Yes |
| Ops snapshot / audit / control | Read | Yes |
| Rules create / evaluate | Read | Yes |
| Analytics snapshot create | Read | Yes |

## Deterministic ordering expectations

- Jobs: queue status + `deterministic_rank` + id.
- Worker executions: rank + created_at + id.
- Workflow executions: workflow + created_at + id.
- Batch chunks: `chunk_rank`.
- Notification deliveries: `delivery_rank`.
- Ops metrics: category, rank, key.
- Rule actions: `action_rank`, type, scope.
- Analytics metrics: category, rank, key; trends by type/window/key; comparisons by type/key.

Engine version map: `apps/api/app/schemas/scan_api_v1.py` → `SCAN_API_V1_ENGINE_VERSIONS`.

---

## P41-01 — Jobs / queues (`automation_jobs`)

### Owner

| Method | Path |
| --- | --- |
| POST | `/automation/jobs` |
| GET | `/automation/jobs` |
| GET | `/automation/jobs/{job_id}` |
| GET | `/automation/jobs/{job_id}/attempts` |
| GET | `/automation/jobs/{job_id}/history` |
| GET | `/automation/jobs/{job_id}/issues` |
| GET | `/automation/jobs/{job_id}/artifacts/{artifact_id}` |

### Ops

| Method | Path |
| --- | --- |
| GET | `/ops/automation/queues` |
| GET | `/ops/automation/jobs` |
| GET | `/ops/automation/jobs/failed` |
| GET | `/ops/automation/jobs/dead-letter` |
| GET | `/ops/automation/issues` |
| GET | `/ops/automation/queue-health` |

---

## P41-02 — Workers (`automation_workers`)

### Owner

| Method | Path |
| --- | --- |
| GET | `/automation/workers` |
| GET | `/automation/workers/{worker_id}` |
| GET | `/automation/workers/{worker_id}/executions` |
| GET | `/automation/workers/{worker_id}/history` |
| GET | `/automation/workers/{worker_id}/issues` |

### Ops

| Method | Path |
| --- | --- |
| POST | `/ops/automation/workers/register` |
| POST | `/ops/automation/workers/{worker_id}/heartbeat` |
| POST | `/ops/automation/workers/{worker_id}/lease` |
| POST | `/ops/automation/workers/{worker_id}/lease/renew` |
| POST | `/ops/automation/workers/{worker_id}/execution/start` |
| POST | `/ops/automation/workers/{worker_id}/execution/complete` |
| POST | `/ops/automation/workers/{worker_id}/execution/fail` |
| POST | `/ops/automation/workers/release-expired` |
| GET | `/ops/automation/workers` |
| GET | `/ops/automation/workers/stale` |
| GET | `/ops/automation/workers/issues` |

---

## P41-03 — Scheduling / workflows (`automation_scheduling`)

### Owner

| Method | Path |
| --- | --- |
| POST | `/automation/schedules` |
| GET | `/automation/schedules` |
| GET | `/automation/schedules/{schedule_id}` |
| POST | `/automation/triggers` |
| GET | `/automation/triggers` |
| GET | `/automation/workflows` |
| GET | `/automation/workflows/{workflow_id}` |
| GET | `/automation/workflows/{workflow_id}/executions` |
| GET | `/automation/workflows/{workflow_id}/history` |

### Ops

| Method | Path |
| --- | --- |
| POST | `/ops/automation/process-schedules` |
| POST | `/ops/automation/process-triggers` |
| POST | `/ops/automation/workflows/{workflow_id}/execute` |
| GET | `/ops/automation/schedules` |
| GET | `/ops/automation/triggers` |
| GET | `/ops/automation/workflows` |
| GET | `/ops/automation/workflows/blocked` |
| GET | `/ops/automation/workflows/issues` |

---

## P41-04 — Recovery (`automation_recovery`)

### Owner

| Method | Path |
| --- | --- |
| GET | `/automation/recovery/runs` |
| GET | `/automation/recovery/runs/{run_id}` |
| GET | `/automation/dead-letter` |
| GET | `/automation/failures` |
| GET | `/automation/recovery/issues` |

### Ops

| Method | Path |
| --- | --- |
| POST | `/ops/automation/retry-policies` |
| POST | `/ops/automation/jobs/{job_id}/retry` |
| POST | `/ops/automation/jobs/{job_id}/dead-letter` |
| POST | `/ops/automation/jobs/{job_id}/replay-recovery` |
| POST | `/ops/automation/executions/{execution_id}/recover` |
| GET | `/ops/automation/recovery/runs` |
| GET | `/ops/automation/dead-letter` |
| GET | `/ops/automation/failures` |
| GET | `/ops/automation/recovery/issues` |
| GET | `/ops/automation/recovery/critical` |

---

## P41-05 — Batch (`automation_batch`)

### Owner

| Method | Path |
| --- | --- |
| GET | `/automation/batch/runs` |
| GET | `/automation/batch/runs/{batch_run_id}` |
| GET | `/automation/batch/runs/{batch_run_id}/chunks` |
| GET | `/automation/maintenance/jobs` |
| GET | `/automation/maintenance/results` |
| GET | `/automation/batch/issues` |

### Ops

| Method | Path |
| --- | --- |
| POST | `/ops/automation/batch/create` |
| POST | `/ops/automation/batch/{batch_run_id}/execute` |
| POST | `/ops/automation/maintenance/run` |
| GET | `/ops/automation/batch/runs` |
| GET | `/ops/automation/batch/failed` |
| GET | `/ops/automation/maintenance/jobs` |
| GET | `/ops/automation/maintenance/issues` |
| GET | `/ops/automation/storage-audit` |
| GET | `/ops/automation/integrity-audit` |

---

## P41-06 — Notifications (`automation_notifications`)

### Owner

| Method | Path |
| --- | --- |
| GET | `/automation/notifications` |
| GET | `/automation/notifications/{notification_id}` |
| GET | `/automation/alerts` |
| GET | `/automation/preferences` |
| GET | `/automation/notification/issues` |

### Ops

| Method | Path |
| --- | --- |
| POST | `/ops/automation/notifications/create` |
| POST | `/ops/automation/alerts/{alert_id}/acknowledge` |
| GET | `/ops/automation/notifications` |
| GET | `/ops/automation/alerts` |
| GET | `/ops/automation/alerts/critical` |
| GET | `/ops/automation/notification/issues` |
| GET | `/ops/automation/delivery-failures` |

---

## P41-07 — Ops dashboard (`automation_ops`)

### Owner

| Method | Path |
| --- | --- |
| GET | `/automation/ops/snapshots` |
| GET | `/automation/ops/snapshots/{snapshot_id}` |
| GET | `/automation/ops/metrics` |
| GET | `/automation/ops/audits` |
| GET | `/automation/ops/issues` |

### Ops

| Method | Path |
| --- | --- |
| POST | `/ops/automation/snapshots/create` |
| POST | `/ops/automation/audits/run` |
| POST | `/ops/automation/controls/apply` |
| GET | `/ops/automation/snapshots` |
| GET | `/ops/automation/metrics` |
| GET | `/ops/automation/audits` |
| GET | `/ops/automation/issues` |
| GET | `/ops/automation/system-health` |

---

## P41-08 — Rules (`automation_rules`)

### Owner

| Method | Path |
| --- | --- |
| GET | `/automation/rules` |
| GET | `/automation/rules/{rule_id}` |
| GET | `/automation/rules/{rule_id}/versions` |
| GET | `/automation/rules/{rule_id}/evaluations` |
| GET | `/automation/rules/{rule_id}/actions` |
| GET | `/automation/rules/issues` |

### Ops

| Method | Path |
| --- | --- |
| POST | `/ops/automation/rules/create` |
| POST | `/ops/automation/rules/{rule_id}/version` |
| POST | `/ops/automation/rules/{rule_id}/evaluate` |
| POST | `/ops/automation/rules/evaluate-system` |
| GET | `/ops/automation/rules` |
| GET | `/ops/automation/rules/failures` |
| GET | `/ops/automation/rules/issues` |
| GET | `/ops/automation/rules/drift` |

---

## P41-09 — Analytics (`automation_analytics`)

### Owner

| Method | Path |
| --- | --- |
| GET | `/automation/analytics/snapshots` |
| GET | `/automation/analytics/snapshots/{id}` |
| GET | `/automation/analytics/metrics` |
| GET | `/automation/analytics/trends` |
| GET | `/automation/analytics/comparisons` |
| GET | `/automation/analytics/issues` |

### Ops

| Method | Path |
| --- | --- |
| POST | `/ops/automation/analytics/create` |
| GET | `/ops/automation/analytics/snapshots` |
| GET | `/ops/automation/analytics/trends` |
| GET | `/ops/automation/analytics/comparisons` |
| GET | `/ops/automation/analytics/failures` |
| GET | `/ops/automation/analytics/drift` |
| GET | `/ops/automation/analytics/system-intelligence` |

---

## Frontend client

TypeScript helpers live in `apps/web/src/api/client.ts` (`listAutomation*`, `listOpsAutomation*`). The UI performs no checksum or ordering logic; it displays API results only.
