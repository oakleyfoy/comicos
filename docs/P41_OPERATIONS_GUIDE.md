# P41 Operations Guide

## Audience

Ops administrators (configured via `OPS_ADMIN_EMAILS`) and owners reading automation visibility in the web app. This guide describes safe operational procedures; it does not authorize destructive cleanup.

## Surfaces

| Area | Owner UI route | Ops panel anchor |
| --- | --- | --- |
| Jobs / queues | `/automation-jobs` | `#automation-jobs-ops` |
| Workers | `/automation-workers` | `#automation-workers-ops` |
| Workflows | `/automation-workflows` | `#automation-workflows-ops` |
| Recovery | `/automation-recovery` | `#automation-recovery-ops` |
| Batch | `/automation-batch` | `#automation-batch-ops` |
| Notifications | `/automation-notifications` | `#automation-notifications-ops` |
| Ops dashboard | `/automation-ops` | `#automation-ops-ops` |
| Rules | `/automation-rules` | `#automation-rules-ops` |
| Analytics | `/automation-analytics` | `#automation-analytics-ops` |

## Queue operations

- **Inspect depth:** owner job list; ops `GET /ops/automation/queues`, `GET /ops/automation/queue-health`.
- **Pause / resume:** ops safe control via ops dashboard (`PAUSE_QUEUE` / `RESUME_QUEUE`) or rules actions; never delete queue.
- **Stuck jobs:** identify `RESERVED`/`RUNNING` with expired lease; run `POST /ops/automation/workers/release-expired`, then review job history and recovery.

## Worker operations

- Register worker (ops), maintain heartbeats, acquire/renew/release leases.
- **Stale workers:** `GET /ops/automation/workers/stale`; investigate missing heartbeats before forcing lease release.
- Review executions and issues on owner worker detail routes.

## Workflow operations

- Create schedules/triggers (owner where permitted); ops `process-schedules`, `process-triggers`, `workflows/{id}/execute`.
- **Failed workflows:** `GET /ops/automation/workflows/issues`, blocked workflows endpoint; inspect execution manifest checksum.
- Pause/resume via ops controls only (non-destructive).

## Recovery operations

- Define retry policies (ops POST).
- Per-job retry, dead-letter, replay-recovery, execution recover endpoints (ops).
- Monitor `GET /ops/automation/dead-letter`, `GET /ops/automation/recovery/critical`.

## Batch / maintenance

- Create batch (ops), execute chunks, run maintenance jobs.
- Use storage/integrity audit ops endpoints on batch layer for drift diagnostics.
- Batch failures: `GET /ops/automation/batch/failed`, maintenance issues.

## Notifications / alerts

- Create notifications (ops); owners read ledger.
- Acknowledge alerts (ops).
- Delivery failures: `GET /ops/automation/delivery-failures`.

## Ops dashboard

- Create snapshot, run audits, apply **allowed** controls only.
- System health: `GET /ops/automation/system-health`.
- Investigate ops issues list before applying controls.

## Rules engine

- Create rules/versions (ops), evaluate single rule or system rules.
- Review drift/failures ops lists; do not inject arbitrary code—expressions are AST-restricted.

## Analytics (P41-09)

- Create analytics snapshot (ops POST create); owners read metrics/trends/comparisons.
- Use drift/failures/system-intelligence ops routes for replay and utilization warnings.

## Safe admin controls

See [P41_OPS_DASHBOARD_ARCHITECTURE.md](./P41_OPS_DASHBOARD_ARCHITECTURE.md). Destructive control types return **403 Forbidden**.

## Troubleshooting playbooks

### Stuck jobs

1. Confirm job status and reservation token on job detail.
2. Check worker lease expiry; release expired leases (ops).
3. If worker crashed, fail execution (ops) and enqueue recovery retry.
4. Append-only history must explain each transition—do not edit rows manually.

### Stale workers

1. List stale workers (ops).
2. Verify heartbeats stopped intentionally vs network partition.
3. Release leases; mark worker shutdown if decommissioned.

### Failed workflows

1. Fetch workflow issues/blocked (ops).
2. Inspect last execution manifest checksum vs prior successful run.
3. Fix upstream job failure; re-execute workflow (ops) with new replay key if idempotency required.

### Dead-letter growth

1. Trend via analytics or ops snapshot metrics.
2. Classify failure reasons from recovery/failure events.
3. Retry individually via ops retry endpoints; **do not purge** dead-letter table.

### Retry exhaustion

1. Confirm retry policy `max_attempts` and deterministic backoff settings.
2. Dead-letter job should exist with checksum lineage.
3. Optional notification/alert already emitted—acknowledge and track remediation.

### Notification failures

1. `GET /ops/automation/delivery-failures`.
2. Inspect delivery checksum and channel; preferences may disable channel.
3. Re-create notification with new replay key only through ops create (idempotent keys prevent duplicates).

### Replay / checksum warnings

1. Scan replay issues feed ops/analytics visibility.
2. Run ops replay verify control where applicable.
3. Compare manifest checksums; escalate to scan replay docs if scan-side drift.

### Queue pause / resume

Use ops dashboard control or rules `PAUSE_QUEUE` / `RESUME_QUEUE` actions. Document reason in ops history metadata.

### Workflow pause / resume

Same pattern via ops workflow controls; verify workflow status in owner UI.

## Known operational limitations

- No distributed workers or queue sharding in P41.
- No realtime websocket telemetry; refresh via API/UI polling.
- No external email/SMS delivery providers wired (ledger-only deliveries).
- No autoscaling or destructive cleanup automation.
- Full API regression may include unrelated market/listing failures; use focused P41 pytest list for automation sign-off.

## Deployment notes

- Run Alembic to head `20260623_0111` (or later single head) before enabling ops routes in production.
- Configure storage roots under `data/` or env overrides (see [P41_STORAGE_ARCHITECTURE.md](./P41_STORAGE_ARCHITECTURE.md)).
- Set `OPS_ADMIN_EMAILS` in production; validate CORS and auth as for rest of API.
