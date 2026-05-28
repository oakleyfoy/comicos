# P41 Workflow Scheduling Architecture

## Purpose

P41-03 adds the deterministic scheduling and trigger orchestration layer that converts owner-created schedules and triggers into replay-safe workflow executions and downstream automation jobs. This layer sequences work on top of the P41-01 queue ledger and P41-02 worker runtime without introducing distributed orchestration, realtime sockets, or external event buses.

## Core model

- `AutomationSchedule` stores immutable schedule snapshots, deterministic schedule checksums, next-run state, and owner-scoped orchestration metadata.
- `AutomationTrigger` stores immutable trigger payloads, deterministic trigger checksums, source lineage, and replay-safe processing state.
- `AutomationWorkflow` defines the orchestration template for a given owner and workflow key.
- `AutomationWorkflowStep` defines deterministic step order, job types, dependency modes, delays, and step-local metadata.
- `AutomationWorkflowExecution` stores the append-only execution manifest, generated job lineage, and execution checksum.
- `AutomationWorkflowIssue` preserves orchestration failures, blocked steps, dependency problems, and trigger processing faults.
- `AutomationWorkflowHistory` records append-only workflow lifecycle events.

## Scheduling model

- Schedules are deterministic snapshots keyed by a checksum derived from owner context, schedule attributes, workflow selection, and metadata.
- Due schedules are processed in stable order: `next_run_at`, `created_at`, then `id`.
- One-time schedules are completed after materialization.
- Interval and recurring schedules deterministically advance `next_run_at` from the stored value rather than from variable wall-clock drift.
- Event-driven schedules remain inert until another subsystem decides to use them; this phase does not add background watchers.

## Trigger model

- Triggers are immutable payload snapshots with deterministic `trigger_checksum` values.
- Duplicate trigger submissions return the existing trigger rather than enqueueing hidden duplicate activations.
- Pending triggers are processed in stable order by `triggered_at`, `created_at`, then `id`.
- Trigger routing is explicit through workflow keys or the built-in deterministic trigger-to-workflow map.

## Dependency orchestration model

- Workflow steps are ordered by `step_rank` and `id`.
- `STRICT_SEQUENCE` steps depend on the immediately prior step.
- Explicit step references can be declared through `metadata_json.depends_on_step_key`.
- Cycles are rejected deterministically during dependency resolution.
- Conditional steps preserve blocked state instead of silently skipping or repairing orchestration.
- Optional steps can remain independent while still contributing deterministic metadata to the execution manifest.

## Deterministic sequencing model

- Execution activation keys derive from workflow key plus schedule/trigger lineage so repeated identical inputs resolve to the same execution record.
- Workflow manifests use stable JSON serialization and deterministic ordering for steps, generated jobs, issues, and artifact references.
- Generated job payloads carry workflow execution lineage, trigger or schedule checksums, and deterministic idempotency keys.
- Execution artifacts are append-only and stored at deterministic paths under `automation-workflows/{workflow_key}/{execution_id}/...`.

## Replay-safe orchestration guarantees

- No hidden retries are introduced by the orchestration layer.
- Upstream schedule and trigger snapshots remain immutable.
- Workflow history and issues are append-only.
- Identical activation input yields a stable execution checksum and stable generated job lineage.
- Blocked and failed orchestration states are surfaced explicitly rather than repaired in place.

## Non-goals

- Distributed orchestration clusters
- Realtime websocket orchestration
- External event buses
- Dynamic workflow editing
- Visual workflow editors
- External cron providers
- Autoscaling or distributed dependency locks
