# P41 Storage Architecture

## Principles

- Artifacts are **append-only** at the application layer: new runs write new paths or skip write if an identical checksum path already exists (phase-specific services).
- Immutable snapshots (ops, analytics, rule evaluations, batch manifests) are never rewritten in place.
- Paths use forward slashes in stored `storage_path` values.
- Each artifact row stores `artifact_checksum` over canonical payload or file hash metadata.

## Storage root configuration

Environment variables (optional; default under repo `data/`):

| Env variable | Default directory |
| --- | --- |
| `AUTOMATION_JOBS_STORAGE_ROOT` | `data/automation_jobs` |
| `AUTOMATION_WORKERS_STORAGE_ROOT` | `data/automation_workers` |
| `AUTOMATION_WORKFLOWS_STORAGE_ROOT` | `data/automation_workflows` |
| `AUTOMATION_RECOVERY_STORAGE_ROOT` | `data/automation_recovery` |
| `AUTOMATION_BATCH_STORAGE_ROOT` | `data/automation_batch` |
| `AUTOMATION_NOTIFICATIONS_STORAGE_ROOT` | `data/automation_notifications` |
| `AUTOMATION_OPS_STORAGE_ROOT` | `data/automation_ops` |
| `AUTOMATION_RULES_STORAGE_ROOT` | `data/automation_rules` |
| `AUTOMATION_ANALYTICS_STORAGE_ROOT` | `data/automation_analytics` |

Properties are exposed on `Settings` in `apps/api/app/core/config.py`. Services resolve paths with root containment checks to prevent directory escape.

## Path conventions

| Layer | Pattern (representative) |
| --- | --- |
| Jobs | Under jobs root: job-scoped artifact types keyed by job id / checksum (see `automation_jobs` service). |
| Workers | Worker execution / runtime artifacts under workers root. |
| Workflows | Workflow execution manifests under workflows root. |
| Recovery | Recovery run manifests and replay artifacts under recovery root. |
| Batch | `automation-batch/{batch_type}/{batch_run_id}/{artifact_type}.{ext}` |
| Notifications | Notification and delivery export artifacts under notifications root. |
| Ops | `automation-ops/{snapshot_type}/{snapshot_id}/{artifact_type}.{ext}` |
| Rules | `automation-rules/{rule_key}/{evaluation_id}/{artifact_type}.json` |
| Analytics | `automation-analytics/{analytics_type}/{snapshot_id}/{artifact_type}.json` |

Exact filenames are deterministic functions of entity ids, types, and checksums defined in each service’s `_write_*_artifacts` helper.

## Artifact checksum rules

1. Serialize JSON with sorted keys and stable separators where applicable.
2. Hash canonical payload → row `artifact_checksum`.
3. Optionally hash file bytes (`body_sha256`) in metadata for filesystem artifacts.
4. Manifest checksums aggregate ordered child lineage (metrics, actions, chunks, etc.).

## Database vs filesystem

- Authoritative state lives in SQLModel tables.
- Filesystem stores human-readable exports (manifests, debug previews, reports).
- Missing files on disk should surface as ops/batch integrity issues, not silent repair.

## Replay-safe path conventions

- Paths include stable ids (snapshot_id, evaluation_id, batch_run_id) so replay re-runs target the same relative path.
- Re-post with same idempotency key returns existing DB row; artifact write helpers skip overwrite when file already present.

## Future cloud-storage readiness

- `storage_backend` column defaults to `filesystem`; future phases may add object-store backends without changing checksum rules.
- Cloud migration should copy bytes preserving relative path keys and re-verify artifact checksums against manifests.

## Operational notes

- Ensure `data/` (or configured roots) are on durable disk with backups aligned to DB backup policy.
- Batch ops routes expose storage/integrity audit read models for drift detection.
- Do not manually delete artifact files unless following a future approved retention policy (deferred; see TECH_DEBT).
