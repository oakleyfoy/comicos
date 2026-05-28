from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models import (
    AutomationAlert,
    AutomationBatchIssue,
    AutomationBatchRun,
    AutomationDeadLetterJob,
    AutomationJob,
    AutomationNotification,
    AutomationNotificationDelivery,
    AutomationOpsArtifact,
    AutomationOpsAudit,
    AutomationOpsControl,
    AutomationOpsHistory,
    AutomationOpsIssue,
    AutomationOpsMetric,
    AutomationOpsSnapshot,
    AutomationQueue,
    AutomationWorkflow,
    AutomationWorker,
    ScanReplayIssue,
)
from app.schemas.automation_ops import (
    AutomationOpsAuditRead,
    AutomationOpsAuditRunCreate,
    AutomationOpsControlApplyCreate,
    AutomationOpsControlRead,
    AutomationOpsIssueRead,
    AutomationOpsListResponse,
    AutomationOpsMetricRead,
    AutomationOpsSnapshotCreate,
    AutomationOpsSnapshotRead,
    AutomationOpsSystemHealthRead,
)

ENGINE_VERSION = "P41-07-v1"
_SNAPSHOT_TYPES = {
    "SYSTEM_HEALTH",
    "WORKER_RUNTIME",
    "QUEUE_STATE",
    "RECOVERY_STATE",
    "BATCH_STATE",
    "NOTIFICATION_STATE",
    "REPLAY_STATE",
}
_AUDIT_TYPES = {
    "QUEUE_AUDIT",
    "WORKER_AUDIT",
    "REPLAY_AUDIT",
    "STORAGE_AUDIT",
    "CHECKSUM_AUDIT",
    "DEAD_LETTER_AUDIT",
    "NOTIFICATION_AUDIT",
}
_CONTROL_TYPES = {
    "PAUSE_QUEUE",
    "RESUME_QUEUE",
    "PAUSE_WORKFLOW",
    "RESUME_WORKFLOW",
    "ACKNOWLEDGE_ALERT",
    "ACKNOWLEDGE_FAILURE",
    "REPLAY_VERIFY",
    "MAINTENANCE_LOCK",
}
_FORBIDDEN_CONTROL_TYPES = {"DELETE_QUEUE", "PURGE_DEAD_LETTER", "FORCE_REPLAY_OVERWRITE"}


@dataclass(frozen=True)
class _HistoryDraft:
    event_type: str
    event_message: str
    metadata_json: dict[str, Any]
    snapshot_id: int | None = None
    audit_id: int | None = None
    control_id: int | None = None
    from_status: str | None = None
    to_status: str | None = None


@dataclass(frozen=True)
class _IssueDraft:
    issue_type: str
    severity: str
    issue_message: str
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _MetricDraft:
    metric_key: str
    metric_category: str
    metric_value: str
    metric_status: str
    metric_rank: int
    metadata_json: dict[str, Any]


def utc_now() -> datetime:
    from app.models.automation_ops import utc_now as _utc_now

    return _utc_now()


def clamp_automation_ops_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value).replace("\\", "/")
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, float):
        return round(value, 6)
    return value


def _hash_payload(payload: Any) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _serialize_json_artifact(payload: Any) -> bytes:
    return json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"), indent=2).encode("utf-8")


def _resolve_ops_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.automation_ops_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("automation ops storage path escapes configured root")
    return target


def _save_ops_artifact_bytes(settings: Settings, *, relative_path: str, body: bytes) -> None:
    target = _resolve_ops_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)


def _ops_artifact_path(*, snapshot_type: str, snapshot_id: int, artifact_type: str, ext: str) -> str:
    return f"automation-ops/{snapshot_type.lower()}/{snapshot_id}/{artifact_type.lower()}{ext}".replace("\\", "/")


def _record_ops_history(session: Session, *, draft: _HistoryDraft) -> None:
    payload = {
        "snapshot_id": draft.snapshot_id,
        "audit_id": draft.audit_id,
        "control_id": draft.control_id,
        "event_type": draft.event_type,
        "from_status": draft.from_status,
        "to_status": draft.to_status,
        "event_message": draft.event_message,
        "metadata_json": draft.metadata_json,
    }
    session.add(
        AutomationOpsHistory(
            snapshot_id=draft.snapshot_id,
            audit_id=draft.audit_id,
            control_id=draft.control_id,
            event_type=draft.event_type,
            from_status=draft.from_status,
            to_status=draft.to_status,
            event_message=draft.event_message,
            event_checksum=_hash_payload(payload),
            metadata_json=_json_safe(draft.metadata_json),
        )
    )


def _gather_visibility_counts(session: Session, *, owner_user_id: int | None) -> dict[str, int]:
    job_query = select(AutomationJob)
    if owner_user_id is not None:
        job_query = job_query.where(AutomationJob.owner_user_id == owner_user_id)
    jobs = list(session.exec(job_query).all())
    queue_depth = len([row for row in jobs if row.job_status in {"QUEUED", "RESERVED", "RUNNING"}])
    failed_jobs = len([row for row in jobs if row.job_status == "FAILED"])

    workers = list(session.exec(select(AutomationWorker)).all())
    active_workers = len([row for row in workers if row.worker_status == "ACTIVE"])
    stale_cutoff = utc_now() - timedelta(minutes=15)
    stale_workers = len(
        [
            row
            for row in workers
            if row.worker_status == "ACTIVE"
            and row.last_heartbeat_at is not None
            and row.last_heartbeat_at < stale_cutoff
        ]
    )

    workflows = list(session.exec(select(AutomationWorkflow)).all())
    active_workflows = len([row for row in workflows if row.workflow_status == "ACTIVE"])

    dead_letters = list(session.exec(select(AutomationDeadLetterJob)).all())
    if owner_user_id is not None:
        owner_job_ids = {row.id for row in jobs if row.id is not None}
        dead_letters = [row for row in dead_letters if row.original_job_id in owner_job_ids]
    dead_letter_count = len(dead_letters)

    replay_issues = list(session.exec(select(ScanReplayIssue)).all())
    replay_warning_count = len([row for row in replay_issues if row.severity in {"WARNING", "ERROR", "CRITICAL"}])

    batch_issues = list(session.exec(select(AutomationBatchIssue)).all())
    checksum_warning_count = len(
        [row for row in batch_issues if row.issue_type in {"CHECKSUM_MISMATCH", "LINEAGE_DRIFT", "ORPHAN_ARTIFACT_DETECTED"}]
    )

    notification_query = select(AutomationNotification)
    if owner_user_id is not None:
        notification_query = notification_query.where(AutomationNotification.owner_user_id == owner_user_id)
    notifications = list(session.exec(notification_query).all())
    notification_ids = [row.id for row in notifications if row.id is not None]
    deliveries = list(
        session.exec(
            select(AutomationNotificationDelivery).where(
                col(AutomationNotificationDelivery.notification_id).in_(notification_ids or [-1])
            )
        ).all()
    )
    notification_failures = len([row for row in deliveries if row.delivery_status == "FAILED"])

    batch_runs_query = select(AutomationBatchRun)
    if owner_user_id is not None:
        batch_runs_query = batch_runs_query.where(AutomationBatchRun.owner_user_id == owner_user_id)
    batch_runs = list(session.exec(batch_runs_query).all())
    batch_failures = len([row for row in batch_runs if row.batch_status in {"FAILED", "PARTIALLY_COMPLETED"}])

    return {
        "queue_depth": queue_depth,
        "active_workers": active_workers,
        "stale_workers": stale_workers,
        "active_workflows": active_workflows,
        "failed_jobs": failed_jobs,
        "dead_letter_count": dead_letter_count,
        "replay_warning_count": replay_warning_count,
        "checksum_warning_count": checksum_warning_count,
        "notification_failures": notification_failures,
        "batch_failures": batch_failures,
    }


def _derive_snapshot_status(counts: dict[str, int]) -> str:
    if counts["failed_jobs"] > 5 or counts["dead_letter_count"] > 10:
        return "CRITICAL"
    if counts["stale_workers"] > 0 or counts["batch_failures"] > 0 or counts["notification_failures"] > 0:
        return "DEGRADED"
    if counts["replay_warning_count"] > 0 or counts["checksum_warning_count"] > 0 or counts["queue_depth"] > 100:
        return "WARNING"
    return "HEALTHY"


def collect_ops_metrics(session: Session, *, counts: dict[str, int]) -> list[_MetricDraft]:
    drafts: list[_MetricDraft] = [
        _MetricDraft("queue_depth", "QUEUE", str(counts["queue_depth"]), "WARNING" if counts["queue_depth"] > 100 else "NORMAL", 10, {}),
        _MetricDraft("failed_jobs", "QUEUE", str(counts["failed_jobs"]), "CRITICAL" if counts["failed_jobs"] > 5 else "NORMAL", 20, {}),
        _MetricDraft("active_workers", "WORKER", str(counts["active_workers"]), "NORMAL", 10, {}),
        _MetricDraft("stale_workers", "WORKER", str(counts["stale_workers"]), "WARNING" if counts["stale_workers"] else "NORMAL", 20, {}),
        _MetricDraft("dead_letter_count", "RECOVERY", str(counts["dead_letter_count"]), "WARNING" if counts["dead_letter_count"] else "NORMAL", 10, {}),
        _MetricDraft("batch_failures", "BATCH", str(counts["batch_failures"]), "WARNING" if counts["batch_failures"] else "NORMAL", 10, {}),
        _MetricDraft("notification_failures", "NOTIFICATION", str(counts["notification_failures"]), "WARNING" if counts["notification_failures"] else "NORMAL", 10, {}),
        _MetricDraft("replay_warning_count", "REPLAY", str(counts["replay_warning_count"]), "WARNING" if counts["replay_warning_count"] else "NORMAL", 10, {}),
        _MetricDraft("checksum_warning_count", "REPLAY", str(counts["checksum_warning_count"]), "WARNING" if counts["checksum_warning_count"] else "NORMAL", 20, {}),
        _MetricDraft("active_workflows", "SYSTEM", str(counts["active_workflows"]), "NORMAL", 10, {}),
        _MetricDraft("engine_version", "SYSTEM", ENGINE_VERSION, "NORMAL", 99, {}),
    ]
    drafts.sort(key=lambda row: (row.metric_category, row.metric_rank, row.metric_key))
    return drafts


def _detect_ops_issues(*, counts: dict[str, int]) -> list[_IssueDraft]:
    issues: list[_IssueDraft] = []
    if counts["queue_depth"] > 100:
        issues.append(_IssueDraft("QUEUE_HEALTH_DEGRADED", "WARNING", "Queue depth exceeds warning threshold.", {"queue_depth": counts["queue_depth"]}))
    if counts["stale_workers"] > 0:
        issues.append(_IssueDraft("WORKER_RUNTIME_WARNING", "WARNING", "Stale worker heartbeats detected.", {"stale_workers": counts["stale_workers"]}))
    if counts["dead_letter_count"] > 0:
        issues.append(_IssueDraft("DEAD_LETTER_GROWTH", "ERROR", "Dead letter backlog present.", {"dead_letter_count": counts["dead_letter_count"]}))
    if counts["replay_warning_count"] > 0:
        issues.append(_IssueDraft("REPLAY_DRIFT_WARNING", "WARNING", "Replay drift warnings detected.", {"replay_warning_count": counts["replay_warning_count"]}))
    if counts["checksum_warning_count"] > 0:
        issues.append(_IssueDraft("CHECKSUM_WARNING", "WARNING", "Checksum or lineage warnings detected.", {"checksum_warning_count": counts["checksum_warning_count"]}))
    if counts["notification_failures"] > 0:
        issues.append(_IssueDraft("NOTIFICATION_FAILURE_WARNING", "WARNING", "Notification delivery failures detected.", {"notification_failures": counts["notification_failures"]}))
    issues.sort(key=lambda row: (row.severity, row.issue_type))
    return issues


def build_ops_manifest(
    *,
    snapshot: AutomationOpsSnapshot,
    metrics: list[AutomationOpsMetric],
    audits: list[AutomationOpsAudit],
    controls: list[AutomationOpsControl],
    issues: list[AutomationOpsIssue],
    artifacts: list[AutomationOpsArtifact],
) -> dict[str, Any]:
    return _json_safe(
        {
            "engine_version": ENGINE_VERSION,
            "snapshot": {
                "id": snapshot.id,
                "snapshot_key": snapshot.snapshot_key,
                "snapshot_type": snapshot.snapshot_type,
                "snapshot_status": snapshot.snapshot_status,
                "snapshot_checksum": snapshot.snapshot_checksum,
            },
            "metric_lineage": [
                {
                    "metric_key": row.metric_key,
                    "metric_category": row.metric_category,
                    "metric_rank": row.metric_rank,
                    "metric_checksum": row.metric_checksum,
                }
                for row in sorted(metrics, key=lambda item: (item.metric_category, item.metric_rank, item.metric_key))
            ],
            "audit_lineage": [
                {"audit_key": row.audit_key, "audit_type": row.audit_type, "audit_checksum": row.audit_checksum}
                for row in sorted(audits, key=lambda item: (item.audit_type, item.audit_key))
            ],
            "control_lineage": [
                {"control_key": row.control_key, "control_type": row.control_type, "control_checksum": row.control_checksum}
                for row in sorted(controls, key=lambda item: (item.control_type, item.control_key))
            ],
            "issues": [
                {"issue_type": row.issue_type, "severity": row.severity, "issue_checksum": row.issue_checksum}
                for row in sorted(issues, key=lambda item: (item.severity, item.issue_type))
            ],
            "artifacts": [
                {"artifact_type": row.artifact_type, "artifact_checksum": row.artifact_checksum, "storage_path": row.storage_path}
                for row in sorted(artifacts, key=lambda item: (item.artifact_type, item.storage_path))
            ],
        }
    )


def _persist_metrics(session: Session, *, snapshot_id: int, drafts: list[_MetricDraft]) -> list[AutomationOpsMetric]:
    rows: list[AutomationOpsMetric] = []
    for draft in drafts:
        payload = {
            "snapshot_id": snapshot_id,
            "metric_key": draft.metric_key,
            "metric_category": draft.metric_category,
            "metric_value": draft.metric_value,
            "metric_status": draft.metric_status,
            "metric_rank": draft.metric_rank,
            "metadata_json": draft.metadata_json,
        }
        row = AutomationOpsMetric(
            snapshot_id=snapshot_id,
            metric_key=draft.metric_key,
            metric_category=draft.metric_category,
            metric_value=draft.metric_value,
            metric_status=draft.metric_status,
            metric_rank=draft.metric_rank,
            metric_checksum=_hash_payload(payload),
            metadata_json=_json_safe(draft.metadata_json),
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return rows


def _persist_issues(session: Session, *, snapshot_id: int, drafts: list[_IssueDraft]) -> list[AutomationOpsIssue]:
    rows: list[AutomationOpsIssue] = []
    for draft in drafts:
        payload = {
            "snapshot_id": snapshot_id,
            "issue_type": draft.issue_type,
            "severity": draft.severity,
            "issue_message": draft.issue_message,
            "metadata_json": draft.metadata_json,
        }
        row = AutomationOpsIssue(
            snapshot_id=snapshot_id,
            issue_type=draft.issue_type,
            severity=draft.severity,
            issue_message=draft.issue_message,
            issue_checksum=_hash_payload(payload),
            metadata_json=_json_safe(draft.metadata_json),
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return rows


def _write_ops_artifacts(
    settings: Settings,
    session: Session,
    *,
    snapshot: AutomationOpsSnapshot,
    manifest: dict[str, Any],
) -> list[AutomationOpsArtifact]:
    assert snapshot.id is not None
    artifacts: list[AutomationOpsArtifact] = []
    specs = [
        ("OPS_REPORT", ".json", {"summary": manifest.get("snapshot"), "counts": snapshot.metadata_json}),
        ("OPS_MANIFEST", ".json", manifest),
        ("METRIC_EXPORT", ".json", {"metric_lineage": manifest.get("metric_lineage")}),
        ("OPS_DEBUG_PREVIEW", ".json", {"engine_version": ENGINE_VERSION, "snapshot_id": snapshot.id}),
    ]
    for artifact_type, ext, payload in specs:
        body = _serialize_json_artifact(payload)
        relative = _ops_artifact_path(snapshot_type=snapshot.snapshot_type, snapshot_id=snapshot.id, artifact_type=artifact_type, ext=ext)
        _save_ops_artifact_bytes(settings, relative_path=relative, body=body)
        checksum = _hash_payload({"path": relative, "body_sha256": hashlib.sha256(body).hexdigest()})
        row = AutomationOpsArtifact(
            snapshot_id=snapshot.id,
            artifact_type=artifact_type,
            storage_path=relative,
            artifact_checksum=checksum,
            metadata_json={"byte_length": len(body)},
        )
        session.add(row)
        artifacts.append(row)
    session.flush()
    return artifacts


def create_ops_snapshot(
    session: Session,
    settings: Settings,
    *,
    payload: AutomationOpsSnapshotCreate,
) -> tuple[AutomationOpsSnapshotRead, bool]:
    snapshot_type = str(payload.snapshot_type).upper()
    if snapshot_type not in _SNAPSHOT_TYPES:
        raise HTTPException(status_code=422, detail=f"Unsupported snapshot_type: {snapshot_type}")

    owner_user_id = payload.owner_user_id
    snapshot_key = f"{owner_user_id or 0}:{snapshot_type}:{payload.replay_key}"
    existing = session.exec(
        select(AutomationOpsSnapshot).where(
            AutomationOpsSnapshot.snapshot_key == snapshot_key,
            AutomationOpsSnapshot.owner_user_id == owner_user_id,
        )
    ).first()
    if existing is not None:
        return AutomationOpsSnapshotRead.model_validate(existing), False

    counts = _gather_visibility_counts(session, owner_user_id=owner_user_id)
    snapshot_status = _derive_snapshot_status(counts)
    metric_drafts = collect_ops_metrics(session, counts=counts)
    issue_drafts = _detect_ops_issues(counts=counts)

    pre_manifest_checksum = _hash_payload(
        {
            "snapshot_key": snapshot_key,
            "snapshot_type": snapshot_type,
            "counts": counts,
            "metrics": [draft.__dict__ for draft in metric_drafts],
            "issues": [draft.__dict__ for draft in issue_drafts],
            "metadata_json": payload.metadata_json,
        }
    )

    snapshot = AutomationOpsSnapshot(
        owner_user_id=owner_user_id,
        snapshot_key=snapshot_key,
        snapshot_type=snapshot_type,
        snapshot_status=snapshot_status,
        queue_depth=counts["queue_depth"],
        active_workers=counts["active_workers"],
        active_workflows=counts["active_workflows"],
        failed_jobs=counts["failed_jobs"],
        dead_letter_count=counts["dead_letter_count"],
        replay_warning_count=counts["replay_warning_count"],
        checksum_warning_count=counts["checksum_warning_count"],
        snapshot_checksum=pre_manifest_checksum,
        snapshot_manifest_json={},
        metadata_json=_json_safe(payload.metadata_json),
    )
    session.add(snapshot)
    session.flush()
    assert snapshot.id is not None

    metrics = _persist_metrics(session, snapshot_id=snapshot.id, drafts=metric_drafts)
    issues = _persist_issues(session, snapshot_id=snapshot.id, drafts=issue_drafts)

    manifest = build_ops_manifest(snapshot=snapshot, metrics=metrics, audits=[], controls=[], issues=issues, artifacts=[])
    manifest_checksum = _hash_payload(manifest)
    snapshot.snapshot_manifest_json = manifest
    snapshot.snapshot_checksum = _hash_payload({"manifest_checksum": manifest_checksum, "snapshot_key": snapshot_key})

    artifacts = _write_ops_artifacts(settings, session, snapshot=snapshot, manifest=manifest)
    manifest = build_ops_manifest(snapshot=snapshot, metrics=metrics, audits=[], controls=[], issues=issues, artifacts=artifacts)
    snapshot.snapshot_manifest_json = manifest
    snapshot.snapshot_checksum = _hash_payload({"manifest_checksum": _hash_payload(manifest), "snapshot_key": snapshot_key})

    _record_ops_history(
        session,
        draft=_HistoryDraft(
            event_type="OPS_SNAPSHOT_CREATED",
            event_message=f"Ops snapshot {snapshot_type} created.",
            metadata_json={"snapshot_key": snapshot_key, "engine_version": ENGINE_VERSION},
            snapshot_id=snapshot.id,
            to_status=snapshot_status,
        ),
    )
    session.commit()
    session.refresh(snapshot)
    return AutomationOpsSnapshotRead.model_validate(snapshot), True


def execute_ops_audit(
    session: Session,
    *,
    payload: AutomationOpsAuditRunCreate,
) -> AutomationOpsAuditRead:
    audit_type = str(payload.audit_type).upper()
    if audit_type not in _AUDIT_TYPES:
        raise HTTPException(status_code=422, detail=f"Unsupported audit_type: {audit_type}")

    audit_key = f"{payload.owner_user_id or 0}:{audit_type}:{payload.replay_key}"
    existing = session.exec(select(AutomationOpsAudit).where(AutomationOpsAudit.audit_key == audit_key)).first()
    if existing is not None:
        return AutomationOpsAuditRead.model_validate(existing)

    counts = _gather_visibility_counts(session, owner_user_id=payload.owner_user_id)
    findings: list[dict[str, Any]] = []
    audit_status = "PASS"

    if audit_type == "QUEUE_AUDIT":
        findings.append({"queue_depth": counts["queue_depth"], "failed_jobs": counts["failed_jobs"]})
        if counts["queue_depth"] > 100 or counts["failed_jobs"] > 0:
            audit_status = "WARNING"
    elif audit_type == "WORKER_AUDIT":
        findings.append({"active_workers": counts["active_workers"], "stale_workers": counts["stale_workers"]})
        if counts["stale_workers"] > 0:
            audit_status = "WARNING"
    elif audit_type == "REPLAY_AUDIT":
        findings.append({"replay_warning_count": counts["replay_warning_count"]})
        if counts["replay_warning_count"] > 0:
            audit_status = "WARNING"
    elif audit_type == "CHECKSUM_AUDIT":
        findings.append({"checksum_warning_count": counts["checksum_warning_count"]})
        if counts["checksum_warning_count"] > 0:
            audit_status = "WARNING"
    elif audit_type == "DEAD_LETTER_AUDIT":
        findings.append({"dead_letter_count": counts["dead_letter_count"]})
        if counts["dead_letter_count"] > 0:
            audit_status = "FAIL" if counts["dead_letter_count"] > 5 else "WARNING"
    elif audit_type == "NOTIFICATION_AUDIT":
        findings.append({"notification_failures": counts["notification_failures"]})
        if counts["notification_failures"] > 0:
            audit_status = "WARNING"
    elif audit_type == "STORAGE_AUDIT":
        findings.append({"batch_failures": counts["batch_failures"]})
        if counts["batch_failures"] > 0:
            audit_status = "WARNING"

    result_json = _json_safe({"audit_type": audit_type, "findings": findings, "engine_version": ENGINE_VERSION})
    audit = AutomationOpsAudit(
        owner_user_id=payload.owner_user_id,
        snapshot_id=payload.snapshot_id,
        audit_key=audit_key,
        audit_type=audit_type,
        audit_status=audit_status,
        audit_scope=payload.audit_scope,
        audit_checksum=_hash_payload(result_json),
        audit_result_json=result_json,
        metadata_json=_json_safe(payload.metadata_json),
    )
    session.add(audit)
    session.flush()
    assert audit.id is not None

    if audit_status == "FAIL":
        snapshot_id = payload.snapshot_id
        if snapshot_id is not None:
            session.add(
                AutomationOpsIssue(
                    snapshot_id=snapshot_id,
                    issue_type="OPS_AUDIT_FAILURE",
                    severity="ERROR",
                    issue_message=f"Audit {audit_type} failed.",
                    issue_checksum=_hash_payload({"audit_id": audit.id, "audit_type": audit_type}),
                    metadata_json={"audit_key": audit_key},
                )
            )

    _record_ops_history(
        session,
        draft=_HistoryDraft(
            event_type="OPS_AUDIT_EXECUTED",
            event_message=f"Ops audit {audit_type} completed with status {audit_status}.",
            metadata_json={"audit_key": audit_key},
            snapshot_id=payload.snapshot_id,
            audit_id=audit.id,
            to_status=audit_status,
        ),
    )
    session.commit()
    session.refresh(audit)
    return AutomationOpsAuditRead.model_validate(audit)


def apply_ops_control(
    session: Session,
    *,
    payload: AutomationOpsControlApplyCreate,
) -> AutomationOpsControlRead:
    control_type = str(payload.control_type).upper()
    if control_type in _FORBIDDEN_CONTROL_TYPES:
        raise HTTPException(status_code=403, detail="Destructive control type is forbidden.")
    if control_type not in _CONTROL_TYPES:
        raise HTTPException(status_code=422, detail=f"Unsupported control_type: {control_type}")

    control_key = f"{payload.owner_user_id or 0}:{control_type}:{payload.replay_key}"
    existing = session.exec(select(AutomationOpsControl).where(AutomationOpsControl.control_key == control_key)).first()
    if existing is not None:
        return AutomationOpsControlRead.model_validate(existing)

    control_status = "APPLIED"
    control_snapshot: dict[str, Any] = {"control_type": control_type, "target_scope": payload.target_scope}

    if control_type in {"PAUSE_QUEUE", "RESUME_QUEUE"}:
        queue = session.exec(select(AutomationQueue).where(AutomationQueue.queue_key == payload.target_scope)).first()
        if queue is None:
            control_status = "REJECTED"
            control_snapshot["reason"] = "queue_not_found"
        else:
            previous = queue.queue_status
            queue.queue_status = "PAUSED" if control_type == "PAUSE_QUEUE" else "ACTIVE"
            session.add(queue)
            control_snapshot["previous_queue_status"] = previous
            control_snapshot["queue_status"] = queue.queue_status
    elif control_type in {"PAUSE_WORKFLOW", "RESUME_WORKFLOW"}:
        workflow = session.exec(select(AutomationWorkflow).where(AutomationWorkflow.workflow_key == payload.target_scope)).first()
        if workflow is None:
            control_status = "REJECTED"
            control_snapshot["reason"] = "workflow_not_found"
        else:
            previous = workflow.workflow_status
            workflow.workflow_status = "PAUSED" if control_type == "PAUSE_WORKFLOW" else "ACTIVE"
            session.add(workflow)
            control_snapshot["previous_workflow_status"] = previous
            control_snapshot["workflow_status"] = workflow.workflow_status
    elif control_type == "ACKNOWLEDGE_ALERT":
        alert = session.exec(select(AutomationAlert).where(AutomationAlert.alert_key == payload.target_scope)).first()
        if alert is None:
            control_status = "REJECTED"
            control_snapshot["reason"] = "alert_not_found"
        else:
            alert.alert_status = "ACKNOWLEDGED"
            alert.acknowledged_at = utc_now()
            session.add(alert)
            control_snapshot["alert_key"] = alert.alert_key
    elif control_type == "ACKNOWLEDGE_FAILURE":
        control_snapshot["acknowledged_scope"] = payload.target_scope
    elif control_type == "REPLAY_VERIFY":
        control_snapshot["replay_verify_scope"] = payload.target_scope
        control_snapshot["verified"] = True
    elif control_type == "MAINTENANCE_LOCK":
        control_snapshot["maintenance_lock"] = True
        control_snapshot["lock_scope"] = payload.target_scope

    conflict = session.exec(
        select(AutomationOpsControl)
        .where(
            AutomationOpsControl.control_type == control_type,
            AutomationOpsControl.target_scope == payload.target_scope,
            AutomationOpsControl.control_status == "APPLIED",
        )
        .order_by(col(AutomationOpsControl.created_at).desc(), col(AutomationOpsControl.id).desc())
    ).first()
    if conflict is not None and control_status == "APPLIED" and conflict.control_key != control_key:
        if payload.snapshot_id is not None:
            session.add(
                AutomationOpsIssue(
                    snapshot_id=payload.snapshot_id,
                    issue_type="OPS_CONTROL_CONFLICT",
                    severity="WARNING",
                    issue_message=f"Control {control_type} may conflict with prior application.",
                    issue_checksum=_hash_payload({"control_key": control_key, "conflict_key": conflict.control_key}),
                    metadata_json={"target_scope": payload.target_scope},
                )
            )

    control = AutomationOpsControl(
        owner_user_id=payload.owner_user_id,
        snapshot_id=payload.snapshot_id,
        control_key=control_key,
        control_type=control_type,
        control_status=control_status,
        target_scope=payload.target_scope,
        control_checksum=_hash_payload(control_snapshot),
        control_snapshot_json=_json_safe(control_snapshot),
        metadata_json=_json_safe(payload.metadata_json),
    )
    session.add(control)
    session.flush()
    assert control.id is not None

    _record_ops_history(
        session,
        draft=_HistoryDraft(
            event_type="OPS_CONTROL_APPLIED",
            event_message=f"Ops control {control_type} recorded as {control_status}.",
            metadata_json={"control_key": control_key},
            snapshot_id=payload.snapshot_id,
            control_id=control.id,
            to_status=control_status,
        ),
    )
    session.commit()
    session.refresh(control)
    return AutomationOpsControlRead.model_validate(control)


def get_automation_ops_snapshot_owner(session: Session, *, owner_user_id: int, snapshot_id: int) -> AutomationOpsSnapshotRead:
    row = session.get(AutomationOpsSnapshot, snapshot_id)
    if row is None or int(row.owner_user_id or 0) != owner_user_id:
        raise HTTPException(status_code=404, detail="Automation ops snapshot not found.")
    return AutomationOpsSnapshotRead.model_validate(row)


def _list_snapshots(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> AutomationOpsListResponse:
    limit, offset = clamp_automation_ops_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationOpsSnapshot).order_by(col(AutomationOpsSnapshot.created_at).desc(), col(AutomationOpsSnapshot.id).desc())).all())
    if owner_user_id is not None:
        rows = [row for row in rows if int(row.owner_user_id or 0) == owner_user_id]
    items = [AutomationOpsSnapshotRead.model_validate(row) for row in rows[offset : offset + limit]]
    replay_warnings = sum(row.replay_warning_count for row in rows)
    issues = list(session.exec(select(AutomationOpsIssue)).all())
    critical = len([row for row in issues if row.severity == "CRITICAL"])
    failed_audits = len(session.exec(select(AutomationOpsAudit).where(AutomationOpsAudit.audit_status == "FAIL")).all())
    return AutomationOpsListResponse(
        items=items,
        total_items=len(rows),
        limit=limit,
        offset=offset,
        replay_warning_count=replay_warnings,
        critical_issue_count=critical,
        failed_audit_count=failed_audits,
    )


def list_automation_ops_snapshots_owner(session: Session, *, owner_user_id: int, limit: int, offset: int) -> AutomationOpsListResponse:
    return _list_snapshots(session, owner_user_id=owner_user_id, limit=limit, offset=offset)


def list_automation_ops_snapshots_ops(session: Session, *, limit: int, offset: int) -> AutomationOpsListResponse:
    return _list_snapshots(session, owner_user_id=None, limit=limit, offset=offset)


def list_automation_ops_metrics(
    session: Session,
    *,
    owner_user_id: int | None,
    snapshot_id: int | None,
    limit: int,
    offset: int,
) -> AutomationOpsListResponse:
    limit, offset = clamp_automation_ops_pagination(limit=limit, offset=offset)
    query = select(AutomationOpsMetric)
    if snapshot_id is not None:
        query = query.where(AutomationOpsMetric.snapshot_id == snapshot_id)
    rows = list(
        session.exec(query.order_by(col(AutomationOpsMetric.metric_category), col(AutomationOpsMetric.metric_rank), col(AutomationOpsMetric.metric_key))).all()
    )
    if owner_user_id is not None:
        snapshot_ids = {
            row.id
            for row in session.exec(select(AutomationOpsSnapshot).where(AutomationOpsSnapshot.owner_user_id == owner_user_id)).all()
            if row.id is not None
        }
        rows = [row for row in rows if row.snapshot_id in snapshot_ids]
    items = [AutomationOpsMetricRead.model_validate(row) for row in rows[offset : offset + limit]]
    return AutomationOpsListResponse(items=items, total_items=len(rows), limit=limit, offset=offset)


def list_automation_ops_audits(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> AutomationOpsListResponse:
    limit, offset = clamp_automation_ops_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationOpsAudit).order_by(col(AutomationOpsAudit.created_at).desc(), col(AutomationOpsAudit.id).desc())).all())
    if owner_user_id is not None:
        rows = [row for row in rows if int(row.owner_user_id or 0) == owner_user_id]
    items = [AutomationOpsAuditRead.model_validate(row) for row in rows[offset : offset + limit]]
    failed = len([row for row in rows if row.audit_status == "FAIL"])
    return AutomationOpsListResponse(items=items, total_items=len(rows), limit=limit, offset=offset, failed_audit_count=failed)


def list_automation_ops_issues(
    session: Session,
    *,
    owner_user_id: int | None,
    snapshot_id: int | None,
    limit: int,
    offset: int,
) -> AutomationOpsListResponse:
    limit, offset = clamp_automation_ops_pagination(limit=limit, offset=offset)
    query = select(AutomationOpsIssue)
    if snapshot_id is not None:
        query = query.where(AutomationOpsIssue.snapshot_id == snapshot_id)
    rows = list(session.exec(query.order_by(col(AutomationOpsIssue.severity), col(AutomationOpsIssue.issue_type), col(AutomationOpsIssue.id))).all())
    if owner_user_id is not None:
        snapshot_ids = {
            row.id
            for row in session.exec(select(AutomationOpsSnapshot).where(AutomationOpsSnapshot.owner_user_id == owner_user_id)).all()
            if row.id is not None
        }
        rows = [row for row in rows if row.snapshot_id in snapshot_ids]
    items = [AutomationOpsIssueRead.model_validate(row) for row in rows[offset : offset + limit]]
    critical = len([row for row in rows if row.severity == "CRITICAL"])
    return AutomationOpsListResponse(items=items, total_items=len(rows), limit=limit, offset=offset, critical_issue_count=critical)


def get_ops_system_health(session: Session, *, owner_user_id: int | None) -> AutomationOpsSystemHealthRead:
    snapshots = _list_snapshots(session, owner_user_id=owner_user_id, limit=1, offset=0)
    latest = snapshots.items[0] if snapshots.items else None
    counts = _gather_visibility_counts(session, owner_user_id=owner_user_id)
    status = _derive_snapshot_status(counts)
    issues = list_automation_ops_issues(session, owner_user_id=owner_user_id, snapshot_id=None, limit=500, offset=0)
    audits = list_automation_ops_audits(session, owner_user_id=owner_user_id, limit=500, offset=0)
    return AutomationOpsSystemHealthRead(
        snapshot_status=status,
        queue_depth=counts["queue_depth"],
        active_workers=counts["active_workers"],
        failed_jobs=counts["failed_jobs"],
        dead_letter_count=counts["dead_letter_count"],
        replay_warning_count=counts["replay_warning_count"],
        checksum_warning_count=counts["checksum_warning_count"],
        critical_issue_count=issues.critical_issue_count,
        failed_audit_count=audits.failed_audit_count,
        latest_snapshot_id=latest.id if latest else None,
        latest_snapshot_checksum=latest.snapshot_checksum if latest else None,
    )
