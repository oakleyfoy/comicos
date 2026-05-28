from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models import (
    AutomationJob,
    AutomationJobArtifact,
    AutomationJobAttempt,
    AutomationJobDependency,
    AutomationJobHistory,
    AutomationJobIssue,
    AutomationQueue,
)
from app.schemas.automation_jobs import (
    AutomationJobArtifactRead,
    AutomationJobAttemptRead,
    AutomationJobCreate,
    AutomationJobDependencyRead,
    AutomationJobDetail,
    AutomationJobHistoryRead,
    AutomationJobIssueRead,
    AutomationJobListResponse,
    AutomationJobRead,
    AutomationQueueListResponse,
    AutomationQueueRead,
)
from app.services.automation_queue_state import build_transition_metadata, validate_job_transition

ENGINE_VERSION = "P41-01-v1"
_QUEUE_PRIORITY_RANK = {"LOW": 1, "NORMAL": 2, "HIGH": 3, "CRITICAL": 4}
_QUEUE_CATEGORY_DEFAULT_NAME = {
    "SCAN_PIPELINE": "Scan Pipeline Queue",
    "REPLAY": "Replay Queue",
    "NOTIFICATION": "Notification Queue",
    "MAINTENANCE": "Maintenance Queue",
    "BATCH": "Batch Queue",
    "REVIEW": "Review Queue",
    "SYSTEM": "System Queue",
}
_ARTIFACT_MEDIA_TYPES = {".json": "application/json", ".txt": "text/plain; charset=utf-8"}


@dataclass(frozen=True)
class _ArtifactDraft:
    artifact_type: str
    body: bytes
    metadata_json: dict[str, Any]
    ext: str


@dataclass(frozen=True)
class _HistoryDraft:
    event_type: str
    from_status: str | None
    to_status: str | None
    event_message: str
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _IssueDraft:
    issue_type: str
    severity: str
    issue_message: str
    metadata_json: dict[str, Any]


def utc_now() -> datetime:
    from app.models.automation_jobs import utc_now as _utc_now

    return _utc_now()


def clamp_automation_jobs_pagination(*, limit: int, offset: int) -> tuple[int, int]:
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


def _sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _serialize_json_artifact(payload: Any) -> bytes:
    return json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"), indent=2).encode("utf-8")


def _queue_storage_path(*, queue_key: str, job_id: int, artifact_type: str, ext: str) -> str:
    return f"automation-jobs/{queue_key}/{job_id}/{artifact_type.lower()}{ext}".replace("\\", "/")


def _resolve_automation_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.automation_jobs_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("automation jobs storage path escapes configured root")
    return target


def _save_artifact_bytes(settings: Settings, *, relative_path: str, body: bytes) -> None:
    target = _resolve_automation_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)


def _load_artifact_payload(settings: Settings, row: AutomationJobArtifact) -> tuple[str | None, str | None, str | None]:
    try:
        body = _resolve_automation_storage_path(settings, row.storage_path).read_bytes()
    except OSError:
        return None, None, None
    media_type = _ARTIFACT_MEDIA_TYPES.get(Path(row.storage_path).suffix.lower(), "application/octet-stream")
    try:
        text_preview = body.decode("utf-8")
    except UnicodeDecodeError:
        return media_type, None, base64.b64encode(body).decode("ascii")
    return media_type, text_preview[:20000], None


def _priority_weight(priority: str) -> int:
    return _QUEUE_PRIORITY_RANK.get(priority, 0)


def _normalize_available_at(value: datetime | None) -> datetime:
    if value is None:
        return utc_now()
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _require_queue_status(queue: AutomationQueue) -> None:
    if queue.queue_status not in {"ACTIVE", "DRAINING"}:
        raise HTTPException(status_code=409, detail=f"Queue {queue.queue_key} is not accepting jobs.")


def _nullable_int_match(value: int | None, expected: int | None) -> bool:
    return value == expected


def _record_history(session: Session, *, job_id: int, draft: _HistoryDraft) -> None:
    payload = {
        "job_id": job_id,
        "event_type": draft.event_type,
        "from_status": draft.from_status,
        "to_status": draft.to_status,
        "event_message": draft.event_message,
        "metadata_json": draft.metadata_json,
    }
    session.add(
        AutomationJobHistory(
            job_id=job_id,
            event_type=draft.event_type,
            from_status=draft.from_status,
            to_status=draft.to_status,
            event_message=draft.event_message,
            event_checksum=_hash_payload(payload),
            metadata_json=_json_safe(draft.metadata_json),
        )
    )


def _record_issue(session: Session, *, job_id: int, draft: _IssueDraft) -> None:
    payload = {
        "job_id": job_id,
        "issue_type": draft.issue_type,
        "severity": draft.severity,
        "issue_message": draft.issue_message,
        "metadata_json": draft.metadata_json,
    }
    session.add(
        AutomationJobIssue(
            job_id=job_id,
            issue_type=draft.issue_type,
            severity=draft.severity,
            issue_message=draft.issue_message,
            issue_checksum=_hash_payload(payload),
            metadata_json=_json_safe(draft.metadata_json),
        )
    )


def _build_job_manifest(
    *,
    queue: AutomationQueue,
    payload_snapshot_json: dict[str, Any],
    payload_checksum: str,
    source_record_type: str | None,
    source_record_id: int | None,
    source_checksum: str | None,
    replay_safe: bool,
    dependencies: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    lineage: dict[str, Any],
) -> dict[str, Any]:
    return {
        "engine_version": ENGINE_VERSION,
        "queue": {
            "queue_key": queue.queue_key,
            "queue_name": queue.queue_name,
            "queue_category": queue.queue_category,
            "queue_status": queue.queue_status,
            "deterministic_ordering_enabled": queue.deterministic_ordering_enabled,
            "max_concurrency": queue.max_concurrency,
            "metadata_json": _json_safe(queue.metadata_json),
        },
        "payload_snapshot_json": _json_safe(payload_snapshot_json),
        "payload_checksum": payload_checksum,
        "source_record_type": source_record_type,
        "source_record_id": source_record_id,
        "source_checksum": source_checksum,
        "replay_safe": replay_safe,
        "dependencies": _json_safe(sorted(dependencies, key=lambda row: (row.get("depends_on_job_id") or 0, row.get("dependency_status") or ""))),
        "attempts": _json_safe(sorted(attempts, key=lambda row: (row.get("attempt_number") or 0, row.get("created_at") or ""))),
        "issues": _json_safe(sorted(issues, key=lambda row: (row.get("severity") or "", row.get("issue_type") or ""))),
        "artifacts": _json_safe(sorted(artifacts, key=lambda row: (row.get("artifact_type") or "", row.get("artifact_checksum") or ""))),
        "lineage": _json_safe(lineage),
    }


def build_job_manifest(
    session: Session,
    *,
    queue: AutomationQueue,
    payload_snapshot_json: dict[str, Any],
    payload_checksum: str,
    source_record_type: str | None,
    source_record_id: int | None,
    source_checksum: str | None,
    replay_safe: bool,
    dependencies: list[AutomationJobDependency] | None = None,
    attempts: list[AutomationJobAttempt] | None = None,
    issues: list[AutomationJobIssue] | None = None,
    artifacts: list[AutomationJobArtifact] | None = None,
) -> tuple[dict[str, Any], str]:
    del session
    dependency_rows = [
        {
            "id": row.id,
            "job_id": row.job_id,
            "depends_on_job_id": row.depends_on_job_id,
            "dependency_status": row.dependency_status,
            "created_at": row.created_at,
        }
        for row in (dependencies or [])
    ]
    attempt_rows = [
        {
            "id": row.id,
            "attempt_number": row.attempt_number,
            "attempt_status": row.attempt_status,
            "worker_identifier": row.worker_identifier,
            "created_at": row.created_at,
        }
        for row in (attempts or [])
    ]
    issue_rows = [
        {
            "id": row.id,
            "issue_type": row.issue_type,
            "severity": row.severity,
            "issue_checksum": row.issue_checksum,
        }
        for row in (issues or [])
    ]
    artifact_rows = [
        {
            "id": row.id,
            "artifact_type": row.artifact_type,
            "artifact_checksum": row.artifact_checksum,
            "storage_path": row.storage_path,
        }
        for row in (artifacts or [])
    ]
    lineage = {
        "source_checksum": source_checksum,
        "payload_checksum": payload_checksum,
        "source_record_type": source_record_type,
        "source_record_id": source_record_id,
    }
    manifest = _build_job_manifest(
        queue=queue,
        payload_snapshot_json=payload_snapshot_json,
        payload_checksum=payload_checksum,
        source_record_type=source_record_type,
        source_record_id=source_record_id,
        source_checksum=source_checksum,
        replay_safe=replay_safe,
        dependencies=dependency_rows,
        attempts=attempt_rows,
        issues=issue_rows,
        artifacts=artifact_rows,
        lineage=lineage,
    )
    return manifest, _hash_payload(manifest)


def _get_or_create_queue(
    session: Session,
    *,
    queue_key: str,
    queue_name: str | None,
    queue_category: str,
) -> AutomationQueue:
    row = session.exec(select(AutomationQueue).where(AutomationQueue.queue_key == queue_key)).first()
    if row is not None:
        return row
    row = AutomationQueue(
        queue_key=queue_key,
        queue_name=queue_name or _QUEUE_CATEGORY_DEFAULT_NAME.get(queue_category, queue_key.replace("_", " ").title()),
        queue_category=queue_category,
        queue_status="ACTIVE",
        deterministic_ordering_enabled=True,
        max_concurrency=1,
        metadata_json={},
    )
    session.add(row)
    session.flush()
    return row


def _job_to_read(job: AutomationJob, queue: AutomationQueue | None) -> AutomationJobRead:
    return AutomationJobRead.model_validate(
        {
            **job.model_dump(),
            "queue_key": queue.queue_key if queue else None,
            "queue_name": queue.queue_name if queue else None,
            "queue_status": queue.queue_status if queue else None,
        }
    )


def _build_job_artifacts(payload_snapshot_json: dict[str, Any], manifest: dict[str, Any]) -> list[_ArtifactDraft]:
    return [
        _ArtifactDraft("JOB_PAYLOAD_SNAPSHOT", _serialize_json_artifact(payload_snapshot_json), {"kind": "payload"}, ".json"),
        _ArtifactDraft("JOB_MANIFEST", _serialize_json_artifact(manifest), {"kind": "manifest"}, ".json"),
        _ArtifactDraft("JOB_DEBUG_PREVIEW", _serialize_json_artifact({"payload": payload_snapshot_json, "manifest": manifest}), {"kind": "preview"}, ".json"),
    ]


def create_automation_job(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: AutomationJobCreate,
) -> tuple[AutomationJobDetail, bool]:
    queue = _get_or_create_queue(
        session,
        queue_key=payload.queue_key,
        queue_name=payload.queue_name,
        queue_category=str(payload.queue_category),
    )
    _require_queue_status(queue)
    if str(payload.priority) not in _QUEUE_PRIORITY_RANK:
        raise HTTPException(status_code=422, detail="Invalid automation job priority.")

    payload_snapshot_json = _json_safe(payload.payload_snapshot_json)
    payload_checksum = _hash_payload(payload_snapshot_json)
    available_at = _normalize_available_at(payload.available_at)
    deterministic_rank = int(
        session.exec(
            select(func.count()).select_from(AutomationJob).where(AutomationJob.queue_id == queue.id)
        ).one()
    ) + 1

    manifest, manifest_checksum = build_job_manifest(
        session,
        queue=queue,
        payload_snapshot_json=payload_snapshot_json,
        payload_checksum=payload_checksum,
        source_record_type=payload.source_record_type,
        source_record_id=payload.source_record_id,
        source_checksum=payload.source_checksum,
        replay_safe=payload.replay_safe,
    )
    job_checksum = _hash_payload(
        {
            "queue_key": queue.queue_key,
            "owner_user_id": owner_user_id,
            "organization_id": payload.organization_id,
            "job_key": payload.job_key,
            "job_type": payload.job_type,
            "payload_checksum": payload_checksum,
            "job_manifest_checksum": manifest_checksum,
            "source_checksum": payload.source_checksum,
            "idempotency_key": payload.idempotency_key,
        }
    )
    existing_stmt = select(AutomationJob).where(
        AutomationJob.queue_id == queue.id,
        AutomationJob.owner_user_id == owner_user_id,
        AutomationJob.job_checksum == job_checksum,
    )
    if payload.organization_id is None:
        existing_stmt = existing_stmt.where(AutomationJob.organization_id.is_(None))
    else:
        existing_stmt = existing_stmt.where(AutomationJob.organization_id == payload.organization_id)
    existing = session.exec(existing_stmt).first()
    if existing is not None:
        return get_automation_job_owner(session, settings, owner_user_id=owner_user_id, job_id=int(existing.id)), False

    job = AutomationJob(
        owner_user_id=owner_user_id,
        organization_id=payload.organization_id,
        queue_id=int(queue.id),
        parent_job_id=payload.parent_job_id,
        job_key=payload.job_key,
        job_type=payload.job_type,
        job_status="PENDING",
        priority=str(payload.priority),
        deterministic_rank=deterministic_rank,
        payload_snapshot_json=payload_snapshot_json,
        payload_checksum=payload_checksum,
        source_record_type=payload.source_record_type,
        source_record_id=payload.source_record_id,
        source_checksum=payload.source_checksum,
        reservation_token=None,
        reserved_until=None,
        available_at=available_at,
        max_attempts=payload.max_attempts,
        current_attempt_count=0,
        replay_safe=payload.replay_safe,
        idempotency_key=payload.idempotency_key,
        job_checksum=job_checksum,
        metadata_json=_json_safe(payload.metadata_json),
    )
    session.add(job)
    session.flush()

    _record_history(
        session,
        job_id=int(job.id),
        draft=_HistoryDraft(
            event_type="JOB_CREATED",
            from_status=None,
            to_status="PENDING",
            event_message="Automation job created.",
            metadata_json={"job_checksum": job_checksum, "payload_checksum": payload_checksum, "manifest_checksum": manifest_checksum},
        ),
    )
    transition_automation_job_status(
        session,
        job=job,
        to_status="AVAILABLE",
        event_type="STATUS_TRANSITION",
        event_message="Automation job became available.",
        metadata_json={"available_at": available_at},
    )

    artifacts = _build_job_artifacts(payload_snapshot_json, manifest)
    for artifact in artifacts:
        artifact_checksum = _sha256_bytes(artifact.body)
        relative_path = _queue_storage_path(queue_key=queue.queue_key, job_id=int(job.id), artifact_type=artifact.artifact_type, ext=artifact.ext)
        _save_artifact_bytes(settings, relative_path=relative_path, body=artifact.body)
        session.add(
            AutomationJobArtifact(
                job_id=int(job.id),
                artifact_type=artifact.artifact_type,
                storage_backend="filesystem",
                storage_path=relative_path,
                artifact_checksum=artifact_checksum,
                metadata_json=_json_safe(artifact.metadata_json),
            )
        )

    session.commit()
    return get_automation_job_owner(session, settings, owner_user_id=owner_user_id, job_id=int(job.id)), True


def transition_automation_job_status(
    session: Session,
    *,
    job: AutomationJob,
    to_status: str,
    event_type: str,
    event_message: str,
    metadata_json: dict[str, Any],
) -> None:
    from_status = job.job_status
    validate_job_transition(from_status=from_status, to_status=to_status)
    occurred_at = utc_now()
    job.job_status = to_status
    if to_status == "RUNNING":
        job.started_at = occurred_at
    elif to_status == "COMPLETED":
        job.completed_at = occurred_at
    elif to_status in {"FAILED", "DEAD_LETTER"}:
        job.failed_at = occurred_at
    _record_history(
        session,
        job_id=int(job.id),
        draft=_HistoryDraft(
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            event_message=event_message,
            metadata_json=build_transition_metadata(from_status=from_status, to_status=to_status, occurred_at=occurred_at, metadata_json=_json_safe(metadata_json)),
        ),
    )


def _load_job(session: Session, *, job_id: int) -> tuple[AutomationJob, AutomationQueue]:
    job = session.get(AutomationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Automation job not found.")
    queue = session.get(AutomationQueue, int(job.queue_id))
    if queue is None:
        raise HTTPException(status_code=404, detail="Automation queue not found.")
    return job, queue


def _ensure_owner_access(job: AutomationJob, *, owner_user_id: int) -> None:
    if job.owner_user_id is not None and int(job.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Automation job not found.")


def reserve_automation_job(
    session: Session,
    *,
    queue_key: str,
    reservation_token: str,
    now: datetime | None = None,
    reservation_window_seconds: int = 300,
) -> AutomationJob | None:
    if not reservation_token.strip():
        raise HTTPException(status_code=422, detail="Reservation token is required.")
    current_time = now or utc_now()
    queue = session.exec(select(AutomationQueue).where(AutomationQueue.queue_key == queue_key)).first()
    if queue is None:
        raise HTTPException(status_code=404, detail="Automation queue not found.")
    _require_queue_status(queue)

    candidates = list(
        session.exec(
            select(AutomationJob)
            .where(
                AutomationJob.queue_id == queue.id,
                AutomationJob.job_status == "AVAILABLE",
                AutomationJob.available_at <= current_time,
            )
        ).all()
    )
    candidates.sort(
        key=lambda row: (
            -_priority_weight(row.priority),
            row.deterministic_rank,
            row.available_at,
            row.created_at,
            row.id or 0,
        )
    )
    if not candidates:
        return None

    job = candidates[0]
    if job.reservation_token and job.reserved_until and job.reserved_until > current_time:
        _record_issue(
            session,
            job_id=int(job.id),
            draft=_IssueDraft(
                issue_type="DOUBLE_RESERVATION_ATTEMPT",
                severity="CRITICAL",
                issue_message="A second reservation attempt was blocked for an already reserved job.",
                metadata_json={"reservation_token": reservation_token},
            ),
        )
        session.commit()
        raise HTTPException(status_code=409, detail="Automation job already reserved.")

    transition_automation_job_status(
        session,
        job=job,
        to_status="RESERVED",
        event_type="JOB_RESERVED",
        event_message="Automation job reserved for worker-safe processing.",
        metadata_json={"reservation_token": reservation_token},
    )
    job.reservation_token = reservation_token
    job.reserved_until = current_time + timedelta(seconds=reservation_window_seconds)
    session.commit()
    session.refresh(job)
    return job


def release_automation_job_reservation(
    session: Session,
    *,
    job_id: int,
    reservation_token: str,
) -> AutomationJob:
    job, _queue = _load_job(session, job_id=job_id)
    if job.job_status != "RESERVED" or job.reservation_token != reservation_token:
        raise HTTPException(status_code=409, detail="Reservation token mismatch.")
    transition_automation_job_status(
        session,
        job=job,
        to_status="AVAILABLE",
        event_type="RESERVATION_RELEASED",
        event_message="Automation job reservation released.",
        metadata_json={"reservation_token": reservation_token},
    )
    job.reservation_token = None
    job.reserved_until = None
    session.commit()
    session.refresh(job)
    return job


def mark_automation_job_completed(
    session: Session,
    *,
    job_id: int,
    reservation_token: str,
    metadata_json: dict[str, Any] | None = None,
) -> AutomationJob:
    job, _queue = _load_job(session, job_id=job_id)
    if job.reservation_token != reservation_token:
        raise HTTPException(status_code=409, detail="Reservation token mismatch.")
    if job.job_status == "RESERVED":
        transition_automation_job_status(
            session,
            job=job,
            to_status="RUNNING",
            event_type="JOB_STARTED",
            event_message="Automation job started running.",
            metadata_json={"reservation_token": reservation_token},
        )
    transition_automation_job_status(
        session,
        job=job,
        to_status="COMPLETED",
        event_type="JOB_COMPLETED",
        event_message="Automation job completed.",
        metadata_json=_json_safe(metadata_json or {}),
    )
    job.reservation_token = None
    job.reserved_until = None
    session.commit()
    session.refresh(job)
    return job


def mark_automation_job_failed(
    session: Session,
    *,
    job_id: int,
    reservation_token: str,
    failure_reason: str,
    metadata_json: dict[str, Any] | None = None,
) -> AutomationJob:
    job, _queue = _load_job(session, job_id=job_id)
    if job.reservation_token != reservation_token:
        raise HTTPException(status_code=409, detail="Reservation token mismatch.")
    if job.job_status == "RESERVED":
        transition_automation_job_status(
            session,
            job=job,
            to_status="RUNNING",
            event_type="JOB_STARTED",
            event_message="Automation job started running.",
            metadata_json={"reservation_token": reservation_token},
        )
    transition_automation_job_status(
        session,
        job=job,
        to_status="FAILED",
        event_type="JOB_FAILED",
        event_message="Automation job failed.",
        metadata_json={"failure_reason": failure_reason, **_json_safe(metadata_json or {})},
    )
    job.current_attempt_count += 1
    job.reservation_token = None
    job.reserved_until = None
    _record_issue(
        session,
        job_id=int(job.id),
        draft=_IssueDraft(
            issue_type="AUTOMATION_JOB_FAILURE",
            severity="ERROR",
            issue_message=failure_reason,
            metadata_json=_json_safe(metadata_json or {}),
        ),
    )
    session.commit()
    session.refresh(job)
    return job


def create_job_dependency(
    session: Session,
    *,
    job_id: int,
    depends_on_job_id: int,
) -> AutomationJobDependency:
    if job_id == depends_on_job_id:
        raise HTTPException(status_code=422, detail="Dependency cycle detected.")
    existing = session.exec(
        select(AutomationJobDependency).where(
            AutomationJobDependency.job_id == depends_on_job_id,
            AutomationJobDependency.depends_on_job_id == job_id,
        )
    ).first()
    if existing is not None:
        raise HTTPException(status_code=422, detail="Dependency cycle detected.")
    row = session.exec(
        select(AutomationJobDependency).where(
            AutomationJobDependency.job_id == job_id,
            AutomationJobDependency.depends_on_job_id == depends_on_job_id,
        )
    ).first()
    if row is not None:
        return row
    row = AutomationJobDependency(job_id=job_id, depends_on_job_id=depends_on_job_id, dependency_status="BLOCKING")
    session.add(row)
    session.flush()
    _record_history(
        session,
        job_id=job_id,
        draft=_HistoryDraft(
            event_type="DEPENDENCY_ADDED",
            from_status=None,
            to_status=None,
            event_message="Job dependency added.",
            metadata_json={"depends_on_job_id": depends_on_job_id},
        ),
    )
    session.commit()
    session.refresh(row)
    return row


def _build_job_detail(session: Session, settings: Settings, *, job: AutomationJob, queue: AutomationQueue) -> AutomationJobDetail:
    attempts = list(session.exec(select(AutomationJobAttempt).where(AutomationJobAttempt.job_id == job.id).order_by(col(AutomationJobAttempt.attempt_number), col(AutomationJobAttempt.id))).all())
    dependencies = list(session.exec(select(AutomationJobDependency).where(AutomationJobDependency.job_id == job.id).order_by(col(AutomationJobDependency.depends_on_job_id), col(AutomationJobDependency.id))).all())
    artifacts = list(session.exec(select(AutomationJobArtifact).where(AutomationJobArtifact.job_id == job.id).order_by(col(AutomationJobArtifact.created_at), col(AutomationJobArtifact.id))).all())
    issues = list(session.exec(select(AutomationJobIssue).where(AutomationJobIssue.job_id == job.id).order_by(col(AutomationJobIssue.created_at), col(AutomationJobIssue.id))).all())
    history = list(session.exec(select(AutomationJobHistory).where(AutomationJobHistory.job_id == job.id).order_by(col(AutomationJobHistory.created_at), col(AutomationJobHistory.id))).all())
    artifact_reads: list[AutomationJobArtifactRead] = []
    for row in artifacts:
        media_type, text_preview, body_base64 = _load_artifact_payload(settings, row)
        artifact_reads.append(AutomationJobArtifactRead.model_validate({**row.model_dump(), "media_type": media_type, "text_preview": text_preview, "body_base64": body_base64}))
    dependency_graph = [
        {
            "job_id": row.job_id,
            "depends_on_job_id": row.depends_on_job_id,
            "dependency_status": row.dependency_status,
        }
        for row in dependencies
    ]
    return AutomationJobDetail(
        **_job_to_read(job, queue).model_dump(),
        attempts=[AutomationJobAttemptRead.model_validate(row) for row in attempts],
        dependencies=[AutomationJobDependencyRead.model_validate(row) for row in dependencies],
        artifacts=artifact_reads,
        issues=[AutomationJobIssueRead.model_validate(row) for row in issues],
        history=[AutomationJobHistoryRead.model_validate(row) for row in history],
        dependency_graph=dependency_graph,
    )


def get_automation_job_owner(session: Session, settings: Settings, *, owner_user_id: int, job_id: int) -> AutomationJobDetail:
    job, queue = _load_job(session, job_id=job_id)
    _ensure_owner_access(job, owner_user_id=owner_user_id)
    return _build_job_detail(session, settings, job=job, queue=queue)


def get_automation_job_artifact_owner(session: Session, settings: Settings, *, owner_user_id: int, job_id: int, artifact_id: int) -> AutomationJobArtifactRead:
    job, _queue = _load_job(session, job_id=job_id)
    _ensure_owner_access(job, owner_user_id=owner_user_id)
    artifact = session.get(AutomationJobArtifact, artifact_id)
    if artifact is None or int(artifact.job_id) != int(job_id):
        raise HTTPException(status_code=404, detail="Automation job artifact not found.")
    media_type, text_preview, body_base64 = _load_artifact_payload(settings, artifact)
    return AutomationJobArtifactRead.model_validate({**artifact.model_dump(), "media_type": media_type, "text_preview": text_preview, "body_base64": body_base64})


def _list_jobs(
    session: Session,
    *,
    owner_user_id: int | None,
    organization_id: int | None,
    queue_key: str | None,
    job_status: str | None,
    limit: int,
    offset: int,
) -> AutomationJobListResponse:
    limit, offset = clamp_automation_jobs_pagination(limit=limit, offset=offset)
    jobs = list(session.exec(select(AutomationJob)).all())
    queues = {row.id: row for row in session.exec(select(AutomationQueue)).all()}
    filtered: list[AutomationJob] = []
    for row in jobs:
        if owner_user_id is not None and row.owner_user_id is not None and int(row.owner_user_id) != owner_user_id:
            continue
        if owner_user_id is not None and row.owner_user_id is None:
            continue
        if organization_id is not None and row.organization_id != organization_id:
            continue
        queue = queues.get(row.queue_id)
        if queue_key is not None and (queue is None or queue.queue_key != queue_key):
            continue
        if job_status is not None and row.job_status != job_status:
            continue
        filtered.append(row)
    filtered.sort(
        key=lambda row: (
            -_priority_weight(row.priority),
            row.deterministic_rank,
            row.available_at,
            row.created_at,
            row.id or 0,
        )
    )
    items = filtered[offset : offset + limit]
    status_counts: dict[str, int] = {}
    priority_counts: dict[str, int] = {}
    queue_counts: dict[str, int] = {}
    for row in filtered:
        status_counts[row.job_status] = status_counts.get(row.job_status, 0) + 1
        priority_counts[row.priority] = priority_counts.get(row.priority, 0) + 1
        queue = queues.get(row.queue_id)
        queue_key_value = queue.queue_key if queue else "unknown"
        queue_counts[queue_key_value] = queue_counts.get(queue_key_value, 0) + 1
    return AutomationJobListResponse(
        items=[_job_to_read(row, queues.get(row.queue_id)) for row in items],
        total_items=len(filtered),
        limit=limit,
        offset=offset,
        status_counts=status_counts,
        priority_counts=priority_counts,
        queue_counts=queue_counts,
        failed_job_count=status_counts.get("FAILED", 0),
        dead_letter_count=status_counts.get("DEAD_LETTER", 0),
        reserved_job_count=status_counts.get("RESERVED", 0),
    )


def list_automation_jobs_owner(
    session: Session,
    *,
    owner_user_id: int,
    queue_key: str | None,
    job_status: str | None,
    limit: int,
    offset: int,
) -> AutomationJobListResponse:
    return _list_jobs(session, owner_user_id=owner_user_id, organization_id=None, queue_key=queue_key, job_status=job_status, limit=limit, offset=offset)


def list_automation_jobs_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    organization_id: int | None,
    queue_key: str | None,
    job_status: str | None,
    limit: int,
    offset: int,
) -> AutomationJobListResponse:
    return _list_jobs(session, owner_user_id=owner_user_id, organization_id=organization_id, queue_key=queue_key, job_status=job_status, limit=limit, offset=offset)


def list_automation_job_attempts_owner(session: Session, *, owner_user_id: int, job_id: int) -> list[AutomationJobAttemptRead]:
    job, _queue = _load_job(session, job_id=job_id)
    _ensure_owner_access(job, owner_user_id=owner_user_id)
    rows = list(session.exec(select(AutomationJobAttempt).where(AutomationJobAttempt.job_id == job_id).order_by(col(AutomationJobAttempt.attempt_number), col(AutomationJobAttempt.id))).all())
    return [AutomationJobAttemptRead.model_validate(row) for row in rows]


def list_automation_job_history_owner(session: Session, *, owner_user_id: int, job_id: int) -> list[AutomationJobHistoryRead]:
    job, _queue = _load_job(session, job_id=job_id)
    _ensure_owner_access(job, owner_user_id=owner_user_id)
    rows = list(session.exec(select(AutomationJobHistory).where(AutomationJobHistory.job_id == job_id).order_by(col(AutomationJobHistory.created_at), col(AutomationJobHistory.id))).all())
    return [AutomationJobHistoryRead.model_validate(row) for row in rows]


def list_automation_job_issues_owner(session: Session, *, owner_user_id: int, job_id: int) -> list[AutomationJobIssueRead]:
    job, _queue = _load_job(session, job_id=job_id)
    _ensure_owner_access(job, owner_user_id=owner_user_id)
    rows = list(session.exec(select(AutomationJobIssue).where(AutomationJobIssue.job_id == job_id).order_by(col(AutomationJobIssue.created_at), col(AutomationJobIssue.id))).all())
    return [AutomationJobIssueRead.model_validate(row) for row in rows]


def list_automation_queues_ops(session: Session, *, limit: int, offset: int) -> AutomationQueueListResponse:
    limit, offset = clamp_automation_jobs_pagination(limit=limit, offset=offset)
    queues = list(session.exec(select(AutomationQueue).order_by(col(AutomationQueue.queue_key), col(AutomationQueue.id))).all())
    jobs = list(session.exec(select(AutomationJob)).all())
    status_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    queue_reads: list[AutomationQueueRead] = []
    for queue in queues:
        status_counts[queue.queue_status] = status_counts.get(queue.queue_status, 0) + 1
        category_counts[queue.queue_category] = category_counts.get(queue.queue_category, 0) + 1
        queue_jobs = [row for row in jobs if int(row.queue_id) == int(queue.id)]
        queue_reads.append(
            AutomationQueueRead.model_validate(
                {
                    **queue.model_dump(),
                    "total_jobs": len(queue_jobs),
                    "pending_jobs": sum(1 for row in queue_jobs if row.job_status in {"PENDING", "AVAILABLE", "RETRY_PENDING"}),
                    "failed_jobs": sum(1 for row in queue_jobs if row.job_status == "FAILED"),
                    "dead_letter_jobs": sum(1 for row in queue_jobs if row.job_status == "DEAD_LETTER"),
                    "reserved_jobs": sum(1 for row in queue_jobs if row.job_status == "RESERVED"),
                }
            )
        )
    paged = queue_reads[offset : offset + limit]
    return AutomationQueueListResponse(items=paged, total_items=len(queue_reads), limit=limit, offset=offset, status_counts=status_counts, queue_category_counts=category_counts)


def list_automation_jobs_failed_ops(session: Session, *, owner_user_id: int | None, limit: int, offset: int) -> AutomationJobListResponse:
    return list_automation_jobs_ops(session, owner_user_id=owner_user_id, organization_id=None, queue_key=None, job_status="FAILED", limit=limit, offset=offset)


def list_automation_jobs_dead_letter_ops(session: Session, *, owner_user_id: int | None, limit: int, offset: int) -> AutomationJobListResponse:
    return list_automation_jobs_ops(session, owner_user_id=owner_user_id, organization_id=None, queue_key=None, job_status="DEAD_LETTER", limit=limit, offset=offset)


def list_automation_issues_ops(session: Session, *, limit: int, offset: int) -> list[AutomationJobIssueRead]:
    limit, offset = clamp_automation_jobs_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationJobIssue).order_by(col(AutomationJobIssue.created_at), col(AutomationJobIssue.id)).offset(offset).limit(limit)).all())
    return [AutomationJobIssueRead.model_validate(row) for row in rows]


def get_automation_queue_health_ops(session: Session, *, limit: int, offset: int) -> AutomationQueueListResponse:
    return list_automation_queues_ops(session, limit=limit, offset=offset)
