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
    AutomationJob,
    AutomationJobIssue,
    AutomationQueue,
    AutomationWorker,
    AutomationWorkerExecution,
    AutomationWorkerHeartbeat,
    AutomationWorkerHistory,
    AutomationWorkerIssue,
    AutomationWorkerLease,
)
from app.schemas.automation_workers import (
    AutomationWorkerDetail,
    AutomationWorkerExecutionComplete,
    AutomationWorkerExecutionFail,
    AutomationWorkerExecutionListResponse,
    AutomationWorkerExecutionRead,
    AutomationWorkerExecutionStart,
    AutomationWorkerHeartbeatCreate,
    AutomationWorkerHeartbeatRead,
    AutomationWorkerHistoryListResponse,
    AutomationWorkerHistoryRead,
    AutomationWorkerIssueListResponse,
    AutomationWorkerIssueRead,
    AutomationWorkerLeaseListResponse,
    AutomationWorkerLeaseAcquire,
    AutomationWorkerLeaseRead,
    AutomationWorkerLeaseRenew,
    AutomationWorkerListResponse,
    AutomationWorkerRead,
    AutomationWorkerRegister,
)
from app.services.automation_jobs import (
    mark_automation_job_completed,
    mark_automation_job_failed,
    reserve_automation_job,
    transition_automation_job_status,
)
from app.services.automation_worker_state import build_worker_transition_metadata, validate_worker_transition

ENGINE_VERSION = "P41-02-v1"
_WORKER_TYPES = {"API_WORKER", "SCAN_WORKER", "REPLAY_WORKER", "MAINTENANCE_WORKER", "SYSTEM_WORKER"}
_HEARTBEAT_STATUSES = {"HEALTHY", "DEGRADED", "OVERLOADED", "LOST"}
_WORKER_ARTIFACT_MEDIA_TYPES = {".json": "application/json", ".txt": "text/plain; charset=utf-8"}
_ACTIVE_LEASE_STATUSES = {"ACTIVE"}
_ACTIVE_EXECUTION_STATUSES = {"STARTED", "RUNNING"}
_LEASE_EXPIRE_EVENT_TYPES = {"LEASE_EXPIRED", "LEASE_RELEASED"}


@dataclass(frozen=True)
class _WorkerIssueDraft:
    issue_type: str
    severity: str
    issue_message: str
    metadata_json: dict[str, Any]
    job_id: int | None = None


@dataclass(frozen=True)
class _WorkerHistoryDraft:
    event_type: str
    event_message: str
    metadata_json: dict[str, Any]
    from_status: str | None = None
    to_status: str | None = None
    job_id: int | None = None


def utc_now() -> datetime:
    from app.models.automation_workers import utc_now as _utc_now

    return _utc_now()


def clamp_automation_workers_pagination(*, limit: int, offset: int) -> tuple[int, int]:
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


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _resolve_worker_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.automation_workers_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("automation workers storage path escapes configured root")
    return target


def _save_worker_artifact_bytes(settings: Settings, *, relative_path: str, body: bytes) -> None:
    target = _resolve_worker_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)


def _load_worker_artifact_payload(settings: Settings, *, storage_path: str) -> tuple[str | None, str | None]:
    try:
        body = _resolve_worker_storage_path(settings, storage_path).read_bytes()
    except OSError:
        return None, None
    media_type = _WORKER_ARTIFACT_MEDIA_TYPES.get(Path(storage_path).suffix.lower(), "application/octet-stream")
    try:
        return media_type, body.decode("utf-8")[:20000]
    except UnicodeDecodeError:
        return media_type, None


def _worker_storage_path(*, worker_key: str, job_id: int, artifact_type: str, ext: str) -> str:
    return f"automation-workers/{worker_key}/{job_id}/{artifact_type.lower()}{ext}".replace("\\", "/")


def _execution_duration_ms(*, started_at: datetime, completed_at: datetime) -> int:
    started = _normalize_datetime(started_at) or completed_at
    ended = _normalize_datetime(completed_at) or completed_at
    return max(int((ended - started).total_seconds() * 1000), 0)


def _stale_seconds(settings: Settings) -> int:
    return 120


def _validate_queue_scope(value: dict[str, Any]) -> dict[str, Any]:
    queue_keys = value.get("queue_keys")
    if queue_keys is None:
        return _json_safe(value)
    if not isinstance(queue_keys, list) or not all(isinstance(item, str) and item.strip() for item in queue_keys):
        raise HTTPException(status_code=422, detail="queue_scope_json.queue_keys must be a list of non-empty strings.")
    return _json_safe(value)


def _record_worker_history(session: Session, *, worker_id: int, draft: _WorkerHistoryDraft) -> None:
    payload = {
        "worker_id": worker_id,
        "job_id": draft.job_id,
        "event_type": draft.event_type,
        "from_status": draft.from_status,
        "to_status": draft.to_status,
        "event_message": draft.event_message,
        "metadata_json": draft.metadata_json,
    }
    session.add(
        AutomationWorkerHistory(
            worker_id=worker_id,
            job_id=draft.job_id,
            event_type=draft.event_type,
            from_status=draft.from_status,
            to_status=draft.to_status,
            event_message=draft.event_message,
            event_checksum=_hash_payload(payload),
            metadata_json=_json_safe(draft.metadata_json),
        )
    )


def _record_worker_issue(session: Session, *, worker_id: int, draft: _WorkerIssueDraft) -> None:
    payload = {
        "worker_id": worker_id,
        "job_id": draft.job_id,
        "issue_type": draft.issue_type,
        "severity": draft.severity,
        "issue_message": draft.issue_message,
        "metadata_json": draft.metadata_json,
    }
    session.add(
        AutomationWorkerIssue(
            worker_id=worker_id,
            job_id=draft.job_id,
            issue_type=draft.issue_type,
            severity=draft.severity,
            issue_message=draft.issue_message,
            issue_checksum=_hash_payload(payload),
            metadata_json=_json_safe(draft.metadata_json),
        )
    )


def transition_automation_worker_status(
    session: Session,
    *,
    worker: AutomationWorker,
    to_status: str,
    event_type: str,
    event_message: str,
    metadata_json: dict[str, Any],
    job_id: int | None = None,
) -> None:
    from_status = worker.worker_status
    validate_worker_transition(from_status=from_status, to_status=to_status)
    occurred_at = utc_now()
    worker.worker_status = to_status
    if to_status == "OFFLINE":
        worker.shutdown_at = occurred_at
    _record_worker_history(
        session,
        worker_id=int(worker.id),
        draft=_WorkerHistoryDraft(
            event_type=event_type,
            event_message=event_message,
            metadata_json=build_worker_transition_metadata(
                from_status=from_status,
                to_status=to_status,
                occurred_at=occurred_at,
                metadata_json=_json_safe(metadata_json),
            ),
            from_status=from_status,
            to_status=to_status,
            job_id=job_id,
        ),
    )


def _active_leases_for_worker(session: Session, *, worker_id: int) -> list[AutomationWorkerLease]:
    now = utc_now()
    rows = list(
        session.exec(
            select(AutomationWorkerLease).where(
                AutomationWorkerLease.worker_id == worker_id,
                AutomationWorkerLease.lease_status == "ACTIVE",
            )
        ).all()
    )
    return [row for row in rows if (_normalize_datetime(row.lease_expires_at) or now) > now]


def _active_executions_for_worker(session: Session, *, worker_id: int) -> list[AutomationWorkerExecution]:
    return list(
        session.exec(
            select(AutomationWorkerExecution).where(
                AutomationWorkerExecution.worker_id == worker_id,
                col(AutomationWorkerExecution.execution_status).in_(_ACTIVE_EXECUTION_STATUSES),
            )
        ).all()
    )


def _build_worker_key(*, worker_identifier: str, worker_type: str, queue_scope_json: dict[str, Any]) -> str:
    return _hash_payload(
        {
            "worker_identifier": worker_identifier,
            "worker_type": worker_type,
            "queue_scope_json": queue_scope_json,
        }
    )[:24]


def _load_worker(session: Session, *, worker_id: int) -> AutomationWorker:
    worker = session.get(AutomationWorker, worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="Automation worker not found.")
    return worker


def _load_job(session: Session, *, job_id: int) -> AutomationJob:
    job = session.get(AutomationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Automation job not found.")
    return job


def _queue_matches_scope(worker: AutomationWorker, queue: AutomationQueue) -> bool:
    queue_keys = worker.queue_scope_json.get("queue_keys")
    if not queue_keys:
        return True
    return queue.queue_key in queue_keys


def _ensure_worker_job_access(worker: AutomationWorker, job: AutomationJob) -> None:
    if worker.current_job_id is not None and worker.current_job_id != job.id and worker.worker_status in {"RESERVED", "RUNNING"}:
        raise HTTPException(status_code=409, detail="Worker already owns a different active job.")


def _build_execution_snapshot(
    *,
    worker: AutomationWorker,
    lease: AutomationWorkerLease,
    job: AutomationJob,
    queue: AutomationQueue,
    execution_rank: int,
    metadata_json: dict[str, Any],
) -> dict[str, Any]:
    return {
        "engine_version": ENGINE_VERSION,
        "worker": {
            "worker_key": worker.worker_key,
            "worker_identifier": worker.worker_identifier,
            "worker_type": worker.worker_type,
            "worker_status": worker.worker_status,
            "max_concurrency": worker.max_concurrency,
            "queue_scope_json": _json_safe(worker.queue_scope_json),
        },
        "lease": {
            "lease_id": lease.id,
            "job_id": lease.job_id,
            "reservation_token": lease.reservation_token,
            "lease_status": lease.lease_status,
            "lease_expires_at": lease.lease_expires_at,
            "acquired_at": lease.acquired_at,
        },
        "job": {
            "job_id": job.id,
            "job_type": job.job_type,
            "job_status": job.job_status,
            "queue_key": queue.queue_key,
            "job_checksum": job.job_checksum,
            "payload_checksum": job.payload_checksum,
            "source_checksum": job.source_checksum,
        },
        "execution_rank": execution_rank,
        "metadata_json": _json_safe(metadata_json),
    }


def _build_execution_manifest(
    *,
    worker: AutomationWorker,
    lease: AutomationWorkerLease,
    execution_snapshot: dict[str, Any],
    execution_checksum: str,
    artifact_refs: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "engine_version": ENGINE_VERSION,
        "worker_key": worker.worker_key,
        "worker_identifier": worker.worker_identifier,
        "lease": _json_safe(
            {
                "reservation_token": lease.reservation_token,
                "lease_expires_at": lease.lease_expires_at,
                "acquired_at": lease.acquired_at,
            }
        ),
        "execution_snapshot": _json_safe(execution_snapshot),
        "execution_checksum": execution_checksum,
        "artifact_refs": _json_safe(sorted(artifact_refs, key=lambda row: (row["artifact_type"], row["storage_path"]))),
        "issues": _json_safe(sorted(issues, key=lambda row: (row.get("severity") or "", row.get("issue_type") or ""))),
    }


def register_worker(session: Session, *, payload: AutomationWorkerRegister) -> tuple[AutomationWorkerDetail, bool]:
    queue_scope_json = _validate_queue_scope(payload.queue_scope_json)
    if str(payload.worker_type) not in _WORKER_TYPES:
        raise HTTPException(status_code=422, detail="Invalid automation worker type.")
    worker_key = _build_worker_key(
        worker_identifier=payload.worker_identifier,
        worker_type=str(payload.worker_type),
        queue_scope_json=queue_scope_json,
    )
    existing = session.exec(select(AutomationWorker).where(AutomationWorker.worker_key == worker_key)).first()
    if existing is not None:
        return get_automation_worker_ops(session, worker_id=int(existing.id)), False

    worker = AutomationWorker(
        worker_key=worker_key,
        worker_identifier=payload.worker_identifier,
        worker_type=str(payload.worker_type),
        worker_status="STARTING",
        process_identifier=payload.process_identifier,
        hostname=payload.hostname,
        queue_scope_json=queue_scope_json,
        current_job_id=None,
        max_concurrency=payload.max_concurrency,
        metadata_json=_json_safe(payload.metadata_json),
    )
    session.add(worker)
    session.flush()
    _record_worker_history(
        session,
        worker_id=int(worker.id),
        draft=_WorkerHistoryDraft(
            event_type="WORKER_REGISTERED",
            event_message="Automation worker registered.",
            metadata_json={"worker_key": worker_key, "worker_type": worker.worker_type},
        ),
    )
    transition_automation_worker_status(
        session,
        worker=worker,
        to_status="IDLE",
        event_type="WORKER_READY",
        event_message="Automation worker entered idle state.",
        metadata_json={"queue_scope_json": queue_scope_json},
    )
    session.commit()
    return get_automation_worker_ops(session, worker_id=int(worker.id)), True


def record_worker_heartbeat(
    session: Session,
    *,
    worker_id: int,
    payload: AutomationWorkerHeartbeatCreate,
) -> AutomationWorkerHeartbeatRead:
    worker = _load_worker(session, worker_id=worker_id)
    if str(payload.heartbeat_status) not in _HEARTBEAT_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid heartbeat status.")
    row = AutomationWorkerHeartbeat(
        worker_id=worker_id,
        heartbeat_status=str(payload.heartbeat_status),
        active_job_count=payload.active_job_count,
        memory_usage_mb=payload.memory_usage_mb,
        cpu_usage_percent=payload.cpu_usage_percent,
        metadata_json=_json_safe(payload.metadata_json),
    )
    session.add(row)
    worker.last_heartbeat_at = row.created_at
    _record_worker_history(
        session,
        worker_id=worker_id,
        draft=_WorkerHistoryDraft(
            event_type="HEARTBEAT_RECORDED",
            event_message="Worker heartbeat recorded.",
            metadata_json={
                "heartbeat_status": payload.heartbeat_status,
                "active_job_count": payload.active_job_count,
            },
        ),
    )
    session.commit()
    session.refresh(row)
    return AutomationWorkerHeartbeatRead.model_validate(row)


def acquire_job_lease(
    session: Session,
    *,
    worker_id: int,
    payload: AutomationWorkerLeaseAcquire,
) -> AutomationWorkerLeaseRead:
    worker = _load_worker(session, worker_id=worker_id)
    active_leases = _active_leases_for_worker(session, worker_id=worker_id)
    active_executions = _active_executions_for_worker(session, worker_id=worker_id)
    if len(active_leases) + len(active_executions) >= worker.max_concurrency:
        _record_worker_issue(
            session,
            worker_id=worker_id,
            draft=_WorkerIssueDraft(
                issue_type="WORKER_CONCURRENCY_EXCEEDED",
                severity="ERROR",
                issue_message="Worker concurrency limit exceeded.",
                metadata_json={"max_concurrency": worker.max_concurrency},
            ),
        )
        session.commit()
        raise HTTPException(status_code=409, detail="Worker concurrency limit exceeded.")

    queue_keys = worker.queue_scope_json.get("queue_keys") or []
    candidate_job: AutomationJob | None = None
    if queue_keys:
        for queue_key in queue_keys:
            job = reserve_automation_job(
                session,
                queue_key=queue_key,
                reservation_token=payload.reservation_token,
                reservation_window_seconds=payload.lease_seconds,
            )
            if job is not None:
                candidate_job = job
                break
    else:
        queues = list(session.exec(select(AutomationQueue).order_by(col(AutomationQueue.queue_key), col(AutomationQueue.id))).all())
        for queue in queues:
            job = reserve_automation_job(
                session,
                queue_key=queue.queue_key,
                reservation_token=payload.reservation_token,
                reservation_window_seconds=payload.lease_seconds,
            )
            if job is not None:
                candidate_job = job
                break
    if candidate_job is None:
        raise HTTPException(status_code=404, detail="No available automation job for worker.")

    queue = session.get(AutomationQueue, int(candidate_job.queue_id))
    if queue is None or not _queue_matches_scope(worker, queue):
        raise HTTPException(status_code=409, detail="Reserved job fell outside worker queue scope.")
    _ensure_worker_job_access(worker, candidate_job)
    if worker.worker_status == "IDLE":
        transition_automation_worker_status(
            session,
            worker=worker,
            to_status="RESERVED",
            event_type="WORKER_RESERVED",
            event_message="Worker reserved a queue job.",
            metadata_json={"job_id": candidate_job.id, "reservation_token": payload.reservation_token},
            job_id=int(candidate_job.id),
        )
    lease = AutomationWorkerLease(
        worker_id=worker_id,
        job_id=int(candidate_job.id),
        reservation_token=payload.reservation_token,
        lease_status="ACTIVE",
        lease_expires_at=utc_now() + timedelta(seconds=payload.lease_seconds),
        metadata_json={"queue_key": queue.queue_key, "job_checksum": candidate_job.job_checksum},
    )
    worker.current_job_id = int(candidate_job.id)
    session.add(lease)
    _record_worker_history(
        session,
        worker_id=worker_id,
        draft=_WorkerHistoryDraft(
            event_type="LEASE_ACQUIRED",
            event_message="Worker lease acquired.",
            metadata_json={"job_id": candidate_job.id, "reservation_token": payload.reservation_token},
            job_id=int(candidate_job.id),
        ),
    )
    session.commit()
    session.refresh(lease)
    return AutomationWorkerLeaseRead.model_validate(lease)


def renew_worker_lease(
    session: Session,
    *,
    worker_id: int,
    payload: AutomationWorkerLeaseRenew,
) -> AutomationWorkerLeaseRead:
    worker = _load_worker(session, worker_id=worker_id)
    lease = session.exec(
        select(AutomationWorkerLease).where(
            AutomationWorkerLease.worker_id == worker_id,
            AutomationWorkerLease.reservation_token == payload.reservation_token,
            AutomationWorkerLease.lease_status == "ACTIVE",
        )
    ).first()
    if lease is None:
        raise HTTPException(status_code=404, detail="Active automation worker lease not found.")
    if (_normalize_datetime(lease.lease_expires_at) or utc_now()) <= utc_now():
        _record_worker_issue(
            session,
            worker_id=worker_id,
            draft=_WorkerIssueDraft(
                issue_type="LEASE_EXPIRED",
                severity="ERROR",
                issue_message="Expired lease cannot be renewed.",
                metadata_json={"reservation_token": payload.reservation_token},
                job_id=int(lease.job_id),
            ),
        )
        session.commit()
        raise HTTPException(status_code=409, detail="Automation worker lease has expired.")
    lease.lease_expires_at = utc_now() + timedelta(seconds=payload.lease_seconds)
    _record_worker_history(
        session,
        worker_id=worker_id,
        draft=_WorkerHistoryDraft(
            event_type="LEASE_RENEWED",
            event_message="Worker lease renewed.",
            metadata_json={"reservation_token": payload.reservation_token, "lease_expires_at": lease.lease_expires_at},
            job_id=int(lease.job_id),
        ),
    )
    session.commit()
    session.refresh(worker)
    session.refresh(lease)
    return AutomationWorkerLeaseRead.model_validate(lease)


def start_job_execution(
    session: Session,
    settings: Settings,
    *,
    worker_id: int,
    payload: AutomationWorkerExecutionStart,
) -> AutomationWorkerExecutionRead:
    worker = _load_worker(session, worker_id=worker_id)
    lease = session.exec(
        select(AutomationWorkerLease).where(
            AutomationWorkerLease.worker_id == worker_id,
            AutomationWorkerLease.reservation_token == payload.reservation_token,
            AutomationWorkerLease.lease_status == "ACTIVE",
        )
    ).first()
    if lease is None:
        raise HTTPException(status_code=404, detail="Active worker lease not found.")
    if (_normalize_datetime(lease.lease_expires_at) or utc_now()) <= utc_now():
        raise HTTPException(status_code=409, detail="Worker lease has expired.")
    job = _load_job(session, job_id=int(lease.job_id))
    queue = session.get(AutomationQueue, int(job.queue_id))
    if queue is None:
        raise HTTPException(status_code=404, detail="Automation queue not found.")
    active_execution = session.exec(
        select(AutomationWorkerExecution).where(
            AutomationWorkerExecution.job_id == int(job.id),
            col(AutomationWorkerExecution.execution_status).in_(_ACTIVE_EXECUTION_STATUSES),
        )
    ).first()
    if active_execution is not None:
        _record_worker_issue(
            session,
            worker_id=worker_id,
            draft=_WorkerIssueDraft(
                issue_type="DOUBLE_EXECUTION_ATTEMPT",
                severity="CRITICAL",
                issue_message="A second execution attempt was blocked for the same job.",
                metadata_json={"job_id": job.id},
                job_id=int(job.id),
            ),
        )
        session.commit()
        raise HTTPException(status_code=409, detail="Automation job already has an active execution.")

    if worker.worker_status == "RESERVED":
        transition_automation_worker_status(
            session,
            worker=worker,
            to_status="RUNNING",
            event_type="WORKER_RUNNING",
            event_message="Worker started job execution.",
            metadata_json={"job_id": job.id, "reservation_token": payload.reservation_token},
            job_id=int(job.id),
        )
    if job.job_status == "RESERVED":
        transition_automation_job_status(
            session,
            job=job,
            to_status="RUNNING",
            event_type="WORKER_EXECUTION_STARTED",
            event_message="Automation job execution started by worker runtime.",
            metadata_json={"worker_id": worker_id, "reservation_token": payload.reservation_token},
        )

    execution_rank = len(
        list(session.exec(select(AutomationWorkerExecution).where(AutomationWorkerExecution.worker_id == worker_id).order_by(col(AutomationWorkerExecution.execution_rank), col(AutomationWorkerExecution.id))).all())
    ) + 1
    snapshot = _build_execution_snapshot(
        worker=worker,
        lease=lease,
        job=job,
        queue=queue,
        execution_rank=execution_rank,
        metadata_json=payload.metadata_json,
    )
    execution_checksum = _hash_payload(
        {
            "job_checksum": job.job_checksum,
            "reservation_token": lease.reservation_token,
            "execution_snapshot": snapshot,
        }
    )
    artifact_refs: list[dict[str, Any]] = []
    for artifact_type, body in [
        ("WORKER_EXECUTION_SNAPSHOT", _serialize_json_artifact(snapshot)),
        ("WORKER_LEASE_EXPORT", _serialize_json_artifact({"lease": _json_safe(lease.model_dump())})),
        ("WORKER_DEBUG_PREVIEW", _serialize_json_artifact({"worker": worker.worker_identifier, "job_id": job.id, "snapshot": snapshot})),
    ]:
        storage_path = _worker_storage_path(worker_key=worker.worker_key, job_id=int(job.id), artifact_type=artifact_type, ext=".json")
        _save_worker_artifact_bytes(settings, relative_path=storage_path, body=body)
        media_type, text_preview = _load_worker_artifact_payload(settings, storage_path=storage_path)
        artifact_refs.append(
            {
                "artifact_type": artifact_type,
                "storage_path": storage_path,
                "artifact_checksum": _hash_payload({"storage_path": storage_path, "body": body.decode("utf-8")}),
                "media_type": media_type,
                "text_preview": text_preview,
            }
        )
    execution = AutomationWorkerExecution(
        worker_id=worker_id,
        job_id=int(job.id),
        execution_status="STARTED",
        execution_rank=execution_rank,
        execution_snapshot_json=_json_safe({**snapshot, "artifact_refs": artifact_refs}),
        execution_checksum=execution_checksum,
        metadata_json=_json_safe(payload.metadata_json),
    )
    session.add(execution)
    _record_worker_history(
        session,
        worker_id=worker_id,
        draft=_WorkerHistoryDraft(
            event_type="EXECUTION_STARTED",
            event_message="Worker execution started.",
            metadata_json={"job_id": job.id, "execution_checksum": execution_checksum},
            job_id=int(job.id),
        ),
    )
    session.commit()
    session.refresh(execution)
    return AutomationWorkerExecutionRead.model_validate(execution)


def complete_job_execution(
    session: Session,
    settings: Settings,
    *,
    worker_id: int,
    payload: AutomationWorkerExecutionComplete,
) -> AutomationWorkerExecutionRead:
    worker = _load_worker(session, worker_id=worker_id)
    lease = session.exec(
        select(AutomationWorkerLease).where(
            AutomationWorkerLease.worker_id == worker_id,
            AutomationWorkerLease.reservation_token == payload.reservation_token,
            AutomationWorkerLease.lease_status == "ACTIVE",
        )
    ).first()
    if lease is None:
        raise HTTPException(status_code=404, detail="Active worker lease not found.")
    execution = session.exec(
        select(AutomationWorkerExecution).where(
            AutomationWorkerExecution.worker_id == worker_id,
            AutomationWorkerExecution.job_id == int(lease.job_id),
            col(AutomationWorkerExecution.execution_status).in_(_ACTIVE_EXECUTION_STATUSES | {"STARTED"}),
        )
        .order_by(col(AutomationWorkerExecution.execution_rank).desc(), col(AutomationWorkerExecution.id).desc())
    ).first()
    if execution is None:
        raise HTTPException(status_code=404, detail="Active worker execution not found.")
    completed_at = utc_now()
    execution.execution_status = "COMPLETED"
    execution.completed_at = completed_at
    execution.execution_time_ms = _execution_duration_ms(started_at=execution.started_at, completed_at=completed_at)
    manifest = _build_execution_manifest(
        worker=worker,
        lease=lease,
        execution_snapshot=execution.execution_snapshot_json,
        execution_checksum=execution.execution_checksum,
        artifact_refs=execution.execution_snapshot_json.get("artifact_refs", []),
        issues=[],
    )
    for artifact_type, body in [
        ("WORKER_EXECUTION_REPORT", _serialize_json_artifact({"execution_id": execution.id, "status": execution.execution_status, "duration_ms": execution.execution_time_ms})),
        ("WORKER_MANIFEST", _serialize_json_artifact(manifest)),
    ]:
        storage_path = _worker_storage_path(worker_key=worker.worker_key, job_id=int(lease.job_id), artifact_type=artifact_type, ext=".json")
        _save_worker_artifact_bytes(settings, relative_path=storage_path, body=body)
    mark_automation_job_completed(
        session,
        job_id=int(lease.job_id),
        reservation_token=payload.reservation_token,
        metadata_json={"worker_id": worker_id, **_json_safe(payload.metadata_json)},
    )
    lease.lease_status = "RELEASED"
    lease.released_at = completed_at
    worker.current_job_id = None
    if worker.worker_status == "RUNNING":
        transition_automation_worker_status(
            session,
            worker=worker,
            to_status="IDLE",
            event_type="WORKER_IDLE",
            event_message="Worker returned to idle after completion.",
            metadata_json={"job_id": lease.job_id},
            job_id=int(lease.job_id),
        )
    _record_worker_history(
        session,
        worker_id=worker_id,
        draft=_WorkerHistoryDraft(
            event_type="EXECUTION_COMPLETED",
            event_message="Worker execution completed.",
            metadata_json={"execution_id": execution.id, "duration_ms": execution.execution_time_ms},
            job_id=int(lease.job_id),
        ),
    )
    session.commit()
    session.refresh(execution)
    return AutomationWorkerExecutionRead.model_validate(execution)


def fail_job_execution(
    session: Session,
    settings: Settings,
    *,
    worker_id: int,
    payload: AutomationWorkerExecutionFail,
) -> AutomationWorkerExecutionRead:
    worker = _load_worker(session, worker_id=worker_id)
    lease = session.exec(
        select(AutomationWorkerLease).where(
            AutomationWorkerLease.worker_id == worker_id,
            AutomationWorkerLease.reservation_token == payload.reservation_token,
            AutomationWorkerLease.lease_status == "ACTIVE",
        )
    ).first()
    if lease is None:
        raise HTTPException(status_code=404, detail="Active worker lease not found.")
    execution = session.exec(
        select(AutomationWorkerExecution).where(
            AutomationWorkerExecution.worker_id == worker_id,
            AutomationWorkerExecution.job_id == int(lease.job_id),
            col(AutomationWorkerExecution.execution_status).in_(_ACTIVE_EXECUTION_STATUSES | {"STARTED"}),
        )
        .order_by(col(AutomationWorkerExecution.execution_rank).desc(), col(AutomationWorkerExecution.id).desc())
    ).first()
    if execution is None:
        raise HTTPException(status_code=404, detail="Active worker execution not found.")
    completed_at = utc_now()
    execution.execution_status = "FAILED"
    execution.completed_at = completed_at
    execution.execution_time_ms = _execution_duration_ms(started_at=execution.started_at, completed_at=completed_at)
    issue_rows = [{"issue_type": "WORKER_RUNTIME_FAILURE", "severity": "ERROR", "message": payload.failure_reason}]
    manifest = _build_execution_manifest(
        worker=worker,
        lease=lease,
        execution_snapshot=execution.execution_snapshot_json,
        execution_checksum=execution.execution_checksum,
        artifact_refs=execution.execution_snapshot_json.get("artifact_refs", []),
        issues=issue_rows,
    )
    for artifact_type, body in [
        ("WORKER_FAILURE_REPORT", _serialize_json_artifact({"execution_id": execution.id, "failure_reason": payload.failure_reason})),
        ("WORKER_MANIFEST", _serialize_json_artifact(manifest)),
    ]:
        storage_path = _worker_storage_path(worker_key=worker.worker_key, job_id=int(lease.job_id), artifact_type=artifact_type, ext=".json")
        _save_worker_artifact_bytes(settings, relative_path=storage_path, body=body)
    mark_automation_job_failed(
        session,
        job_id=int(lease.job_id),
        reservation_token=payload.reservation_token,
        failure_reason=payload.failure_reason,
        metadata_json={"worker_id": worker_id, **_json_safe(payload.metadata_json)},
    )
    lease.lease_status = "RELEASED"
    lease.released_at = completed_at
    worker.current_job_id = None
    if worker.worker_status == "RUNNING":
        transition_automation_worker_status(
            session,
            worker=worker,
            to_status="IDLE",
            event_type="WORKER_IDLE",
            event_message="Worker returned to idle after failure.",
            metadata_json={"job_id": lease.job_id},
            job_id=int(lease.job_id),
        )
    _record_worker_issue(
        session,
        worker_id=worker_id,
        draft=_WorkerIssueDraft(
            issue_type="WORKER_RUNTIME_FAILURE",
            severity="ERROR",
            issue_message=payload.failure_reason,
            metadata_json=_json_safe(payload.metadata_json),
            job_id=int(lease.job_id),
        ),
    )
    _record_worker_history(
        session,
        worker_id=worker_id,
        draft=_WorkerHistoryDraft(
            event_type="EXECUTION_FAILED",
            event_message="Worker execution failed.",
            metadata_json={"execution_id": execution.id, "failure_reason": payload.failure_reason},
            job_id=int(lease.job_id),
        ),
    )
    session.commit()
    session.refresh(execution)
    return AutomationWorkerExecutionRead.model_validate(execution)


def release_expired_leases(session: Session) -> AutomationWorkerLeaseListResponse:
    now = utc_now()
    rows = list(
        session.exec(
            select(AutomationWorkerLease)
            .where(
                AutomationWorkerLease.lease_status == "ACTIVE",
                AutomationWorkerLease.lease_expires_at <= now,
            )
            .order_by(col(AutomationWorkerLease.lease_expires_at), col(AutomationWorkerLease.id))
        ).all()
    )
    released: list[AutomationWorkerLeaseRead] = []
    for lease in rows:
        active_execution = session.exec(
            select(AutomationWorkerExecution).where(
                AutomationWorkerExecution.worker_id == int(lease.worker_id),
                AutomationWorkerExecution.job_id == int(lease.job_id),
                col(AutomationWorkerExecution.execution_status).in_(_ACTIVE_EXECUTION_STATUSES),
            )
        ).first()
        if active_execution is not None:
            continue
        worker = _load_worker(session, worker_id=int(lease.worker_id))
        lease.lease_status = "EXPIRED"
        lease.released_at = now
        job = _load_job(session, job_id=int(lease.job_id))
        if job.job_status == "RESERVED" and job.reservation_token == lease.reservation_token:
            job.job_status = "AVAILABLE"
            job.reservation_token = None
            job.reserved_until = None
        if worker.current_job_id == lease.job_id:
            worker.current_job_id = None
            if worker.worker_status == "RESERVED":
                worker.worker_status = "IDLE"
        _record_worker_issue(
            session,
            worker_id=int(lease.worker_id),
            draft=_WorkerIssueDraft(
                issue_type="LEASE_EXPIRED",
                severity="ERROR",
                issue_message="Worker lease expired and was released.",
                metadata_json={"reservation_token": lease.reservation_token},
                job_id=int(lease.job_id),
            ),
        )
        _record_worker_history(
            session,
            worker_id=int(lease.worker_id),
            draft=_WorkerHistoryDraft(
                event_type="LEASE_EXPIRED",
                event_message="Expired worker lease released.",
                metadata_json={"reservation_token": lease.reservation_token},
                job_id=int(lease.job_id),
            ),
        )
        released.append(AutomationWorkerLeaseRead.model_validate(lease))
    session.commit()
    return AutomationWorkerLeaseListResponse(items=released, total_items=len(released), limit=len(released) or 1, offset=0)


def _is_stale(worker: AutomationWorker, *, settings: Settings) -> tuple[bool, int | None]:
    if worker.last_heartbeat_at is None:
        return True, None
    heartbeat_at = _normalize_datetime(worker.last_heartbeat_at) or utc_now()
    age_seconds = max(int((utc_now() - heartbeat_at).total_seconds()), 0)
    return age_seconds > _stale_seconds(settings), age_seconds


def _worker_to_read(
    session: Session,
    settings: Settings,
    *,
    worker: AutomationWorker,
) -> AutomationWorkerRead:
    active_lease_count = len(_active_leases_for_worker(session, worker_id=int(worker.id)))
    active_execution_count = len(_active_executions_for_worker(session, worker_id=int(worker.id)))
    stale, heartbeat_age_seconds = _is_stale(worker, settings=settings)
    return AutomationWorkerRead.model_validate(
        {
            **worker.model_dump(),
            "active_lease_count": active_lease_count,
            "active_execution_count": active_execution_count,
            "stale": stale,
            "heartbeat_age_seconds": heartbeat_age_seconds,
        }
    )


def _accessible_worker_ids_for_owner(session: Session, *, owner_user_id: int) -> set[int]:
    ids: set[int] = set()
    jobs = list(session.exec(select(AutomationJob).where(AutomationJob.owner_user_id == owner_user_id)).all())
    job_ids = {int(job.id) for job in jobs if job.id is not None}
    for lease in session.exec(select(AutomationWorkerLease)).all():
        if int(lease.job_id) in job_ids:
            ids.add(int(lease.worker_id))
    for execution in session.exec(select(AutomationWorkerExecution)).all():
        if int(execution.job_id) in job_ids:
            ids.add(int(execution.worker_id))
    for worker in session.exec(select(AutomationWorker)).all():
        if worker.current_job_id is not None and int(worker.current_job_id) in job_ids:
            ids.add(int(worker.id))
    return ids


def _build_worker_detail(session: Session, settings: Settings, *, worker: AutomationWorker) -> AutomationWorkerDetail:
    heartbeats = list(session.exec(select(AutomationWorkerHeartbeat).where(AutomationWorkerHeartbeat.worker_id == worker.id).order_by(col(AutomationWorkerHeartbeat.created_at).desc(), col(AutomationWorkerHeartbeat.id).desc())).all())
    leases = list(session.exec(select(AutomationWorkerLease).where(AutomationWorkerLease.worker_id == worker.id).order_by(col(AutomationWorkerLease.created_at).desc(), col(AutomationWorkerLease.id).desc())).all())
    executions = list(session.exec(select(AutomationWorkerExecution).where(AutomationWorkerExecution.worker_id == worker.id).order_by(col(AutomationWorkerExecution.created_at).desc(), col(AutomationWorkerExecution.id).desc())).all())
    issues = list(session.exec(select(AutomationWorkerIssue).where(AutomationWorkerIssue.worker_id == worker.id).order_by(col(AutomationWorkerIssue.created_at).desc(), col(AutomationWorkerIssue.id).desc())).all())
    history = list(session.exec(select(AutomationWorkerHistory).where(AutomationWorkerHistory.worker_id == worker.id).order_by(col(AutomationWorkerHistory.created_at).desc(), col(AutomationWorkerHistory.id).desc())).all())
    return AutomationWorkerDetail(
        **_worker_to_read(session, settings, worker=worker).model_dump(),
        heartbeats=[AutomationWorkerHeartbeatRead.model_validate(row) for row in heartbeats],
        leases=[AutomationWorkerLeaseRead.model_validate(row) for row in leases],
        executions=[AutomationWorkerExecutionRead.model_validate(row) for row in executions],
        issues=[AutomationWorkerIssueRead.model_validate(row) for row in issues],
        history=[AutomationWorkerHistoryRead.model_validate(row) for row in history],
    )


def get_automation_worker_owner(session: Session, settings: Settings, *, owner_user_id: int, worker_id: int) -> AutomationWorkerDetail:
    accessible = _accessible_worker_ids_for_owner(session, owner_user_id=owner_user_id)
    if worker_id not in accessible:
        raise HTTPException(status_code=404, detail="Automation worker not found.")
    worker = _load_worker(session, worker_id=worker_id)
    return _build_worker_detail(session, settings, worker=worker)


def get_automation_worker_ops(session: Session, *, worker_id: int) -> AutomationWorkerDetail:
    worker = _load_worker(session, worker_id=worker_id)
    from app.core.config import get_settings

    return _build_worker_detail(session, get_settings(), worker=worker)


def _list_workers(
    session: Session,
    settings: Settings,
    *,
    worker_ids: set[int] | None,
    stale_only: bool,
    limit: int,
    offset: int,
) -> AutomationWorkerListResponse:
    limit, offset = clamp_automation_workers_pagination(limit=limit, offset=offset)
    workers = list(session.exec(select(AutomationWorker).order_by(col(AutomationWorker.created_at).desc(), col(AutomationWorker.id).desc())).all())
    items: list[AutomationWorkerRead] = []
    for worker in workers:
        if worker_ids is not None and int(worker.id) not in worker_ids:
            continue
        row = _worker_to_read(session, settings, worker=worker)
        if stale_only and not row.stale:
            continue
        items.append(row)
    total_items = len(items)
    paged = items[offset : offset + limit]
    status_counts: dict[str, int] = {}
    worker_type_counts: dict[str, int] = {}
    stale_count = 0
    active_execution_count = 0
    runtime_issue_count = 0
    issues = list(session.exec(select(AutomationWorkerIssue)).all())
    for item in items:
        status_counts[item.worker_status] = status_counts.get(item.worker_status, 0) + 1
        worker_type_counts[item.worker_type] = worker_type_counts.get(item.worker_type, 0) + 1
        stale_count += 1 if item.stale else 0
        active_execution_count += item.active_execution_count
    visible_ids = {item.id for item in items}
    for issue in issues:
        if int(issue.worker_id) in visible_ids:
            runtime_issue_count += 1
    return AutomationWorkerListResponse(
        items=paged,
        total_items=total_items,
        limit=limit,
        offset=offset,
        status_counts=status_counts,
        worker_type_counts=worker_type_counts,
        stale_count=stale_count,
        active_execution_count=active_execution_count,
        runtime_issue_count=runtime_issue_count,
    )


def list_automation_workers_owner(session: Session, settings: Settings, *, owner_user_id: int, limit: int, offset: int) -> AutomationWorkerListResponse:
    return _list_workers(
        session,
        settings,
        worker_ids=_accessible_worker_ids_for_owner(session, owner_user_id=owner_user_id),
        stale_only=False,
        limit=limit,
        offset=offset,
    )


def list_automation_workers_ops(session: Session, settings: Settings, *, stale_only: bool, limit: int, offset: int) -> AutomationWorkerListResponse:
    return _list_workers(session, settings, worker_ids=None, stale_only=stale_only, limit=limit, offset=offset)


def list_automation_worker_executions_owner(session: Session, *, owner_user_id: int, worker_id: int, limit: int, offset: int) -> AutomationWorkerExecutionListResponse:
    accessible = _accessible_worker_ids_for_owner(session, owner_user_id=owner_user_id)
    if worker_id not in accessible:
        raise HTTPException(status_code=404, detail="Automation worker not found.")
    limit, offset = clamp_automation_workers_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationWorkerExecution).where(AutomationWorkerExecution.worker_id == worker_id).order_by(col(AutomationWorkerExecution.created_at).desc(), col(AutomationWorkerExecution.id).desc())).all())
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row.execution_status] = status_counts.get(row.execution_status, 0) + 1
    paged = rows[offset : offset + limit]
    return AutomationWorkerExecutionListResponse(
        items=[AutomationWorkerExecutionRead.model_validate(row) for row in paged],
        total_items=len(rows),
        limit=limit,
        offset=offset,
        execution_status_counts=status_counts,
    )


def list_automation_worker_history_owner(session: Session, *, owner_user_id: int, worker_id: int, limit: int, offset: int) -> AutomationWorkerHistoryListResponse:
    accessible = _accessible_worker_ids_for_owner(session, owner_user_id=owner_user_id)
    if worker_id not in accessible:
        raise HTTPException(status_code=404, detail="Automation worker not found.")
    limit, offset = clamp_automation_workers_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationWorkerHistory).where(AutomationWorkerHistory.worker_id == worker_id).order_by(col(AutomationWorkerHistory.created_at).desc(), col(AutomationWorkerHistory.id).desc())).all())
    paged = rows[offset : offset + limit]
    return AutomationWorkerHistoryListResponse(
        items=[AutomationWorkerHistoryRead.model_validate(row) for row in paged],
        total_items=len(rows),
        limit=limit,
        offset=offset,
    )


def list_automation_worker_issues_owner(session: Session, *, owner_user_id: int, worker_id: int, limit: int, offset: int) -> AutomationWorkerIssueListResponse:
    accessible = _accessible_worker_ids_for_owner(session, owner_user_id=owner_user_id)
    if worker_id not in accessible:
        raise HTTPException(status_code=404, detail="Automation worker not found.")
    limit, offset = clamp_automation_workers_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationWorkerIssue).where(AutomationWorkerIssue.worker_id == worker_id).order_by(col(AutomationWorkerIssue.created_at).desc(), col(AutomationWorkerIssue.id).desc())).all())
    severity_counts: dict[str, int] = {}
    for row in rows:
        severity_counts[row.severity] = severity_counts.get(row.severity, 0) + 1
    paged = rows[offset : offset + limit]
    return AutomationWorkerIssueListResponse(
        items=[AutomationWorkerIssueRead.model_validate(row) for row in paged],
        total_items=len(rows),
        limit=limit,
        offset=offset,
        severity_counts=severity_counts,
    )


def list_automation_worker_issues_ops(session: Session, *, limit: int, offset: int) -> AutomationWorkerIssueListResponse:
    limit, offset = clamp_automation_workers_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationWorkerIssue).order_by(col(AutomationWorkerIssue.created_at).desc(), col(AutomationWorkerIssue.id).desc())).all())
    severity_counts: dict[str, int] = {}
    for row in rows:
        severity_counts[row.severity] = severity_counts.get(row.severity, 0) + 1
    paged = rows[offset : offset + limit]
    return AutomationWorkerIssueListResponse(
        items=[AutomationWorkerIssueRead.model_validate(row) for row in paged],
        total_items=len(rows),
        limit=limit,
        offset=offset,
        severity_counts=severity_counts,
    )
