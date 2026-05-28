# P41 Architecture Index

## Overview

P41 is ComicOS’s deterministic automation and workflow engine. It provides queue-backed job ledgers, worker runtime, workflow orchestration, retry/recovery, batch/maintenance processing, notifications and alerts, operational dashboarding, policy rules, operational analytics (P41-09), and this closeout package (P41-10).

Design themes across P41:

- Deterministic ordering and checksum lineage
- Replay-safe manifests and idempotent creation keys
- Append-only history (no in-place mutation of immutable payloads)
- Owner/org isolation on owner routes; privileged mutation on ops routes only
- Safe admin controls (no destructive queue purge, dead-letter delete, or force-overwrite replay)

## Phase map

| Phase | Focus | Engine key | Architecture doc |
| --- | --- | --- | --- |
| P41-01 | Queue / job foundation | `automation_jobs` | [P41_AUTOMATION_QUEUE_ARCHITECTURE.md](./P41_AUTOMATION_QUEUE_ARCHITECTURE.md) |
| P41-02 | Worker runtime | `automation_workers` | [P41_WORKER_RUNTIME_ARCHITECTURE.md](./P41_WORKER_RUNTIME_ARCHITECTURE.md) |
| P41-03 | Workflow / schedule / triggers | `automation_scheduling` | [P41_WORKFLOW_SCHEDULING_ARCHITECTURE.md](./P41_WORKFLOW_SCHEDULING_ARCHITECTURE.md) |
| P41-04 | Retry / recovery / dead-letter | `automation_recovery` | [P41_RECOVERY_ARCHITECTURE.md](./P41_RECOVERY_ARCHITECTURE.md) |
| P41-05 | Batch / maintenance | `automation_batch` | [P41_BATCH_PROCESSING_ARCHITECTURE.md](./P41_BATCH_PROCESSING_ARCHITECTURE.md) |
| P41-06 | Notifications / alerts | `automation_notifications` | [P41_NOTIFICATION_ARCHITECTURE.md](./P41_NOTIFICATION_ARCHITECTURE.md) |
| P41-07 | Ops dashboard / safe controls | `automation_ops` | [P41_OPS_DASHBOARD_ARCHITECTURE.md](./P41_OPS_DASHBOARD_ARCHITECTURE.md) |
| P41-08 | Rules engine | `automation_rules` | [P41_RULES_ENGINE_ARCHITECTURE.md](./P41_RULES_ENGINE_ARCHITECTURE.md) |
| P41-09 | Analytics / intelligence (deterministic) | `automation_analytics` | [P41_ANALYTICS_ARCHITECTURE.md](./P41_ANALYTICS_ARCHITECTURE.md) |
| P41-10 | Closeout / docs / readiness | — | This index and companion closeout docs |

Related scan platform context (not P41 core automation, but integrated in ops/analytics visibility):

- P41-17 scan intelligence feed — `docs/SCAN_INTELLIGENCE_FEED_ARCHITECTURE.md`
- P40-18 scan replay — `docs/SCAN_REPLAY_ARCHITECTURE.md`

## System dependency map (summary)

See [P41_DEPENDENCY_GRAPH.md](./P41_DEPENDENCY_GRAPH.md) for diagrams and lineage chains.

High level:

1. **Queues** hold **jobs** with deterministic rank ordering.
2. **Workers** lease jobs and record **executions**.
3. **Schedules/triggers** activate **workflows** that enqueue downstream jobs.
4. **Failures** flow into **recovery** and optionally **dead-letter**.
5. **Notifications/alerts** record operational messaging lineage.
6. **Ops snapshots** aggregate cross-system visibility and expose safe controls.
7. **Rules** evaluate policy and plan ordered, non-destructive actions.
8. **Analytics snapshots** aggregate metrics/trends/comparisons for operational intelligence.

## Layer summaries

### Queue foundation (P41-01)

Deterministic job ledger, queue metadata, dependencies, attempts, artifacts, append-only job history. Jobs are created and listed; execution is delegated to workers.

### Worker runtime (P41-02)

Registration, heartbeats, leases, execution start/complete/fail, stale worker visibility, runtime issues and history.

### Workflow orchestration (P41-03)

Schedules, triggers, workflows, steps, executions, blocked/issue diagnostics, ops-driven schedule/trigger processing and workflow execution.

### Retry / recovery (P41-04)

Retry policies, recovery runs, failure events, dead-letter jobs, replay-recovery paths, critical failure ops views.

### Batch / maintenance (P41-05)

Batch runs, deterministic chunks, maintenance jobs/results, integrity audits, batch artifacts and history.

### Notifications / action center (P41-06)

Notification ledger, deliveries, templates, preferences, alerts, escalation, delivery-failure ops views.

### Ops dashboard (P41-07)

Snapshots, metrics, audits, safe controls, issues, manifests, system health. No destructive admin tooling.

### Rules engine (P41-08)

Immutable rule versions, restricted expression evaluation, ordered actions, evaluation artifacts, drift/issue diagnostics.

### Analytics (P41-09)

Immutable analytics snapshots, metrics, trends, comparisons, artifacts. No ML forecasting or streaming.

### Hardening / closeout (P41-10)

Documentation consolidation, operational playbooks, API/storage/determinism references, production readiness report, focused test verification. See [P41_HARDENING_REPORT.md](./P41_HARDENING_REPORT.md).

## Closeout documentation set

| Document | Purpose |
| --- | --- |
| [P41_DEPENDENCY_GRAPH.md](./P41_DEPENDENCY_GRAPH.md) | Dependencies, checksum chains, isolation, control boundaries |
| [P41_AUTOMATION_LIFECYCLE.md](./P41_AUTOMATION_LIFECYCLE.md) | End-to-end lifecycle and state transitions |
| [P41_OPERATIONS_GUIDE.md](./P41_OPERATIONS_GUIDE.md) | Runbooks and troubleshooting |
| [P41_API_REFERENCE.md](./P41_API_REFERENCE.md) | Owner vs ops routes, envelope and pagination |
| [P41_STORAGE_ARCHITECTURE.md](./P41_STORAGE_ARCHITECTURE.md) | Artifact paths and storage roots |
| [P41_DETERMINISM_GUARANTEES.md](./P41_DETERMINISM_GUARANTEES.md) | What is guaranteed vs deferred |
| [P41_PRODUCTION_READINESS_REPORT.md](./P41_PRODUCTION_READINESS_REPORT.md) | Readiness summary and P42 handoff |
| [P41_HARDENING_REPORT.md](./P41_HARDENING_REPORT.md) | Verification sweep notes |

## P42 handoff

P41 intentionally stops at single-tenant deterministic automation infrastructure. **P42 — Multi-User / Dealer Infrastructure** should build org/dealer boundaries, shared operational roles, and marketplace-adjacent workflows without redesigning P41 checksum or history models.
