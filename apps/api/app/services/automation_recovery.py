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
    AutomationDeadLetterJob,
    AutomationFailureEvent,
    AutomationJob,
    AutomationQueue,
    AutomationRecoveryArtifact,
    AutomationRecoveryHistory,
    AutomationRecoveryIssue,
    AutomationRecoveryRun,
    AutomationRetryPolicy,
    AutomationWorker,
    AutomationWorkerExecution,
    AutomationWorkerLease,
)
from app.schemas.automation_jobs import AutomationJobCreate
from app.schemas.automation_recovery import (
    AutomationDeadLetterListResponse,
    AutomationDeadLetterRead,
    AutomationFailureEventListResponse,
    AutomationFailureEventRead,
    AutomationRecoveryArtifactRead,
    AutomationRecoveryHistoryRead,
    AutomationRecoveryIssueListResponse,
    AutomationRecoveryIssueRead,
    AutomationRecoveryListResponse,
    AutomationRecoveryRunRead,
    AutomationRetryPolicyCreate,
    AutomationRetryPolicyRead,
)
from app.services.automation_jobs import create_automation_job, get_automation_job_owner, transition_automation_job_status

ENGINE_VERSION = "P41-04-v1"
_RETRY_MODES = {"FIXED_DELAY", "LINEAR_BACKOFF", "EXPONENTIAL_BACKOFF", "MANUAL_ONLY"}
_RECOVERY_TYPES = {"RETRY", "DEAD_LETTER_TRANSFER", "LEASE_RECOVERY", "EXECUTION_RECOVERY", "REPLAY_RECOVERY", "MANUAL_RECOVERY"}
_RECOVERY_STATUSES = {"CREATED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", "BLOCKED"}
_DEAD_LETTER_STATUSES = {"ACTIVE", "ACKNOWLEDGED", "REPLAY_PENDING", "RESOLVED", "ARCHIVED"}
_FAILURE_SEVERITIES = {"INFO", "WARNING", "ERROR", "CRITICAL"}
_ARTIFACT_MEDIA_TYPES = {".json": "application/json", ".txt": "text/plain; charset=utf-8"}


@dataclass(frozen=True)
class _HistoryDraft:
    event_type: str
    event_message: str
    metadata_json: dict[str, Any]
    from_status: str | None = None
    to_status: str | None = None


@dataclass(frozen=True)
class _IssueDraft:
    issue_type: str
    severity: str
    issue_message: str
    metadata_json: dict[str, Any]


def utc_now() -> datetime:
    from app.models.automation_recovery import utc_now as _utc_now

    return _utc_now()


def clamp_automation_recovery_pagination(*, limit: int, offset: int) -> tuple[int, int]:
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


def _resolve_recovery_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.automation_recovery_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("automation recovery storage path escapes configured root")
    return target


def _save_recovery_artifact_bytes(settings: Settings, *, relative_path: str, body: bytes) -> None:
    target = _resolve_recovery_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _recovery_artifact_path(*, recovery_type: str, recovery_run_id: int, artifact_type: str, ext: str) -> str:
    return f"automation-recovery/{recovery_type.lower()}/{recovery_run_id}/{artifact_type.lower()}{ext}".replace("\\", "/")


def _load_job(session: Session, *, job_id: int) -> tuple[AutomationJob, AutomationQueue]:
    job = session.get(AutomationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Automation job not found.")
    queue = session.get(AutomationQueue, int(job.queue_id))
    if queue is None:
        raise HTTPException(status_code=404, detail="Automation queue not found.")
    return job, queue


def _load_execution(session: Session, *, execution_id: int) -> AutomationWorkerExecution:
    execution = session.get(AutomationWorkerExecution, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Automation worker execution not found.")
    return execution


def _record_recovery_history(session: Session, *, recovery_run_id: int, draft: _HistoryDraft) -> None:
    payload = {
        "recovery_run_id": recovery_run_id,
        "event_type": draft.event_type,
        "from_status": draft.from_status,
        "to_status": draft.to_status,
        "event_message": draft.event_message,
        "metadata_json": draft.metadata_json,
    }
    session.add(
        AutomationRecoveryHistory(
            recovery_run_id=recovery_run_id,
            event_type=draft.event_type,
            from_status=draft.from_status,
            to_status=draft.to_status,
            event_message=draft.event_message,
            event_checksum=_hash_payload(payload),
            metadata_json=_json_safe(draft.metadata_json),
        )
    )


def _record_recovery_issue(session: Session, *, recovery_run_id: int, draft: _IssueDraft) -> None:
    payload = {
        "recovery_run_id": recovery_run_id,
        "issue_type": draft.issue_type,
        "severity": draft.severity,
        "issue_message": draft.issue_message,
        "metadata_json": draft.metadata_json,
    }
    session.add(
        AutomationRecoveryIssue(
            recovery_run_id=recovery_run_id,
            issue_type=draft.issue_type,
            severity=draft.severity,
            issue_message=draft.issue_message,
            issue_checksum=_hash_payload(payload),
            metadata_json=_json_safe(draft.metadata_json),
        )
    )


def _record_failure_event(
    session: Session,
    *,
    job_id: int | None,
    worker_execution_id: int | None,
    failure_type: str,
    failure_severity: str,
    failure_snapshot_json: dict[str, Any],
    metadata_json: dict[str, Any],
) -> AutomationFailureEvent:
    row = AutomationFailureEvent(
        job_id=job_id,
        worker_execution_id=worker_execution_id,
        failure_type=failure_type,
        failure_severity=failure_severity,
        failure_snapshot_json=_json_safe(failure_snapshot_json),
        failure_checksum=_hash_payload(
            {
                "job_id": job_id,
                "worker_execution_id": worker_execution_id,
                "failure_type": failure_type,
                "failure_snapshot_json": failure_snapshot_json,
            }
        ),
        metadata_json=_json_safe(metadata_json),
    )
    session.add(row)
    session.flush()
    return row


def _backoff_delay_seconds(*, policy: AutomationRetryPolicy, attempt_number: int) -> int:
    base = max(int(policy.base_delay_seconds), 0)
    max_delay = max(int(policy.max_delay_seconds), base)
    if policy.retry_mode == "MANUAL_ONLY":
        return max_delay
    if policy.retry_mode == "FIXED_DELAY":
        return min(base, max_delay)
    if policy.retry_mode == "LINEAR_BACKOFF":
        return min(base * max(attempt_number, 1), max_delay)
    if policy.retry_mode == "EXPONENTIAL_BACKOFF":
        return min(base * (2 ** max(attempt_number - 1, 0)), max_delay)
    raise HTTPException(status_code=422, detail="Invalid retry mode.")


def _recovery_rank(session: Session, *, job_id: int) -> int:
    return len(
        list(
            session.exec(
                select(AutomationRecoveryRun)
                .where(AutomationRecoveryRun.job_id == job_id)
                .order_by(col(AutomationRecoveryRun.recovery_rank), col(AutomationRecoveryRun.id))
            ).all()
        )
    ) + 1


def _build_recovery_manifest(
    *,
    job: AutomationJob,
    queue: AutomationQueue,
    recovery_type: str,
    failure_events: list[AutomationFailureEvent],
    retry_policy: AutomationRetryPolicy | None,
    dead_letter: AutomationDeadLetterJob | None,
    replay_job: dict[str, Any] | None,
    recovery_metadata: dict[str, Any],
    artifact_refs: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    manifest = {
        "engine_version": ENGINE_VERSION,
        "recovery_type": recovery_type,
        "original_job_snapshot": _json_safe(
            {
                "job_id": job.id,
                "queue_key": queue.queue_key,
                "job_key": job.job_key,
                "job_type": job.job_type,
                "job_status": job.job_status,
                "priority": job.priority,
                "deterministic_rank": job.deterministic_rank,
                "payload_snapshot_json": job.payload_snapshot_json,
                "payload_checksum": job.payload_checksum,
                "job_checksum": job.job_checksum,
                "current_attempt_count": job.current_attempt_count,
                "max_attempts": job.max_attempts,
                "source_checksum": job.source_checksum,
            }
        ),
        "failure_lineage": _json_safe(
            sorted(
                [
                    {
                        "failure_type": row.failure_type,
                        "failure_severity": row.failure_severity,
                        "failure_checksum": row.failure_checksum,
                        "failure_snapshot_json": row.failure_snapshot_json,
                    }
                    for row in failure_events
                ],
                key=lambda row: (row["failure_severity"], row["failure_type"], row["failure_checksum"]),
            )
        ),
        "retry_policy": _json_safe(retry_policy.model_dump() if retry_policy else None),
        "dead_letter_lineage": _json_safe(dead_letter.model_dump() if dead_letter else None),
        "replay_references": _json_safe(replay_job),
        "recovery_metadata": _json_safe(recovery_metadata),
        "artifacts": _json_safe(sorted(artifact_refs, key=lambda row: (row["artifact_type"], row["artifact_checksum"]))),
        "issues": _json_safe(sorted(issues, key=lambda row: (row.get("severity") or "", row.get("issue_type") or ""))),
    }
    return manifest, _hash_payload(manifest)


def create_retry_policy(session: Session, *, payload: AutomationRetryPolicyCreate) -> tuple[AutomationRetryPolicyRead, bool]:
    if str(payload.retry_mode) not in _RETRY_MODES:
        raise HTTPException(status_code=422, detail="Invalid retry mode.")
    snapshot = {
        "policy_name": payload.policy_name,
        "retry_mode": str(payload.retry_mode),
        "max_attempts": payload.max_attempts,
        "base_delay_seconds": payload.base_delay_seconds,
        "max_delay_seconds": payload.max_delay_seconds,
        "deterministic_backoff_enabled": payload.deterministic_backoff_enabled,
        "dead_letter_enabled": payload.dead_letter_enabled,
        "replay_safe": payload.replay_safe,
        "metadata_json": payload.metadata_json,
    }
    policy_checksum = _hash_payload(snapshot)
    policy_key = _hash_payload({"policy_name": payload.policy_name, "policy_checksum": policy_checksum})[:24]
    existing = session.exec(select(AutomationRetryPolicy).where(AutomationRetryPolicy.policy_checksum == policy_checksum)).first()
    if existing is not None:
        return AutomationRetryPolicyRead.model_validate(existing), False
    row = AutomationRetryPolicy(
        policy_key=policy_key,
        policy_name=payload.policy_name,
        retry_mode=str(payload.retry_mode),
        max_attempts=payload.max_attempts,
        base_delay_seconds=payload.base_delay_seconds,
        max_delay_seconds=max(payload.max_delay_seconds, payload.base_delay_seconds),
        deterministic_backoff_enabled=payload.deterministic_backoff_enabled,
        dead_letter_enabled=payload.dead_letter_enabled,
        replay_safe=payload.replay_safe,
        policy_checksum=policy_checksum,
        metadata_json=_json_safe(payload.metadata_json),
    )
    session.add(row)
    session.commit()
    return AutomationRetryPolicyRead.model_validate(row), True


def _create_recovery_run(
    session: Session,
    settings: Settings,
    *,
    job: AutomationJob,
    queue: AutomationQueue,
    recovery_type: str,
    worker_execution_id: int | None,
    retry_policy: AutomationRetryPolicy | None,
    dead_letter: AutomationDeadLetterJob | None,
    failure_events: list[AutomationFailureEvent],
    replay_job: dict[str, Any] | None,
    metadata_json: dict[str, Any],
    issue_payloads: list[dict[str, Any]] | None = None,
) -> AutomationRecoveryRun:
    if recovery_type not in _RECOVERY_TYPES:
        raise HTTPException(status_code=422, detail="Invalid recovery type.")
    rank = _recovery_rank(session, job_id=int(job.id))
    artifact_refs: list[dict[str, Any]] = []
    issues = issue_payloads or []
    manifest, checksum = _build_recovery_manifest(
        job=job,
        queue=queue,
        recovery_type=recovery_type,
        failure_events=failure_events,
        retry_policy=retry_policy,
        dead_letter=dead_letter,
        replay_job=replay_job,
        recovery_metadata=metadata_json,
        artifact_refs=artifact_refs,
        issues=issues,
    )
    existing = session.exec(select(AutomationRecoveryRun).where(AutomationRecoveryRun.recovery_checksum == checksum)).first()
    if existing is not None:
        return existing
    run = AutomationRecoveryRun(
        owner_user_id=job.owner_user_id,
        organization_id=job.organization_id,
        job_id=int(job.id),
        worker_execution_id=worker_execution_id,
        retry_policy_id=int(retry_policy.id) if retry_policy else None,
        recovery_status="RUNNING",
        recovery_type=recovery_type,
        recovery_rank=rank,
        recovery_checksum=checksum,
        recovery_manifest_json=_json_safe(manifest),
        metadata_json=_json_safe(metadata_json),
    )
    session.add(run)
    session.flush()
    _record_recovery_history(
        session,
        recovery_run_id=int(run.id),
        draft=_HistoryDraft(
            event_type="RECOVERY_CREATED",
            event_message="Automation recovery run created.",
            metadata_json={"recovery_type": recovery_type, "recovery_checksum": checksum},
            to_status="RUNNING",
        ),
    )
    artifacts = [
        ("FAILURE_SNAPSHOT", _serialize_json_artifact({"failure_events": [_json_safe(row.model_dump()) for row in failure_events]})),
        ("RECOVERY_MANIFEST", _serialize_json_artifact(manifest)),
        ("RECOVERY_DEBUG_PREVIEW", _serialize_json_artifact({"recovery_type": recovery_type, "job_id": job.id, "metadata_json": metadata_json})),
    ]
    if recovery_type == "RETRY":
        artifacts.insert(0, ("RETRY_REPORT", _serialize_json_artifact({"job_id": job.id, "metadata_json": metadata_json})))
    if recovery_type == "DEAD_LETTER_TRANSFER":
        artifacts.insert(0, ("DEAD_LETTER_EXPORT", _serialize_json_artifact({"dead_letter": _json_safe(dead_letter.model_dump()) if dead_letter else None})))
    for artifact_type, body in artifacts:
        storage_path = _recovery_artifact_path(recovery_type=recovery_type, recovery_run_id=int(run.id), artifact_type=artifact_type, ext=".json")
        _save_recovery_artifact_bytes(settings, relative_path=storage_path, body=body)
        checksum_artifact = _sha256_bytes(body)
        artifact_refs.append(
            {
                "artifact_type": artifact_type,
                "storage_path": storage_path,
                "artifact_checksum": checksum_artifact,
            }
        )
        session.add(
            AutomationRecoveryArtifact(
                recovery_run_id=int(run.id),
                artifact_type=artifact_type,
                storage_backend="filesystem",
                storage_path=storage_path,
                artifact_checksum=checksum_artifact,
                metadata_json={},
            )
        )
    for issue in issues:
        _record_recovery_issue(
            session,
            recovery_run_id=int(run.id),
            draft=_IssueDraft(
                issue_type=str(issue["issue_type"]),
                severity=str(issue["severity"]),
                issue_message=str(issue["issue_message"]),
                metadata_json=_json_safe(issue.get("metadata_json") or {}),
            ),
        )
    final_manifest, final_checksum = _build_recovery_manifest(
        job=job,
        queue=queue,
        recovery_type=recovery_type,
        failure_events=failure_events,
        retry_policy=retry_policy,
        dead_letter=dead_letter,
        replay_job=replay_job,
        recovery_metadata=metadata_json,
        artifact_refs=artifact_refs,
        issues=issues,
    )
    run.recovery_manifest_json = _json_safe(final_manifest)
    run.recovery_checksum = final_checksum
    run.recovery_status = "COMPLETED"
    run.completed_at = utc_now()
    _record_recovery_history(
        session,
        recovery_run_id=int(run.id),
        draft=_HistoryDraft(
            event_type="RECOVERY_COMPLETED",
            event_message="Automation recovery run completed.",
            metadata_json={"recovery_checksum": final_checksum},
            from_status="RUNNING",
            to_status="COMPLETED",
        ),
    )
    session.flush()
    return run


def transfer_to_dead_letter(
    session: Session,
    settings: Settings,
    *,
    job_id: int,
    dead_letter_reason: str,
    metadata_json: dict[str, Any] | None = None,
) -> AutomationRecoveryRunRead:
    job, queue = _load_job(session, job_id=job_id)
    if job.job_status not in {"FAILED", "RETRY_PENDING", "DEAD_LETTER"}:
        raise HTTPException(status_code=409, detail="Only failed or retry-pending jobs can transfer to dead-letter.")
    existing_dead_letter = session.exec(select(AutomationDeadLetterJob).where(AutomationDeadLetterJob.original_job_id == job_id)).first()
    if existing_dead_letter is None:
        existing_dead_letter = AutomationDeadLetterJob(
            original_job_id=job_id,
            dead_letter_reason=dead_letter_reason,
            dead_letter_status="ACTIVE",
            failure_count=int(job.current_attempt_count),
            source_checksum=job.source_checksum,
            dead_letter_checksum=_hash_payload(
                {
                    "original_job_id": job_id,
                    "dead_letter_reason": dead_letter_reason,
                    "failure_count": job.current_attempt_count,
                    "job_checksum": job.job_checksum,
                }
            ),
            metadata_json=_json_safe(metadata_json or {}),
        )
        session.add(existing_dead_letter)
        session.flush()
    failure = _record_failure_event(
        session,
        job_id=job_id,
        worker_execution_id=None,
        failure_type="EXECUTION_FAILURE",
        failure_severity="ERROR",
        failure_snapshot_json={"job_status": job.job_status, "job_checksum": job.job_checksum, "dead_letter_reason": dead_letter_reason},
        metadata_json=_json_safe(metadata_json or {}),
    )
    if job.job_status != "DEAD_LETTER":
        transition_automation_job_status(
            session,
            job=job,
            to_status="DEAD_LETTER",
            event_type="JOB_DEAD_LETTER",
            event_message="Automation job transferred to dead-letter.",
            metadata_json={"dead_letter_reason": dead_letter_reason},
        )
    run = _create_recovery_run(
        session,
        settings,
        job=job,
        queue=queue,
        recovery_type="DEAD_LETTER_TRANSFER",
        worker_execution_id=None,
        retry_policy=None,
        dead_letter=existing_dead_letter,
        failure_events=[failure],
        replay_job=None,
        metadata_json={"dead_letter_reason": dead_letter_reason, **_json_safe(metadata_json or {})},
        issue_payloads=[
            {
                "issue_type": "DEAD_LETTER_TRANSFERRED",
                "severity": "ERROR",
                "issue_message": dead_letter_reason,
                "metadata_json": {"dead_letter_id": existing_dead_letter.id},
            }
        ],
    )
    session.commit()
    return get_automation_recovery_run_ops(session, run_id=int(run.id))


def schedule_retry(
    session: Session,
    settings: Settings,
    *,
    job_id: int,
    retry_policy_id: int,
    metadata_json: dict[str, Any] | None = None,
) -> AutomationRecoveryRunRead:
    job, queue = _load_job(session, job_id=job_id)
    policy = session.get(AutomationRetryPolicy, retry_policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Automation retry policy not found.")
    if job.job_status not in {"FAILED", "RETRY_PENDING"}:
        raise HTTPException(status_code=409, detail="Only failed jobs can be retried.")
    next_attempt = int(job.current_attempt_count) + 1
    if next_attempt > min(policy.max_attempts, job.max_attempts):
        if policy.dead_letter_enabled:
            return transfer_to_dead_letter(session, settings, job_id=job_id, dead_letter_reason="Retry attempts exhausted.", metadata_json={"retry_policy_id": retry_policy_id, **_json_safe(metadata_json or {})})
        raise HTTPException(status_code=409, detail="Retry attempts exhausted.")
    delay_seconds = _backoff_delay_seconds(policy=policy, attempt_number=next_attempt)
    available_at = utc_now() + timedelta(seconds=delay_seconds)
    failure = _record_failure_event(
        session,
        job_id=job_id,
        worker_execution_id=None,
        failure_type="EXECUTION_FAILURE",
        failure_severity="WARNING",
        failure_snapshot_json={"job_status": job.job_status, "job_checksum": job.job_checksum, "attempt_number": next_attempt},
        metadata_json={"retry_policy_id": retry_policy_id, **_json_safe(metadata_json or {})},
    )
    if job.job_status == "FAILED":
        transition_automation_job_status(
            session,
            job=job,
            to_status="RETRY_PENDING",
            event_type="JOB_RETRY_PENDING",
            event_message="Automation job entered deterministic retry pending state.",
            metadata_json={"retry_policy_id": retry_policy_id, "delay_seconds": delay_seconds},
        )
    job.available_at = available_at
    transition_automation_job_status(
        session,
        job=job,
        to_status="AVAILABLE",
        event_type="JOB_RETRY_SCHEDULED",
        event_message="Automation job retry scheduled.",
        metadata_json={"retry_policy_id": retry_policy_id, "delay_seconds": delay_seconds, "available_at": available_at},
    )
    run = _create_recovery_run(
        session,
        settings,
        job=job,
        queue=queue,
        recovery_type="RETRY",
        worker_execution_id=None,
        retry_policy=policy,
        dead_letter=None,
        failure_events=[failure],
        replay_job=None,
        metadata_json={"retry_policy_id": retry_policy_id, "retry_delay_seconds": delay_seconds, "next_attempt_number": next_attempt, **_json_safe(metadata_json or {})},
        issue_payloads=[],
    )
    session.commit()
    return get_automation_recovery_run_ops(session, run_id=int(run.id))


def recover_expired_execution(
    session: Session,
    settings: Settings,
    *,
    execution_id: int,
    metadata_json: dict[str, Any] | None = None,
) -> AutomationRecoveryRunRead:
    execution = _load_execution(session, execution_id=execution_id)
    if execution.completed_at is not None or execution.execution_status not in {"STARTED", "RUNNING"}:
        raise HTTPException(status_code=409, detail="Only active stale executions can be recovered.")
    job, queue = _load_job(session, job_id=int(execution.job_id))
    lease = session.exec(
        select(AutomationWorkerLease)
        .where(
            AutomationWorkerLease.worker_id == execution.worker_id,
            AutomationWorkerLease.job_id == execution.job_id,
        )
        .order_by(col(AutomationWorkerLease.created_at).desc(), col(AutomationWorkerLease.id).desc())
    ).first()
    worker = session.get(AutomationWorker, int(execution.worker_id))
    if lease is None:
        raise HTTPException(status_code=409, detail="Execution has no lease lineage to recover.")
    now = utc_now()
    if lease.lease_status == "ACTIVE":
        lease_expires_at = _normalize_datetime(lease.lease_expires_at) or now
        heartbeat_at = _normalize_datetime(worker.last_heartbeat_at) if worker is not None else None
        if lease_expires_at > now and worker is not None and heartbeat_at is not None and (now - heartbeat_at).total_seconds() <= 120:
            raise HTTPException(status_code=409, detail="Execution is not stale enough for recovery.")
        lease.lease_status = "EXPIRED"
        lease.released_at = now
    execution.execution_status = "ABANDONED"
    execution.completed_at = now
    if worker is not None:
        worker.current_job_id = None
        if worker.worker_status in {"RESERVED", "RUNNING"}:
            worker.worker_status = "IDLE"
    if job.job_status in {"RESERVED", "RUNNING"}:
        transition_automation_job_status(
            session,
            job=job,
            to_status="FAILED",
            event_type="JOB_STALE_EXECUTION_RECOVERED",
            event_message="Automation job marked failed during stale execution recovery.",
            metadata_json={"execution_id": execution_id},
        )
        job.current_attempt_count += 1
        job.reservation_token = None
        job.reserved_until = None
    failure_type = "HEARTBEAT_LOSS" if worker and worker.last_heartbeat_at and (now - worker.last_heartbeat_at).total_seconds() > 120 else "LEASE_TIMEOUT"
    failure = _record_failure_event(
        session,
        job_id=int(job.id),
        worker_execution_id=int(execution.id),
        failure_type=failure_type,
        failure_severity="ERROR",
        failure_snapshot_json={"execution_id": execution.id, "lease_status": lease.lease_status, "job_status": job.job_status},
        metadata_json=_json_safe(metadata_json or {}),
    )
    run = _create_recovery_run(
        session,
        settings,
        job=job,
        queue=queue,
        recovery_type="EXECUTION_RECOVERY",
        worker_execution_id=int(execution.id),
        retry_policy=None,
        dead_letter=None,
        failure_events=[failure],
        replay_job=None,
        metadata_json={"execution_id": execution_id, **_json_safe(metadata_json or {})},
        issue_payloads=[],
    )
    session.commit()
    return get_automation_recovery_run_ops(session, run_id=int(run.id))


def replay_failed_job(
    session: Session,
    settings: Settings,
    *,
    job_id: int,
    metadata_json: dict[str, Any] | None = None,
) -> AutomationRecoveryRunRead:
    job, queue = _load_job(session, job_id=job_id)
    if job.job_status not in {"FAILED", "DEAD_LETTER"}:
        raise HTTPException(status_code=409, detail="Only failed or dead-letter jobs can be replayed for recovery.")
    if job.owner_user_id is None:
        raise HTTPException(status_code=409, detail="Replay recovery requires an owner-scoped job.")
    dead_letter = session.exec(select(AutomationDeadLetterJob).where(AutomationDeadLetterJob.original_job_id == job_id)).first()
    if dead_letter is not None:
        dead_letter.dead_letter_status = "REPLAY_PENDING"
    failure = _record_failure_event(
        session,
        job_id=int(job.id),
        worker_execution_id=None,
        failure_type="CHECKSUM_DRIFT" if job.job_status == "DEAD_LETTER" else "EXECUTION_FAILURE",
        failure_severity="WARNING",
        failure_snapshot_json={"job_status": job.job_status, "job_checksum": job.job_checksum},
        metadata_json=_json_safe(metadata_json or {}),
    )
    replay_payload = AutomationJobCreate(
        queue_key=queue.queue_key,
        queue_name=queue.queue_name,
        queue_category=queue.queue_category,
        organization_id=job.organization_id,
        parent_job_id=int(job.id),
        job_key=f"{job.job_key}:replay-recovery",
        job_type=job.job_type,
        priority=job.priority,
        payload_snapshot_json=dict(job.payload_snapshot_json),
        source_record_type="automation_job",
        source_record_id=int(job.id),
        source_checksum=job.job_checksum,
        available_at=utc_now(),
        max_attempts=job.max_attempts,
        replay_safe=job.replay_safe,
        idempotency_key=f"replay-recovery:{job.job_checksum}",
        metadata_json={"replay_recovery": True, **_json_safe(metadata_json or {})},
    )
    replay_job, _created = create_automation_job(session, settings, owner_user_id=int(job.owner_user_id), payload=replay_payload)
    if dead_letter is not None:
        dead_letter.dead_letter_status = "RESOLVED"
    run = _create_recovery_run(
        session,
        settings,
        job=job,
        queue=queue,
        recovery_type="REPLAY_RECOVERY",
        worker_execution_id=None,
        retry_policy=None,
        dead_letter=dead_letter,
        failure_events=[failure],
        replay_job={"replay_job_id": replay_job.id, "replay_job_checksum": replay_job.job_checksum},
        metadata_json={"replay_job_id": replay_job.id, **_json_safe(metadata_json or {})},
        issue_payloads=[],
    )
    session.commit()
    return get_automation_recovery_run_ops(session, run_id=int(run.id))


def _recovery_run_to_read(session: Session, *, run: AutomationRecoveryRun) -> AutomationRecoveryRunRead:
    retry_policy = session.get(AutomationRetryPolicy, int(run.retry_policy_id)) if run.retry_policy_id is not None else None
    dead_letter = session.exec(select(AutomationDeadLetterJob).where(AutomationDeadLetterJob.original_job_id == run.job_id)).first()
    failure_events = list(
        session.exec(
            select(AutomationFailureEvent)
            .where((AutomationFailureEvent.job_id == run.job_id) | (AutomationFailureEvent.worker_execution_id == run.worker_execution_id))
            .order_by(col(AutomationFailureEvent.created_at).desc(), col(AutomationFailureEvent.id).desc())
        ).all()
    )
    artifacts = list(
        session.exec(
            select(AutomationRecoveryArtifact)
            .where(AutomationRecoveryArtifact.recovery_run_id == run.id)
            .order_by(col(AutomationRecoveryArtifact.created_at), col(AutomationRecoveryArtifact.id))
        ).all()
    )
    issues = list(
        session.exec(
            select(AutomationRecoveryIssue)
            .where(AutomationRecoveryIssue.recovery_run_id == run.id)
            .order_by(col(AutomationRecoveryIssue.created_at), col(AutomationRecoveryIssue.id))
        ).all()
    )
    history = list(
        session.exec(
            select(AutomationRecoveryHistory)
            .where(AutomationRecoveryHistory.recovery_run_id == run.id)
            .order_by(col(AutomationRecoveryHistory.created_at), col(AutomationRecoveryHistory.id))
        ).all()
    )
    return AutomationRecoveryRunRead(
        **run.model_dump(),
        retry_policy=AutomationRetryPolicyRead.model_validate(retry_policy) if retry_policy else None,
        dead_letter=AutomationDeadLetterRead.model_validate(dead_letter) if dead_letter else None,
        failure_events=[AutomationFailureEventRead.model_validate(row) for row in failure_events],
        artifacts=[row.model_dump() for row in artifacts],  # type: ignore[arg-type]
        issues=[AutomationRecoveryIssueRead.model_validate(row) for row in issues],
        history=[row.model_dump() for row in history],  # type: ignore[arg-type]
    )


def _recovery_run_to_read_full(session: Session, *, run: AutomationRecoveryRun) -> AutomationRecoveryRunRead:
    retry_policy = session.get(AutomationRetryPolicy, int(run.retry_policy_id)) if run.retry_policy_id is not None else None
    dead_letter = session.exec(select(AutomationDeadLetterJob).where(AutomationDeadLetterJob.original_job_id == run.job_id)).first()
    failure_events = list(
        session.exec(
            select(AutomationFailureEvent)
            .where((AutomationFailureEvent.job_id == run.job_id) | (AutomationFailureEvent.worker_execution_id == run.worker_execution_id))
            .order_by(col(AutomationFailureEvent.created_at).desc(), col(AutomationFailureEvent.id).desc())
        ).all()
    )
    artifacts = list(session.exec(select(AutomationRecoveryArtifact).where(AutomationRecoveryArtifact.recovery_run_id == run.id).order_by(col(AutomationRecoveryArtifact.created_at), col(AutomationRecoveryArtifact.id))).all())
    issues = list(session.exec(select(AutomationRecoveryIssue).where(AutomationRecoveryIssue.recovery_run_id == run.id).order_by(col(AutomationRecoveryIssue.created_at), col(AutomationRecoveryIssue.id))).all())
    history = list(session.exec(select(AutomationRecoveryHistory).where(AutomationRecoveryHistory.recovery_run_id == run.id).order_by(col(AutomationRecoveryHistory.created_at), col(AutomationRecoveryHistory.id))).all())
    return AutomationRecoveryRunRead(
        **run.model_dump(),
        retry_policy=AutomationRetryPolicyRead.model_validate(retry_policy) if retry_policy else None,
        dead_letter=AutomationDeadLetterRead.model_validate(dead_letter) if dead_letter else None,
        failure_events=[AutomationFailureEventRead.model_validate(row) for row in failure_events],
        artifacts=[AutomationRecoveryArtifactRead.model_validate(row) for row in artifacts],
        issues=[AutomationRecoveryIssueRead.model_validate(row) for row in issues],
        history=[AutomationRecoveryHistoryRead.model_validate(row) for row in history],
    )


def get_automation_recovery_run_owner(session: Session, *, owner_user_id: int, run_id: int) -> AutomationRecoveryRunRead:
    run = session.get(AutomationRecoveryRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Automation recovery run not found.")
    job = session.get(AutomationJob, int(run.job_id))
    if job is None or int(job.owner_user_id or 0) != owner_user_id:
        raise HTTPException(status_code=404, detail="Automation recovery run not found.")
    return _recovery_run_to_read_full(session, run=run)


def get_automation_recovery_run_ops(session: Session, *, run_id: int) -> AutomationRecoveryRunRead:
    run = session.get(AutomationRecoveryRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Automation recovery run not found.")
    return _recovery_run_to_read_full(session, run=run)


def _list_recovery_runs(session: Session, *, owner_user_id: int | None, critical_only: bool, limit: int, offset: int) -> AutomationRecoveryListResponse:
    limit, offset = clamp_automation_recovery_pagination(limit=limit, offset=offset)
    runs = list(session.exec(select(AutomationRecoveryRun).order_by(col(AutomationRecoveryRun.created_at).desc(), col(AutomationRecoveryRun.id).desc())).all())
    items: list[AutomationRecoveryRunRead] = []
    for run in runs:
        job = session.get(AutomationJob, int(run.job_id))
        if owner_user_id is not None and (job is None or int(job.owner_user_id or 0) != owner_user_id):
            continue
        read = _recovery_run_to_read_full(session, run=run)
        if critical_only:
            if not any(issue.severity == "CRITICAL" for issue in read.issues) and not any(event.failure_severity == "CRITICAL" for event in read.failure_events):
                continue
        items.append(read)
    total = len(items)
    paged = items[offset : offset + limit]
    status_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    dead_letter_count = 0
    critical_failure_count = 0
    for row in items:
        status_counts[row.recovery_status] = status_counts.get(row.recovery_status, 0) + 1
        type_counts[row.recovery_type] = type_counts.get(row.recovery_type, 0) + 1
        dead_letter_count += 1 if row.dead_letter is not None else 0
        critical_failure_count += sum(1 for event in row.failure_events if event.failure_severity == "CRITICAL")
    return AutomationRecoveryListResponse(
        items=paged,
        total_items=total,
        limit=limit,
        offset=offset,
        status_counts=status_counts,
        recovery_type_counts=type_counts,
        dead_letter_count=dead_letter_count,
        critical_failure_count=critical_failure_count,
    )


def list_automation_recovery_runs_owner(session: Session, *, owner_user_id: int, limit: int, offset: int) -> AutomationRecoveryListResponse:
    return _list_recovery_runs(session, owner_user_id=owner_user_id, critical_only=False, limit=limit, offset=offset)


def list_automation_recovery_runs_ops(session: Session, *, limit: int, offset: int, critical_only: bool) -> AutomationRecoveryListResponse:
    return _list_recovery_runs(session, owner_user_id=None, critical_only=critical_only, limit=limit, offset=offset)


def list_automation_dead_letter_owner(session: Session, *, owner_user_id: int, limit: int, offset: int) -> AutomationDeadLetterListResponse:
    limit, offset = clamp_automation_recovery_pagination(limit=limit, offset=offset)
    rows = []
    for row in session.exec(select(AutomationDeadLetterJob).order_by(col(AutomationDeadLetterJob.created_at).desc(), col(AutomationDeadLetterJob.id).desc())).all():
        job = session.get(AutomationJob, int(row.original_job_id))
        if job is not None and int(job.owner_user_id or 0) == owner_user_id:
            rows.append(row)
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row.dead_letter_status] = status_counts.get(row.dead_letter_status, 0) + 1
    paged = rows[offset : offset + limit]
    return AutomationDeadLetterListResponse(items=[AutomationDeadLetterRead.model_validate(row) for row in paged], total_items=len(rows), limit=limit, offset=offset, status_counts=status_counts)


def list_automation_dead_letter_ops(session: Session, *, limit: int, offset: int) -> AutomationDeadLetterListResponse:
    limit, offset = clamp_automation_recovery_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationDeadLetterJob).order_by(col(AutomationDeadLetterJob.created_at).desc(), col(AutomationDeadLetterJob.id).desc())).all())
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row.dead_letter_status] = status_counts.get(row.dead_letter_status, 0) + 1
    paged = rows[offset : offset + limit]
    return AutomationDeadLetterListResponse(items=[AutomationDeadLetterRead.model_validate(row) for row in paged], total_items=len(rows), limit=limit, offset=offset, status_counts=status_counts)


def list_automation_failure_events_owner(session: Session, *, owner_user_id: int, limit: int, offset: int) -> AutomationFailureEventListResponse:
    limit, offset = clamp_automation_recovery_pagination(limit=limit, offset=offset)
    rows = []
    for row in session.exec(select(AutomationFailureEvent).order_by(col(AutomationFailureEvent.created_at).desc(), col(AutomationFailureEvent.id).desc())).all():
        if row.job_id is None:
            continue
        job = session.get(AutomationJob, int(row.job_id))
        if job is not None and int(job.owner_user_id or 0) == owner_user_id:
            rows.append(row)
    severity_counts: dict[str, int] = {}
    for row in rows:
        severity_counts[row.failure_severity] = severity_counts.get(row.failure_severity, 0) + 1
    paged = rows[offset : offset + limit]
    return AutomationFailureEventListResponse(items=[AutomationFailureEventRead.model_validate(row) for row in paged], total_items=len(rows), limit=limit, offset=offset, severity_counts=severity_counts)


def list_automation_failure_events_ops(session: Session, *, limit: int, offset: int) -> AutomationFailureEventListResponse:
    limit, offset = clamp_automation_recovery_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationFailureEvent).order_by(col(AutomationFailureEvent.created_at).desc(), col(AutomationFailureEvent.id).desc())).all())
    severity_counts: dict[str, int] = {}
    for row in rows:
        severity_counts[row.failure_severity] = severity_counts.get(row.failure_severity, 0) + 1
    paged = rows[offset : offset + limit]
    return AutomationFailureEventListResponse(items=[AutomationFailureEventRead.model_validate(row) for row in paged], total_items=len(rows), limit=limit, offset=offset, severity_counts=severity_counts)


def list_automation_recovery_issues_owner(session: Session, *, owner_user_id: int, limit: int, offset: int) -> AutomationRecoveryIssueListResponse:
    limit, offset = clamp_automation_recovery_pagination(limit=limit, offset=offset)
    rows = []
    for row in session.exec(select(AutomationRecoveryIssue).order_by(col(AutomationRecoveryIssue.created_at).desc(), col(AutomationRecoveryIssue.id).desc())).all():
        run = session.get(AutomationRecoveryRun, int(row.recovery_run_id))
        if run is None:
            continue
        job = session.get(AutomationJob, int(run.job_id))
        if job is not None and int(job.owner_user_id or 0) == owner_user_id:
            rows.append(row)
    severity_counts: dict[str, int] = {}
    for row in rows:
        severity_counts[row.severity] = severity_counts.get(row.severity, 0) + 1
    paged = rows[offset : offset + limit]
    return AutomationRecoveryIssueListResponse(items=[AutomationRecoveryIssueRead.model_validate(row) for row in paged], total_items=len(rows), limit=limit, offset=offset, severity_counts=severity_counts)


def list_automation_recovery_issues_ops(session: Session, *, limit: int, offset: int, critical_only: bool = False) -> AutomationRecoveryIssueListResponse:
    limit, offset = clamp_automation_recovery_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationRecoveryIssue).order_by(col(AutomationRecoveryIssue.created_at).desc(), col(AutomationRecoveryIssue.id).desc())).all())
    if critical_only:
        rows = [row for row in rows if row.severity == "CRITICAL"]
    severity_counts: dict[str, int] = {}
    for row in rows:
        severity_counts[row.severity] = severity_counts.get(row.severity, 0) + 1
    paged = rows[offset : offset + limit]
    return AutomationRecoveryIssueListResponse(items=[AutomationRecoveryIssueRead.model_validate(row) for row in paged], total_items=len(rows), limit=limit, offset=offset, severity_counts=severity_counts)
