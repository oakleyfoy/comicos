from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models import (
    AutomationBatchArtifact,
    AutomationBatchChunk,
    AutomationBatchHistory,
    AutomationBatchIssue,
    AutomationBatchRun,
    AutomationMaintenanceJob,
    AutomationMaintenanceResult,
)
from app.schemas.automation_batch import (
    AutomationBatchChunkListResponse,
    AutomationBatchChunkRead,
    AutomationBatchIssueListResponse,
    AutomationBatchIssueRead,
    AutomationBatchListResponse,
    AutomationBatchRunCreate,
    AutomationBatchRunRead,
    AutomationMaintenanceJobListResponse,
    AutomationMaintenanceJobRead,
    AutomationMaintenanceResultListResponse,
    AutomationMaintenanceResultRead,
    AutomationMaintenanceRunCreate,
)

ENGINE_VERSION = "P41-05-v1"
_BATCH_TYPES = {
    "REPLAY_SWEEP",
    "FEED_REBUILD",
    "AUTHENTICATION_RECHECK",
    "REVIEW_EXPORT",
    "INTEGRITY_AUDIT",
    "STORAGE_AUDIT",
    "CLEANUP_JOB",
    "SYSTEM_MAINTENANCE",
}
_BATCH_STATUSES = {"CREATED", "QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", "PARTIALLY_COMPLETED"}
_CHUNK_STATUSES = {"CREATED", "RESERVED", "RUNNING", "COMPLETED", "FAILED", "SKIPPED"}
_MAINTENANCE_TYPES = {
    "CHECKSUM_AUDIT",
    "LINEAGE_AUDIT",
    "STORAGE_AUDIT",
    "ARTIFACT_CLEANUP",
    "REPLAY_AUDIT",
    "DEAD_LETTER_REVIEW",
    "QUEUE_INTEGRITY_CHECK",
    "SYSTEM_HEALTH_CHECK",
}
_MAINTENANCE_STATUSES = {"CREATED", "RUNNING", "COMPLETED", "FAILED", "BLOCKED"}


@dataclass(frozen=True)
class _HistoryDraft:
    event_type: str
    event_message: str
    metadata_json: dict[str, Any]
    batch_run_id: int | None = None
    maintenance_job_id: int | None = None
    from_status: str | None = None
    to_status: str | None = None


@dataclass(frozen=True)
class _IssueDraft:
    issue_type: str
    severity: str
    issue_message: str
    metadata_json: dict[str, Any]
    batch_run_id: int | None = None
    maintenance_job_id: int | None = None


def utc_now() -> datetime:
    from app.models.automation_batch import utc_now as _utc_now

    return _utc_now()


def clamp_automation_batch_pagination(*, limit: int, offset: int) -> tuple[int, int]:
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


def _resolve_batch_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.automation_batch_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("automation batch storage path escapes configured root")
    return target


def _save_batch_artifact_bytes(settings: Settings, *, relative_path: str, body: bytes) -> None:
    target = _resolve_batch_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)


def _batch_artifact_path(*, batch_type: str, batch_run_id: int, artifact_type: str, ext: str) -> str:
    return f"automation-batch/{batch_type.lower()}/{batch_run_id}/{artifact_type.lower()}{ext}".replace("\\", "/")


def _record_batch_history(session: Session, *, draft: _HistoryDraft) -> None:
    payload = {
        "batch_run_id": draft.batch_run_id,
        "maintenance_job_id": draft.maintenance_job_id,
        "event_type": draft.event_type,
        "from_status": draft.from_status,
        "to_status": draft.to_status,
        "event_message": draft.event_message,
        "metadata_json": draft.metadata_json,
    }
    session.add(
        AutomationBatchHistory(
            batch_run_id=draft.batch_run_id,
            maintenance_job_id=draft.maintenance_job_id,
            event_type=draft.event_type,
            from_status=draft.from_status,
            to_status=draft.to_status,
            event_message=draft.event_message,
            event_checksum=_hash_payload(payload),
            metadata_json=_json_safe(draft.metadata_json),
        )
    )


def _record_batch_issue(session: Session, *, draft: _IssueDraft) -> None:
    payload = {
        "batch_run_id": draft.batch_run_id,
        "maintenance_job_id": draft.maintenance_job_id,
        "issue_type": draft.issue_type,
        "severity": draft.severity,
        "issue_message": draft.issue_message,
        "metadata_json": draft.metadata_json,
    }
    session.add(
        AutomationBatchIssue(
            batch_run_id=draft.batch_run_id,
            maintenance_job_id=draft.maintenance_job_id,
            issue_type=draft.issue_type,
            severity=draft.severity,
            issue_message=draft.issue_message,
            issue_checksum=_hash_payload(payload),
            metadata_json=_json_safe(draft.metadata_json),
        )
    )


def _partition_items(item_ids: list[int], chunk_size: int) -> list[list[int]]:
    ordered = sorted(set(int(item) for item in item_ids))
    if not ordered:
        return []
    return [ordered[index : index + chunk_size] for index in range(0, len(ordered), chunk_size)]


def partition_batch_chunks(
    *,
    batch_run_id: int,
    item_ids: list[int],
    chunk_size: int,
) -> list[dict[str, Any]]:
    partitions = _partition_items(item_ids, chunk_size)
    rows: list[dict[str, Any]] = []
    for rank, partition in enumerate(partitions, start=1):
        payload = {
            "batch_run_id": batch_run_id,
            "chunk_rank": rank,
            "partition_key": f"{partition[0]}-{partition[-1]}",
            "item_start": partition[0],
            "item_end": partition[-1],
            "item_count": len(partition),
            "item_ids": partition,
        }
        rows.append({**payload, "chunk_checksum": _hash_payload(payload)})
    return rows


def _load_batch_run(session: Session, *, batch_run_id: int) -> AutomationBatchRun:
    row = session.get(AutomationBatchRun, batch_run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Automation batch run not found.")
    return row


def _load_maintenance_job(session: Session, *, maintenance_job_id: int) -> AutomationMaintenanceJob:
    row = session.get(AutomationMaintenanceJob, maintenance_job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Automation maintenance job not found.")
    return row


def _build_batch_manifest(
    *,
    batch: AutomationBatchRun,
    chunks: list[AutomationBatchChunk],
    maintenance_jobs: list[AutomationMaintenanceJob],
    maintenance_results: list[AutomationMaintenanceResult],
    issues: list[AutomationBatchIssue],
    artifacts: list[AutomationBatchArtifact],
) -> tuple[dict[str, Any], str]:
    manifest = {
        "engine_version": ENGINE_VERSION,
        "batch_snapshot": _json_safe(
            {
                "batch_key": batch.batch_key,
                "batch_type": batch.batch_type,
                "batch_status": batch.batch_status,
                "source_scope": batch.source_scope,
                "total_item_count": batch.total_item_count,
                "completed_item_count": batch.completed_item_count,
                "failed_item_count": batch.failed_item_count,
                "metadata_json": batch.metadata_json,
            }
        ),
        "chunk_partitions": _json_safe(
            [
                {
                    "chunk_rank": row.chunk_rank,
                    "chunk_status": row.chunk_status,
                    "partition_key": row.partition_key,
                    "item_start": row.item_start,
                    "item_end": row.item_end,
                    "item_count": row.item_count,
                    "chunk_checksum": row.chunk_checksum,
                }
                for row in sorted(chunks, key=lambda chunk: (chunk.chunk_rank, chunk.id or 0))
            ]
        ),
        "maintenance_lineage": _json_safe(
            [
                {
                    "maintenance_key": job.maintenance_key,
                    "maintenance_type": job.maintenance_type,
                    "maintenance_status": job.maintenance_status,
                    "maintenance_checksum": job.maintenance_checksum,
                }
                for job in sorted(maintenance_jobs, key=lambda row: (row.maintenance_type, row.created_at, row.id or 0))
            ]
        ),
        "maintenance_results": _json_safe(
            [
                {
                    "maintenance_job_id": row.maintenance_job_id,
                    "result_type": row.result_type,
                    "result_status": row.result_status,
                    "result_checksum": row.result_checksum,
                }
                for row in sorted(maintenance_results, key=lambda result: (result.maintenance_job_id, result.result_type, result.id or 0))
            ]
        ),
        "issues": _json_safe(
            [
                {
                    "issue_type": row.issue_type,
                    "severity": row.severity,
                    "issue_checksum": row.issue_checksum,
                }
                for row in sorted(issues, key=lambda issue: (issue.severity, issue.issue_type, issue.id or 0))
            ]
        ),
        "artifacts": _json_safe(
            [
                {
                    "artifact_type": row.artifact_type,
                    "storage_path": row.storage_path,
                    "artifact_checksum": row.artifact_checksum,
                }
                for row in sorted(artifacts, key=lambda artifact: (artifact.artifact_type, artifact.storage_path))
            ]
        ),
        "replay_metadata": _json_safe({"replay_safe": batch.replay_safe}),
    }
    return manifest, _hash_payload(manifest)


def _maintenance_job_to_read(
    session: Session,
    *,
    job: AutomationMaintenanceJob,
) -> AutomationMaintenanceJobRead:
    results = list(
        session.exec(
            select(AutomationMaintenanceResult)
            .where(AutomationMaintenanceResult.maintenance_job_id == job.id)
            .order_by(col(AutomationMaintenanceResult.created_at), col(AutomationMaintenanceResult.id))
        ).all()
    )
    base = AutomationMaintenanceJobRead.model_validate(job)
    return base.model_copy(update={"results": [AutomationMaintenanceResultRead.model_validate(result) for result in results]})


def _batch_to_read(session: Session, *, batch: AutomationBatchRun) -> AutomationBatchRunRead:
    chunks = list(session.exec(select(AutomationBatchChunk).where(AutomationBatchChunk.batch_run_id == batch.id).order_by(col(AutomationBatchChunk.chunk_rank), col(AutomationBatchChunk.id))).all())
    maintenance_jobs = list(session.exec(select(AutomationMaintenanceJob).where(AutomationMaintenanceJob.owner_user_id == batch.owner_user_id).order_by(col(AutomationMaintenanceJob.created_at).desc(), col(AutomationMaintenanceJob.id).desc())).all())
    maintenance_results = list(session.exec(select(AutomationMaintenanceResult).where(col(AutomationMaintenanceResult.maintenance_job_id).in_([job.id for job in maintenance_jobs] or [-1])).order_by(col(AutomationMaintenanceResult.created_at), col(AutomationMaintenanceResult.id))).all())
    result_map: dict[int, list[AutomationMaintenanceResultRead]] = {}
    for row in maintenance_results:
        result_map.setdefault(int(row.maintenance_job_id), []).append(AutomationMaintenanceResultRead.model_validate(row))
    job_reads = [AutomationMaintenanceJobRead.model_validate(job).model_copy(update={"results": result_map.get(int(job.id), [])}) for job in maintenance_jobs]
    maintenance_job_ids = [int(job.id) for job in maintenance_jobs]
    artifacts = list(
        session.exec(
            select(AutomationBatchArtifact)
            .where(
                (AutomationBatchArtifact.batch_run_id == batch.id)
                | col(AutomationBatchArtifact.maintenance_job_id).in_(maintenance_job_ids or [-1])
            )
            .order_by(col(AutomationBatchArtifact.created_at), col(AutomationBatchArtifact.id))
        ).all()
    )
    issues = list(
        session.exec(
            select(AutomationBatchIssue)
            .where(
                (AutomationBatchIssue.batch_run_id == batch.id)
                | col(AutomationBatchIssue.maintenance_job_id).in_(maintenance_job_ids or [-1])
            )
            .order_by(col(AutomationBatchIssue.created_at), col(AutomationBatchIssue.id))
        ).all()
    )
    history = list(
        session.exec(
            select(AutomationBatchHistory)
            .where(
                (AutomationBatchHistory.batch_run_id == batch.id)
                | col(AutomationBatchHistory.maintenance_job_id).in_(maintenance_job_ids or [-1])
            )
            .order_by(col(AutomationBatchHistory.created_at), col(AutomationBatchHistory.id))
        ).all()
    )
    return AutomationBatchRunRead(
        **batch.model_dump(),
        chunks=[AutomationBatchChunkRead.model_validate(row) for row in chunks],
        maintenance_jobs=job_reads,
        artifacts=[artifact.model_dump() for artifact in artifacts],  # type: ignore[arg-type]
        issues=[AutomationBatchIssueRead.model_validate(row) for row in issues],
        history=[entry.model_dump() for entry in history],  # type: ignore[arg-type]
    )


def create_batch_run(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: AutomationBatchRunCreate,
) -> tuple[AutomationBatchRunRead, bool]:
    if str(payload.batch_type) not in _BATCH_TYPES:
        raise HTTPException(status_code=422, detail="Invalid automation batch type.")
    item_ids = sorted(set(int(item) for item in payload.item_ids))
    effective_owner_user_id = int(payload.owner_user_id or owner_user_id)
    snapshot = {
        "owner_user_id": effective_owner_user_id,
        "batch_type": str(payload.batch_type),
        "source_scope": payload.source_scope,
        "item_ids": item_ids,
        "chunk_size": payload.chunk_size,
        "replay_safe": payload.replay_safe,
        "metadata_json": payload.metadata_json,
    }
    batch_checksum = _hash_payload(snapshot)
    batch_key = _hash_payload({"batch_type": payload.batch_type, "source_scope": payload.source_scope, "batch_checksum": batch_checksum})[:24]
    existing = session.exec(
        select(AutomationBatchRun).where(
            AutomationBatchRun.owner_user_id == effective_owner_user_id,
            AutomationBatchRun.batch_checksum == batch_checksum,
        )
    ).first()
    if existing is not None:
        return _batch_to_read(session, batch=existing), False
    row = AutomationBatchRun(
        owner_user_id=effective_owner_user_id,
        organization_id=None,
        batch_key=batch_key,
        batch_type=str(payload.batch_type),
        batch_status="QUEUED",
        source_scope=payload.source_scope,
        deterministic_partitioning_enabled=True,
        replay_safe=payload.replay_safe,
        total_item_count=len(item_ids),
        completed_item_count=0,
        failed_item_count=0,
        batch_checksum=batch_checksum,
        manifest_json={},
        metadata_json=_json_safe({**payload.metadata_json, "item_ids": item_ids, "chunk_size": payload.chunk_size}),
    )
    session.add(row)
    session.flush()
    for chunk in partition_batch_chunks(batch_run_id=int(row.id), item_ids=item_ids, chunk_size=payload.chunk_size):
        session.add(
            AutomationBatchChunk(
                batch_run_id=int(row.id),
                chunk_rank=int(chunk["chunk_rank"]),
                chunk_status="CREATED",
                partition_key=str(chunk["partition_key"]),
                item_start=int(chunk["item_start"]),
                item_end=int(chunk["item_end"]),
                item_count=int(chunk["item_count"]),
                chunk_checksum=str(chunk["chunk_checksum"]),
                metadata_json={"item_ids": chunk["item_ids"]},
            )
        )
    _record_batch_history(
        session,
        draft=_HistoryDraft(
            batch_run_id=int(row.id),
            event_type="BATCH_CREATED",
            event_message="Automation batch run created.",
            metadata_json={"batch_checksum": batch_checksum, "chunk_size": payload.chunk_size},
            to_status="QUEUED",
        ),
    )
    session.commit()
    return _batch_to_read(session, batch=row), True


def _execute_batch_chunk(
    session: Session,
    *,
    chunk: AutomationBatchChunk,
    fail_chunk_ranks: set[int],
) -> None:
    chunk.chunk_status = "RUNNING"
    chunk.started_at = utc_now()
    if chunk.chunk_rank in fail_chunk_ranks:
        chunk.chunk_status = "FAILED"
        chunk.completed_at = utc_now()
        return
    chunk.chunk_status = "COMPLETED"
    chunk.completed_at = utc_now()


def _write_batch_artifacts(
    session: Session,
    settings: Settings,
    *,
    batch: AutomationBatchRun,
    chunks: list[AutomationBatchChunk],
    maintenance_jobs: list[AutomationMaintenanceJob],
    maintenance_results: list[AutomationMaintenanceResult],
    issues: list[AutomationBatchIssue],
) -> list[AutomationBatchArtifact]:
    existing = list(session.exec(select(AutomationBatchArtifact).where(AutomationBatchArtifact.batch_run_id == batch.id).order_by(col(AutomationBatchArtifact.created_at), col(AutomationBatchArtifact.id))).all())
    manifest, checksum = _build_batch_manifest(
        batch=batch,
        chunks=chunks,
        maintenance_jobs=maintenance_jobs,
        maintenance_results=maintenance_results,
        issues=issues,
        artifacts=existing,
    )
    payloads = [
        ("BATCH_REPORT", _serialize_json_artifact({"batch_id": batch.id, "batch_status": batch.batch_status, "completed_item_count": batch.completed_item_count, "failed_item_count": batch.failed_item_count})),
        ("CHUNK_EXPORT", _serialize_json_artifact({"chunks": [_json_safe(chunk.model_dump()) for chunk in chunks]})),
        ("BATCH_MANIFEST", _serialize_json_artifact(manifest)),
        ("BATCH_DEBUG_PREVIEW", _serialize_json_artifact({"batch_key": batch.batch_key, "batch_type": batch.batch_type, "batch_checksum": checksum})),
    ]
    rows: list[AutomationBatchArtifact] = []
    for artifact_type, body in payloads:
        storage_path = _batch_artifact_path(batch_type=batch.batch_type, batch_run_id=int(batch.id), artifact_type=artifact_type, ext=".json")
        artifact_checksum = _sha256_bytes(body)
        artifact = session.exec(
            select(AutomationBatchArtifact).where(
                AutomationBatchArtifact.batch_run_id == batch.id,
                AutomationBatchArtifact.artifact_type == artifact_type,
                AutomationBatchArtifact.artifact_checksum == artifact_checksum,
            )
        ).first()
        if artifact is None:
            _save_batch_artifact_bytes(settings, relative_path=storage_path, body=body)
            artifact = AutomationBatchArtifact(
                batch_run_id=int(batch.id),
                maintenance_job_id=None,
                artifact_type=artifact_type,
                storage_backend="filesystem",
                storage_path=storage_path,
                artifact_checksum=artifact_checksum,
                metadata_json={},
            )
            session.add(artifact)
            session.flush()
        rows.append(artifact)
    batch.manifest_json = manifest
    batch.batch_checksum = checksum
    return rows


def finalize_batch_run(
    session: Session,
    settings: Settings,
    *,
    batch_run_id: int,
) -> AutomationBatchRunRead:
    batch = _load_batch_run(session, batch_run_id=batch_run_id)
    chunks = list(session.exec(select(AutomationBatchChunk).where(AutomationBatchChunk.batch_run_id == batch.id).order_by(col(AutomationBatchChunk.chunk_rank), col(AutomationBatchChunk.id))).all())
    batch.completed_item_count = sum(chunk.item_count for chunk in chunks if chunk.chunk_status == "COMPLETED")
    batch.failed_item_count = sum(chunk.item_count for chunk in chunks if chunk.chunk_status == "FAILED")
    if batch.failed_item_count and batch.completed_item_count:
        batch.batch_status = "PARTIALLY_COMPLETED"
    elif batch.failed_item_count:
        batch.batch_status = "FAILED"
    else:
        batch.batch_status = "COMPLETED"
    batch.completed_at = utc_now()
    maintenance_jobs = list(session.exec(select(AutomationMaintenanceJob).where(AutomationMaintenanceJob.owner_user_id == batch.owner_user_id)).all())
    maintenance_results = list(session.exec(select(AutomationMaintenanceResult).where(col(AutomationMaintenanceResult.maintenance_job_id).in_([job.id for job in maintenance_jobs] or [-1]))).all())
    issues = list(session.exec(select(AutomationBatchIssue).where(AutomationBatchIssue.batch_run_id == batch.id)).all())
    _write_batch_artifacts(session, settings, batch=batch, chunks=chunks, maintenance_jobs=maintenance_jobs, maintenance_results=maintenance_results, issues=issues)
    _record_batch_history(
        session,
        draft=_HistoryDraft(
            batch_run_id=int(batch.id),
            event_type="BATCH_FINALIZED",
            event_message="Automation batch run finalized.",
            metadata_json={"completed_item_count": batch.completed_item_count, "failed_item_count": batch.failed_item_count},
            from_status="RUNNING",
            to_status=batch.batch_status,
        ),
    )
    session.commit()
    return _batch_to_read(session, batch=batch)


def execute_batch_run(
    session: Session,
    settings: Settings,
    *,
    batch_run_id: int,
) -> AutomationBatchRunRead:
    batch = _load_batch_run(session, batch_run_id=batch_run_id)
    if batch.batch_status not in {"QUEUED", "CREATED", "RUNNING"}:
        raise HTTPException(status_code=409, detail="Batch run cannot be executed from its current state.")
    batch.batch_status = "RUNNING"
    chunks = list(session.exec(select(AutomationBatchChunk).where(AutomationBatchChunk.batch_run_id == batch.id).order_by(col(AutomationBatchChunk.chunk_rank), col(AutomationBatchChunk.id))).all())
    fail_chunk_ranks = {int(rank) for rank in batch.metadata_json.get("force_failed_chunk_ranks", []) if isinstance(rank, int)}
    for chunk in chunks:
        _execute_batch_chunk(session, chunk=chunk, fail_chunk_ranks=fail_chunk_ranks)
    if batch.batch_type in {"INTEGRITY_AUDIT", "STORAGE_AUDIT"}:
        execute_maintenance_job(
            session,
            settings,
            owner_user_id=int(batch.owner_user_id or 0),
            payload=AutomationMaintenanceRunCreate(
                maintenance_type="STORAGE_AUDIT" if batch.batch_type == "STORAGE_AUDIT" else "CHECKSUM_AUDIT",
                maintenance_scope=batch.source_scope,
                replay_safe=batch.replay_safe,
                metadata_json={"batch_run_id": batch_run_id, **_json_safe(batch.metadata_json)},
            ),
        )
    if fail_chunk_ranks:
        _record_batch_issue(
            session,
            draft=_IssueDraft(
                batch_run_id=int(batch.id),
                issue_type="BATCH_EXECUTION_FAILURE",
                severity="ERROR",
                issue_message="One or more batch chunks failed during execution.",
                metadata_json={"failed_chunk_ranks": sorted(fail_chunk_ranks)},
            ),
        )
    session.commit()
    return finalize_batch_run(session, settings, batch_run_id=batch_run_id)


def execute_maintenance_job(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: AutomationMaintenanceRunCreate,
) -> AutomationMaintenanceJobRead:
    if str(payload.maintenance_type) not in _MAINTENANCE_TYPES:
        raise HTTPException(status_code=422, detail="Invalid maintenance type.")
    effective_owner_user_id = int(payload.owner_user_id or owner_user_id)
    snapshot = {
        "owner_user_id": effective_owner_user_id,
        "maintenance_type": str(payload.maintenance_type),
        "maintenance_scope": payload.maintenance_scope,
        "replay_safe": payload.replay_safe,
        "metadata_json": payload.metadata_json,
    }
    checksum = _hash_payload(snapshot)
    maintenance_key = _hash_payload({"maintenance_type": payload.maintenance_type, "maintenance_scope": payload.maintenance_scope, "checksum": checksum})[:24]
    existing = session.exec(
        select(AutomationMaintenanceJob).where(
            AutomationMaintenanceJob.owner_user_id == effective_owner_user_id,
            AutomationMaintenanceJob.maintenance_checksum == checksum,
        )
    ).first()
    if existing is not None:
        return _maintenance_job_to_read(session, job=existing)
    job = AutomationMaintenanceJob(
        owner_user_id=effective_owner_user_id,
        organization_id=None,
        maintenance_key=maintenance_key,
        maintenance_type=str(payload.maintenance_type),
        maintenance_status="RUNNING",
        maintenance_scope=payload.maintenance_scope,
        replay_safe=payload.replay_safe,
        maintenance_checksum=checksum,
        metadata_json=_json_safe(payload.metadata_json),
    )
    session.add(job)
    session.flush()
    result_rows: list[AutomationMaintenanceResult] = []
    warnings = payload.metadata_json.get("orphan_artifact_paths", []) if isinstance(payload.metadata_json.get("orphan_artifact_paths"), list) else []
    status = "PASS"
    if warnings:
        status = "WARNING"
    if payload.metadata_json.get("force_fail"):
        status = "FAIL"
    result_payload = {
        "maintenance_type": payload.maintenance_type,
        "maintenance_scope": payload.maintenance_scope,
        "orphan_artifact_count": len(warnings),
        "queue_warning_count": int(payload.metadata_json.get("queue_warning_count", 0) or 0),
    }
    result = AutomationMaintenanceResult(
        maintenance_job_id=int(job.id),
        result_type="STORAGE_RESULT" if payload.maintenance_type == "STORAGE_AUDIT" else "AUDIT_RESULT",
        result_status=status,
        result_snapshot_json=_json_safe(result_payload),
        result_checksum=_hash_payload(result_payload),
        metadata_json=_json_safe(payload.metadata_json),
    )
    session.add(result)
    session.flush()
    result_rows.append(result)
    if warnings:
        _record_batch_issue(
            session,
            draft=_IssueDraft(
                maintenance_job_id=int(job.id),
                issue_type="ORPHAN_ARTIFACT_DETECTED",
                severity="WARNING",
                issue_message="Orphan artifacts were detected during maintenance.",
                metadata_json={"orphan_artifact_paths": warnings},
            ),
        )
    if status == "FAIL":
        _record_batch_issue(
            session,
            draft=_IssueDraft(
                maintenance_job_id=int(job.id),
                issue_type="MAINTENANCE_FAILURE",
                severity="ERROR",
                issue_message="Maintenance execution reported a failure.",
                metadata_json=_json_safe(payload.metadata_json),
            ),
        )
        job.maintenance_status = "FAILED"
    else:
        job.maintenance_status = "COMPLETED"
    job.completed_at = utc_now()
    _record_batch_history(
        session,
        draft=_HistoryDraft(
            maintenance_job_id=int(job.id),
            event_type="MAINTENANCE_COMPLETED",
            event_message="Automation maintenance job completed.",
            metadata_json={"result_status": status},
            from_status="RUNNING",
            to_status=job.maintenance_status,
        ),
    )
    artifact_payloads = [
        ("MAINTENANCE_REPORT", _serialize_json_artifact({"maintenance_job_id": job.id, "result_status": status, "results": [row.model_dump() for row in result_rows]})),
        ("STORAGE_AUDIT_EXPORT" if payload.maintenance_type == "STORAGE_AUDIT" else "BATCH_DEBUG_PREVIEW", _serialize_json_artifact(result_payload)),
    ]
    for artifact_type, body in artifact_payloads:
        storage_path = _batch_artifact_path(batch_type=payload.maintenance_type, batch_run_id=int(job.id), artifact_type=artifact_type, ext=".json")
        _save_batch_artifact_bytes(settings, relative_path=storage_path, body=body)
        session.add(
            AutomationBatchArtifact(
                batch_run_id=None,
                maintenance_job_id=int(job.id),
                artifact_type=artifact_type,
                storage_backend="filesystem",
                storage_path=storage_path,
                artifact_checksum=_sha256_bytes(body),
                metadata_json={},
            )
        )
    session.commit()
    return _maintenance_job_to_read(session, job=job)


def get_automation_batch_run_owner(session: Session, *, owner_user_id: int, batch_run_id: int) -> AutomationBatchRunRead:
    row = _load_batch_run(session, batch_run_id=batch_run_id)
    if int(row.owner_user_id or 0) != owner_user_id:
        raise HTTPException(status_code=404, detail="Automation batch run not found.")
    return _batch_to_read(session, batch=row)


def get_automation_batch_run_ops(session: Session, *, batch_run_id: int) -> AutomationBatchRunRead:
    return _batch_to_read(session, batch=_load_batch_run(session, batch_run_id=batch_run_id))


def list_automation_batch_runs_owner(session: Session, *, owner_user_id: int, limit: int, offset: int) -> AutomationBatchListResponse:
    limit, offset = clamp_automation_batch_pagination(limit=limit, offset=offset)
    rows = [row for row in session.exec(select(AutomationBatchRun).order_by(col(AutomationBatchRun.created_at).desc(), col(AutomationBatchRun.id).desc())).all() if int(row.owner_user_id or 0) == owner_user_id]
    items = [_batch_to_read(session, batch=row) for row in rows[offset : offset + limit]]
    status_counts: dict[str, int] = {}
    batch_type_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row.batch_status] = status_counts.get(row.batch_status, 0) + 1
        batch_type_counts[row.batch_type] = batch_type_counts.get(row.batch_type, 0) + 1
    return AutomationBatchListResponse(
        items=items,
        total_items=len(rows),
        limit=limit,
        offset=offset,
        status_counts=status_counts,
        batch_type_counts=batch_type_counts,
        failed_batch_count=status_counts.get("FAILED", 0) + status_counts.get("PARTIALLY_COMPLETED", 0),
        maintenance_job_count=len([job for job in session.exec(select(AutomationMaintenanceJob).where(AutomationMaintenanceJob.owner_user_id == owner_user_id)).all()]),
        integrity_audit_count=len([job for job in session.exec(select(AutomationMaintenanceJob).where(AutomationMaintenanceJob.owner_user_id == owner_user_id)).all() if job.maintenance_type in {"CHECKSUM_AUDIT", "LINEAGE_AUDIT", "QUEUE_INTEGRITY_CHECK"}]),
    )


def list_automation_batch_runs_ops(session: Session, *, limit: int, offset: int, failed_only: bool = False) -> AutomationBatchListResponse:
    limit, offset = clamp_automation_batch_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationBatchRun).order_by(col(AutomationBatchRun.created_at).desc(), col(AutomationBatchRun.id).desc())).all())
    if failed_only:
        rows = [row for row in rows if row.batch_status in {"FAILED", "PARTIALLY_COMPLETED"}]
    items = [_batch_to_read(session, batch=row) for row in rows[offset : offset + limit]]
    status_counts: dict[str, int] = {}
    batch_type_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row.batch_status] = status_counts.get(row.batch_status, 0) + 1
        batch_type_counts[row.batch_type] = batch_type_counts.get(row.batch_type, 0) + 1
    maintenance_jobs = list(session.exec(select(AutomationMaintenanceJob)).all())
    return AutomationBatchListResponse(
        items=items,
        total_items=len(rows),
        limit=limit,
        offset=offset,
        status_counts=status_counts,
        batch_type_counts=batch_type_counts,
        failed_batch_count=status_counts.get("FAILED", 0) + status_counts.get("PARTIALLY_COMPLETED", 0),
        maintenance_job_count=len(maintenance_jobs),
        integrity_audit_count=len([job for job in maintenance_jobs if job.maintenance_type in {"CHECKSUM_AUDIT", "LINEAGE_AUDIT", "QUEUE_INTEGRITY_CHECK"}]),
    )


def list_automation_batch_chunks_owner(session: Session, *, owner_user_id: int, batch_run_id: int, limit: int, offset: int) -> AutomationBatchChunkListResponse:
    batch = _load_batch_run(session, batch_run_id=batch_run_id)
    if int(batch.owner_user_id or 0) != owner_user_id:
        raise HTTPException(status_code=404, detail="Automation batch run not found.")
    limit, offset = clamp_automation_batch_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationBatchChunk).where(AutomationBatchChunk.batch_run_id == batch_run_id).order_by(col(AutomationBatchChunk.chunk_rank), col(AutomationBatchChunk.id))).all())
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row.chunk_status] = status_counts.get(row.chunk_status, 0) + 1
    paged = rows[offset : offset + limit]
    return AutomationBatchChunkListResponse(items=[AutomationBatchChunkRead.model_validate(row) for row in paged], total_items=len(rows), limit=limit, offset=offset, status_counts=status_counts)


def list_automation_maintenance_jobs_owner(session: Session, *, owner_user_id: int, limit: int, offset: int, maintenance_types: set[str] | None = None) -> AutomationMaintenanceJobListResponse:
    limit, offset = clamp_automation_batch_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationMaintenanceJob).where(AutomationMaintenanceJob.owner_user_id == owner_user_id).order_by(col(AutomationMaintenanceJob.created_at).desc(), col(AutomationMaintenanceJob.id).desc())).all())
    if maintenance_types:
        rows = [row for row in rows if row.maintenance_type in maintenance_types]
    status_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    job_reads: list[AutomationMaintenanceJobRead] = []
    for row in rows:
        status_counts[row.maintenance_status] = status_counts.get(row.maintenance_status, 0) + 1
        type_counts[row.maintenance_type] = type_counts.get(row.maintenance_type, 0) + 1
    for row in rows[offset : offset + limit]:
        job_reads.append(_maintenance_job_to_read(session, job=row))
    return AutomationMaintenanceJobListResponse(items=job_reads, total_items=len(rows), limit=limit, offset=offset, status_counts=status_counts, maintenance_type_counts=type_counts)


def list_automation_maintenance_jobs_ops(session: Session, *, limit: int, offset: int, maintenance_types: set[str] | None = None) -> AutomationMaintenanceJobListResponse:
    limit, offset = clamp_automation_batch_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationMaintenanceJob).order_by(col(AutomationMaintenanceJob.created_at).desc(), col(AutomationMaintenanceJob.id).desc())).all())
    if maintenance_types:
        rows = [row for row in rows if row.maintenance_type in maintenance_types]
    status_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    job_reads: list[AutomationMaintenanceJobRead] = []
    for row in rows:
        status_counts[row.maintenance_status] = status_counts.get(row.maintenance_status, 0) + 1
        type_counts[row.maintenance_type] = type_counts.get(row.maintenance_type, 0) + 1
    for row in rows[offset : offset + limit]:
        job_reads.append(_maintenance_job_to_read(session, job=row))
    return AutomationMaintenanceJobListResponse(items=job_reads, total_items=len(rows), limit=limit, offset=offset, status_counts=status_counts, maintenance_type_counts=type_counts)


def list_automation_maintenance_results_owner(session: Session, *, owner_user_id: int, limit: int, offset: int) -> AutomationMaintenanceResultListResponse:
    maintenance_jobs = [row.id for row in session.exec(select(AutomationMaintenanceJob).where(AutomationMaintenanceJob.owner_user_id == owner_user_id)).all()]
    limit, offset = clamp_automation_batch_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationMaintenanceResult).where(col(AutomationMaintenanceResult.maintenance_job_id).in_(maintenance_jobs or [-1])).order_by(col(AutomationMaintenanceResult.created_at).desc(), col(AutomationMaintenanceResult.id).desc())).all())
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row.result_status] = status_counts.get(row.result_status, 0) + 1
    return AutomationMaintenanceResultListResponse(items=[AutomationMaintenanceResultRead.model_validate(row) for row in rows[offset : offset + limit]], total_items=len(rows), limit=limit, offset=offset, status_counts=status_counts)


def list_automation_batch_issues_owner(session: Session, *, owner_user_id: int, limit: int, offset: int) -> AutomationBatchIssueListResponse:
    owner_batch_ids = [row.id for row in session.exec(select(AutomationBatchRun).where(AutomationBatchRun.owner_user_id == owner_user_id)).all()]
    owner_maintenance_ids = [row.id for row in session.exec(select(AutomationMaintenanceJob).where(AutomationMaintenanceJob.owner_user_id == owner_user_id)).all()]
    limit, offset = clamp_automation_batch_pagination(limit=limit, offset=offset)
    rows = [
        row
        for row in session.exec(select(AutomationBatchIssue).order_by(col(AutomationBatchIssue.created_at).desc(), col(AutomationBatchIssue.id).desc())).all()
        if (row.batch_run_id in owner_batch_ids) or (row.maintenance_job_id in owner_maintenance_ids)
    ]
    severity_counts: dict[str, int] = {}
    for row in rows:
        severity_counts[row.severity] = severity_counts.get(row.severity, 0) + 1
    return AutomationBatchIssueListResponse(items=[AutomationBatchIssueRead.model_validate(row) for row in rows[offset : offset + limit]], total_items=len(rows), limit=limit, offset=offset, severity_counts=severity_counts)


def list_automation_batch_issues_ops(session: Session, *, limit: int, offset: int, issue_types: set[str] | None = None) -> AutomationBatchIssueListResponse:
    limit, offset = clamp_automation_batch_pagination(limit=limit, offset=offset)
    rows = list(session.exec(select(AutomationBatchIssue).order_by(col(AutomationBatchIssue.created_at).desc(), col(AutomationBatchIssue.id).desc())).all())
    if issue_types:
        rows = [row for row in rows if row.issue_type in issue_types]
    severity_counts: dict[str, int] = {}
    for row in rows:
        severity_counts[row.severity] = severity_counts.get(row.severity, 0) + 1
    return AutomationBatchIssueListResponse(items=[AutomationBatchIssueRead.model_validate(row) for row in rows[offset : offset + limit]], total_items=len(rows), limit=limit, offset=offset, severity_counts=severity_counts)
