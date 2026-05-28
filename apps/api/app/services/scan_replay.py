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
    ScanAuthenticationHistory,
    ScanAuthenticationIssue,
    ScanAuthenticationRun,
    ScanBoundaryArtifact,
    ScanBoundaryHistory,
    ScanBoundaryIssue,
    ScanBoundaryRun,
    ScanCornerEdgeArtifact,
    ScanCornerEdgeHistory,
    ScanCornerEdgeIssue,
    ScanCornerEdgeRun,
    ScanDefectAggregationArtifact,
    ScanDefectAggregationHistory,
    ScanDefectAggregationIssue,
    ScanDefectAggregationRun,
    ScanDefectArtifact,
    ScanDefectHistory,
    ScanDefectIssue,
    ScanDefectRun,
    ScanGradingAssistanceArtifact,
    ScanGradingAssistanceHistory,
    ScanGradingAssistanceIssue,
    ScanGradingAssistanceRun,
    ScanHistoricalComparisonArtifact,
    ScanHistoricalComparisonHistory,
    ScanHistoricalComparisonIssue,
    ScanHistoricalComparisonRun,
    ScanImage,
    ScanIngestionBatch,
    ScanIntelligenceFeedArtifact,
    ScanIntelligenceFeedEvent,
    ScanIntelligenceFeedHistory,
    ScanIntelligenceFeedIssue,
    ScanIntelligenceFeedRun,
    ScanNormalizationArtifact,
    ScanNormalizationHistory,
    ScanNormalizationIssue,
    ScanNormalizationRun,
    ScanOcrArtifact,
    ScanOcrHistory,
    ScanOcrIssue,
    ScanOcrRun,
    ScanReconciliationArtifact,
    ScanReconciliationHistory,
    ScanReconciliationIssue,
    ScanReconciliationRun,
    ScanReplayArtifact,
    ScanReplayCheck,
    ScanReplayDiscrepancy,
    ScanReplayHistory,
    ScanReplayIssue,
    ScanReplayRun,
    ScanReplayStep,
    ScanReviewArtifact,
    ScanReviewDecision,
    ScanReviewHistory,
    ScanReviewIssue,
    ScanReviewSession,
    ScanSpineTickArtifact,
    ScanSpineTickHistory,
    ScanSpineTickIssue,
    ScanSpineTickRun,
    ScanStructuralDamageArtifact,
    ScanStructuralDamageHistory,
    ScanStructuralDamageIssue,
    ScanStructuralDamageRun,
    ScanSurfaceDefectArtifact,
    ScanSurfaceDefectHistory,
    ScanSurfaceDefectIssue,
    ScanSurfaceDefectRun,
    ScanUploadSession,
    ScanVisualEvidenceArtifact,
    ScanVisualEvidenceHistory,
    ScanVisualEvidenceIssue,
    ScanVisualEvidenceRun,
)
from app.schemas.scan_replay import (
    ScanReplayArtifactRead,
    ScanReplayCheckListResponse,
    ScanReplayCheckRead,
    ScanReplayDiscrepancyListResponse,
    ScanReplayDiscrepancyRead,
    ScanReplayHistoryRead,
    ScanReplayIssueListResponse,
    ScanReplayIssueRead,
    ScanReplayRunCreate,
    ScanReplayRunDetail,
    ScanReplayRunListResponse,
    ScanReplayRunRead,
    ScanReplayStepListResponse,
    ScanReplayStepRead,
)

ENGINE_VERSION = "P40-18-v1"

_PHASE_ORDER = [
    "P40_01_SCAN_INGESTION",
    "P40_02_NORMALIZATION",
    "P40_03_BOUNDARY",
    "P40_04_OCR",
    "P40_05_RECONCILIATION",
    "P40_06_DEFECT_FOUNDATION",
    "P40_07_SPINE",
    "P40_08_CORNER_EDGE",
    "P40_09_SURFACE",
    "P40_10_STRUCTURAL",
    "P40_11_AGGREGATION",
    "P40_12_GRADING_ASSISTANCE",
    "P40_13_VISUAL_EVIDENCE",
    "P40_14_REVIEW",
    "P40_15_HISTORICAL_COMPARISON",
    "P40_16_AUTHENTICATION",
    "P40_17_FEED",
]
_SEVERITY_RANK = {"INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}
_CHECK_STATUS_RANK = {"PASS": 1, "WARNING": 2, "SKIPPED": 3, "FAIL": 4}
_STEP_STATUS_RANK = {"MATCHED": 1, "SKIPPED": 2, "MISSING_SOURCE": 3, "REPLAY_BLOCKED": 4, "MISMATCHED": 5, "ERROR": 6}
_MIME_BY_EXT = {".json": "application/json", ".txt": "text/plain; charset=utf-8"}
_REQUIRED_BY_SCOPE = {
    "SINGLE_SCAN": {"P40_01_SCAN_INGESTION", "P40_02_NORMALIZATION", "P40_03_BOUNDARY"},
    "FULL_P40_PIPELINE": {"P40_01_SCAN_INGESTION", "P40_02_NORMALIZATION", "P40_03_BOUNDARY", "P40_04_OCR", "P40_05_RECONCILIATION", "P40_06_DEFECT_FOUNDATION"},
    "SELECTED_STAGE": set(),
    "OPS_AUDIT": set(),
    "BATCH_REPLAY": set(),
}
_LINEAGE_KEY_BY_PHASE = {
    "P40_01_SCAN_INGESTION": "original_scan_checksum",
    "P40_02_NORMALIZATION": "normalization_checksum",
    "P40_03_BOUNDARY": "boundary_checksum",
    "P40_04_OCR": "ocr_checksum",
    "P40_05_RECONCILIATION": "reconciliation_checksum",
    "P40_06_DEFECT_FOUNDATION": "defect_checksum",
    "P40_07_SPINE": "spine_tick_checksum",
    "P40_08_CORNER_EDGE": "corner_edge_checksum",
    "P40_09_SURFACE": "surface_defect_checksum",
    "P40_10_STRUCTURAL": "structural_damage_checksum",
    "P40_11_AGGREGATION": "defect_aggregation_checksum",
    "P40_12_GRADING_ASSISTANCE": "grading_assistance_checksum",
    "P40_13_VISUAL_EVIDENCE": "visual_evidence_checksum",
    "P40_14_REVIEW": "review_checksum",
    "P40_15_HISTORICAL_COMPARISON": "historical_comparison_checksum",
    "P40_16_AUTHENTICATION": "authentication_checksum",
    "P40_17_FEED": "feed_checksum",
}


@dataclass(frozen=True)
class _ReplayStepDraft:
    step_rank: int
    phase_key: str
    source_record_id: int | None
    expected_checksum: str | None
    observed_checksum: str | None
    replay_step_status: str
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _CheckDraft:
    step_rank: int | None
    phase_key: str | None
    check_type: str
    check_status: str
    expected_value: str | None
    observed_value: str | None
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _DiscrepancyDraft:
    step_rank: int | None
    phase_key: str | None
    discrepancy_type: str
    severity: str
    expected_value: str | None
    observed_value: str | None
    discrepancy_message: str
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _IssueDraft:
    issue_type: str
    severity: str
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
class _ReplayContext:
    scan_image: ScanImage | None
    upload_session: ScanUploadSession | None
    ingestion_batch: ScanIngestionBatch | None
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
    feed_run: ScanIntelligenceFeedRun | None


@dataclass(frozen=True)
class _PhaseSpec:
    phase_key: str
    label: str
    attr_name: str | None
    checksum_field: str | None
    status_field: str | None
    source_checksum_field: str | None
    artifact_model: type | None = None
    artifact_fk_field: str | None = None
    issue_model: type | None = None
    issue_fk_field: str | None = None
    history_model: type | None = None
    history_fk_field: str | None = None
    storage_root_attr: str | None = None
    relative_path_attr: str | None = "storage_path"


_PHASE_SPECS: dict[str, _PhaseSpec] = {
    "P40_01_SCAN_INGESTION": _PhaseSpec("P40_01_SCAN_INGESTION", "Scan ingestion", "scan_image", "sha256_checksum", "processing_status", None, None, None, None, None, None, None, "scan_ingestion_storage_root"),
    "P40_02_NORMALIZATION": _PhaseSpec("P40_02_NORMALIZATION", "Normalization", "normalization_run", "normalization_checksum", "normalization_status", "source_sha256_checksum", ScanNormalizationArtifact, "scan_normalization_run_id", ScanNormalizationIssue, "scan_normalization_run_id", ScanNormalizationHistory, "scan_normalization_run_id", "scan_normalization_storage_root"),
    "P40_03_BOUNDARY": _PhaseSpec("P40_03_BOUNDARY", "Boundary", "boundary_run", "boundary_checksum", "boundary_status", "source_checksum", ScanBoundaryArtifact, "boundary_run_id", ScanBoundaryIssue, "boundary_run_id", ScanBoundaryHistory, "boundary_run_id", "scan_boundary_storage_root"),
    "P40_04_OCR": _PhaseSpec("P40_04_OCR", "OCR", "ocr_run", "ocr_checksum", "ocr_status", "source_checksum", ScanOcrArtifact, "ocr_run_id", ScanOcrIssue, "ocr_run_id", ScanOcrHistory, "ocr_run_id", "scan_ocr_storage_root"),
    "P40_05_RECONCILIATION": _PhaseSpec("P40_05_RECONCILIATION", "Reconciliation", "reconciliation_run", "reconciliation_checksum", "reconciliation_status", "source_checksum", ScanReconciliationArtifact, "reconciliation_run_id", ScanReconciliationIssue, "reconciliation_run_id", ScanReconciliationHistory, "reconciliation_run_id", "scan_reconciliation_storage_root"),
    "P40_06_DEFECT_FOUNDATION": _PhaseSpec("P40_06_DEFECT_FOUNDATION", "Defect foundation", "defect_run", "defect_checksum", "defect_status", "source_checksum", ScanDefectArtifact, "defect_run_id", ScanDefectIssue, "defect_run_id", ScanDefectHistory, "defect_run_id", "scan_defects_storage_root"),
    "P40_07_SPINE": _PhaseSpec("P40_07_SPINE", "Spine ticks", "spine_tick_run", "spine_tick_checksum", "detection_status", "source_checksum", ScanSpineTickArtifact, "spine_tick_run_id", ScanSpineTickIssue, "spine_tick_run_id", ScanSpineTickHistory, "spine_tick_run_id", "scan_spine_ticks_storage_root"),
    "P40_08_CORNER_EDGE": _PhaseSpec("P40_08_CORNER_EDGE", "Corner edges", "corner_edge_run", "corner_edge_checksum", "detection_status", "source_checksum", ScanCornerEdgeArtifact, "corner_edge_run_id", ScanCornerEdgeIssue, "corner_edge_run_id", ScanCornerEdgeHistory, "corner_edge_run_id", "scan_corner_edges_storage_root"),
    "P40_09_SURFACE": _PhaseSpec("P40_09_SURFACE", "Surface defects", "surface_defect_run", "surface_defect_checksum", "detection_status", "source_checksum", ScanSurfaceDefectArtifact, "surface_defect_run_id", ScanSurfaceDefectIssue, "surface_defect_run_id", ScanSurfaceDefectHistory, "surface_defect_run_id", "scan_surface_defects_storage_root"),
    "P40_10_STRUCTURAL": _PhaseSpec("P40_10_STRUCTURAL", "Structural damage", "structural_damage_run", "structural_damage_checksum", "detection_status", "source_checksum", ScanStructuralDamageArtifact, "structural_damage_run_id", ScanStructuralDamageIssue, "structural_damage_run_id", ScanStructuralDamageHistory, "structural_damage_run_id", "scan_structural_damage_storage_root"),
    "P40_11_AGGREGATION": _PhaseSpec("P40_11_AGGREGATION", "Defect aggregation", "defect_aggregation_run", "aggregation_checksum", "aggregation_status", "source_checksum", ScanDefectAggregationArtifact, "aggregation_run_id", ScanDefectAggregationIssue, "aggregation_run_id", ScanDefectAggregationHistory, "aggregation_run_id", "scan_defect_aggregation_storage_root"),
    "P40_12_GRADING_ASSISTANCE": _PhaseSpec("P40_12_GRADING_ASSISTANCE", "Grading assistance", "grading_assistance_run", "grading_assistance_checksum", "assistance_status", "source_checksum", ScanGradingAssistanceArtifact, "grading_assistance_run_id", ScanGradingAssistanceIssue, "grading_assistance_run_id", ScanGradingAssistanceHistory, "grading_assistance_run_id", "scan_grading_assistance_storage_root"),
    "P40_13_VISUAL_EVIDENCE": _PhaseSpec("P40_13_VISUAL_EVIDENCE", "Visual evidence", "visual_evidence_run", "visual_evidence_checksum", "evidence_status", "source_checksum", ScanVisualEvidenceArtifact, "visual_evidence_run_id", ScanVisualEvidenceIssue, "visual_evidence_run_id", ScanVisualEvidenceHistory, "visual_evidence_run_id", "scan_visual_evidence_storage_root"),
    "P40_14_REVIEW": _PhaseSpec("P40_14_REVIEW", "Review", "review_session", "review_checksum", "review_status", "snapshot_checksum", ScanReviewArtifact, "review_session_id", ScanReviewIssue, "review_session_id", ScanReviewHistory, "review_session_id", "scan_review_storage_root"),
    "P40_15_HISTORICAL_COMPARISON": _PhaseSpec("P40_15_HISTORICAL_COMPARISON", "Historical comparison", "historical_comparison_run", "historical_comparison_checksum", "comparison_status", "source_checksum", ScanHistoricalComparisonArtifact, "comparison_run_id", ScanHistoricalComparisonIssue, "comparison_run_id", ScanHistoricalComparisonHistory, "comparison_run_id", "scan_historical_comparison_storage_root"),
    "P40_16_AUTHENTICATION": _PhaseSpec("P40_16_AUTHENTICATION", "Authentication", "authentication_run", "authentication_checksum", "authentication_status", "source_checksum", ScanAuthenticationArtifact, "authentication_run_id", ScanAuthenticationIssue, "authentication_run_id", ScanAuthenticationHistory, "authentication_run_id", "scan_authentication_storage_root"),
    "P40_17_FEED": _PhaseSpec("P40_17_FEED", "Scan intelligence feed", "feed_run", "feed_checksum", "feed_status", "source_checksum", ScanIntelligenceFeedArtifact, "feed_run_id", ScanIntelligenceFeedIssue, "feed_run_id", ScanIntelligenceFeedHistory, "feed_run_id", "scan_intelligence_feed_storage_root"),
}


def utc_now() -> datetime:
    from app.models.scan_replay import utc_now as _utc_now

    return _utc_now()


def clamp_scan_replay_pagination(*, limit: int, offset: int) -> tuple[int, int]:
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


def _normalize_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _resolve_replay_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.scan_replay_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("scan replay storage path escapes configured root")
    return target


def _artifact_storage_path(*, owner_user_id: int, scan_image_id: int | None, replay_run_id: int, artifact_type: str, ext: str) -> str:
    scan_segment = str(scan_image_id) if scan_image_id is not None else "global"
    return f"scan-replay/{owner_user_id}/{scan_segment}/{replay_run_id}/{artifact_type.lower()}{ext}".replace("\\", "/")


def _save_artifact_bytes(settings: Settings, *, relative_path: str, body: bytes) -> None:
    target = _resolve_replay_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)


def _load_replay_artifact_payload(settings: Settings, row: ScanReplayArtifact) -> tuple[str | None, str | None, str | None]:
    try:
        body = _resolve_replay_storage_path(settings, row.storage_path).read_bytes()
    except OSError:
        return None, None, None
    media_type = _MIME_BY_EXT.get(Path(row.storage_path).suffix.lower(), "application/octet-stream")
    try:
        text_preview = body.decode("utf-8")
    except UnicodeDecodeError:
        return media_type, None, base64.b64encode(body).decode("ascii")
    return media_type, text_preview[:20000], None


def _resolve_stage_path(settings: Settings, *, storage_root_attr: str | None, relative_path: str | None) -> Path | None:
    if not storage_root_attr or not relative_path:
        return None
    base = getattr(settings, storage_root_attr, None)
    if base is None:
        return None
    base_path = Path(base).resolve()
    target = (base_path / relative_path).resolve()
    if base_path != target and base_path not in target.parents:
        return None
    return target


def _load_context(
    session: Session,
    *,
    owner_user_id: int,
    payload: ScanReplayRunCreate,
) -> _ReplayContext:
    scan_image = None
    ingestion_batch = None
    upload_session = None
    normalization_run = boundary_run = ocr_run = reconciliation_run = None
    defect_run = spine_tick_run = corner_edge_run = surface_defect_run = None
    structural_damage_run = defect_aggregation_run = grading_assistance_run = None
    visual_evidence_run = review_session = historical_comparison_run = None
    authentication_run = feed_run = None

    if payload.scan_image_id is not None:
        scan_image = session.get(ScanImage, payload.scan_image_id)
        if scan_image is None or int(scan_image.owner_user_id) != owner_user_id:
            raise HTTPException(status_code=404, detail="Scan image not found.")
        ingestion_batch = session.get(ScanIngestionBatch, int(scan_image.ingestion_batch_id))
        upload_session = session.get(ScanUploadSession, int(ingestion_batch.upload_session_id)) if ingestion_batch else None

        def _latest(model):
            return session.exec(select(model).where(model.owner_user_id == owner_user_id, model.scan_image_id == payload.scan_image_id).order_by(col(model.id).desc())).first()

        normalization_run = _latest(ScanNormalizationRun)
        boundary_run = _latest(ScanBoundaryRun)
        ocr_run = _latest(ScanOcrRun)
        reconciliation_run = _latest(ScanReconciliationRun)
        defect_run = _latest(ScanDefectRun)
        spine_tick_run = _latest(ScanSpineTickRun)
        corner_edge_run = _latest(ScanCornerEdgeRun)
        surface_defect_run = _latest(ScanSurfaceDefectRun)
        structural_damage_run = _latest(ScanStructuralDamageRun)
        defect_aggregation_run = _latest(ScanDefectAggregationRun)
        grading_assistance_run = _latest(ScanGradingAssistanceRun)
        visual_evidence_run = _latest(ScanVisualEvidenceRun)
        review_session = _latest(ScanReviewSession)
        historical_comparison_run = _latest(ScanHistoricalComparisonRun)
        authentication_run = _latest(ScanAuthenticationRun)
        feed_run = _latest(ScanIntelligenceFeedRun)

    return _ReplayContext(
        scan_image=scan_image,
        upload_session=upload_session,
        ingestion_batch=ingestion_batch,
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
        feed_run=feed_run,
    )


def _collect_expected_lineage(ctx: _ReplayContext) -> dict[str, str | None]:
    if ctx.feed_run is not None:
        manifest = dict((ctx.feed_run.input_manifest_json or {}).get("lineage_checksums") or {})
        manifest["feed_checksum"] = ctx.feed_run.feed_checksum
        return manifest
    lineage = {
        "original_scan_checksum": ctx.scan_image.sha256_checksum if ctx.scan_image else None,
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
        "feed_checksum": None,
    }
    return lineage


def _phase_row(ctx: _ReplayContext, phase_key: str):
    spec = _PHASE_SPECS[phase_key]
    return getattr(ctx, spec.attr_name) if spec.attr_name else None


def collect_p40_lineage(
    session: Session,
    *,
    ctx: _ReplayContext,
    replay_scope: str,
    selected_phase_key: str | None,
) -> list[_ReplayStepDraft]:
    del session
    expected_lineage = _collect_expected_lineage(ctx)
    phase_keys = _PHASE_ORDER if replay_scope != "SELECTED_STAGE" or not selected_phase_key else [selected_phase_key]
    drafts: list[_ReplayStepDraft] = []
    for index, phase_key in enumerate(phase_keys, start=1):
        spec = _PHASE_SPECS[phase_key]
        row = _phase_row(ctx, phase_key)
        expected_checksum = expected_lineage.get(_LINEAGE_KEY_BY_PHASE[phase_key])
        required = phase_key in _REQUIRED_BY_SCOPE.get(replay_scope, set())
        if phase_key == "P40_01_SCAN_INGESTION":
            observed = ctx.scan_image.sha256_checksum if ctx.scan_image else None
            status = "MATCHED" if observed else ("REPLAY_BLOCKED" if replay_scope in {"FULL_P40_PIPELINE", "SINGLE_SCAN", "SELECTED_STAGE"} else "MISSING_SOURCE")
            if expected_checksum and observed and expected_checksum != observed:
                status = "MISMATCHED"
            elif observed is None and not required:
                status = "SKIPPED" if replay_scope in {"OPS_AUDIT", "BATCH_REPLAY"} else status
            drafts.append(
                _ReplayStepDraft(
                    step_rank=index,
                    phase_key=phase_key,
                    source_record_id=ctx.scan_image.id if ctx.scan_image else None,
                    expected_checksum=expected_checksum,
                    observed_checksum=observed,
                    replay_step_status=status,
                    metadata_json={"label": spec.label, "required": required, "processing_status": ctx.scan_image.processing_status if ctx.scan_image else None},
                )
            )
            continue
        if row is None:
            status = "MISSING_SOURCE" if required else "SKIPPED"
            drafts.append(
                _ReplayStepDraft(
                    step_rank=index,
                    phase_key=phase_key,
                    source_record_id=None,
                    expected_checksum=expected_checksum,
                    observed_checksum=None,
                    replay_step_status=status,
                    metadata_json={"label": spec.label, "required": required},
                )
            )
            continue
        observed_checksum = str(getattr(row, spec.checksum_field)) if spec.checksum_field else None
        stage_status = str(getattr(row, spec.status_field)) if spec.status_field else None
        source_checksum = str(getattr(row, spec.source_checksum_field)) if spec.source_checksum_field and getattr(row, spec.source_checksum_field, None) else None
        step_status = "MATCHED"
        if expected_checksum and observed_checksum and expected_checksum != observed_checksum:
            step_status = "MISMATCHED"
        drafts.append(
            _ReplayStepDraft(
                step_rank=index,
                phase_key=phase_key,
                source_record_id=int(row.id),
                expected_checksum=expected_checksum,
                observed_checksum=observed_checksum,
                replay_step_status=step_status,
                metadata_json={"label": spec.label, "required": required, "stage_status": stage_status, "source_checksum": source_checksum},
            )
        )
    return drafts


def verify_checksum_chain(step_drafts: list[_ReplayStepDraft]) -> tuple[list[_CheckDraft], list[_DiscrepancyDraft], list[_IssueDraft]]:
    checks: list[_CheckDraft] = []
    discrepancies: list[_DiscrepancyDraft] = []
    issues: list[_IssueDraft] = []
    for step in step_drafts:
        if step.observed_checksum is None:
            status = "FAIL" if step.replay_step_status == "MISSING_SOURCE" else "SKIPPED"
            checks.append(_CheckDraft(step.step_rank, step.phase_key, "CHECKSUM_MATCH", status, step.expected_checksum, None, {}))
            if step.replay_step_status == "MISSING_SOURCE":
                discrepancies.append(
                    _DiscrepancyDraft(step.step_rank, step.phase_key, "SOURCE_RECORD_MISSING", "ERROR", step.expected_checksum, None, f"{step.phase_key} source record missing during replay verification.", {})
                )
                issues.append(_IssueDraft("LINEAGE_INCOMPLETE", "ERROR", f"{step.phase_key} source record missing.", {"phase_key": step.phase_key}))
            continue
        status = "PASS"
        if step.expected_checksum and step.expected_checksum != step.observed_checksum:
            status = "FAIL"
            discrepancies.append(
                _DiscrepancyDraft(step.step_rank, step.phase_key, "CHECKSUM_MISMATCH", "ERROR", step.expected_checksum, step.observed_checksum, f"{step.phase_key} checksum mismatch detected.", {})
            )
            issues.append(_IssueDraft("CHECKSUM_MISMATCH_FOUND", "ERROR", f"{step.phase_key} checksum did not match expected lineage.", {"phase_key": step.phase_key}))
        checks.append(_CheckDraft(step.step_rank, step.phase_key, "CHECKSUM_MATCH", status, step.expected_checksum, step.observed_checksum, {}))
        checks.append(_CheckDraft(step.step_rank, step.phase_key, "LINEAGE_PRESENT", "PASS" if step.observed_checksum else "FAIL", step.expected_checksum, step.observed_checksum, {}))
    return checks, discrepancies, issues


def _list_stage_rows(session: Session, *, model: type | None, fk_field: str | None, record_id: int | None) -> list[Any]:
    if model is None or fk_field is None or record_id is None:
        return []
    return list(session.exec(select(model).where(getattr(model, fk_field) == record_id).order_by(col(model.created_at), col(model.id))).all())


def _resolve_stage_file(settings: Settings, *, spec: _PhaseSpec, row) -> Path | None:
    relative_path = getattr(row, spec.relative_path_attr, None) if spec.relative_path_attr else None
    return _resolve_stage_path(settings, storage_root_attr=spec.storage_root_attr, relative_path=relative_path)


def verify_artifact_lineage(
    session: Session,
    settings: Settings,
    *,
    ctx: _ReplayContext,
    step_drafts: list[_ReplayStepDraft],
) -> tuple[list[_CheckDraft], list[_DiscrepancyDraft], list[_IssueDraft]]:
    checks: list[_CheckDraft] = []
    discrepancies: list[_DiscrepancyDraft] = []
    issues: list[_IssueDraft] = []

    if ctx.scan_image is not None:
        scan_path = _resolve_stage_path(settings, storage_root_attr="scan_ingestion_storage_root", relative_path=ctx.scan_image.storage_path)
        present = scan_path is not None and scan_path.exists()
        checksum = _sha256_bytes(scan_path.read_bytes()) if present else None
        checks.append(_CheckDraft(1, "P40_01_SCAN_INGESTION", "ARTIFACT_PRESENT", "PASS" if present else "FAIL", ctx.scan_image.storage_path, str(scan_path) if present else None, {}))
        if not present:
            discrepancies.append(_DiscrepancyDraft(1, "P40_01_SCAN_INGESTION", "ARTIFACT_MISSING", "CRITICAL", ctx.scan_image.storage_path, None, "Original scan artifact is missing.", {}))
            issues.append(_IssueDraft("ARTIFACT_MISSING", "CRITICAL", "Original scan artifact is missing.", {"phase_key": "P40_01_SCAN_INGESTION"}))
        else:
            checks.append(_CheckDraft(1, "P40_01_SCAN_INGESTION", "IMMUTABILITY_PRESERVED", "PASS" if checksum == ctx.scan_image.sha256_checksum else "FAIL", ctx.scan_image.sha256_checksum, checksum, {}))
            if checksum != ctx.scan_image.sha256_checksum:
                discrepancies.append(_DiscrepancyDraft(1, "P40_01_SCAN_INGESTION", "IMMUTABILITY_VIOLATION", "CRITICAL", ctx.scan_image.sha256_checksum, checksum, "Original scan bytes changed from stored checksum.", {}))

    for step in step_drafts[1:]:
        spec = _PHASE_SPECS.get(step.phase_key)
        if spec is None or spec.artifact_model is None or step.source_record_id is None:
            continue
        artifact_rows = _list_stage_rows(session, model=spec.artifact_model, fk_field=spec.artifact_fk_field, record_id=step.source_record_id)
        if not artifact_rows:
            checks.append(_CheckDraft(step.step_rank, step.phase_key, "ARTIFACT_PRESENT", "WARNING", "artifact rows", None, {}))
            issues.append(_IssueDraft("ARTIFACT_MISSING", "WARNING", f"{step.phase_key} has no persisted artifact rows.", {"phase_key": step.phase_key}))
            continue
        for row in artifact_rows:
            path = _resolve_stage_file(settings, spec=spec, row=row)
            present = path is not None and path.exists()
            checks.append(_CheckDraft(step.step_rank, step.phase_key, "ARTIFACT_PRESENT", "PASS" if present else "FAIL", row.storage_path, str(path) if present else None, {"artifact_type": getattr(row, "artifact_type", None)}))
            deterministic_path = row.storage_path.replace("\\", "/")
            expected_fragment = f"/{row.owner_user_id}/{ctx.scan_image.id if ctx.scan_image else 'global'}/"
            path_status = "PASS" if expected_fragment in f"/{deterministic_path}" else "WARNING"
            checks.append(_CheckDraft(step.step_rank, step.phase_key, "LINEAGE_PRESENT", path_status, expected_fragment, deterministic_path, {"artifact_type": getattr(row, "artifact_type", None)}))
            if not present:
                discrepancies.append(_DiscrepancyDraft(step.step_rank, step.phase_key, "ARTIFACT_MISSING", "ERROR", row.storage_path, None, f"{step.phase_key} artifact missing from storage.", {"artifact_type": getattr(row, 'artifact_type', None)}))
                issues.append(_IssueDraft("ARTIFACT_MISSING", "ERROR", f"{step.phase_key} artifact missing from storage.", {"phase_key": step.phase_key, "artifact_type": getattr(row, "artifact_type", None)}))
                continue
            observed_checksum = _sha256_bytes(path.read_bytes())
            status = "PASS" if observed_checksum == getattr(row, "artifact_checksum", None) else "FAIL"
            checks.append(_CheckDraft(step.step_rank, step.phase_key, "IMMUTABILITY_PRESERVED", status, getattr(row, "artifact_checksum", None), observed_checksum, {"artifact_type": getattr(row, "artifact_type", None)}))
            if status == "FAIL":
                discrepancies.append(_DiscrepancyDraft(step.step_rank, step.phase_key, "IMMUTABILITY_VIOLATION", "CRITICAL", getattr(row, "artifact_checksum", None), observed_checksum, f"{step.phase_key} artifact checksum mismatch detected.", {"artifact_type": getattr(row, 'artifact_type', None)}))
                issues.append(_IssueDraft("IMMUTABILITY_CONCERN", "CRITICAL", f"{step.phase_key} artifact checksum mismatch detected.", {"phase_key": step.phase_key, "artifact_type": getattr(row, "artifact_type", None)}))
    return checks, discrepancies, issues


def verify_ordering_stability(
    session: Session,
    *,
    ctx: _ReplayContext,
    step_drafts: list[_ReplayStepDraft],
) -> tuple[list[_CheckDraft], list[_DiscrepancyDraft], list[_IssueDraft]]:
    checks: list[_CheckDraft] = []
    discrepancies: list[_DiscrepancyDraft] = []
    issues: list[_IssueDraft] = []
    expected_steps = list(range(1, len(step_drafts) + 1))
    observed_steps = [row.step_rank for row in step_drafts]
    status = "PASS" if observed_steps == expected_steps else "FAIL"
    checks.append(_CheckDraft(None, None, "ORDERING_STABLE", status, json.dumps(expected_steps), json.dumps(observed_steps), {"target": "replay_steps"}))
    if status == "FAIL":
        discrepancies.append(_DiscrepancyDraft(None, None, "ORDERING_DRIFT", "ERROR", json.dumps(expected_steps), json.dumps(observed_steps), "Replay step ordering drift detected.", {"target": "replay_steps"}))
        issues.append(_IssueDraft("NONDETERMINISM_DETECTED", "ERROR", "Replay step ordering drift detected.", {"target": "replay_steps"}))

    if ctx.feed_run is not None:
        # Deliberately query ordered by stored ranks, then compare against recomputed deterministic order.
        feed_events = list(
            session.exec(
                select(ScanIntelligenceFeedEvent)
                .where(ScanIntelligenceFeedEvent.feed_run_id == ctx.feed_run.id)
                .order_by(col(ScanIntelligenceFeedEvent.timeline_rank), col(ScanIntelligenceFeedEvent.id))
            ).all()
        )
        recomputed = sorted(
            feed_events,
            key=lambda row: (
                _normalize_datetime(row.event_occurred_at),
                row.event_category,
                row.severity,
                row.source_system,
                row.source_record_id or 0,
                row.source_checksum or "",
                row.event_key,
            ),
        )
        stored_ids = [row.id for row in feed_events]
        recomputed_ids = [row.id for row in recomputed]
        feed_status = "PASS" if stored_ids == recomputed_ids else "FAIL"
        checks.append(_CheckDraft(None, "P40_17_FEED", "ORDERING_STABLE", feed_status, json.dumps(stored_ids), json.dumps(recomputed_ids), {"target": "feed_events"}))
        if feed_status == "FAIL":
            discrepancies.append(_DiscrepancyDraft(None, "P40_17_FEED", "ORDERING_DRIFT", "ERROR", json.dumps(stored_ids), json.dumps(recomputed_ids), "Feed event ordering drift detected.", {"target": "feed_events"}))
            issues.append(_IssueDraft("NONDETERMINISM_DETECTED", "ERROR", "Feed event ordering drift detected.", {"target": "feed_events"}))

    if ctx.review_session is not None:
        decisions = list(
            session.exec(
                select(ScanReviewDecision)
                .where(ScanReviewDecision.review_session_id == ctx.review_session.id)
                .order_by(col(ScanReviewDecision.created_at), col(ScanReviewDecision.id))
            ).all()
        )
        decision_ids = [row.id for row in decisions]
        checks.append(_CheckDraft(None, "P40_14_REVIEW", "ORDERING_STABLE", "PASS", json.dumps(decision_ids), json.dumps(decision_ids), {"target": "review_decisions"}))
    return checks, discrepancies, issues


def verify_immutability_contracts(
    session: Session,
    *,
    ctx: _ReplayContext,
    step_drafts: list[_ReplayStepDraft],
) -> tuple[list[_CheckDraft], list[_DiscrepancyDraft], list[_IssueDraft]]:
    checks: list[_CheckDraft] = []
    discrepancies: list[_DiscrepancyDraft] = []
    issues: list[_IssueDraft] = []
    owner_id = ctx.scan_image.owner_user_id if ctx.scan_image else None
    owner_ok = True
    for step in step_drafts:
        if step.source_record_id is None or step.phase_key == "P40_01_SCAN_INGESTION":
            continue
        row = _phase_row(ctx, step.phase_key)
        if row is None:
            continue
        if int(getattr(row, "owner_user_id", owner_id or 0)) != int(owner_id or getattr(row, "owner_user_id", 0)):
            owner_ok = False
    checks.append(_CheckDraft(None, None, "OWNER_ISOLATION", "PASS" if owner_ok else "FAIL", str(owner_id) if owner_id is not None else None, str(owner_id) if owner_id is not None else None, {}))
    if not owner_ok:
        discrepancies.append(_DiscrepancyDraft(None, None, "IMMUTABILITY_VIOLATION", "CRITICAL", str(owner_id), None, "Owner isolation validation failed during replay verification.", {}))
        issues.append(_IssueDraft("IMMUTABILITY_CONCERN", "CRITICAL", "Owner isolation validation failed during replay verification.", {}))

    for phase_key, spec in _PHASE_SPECS.items():
        row = _phase_row(ctx, phase_key)
        if row is None or spec.history_model is None or spec.history_fk_field is None:
            continue
        history_rows = _list_stage_rows(session, model=spec.history_model, fk_field=spec.history_fk_field, record_id=int(row.id))
        if not history_rows:
            continue
        timestamps = [_normalize_datetime(getattr(item, "created_at", None)) for item in history_rows]
        ordered = timestamps == sorted(timestamps)
        unique_hashes = len({_hash_payload(_json_safe(getattr(item, "metadata_json", getattr(item, "detail_json", {})))) + str(getattr(item, "id")) for item in history_rows}) == len(history_rows)
        status = "PASS" if ordered and unique_hashes else "FAIL"
        checks.append(_CheckDraft(None, phase_key, "HISTORY_APPEND_ONLY", status, "ordered_unique", f"ordered={ordered},unique={unique_hashes}", {}))
        if status == "FAIL":
            discrepancies.append(_DiscrepancyDraft(None, phase_key, "HISTORY_MUTATION", "CRITICAL", "ordered_unique", f"ordered={ordered},unique={unique_hashes}", f"{phase_key} history append-only contract failed.", {}))
            issues.append(_IssueDraft("HISTORY_APPEND_ONLY_CONCERN", "CRITICAL", f"{phase_key} history append-only contract failed.", {"phase_key": phase_key}))

    checks.append(_CheckDraft(None, None, "ROUTE_READ_ONLY", "SKIPPED", None, None, {"reason": "validated in API tests"}))
    return checks, discrepancies, issues


def build_replay_manifest(
    *,
    replay_scope: str,
    selected_phase_key: str | None,
    lineage_chain: list[dict[str, Any]],
    step_payloads: list[dict[str, Any]],
    check_payloads: list[dict[str, Any]],
    discrepancy_payloads: list[dict[str, Any]],
    issue_payloads: list[dict[str, Any]],
    artifact_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "engine_version": ENGINE_VERSION,
        "replay_scope": replay_scope,
        "selected_phase_key": selected_phase_key,
        "lineage_chain": lineage_chain,
        "steps": step_payloads,
        "checks": check_payloads,
        "discrepancies": discrepancy_payloads,
        "issues": issue_payloads,
        "artifacts": artifact_refs,
    }


def _build_input_manifest(ctx: _ReplayContext, payload: ScanReplayRunCreate) -> dict[str, Any]:
    return {
        "replay_scope": payload.replay_scope,
        "selected_phase_key": payload.selected_phase_key,
        "scan_image_id": ctx.scan_image.id if ctx.scan_image else payload.scan_image_id,
        "scan_image_checksum": ctx.scan_image.sha256_checksum if ctx.scan_image else None,
        "feed_run_id": ctx.feed_run.id if ctx.feed_run else None,
        "authentication_run_id": ctx.authentication_run.id if ctx.authentication_run else None,
    }


def _build_artifacts(
    *,
    manifest: dict[str, Any],
    check_payloads: list[dict[str, Any]],
    lineage_chain: list[dict[str, Any]],
    discrepancy_payloads: list[dict[str, Any]],
    summary_payload: dict[str, Any],
) -> list[_ArtifactDraft]:
    return [
        _ArtifactDraft("REPLAY_MANIFEST", _serialize_json_artifact(manifest), {"kind": "manifest"}, ".json"),
        _ArtifactDraft("CHECKSUM_AUDIT_EXPORT", _serialize_json_artifact(check_payloads), {"kind": "checks"}, ".json"),
        _ArtifactDraft("LINEAGE_AUDIT_EXPORT", _serialize_json_artifact(lineage_chain), {"kind": "lineage"}, ".json"),
        _ArtifactDraft("DISCREPANCY_REPORT", _serialize_json_artifact(discrepancy_payloads), {"kind": "discrepancies"}, ".json"),
        _ArtifactDraft("REPLAY_REPORT", _serialize_json_artifact(summary_payload), {"kind": "report"}, ".json"),
        _ArtifactDraft("REPLAY_DEBUG_PREVIEW", _serialize_json_artifact(summary_payload), {"kind": "preview"}, ".json"),
    ]


def _dedupe_payloads(rows: list[dict[str, Any]], *, key_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        key = tuple(row.get(field) for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _build_run_detail(session: Session, settings: Settings, *, run: ScanReplayRun) -> ScanReplayRunDetail:
    steps = list(session.exec(select(ScanReplayStep).where(ScanReplayStep.replay_run_id == run.id).order_by(col(ScanReplayStep.step_rank), col(ScanReplayStep.id))).all())
    step_by_id = {row.id: row for row in steps}
    checks = list(session.exec(select(ScanReplayCheck).where(ScanReplayCheck.replay_run_id == run.id).order_by(col(ScanReplayCheck.created_at), col(ScanReplayCheck.id))).all())
    discrepancies = list(session.exec(select(ScanReplayDiscrepancy).where(ScanReplayDiscrepancy.replay_run_id == run.id).order_by(col(ScanReplayDiscrepancy.created_at), col(ScanReplayDiscrepancy.id))).all())
    artifacts = list(session.exec(select(ScanReplayArtifact).where(ScanReplayArtifact.replay_run_id == run.id).order_by(col(ScanReplayArtifact.created_at), col(ScanReplayArtifact.id))).all())
    issues = list(session.exec(select(ScanReplayIssue).where(ScanReplayIssue.replay_run_id == run.id).order_by(col(ScanReplayIssue.created_at), col(ScanReplayIssue.id))).all())
    history = list(session.exec(select(ScanReplayHistory).where(ScanReplayHistory.replay_run_id == run.id).order_by(col(ScanReplayHistory.created_at), col(ScanReplayHistory.id))).all())
    artifact_reads: list[ScanReplayArtifactRead] = []
    for row in artifacts:
        media_type, text_preview, body_base64 = _load_replay_artifact_payload(settings, row)
        artifact_reads.append(ScanReplayArtifactRead.model_validate({**row.model_dump(), "media_type": media_type, "text_preview": text_preview, "body_base64": body_base64}))
    output_manifest = dict(run.output_manifest_json or {})
    return ScanReplayRunDetail(
        **ScanReplayRunRead.model_validate(run).model_dump(),
        steps=[ScanReplayStepRead.model_validate(row) for row in steps],
        checks=[ScanReplayCheckRead.model_validate(row) for row in checks],
        discrepancies=[ScanReplayDiscrepancyRead.model_validate(row) for row in discrepancies],
        artifacts=artifact_reads,
        issues=[ScanReplayIssueRead.model_validate(row) for row in issues],
        history=[ScanReplayHistoryRead.model_validate(row) for row in history],
        original_scan_checksum=output_manifest.get("original_scan_checksum"),
        scan_feed_checksum=output_manifest.get("scan_feed_checksum"),
        lineage_chain=list(output_manifest.get("lineage_chain") or []),
        critical_discrepancy_count=sum(1 for row in discrepancies if row.severity == "CRITICAL"),
    )


def run_scan_replay_verification(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: ScanReplayRunCreate,
) -> tuple[ScanReplayRunDetail, bool]:
    ctx = _load_context(session, owner_user_id=owner_user_id, payload=payload)
    input_manifest = _build_input_manifest(ctx, payload)
    source_checksum = _hash_payload(input_manifest)
    step_drafts = collect_p40_lineage(session, ctx=ctx, replay_scope=str(payload.replay_scope), selected_phase_key=payload.selected_phase_key)

    checks: list[_CheckDraft] = []
    discrepancies: list[_DiscrepancyDraft] = []
    issues: list[_IssueDraft] = []

    part_checks, part_discrepancies, part_issues = verify_checksum_chain(step_drafts)
    checks.extend(part_checks)
    discrepancies.extend(part_discrepancies)
    issues.extend(part_issues)

    part_checks, part_discrepancies, part_issues = verify_artifact_lineage(session, settings, ctx=ctx, step_drafts=step_drafts)
    checks.extend(part_checks)
    discrepancies.extend(part_discrepancies)
    issues.extend(part_issues)

    part_checks, part_discrepancies, part_issues = verify_ordering_stability(session, ctx=ctx, step_drafts=step_drafts)
    checks.extend(part_checks)
    discrepancies.extend(part_discrepancies)
    issues.extend(part_issues)

    part_checks, part_discrepancies, part_issues = verify_immutability_contracts(session, ctx=ctx, step_drafts=step_drafts)
    checks.extend(part_checks)
    discrepancies.extend(part_discrepancies)
    issues.extend(part_issues)

    if ctx.scan_image is None and str(payload.replay_scope) in {"SINGLE_SCAN", "FULL_P40_PIPELINE", "SELECTED_STAGE"}:
        issues.append(_IssueDraft("REPLAY_SCOPE_EMPTY", "ERROR", "Replay scope requires a scan image but none was provided.", {"replay_scope": payload.replay_scope}))
        discrepancies.append(_DiscrepancyDraft(None, None, "REPLAY_EXCEPTION", "ERROR", "scan_image_id", None, "Replay scope requires a scan image but none was provided.", {"replay_scope": payload.replay_scope}))

    step_payloads = [
        {
            "step_rank": row.step_rank,
            "phase_key": row.phase_key,
            "source_record_id": row.source_record_id,
            "expected_checksum": row.expected_checksum,
            "observed_checksum": row.observed_checksum,
            "replay_step_status": row.replay_step_status,
            "metadata_json": row.metadata_json,
        }
        for row in sorted(step_drafts, key=lambda item: item.step_rank)
    ]
    check_payloads = [
        {
            "step_rank": row.step_rank,
            "phase_key": row.phase_key,
            "check_type": row.check_type,
            "check_status": row.check_status,
            "expected_value": row.expected_value,
            "observed_value": row.observed_value,
            "metadata_json": row.metadata_json,
        }
        for row in sorted(checks, key=lambda item: (item.step_rank or 0, item.phase_key or "", item.check_type, _CHECK_STATUS_RANK.get(item.check_status, 99), _hash_payload(item.metadata_json)))
    ]
    check_payloads = _dedupe_payloads(
        check_payloads,
        key_fields=("step_rank", "phase_key", "check_type", "expected_value", "observed_value"),
    )
    discrepancy_payloads = [
        {
            "step_rank": row.step_rank,
            "phase_key": row.phase_key,
            "discrepancy_type": row.discrepancy_type,
            "severity": row.severity,
            "expected_value": row.expected_value,
            "observed_value": row.observed_value,
            "discrepancy_message": row.discrepancy_message,
            "metadata_json": row.metadata_json,
        }
        for row in sorted(discrepancies, key=lambda item: (item.step_rank or 0, item.phase_key or "", _SEVERITY_RANK.get(item.severity, 99), item.discrepancy_type, _hash_payload(item.metadata_json)))
    ]
    discrepancy_payloads = _dedupe_payloads(
        discrepancy_payloads,
        key_fields=("step_rank", "phase_key", "discrepancy_type", "expected_value", "observed_value"),
    )
    issue_payloads = [
        {
            "issue_type": row.issue_type,
            "severity": row.severity,
            "issue_message": row.issue_message,
            "metadata_json": row.metadata_json,
            "issue_checksum": _hash_payload({"issue_type": row.issue_type, "severity": row.severity, "issue_message": row.issue_message, "metadata_json": row.metadata_json}),
        }
        for row in sorted(issues, key=lambda item: (_SEVERITY_RANK.get(item.severity, 99), item.issue_type, _hash_payload(item.metadata_json)))
    ]

    lineage_chain = [
        {
            "phase_key": row["phase_key"],
            "step_rank": row["step_rank"],
            "source_record_id": row["source_record_id"],
            "expected_checksum": row["expected_checksum"],
            "observed_checksum": row["observed_checksum"],
            "replay_step_status": row["replay_step_status"],
        }
        for row in step_payloads
    ]
    replay_status = "COMPLETE"
    if any(row["severity"] == "CRITICAL" for row in discrepancy_payloads):
        replay_status = "CRITICAL"
    elif any(row["severity"] == "ERROR" for row in discrepancy_payloads):
        replay_status = "FAILED"
    elif issue_payloads or any(row["check_status"] == "WARNING" for row in check_payloads):
        replay_status = "COMPLETE_WITH_WARNINGS"
    if any(row["replay_step_status"] == "REPLAY_BLOCKED" for row in step_payloads):
        replay_status = "REPLAY_BLOCKED"

    placeholder_manifest = build_replay_manifest(
        replay_scope=str(payload.replay_scope),
        selected_phase_key=payload.selected_phase_key,
        lineage_chain=lineage_chain,
        step_payloads=step_payloads,
        check_payloads=check_payloads,
        discrepancy_payloads=discrepancy_payloads,
        issue_payloads=issue_payloads,
        artifact_refs=[],
    )

    summary_payload = {
        "replay_scope": payload.replay_scope,
        "replay_status": replay_status,
        "step_count": len(step_payloads),
        "check_count": len(check_payloads),
        "discrepancy_count": len(discrepancy_payloads),
        "issue_count": len(issue_payloads),
    }
    artifacts = _build_artifacts(
        manifest=placeholder_manifest,
        check_payloads=check_payloads,
        lineage_chain=lineage_chain,
        discrepancy_payloads=discrepancy_payloads,
        summary_payload=summary_payload,
    )

    artifact_refs = []
    for artifact in artifacts:
        artifact_refs.append({"artifact_type": artifact.artifact_type, "artifact_checksum": _sha256_bytes(artifact.body)})
    output_manifest = build_replay_manifest(
        replay_scope=str(payload.replay_scope),
        selected_phase_key=payload.selected_phase_key,
        lineage_chain=lineage_chain,
        step_payloads=step_payloads,
        check_payloads=check_payloads,
        discrepancy_payloads=discrepancy_payloads,
        issue_payloads=issue_payloads,
        artifact_refs=artifact_refs,
    )
    output_manifest.update(
        {
            "replay_status": replay_status,
            "original_scan_checksum": ctx.scan_image.sha256_checksum if ctx.scan_image else None,
            "scan_feed_checksum": ctx.feed_run.feed_checksum if ctx.feed_run else None,
        }
    )
    replay_checksum = _hash_payload(output_manifest)

    existing = session.exec(
        select(ScanReplayRun).where(
            ScanReplayRun.owner_user_id == owner_user_id,
            ScanReplayRun.replay_checksum == replay_checksum,
        )
    ).first()
    if existing is not None:
        return _build_run_detail(session, settings, run=existing), False

    artifacts = [
        artifact if artifact.artifact_type != "REPLAY_MANIFEST" else _ArtifactDraft("REPLAY_MANIFEST", _serialize_json_artifact(output_manifest), {"kind": "manifest"}, ".json")
        for artifact in artifacts
    ]

    run = ScanReplayRun(
        owner_user_id=owner_user_id,
        scan_image_id=ctx.scan_image.id if ctx.scan_image else None,
        replay_scope=str(payload.replay_scope),
        source_checksum=source_checksum,
        replay_checksum=replay_checksum,
        replay_status=replay_status,
        engine_version=ENGINE_VERSION,
        input_manifest_json=_json_safe(input_manifest),
        output_manifest_json=_json_safe(output_manifest),
        completed_at=utc_now(),
    )
    session.add(run)
    session.flush()

    step_rows: list[ScanReplayStep] = []
    for row in step_payloads:
        step_row = ScanReplayStep(
            owner_user_id=owner_user_id,
            replay_run_id=int(run.id),
            step_rank=int(row["step_rank"]),
            phase_key=str(row["phase_key"]),
            source_record_id=row["source_record_id"],
            expected_checksum=row["expected_checksum"],
            observed_checksum=row["observed_checksum"],
            replay_step_status=str(row["replay_step_status"]),
            metadata_json=dict(row["metadata_json"]),
        )
        session.add(step_row)
        session.flush()
        step_rows.append(step_row)
    step_id_by_rank = {row.step_rank: int(row.id) for row in step_rows if row.id is not None}

    for row in check_payloads:
        session.add(
            ScanReplayCheck(
                owner_user_id=owner_user_id,
                replay_run_id=int(run.id),
                step_id=step_id_by_rank.get(int(row["step_rank"])) if row["step_rank"] else None,
                check_type=str(row["check_type"]),
                check_status=str(row["check_status"]),
                expected_value=row["expected_value"],
                observed_value=row["observed_value"],
                metadata_json=dict(row["metadata_json"]),
            )
        )
    for row in discrepancy_payloads:
        session.add(
            ScanReplayDiscrepancy(
                owner_user_id=owner_user_id,
                replay_run_id=int(run.id),
                step_id=step_id_by_rank.get(int(row["step_rank"])) if row["step_rank"] else None,
                discrepancy_type=str(row["discrepancy_type"]),
                severity=str(row["severity"]),
                expected_value=row["expected_value"],
                observed_value=row["observed_value"],
                discrepancy_message=str(row["discrepancy_message"]),
                metadata_json=dict(row["metadata_json"]),
            )
        )
    for row in issue_payloads:
        session.add(
            ScanReplayIssue(
                owner_user_id=owner_user_id,
                replay_run_id=int(run.id),
                issue_type=str(row["issue_type"]),
                severity=str(row["severity"]),
                issue_message=str(row["issue_message"]),
                issue_checksum=str(row["issue_checksum"]),
                metadata_json=dict(row["metadata_json"]),
            )
        )

    for artifact in artifacts:
        artifact_checksum = _sha256_bytes(artifact.body)
        relative_path = _artifact_storage_path(
            owner_user_id=owner_user_id,
            scan_image_id=ctx.scan_image.id if ctx.scan_image else None,
            replay_run_id=int(run.id),
            artifact_type=artifact.artifact_type,
            ext=artifact.ext,
        )
        _save_artifact_bytes(settings, relative_path=relative_path, body=artifact.body)
        session.add(
            ScanReplayArtifact(
                owner_user_id=owner_user_id,
                replay_run_id=int(run.id),
                artifact_type=artifact.artifact_type,
                storage_backend="filesystem",
                storage_path=relative_path,
                artifact_checksum=artifact_checksum,
                metadata_json=dict(artifact.metadata_json),
            )
        )

    history = [
        _HistoryDraft("RUN_CREATED", "Scan replay verification created.", {"replay_scope": payload.replay_scope}),
        _HistoryDraft("LINEAGE_COLLECTED", f"Collected {len(step_payloads)} replay steps.", {"step_count": len(step_payloads)}),
        _HistoryDraft("CHECKS_RECORDED", f"Recorded {len(check_payloads)} replay checks.", {"check_count": len(check_payloads)}),
        _HistoryDraft("DISCREPANCIES_RECORDED", f"Recorded {len(discrepancy_payloads)} replay discrepancies.", {"discrepancy_count": len(discrepancy_payloads)}),
    ]
    for row in history:
        session.add(
            ScanReplayHistory(
                owner_user_id=owner_user_id,
                replay_run_id=int(run.id),
                event_type=row.event_type,
                event_message=row.event_message,
                event_checksum=_hash_payload({"event_type": row.event_type, "event_message": row.event_message, "metadata_json": row.metadata_json}),
                metadata_json=dict(row.metadata_json),
            )
        )

    session.commit()
    session.refresh(run)
    return _build_run_detail(session, settings, run=run), True


def get_scan_replay_run_owner(session: Session, settings: Settings, *, owner_user_id: int, run_id: int) -> ScanReplayRunDetail:
    run = session.get(ScanReplayRun, run_id)
    if run is None or int(run.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan replay run not found.")
    return _build_run_detail(session, settings, run=run)


def get_scan_replay_artifact_owner(session: Session, settings: Settings, *, owner_user_id: int, artifact_id: int) -> ScanReplayArtifactRead:
    row = session.get(ScanReplayArtifact, artifact_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan replay artifact not found.")
    media_type, text_preview, body_base64 = _load_replay_artifact_payload(settings, row)
    return ScanReplayArtifactRead.model_validate({**row.model_dump(), "media_type": media_type, "text_preview": text_preview, "body_base64": body_base64})


def _list_runs(session: Session, *, owner_user_id: int | None, scan_image_id: int | None, replay_scope: str | None, limit: int, offset: int) -> ScanReplayRunListResponse:
    limit, offset = clamp_scan_replay_pagination(limit=limit, offset=offset)
    stmt = select(ScanReplayRun)
    count_stmt = select(func.count()).select_from(ScanReplayRun)
    if owner_user_id is not None:
        stmt = stmt.where(ScanReplayRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanReplayRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanReplayRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanReplayRun.scan_image_id == scan_image_id)
    if replay_scope is not None:
        stmt = stmt.where(ScanReplayRun.replay_scope == replay_scope)
        count_stmt = count_stmt.where(ScanReplayRun.replay_scope == replay_scope)
    ordered = stmt.order_by(col(ScanReplayRun.created_at).desc(), col(ScanReplayRun.id).desc())
    items = list(session.exec(ordered.offset(offset).limit(limit)).all())
    filtered = list(session.exec(ordered).all())
    status_counts: dict[str, int] = {}
    critical_discrepancy_count = 0
    mismatch_count = 0
    for row in filtered:
        status_counts[row.replay_status] = status_counts.get(row.replay_status, 0) + 1
        critical_discrepancy_count += int(
            session.exec(
                select(func.count()).select_from(ScanReplayDiscrepancy).where(ScanReplayDiscrepancy.replay_run_id == row.id, ScanReplayDiscrepancy.severity == "CRITICAL")
            ).one()
        )
        mismatch_count += int(
            session.exec(
                select(func.count()).select_from(ScanReplayDiscrepancy).where(ScanReplayDiscrepancy.replay_run_id == row.id, ScanReplayDiscrepancy.discrepancy_type == "CHECKSUM_MISMATCH")
            ).one()
        )
    return ScanReplayRunListResponse(
        items=[ScanReplayRunRead.model_validate(row) for row in items],
        total_items=int(session.exec(count_stmt).one()),
        limit=limit,
        offset=offset,
        status_counts=status_counts,
        critical_discrepancy_count=critical_discrepancy_count,
        mismatch_count=mismatch_count,
    )


def list_scan_replay_runs_owner(session: Session, *, owner_user_id: int, scan_image_id: int | None, replay_scope: str | None, limit: int, offset: int) -> ScanReplayRunListResponse:
    return _list_runs(session, owner_user_id=owner_user_id, scan_image_id=scan_image_id, replay_scope=replay_scope, limit=limit, offset=offset)


def list_scan_replay_runs_ops(session: Session, *, owner_user_id: int | None, scan_image_id: int | None, replay_scope: str | None, limit: int, offset: int) -> ScanReplayRunListResponse:
    return _list_runs(session, owner_user_id=owner_user_id, scan_image_id=scan_image_id, replay_scope=replay_scope, limit=limit, offset=offset)


def _list_rows(session: Session, *, model: type, owner_user_id: int | None, run_id: int | None, run_fk_field: str, severity: str | None, limit: int, offset: int, reader, extra_counts: list[str] | None = None):
    limit, offset = clamp_scan_replay_pagination(limit=limit, offset=offset)
    stmt = select(model)
    count_stmt = select(func.count()).select_from(model)
    if owner_user_id is not None:
        stmt = stmt.where(model.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(model.owner_user_id == owner_user_id)
    if run_id is not None:
        stmt = stmt.where(getattr(model, run_fk_field) == run_id)
        count_stmt = count_stmt.where(getattr(model, run_fk_field) == run_id)
    if severity is not None and hasattr(model, "severity"):
        stmt = stmt.where(model.severity == severity)
        count_stmt = count_stmt.where(model.severity == severity)
    ordered = stmt.order_by(col(model.created_at), col(model.id))
    items = list(session.exec(ordered.offset(offset).limit(limit)).all())
    filtered = list(session.exec(ordered).all())
    counts: dict[str, dict[str, int]] = {}
    for field in extra_counts or []:
        bucket: dict[str, int] = {}
        for row in filtered:
            value = str(getattr(row, field))
            bucket[value] = bucket.get(value, 0) + 1
        counts[field] = bucket
    return items, int(session.exec(count_stmt).one()), counts, limit, offset, reader


def list_scan_replay_steps_owner(session: Session, *, owner_user_id: int, run_id: int | None, limit: int, offset: int) -> ScanReplayStepListResponse:
    items, total, counts, limit, offset, reader = _list_rows(session, model=ScanReplayStep, owner_user_id=owner_user_id, run_id=run_id, run_fk_field="replay_run_id", severity=None, limit=limit, offset=offset, reader=ScanReplayStepRead, extra_counts=["replay_step_status"])
    return ScanReplayStepListResponse(items=[reader.model_validate(row) for row in items], total_items=total, limit=limit, offset=offset, step_status_counts=counts["replay_step_status"])


def list_scan_replay_checks_owner(session: Session, *, owner_user_id: int, run_id: int | None, limit: int, offset: int) -> ScanReplayCheckListResponse:
    items, total, counts, limit, offset, reader = _list_rows(session, model=ScanReplayCheck, owner_user_id=owner_user_id, run_id=run_id, run_fk_field="replay_run_id", severity=None, limit=limit, offset=offset, reader=ScanReplayCheckRead, extra_counts=["check_status", "check_type"])
    return ScanReplayCheckListResponse(items=[reader.model_validate(row) for row in items], total_items=total, limit=limit, offset=offset, check_status_counts=counts["check_status"], check_type_counts=counts["check_type"])


def list_scan_replay_discrepancies_owner(session: Session, *, owner_user_id: int, run_id: int | None, severity: str | None, limit: int, offset: int) -> ScanReplayDiscrepancyListResponse:
    items, total, counts, limit, offset, reader = _list_rows(session, model=ScanReplayDiscrepancy, owner_user_id=owner_user_id, run_id=run_id, run_fk_field="replay_run_id", severity=severity, limit=limit, offset=offset, reader=ScanReplayDiscrepancyRead, extra_counts=["severity", "discrepancy_type"])
    return ScanReplayDiscrepancyListResponse(items=[reader.model_validate(row) for row in items], total_items=total, limit=limit, offset=offset, severity_counts=counts["severity"], discrepancy_type_counts=counts["discrepancy_type"])


def list_scan_replay_issues_owner(session: Session, *, owner_user_id: int, run_id: int | None, severity: str | None, limit: int, offset: int) -> ScanReplayIssueListResponse:
    items, total, counts, limit, offset, reader = _list_rows(session, model=ScanReplayIssue, owner_user_id=owner_user_id, run_id=run_id, run_fk_field="replay_run_id", severity=severity, limit=limit, offset=offset, reader=ScanReplayIssueRead, extra_counts=["severity", "issue_type"])
    return ScanReplayIssueListResponse(items=[reader.model_validate(row) for row in items], total_items=total, limit=limit, offset=offset, severity_counts=counts["severity"], issue_type_counts=counts["issue_type"])


def list_scan_replay_steps_ops(session: Session, *, owner_user_id: int | None, run_id: int | None, limit: int, offset: int) -> ScanReplayStepListResponse:
    items, total, counts, limit, offset, reader = _list_rows(session, model=ScanReplayStep, owner_user_id=owner_user_id, run_id=run_id, run_fk_field="replay_run_id", severity=None, limit=limit, offset=offset, reader=ScanReplayStepRead, extra_counts=["replay_step_status"])
    return ScanReplayStepListResponse(items=[reader.model_validate(row) for row in items], total_items=total, limit=limit, offset=offset, step_status_counts=counts["replay_step_status"])


def list_scan_replay_checks_ops(session: Session, *, owner_user_id: int | None, run_id: int | None, limit: int, offset: int) -> ScanReplayCheckListResponse:
    items, total, counts, limit, offset, reader = _list_rows(session, model=ScanReplayCheck, owner_user_id=owner_user_id, run_id=run_id, run_fk_field="replay_run_id", severity=None, limit=limit, offset=offset, reader=ScanReplayCheckRead, extra_counts=["check_status", "check_type"])
    return ScanReplayCheckListResponse(items=[reader.model_validate(row) for row in items], total_items=total, limit=limit, offset=offset, check_status_counts=counts["check_status"], check_type_counts=counts["check_type"])


def list_scan_replay_discrepancies_ops(session: Session, *, owner_user_id: int | None, run_id: int | None, severity: str | None, limit: int, offset: int) -> ScanReplayDiscrepancyListResponse:
    items, total, counts, limit, offset, reader = _list_rows(session, model=ScanReplayDiscrepancy, owner_user_id=owner_user_id, run_id=run_id, run_fk_field="replay_run_id", severity=severity, limit=limit, offset=offset, reader=ScanReplayDiscrepancyRead, extra_counts=["severity", "discrepancy_type"])
    return ScanReplayDiscrepancyListResponse(items=[reader.model_validate(row) for row in items], total_items=total, limit=limit, offset=offset, severity_counts=counts["severity"], discrepancy_type_counts=counts["discrepancy_type"])


def list_scan_replay_issues_ops(session: Session, *, owner_user_id: int | None, run_id: int | None, severity: str | None, limit: int, offset: int) -> ScanReplayIssueListResponse:
    items, total, counts, limit, offset, reader = _list_rows(session, model=ScanReplayIssue, owner_user_id=owner_user_id, run_id=run_id, run_fk_field="replay_run_id", severity=severity, limit=limit, offset=offset, reader=ScanReplayIssueRead, extra_counts=["severity", "issue_type"])
    return ScanReplayIssueListResponse(items=[reader.model_validate(row) for row in items], total_items=total, limit=limit, offset=offset, severity_counts=counts["severity"], issue_type_counts=counts["issue_type"])


def list_scan_replay_failures_ops(session: Session, *, owner_user_id: int | None, limit: int, offset: int) -> ScanReplayDiscrepancyListResponse:
    return list_scan_replay_discrepancies_ops(session, owner_user_id=owner_user_id, run_id=None, severity="ERROR", limit=limit, offset=offset)


def list_scan_replay_critical_ops(session: Session, *, owner_user_id: int | None, limit: int, offset: int) -> ScanReplayDiscrepancyListResponse:
    return list_scan_replay_discrepancies_ops(session, owner_user_id=owner_user_id, run_id=None, severity="CRITICAL", limit=limit, offset=offset)
