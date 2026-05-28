from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models import (
    ScanAuthenticationArtifact,
    ScanAuthenticationFinding,
    ScanAuthenticationHistory,
    ScanAuthenticationIssue,
    ScanAuthenticationRun,
    ScanAuthenticationSignal,
    ScanBoundaryHistory,
    ScanBoundaryIssue,
    ScanBoundaryRun,
    ScanCornerEdgeHistory,
    ScanCornerEdgeIssue,
    ScanCornerEdgeRun,
    ScanDefectAggregationHistory,
    ScanDefectAggregationIssue,
    ScanDefectAggregationRun,
    ScanDefectHistory,
    ScanDefectIssue,
    ScanDefectRun,
    ScanGradingAssistanceFinding,
    ScanGradingAssistanceHistory,
    ScanGradingAssistanceIssue,
    ScanGradingAssistanceRun,
    ScanHistoricalComparisonDelta,
    ScanHistoricalComparisonHistory,
    ScanHistoricalComparisonIssue,
    ScanHistoricalComparisonRun,
    ScanImage,
    ScanIngestionBatch,
    ScanIngestionEvent,
    ScanIntelligenceFeedArtifact,
    ScanIntelligenceFeedEvent,
    ScanIntelligenceFeedHistory,
    ScanIntelligenceFeedIssue,
    ScanIntelligenceFeedRun,
    ScanNormalizationHistory,
    ScanNormalizationIssue,
    ScanNormalizationRun,
    ScanOcrHistory,
    ScanOcrIssue,
    ScanOcrRun,
    ScanReconciliationDecision,
    ScanReconciliationHistory,
    ScanReconciliationIssue,
    ScanReconciliationRun,
    ScanReviewDecision,
    ScanReviewEvidenceAction,
    ScanReviewHistory,
    ScanReviewIssue,
    ScanReviewNote,
    ScanReviewSession,
    ScanSpineTickHistory,
    ScanSpineTickIssue,
    ScanSpineTickRun,
    ScanStructuralDamageHistory,
    ScanStructuralDamageIssue,
    ScanStructuralDamageRun,
    ScanSurfaceDefectHistory,
    ScanSurfaceDefectIssue,
    ScanSurfaceDefectRun,
    ScanUploadSession,
    ScanVisualEvidenceHistory,
    ScanVisualEvidenceIssue,
    ScanVisualEvidenceItem,
    ScanVisualEvidencePackage,
    ScanVisualEvidenceRun,
)
from app.schemas.scan_intelligence_feed import (
    ScanIntelligenceFeedArtifactRead,
    ScanIntelligenceFeedEventListResponse,
    ScanIntelligenceFeedEventRead,
    ScanIntelligenceFeedHistoryRead,
    ScanIntelligenceFeedIssueListResponse,
    ScanIntelligenceFeedIssueRead,
    ScanIntelligenceFeedRunCreate,
    ScanIntelligenceFeedRunDetail,
    ScanIntelligenceFeedRunListResponse,
    ScanIntelligenceFeedRunRead,
)

ENGINE_VERSION = "P41-17-v1"

_CATEGORY_RANK = {
    "INGESTION": 1,
    "NORMALIZATION": 2,
    "BOUNDARY": 3,
    "OCR": 4,
    "RECONCILIATION": 5,
    "DEFECT_FOUNDATION": 6,
    "SPINE": 7,
    "CORNER_EDGE": 8,
    "SURFACE": 9,
    "STRUCTURAL": 10,
    "AGGREGATION": 11,
    "GRADING_ASSISTANCE": 12,
    "VISUAL_EVIDENCE": 13,
    "REVIEW": 14,
    "HISTORICAL_COMPARISON": 15,
    "AUTHENTICATION": 16,
    "OPS": 17,
    "SYSTEM": 18,
}
_SEVERITY_RANK = {
    "SUCCESS": 1,
    "INFO": 2,
    "WARNING": 3,
    "REVIEW_REQUIRED": 4,
    "ERROR": 5,
}
_SOURCE_SYSTEM_RANK = {
    "SCAN_INGESTION": 1,
    "SCAN_NORMALIZATION": 2,
    "SCAN_BOUNDARY": 3,
    "SCAN_OCR": 4,
    "SCAN_RECONCILIATION": 5,
    "SCAN_DEFECTS": 6,
    "SCAN_SPINE_TICKS": 7,
    "SCAN_CORNER_EDGES": 8,
    "SCAN_SURFACE_DEFECTS": 9,
    "SCAN_STRUCTURAL_DAMAGE": 10,
    "SCAN_DEFECT_AGGREGATION": 11,
    "SCAN_GRADING_ASSISTANCE": 12,
    "SCAN_VISUAL_EVIDENCE": 13,
    "SCAN_REVIEW": 14,
    "SCAN_HISTORICAL_COMPARISON": 15,
    "SCAN_AUTHENTICATION": 16,
    "SCAN_FEED": 17,
}
_MIME_BY_EXT = {
    ".json": "application/json",
    ".txt": "text/plain; charset=utf-8",
}


@dataclass(frozen=True)
class _EventDraft:
    event_category: str
    event_type: str
    severity: str
    source_system: str
    event_occurred_at: datetime
    source_record_id: int | None
    source_checksum: str | None
    lineage_checksum: str | None
    event_payload_json: dict[str, Any]
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _IssueDraft:
    issue_type: str
    severity: str
    source_system: str
    source_record_id: int | None
    issue_message: str
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _ArtifactDraft:
    artifact_type: str
    body: bytes
    metadata_json: dict[str, Any]
    ext: str


@dataclass(frozen=True)
class _HistoryDraft:
    event_type: str
    event_message: str
    metadata_json: dict[str, Any]


@dataclass
class _FeedContext:
    scan_image: ScanImage
    upload_session: ScanUploadSession | None
    ingestion_batch: ScanIngestionBatch | None
    ingestion_events: list[ScanIngestionEvent]
    normalization_run: ScanNormalizationRun | None
    boundary_run: ScanBoundaryRun | None
    ocr_run: ScanOcrRun | None
    reconciliation_run: ScanReconciliationRun | None
    defect_run: ScanDefectRun | None
    spine_tick_run: ScanSpineTickRun | None
    corner_edge_run: ScanCornerEdgeRun | None
    surface_defect_run: ScanSurfaceDefectRun | None
    structural_damage_run: ScanStructuralDamageRun | None
    defect_aggregation_run: ScanDefectAggregationRun | None
    grading_assistance_run: ScanGradingAssistanceRun | None
    visual_evidence_run: ScanVisualEvidenceRun | None
    review_session: ScanReviewSession | None
    historical_comparison_run: ScanHistoricalComparisonRun | None
    authentication_run: ScanAuthenticationRun | None


@dataclass(frozen=True)
class _RunSpec:
    category: str
    source_system: str
    status_field: str
    checksum_field: str
    issue_model: type | None
    issue_fk_field: str | None
    history_model: type | None
    history_fk_field: str | None
    engine_field: str | None = "engine_version"
    source_checksum_field: str | None = "source_checksum"


_RUN_SPECS: dict[str, _RunSpec] = {
    "normalization_run": _RunSpec("NORMALIZATION", "SCAN_NORMALIZATION", "normalization_status", "normalization_checksum", ScanNormalizationIssue, "scan_normalization_run_id", ScanNormalizationHistory, "scan_normalization_run_id", None, "source_sha256_checksum"),
    "boundary_run": _RunSpec("BOUNDARY", "SCAN_BOUNDARY", "boundary_status", "boundary_checksum", ScanBoundaryIssue, "boundary_run_id", ScanBoundaryHistory, "boundary_run_id"),
    "ocr_run": _RunSpec("OCR", "SCAN_OCR", "ocr_status", "ocr_checksum", ScanOcrIssue, "ocr_run_id", ScanOcrHistory, "ocr_run_id"),
    "reconciliation_run": _RunSpec("RECONCILIATION", "SCAN_RECONCILIATION", "reconciliation_status", "reconciliation_checksum", ScanReconciliationIssue, "reconciliation_run_id", ScanReconciliationHistory, "reconciliation_run_id", "reconciliation_engine_version"),
    "defect_run": _RunSpec("DEFECT_FOUNDATION", "SCAN_DEFECTS", "defect_status", "defect_checksum", ScanDefectIssue, "defect_run_id", ScanDefectHistory, "defect_run_id"),
    "spine_tick_run": _RunSpec("SPINE", "SCAN_SPINE_TICKS", "detection_status", "spine_tick_checksum", ScanSpineTickIssue, "spine_tick_run_id", ScanSpineTickHistory, "spine_tick_run_id"),
    "corner_edge_run": _RunSpec("CORNER_EDGE", "SCAN_CORNER_EDGES", "detection_status", "corner_edge_checksum", ScanCornerEdgeIssue, "corner_edge_run_id", ScanCornerEdgeHistory, "corner_edge_run_id"),
    "surface_defect_run": _RunSpec("SURFACE", "SCAN_SURFACE_DEFECTS", "detection_status", "surface_defect_checksum", ScanSurfaceDefectIssue, "surface_defect_run_id", ScanSurfaceDefectHistory, "surface_defect_run_id"),
    "structural_damage_run": _RunSpec("STRUCTURAL", "SCAN_STRUCTURAL_DAMAGE", "detection_status", "structural_damage_checksum", ScanStructuralDamageIssue, "structural_damage_run_id", ScanStructuralDamageHistory, "structural_damage_run_id"),
    "defect_aggregation_run": _RunSpec("AGGREGATION", "SCAN_DEFECT_AGGREGATION", "aggregation_status", "aggregation_checksum", ScanDefectAggregationIssue, "aggregation_run_id", ScanDefectAggregationHistory, "aggregation_run_id"),
    "grading_assistance_run": _RunSpec("GRADING_ASSISTANCE", "SCAN_GRADING_ASSISTANCE", "assistance_status", "grading_assistance_checksum", ScanGradingAssistanceIssue, "grading_assistance_run_id", ScanGradingAssistanceHistory, "grading_assistance_run_id", "engine_version"),
    "visual_evidence_run": _RunSpec("VISUAL_EVIDENCE", "SCAN_VISUAL_EVIDENCE", "evidence_status", "visual_evidence_checksum", ScanVisualEvidenceIssue, "visual_evidence_run_id", ScanVisualEvidenceHistory, "visual_evidence_run_id"),
    "review_session": _RunSpec("REVIEW", "SCAN_REVIEW", "review_status", "review_checksum", ScanReviewIssue, "review_session_id", ScanReviewHistory, "review_session_id", None, "snapshot_checksum"),
    "historical_comparison_run": _RunSpec("HISTORICAL_COMPARISON", "SCAN_HISTORICAL_COMPARISON", "comparison_status", "historical_comparison_checksum", ScanHistoricalComparisonIssue, "comparison_run_id", ScanHistoricalComparisonHistory, "comparison_run_id"),
    "authentication_run": _RunSpec("AUTHENTICATION", "SCAN_AUTHENTICATION", "authentication_status", "authentication_checksum", ScanAuthenticationIssue, "authentication_run_id", ScanAuthenticationHistory, "authentication_run_id"),
}


def utc_now() -> datetime:
    from app.models.scan_intelligence_feed import utc_now as _utc_now

    return _utc_now()


def clamp_scan_intelligence_feed_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value).replace("\\", "/")
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
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


def _resolve_feed_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.scan_intelligence_feed_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("scan intelligence feed storage path escapes configured root")
    return target


def _artifact_storage_path(*, owner_user_id: int, scan_image_id: int, feed_run_id: int, artifact_type: str, ext: str) -> str:
    return f"scan-intelligence-feed/{owner_user_id}/{scan_image_id}/{feed_run_id}/{artifact_type.lower()}{ext}".replace("\\", "/")


def _save_artifact_bytes(settings: Settings, *, relative_path: str, body: bytes) -> None:
    target = _resolve_feed_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)


def _load_artifact_payload(settings: Settings, row: ScanIntelligenceFeedArtifact) -> tuple[str | None, str | None, str | None]:
    path = _resolve_feed_storage_path(settings, row.storage_path)
    try:
        body = path.read_bytes()
    except OSError:
        return None, None, None
    media_type = _MIME_BY_EXT.get(path.suffix.lower(), "application/octet-stream")
    try:
        text_preview = body.decode("utf-8")
    except UnicodeDecodeError:
        return media_type, None, base64.b64encode(body).decode("ascii")
    return media_type, text_preview[:20000], None


def _normalize_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _severity_from_status(status: str | None) -> str:
    normalized = (status or "").upper()
    if any(token in normalized for token in ("FAIL", "ERROR")):
        return "ERROR"
    if "REVIEW" in normalized:
        return "REVIEW_REQUIRED"
    if any(token in normalized for token in ("WARN", "INCONCLUSIVE", "MISSING")):
        return "WARNING"
    if any(token in normalized for token in ("COMPLETE", "PROCESSED", "APPROVED", "CONFIRMED", "READY", "MATCHED", "SUPPORTIVE", "ACTIVE")):
        return "SUCCESS"
    return "INFO"


def _severity_from_text(event_type: str, message: str) -> str:
    joined = f"{event_type} {message}".upper()
    if any(token in joined for token in ("FAIL", "ERROR")):
        return "ERROR"
    if "REVIEW" in joined:
        return "REVIEW_REQUIRED"
    if any(token in joined for token in ("WARN", "CONFLICT", "MISSING", "INCONCLUSIVE")):
        return "WARNING"
    if any(token in joined for token in ("COMPLETE", "SUCCESS", "CREATED", "MATCHED")):
        return "SUCCESS"
    return "INFO"


def _row_metadata(row) -> dict[str, Any]:
    metadata = getattr(row, "metadata_json", None)
    if metadata is None:
        metadata = getattr(row, "detail_json", None)
    return dict(metadata or {})


def _issue_message(row) -> str:
    if getattr(row, "issue_message", None):
        return str(row.issue_message)
    status = getattr(row, "normalization_status", None)
    metric = getattr(row, "metric_value", None)
    fragments = [str(getattr(row, "issue_type", "ISSUE"))]
    if status:
        fragments.append(str(status))
    if metric:
        fragments.append(str(metric))
    details = _row_metadata(row)
    if details:
        fragments.append(json.dumps(_json_safe(details), sort_keys=True))
    return " | ".join(fragments)


def _history_message(row) -> str:
    if getattr(row, "event_message", None):
        return str(row.event_message)
    if getattr(row, "notes", None):
        return str(row.notes)
    if getattr(row, "stage_name", None):
        return f"{row.stage_name} {row.event_type}"
    return str(getattr(row, "event_type", "HISTORY"))


def _history_checksum(row) -> str:
    checksum = getattr(row, "event_checksum", None) or getattr(row, "to_checksum", None) or getattr(row, "from_checksum", None)
    if checksum:
        return str(checksum)
    return _hash_payload({"event_type": getattr(row, "event_type", None), "message": _history_message(row), "metadata_json": _row_metadata(row)})


def _event_key(draft: _EventDraft) -> str:
    seed = {
        "event_category": draft.event_category,
        "event_type": draft.event_type,
        "severity": draft.severity,
        "source_system": draft.source_system,
        "event_occurred_at": _normalize_datetime(draft.event_occurred_at),
        "source_record_id": draft.source_record_id,
        "source_checksum": draft.source_checksum,
        "lineage_checksum": draft.lineage_checksum,
        "event_payload_json": draft.event_payload_json,
        "metadata_json": draft.metadata_json,
    }
    digest = _hash_payload(seed)
    return f"{draft.source_system}:{draft.event_type}:{draft.source_record_id or 0}:{digest[:32]}"


def _select_latest_for_scan(
    session: Session,
    *,
    model: type,
    owner_user_id: int,
    scan_image_id: int,
    override_id: int | None = None,
):
    stmt = select(model).where(model.owner_user_id == owner_user_id, model.scan_image_id == scan_image_id)
    if override_id is not None:
        stmt = stmt.where(model.id == override_id)
    return session.exec(stmt.order_by(col(model.id).desc())).first()


def _load_context(
    session: Session,
    *,
    owner_user_id: int,
    payload: ScanIntelligenceFeedRunCreate,
) -> _FeedContext:
    scan_image = session.get(ScanImage, payload.scan_image_id)
    if scan_image is None or int(scan_image.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan image not found.")

    ingestion_batch = session.get(ScanIngestionBatch, int(scan_image.ingestion_batch_id))
    upload_session = session.get(ScanUploadSession, int(ingestion_batch.upload_session_id)) if ingestion_batch else None
    ingestion_events = list(
        session.exec(
            select(ScanIngestionEvent)
            .where(
                ScanIngestionEvent.ingestion_batch_id == scan_image.ingestion_batch_id,
                (ScanIngestionEvent.scan_image_id == scan_image.id) | (ScanIngestionEvent.scan_image_id.is_(None)),
            )
            .order_by(col(ScanIngestionEvent.created_at), col(ScanIngestionEvent.id))
        ).all()
    )

    normalization_run = _select_latest_for_scan(session, model=ScanNormalizationRun, owner_user_id=owner_user_id, scan_image_id=payload.scan_image_id)
    boundary_run = _select_latest_for_scan(session, model=ScanBoundaryRun, owner_user_id=owner_user_id, scan_image_id=payload.scan_image_id)
    ocr_run = _select_latest_for_scan(session, model=ScanOcrRun, owner_user_id=owner_user_id, scan_image_id=payload.scan_image_id)
    reconciliation_run = _select_latest_for_scan(
        session,
        model=ScanReconciliationRun,
        owner_user_id=owner_user_id,
        scan_image_id=payload.scan_image_id,
        override_id=payload.reconciliation_run_id,
    )
    defect_run = _select_latest_for_scan(session, model=ScanDefectRun, owner_user_id=owner_user_id, scan_image_id=payload.scan_image_id)
    spine_tick_run = _select_latest_for_scan(session, model=ScanSpineTickRun, owner_user_id=owner_user_id, scan_image_id=payload.scan_image_id)
    corner_edge_run = _select_latest_for_scan(session, model=ScanCornerEdgeRun, owner_user_id=owner_user_id, scan_image_id=payload.scan_image_id)
    surface_defect_run = _select_latest_for_scan(session, model=ScanSurfaceDefectRun, owner_user_id=owner_user_id, scan_image_id=payload.scan_image_id)
    structural_damage_run = _select_latest_for_scan(session, model=ScanStructuralDamageRun, owner_user_id=owner_user_id, scan_image_id=payload.scan_image_id)
    defect_aggregation_run = _select_latest_for_scan(session, model=ScanDefectAggregationRun, owner_user_id=owner_user_id, scan_image_id=payload.scan_image_id)
    grading_assistance_run = _select_latest_for_scan(
        session,
        model=ScanGradingAssistanceRun,
        owner_user_id=owner_user_id,
        scan_image_id=payload.scan_image_id,
        override_id=payload.grading_assistance_run_id,
    )
    visual_evidence_run = _select_latest_for_scan(
        session,
        model=ScanVisualEvidenceRun,
        owner_user_id=owner_user_id,
        scan_image_id=payload.scan_image_id,
        override_id=payload.visual_evidence_run_id,
    )
    review_session = _select_latest_for_scan(
        session,
        model=ScanReviewSession,
        owner_user_id=owner_user_id,
        scan_image_id=payload.scan_image_id,
        override_id=payload.review_session_id,
    )
    historical_comparison_run = _select_latest_for_scan(
        session,
        model=ScanHistoricalComparisonRun,
        owner_user_id=owner_user_id,
        scan_image_id=payload.scan_image_id,
        override_id=payload.historical_comparison_run_id,
    )
    authentication_run = _select_latest_for_scan(
        session,
        model=ScanAuthenticationRun,
        owner_user_id=owner_user_id,
        scan_image_id=payload.scan_image_id,
        override_id=payload.authentication_run_id,
    )

    return _FeedContext(
        scan_image=scan_image,
        upload_session=upload_session,
        ingestion_batch=ingestion_batch,
        ingestion_events=ingestion_events,
        normalization_run=normalization_run,
        boundary_run=boundary_run,
        ocr_run=ocr_run,
        reconciliation_run=reconciliation_run,
        defect_run=defect_run,
        spine_tick_run=spine_tick_run,
        corner_edge_run=corner_edge_run,
        surface_defect_run=surface_defect_run,
        structural_damage_run=structural_damage_run,
        defect_aggregation_run=defect_aggregation_run,
        grading_assistance_run=grading_assistance_run,
        visual_evidence_run=visual_evidence_run,
        review_session=review_session,
        historical_comparison_run=historical_comparison_run,
        authentication_run=authentication_run,
    )


def _collect_ingestion(ctx: _FeedContext) -> tuple[list[_EventDraft], list[_IssueDraft]]:
    events: list[_EventDraft] = []
    issues: list[_IssueDraft] = []
    scan_image = ctx.scan_image
    if ctx.upload_session is not None:
        events.append(
            _EventDraft(
                event_category="INGESTION",
                event_type="UPLOAD_SESSION",
                severity="SUCCESS" if ctx.upload_session.completed_at else "INFO",
                source_system="SCAN_INGESTION",
                event_occurred_at=ctx.upload_session.completed_at or ctx.upload_session.started_at,
                source_record_id=ctx.upload_session.id,
                source_checksum=ctx.upload_session.session_checksum,
                lineage_checksum=scan_image.sha256_checksum,
                event_payload_json={
                    "upload_source": ctx.upload_session.upload_source,
                    "total_files": ctx.upload_session.total_files,
                    "successful_files": ctx.upload_session.successful_files,
                    "failed_files": ctx.upload_session.failed_files,
                },
                metadata_json={},
            )
        )
    if ctx.ingestion_batch is not None:
        events.append(
            _EventDraft(
                event_category="INGESTION",
                event_type="INGESTION_BATCH",
                severity=_severity_from_status(ctx.ingestion_batch.batch_status),
                source_system="SCAN_INGESTION",
                event_occurred_at=ctx.ingestion_batch.completed_at or ctx.ingestion_batch.created_at,
                source_record_id=ctx.ingestion_batch.id,
                source_checksum=ctx.ingestion_batch.ingestion_checksum,
                lineage_checksum=scan_image.sha256_checksum,
                event_payload_json={
                    "source_type": ctx.ingestion_batch.source_type,
                    "batch_status": ctx.ingestion_batch.batch_status,
                    "image_count": ctx.ingestion_batch.image_count,
                    "failed_count": ctx.ingestion_batch.failed_count,
                    "duplicate_count": ctx.ingestion_batch.duplicate_count,
                },
                metadata_json={},
            )
        )
    events.append(
        _EventDraft(
            event_category="INGESTION",
            event_type="SCAN_IMAGE_REGISTERED",
            severity=_severity_from_status(scan_image.processing_status),
            source_system="SCAN_INGESTION",
            event_occurred_at=scan_image.created_at,
            source_record_id=scan_image.id,
            source_checksum=scan_image.sha256_checksum,
            lineage_checksum=scan_image.sha256_checksum,
            event_payload_json={
                "original_filename": scan_image.original_filename,
                "processing_status": scan_image.processing_status,
                "mime_type": scan_image.mime_type,
                "file_size_bytes": scan_image.file_size_bytes,
                "is_duplicate": scan_image.is_duplicate,
            },
            metadata_json={},
        )
    )
    for row in ctx.ingestion_events:
        events.append(
            _EventDraft(
                event_category="INGESTION",
                event_type=row.event_type,
                severity=_severity_from_text(row.event_type, ""),
                source_system="SCAN_INGESTION",
                event_occurred_at=row.created_at,
                source_record_id=row.id,
                source_checksum=ctx.ingestion_batch.ingestion_checksum if ctx.ingestion_batch else scan_image.sha256_checksum,
                lineage_checksum=scan_image.sha256_checksum,
                event_payload_json=dict(row.metadata_json or {}),
                metadata_json={"scan_image_id": row.scan_image_id},
            )
        )
    if scan_image.failure_reason:
        issues.append(
            _IssueDraft(
                issue_type="INGESTION_FAILURE",
                severity="ERROR",
                source_system="SCAN_INGESTION",
                source_record_id=scan_image.id,
                issue_message=scan_image.failure_reason,
                metadata_json={},
            )
        )
    return events, issues


def _collect_run_family(
    session: Session,
    *,
    run,
    spec: _RunSpec,
) -> tuple[list[_EventDraft], list[_IssueDraft]]:
    if run is None:
        return [], []
    events: list[_EventDraft] = []
    issues: list[_IssueDraft] = []
    status = str(getattr(run, spec.status_field))
    checksum = str(getattr(run, spec.checksum_field))
    source_checksum = str(getattr(run, spec.source_checksum_field)) if spec.source_checksum_field and getattr(run, spec.source_checksum_field, None) else None
    occurred_at = getattr(run, "completed_at", None) or getattr(run, "updated_at", None) or getattr(run, "created_at")
    payload: dict[str, Any] = {
        "run_id": run.id,
        "status": status,
        "checksum": checksum,
        "source_checksum": source_checksum,
    }
    if spec.engine_field and getattr(run, spec.engine_field, None):
        payload["engine_version"] = getattr(run, spec.engine_field)
    events.append(
        _EventDraft(
            event_category=spec.category,
            event_type=f"{spec.category}_RUN",
            severity=_severity_from_status(status),
            source_system=spec.source_system,
            event_occurred_at=occurred_at,
            source_record_id=run.id,
            source_checksum=checksum,
            lineage_checksum=source_checksum or checksum,
            event_payload_json=payload,
            metadata_json={},
        )
    )
    if spec.issue_model is not None and spec.issue_fk_field is not None:
        issue_rows = list(
            session.exec(
                select(spec.issue_model)
                .where(getattr(spec.issue_model, spec.issue_fk_field) == run.id)
                .order_by(col(spec.issue_model.created_at), col(spec.issue_model.id))
            ).all()
        )
        for row in issue_rows:
            issues.append(
                _IssueDraft(
                    issue_type=str(row.issue_type),
                    severity=str(row.severity),
                    source_system=spec.source_system,
                    source_record_id=int(row.id),
                    issue_message=_issue_message(row),
                    metadata_json=_row_metadata(row),
                )
            )
            events.append(
                _EventDraft(
                    event_category=spec.category,
                    event_type=f"{spec.category}_ISSUE_{row.issue_type}",
                    severity=str(row.severity),
                    source_system=spec.source_system,
                    event_occurred_at=row.created_at,
                    source_record_id=row.id,
                    source_checksum=checksum,
                    lineage_checksum=source_checksum or checksum,
                    event_payload_json={"issue_message": _issue_message(row)},
                    metadata_json=_row_metadata(row),
                )
            )
    if spec.history_model is not None and spec.history_fk_field is not None:
        history_rows = list(
            session.exec(
                select(spec.history_model)
                .where(getattr(spec.history_model, spec.history_fk_field) == run.id)
                .order_by(col(spec.history_model.created_at), col(spec.history_model.id))
            ).all()
        )
        for row in history_rows:
            history_message = _history_message(row)
            events.append(
                _EventDraft(
                    event_category=spec.category,
                    event_type=f"{spec.category}_HISTORY_{row.event_type}",
                    severity=_severity_from_text(str(row.event_type), history_message),
                    source_system=spec.source_system,
                    event_occurred_at=row.created_at,
                    source_record_id=row.id,
                    source_checksum=_history_checksum(row),
                    lineage_checksum=source_checksum or checksum,
                    event_payload_json={"event_message": history_message},
                    metadata_json=_row_metadata(row),
                )
            )
    return events, issues


def _collect_reconciliation_detail(session: Session, *, run: ScanReconciliationRun | None) -> list[_EventDraft]:
    if run is None:
        return []
    events: list[_EventDraft] = []
    decision = session.exec(
        select(ScanReconciliationDecision)
        .where(ScanReconciliationDecision.reconciliation_run_id == run.id)
        .order_by(col(ScanReconciliationDecision.created_at).desc(), col(ScanReconciliationDecision.id).desc())
    ).first()
    if decision is not None:
        events.append(
            _EventDraft(
                event_category="RECONCILIATION",
                event_type="RECONCILIATION_DECISION",
                severity=_severity_from_status(decision.decision_status),
                source_system="SCAN_RECONCILIATION",
                event_occurred_at=decision.created_at,
                source_record_id=decision.id,
                source_checksum=run.reconciliation_checksum,
                lineage_checksum=run.source_checksum,
                event_payload_json={
                    "decision_status": decision.decision_status,
                    "final_confidence_score": decision.final_confidence_score,
                    "decision_reason": decision.decision_reason,
                },
                metadata_json=dict(decision.metadata_json or {}),
            )
        )
    return events


def _collect_grading_detail(session: Session, *, run: ScanGradingAssistanceRun | None) -> list[_EventDraft]:
    if run is None:
        return []
    events: list[_EventDraft] = []
    rows = list(
        session.exec(
            select(ScanGradingAssistanceFinding)
            .where(ScanGradingAssistanceFinding.grading_assistance_run_id == run.id)
            .order_by(col(ScanGradingAssistanceFinding.created_at), col(ScanGradingAssistanceFinding.id))
        ).all()
    )
    for row in rows:
        severity = _severity_from_status(row.finding_severity_hint)
        events.append(
            _EventDraft(
                event_category="GRADING_ASSISTANCE",
                event_type=f"GRADING_FINDING_{row.finding_type}",
                severity=severity,
                source_system="SCAN_GRADING_ASSISTANCE",
                event_occurred_at=row.created_at,
                source_record_id=row.id,
                source_checksum=run.grading_assistance_checksum,
                lineage_checksum=run.source_checksum,
                event_payload_json={
                    "grade_pressure_hint": row.grade_pressure_hint,
                    "confidence_score": row.confidence_score,
                    "finding_text": row.finding_text,
                },
                metadata_json=dict(row.metadata_json or {}),
            )
        )
    return events


def _collect_visual_detail(session: Session, *, run: ScanVisualEvidenceRun | None) -> list[_EventDraft]:
    if run is None:
        return []
    events: list[_EventDraft] = []
    packages = list(
        session.exec(
            select(ScanVisualEvidencePackage)
            .where(ScanVisualEvidencePackage.visual_evidence_run_id == run.id)
            .order_by(col(ScanVisualEvidencePackage.created_at), col(ScanVisualEvidencePackage.id))
        ).all()
    )
    for pkg in packages:
        events.append(
            _EventDraft(
                event_category="VISUAL_EVIDENCE",
                event_type=f"VISUAL_PACKAGE_{pkg.package_type}",
                severity=_severity_from_status(pkg.package_status),
                source_system="SCAN_VISUAL_EVIDENCE",
                event_occurred_at=pkg.created_at,
                source_record_id=pkg.id,
                source_checksum=run.visual_evidence_checksum,
                lineage_checksum=run.source_checksum,
                event_payload_json={
                    "package_status": pkg.package_status,
                    "package_title": pkg.package_title,
                    "package_summary": pkg.package_summary,
                },
                metadata_json=dict(pkg.metadata_json or {}),
            )
        )
    items = list(
        session.exec(
            select(ScanVisualEvidenceItem)
            .where(ScanVisualEvidenceItem.visual_evidence_run_id == run.id)
            .order_by(col(ScanVisualEvidenceItem.created_at), col(ScanVisualEvidenceItem.id))
        ).all()
    )
    for row in items:
        events.append(
            _EventDraft(
                event_category="VISUAL_EVIDENCE",
                event_type=f"VISUAL_ITEM_{row.item_type}",
                severity=_severity_from_status(row.severity_hint or "INFO"),
                source_system="SCAN_VISUAL_EVIDENCE",
                event_occurred_at=row.created_at,
                source_record_id=row.id,
                source_checksum=run.visual_evidence_checksum,
                lineage_checksum=run.source_checksum,
                event_payload_json={
                    "item_title": row.item_title,
                    "item_summary": row.item_summary,
                    "confidence_score": row.confidence_score,
                    "source_system": row.source_system,
                },
                metadata_json=dict(row.metadata_json or {}),
            )
        )
    return events


def _collect_review_detail(session: Session, *, run: ScanReviewSession | None) -> list[_EventDraft]:
    if run is None:
        return []
    events: list[_EventDraft] = []
    decisions = list(
        session.exec(
            select(ScanReviewDecision)
            .where(ScanReviewDecision.review_session_id == run.id)
            .order_by(col(ScanReviewDecision.created_at), col(ScanReviewDecision.id))
        ).all()
    )
    for row in decisions:
        events.append(
            _EventDraft(
                event_category="REVIEW",
                event_type=f"REVIEW_DECISION_{row.decision_type}",
                severity=_severity_from_status(row.decision_status),
                source_system="SCAN_REVIEW",
                event_occurred_at=row.created_at,
                source_record_id=row.id,
                source_checksum=run.review_checksum,
                lineage_checksum=run.snapshot_checksum,
                event_payload_json={
                    "decision_status": row.decision_status,
                    "decision_value": row.decision_value,
                    "reason_text": row.reason_text,
                    "confidence_score": row.confidence_score,
                },
                metadata_json=dict(row.metadata_json or {}),
            )
        )
    actions = list(
        session.exec(
            select(ScanReviewEvidenceAction)
            .where(ScanReviewEvidenceAction.review_session_id == run.id)
            .order_by(col(ScanReviewEvidenceAction.created_at), col(ScanReviewEvidenceAction.id))
        ).all()
    )
    for row in actions:
        events.append(
            _EventDraft(
                event_category="REVIEW",
                event_type=f"REVIEW_ACTION_{row.action_type}",
                severity=_severity_from_status(row.action_status),
                source_system="SCAN_REVIEW",
                event_occurred_at=row.created_at,
                source_record_id=row.id,
                source_checksum=run.review_checksum,
                lineage_checksum=run.snapshot_checksum,
                event_payload_json={
                    "action_status": row.action_status,
                    "reason_text": row.reason_text,
                    "source_system": row.source_system,
                    "source_record_id": row.source_record_id,
                },
                metadata_json=dict(row.metadata_json or {}),
            )
        )
    notes = list(
        session.exec(
            select(ScanReviewNote)
            .where(ScanReviewNote.review_session_id == run.id)
            .order_by(col(ScanReviewNote.created_at), col(ScanReviewNote.id))
        ).all()
    )
    for row in notes:
        events.append(
            _EventDraft(
                event_category="REVIEW",
                event_type=f"REVIEW_NOTE_{row.note_type}",
                severity="INFO",
                source_system="SCAN_REVIEW",
                event_occurred_at=row.created_at,
                source_record_id=row.id,
                source_checksum=run.review_checksum,
                lineage_checksum=run.snapshot_checksum,
                event_payload_json={"note_text": row.note_text},
                metadata_json=dict(row.metadata_json or {}),
            )
        )
    return events


def _collect_historical_detail(session: Session, *, run: ScanHistoricalComparisonRun | None) -> list[_EventDraft]:
    if run is None:
        return []
    events: list[_EventDraft] = []
    rows = list(
        session.exec(
            select(ScanHistoricalComparisonDelta)
            .where(ScanHistoricalComparisonDelta.comparison_run_id == run.id)
            .order_by(col(ScanHistoricalComparisonDelta.created_at), col(ScanHistoricalComparisonDelta.id))
        ).all()
    )
    for row in rows:
        severity = _severity_from_status(row.severity_hint)
        events.append(
            _EventDraft(
                event_category="HISTORICAL_COMPARISON",
                event_type=f"HISTORICAL_DELTA_{row.delta_type}",
                severity=severity,
                source_system="SCAN_HISTORICAL_COMPARISON",
                event_occurred_at=row.created_at,
                source_record_id=row.id,
                source_checksum=run.historical_comparison_checksum,
                lineage_checksum=run.source_checksum,
                event_payload_json={
                    "delta_category": row.delta_category,
                    "delta_direction": row.delta_direction,
                    "confidence_score": row.confidence_score,
                    "region_type": row.region_type,
                },
                metadata_json=dict(row.metadata_json or {}),
            )
        )
    return events


def _collect_authentication_detail(session: Session, *, run: ScanAuthenticationRun | None) -> list[_EventDraft]:
    if run is None:
        return []
    events: list[_EventDraft] = []
    signals = list(
        session.exec(
            select(ScanAuthenticationSignal)
            .where(ScanAuthenticationSignal.authentication_run_id == run.id)
            .order_by(col(ScanAuthenticationSignal.signal_rank), col(ScanAuthenticationSignal.id))
        ).all()
    )
    for row in signals:
        events.append(
            _EventDraft(
                event_category="AUTHENTICATION",
                event_type=f"AUTH_SIGNAL_{row.signal_type}",
                severity=_severity_from_status(row.signal_status),
                source_system="SCAN_AUTHENTICATION",
                event_occurred_at=row.created_at,
                source_record_id=row.id,
                source_checksum=run.authentication_checksum,
                lineage_checksum=run.source_checksum,
                event_payload_json={
                    "signal_category": row.signal_category,
                    "signal_status": row.signal_status,
                    "confidence_score": row.confidence_score,
                },
                metadata_json=dict(row.metadata_json or {}),
            )
        )
    findings = list(
        session.exec(
            select(ScanAuthenticationFinding)
            .where(ScanAuthenticationFinding.authentication_run_id == run.id)
            .order_by(col(ScanAuthenticationFinding.finding_rank), col(ScanAuthenticationFinding.id))
        ).all()
    )
    for row in findings:
        events.append(
            _EventDraft(
                event_category="AUTHENTICATION",
                event_type=f"AUTH_FINDING_{row.finding_type}",
                severity=_severity_from_status(row.finding_status),
                source_system="SCAN_AUTHENTICATION",
                event_occurred_at=row.created_at,
                source_record_id=row.id,
                source_checksum=run.authentication_checksum,
                lineage_checksum=run.source_checksum,
                event_payload_json={
                    "finding_status": row.finding_status,
                    "review_priority": row.review_priority,
                    "confidence_score": row.confidence_score,
                    "finding_text": row.finding_text,
                },
                metadata_json=dict(row.metadata_json or {}),
            )
        )
    return events


def _collect_lineage_issues(ctx: _FeedContext) -> list[_IssueDraft]:
    issues: list[_IssueDraft] = []
    if ctx.normalization_run is None:
        issues.append(_IssueDraft("LINEAGE_GAP", "WARNING", "SCAN_FEED", None, "Normalization run missing for scan image.", {"missing_stage": "NORMALIZATION"}))
    elif ctx.boundary_run is None:
        issues.append(_IssueDraft("LINEAGE_GAP", "WARNING", "SCAN_FEED", None, "Boundary run missing after normalization.", {"missing_stage": "BOUNDARY"}))
    elif ctx.ocr_run is None:
        issues.append(_IssueDraft("LINEAGE_GAP", "WARNING", "SCAN_FEED", None, "OCR run missing after boundary completion.", {"missing_stage": "OCR"}))
    elif ctx.reconciliation_run is None:
        issues.append(_IssueDraft("LINEAGE_GAP", "WARNING", "SCAN_FEED", None, "Reconciliation run missing after OCR completion.", {"missing_stage": "RECONCILIATION"}))
    return issues


def _collect_feed_inputs(session: Session, *, ctx: _FeedContext) -> tuple[list[_EventDraft], list[_IssueDraft]]:
    events: list[_EventDraft] = []
    issues: list[_IssueDraft] = []
    part_events, part_issues = _collect_ingestion(ctx)
    events.extend(part_events)
    issues.extend(part_issues)
    issues.extend(_collect_lineage_issues(ctx))
    for attr_name, spec in _RUN_SPECS.items():
        run = getattr(ctx, attr_name)
        part_events, part_issues = _collect_run_family(session, run=run, spec=spec)
        events.extend(part_events)
        issues.extend(part_issues)
    events.extend(_collect_reconciliation_detail(session, run=ctx.reconciliation_run))
    events.extend(_collect_grading_detail(session, run=ctx.grading_assistance_run))
    events.extend(_collect_visual_detail(session, run=ctx.visual_evidence_run))
    events.extend(_collect_review_detail(session, run=ctx.review_session))
    events.extend(_collect_historical_detail(session, run=ctx.historical_comparison_run))
    events.extend(_collect_authentication_detail(session, run=ctx.authentication_run))
    return events, issues


def _event_sort_key(draft: _EventDraft) -> tuple[Any, ...]:
    normalized_time = _normalize_datetime(draft.event_occurred_at)
    return (
        normalized_time,
        _CATEGORY_RANK.get(draft.event_category, 999),
        _SEVERITY_RANK.get(draft.severity, 999),
        _SOURCE_SYSTEM_RANK.get(draft.source_system, 999),
        draft.source_record_id or 0,
        draft.source_checksum or "",
        _event_key(draft),
    )


def _build_input_manifest(ctx: _FeedContext) -> dict[str, Any]:
    anchors: dict[str, Any] = {
        "scan_image_id": ctx.scan_image.id,
        "scan_image_checksum": ctx.scan_image.sha256_checksum,
        "upload_session_id": ctx.upload_session.id if ctx.upload_session else None,
        "ingestion_batch_id": ctx.ingestion_batch.id if ctx.ingestion_batch else None,
    }
    lineage_checksums = {
        "original_scan_checksum": ctx.scan_image.sha256_checksum,
        "normalization_checksum": ctx.normalization_run.normalization_checksum if ctx.normalization_run else None,
        "boundary_checksum": ctx.boundary_run.boundary_checksum if ctx.boundary_run else None,
        "ocr_checksum": ctx.ocr_run.ocr_checksum if ctx.ocr_run else None,
        "reconciliation_checksum": ctx.reconciliation_run.reconciliation_checksum if ctx.reconciliation_run else None,
        "defect_checksum": ctx.defect_run.defect_checksum if ctx.defect_run else None,
        "spine_tick_checksum": ctx.spine_tick_run.spine_tick_checksum if ctx.spine_tick_run else None,
        "corner_edge_checksum": ctx.corner_edge_run.corner_edge_checksum if ctx.corner_edge_run else None,
        "surface_defect_checksum": ctx.surface_defect_run.surface_defect_checksum if ctx.surface_defect_run else None,
        "structural_damage_checksum": ctx.structural_damage_run.structural_damage_checksum if ctx.structural_damage_run else None,
        "defect_aggregation_checksum": ctx.defect_aggregation_run.aggregation_checksum if ctx.defect_aggregation_run else None,
        "grading_assistance_checksum": ctx.grading_assistance_run.grading_assistance_checksum if ctx.grading_assistance_run else None,
        "visual_evidence_checksum": ctx.visual_evidence_run.visual_evidence_checksum if ctx.visual_evidence_run else None,
        "review_checksum": ctx.review_session.review_checksum if ctx.review_session else None,
        "historical_comparison_checksum": ctx.historical_comparison_run.historical_comparison_checksum if ctx.historical_comparison_run else None,
        "authentication_checksum": ctx.authentication_run.authentication_checksum if ctx.authentication_run else None,
    }
    anchors.update({k: v for k, v in lineage_checksums.items() if k.endswith("_checksum")})
    return {
        "engine_version": ENGINE_VERSION,
        "anchors": anchors,
        "lineage_checksums": lineage_checksums,
        "included_families": [
            "scan_upload_session",
            "scan_ingestion_batch",
            "scan_ingestion_event",
            "scan_image",
            "scan_normalization",
            "scan_boundary",
            "scan_ocr",
            "scan_reconciliation",
            "scan_defects",
            "scan_spine_ticks",
            "scan_corner_edges",
            "scan_surface_defects",
            "scan_structural_damage",
            "scan_defect_aggregation",
            "scan_grading_assistance",
            "scan_visual_evidence",
            "scan_review",
            "scan_historical_comparison",
            "scan_authentication",
        ],
    }


def _build_artifacts(
    *,
    input_manifest: dict[str, Any],
    output_manifest: dict[str, Any],
    events_payload: list[dict[str, Any]],
    issues_payload: list[dict[str, Any]],
) -> list[_ArtifactDraft]:
    manifest_body = _serialize_json_artifact({"input_manifest": input_manifest, "output_manifest": output_manifest})
    timeline_body = _serialize_json_artifact(
        [
            {
                "timeline_rank": row["timeline_rank"],
                "event_occurred_at": row["event_occurred_at"],
                "event_category": row["event_category"],
                "event_type": row["event_type"],
                "severity": row["severity"],
                "source_system": row["source_system"],
            }
            for row in events_payload
        ]
    )
    feed_body = _serialize_json_artifact({"events": events_payload, "issues": issues_payload})
    ops_body = _serialize_json_artifact(
        {
            "events": [row for row in events_payload if row["severity"] in {"ERROR", "WARNING", "REVIEW_REQUIRED"}],
            "issues": issues_payload,
        }
    )
    preview_body = _serialize_json_artifact(
        {
            "feed_status": output_manifest["feed_status"],
            "total_events": output_manifest["total_events"],
            "total_issues": output_manifest["total_issues"],
            "top_categories": output_manifest["category_counts"],
        }
    )
    return [
        _ArtifactDraft("FEED_MANIFEST", manifest_body, {"kind": "manifest"}, ".json"),
        _ArtifactDraft("SCAN_TIMELINE_EXPORT", timeline_body, {"kind": "timeline"}, ".json"),
        _ArtifactDraft("SCAN_FEED_EXPORT", feed_body, {"kind": "feed"}, ".json"),
        _ArtifactDraft("OPS_FEED_EXPORT", ops_body, {"kind": "ops"}, ".json"),
        _ArtifactDraft("FEED_DEBUG_PREVIEW", preview_body, {"kind": "preview"}, ".json"),
    ]


def _build_run_detail(
    session: Session,
    settings: Settings,
    *,
    run: ScanIntelligenceFeedRun,
) -> ScanIntelligenceFeedRunDetail:
    events = list(
        session.exec(
            select(ScanIntelligenceFeedEvent)
            .where(ScanIntelligenceFeedEvent.feed_run_id == run.id)
            .order_by(col(ScanIntelligenceFeedEvent.timeline_rank), col(ScanIntelligenceFeedEvent.id))
        ).all()
    )
    artifacts = list(
        session.exec(
            select(ScanIntelligenceFeedArtifact)
            .where(ScanIntelligenceFeedArtifact.feed_run_id == run.id)
            .order_by(col(ScanIntelligenceFeedArtifact.created_at), col(ScanIntelligenceFeedArtifact.id))
        ).all()
    )
    issues = list(
        session.exec(
            select(ScanIntelligenceFeedIssue)
            .where(ScanIntelligenceFeedIssue.feed_run_id == run.id)
            .order_by(col(ScanIntelligenceFeedIssue.created_at), col(ScanIntelligenceFeedIssue.id))
        ).all()
    )
    history = list(
        session.exec(
            select(ScanIntelligenceFeedHistory)
            .where(ScanIntelligenceFeedHistory.feed_run_id == run.id)
            .order_by(col(ScanIntelligenceFeedHistory.created_at), col(ScanIntelligenceFeedHistory.id))
        ).all()
    )
    lineage = dict((run.input_manifest_json or {}).get("lineage_checksums") or {})
    artifact_reads: list[ScanIntelligenceFeedArtifactRead] = []
    for row in artifacts:
        media_type, text_preview, body_base64 = _load_artifact_payload(settings, row)
        artifact_reads.append(
            ScanIntelligenceFeedArtifactRead.model_validate(
                {
                    **row.model_dump(),
                    "media_type": media_type,
                    "text_preview": text_preview,
                    "body_base64": body_base64,
                }
            )
        )
    return ScanIntelligenceFeedRunDetail(
        **ScanIntelligenceFeedRunRead.model_validate(run).model_dump(),
        events=[ScanIntelligenceFeedEventRead.model_validate(row) for row in events],
        artifacts=artifact_reads,
        issues=[ScanIntelligenceFeedIssueRead.model_validate(row) for row in issues],
        history=[ScanIntelligenceFeedHistoryRead.model_validate(row) for row in history],
        original_scan_checksum=lineage.get("original_scan_checksum"),
        normalization_checksum=lineage.get("normalization_checksum"),
        boundary_checksum=lineage.get("boundary_checksum"),
        ocr_checksum=lineage.get("ocr_checksum"),
        reconciliation_checksum=lineage.get("reconciliation_checksum"),
        defect_checksum=lineage.get("defect_checksum"),
        spine_tick_checksum=lineage.get("spine_tick_checksum"),
        corner_edge_checksum=lineage.get("corner_edge_checksum"),
        surface_defect_checksum=lineage.get("surface_defect_checksum"),
        structural_damage_checksum=lineage.get("structural_damage_checksum"),
        defect_aggregation_checksum=lineage.get("defect_aggregation_checksum"),
        grading_assistance_checksum=lineage.get("grading_assistance_checksum"),
        visual_evidence_checksum=lineage.get("visual_evidence_checksum"),
        review_checksum=lineage.get("review_checksum"),
        historical_comparison_checksum=lineage.get("historical_comparison_checksum"),
        authentication_checksum=lineage.get("authentication_checksum"),
    )


def run_scan_intelligence_feed(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: ScanIntelligenceFeedRunCreate,
) -> tuple[ScanIntelligenceFeedRunDetail, bool]:
    ctx = _load_context(session, owner_user_id=owner_user_id, payload=payload)
    input_manifest = _build_input_manifest(ctx)
    source_checksum = _hash_payload(input_manifest)
    event_drafts, issue_drafts = _collect_feed_inputs(session, ctx=ctx)

    events_sorted = sorted(event_drafts, key=_event_sort_key)
    seen_event_keys: set[str] = set()
    for draft in events_sorted:
        key = _event_key(draft)
        if key in seen_event_keys:
            issue_drafts.append(
                _IssueDraft(
                    issue_type="ORDERING_COLLISION",
                    severity="ERROR",
                    source_system="SCAN_FEED",
                    source_record_id=draft.source_record_id,
                    issue_message=f"Deterministic ordering collision for {draft.event_type}.",
                    metadata_json={"event_key": key},
                )
            )
        seen_event_keys.add(key)

    event_payloads: list[dict[str, Any]] = []
    for index, draft in enumerate(sorted(events_sorted, key=_event_sort_key), start=1):
        key = _event_key(draft)
        event_payloads.append(
            {
                "event_rank": index,
                "timeline_rank": index,
                "event_category": draft.event_category,
                "event_type": draft.event_type,
                "severity": draft.severity,
                "source_system": draft.source_system,
                "event_occurred_at": _normalize_datetime(draft.event_occurred_at),
                "source_record_id": draft.source_record_id,
                "source_checksum": draft.source_checksum,
                "lineage_checksum": draft.lineage_checksum,
                "event_key": key,
                "event_payload_json": draft.event_payload_json,
                "metadata_json": draft.metadata_json,
            }
        )

    issue_payloads: list[dict[str, Any]] = []
    for draft in sorted(issue_drafts, key=lambda row: (_SEVERITY_RANK.get(row.severity, 999), row.source_system, row.source_record_id or 0, row.issue_type, _hash_payload(row.metadata_json))):
        issue_payloads.append(
            {
                "issue_type": draft.issue_type,
                "severity": draft.severity,
                "source_system": draft.source_system,
                "source_record_id": draft.source_record_id,
                "issue_message": draft.issue_message,
                "metadata_json": draft.metadata_json,
                "issue_checksum": _hash_payload(
                    {
                        "issue_type": draft.issue_type,
                        "severity": draft.severity,
                        "source_system": draft.source_system,
                        "source_record_id": draft.source_record_id,
                        "issue_message": draft.issue_message,
                        "metadata_json": draft.metadata_json,
                    }
                ),
            }
        )

    severity_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    source_system_counts: dict[str, int] = {}
    for row in event_payloads:
        severity_counts[row["severity"]] = severity_counts.get(row["severity"], 0) + 1
        category_counts[row["event_category"]] = category_counts.get(row["event_category"], 0) + 1
        source_system_counts[row["source_system"]] = source_system_counts.get(row["source_system"], 0) + 1

    feed_status = "COMPLETE"
    if severity_counts.get("ERROR"):
        feed_status = "FAILED"
    elif severity_counts.get("REVIEW_REQUIRED"):
        feed_status = "REVIEW_REQUIRED"
    elif severity_counts.get("WARNING") or issue_payloads:
        feed_status = "COMPLETE_WITH_WARNINGS"

    output_manifest = {
        "feed_status": feed_status,
        "total_events": len(event_payloads),
        "total_issues": len(issue_payloads),
        "review_required_count": severity_counts.get("REVIEW_REQUIRED", 0),
        "error_count": severity_counts.get("ERROR", 0),
        "severity_counts": severity_counts,
        "category_counts": category_counts,
        "source_system_counts": source_system_counts,
        "timeline": [
            {
                "timeline_rank": row["timeline_rank"],
                "event_key": row["event_key"],
                "event_occurred_at": row["event_occurred_at"],
                "event_category": row["event_category"],
                "severity": row["severity"],
            }
            for row in event_payloads
        ],
        "issue_checksums": [row["issue_checksum"] for row in issue_payloads],
    }
    feed_checksum = _hash_payload({"input_manifest": input_manifest, "output_manifest": output_manifest})

    existing = session.exec(
        select(ScanIntelligenceFeedRun).where(
            ScanIntelligenceFeedRun.owner_user_id == owner_user_id,
            ScanIntelligenceFeedRun.feed_checksum == feed_checksum,
        )
    ).first()
    if existing is not None:
        return _build_run_detail(session, settings, run=existing), False

    run = ScanIntelligenceFeedRun(
        owner_user_id=owner_user_id,
        scan_image_id=int(ctx.scan_image.id),
        upload_session_id=ctx.upload_session.id if ctx.upload_session else None,
        ingestion_batch_id=ctx.ingestion_batch.id if ctx.ingestion_batch else None,
        normalization_run_id=ctx.normalization_run.id if ctx.normalization_run else None,
        boundary_run_id=ctx.boundary_run.id if ctx.boundary_run else None,
        ocr_run_id=ctx.ocr_run.id if ctx.ocr_run else None,
        reconciliation_run_id=ctx.reconciliation_run.id if ctx.reconciliation_run else None,
        defect_run_id=ctx.defect_run.id if ctx.defect_run else None,
        spine_tick_run_id=ctx.spine_tick_run.id if ctx.spine_tick_run else None,
        corner_edge_run_id=ctx.corner_edge_run.id if ctx.corner_edge_run else None,
        surface_defect_run_id=ctx.surface_defect_run.id if ctx.surface_defect_run else None,
        structural_damage_run_id=ctx.structural_damage_run.id if ctx.structural_damage_run else None,
        defect_aggregation_run_id=ctx.defect_aggregation_run.id if ctx.defect_aggregation_run else None,
        grading_assistance_run_id=ctx.grading_assistance_run.id if ctx.grading_assistance_run else None,
        visual_evidence_run_id=ctx.visual_evidence_run.id if ctx.visual_evidence_run else None,
        review_session_id=ctx.review_session.id if ctx.review_session else None,
        historical_comparison_run_id=ctx.historical_comparison_run.id if ctx.historical_comparison_run else None,
        authentication_run_id=ctx.authentication_run.id if ctx.authentication_run else None,
        source_checksum=source_checksum,
        feed_checksum=feed_checksum,
        feed_status=feed_status,
        engine_version=ENGINE_VERSION,
        input_manifest_json=_json_safe(input_manifest),
        output_manifest_json=_json_safe(output_manifest),
        total_events=len(event_payloads),
        total_issues=len(issue_payloads),
        review_required_count=severity_counts.get("REVIEW_REQUIRED", 0),
        error_count=severity_counts.get("ERROR", 0),
        completed_at=utc_now(),
    )
    session.add(run)
    session.flush()

    for row in event_payloads:
        session.add(
            ScanIntelligenceFeedEvent(
                owner_user_id=owner_user_id,
                feed_run_id=int(run.id),
                event_rank=int(row["event_rank"]),
                timeline_rank=int(row["timeline_rank"]),
                event_category=str(row["event_category"]),
                event_type=str(row["event_type"]),
                severity=str(row["severity"]),
                source_system=str(row["source_system"]),
                event_occurred_at=row["event_occurred_at"],
                source_record_id=row["source_record_id"],
                source_checksum=row["source_checksum"],
                lineage_checksum=row["lineage_checksum"],
                event_key=str(row["event_key"]),
                event_payload_json=dict(row["event_payload_json"]),
                metadata_json=dict(row["metadata_json"]),
            )
        )
    for row in issue_payloads:
        session.add(
            ScanIntelligenceFeedIssue(
                owner_user_id=owner_user_id,
                feed_run_id=int(run.id),
                issue_type=str(row["issue_type"]),
                severity=str(row["severity"]),
                source_system=str(row["source_system"]),
                source_record_id=row["source_record_id"],
                issue_message=str(row["issue_message"]),
                issue_checksum=str(row["issue_checksum"]),
                metadata_json=dict(row["metadata_json"]),
            )
        )

    artifacts = _build_artifacts(input_manifest=input_manifest, output_manifest=output_manifest, events_payload=event_payloads, issues_payload=issue_payloads)
    for artifact in artifacts:
        artifact_checksum = _sha256_bytes(artifact.body)
        relative_path = _artifact_storage_path(
            owner_user_id=owner_user_id,
            scan_image_id=int(ctx.scan_image.id),
            feed_run_id=int(run.id),
            artifact_type=artifact.artifact_type,
            ext=artifact.ext,
        )
        _save_artifact_bytes(settings, relative_path=relative_path, body=artifact.body)
        session.add(
            ScanIntelligenceFeedArtifact(
                owner_user_id=owner_user_id,
                feed_run_id=int(run.id),
                artifact_type=artifact.artifact_type,
                storage_backend="filesystem",
                storage_path=relative_path,
                artifact_checksum=artifact_checksum,
                metadata_json=dict(artifact.metadata_json),
            )
        )

    history = [
        _HistoryDraft("RUN_CREATED", "Scan intelligence feed generated.", {"feed_checksum": feed_checksum}),
        _HistoryDraft("EVENTS_AGGREGATED", f"Aggregated {len(event_payloads)} deterministic feed events.", {"total_events": len(event_payloads)}),
        _HistoryDraft("ISSUES_AGGREGATED", f"Captured {len(issue_payloads)} feed issues.", {"total_issues": len(issue_payloads)}),
        _HistoryDraft("ARTIFACTS_WRITTEN", f"Persisted {len(artifacts)} feed artifacts.", {"artifact_types": [row.artifact_type for row in artifacts]}),
    ]
    for row in history:
        session.add(
            ScanIntelligenceFeedHistory(
                owner_user_id=owner_user_id,
                feed_run_id=int(run.id),
                event_type=row.event_type,
                event_message=row.event_message,
                event_checksum=_hash_payload({"event_type": row.event_type, "event_message": row.event_message, "metadata_json": row.metadata_json}),
                metadata_json=dict(row.metadata_json),
            )
        )

    session.commit()
    session.refresh(run)
    return _build_run_detail(session, settings, run=run), True


def get_scan_intelligence_feed_run_owner(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    run_id: int,
) -> ScanIntelligenceFeedRunDetail:
    run = session.get(ScanIntelligenceFeedRun, run_id)
    if run is None or int(run.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan intelligence feed run not found.")
    return _build_run_detail(session, settings, run=run)


def get_scan_intelligence_feed_artifact_owner(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    artifact_id: int,
) -> ScanIntelligenceFeedArtifactRead:
    row = session.get(ScanIntelligenceFeedArtifact, artifact_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan intelligence feed artifact not found.")
    media_type, text_preview, body_base64 = _load_artifact_payload(settings, row)
    return ScanIntelligenceFeedArtifactRead.model_validate(
        {
            **row.model_dump(),
            "media_type": media_type,
            "text_preview": text_preview,
            "body_base64": body_base64,
        }
    )


def _list_runs(
    session: Session,
    *,
    owner_user_id: int | None,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanIntelligenceFeedRunListResponse:
    limit, offset = clamp_scan_intelligence_feed_pagination(limit=limit, offset=offset)
    stmt = select(ScanIntelligenceFeedRun)
    count_stmt = select(func.count()).select_from(ScanIntelligenceFeedRun)
    if owner_user_id is not None:
        stmt = stmt.where(ScanIntelligenceFeedRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanIntelligenceFeedRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanIntelligenceFeedRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanIntelligenceFeedRun.scan_image_id == scan_image_id)
    ordered = stmt.order_by(col(ScanIntelligenceFeedRun.created_at).desc(), col(ScanIntelligenceFeedRun.id).desc())
    items = list(session.exec(ordered.offset(offset).limit(limit)).all())
    total_items = int(session.exec(count_stmt).one())
    filtered = list(session.exec(ordered).all())
    status_counts: dict[str, int] = {}
    total_event_count = 0
    total_review_required_count = 0
    total_error_count = 0
    for row in filtered:
        status_counts[row.feed_status] = status_counts.get(row.feed_status, 0) + 1
        total_event_count += int(row.total_events)
        total_review_required_count += int(row.review_required_count)
        total_error_count += int(row.error_count)
    return ScanIntelligenceFeedRunListResponse(
        items=[ScanIntelligenceFeedRunRead.model_validate(row) for row in items],
        total_items=total_items,
        limit=limit,
        offset=offset,
        status_counts=status_counts,
        total_event_count=total_event_count,
        total_review_required_count=total_review_required_count,
        total_error_count=total_error_count,
    )


def list_scan_intelligence_feed_runs_owner(session: Session, *, owner_user_id: int, scan_image_id: int | None, limit: int, offset: int) -> ScanIntelligenceFeedRunListResponse:
    return _list_runs(session, owner_user_id=owner_user_id, scan_image_id=scan_image_id, limit=limit, offset=offset)


def list_scan_intelligence_feed_runs_ops(session: Session, *, owner_user_id: int | None, scan_image_id: int | None, limit: int, offset: int) -> ScanIntelligenceFeedRunListResponse:
    return _list_runs(session, owner_user_id=owner_user_id, scan_image_id=scan_image_id, limit=limit, offset=offset)


def _list_events(
    session: Session,
    *,
    owner_user_id: int | None,
    run_id: int | None,
    severity: str | None,
    event_category: str | None,
    source_system: str | None,
    limit: int,
    offset: int,
) -> ScanIntelligenceFeedEventListResponse:
    limit, offset = clamp_scan_intelligence_feed_pagination(limit=limit, offset=offset)
    stmt = select(ScanIntelligenceFeedEvent)
    count_stmt = select(func.count()).select_from(ScanIntelligenceFeedEvent)
    if owner_user_id is not None:
        stmt = stmt.where(ScanIntelligenceFeedEvent.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanIntelligenceFeedEvent.owner_user_id == owner_user_id)
    if run_id is not None:
        stmt = stmt.where(ScanIntelligenceFeedEvent.feed_run_id == run_id)
        count_stmt = count_stmt.where(ScanIntelligenceFeedEvent.feed_run_id == run_id)
    if severity is not None:
        stmt = stmt.where(ScanIntelligenceFeedEvent.severity == severity)
        count_stmt = count_stmt.where(ScanIntelligenceFeedEvent.severity == severity)
    if event_category is not None:
        stmt = stmt.where(ScanIntelligenceFeedEvent.event_category == event_category)
        count_stmt = count_stmt.where(ScanIntelligenceFeedEvent.event_category == event_category)
    if source_system is not None:
        stmt = stmt.where(ScanIntelligenceFeedEvent.source_system == source_system)
        count_stmt = count_stmt.where(ScanIntelligenceFeedEvent.source_system == source_system)
    ordered = stmt.order_by(col(ScanIntelligenceFeedEvent.timeline_rank), col(ScanIntelligenceFeedEvent.id))
    items = list(session.exec(ordered.offset(offset).limit(limit)).all())
    total_items = int(session.exec(count_stmt).one())
    filtered = list(session.exec(ordered).all())
    severity_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    source_system_counts: dict[str, int] = {}
    for row in filtered:
        severity_counts[row.severity] = severity_counts.get(row.severity, 0) + 1
        category_counts[row.event_category] = category_counts.get(row.event_category, 0) + 1
        source_system_counts[row.source_system] = source_system_counts.get(row.source_system, 0) + 1
    return ScanIntelligenceFeedEventListResponse(
        items=[ScanIntelligenceFeedEventRead.model_validate(row) for row in items],
        total_items=total_items,
        limit=limit,
        offset=offset,
        severity_counts=severity_counts,
        category_counts=category_counts,
        source_system_counts=source_system_counts,
    )


def list_scan_intelligence_feed_events_owner(
    session: Session,
    *,
    owner_user_id: int,
    run_id: int | None,
    severity: str | None,
    event_category: str | None,
    source_system: str | None,
    limit: int,
    offset: int,
) -> ScanIntelligenceFeedEventListResponse:
    return _list_events(
        session,
        owner_user_id=owner_user_id,
        run_id=run_id,
        severity=severity,
        event_category=event_category,
        source_system=source_system,
        limit=limit,
        offset=offset,
    )


def list_scan_intelligence_feed_events_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    run_id: int | None,
    severity: str | None,
    event_category: str | None,
    source_system: str | None,
    limit: int,
    offset: int,
) -> ScanIntelligenceFeedEventListResponse:
    return _list_events(
        session,
        owner_user_id=owner_user_id,
        run_id=run_id,
        severity=severity,
        event_category=event_category,
        source_system=source_system,
        limit=limit,
        offset=offset,
    )


def _list_issues(
    session: Session,
    *,
    owner_user_id: int | None,
    run_id: int | None,
    severity: str | None,
    limit: int,
    offset: int,
) -> ScanIntelligenceFeedIssueListResponse:
    limit, offset = clamp_scan_intelligence_feed_pagination(limit=limit, offset=offset)
    stmt = select(ScanIntelligenceFeedIssue)
    count_stmt = select(func.count()).select_from(ScanIntelligenceFeedIssue)
    if owner_user_id is not None:
        stmt = stmt.where(ScanIntelligenceFeedIssue.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanIntelligenceFeedIssue.owner_user_id == owner_user_id)
    if run_id is not None:
        stmt = stmt.where(ScanIntelligenceFeedIssue.feed_run_id == run_id)
        count_stmt = count_stmt.where(ScanIntelligenceFeedIssue.feed_run_id == run_id)
    if severity is not None:
        stmt = stmt.where(ScanIntelligenceFeedIssue.severity == severity)
        count_stmt = count_stmt.where(ScanIntelligenceFeedIssue.severity == severity)
    ordered = stmt.order_by(col(ScanIntelligenceFeedIssue.created_at), col(ScanIntelligenceFeedIssue.id))
    items = list(session.exec(ordered.offset(offset).limit(limit)).all())
    total_items = int(session.exec(count_stmt).one())
    filtered = list(session.exec(ordered).all())
    severity_counts: dict[str, int] = {}
    issue_type_counts: dict[str, int] = {}
    source_system_counts: dict[str, int] = {}
    for row in filtered:
        severity_counts[row.severity] = severity_counts.get(row.severity, 0) + 1
        issue_type_counts[row.issue_type] = issue_type_counts.get(row.issue_type, 0) + 1
        source_system_counts[row.source_system] = source_system_counts.get(row.source_system, 0) + 1
    return ScanIntelligenceFeedIssueListResponse(
        items=[ScanIntelligenceFeedIssueRead.model_validate(row) for row in items],
        total_items=total_items,
        limit=limit,
        offset=offset,
        severity_counts=severity_counts,
        issue_type_counts=issue_type_counts,
        source_system_counts=source_system_counts,
    )


def list_scan_intelligence_feed_issues_owner(session: Session, *, owner_user_id: int, run_id: int | None, severity: str | None, limit: int, offset: int) -> ScanIntelligenceFeedIssueListResponse:
    return _list_issues(session, owner_user_id=owner_user_id, run_id=run_id, severity=severity, limit=limit, offset=offset)


def list_scan_intelligence_feed_issues_ops(session: Session, *, owner_user_id: int | None, run_id: int | None, severity: str | None, limit: int, offset: int) -> ScanIntelligenceFeedIssueListResponse:
    return _list_issues(session, owner_user_id=owner_user_id, run_id=run_id, severity=severity, limit=limit, offset=offset)


def list_scan_intelligence_feed_failures_ops(session: Session, *, owner_user_id: int | None, limit: int, offset: int) -> ScanIntelligenceFeedEventListResponse:
    return _list_events(session, owner_user_id=owner_user_id, run_id=None, severity="ERROR", event_category=None, source_system=None, limit=limit, offset=offset)


def list_scan_intelligence_feed_review_required_ops(session: Session, *, owner_user_id: int | None, limit: int, offset: int) -> ScanIntelligenceFeedEventListResponse:
    return _list_events(session, owner_user_id=owner_user_id, run_id=None, severity="REVIEW_REQUIRED", event_category=None, source_system=None, limit=limit, offset=offset)
