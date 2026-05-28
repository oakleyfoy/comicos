from __future__ import annotations

import base64
import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from PIL import Image, ImageDraw, UnidentifiedImageError
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models import (
    ScanBoundaryRun,
    ScanDefectAggregateCluster,
    ScanDefectAggregationRun,
    ScanGradingAssistanceRun,
    ScanHistoricalComparisonArtifact,
    ScanHistoricalComparisonDelta,
    ScanHistoricalComparisonHistory,
    ScanHistoricalComparisonIssue,
    ScanHistoricalComparisonPair,
    ScanHistoricalComparisonRun,
    ScanImage,
    ScanNormalizationArtifact,
    ScanNormalizationRun,
    ScanOcrCandidate,
    ScanOcrRun,
    ScanReconciliationCandidate,
    ScanReconciliationDecision,
    ScanReconciliationRun,
    ScanReviewDecision,
    ScanReviewSession,
    ScanVisualEvidenceRun,
)
from app.schemas.scan_historical_comparison import (
    ScanHistoricalComparisonArtifactRead,
    ScanHistoricalComparisonDeltaListResponse,
    ScanHistoricalComparisonDeltaRead,
    ScanHistoricalComparisonIssueListResponse,
    ScanHistoricalComparisonIssueRead,
    ScanHistoricalComparisonPairListResponse,
    ScanHistoricalComparisonPairRead,
    ScanHistoricalComparisonRunCreate,
    ScanHistoricalComparisonRunDetail,
    ScanHistoricalComparisonRunListResponse,
    ScanHistoricalComparisonRunRead,
    ScanHistoricalComparisonHistoryRead,
)
from app.services.scan_defects import _load_source_preview, _resolve_normalization_artifact_path

ENGINE_VERSION = "P40-15-v1"
_PREVIEW_MAX = 440
_MAX_PRIOR_SCANS = 10
_SEVERITY_SCORES = {"MINOR": 1, "MODERATE": 2, "MAJOR": 3}


@dataclass(frozen=True)
class _IdentityResult:
    identity_key: str | None
    match_basis: str | None
    confidence: float
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _NormalizedBox:
    x_min: float
    y_min: float
    x_max: float
    y_max: float


@dataclass(frozen=True)
class _ClusterComparable:
    cluster_id: int
    cluster_rank: int
    cluster_type: str
    cluster_region: str
    severity_hint: str
    confidence_score: float
    region_type: str
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    normalized_box: _NormalizedBox
    measurement_json: dict[str, Any]
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _PriorCandidate:
    scan_image: ScanImage
    context: "_ComparisonContext"
    include_reason: str
    match_basis: str
    match_confidence: float


@dataclass(frozen=True)
class _IssueDraft:
    issue_type: str
    severity: str
    issue_message: str
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _HistoryDraft:
    event_type: str
    event_message: str
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _ArtifactDraft:
    artifact_type: str
    body: bytes
    metadata_json: dict[str, Any]
    ext: str


@dataclass(frozen=True)
class _DeltaDraft:
    pair_index: int
    delta_type: str
    delta_category: str
    delta_direction: str
    confidence_score: float
    severity_hint: str
    region_type: str | None
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    measurement_json: dict[str, Any]
    metadata_json: dict[str, Any]


@dataclass
class _ComparisonContext:
    scan_image: ScanImage
    normalization_run: ScanNormalizationRun | None
    boundary_run: ScanBoundaryRun | None
    source_artifact: ScanNormalizationArtifact | None
    ocr_run: ScanOcrRun | None
    ocr_candidates: list[ScanOcrCandidate]
    reconciliation_run: ScanReconciliationRun | None
    reconciliation_decision: ScanReconciliationDecision | None
    reconciliation_candidate: ScanReconciliationCandidate | None
    aggregation_run: ScanDefectAggregationRun | None
    aggregation_clusters: list[ScanDefectAggregateCluster]
    grading_run: ScanGradingAssistanceRun | None
    visual_run: ScanVisualEvidenceRun | None
    review_session: ScanReviewSession | None
    review_identity_decision: ScanReviewDecision | None
    review_status_decision: ScanReviewDecision | None


def utc_now():
    from app.models.scan_historical_comparison import utc_now as _utc_now

    return _utc_now()


def clamp_scan_historical_comparison_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value).replace("\\", "/")
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


def _resolve_hist_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.scan_historical_comparison_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("scan historical comparison storage path escapes configured root")
    return target


def _artifact_storage_path(
    *,
    owner_user_id: int,
    scan_image_id: int,
    comparison_run_id: int,
    artifact_type: str,
    ext: str,
) -> str:
    return (
        f"scan-historical-comparison/{owner_user_id}/{scan_image_id}/{comparison_run_id}/{artifact_type.lower()}{ext}".replace("\\", "/")
    )


def _save_artifact_bytes(settings: Settings, *, relative_path: str, body: bytes) -> None:
    target = _resolve_hist_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)


def _artifact_preview_data_url(settings: Settings, row: ScanHistoricalComparisonArtifact) -> str | None:
    if not row.storage_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        return None
    try:
        body = _resolve_hist_storage_path(settings, row.storage_path).read_bytes()
    except OSError:
        return None
    return f"data:image/png;base64,{base64.b64encode(body).decode('ascii')}"


def _load_latest(session: Session, model: Any, *filters: Any, order_by: Any) -> Any | None:
    stmt = select(model)
    for clause in filters:
        stmt = stmt.where(clause)
    return session.exec(stmt.order_by(order_by)).first()


def _load_context_for_scan(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int,
    reconciliation_run_id: int | None = None,
    visual_evidence_run_id: int | None = None,
    review_session_id: int | None = None,
) -> _ComparisonContext:
    scan_image = session.get(ScanImage, scan_image_id)
    if scan_image is None or int(scan_image.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan image not found.")

    normalization_run = _load_latest(
        session,
        ScanNormalizationRun,
        ScanNormalizationRun.owner_user_id == owner_user_id,
        ScanNormalizationRun.scan_image_id == scan_image_id,
        ScanNormalizationRun.normalization_status == "COMPLETE",
        order_by=col(ScanNormalizationRun.id).desc(),
    )
    boundary_run = _load_latest(
        session,
        ScanBoundaryRun,
        ScanBoundaryRun.owner_user_id == owner_user_id,
        ScanBoundaryRun.scan_image_id == scan_image_id,
        ScanBoundaryRun.boundary_status == "COMPLETE",
        order_by=col(ScanBoundaryRun.id).desc(),
    )
    source_artifact = session.get(ScanNormalizationArtifact, int(boundary_run.source_artifact_id)) if boundary_run else None
    ocr_run = _load_latest(
        session,
        ScanOcrRun,
        ScanOcrRun.owner_user_id == owner_user_id,
        ScanOcrRun.scan_image_id == scan_image_id,
        ScanOcrRun.ocr_status == "COMPLETE",
        order_by=col(ScanOcrRun.id).desc(),
    )
    ocr_candidates: list[ScanOcrCandidate] = []
    if ocr_run is not None:
        ocr_candidates = session.exec(
            select(ScanOcrCandidate)
            .where(ScanOcrCandidate.ocr_run_id == ocr_run.id)
            .order_by(col(ScanOcrCandidate.candidate_type).asc(), col(ScanOcrCandidate.confidence_score).desc(), col(ScanOcrCandidate.id).asc())
        ).all()

    reconciliation_run = None
    if reconciliation_run_id is not None:
        reconciliation_run = session.get(ScanReconciliationRun, reconciliation_run_id)
        if reconciliation_run is None or int(reconciliation_run.owner_user_id) != owner_user_id:
            raise HTTPException(status_code=404, detail="Reconciliation run not found.")
    else:
        reconciliation_run = _load_latest(
            session,
            ScanReconciliationRun,
            ScanReconciliationRun.owner_user_id == owner_user_id,
            ScanReconciliationRun.scan_image_id == scan_image_id,
            ScanReconciliationRun.reconciliation_status != "FAILED",
            order_by=col(ScanReconciliationRun.id).desc(),
        )

    reconciliation_decision = None
    reconciliation_candidate = None
    if reconciliation_run is not None:
        reconciliation_decision = session.exec(
            select(ScanReconciliationDecision)
            .where(ScanReconciliationDecision.reconciliation_run_id == reconciliation_run.id)
            .order_by(col(ScanReconciliationDecision.created_at).desc(), col(ScanReconciliationDecision.id).desc())
        ).first()
        if reconciliation_decision is not None and reconciliation_decision.selected_candidate_id is not None:
            reconciliation_candidate = session.get(ScanReconciliationCandidate, int(reconciliation_decision.selected_candidate_id))

    visual_run = None
    if visual_evidence_run_id is not None:
        visual_run = session.get(ScanVisualEvidenceRun, visual_evidence_run_id)
        if visual_run is None or int(visual_run.owner_user_id) != owner_user_id:
            raise HTTPException(status_code=404, detail="Visual evidence run not found.")
    else:
        visual_run = _load_latest(
            session,
            ScanVisualEvidenceRun,
            ScanVisualEvidenceRun.owner_user_id == owner_user_id,
            ScanVisualEvidenceRun.scan_image_id == scan_image_id,
            ScanVisualEvidenceRun.evidence_status == "COMPLETE",
            order_by=col(ScanVisualEvidenceRun.id).desc(),
        )

    aggregation_run = None
    grading_run = None
    if visual_run is not None and visual_run.aggregation_run_id is not None:
        aggregation_run = session.get(ScanDefectAggregationRun, int(visual_run.aggregation_run_id))
    if aggregation_run is None:
        aggregation_run = _load_latest(
            session,
            ScanDefectAggregationRun,
            ScanDefectAggregationRun.owner_user_id == owner_user_id,
            ScanDefectAggregationRun.scan_image_id == scan_image_id,
            ScanDefectAggregationRun.aggregation_status == "COMPLETE",
            order_by=col(ScanDefectAggregationRun.id).desc(),
        )
    if visual_run is not None and visual_run.grading_assistance_run_id is not None:
        grading_run = session.get(ScanGradingAssistanceRun, int(visual_run.grading_assistance_run_id))
    if grading_run is None:
        grading_run = _load_latest(
            session,
            ScanGradingAssistanceRun,
            ScanGradingAssistanceRun.owner_user_id == owner_user_id,
            ScanGradingAssistanceRun.scan_image_id == scan_image_id,
            ScanGradingAssistanceRun.assistance_status == "COMPLETE",
            order_by=col(ScanGradingAssistanceRun.id).desc(),
        )
    aggregation_clusters: list[ScanDefectAggregateCluster] = []
    if aggregation_run is not None:
        aggregation_clusters = session.exec(
            select(ScanDefectAggregateCluster)
            .where(ScanDefectAggregateCluster.aggregation_run_id == aggregation_run.id)
            .order_by(col(ScanDefectAggregateCluster.cluster_rank).asc(), col(ScanDefectAggregateCluster.id).asc())
        ).all()

    review_session = None
    if review_session_id is not None:
        review_session = session.get(ScanReviewSession, review_session_id)
        if review_session is None or int(review_session.owner_user_id) != owner_user_id:
            raise HTTPException(status_code=404, detail="Review session not found.")
    else:
        review_session = session.exec(
            select(ScanReviewSession)
            .where(ScanReviewSession.owner_user_id == owner_user_id, ScanReviewSession.scan_image_id == scan_image_id)
            .order_by(col(ScanReviewSession.id).desc())
        ).first()

    review_identity_decision = None
    review_status_decision = None
    if review_session is not None:
        decisions = session.exec(
            select(ScanReviewDecision)
            .where(ScanReviewDecision.review_session_id == review_session.id)
            .order_by(col(ScanReviewDecision.id).desc())
        ).all()
        review_identity_decision = next(
            (
                row
                for row in decisions
                if row.decision_type == "IDENTITY_CONFIRMATION" and row.decision_status in {"ACCEPTED", "OVERRIDDEN", "NOT_APPLICABLE"}
            ),
            None,
        )
        review_status_decision = next(
            (row for row in decisions if row.decision_type in {"SCAN_QUALITY_DECISION", "ESCALATION_DECISION"}),
            None,
        )

    return _ComparisonContext(
        scan_image=scan_image,
        normalization_run=normalization_run,
        boundary_run=boundary_run,
        source_artifact=source_artifact,
        ocr_run=ocr_run,
        ocr_candidates=ocr_candidates,
        reconciliation_run=reconciliation_run,
        reconciliation_decision=reconciliation_decision,
        reconciliation_candidate=reconciliation_candidate,
        aggregation_run=aggregation_run,
        aggregation_clusters=aggregation_clusters,
        grading_run=grading_run,
        visual_run=visual_run,
        review_session=review_session,
        review_identity_decision=review_identity_decision,
        review_status_decision=review_status_decision,
    )


def determine_comparison_identity_key(context: _ComparisonContext) -> _IdentityResult:
    if context.reconciliation_candidate is not None and context.reconciliation_candidate.canonical_comic_id is not None:
        return _IdentityResult(
            identity_key=f"canonical:{int(context.reconciliation_candidate.canonical_comic_id)}",
            match_basis="SAME_RECONCILED_IDENTITY",
            confidence=round(float(context.reconciliation_decision.final_confidence_score if context.reconciliation_decision else 0.0), 6),
            metadata_json={"canonical_comic_id": int(context.reconciliation_candidate.canonical_comic_id)},
        )
    if context.review_identity_decision is not None and context.review_identity_decision.decision_value.strip():
        value = context.review_identity_decision.decision_value.strip().lower()
        return _IdentityResult(
            identity_key=f"manual-review:{value}",
            match_basis="MANUAL_REVIEW_LINK",
            confidence=round(float(context.review_identity_decision.confidence_score or 0.7), 6),
            metadata_json={"review_session_id": int(context.review_session.id or 0) if context.review_session else None},
        )
    best_by_type: dict[str, ScanOcrCandidate] = {}
    for row in context.ocr_candidates:
        if row.candidate_type not in {"TITLE", "ISSUE_NUMBER", "PUBLISHER"}:
            continue
        if row.candidate_type not in best_by_type:
            best_by_type[row.candidate_type] = row
    if {"TITLE", "ISSUE_NUMBER"} <= set(best_by_type):
        title = (best_by_type["TITLE"].normalized_candidate_value or best_by_type["TITLE"].candidate_value or "").strip().lower()
        issue = (best_by_type["ISSUE_NUMBER"].normalized_candidate_value or best_by_type["ISSUE_NUMBER"].candidate_value or "").strip().lower()
        publisher = (best_by_type.get("PUBLISHER").normalized_candidate_value if best_by_type.get("PUBLISHER") else "") or ""
        publisher = publisher.strip().lower()
        confidence_values = [best_by_type["TITLE"].confidence_score, best_by_type["ISSUE_NUMBER"].confidence_score]
        if best_by_type.get("PUBLISHER") is not None:
            confidence_values.append(best_by_type["PUBLISHER"].confidence_score)
        return _IdentityResult(
            identity_key=f"ocr:{title}|{issue}|{publisher}",
            match_basis="SAME_CANONICAL_COMIC",
            confidence=round(sum(confidence_values) / len(confidence_values), 6),
            metadata_json={"title": title, "issue_number": issue, "publisher": publisher},
        )
    if context.scan_image.duplicate_of_scan_image_id is not None:
        return _IdentityResult(
            identity_key=f"duplicate:{int(context.scan_image.duplicate_of_scan_image_id)}",
            match_basis="CHECKSUM_RELATED_VARIANT",
            confidence=0.5,
            metadata_json={"duplicate_of_scan_image_id": int(context.scan_image.duplicate_of_scan_image_id)},
        )
    return _IdentityResult(identity_key=None, match_basis=None, confidence=0.0, metadata_json={})


def _ocr_identity_key(context: _ComparisonContext) -> str | None:
    best_by_type: dict[str, ScanOcrCandidate] = {}
    for row in context.ocr_candidates:
        if row.candidate_type not in {"TITLE", "ISSUE_NUMBER", "PUBLISHER"}:
            continue
        if row.candidate_type not in best_by_type:
            best_by_type[row.candidate_type] = row
    if {"TITLE", "ISSUE_NUMBER"} <= set(best_by_type):
        title = (best_by_type["TITLE"].normalized_candidate_value or best_by_type["TITLE"].candidate_value or "").strip().lower()
        issue = (best_by_type["ISSUE_NUMBER"].normalized_candidate_value or best_by_type["ISSUE_NUMBER"].candidate_value or "").strip().lower()
        publisher = (best_by_type.get("PUBLISHER").normalized_candidate_value if best_by_type.get("PUBLISHER") else "") or ""
        publisher = publisher.strip().lower()
        return f"ocr:{title}|{issue}|{publisher}"
    return None


def _boundary_geometry(context: _ComparisonContext) -> dict[str, Any]:
    return dict((context.boundary_run.output_manifest_json or {}).get("geometry") or {}) if context.boundary_run else {}


def normalize_comparison_geometry(current: _ComparisonContext, prior: _ComparisonContext) -> tuple[float, dict[str, Any]]:
    current_geom = _boundary_geometry(current)
    prior_geom = _boundary_geometry(prior)
    if not current_geom or not prior_geom:
        return 0.0, {"reason": "missing_boundary_geometry"}
    current_conf = float(((current.boundary_run.output_manifest_json or {}).get("detection") or {}).get("confidence_score") or 0.0) if current.boundary_run else 0.0
    prior_conf = float(((prior.boundary_run.output_manifest_json or {}).get("detection") or {}).get("confidence_score") or 0.0) if prior.boundary_run else 0.0
    current_width = max(int(current_geom.get("x_max", 0)) - int(current_geom.get("x_min", 0)) + 1, 1)
    current_height = max(int(current_geom.get("y_max", 0)) - int(current_geom.get("y_min", 0)) + 1, 1)
    prior_width = max(int(prior_geom.get("x_max", 0)) - int(prior_geom.get("x_min", 0)) + 1, 1)
    prior_height = max(int(prior_geom.get("y_max", 0)) - int(prior_geom.get("y_min", 0)) + 1, 1)
    width_ratio = min(current_width, prior_width) / max(current_width, prior_width)
    height_ratio = min(current_height, prior_height) / max(current_height, prior_height)
    geometry_confidence = round(min(current_conf, prior_conf) * width_ratio * height_ratio, 6)
    return geometry_confidence, {
        "current_geometry": current_geom,
        "prior_geometry": prior_geom,
        "current_boundary_confidence": round(current_conf, 6),
        "prior_boundary_confidence": round(prior_conf, 6),
        "width_ratio": round(width_ratio, 6),
        "height_ratio": round(height_ratio, 6),
    }


def _normalize_box(box: tuple[int, int, int, int], geometry: dict[str, Any]) -> _NormalizedBox:
    gx0 = int(geometry.get("x_min", 0))
    gy0 = int(geometry.get("y_min", 0))
    gx1 = int(geometry.get("x_max", 1))
    gy1 = int(geometry.get("y_max", 1))
    gwidth = max(gx1 - gx0 + 1, 1)
    gheight = max(gy1 - gy0 + 1, 1)
    x0, y0, x1, y1 = box
    return _NormalizedBox(
        x_min=round((x0 - gx0) / gwidth, 6),
        y_min=round((y0 - gy0) / gheight, 6),
        x_max=round((x1 - gx0) / gwidth, 6),
        y_max=round((y1 - gy0) / gheight, 6),
    )


def _cluster_comparables(context: _ComparisonContext) -> list[_ClusterComparable]:
    geometry = _boundary_geometry(context)
    rows: list[_ClusterComparable] = []
    for cluster in context.aggregation_clusters:
        rows.append(
            _ClusterComparable(
                cluster_id=int(cluster.id or 0),
                cluster_rank=int(cluster.cluster_rank),
                cluster_type=cluster.cluster_type,
                cluster_region=cluster.cluster_region,
                severity_hint=cluster.aggregate_severity_hint,
                confidence_score=round(float(cluster.cluster_confidence), 6),
                region_type=cluster.cluster_region,
                x_min=int(cluster.x_min),
                y_min=int(cluster.y_min),
                x_max=int(cluster.x_max),
                y_max=int(cluster.y_max),
                normalized_box=_normalize_box((int(cluster.x_min), int(cluster.y_min), int(cluster.x_max), int(cluster.y_max)), geometry) if geometry else _NormalizedBox(0.0, 0.0, 1.0, 1.0),
                measurement_json=dict(cluster.measurement_json or {}),
                metadata_json=dict(cluster.metadata_json or {}),
            )
        )
    return rows


def _iou(a: _NormalizedBox, b: _NormalizedBox) -> float:
    x0 = max(a.x_min, b.x_min)
    y0 = max(a.y_min, b.y_min)
    x1 = min(a.x_max, b.x_max)
    y1 = min(a.y_max, b.y_max)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    inter = (x1 - x0) * (y1 - y0)
    area_a = max((a.x_max - a.x_min), 0.0) * max((a.y_max - a.y_min), 0.0)
    area_b = max((b.x_max - b.x_min), 0.0) * max((b.y_max - b.y_min), 0.0)
    denom = area_a + area_b - inter
    return round(inter / denom, 6) if denom > 0 else 0.0


def _delta_category_for_region(region: str) -> str:
    region_upper = (region or "").upper()
    if "SPINE" in region_upper:
        return "SPINE"
    if "CORNER" in region_upper:
        return "CORNER"
    if "EDGE" in region_upper:
        return "EDGE"
    if "SURFACE" in region_upper:
        return "SURFACE"
    if "STRUCT" in region_upper:
        return "STRUCTURAL"
    return "SURFACE"


def find_eligible_prior_scans(
    session: Session,
    *,
    owner_user_id: int,
    current_context: _ComparisonContext,
    current_identity: _IdentityResult,
    max_comparison_count: int,
) -> tuple[list[_PriorCandidate], list[dict[str, Any]], list[dict[str, Any]]]:
    max_comparison_count = min(max(max_comparison_count, 1), _MAX_PRIOR_SCANS)
    current_scan_id = int(current_context.scan_image.id or 0)
    rows = session.exec(
        select(ScanImage)
        .where(ScanImage.owner_user_id == owner_user_id, ScanImage.id != current_scan_id)
        .order_by(col(ScanImage.created_at).desc(), col(ScanImage.id).desc(), col(ScanImage.sha256_checksum).asc())
    ).all()
    included: list[_PriorCandidate] = []
    included_reasons: list[dict[str, Any]] = []
    excluded_reasons: list[dict[str, Any]] = []
    current_ocr_key = _ocr_identity_key(current_context)
    for row in rows:
        context = _load_context_for_scan(session, owner_user_id=owner_user_id, scan_image_id=int(row.id or 0))
        identity = determine_comparison_identity_key(context)
        prior_ocr_key = _ocr_identity_key(context)
        reason = "identity_mismatch"
        include = False
        match_basis = identity.match_basis or "CHECKSUM_RELATED_VARIANT"
        confidence = identity.confidence
        if current_identity.identity_key and identity.identity_key and identity.identity_key == current_identity.identity_key:
            include = True
            reason = "matching_identity_key"
            match_basis = current_identity.match_basis or identity.match_basis or "SAME_CANONICAL_COMIC"
            confidence = round(min(current_identity.confidence or 1.0, identity.confidence or 1.0), 6)
        elif current_ocr_key and prior_ocr_key and current_ocr_key == prior_ocr_key:
            include = True
            reason = "matching_ocr_identity_key"
            match_basis = "SAME_CANONICAL_COMIC"
            confidence = round(min(max(current_identity.confidence, 0.55), max(identity.confidence, 0.55)), 6)
        elif row.duplicate_of_scan_image_id == current_scan_id or current_context.scan_image.duplicate_of_scan_image_id == int(row.id or 0):
            include = True
            reason = "duplicate_chain_match"
            match_basis = "CHECKSUM_RELATED_VARIANT"
            confidence = 0.5
        if include and len(included) < max_comparison_count:
            included.append(_PriorCandidate(scan_image=row, context=context, include_reason=reason, match_basis=match_basis, match_confidence=confidence))
            included_reasons.append(
                {
                    "prior_scan_image_id": int(row.id or 0),
                    "reason": reason,
                    "match_basis": match_basis,
                    "match_confidence": confidence,
                    "identity_key": identity.identity_key,
                }
            )
        else:
            excluded_reasons.append(
                {
                    "prior_scan_image_id": int(row.id or 0),
                    "reason": "comparison_limit_reached" if include else reason,
                    "identity_key": identity.identity_key,
                }
            )
    return included, included_reasons, excluded_reasons


def compare_evidence_sets(
    *,
    current: _ComparisonContext,
    prior: _ComparisonContext,
    pair_index: int,
    geometry_confidence: float,
    geometry_metadata: dict[str, Any],
) -> list[_DeltaDraft]:
    current_clusters = _cluster_comparables(current)
    prior_clusters = _cluster_comparables(prior)
    prior_unused = {row.cluster_id: row for row in prior_clusters}
    deltas: list[_DeltaDraft] = []

    for cluster in current_clusters:
        candidate_matches = [
            (prior_row, _iou(cluster.normalized_box, prior_row.normalized_box))
            for prior_row in prior_unused.values()
            if prior_row.cluster_region == cluster.cluster_region or prior_row.cluster_type == cluster.cluster_type
        ]
        candidate_matches.sort(key=lambda item: (-item[1], item[0].cluster_rank, item[0].cluster_id))
        match = candidate_matches[0] if candidate_matches and candidate_matches[0][1] >= 0.08 else None
        if match is None:
            deltas.append(
                _DeltaDraft(
                    pair_index=pair_index,
                    delta_type="NEW_EVIDENCE",
                    delta_category=_delta_category_for_region(cluster.cluster_region),
                    delta_direction="WORSENED" if geometry_confidence >= 0.45 else "INCONCLUSIVE",
                    confidence_score=round(min(cluster.confidence_score, max(geometry_confidence, 0.2)), 6),
                    severity_hint=cluster.severity_hint,
                    region_type=cluster.region_type,
                    x_min=cluster.x_min,
                    y_min=cluster.y_min,
                    x_max=cluster.x_max,
                    y_max=cluster.y_max,
                    measurement_json={"current_cluster_id": cluster.cluster_id, "normalized_box": cluster.normalized_box.__dict__},
                    metadata_json={"source": "current_cluster_only", "cluster_type": cluster.cluster_type},
                )
            )
            continue

        prior_row, overlap = match
        prior_unused.pop(prior_row.cluster_id, None)
        current_severity = _SEVERITY_SCORES.get(cluster.severity_hint, 1)
        prior_severity = _SEVERITY_SCORES.get(prior_row.severity_hint, 1)
        if current_severity > prior_severity:
            deltas.append(
                _DeltaDraft(
                    pair_index=pair_index,
                    delta_type="INTENSIFIED_EVIDENCE",
                    delta_category=_delta_category_for_region(cluster.cluster_region),
                    delta_direction="WORSENED" if geometry_confidence >= 0.45 else "INCONCLUSIVE",
                    confidence_score=round(min(cluster.confidence_score, prior_row.confidence_score, max(geometry_confidence, 0.2)), 6),
                    severity_hint=cluster.severity_hint,
                    region_type=cluster.region_type,
                    x_min=cluster.x_min,
                    y_min=cluster.y_min,
                    x_max=cluster.x_max,
                    y_max=cluster.y_max,
                    measurement_json={"overlap_iou": overlap, "current_severity": current_severity, "prior_severity": prior_severity},
                    metadata_json={"current_cluster_id": cluster.cluster_id, "prior_cluster_id": prior_row.cluster_id},
                )
            )
        elif current_severity < prior_severity:
            deltas.append(
                _DeltaDraft(
                    pair_index=pair_index,
                    delta_type="REDUCED_EVIDENCE",
                    delta_category=_delta_category_for_region(cluster.cluster_region),
                    delta_direction="IMPROVED" if geometry_confidence >= 0.45 else "INCONCLUSIVE",
                    confidence_score=round(min(cluster.confidence_score, prior_row.confidence_score, max(geometry_confidence, 0.2)), 6),
                    severity_hint=prior_row.severity_hint,
                    region_type=cluster.region_type,
                    x_min=cluster.x_min,
                    y_min=cluster.y_min,
                    x_max=cluster.x_max,
                    y_max=cluster.y_max,
                    measurement_json={"overlap_iou": overlap, "current_severity": current_severity, "prior_severity": prior_severity},
                    metadata_json={"current_cluster_id": cluster.cluster_id, "prior_cluster_id": prior_row.cluster_id},
                )
            )
        current_area = max(cluster.normalized_box.x_max - cluster.normalized_box.x_min, 0.0) * max(cluster.normalized_box.y_max - cluster.normalized_box.y_min, 0.0)
        prior_area = max(prior_row.normalized_box.x_max - prior_row.normalized_box.x_min, 0.0) * max(prior_row.normalized_box.y_max - prior_row.normalized_box.y_min, 0.0)
        if prior_area > 0:
            area_change = round((current_area - prior_area) / prior_area, 6)
            if abs(area_change) >= 0.2:
                deltas.append(
                    _DeltaDraft(
                        pair_index=pair_index,
                        delta_type="INTENSIFIED_EVIDENCE" if area_change > 0 else "REDUCED_EVIDENCE",
                        delta_category=_delta_category_for_region(cluster.cluster_region),
                        delta_direction=("WORSENED" if area_change > 0 else "IMPROVED") if geometry_confidence >= 0.45 else "INCONCLUSIVE",
                        confidence_score=round(min(cluster.confidence_score, prior_row.confidence_score, max(geometry_confidence, 0.2)), 6),
                        severity_hint=cluster.severity_hint if area_change > 0 else prior_row.severity_hint,
                        region_type=cluster.region_type,
                        x_min=cluster.x_min,
                        y_min=cluster.y_min,
                        x_max=cluster.x_max,
                        y_max=cluster.y_max,
                        measurement_json={"overlap_iou": overlap, "area_change_ratio": area_change, "current_area": round(current_area, 6), "prior_area": round(prior_area, 6)},
                        metadata_json={"current_cluster_id": cluster.cluster_id, "prior_cluster_id": prior_row.cluster_id},
                    )
                )
        center_shift = abs(((cluster.normalized_box.x_min + cluster.normalized_box.x_max) / 2.0) - ((prior_row.normalized_box.x_min + prior_row.normalized_box.x_max) / 2.0)) + abs(((cluster.normalized_box.y_min + cluster.normalized_box.y_max) / 2.0) - ((prior_row.normalized_box.y_min + prior_row.normalized_box.y_max) / 2.0))
        if center_shift > 0.1:
            deltas.append(
                _DeltaDraft(
                    pair_index=pair_index,
                    delta_type="POSITION_SHIFT",
                    delta_category=_delta_category_for_region(cluster.cluster_region),
                    delta_direction="INCONCLUSIVE" if geometry_confidence < 0.7 else "UNCHANGED",
                    confidence_score=round(max(geometry_confidence, 0.2), 6),
                    severity_hint="MINOR",
                    region_type=cluster.region_type,
                    x_min=cluster.x_min,
                    y_min=cluster.y_min,
                    x_max=cluster.x_max,
                    y_max=cluster.y_max,
                    measurement_json={"center_shift": round(center_shift, 6), "overlap_iou": overlap},
                    metadata_json={"current_cluster_id": cluster.cluster_id, "prior_cluster_id": prior_row.cluster_id},
                )
            )

    for prior_row in prior_unused.values():
        deltas.append(
            _DeltaDraft(
                pair_index=pair_index,
                delta_type="RESOLVED_EVIDENCE",
                delta_category=_delta_category_for_region(prior_row.cluster_region),
                delta_direction="IMPROVED" if geometry_confidence >= 0.45 else "INCONCLUSIVE",
                confidence_score=round(min(prior_row.confidence_score, max(geometry_confidence, 0.2)), 6),
                severity_hint=prior_row.severity_hint,
                region_type=prior_row.region_type,
                x_min=prior_row.x_min,
                y_min=prior_row.y_min,
                x_max=prior_row.x_max,
                y_max=prior_row.y_max,
                measurement_json={"prior_cluster_id": prior_row.cluster_id, "normalized_box": prior_row.normalized_box.__dict__},
                metadata_json={"source": "prior_cluster_only"},
            )
        )

    current_boundary_conf = float(((current.boundary_run.output_manifest_json or {}).get("detection") or {}).get("confidence_score") or 0.0) if current.boundary_run else 0.0
    prior_boundary_conf = float(((prior.boundary_run.output_manifest_json or {}).get("detection") or {}).get("confidence_score") or 0.0) if prior.boundary_run else 0.0
    quality_delta = current_boundary_conf - prior_boundary_conf
    if abs(quality_delta) >= 0.12:
        deltas.append(
            _DeltaDraft(
                pair_index=pair_index,
                delta_type="SCAN_QUALITY_CHANGE",
                delta_category="SCAN_QUALITY",
                delta_direction="IMPROVED" if quality_delta > 0 else "WORSENED",
                confidence_score=round(max(abs(quality_delta), 0.2), 6),
                severity_hint="MODERATE" if abs(quality_delta) >= 0.25 else "MINOR",
                region_type=None,
                x_min=0,
                y_min=0,
                x_max=max(int(current.scan_image.width or 1), 1),
                y_max=max(int(current.scan_image.height or 1), 1),
                measurement_json={"current_boundary_confidence": round(current_boundary_conf, 6), "prior_boundary_confidence": round(prior_boundary_conf, 6)},
                metadata_json=geometry_metadata,
            )
        )

    current_geom = _boundary_geometry(current)
    prior_geom = _boundary_geometry(prior)
    if current_geom and prior_geom:
        current_ratio = float(current_geom.get("cover_coverage_ratio") or 0.0)
        prior_ratio = float(prior_geom.get("cover_coverage_ratio") or 0.0)
        if abs(current_ratio - prior_ratio) >= 0.08:
            deltas.append(
                _DeltaDraft(
                    pair_index=pair_index,
                    delta_type="GEOMETRY_CHANGE",
                    delta_category="SCAN_QUALITY",
                    delta_direction="INCONCLUSIVE" if geometry_confidence < 0.7 else "UNCHANGED",
                    confidence_score=round(max(geometry_confidence, 0.2), 6),
                    severity_hint="MODERATE" if abs(current_ratio - prior_ratio) >= 0.15 else "MINOR",
                    region_type=None,
                    x_min=0,
                    y_min=0,
                    x_max=max(int(current.scan_image.width or 1), 1),
                    y_max=max(int(current.scan_image.height or 1), 1),
                    measurement_json={"current_cover_ratio": round(current_ratio, 6), "prior_cover_ratio": round(prior_ratio, 6)},
                    metadata_json=geometry_metadata,
                )
            )

    if (current.scan_image.color_mode or "") != (prior.scan_image.color_mode or ""):
        deltas.append(
            _DeltaDraft(
                pair_index=pair_index,
                delta_type="COLOR_PROFILE_CHANGE",
                delta_category="SCAN_QUALITY",
                delta_direction="INCONCLUSIVE",
                confidence_score=0.4,
                severity_hint="MINOR",
                region_type=None,
                x_min=0,
                y_min=0,
                x_max=max(int(current.scan_image.width or 1), 1),
                y_max=max(int(current.scan_image.height or 1), 1),
                measurement_json={"current_color_mode": current.scan_image.color_mode, "prior_color_mode": prior.scan_image.color_mode},
                metadata_json={},
            )
        )

    if current.review_session is not None and prior.review_session is not None and current.review_session.review_status != prior.review_session.review_status:
        direction = "IMPROVED" if current.review_session.review_status == "REVIEW_COMPLETE" else "INCONCLUSIVE"
        deltas.append(
            _DeltaDraft(
                pair_index=pair_index,
                delta_type="REVIEW_STATUS_CHANGE",
                delta_category="REVIEW",
                delta_direction=direction,
                confidence_score=0.7,
                severity_hint="MINOR",
                region_type=None,
                x_min=0,
                y_min=0,
                x_max=max(int(current.scan_image.width or 1), 1),
                y_max=max(int(current.scan_image.height or 1), 1),
                measurement_json={"current_review_status": current.review_session.review_status, "prior_review_status": prior.review_session.review_status},
                metadata_json={"current_review_session_id": int(current.review_session.id or 0), "prior_review_session_id": int(prior.review_session.id or 0)},
            )
        )

    return deltas


def generate_historical_deltas(
    *,
    current_context: _ComparisonContext,
    pairs: list[_PriorCandidate],
) -> tuple[list[_DeltaDraft], list[_IssueDraft]]:
    deltas: list[_DeltaDraft] = []
    issues: list[_IssueDraft] = []
    for pair_index, candidate in enumerate(pairs, start=1):
        geometry_confidence, geometry_metadata = normalize_comparison_geometry(current_context, candidate.context)
        if geometry_confidence < 0.5:
            issues.append(
                _IssueDraft(
                    "GEOMETRY_ALIGNMENT_LOW_CONFIDENCE",
                    "WARNING",
                    "Boundary geometry confidence is low for one or more comparison pairs.",
                    {"prior_scan_image_id": int(candidate.scan_image.id or 0), "geometry_confidence": geometry_confidence},
                )
            )
        if candidate.match_confidence < 0.55:
            issues.append(
                _IssueDraft(
                    "LOW_MATCH_CONFIDENCE",
                    "WARNING",
                    "Historical comparison matched a prior scan with low confidence.",
                    {"prior_scan_image_id": int(candidate.scan_image.id or 0), "match_confidence": candidate.match_confidence},
                )
            )
        if candidate.context.boundary_run is None or candidate.context.normalization_run is None:
            issues.append(
                _IssueDraft(
                    "PRIOR_SCAN_LINEAGE_MISSING",
                    "WARNING",
                    "Prior scan is missing normalization or boundary lineage needed for reliable comparison.",
                    {"prior_scan_image_id": int(candidate.scan_image.id or 0)},
                )
            )
        pair_deltas = compare_evidence_sets(
            current=current_context,
            prior=candidate.context,
            pair_index=pair_index,
            geometry_confidence=geometry_confidence,
            geometry_metadata=geometry_metadata,
        )
        if not pair_deltas and current_context.scan_image.sha256_checksum != candidate.context.scan_image.sha256_checksum:
            pair_deltas.append(
                _DeltaDraft(
                    pair_index=pair_index,
                    delta_type="SCAN_QUALITY_CHANGE",
                    delta_category="SCAN_QUALITY",
                    delta_direction="INCONCLUSIVE",
                    confidence_score=round(max(geometry_confidence, 0.25), 6),
                    severity_hint="MINOR",
                    region_type=None,
                    x_min=0,
                    y_min=0,
                    x_max=max(int(current_context.scan_image.width or 1), 1),
                    y_max=max(int(current_context.scan_image.height or 1), 1),
                    measurement_json={
                        "reason": "scan_images_differ_without_reliable_material_delta",
                        "current_scan_checksum": current_context.scan_image.sha256_checksum,
                        "prior_scan_checksum": candidate.context.scan_image.sha256_checksum,
                    },
                    metadata_json={"prior_scan_image_id": int(candidate.scan_image.id or 0)},
                )
            )
        deltas.extend(pair_deltas)
        if any(delta.delta_direction == "INCONCLUSIVE" for delta in pair_deltas):
            issues.append(
                _IssueDraft(
                    "COMPARISON_INCONCLUSIVE",
                    "INFO",
                    "One or more detected deltas are inconclusive because scan reliability differs across comparison pairs.",
                    {"prior_scan_image_id": int(candidate.scan_image.id or 0)},
                )
            )
        if any(delta.delta_type == "SCAN_QUALITY_CHANGE" for delta in pair_deltas):
            issues.append(
                _IssueDraft(
                    "SCAN_QUALITY_MISMATCH",
                    "WARNING",
                    "Scan quality differs enough across historical scans to affect comparison reliability.",
                    {"prior_scan_image_id": int(candidate.scan_image.id or 0)},
                )
            )
    if not pairs:
        issues.append(_IssueDraft("NO_PRIOR_SCAN_FOUND", "INFO", "No eligible prior scan was found for deterministic comparison.", {}))
        issues.append(_IssueDraft("COMPARISON_INCONCLUSIVE", "WARNING", "Historical comparison is inconclusive without a prior scan.", {}))
    return sorted(
        deltas,
        key=lambda row: (
            row.pair_index,
            row.delta_type,
            row.delta_category,
            row.delta_direction,
            -row.confidence_score,
            row.region_type or "",
            row.x_min,
            row.y_min,
            row.x_max,
            row.y_max,
        ),
    ), list({(row.issue_type, row.issue_message): row for row in issues}.values())


def build_historical_comparison_manifest(
    *,
    current_lineage: dict[str, Any],
    prior_lineage: list[dict[str, Any]],
    comparison_pairs: list[dict[str, Any]],
    deltas: list[dict[str, Any]],
    included_scan_reasons: list[dict[str, Any]],
    excluded_scan_reasons: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    artifact_refs: list[dict[str, str]],
) -> tuple[dict[str, Any], str]:
    manifest = {
        "engine_version": ENGINE_VERSION,
        "current_lineage": current_lineage,
        "prior_scan_lineage": prior_lineage,
        "comparison_pairs": comparison_pairs,
        "deltas": deltas,
        "included_scan_reasons": included_scan_reasons,
        "excluded_scan_reasons": excluded_scan_reasons,
        "issues": issues,
        "artifact_refs": artifact_refs,
    }
    return manifest, _hash_payload(manifest)


def _image_or_blank(settings: Settings, source_artifact: ScanNormalizationArtifact | None) -> Image.Image:
    if source_artifact is None:
        return Image.new("RGB", (240, 340), (18, 18, 24))
    try:
        with Image.open(_resolve_normalization_artifact_path(settings, source_artifact)) as image_fp:
            image = image_fp.copy().convert("RGB")
    except (OSError, ValueError, UnidentifiedImageError, FileNotFoundError):
        image = Image.new("RGB", (240, 340), (18, 18, 24))
    image.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
    return image


def _render_side_by_side(settings: Settings, current: _ComparisonContext, prior: _ComparisonContext | None) -> bytes:
    current_image = _image_or_blank(settings, current.source_artifact)
    prior_image = _image_or_blank(settings, prior.source_artifact if prior else None)
    width = current_image.width + prior_image.width + 16
    height = max(current_image.height, prior_image.height) + 24
    canvas = Image.new("RGB", (width, height), (14, 16, 20))
    canvas.paste(current_image, (8, 12))
    canvas.paste(prior_image, (current_image.width + 16, 12))
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def _render_delta_overlay(settings: Settings, current: _ComparisonContext, deltas: list[_DeltaDraft]) -> bytes:
    canvas = _image_or_blank(settings, current.source_artifact)
    draw = ImageDraw.Draw(canvas)
    palette = {
        "NEW_EVIDENCE": (255, 90, 90),
        "INTENSIFIED_EVIDENCE": (255, 150, 0),
        "REDUCED_EVIDENCE": (90, 220, 140),
        "RESOLVED_EVIDENCE": (90, 220, 140),
        "POSITION_SHIFT": (240, 220, 80),
        "SCAN_QUALITY_CHANGE": (160, 180, 255),
        "GEOMETRY_CHANGE": (180, 120, 255),
        "COLOR_PROFILE_CHANGE": (220, 120, 255),
        "REVIEW_STATUS_CHANGE": (255, 210, 120),
    }
    for row in deltas:
        if row.x_max <= row.x_min or row.y_max <= row.y_min:
            continue
        color = palette.get(row.delta_type, (255, 255, 255))
        draw.rectangle((row.x_min, row.y_min, row.x_max, row.y_max), outline=color, width=3)
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def _persist_artifacts(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    scan_image_id: int,
    comparison_run_id: int,
    drafts: list[_ArtifactDraft],
) -> None:
    for draft in drafts:
        checksum = _sha256_bytes(draft.body)
        existing = session.exec(
            select(ScanHistoricalComparisonArtifact).where(
                ScanHistoricalComparisonArtifact.comparison_run_id == comparison_run_id,
                ScanHistoricalComparisonArtifact.artifact_type == draft.artifact_type,
                ScanHistoricalComparisonArtifact.artifact_checksum == checksum,
            )
        ).first()
        if existing is not None:
            continue
        relative_path = _artifact_storage_path(
            owner_user_id=owner_user_id,
            scan_image_id=scan_image_id,
            comparison_run_id=comparison_run_id,
            artifact_type=draft.artifact_type,
            ext=draft.ext,
        )
        _save_artifact_bytes(settings, relative_path=relative_path, body=draft.body)
        session.add(
            ScanHistoricalComparisonArtifact(
                owner_user_id=owner_user_id,
                comparison_run_id=comparison_run_id,
                artifact_type=draft.artifact_type,
                storage_path=relative_path,
                artifact_checksum=checksum,
                metadata_json=draft.metadata_json,
            )
        )


def _append_history(
    session: Session,
    *,
    owner_user_id: int,
    comparison_run_id: int,
    event_type: str,
    event_message: str,
    metadata_json: dict[str, Any],
) -> None:
    session.add(
        ScanHistoricalComparisonHistory(
            owner_user_id=owner_user_id,
            comparison_run_id=comparison_run_id,
            event_type=event_type,
            event_message=event_message,
            event_checksum=_hash_payload(
                {
                    "comparison_run_id": comparison_run_id,
                    "event_type": event_type,
                    "event_message": event_message,
                    "metadata_json": metadata_json,
                }
            ),
            metadata_json=metadata_json,
        )
    )


def _current_lineage(context: _ComparisonContext) -> dict[str, Any]:
    return {
        "current_original_scan_checksum": context.scan_image.sha256_checksum,
        "current_normalization_checksum": context.normalization_run.normalization_checksum if context.normalization_run else None,
        "current_boundary_checksum": context.boundary_run.boundary_checksum if context.boundary_run else None,
        "current_reconciliation_checksum": context.reconciliation_run.reconciliation_checksum if context.reconciliation_run else None,
        "current_aggregation_checksum": context.aggregation_run.aggregation_checksum if context.aggregation_run else None,
        "current_grading_assistance_checksum": context.grading_run.grading_assistance_checksum if context.grading_run else None,
        "current_review_checksum": context.review_session.review_checksum if context.review_session else None,
        "current_visual_evidence_checksum": context.visual_run.visual_evidence_checksum if context.visual_run else None,
    }


def _prior_lineage_rows(candidates: list[_PriorCandidate]) -> list[dict[str, Any]]:
    return [
        {
            "prior_scan_image_id": int(row.scan_image.id or 0),
            "prior_original_scan_checksum": row.context.scan_image.sha256_checksum,
            "prior_normalization_checksum": row.context.normalization_run.normalization_checksum if row.context.normalization_run else None,
            "prior_boundary_checksum": row.context.boundary_run.boundary_checksum if row.context.boundary_run else None,
            "prior_reconciliation_checksum": row.context.reconciliation_run.reconciliation_checksum if row.context.reconciliation_run else None,
            "prior_aggregation_checksum": row.context.aggregation_run.aggregation_checksum if row.context.aggregation_run else None,
            "prior_grading_assistance_checksum": row.context.grading_run.grading_assistance_checksum if row.context.grading_run else None,
            "prior_review_checksum": row.context.review_session.review_checksum if row.context.review_session else None,
            "prior_visual_evidence_checksum": row.context.visual_run.visual_evidence_checksum if row.context.visual_run else None,
        }
        for row in candidates
    ]


def _detail_from_run(session: Session, settings: Settings, run: ScanHistoricalComparisonRun) -> ScanHistoricalComparisonRunDetail:
    pairs = session.exec(
        select(ScanHistoricalComparisonPair)
        .where(ScanHistoricalComparisonPair.comparison_run_id == run.id)
        .order_by(col(ScanHistoricalComparisonPair.id).asc())
    ).all()
    deltas = session.exec(
        select(ScanHistoricalComparisonDelta)
        .where(ScanHistoricalComparisonDelta.comparison_run_id == run.id)
        .order_by(col(ScanHistoricalComparisonDelta.delta_rank).asc(), col(ScanHistoricalComparisonDelta.id).asc())
    ).all()
    artifacts = session.exec(
        select(ScanHistoricalComparisonArtifact)
        .where(ScanHistoricalComparisonArtifact.comparison_run_id == run.id)
        .order_by(col(ScanHistoricalComparisonArtifact.id).asc())
    ).all()
    issues = session.exec(
        select(ScanHistoricalComparisonIssue)
        .where(ScanHistoricalComparisonIssue.comparison_run_id == run.id)
        .order_by(col(ScanHistoricalComparisonIssue.id).asc())
    ).all()
    history = session.exec(
        select(ScanHistoricalComparisonHistory)
        .where(ScanHistoricalComparisonHistory.comparison_run_id == run.id)
        .order_by(col(ScanHistoricalComparisonHistory.id).asc())
    ).all()

    current_context = _load_context_for_scan(
        session,
        owner_user_id=int(run.owner_user_id),
        scan_image_id=int(run.scan_image_id),
        reconciliation_run_id=run.reconciliation_run_id,
        visual_evidence_run_id=run.visual_evidence_run_id,
        review_session_id=run.review_session_id,
    )
    artifact_reads = [
        ScanHistoricalComparisonArtifactRead.model_validate(row).model_copy(update={"preview_data_url": _artifact_preview_data_url(settings, row)})
        for row in artifacts
    ]
    side_by_side = next((row for row in artifact_reads if row.artifact_type == "SIDE_BY_SIDE_COMPARISON"), None)
    delta_overlay = next((row for row in artifact_reads if row.artifact_type == "DELTA_OVERLAY"), None)

    output = run.output_manifest_json or {}
    current_lineage = dict(output.get("current_lineage") or {})
    return ScanHistoricalComparisonRunDetail(
        **ScanHistoricalComparisonRunRead.model_validate(run).model_dump(),
        pairs=[ScanHistoricalComparisonPairRead.model_validate(row) for row in pairs],
        deltas=[ScanHistoricalComparisonDeltaRead.model_validate(row) for row in deltas],
        artifacts=artifact_reads,
        issues=[ScanHistoricalComparisonIssueRead.model_validate(row) for row in issues],
        history=[ScanHistoricalComparisonHistoryRead.model_validate(row) for row in history],
        current_original_scan_checksum=current_lineage.get("current_original_scan_checksum"),
        current_normalization_checksum=current_lineage.get("current_normalization_checksum"),
        current_boundary_checksum=current_lineage.get("current_boundary_checksum"),
        current_reconciliation_checksum=current_lineage.get("current_reconciliation_checksum"),
        current_aggregation_checksum=current_lineage.get("current_aggregation_checksum"),
        current_grading_assistance_checksum=current_lineage.get("current_grading_assistance_checksum"),
        current_review_checksum=current_lineage.get("current_review_checksum"),
        prior_lineage=list(output.get("prior_scan_lineage") or []),
        current_preview_data_url=_load_source_preview(settings, current_context.source_artifact) if current_context.source_artifact else None,
        side_by_side_preview_data_url=side_by_side.preview_data_url if side_by_side else None,
        delta_overlay_preview_data_url=delta_overlay.preview_data_url if delta_overlay else None,
    )


def run_scan_historical_comparison(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: ScanHistoricalComparisonRunCreate,
) -> tuple[ScanHistoricalComparisonRunDetail, bool]:
    current_context = _load_context_for_scan(
        session,
        owner_user_id=owner_user_id,
        scan_image_id=payload.scan_image_id,
        reconciliation_run_id=payload.reconciliation_run_id,
        visual_evidence_run_id=payload.visual_evidence_run_id,
        review_session_id=payload.review_session_id,
    )
    current_identity = determine_comparison_identity_key(current_context)
    included_pairs, included_scan_reasons, excluded_scan_reasons = find_eligible_prior_scans(
        session,
        owner_user_id=owner_user_id,
        current_context=current_context,
        current_identity=current_identity,
        max_comparison_count=payload.max_prior_scans,
    )
    deltas, issue_drafts = generate_historical_deltas(current_context=current_context, pairs=included_pairs)
    if current_identity.identity_key is None:
        issue_drafts.append(_IssueDraft("IDENTITY_KEY_MISSING", "ERROR", "Unable to determine a stable historical comparison identity key.", {}))

    pair_payloads = [
        {
            "current_scan_image_id": int(current_context.scan_image.id or 0),
            "prior_scan_image_id": int(row.scan_image.id or 0),
            "current_identity_key": current_identity.identity_key or "",
            "prior_identity_key": determine_comparison_identity_key(row.context).identity_key or "",
            "match_basis": row.match_basis,
            "match_confidence": row.match_confidence,
            "current_checksum": current_context.scan_image.sha256_checksum,
            "prior_checksum": row.context.scan_image.sha256_checksum,
            "metadata_json": {
                "include_reason": row.include_reason,
                "current_review_status": current_context.review_session.review_status if current_context.review_session else None,
                "prior_review_status": row.context.review_session.review_status if row.context.review_session else None,
            },
        }
        for row in included_pairs
    ]
    delta_payloads = [
        {
            "delta_type": row.delta_type,
            "delta_category": row.delta_category,
            "delta_direction": row.delta_direction,
            "confidence_score": row.confidence_score,
            "severity_hint": row.severity_hint,
            "region_type": row.region_type,
            "x_min": row.x_min,
            "y_min": row.y_min,
            "x_max": row.x_max,
            "y_max": row.y_max,
            "measurement_json": row.measurement_json,
            "metadata_json": row.metadata_json,
            "pair_index": row.pair_index,
        }
        for row in deltas
    ]
    issue_payloads = [
        {
            "issue_type": row.issue_type,
            "severity": row.severity,
            "issue_message": row.issue_message,
            "metadata_json": row.metadata_json,
        }
        for row in sorted(issue_drafts, key=lambda row: (row.issue_type, row.severity, row.issue_message))
    ]
    manifest, provisional_checksum = build_historical_comparison_manifest(
        current_lineage=_current_lineage(current_context),
        prior_lineage=_prior_lineage_rows(included_pairs),
        comparison_pairs=pair_payloads,
        deltas=delta_payloads,
        included_scan_reasons=included_scan_reasons,
        excluded_scan_reasons=excluded_scan_reasons,
        issues=issue_payloads,
        artifact_refs=[],
    )
    first_prior = included_pairs[0].context if included_pairs else None
    artifact_drafts = [
        _ArtifactDraft("HISTORICAL_DELTA_REPORT", _serialize_json_artifact(delta_payloads), {"format": "json"}, ".json"),
        _ArtifactDraft("SIDE_BY_SIDE_COMPARISON", _render_side_by_side(settings, current_context, first_prior), {"format": "png"}, ".png"),
        _ArtifactDraft("DELTA_OVERLAY", _render_delta_overlay(settings, current_context, deltas), {"format": "png"}, ".png"),
        _ArtifactDraft("COMPARISON_PAIR_EXPORT", _serialize_json_artifact(pair_payloads), {"format": "json"}, ".json"),
        _ArtifactDraft("HISTORICAL_COMPARISON_MANIFEST", _serialize_json_artifact(manifest), {"format": "json"}, ".json"),
        _ArtifactDraft("HISTORICAL_DEBUG_PREVIEW", _render_side_by_side(settings, current_context, first_prior), {"format": "png"}, ".png"),
    ]
    artifact_refs = [{"artifact_type": row.artifact_type, "artifact_checksum": _sha256_bytes(row.body)} for row in artifact_drafts]
    final_manifest, final_checksum = build_historical_comparison_manifest(
        current_lineage=_current_lineage(current_context),
        prior_lineage=_prior_lineage_rows(included_pairs),
        comparison_pairs=pair_payloads,
        deltas=delta_payloads,
        included_scan_reasons=included_scan_reasons,
        excluded_scan_reasons=excluded_scan_reasons,
        issues=issue_payloads,
        artifact_refs=artifact_refs,
    )
    existing = session.exec(
        select(ScanHistoricalComparisonRun)
        .where(
            ScanHistoricalComparisonRun.owner_user_id == owner_user_id,
            ScanHistoricalComparisonRun.historical_comparison_checksum == final_checksum,
        )
        .order_by(col(ScanHistoricalComparisonRun.id).desc())
    ).first()
    if existing is not None:
        return _detail_from_run(session, settings, existing), False

    comparison_status = "INCONCLUSIVE" if any(row["issue_type"] in {"NO_PRIOR_SCAN_FOUND", "IDENTITY_KEY_MISSING", "COMPARISON_INCONCLUSIVE"} for row in issue_payloads) else "COMPLETE"
    run = ScanHistoricalComparisonRun(
        owner_user_id=owner_user_id,
        scan_image_id=payload.scan_image_id,
        reconciliation_run_id=int(current_context.reconciliation_run.id or 0) if current_context.reconciliation_run else None,
        visual_evidence_run_id=int(current_context.visual_run.id or 0) if current_context.visual_run else None,
        review_session_id=int(current_context.review_session.id or 0) if current_context.review_session else None,
        source_checksum=current_context.visual_run.visual_evidence_checksum if current_context.visual_run else current_context.scan_image.sha256_checksum,
        historical_comparison_checksum=final_checksum,
        comparison_status=comparison_status,
        engine_version=ENGINE_VERSION,
        input_manifest_json={
            "scan_image_id": payload.scan_image_id,
            "reconciliation_run_id": payload.reconciliation_run_id,
            "visual_evidence_run_id": payload.visual_evidence_run_id,
            "review_session_id": payload.review_session_id,
            "max_prior_scans": payload.max_prior_scans,
        },
        output_manifest_json=final_manifest,
    )
    session.add(run)
    session.flush()

    _append_history(
        session,
        owner_user_id=owner_user_id,
        comparison_run_id=int(run.id or 0),
        event_type="HISTORICAL_COMPARISON_STARTED",
        event_message="Started deterministic historical comparison run.",
        metadata_json={"identity_key": current_identity.identity_key, "prior_scan_count": len(included_pairs)},
    )

    pair_rows: list[ScanHistoricalComparisonPair] = []
    for row in pair_payloads:
        pair = ScanHistoricalComparisonPair(
            owner_user_id=owner_user_id,
            comparison_run_id=int(run.id or 0),
            current_scan_image_id=row["current_scan_image_id"],
            prior_scan_image_id=row["prior_scan_image_id"],
            current_identity_key=row["current_identity_key"],
            prior_identity_key=row["prior_identity_key"],
            match_basis=row["match_basis"],
            match_confidence=row["match_confidence"],
            current_checksum=row["current_checksum"],
            prior_checksum=row["prior_checksum"],
            metadata_json=row["metadata_json"],
        )
        session.add(pair)
        pair_rows.append(pair)
    session.flush()

    for rank, row in enumerate(delta_payloads, start=1):
        pair_row = pair_rows[row["pair_index"] - 1] if 0 < row["pair_index"] <= len(pair_rows) else None
        session.add(
            ScanHistoricalComparisonDelta(
                owner_user_id=owner_user_id,
                comparison_run_id=int(run.id or 0),
                pair_id=int(pair_row.id or 0) if pair_row else 0,
                delta_rank=rank,
                delta_type=row["delta_type"],
                delta_category=row["delta_category"],
                delta_direction=row["delta_direction"],
                confidence_score=row["confidence_score"],
                severity_hint=row["severity_hint"],
                region_type=row["region_type"],
                x_min=row["x_min"],
                y_min=row["y_min"],
                x_max=row["x_max"],
                y_max=row["y_max"],
                measurement_json=row["measurement_json"],
                metadata_json=row["metadata_json"],
            )
        )

    for row in issue_payloads:
        session.add(
            ScanHistoricalComparisonIssue(
                owner_user_id=owner_user_id,
                comparison_run_id=int(run.id or 0),
                issue_type=row["issue_type"],
                severity=row["severity"],
                issue_message=row["issue_message"],
                metadata_json=row["metadata_json"],
            )
        )
    session.flush()

    _persist_artifacts(
        session,
        settings,
        owner_user_id=owner_user_id,
        scan_image_id=payload.scan_image_id,
        comparison_run_id=int(run.id or 0),
        drafts=artifact_drafts,
    )
    session.flush()
    _append_history(
        session,
        owner_user_id=owner_user_id,
        comparison_run_id=int(run.id or 0),
        event_type="HISTORICAL_COMPARISON_COMPLETED",
        event_message="Completed deterministic historical comparison run.",
        metadata_json={"historical_comparison_checksum": final_checksum, "delta_count": len(delta_payloads)},
    )
    session.commit()
    session.refresh(run)
    return _detail_from_run(session, settings, run), True


def get_scan_historical_comparison_run_owner(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    run_id: int,
) -> ScanHistoricalComparisonRunDetail:
    row = session.get(ScanHistoricalComparisonRun, run_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Historical comparison run not found.")
    return _detail_from_run(session, settings, row)


def get_scan_historical_comparison_artifact_owner(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    artifact_id: int,
) -> ScanHistoricalComparisonArtifactRead:
    row = session.get(ScanHistoricalComparisonArtifact, artifact_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Historical comparison artifact not found.")
    return ScanHistoricalComparisonArtifactRead.model_validate(row).model_copy(update={"preview_data_url": _artifact_preview_data_url(settings, row)})


def _run_list_response(rows: list[ScanHistoricalComparisonRun], *, limit: int, offset: int, total_items: int) -> ScanHistoricalComparisonRunListResponse:
    return ScanHistoricalComparisonRunListResponse(
        items=[ScanHistoricalComparisonRunRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        status_counts={key: sum(1 for row in rows if row.comparison_status == key) for key in sorted({row.comparison_status for row in rows})},
        inconclusive_count=sum(1 for row in rows if row.comparison_status == "INCONCLUSIVE"),
        scans_with_prior_history_count=sum(1 for row in rows if bool((row.output_manifest_json or {}).get("comparison_pairs"))),
    )


def list_scan_historical_comparison_runs_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanHistoricalComparisonRunListResponse:
    limit, offset = clamp_scan_historical_comparison_pagination(limit=limit, offset=offset)
    stmt = select(ScanHistoricalComparisonRun).where(ScanHistoricalComparisonRun.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanHistoricalComparisonRun).where(ScanHistoricalComparisonRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanHistoricalComparisonRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanHistoricalComparisonRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanHistoricalComparisonRun.created_at).desc(), col(ScanHistoricalComparisonRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_historical_comparison_runs_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanHistoricalComparisonRunListResponse:
    limit, offset = clamp_scan_historical_comparison_pagination(limit=limit, offset=offset)
    stmt = select(ScanHistoricalComparisonRun)
    count_stmt = select(func.count()).select_from(ScanHistoricalComparisonRun)
    if owner_user_id is not None:
        stmt = stmt.where(ScanHistoricalComparisonRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanHistoricalComparisonRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanHistoricalComparisonRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanHistoricalComparisonRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanHistoricalComparisonRun.created_at).desc(), col(ScanHistoricalComparisonRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_historical_comparison_pairs_owner(
    session: Session,
    *,
    owner_user_id: int,
    run_id: int | None,
    limit: int,
    offset: int,
) -> ScanHistoricalComparisonPairListResponse:
    limit, offset = clamp_scan_historical_comparison_pagination(limit=limit, offset=offset)
    stmt = select(ScanHistoricalComparisonPair).where(ScanHistoricalComparisonPair.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanHistoricalComparisonPair).where(ScanHistoricalComparisonPair.owner_user_id == owner_user_id)
    if run_id is not None:
        stmt = stmt.where(ScanHistoricalComparisonPair.comparison_run_id == run_id)
        count_stmt = count_stmt.where(ScanHistoricalComparisonPair.comparison_run_id == run_id)
    rows = session.exec(stmt.order_by(col(ScanHistoricalComparisonPair.id).asc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanHistoricalComparisonPairListResponse(
        items=[ScanHistoricalComparisonPairRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        match_basis_counts={key: sum(1 for row in rows if row.match_basis == key) for key in sorted({row.match_basis for row in rows})},
    )


def list_scan_historical_comparison_deltas_owner(
    session: Session,
    *,
    owner_user_id: int,
    run_id: int | None,
    limit: int,
    offset: int,
) -> ScanHistoricalComparisonDeltaListResponse:
    limit, offset = clamp_scan_historical_comparison_pagination(limit=limit, offset=offset)
    stmt = select(ScanHistoricalComparisonDelta).where(ScanHistoricalComparisonDelta.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanHistoricalComparisonDelta).where(ScanHistoricalComparisonDelta.owner_user_id == owner_user_id)
    if run_id is not None:
        stmt = stmt.where(ScanHistoricalComparisonDelta.comparison_run_id == run_id)
        count_stmt = count_stmt.where(ScanHistoricalComparisonDelta.comparison_run_id == run_id)
    rows = session.exec(stmt.order_by(col(ScanHistoricalComparisonDelta.delta_rank).asc(), col(ScanHistoricalComparisonDelta.id).asc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanHistoricalComparisonDeltaListResponse(
        items=[ScanHistoricalComparisonDeltaRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        delta_type_counts={key: sum(1 for row in rows if row.delta_type == key) for key in sorted({row.delta_type for row in rows})},
        delta_direction_counts={key: sum(1 for row in rows if row.delta_direction == key) for key in sorted({row.delta_direction for row in rows})},
    )


def list_scan_historical_comparison_issues_owner(
    session: Session,
    *,
    owner_user_id: int,
    run_id: int | None,
    limit: int,
    offset: int,
) -> ScanHistoricalComparisonIssueListResponse:
    limit, offset = clamp_scan_historical_comparison_pagination(limit=limit, offset=offset)
    stmt = select(ScanHistoricalComparisonIssue).where(ScanHistoricalComparisonIssue.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanHistoricalComparisonIssue).where(ScanHistoricalComparisonIssue.owner_user_id == owner_user_id)
    if run_id is not None:
        stmt = stmt.where(ScanHistoricalComparisonIssue.comparison_run_id == run_id)
        count_stmt = count_stmt.where(ScanHistoricalComparisonIssue.comparison_run_id == run_id)
    rows = session.exec(stmt.order_by(col(ScanHistoricalComparisonIssue.id).asc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanHistoricalComparisonIssueListResponse(
        items=[ScanHistoricalComparisonIssueRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        issue_type_counts={key: sum(1 for row in rows if row.issue_type == key) for key in sorted({row.issue_type for row in rows})},
    )


def list_scan_historical_comparison_issues_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanHistoricalComparisonIssueListResponse:
    limit, offset = clamp_scan_historical_comparison_pagination(limit=limit, offset=offset)
    stmt = select(ScanHistoricalComparisonIssue)
    count_stmt = select(func.count()).select_from(ScanHistoricalComparisonIssue)
    if owner_user_id is not None:
        stmt = stmt.where(ScanHistoricalComparisonIssue.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanHistoricalComparisonIssue.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanHistoricalComparisonIssue.id).asc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanHistoricalComparisonIssueListResponse(
        items=[ScanHistoricalComparisonIssueRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        issue_type_counts={key: sum(1 for row in rows if row.issue_type == key) for key in sorted({row.issue_type for row in rows})},
    )


def list_scan_historical_comparison_failures_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanHistoricalComparisonRunListResponse:
    limit, offset = clamp_scan_historical_comparison_pagination(limit=limit, offset=offset)
    stmt = select(ScanHistoricalComparisonRun).where(ScanHistoricalComparisonRun.comparison_status == "FAILED")
    count_stmt = select(func.count()).select_from(ScanHistoricalComparisonRun).where(ScanHistoricalComparisonRun.comparison_status == "FAILED")
    if owner_user_id is not None:
        stmt = stmt.where(ScanHistoricalComparisonRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanHistoricalComparisonRun.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanHistoricalComparisonRun.created_at).desc(), col(ScanHistoricalComparisonRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_historical_comparison_inconclusive_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanHistoricalComparisonRunListResponse:
    limit, offset = clamp_scan_historical_comparison_pagination(limit=limit, offset=offset)
    stmt = select(ScanHistoricalComparisonRun).where(ScanHistoricalComparisonRun.comparison_status == "INCONCLUSIVE")
    count_stmt = select(func.count()).select_from(ScanHistoricalComparisonRun).where(ScanHistoricalComparisonRun.comparison_status == "INCONCLUSIVE")
    if owner_user_id is not None:
        stmt = stmt.where(ScanHistoricalComparisonRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanHistoricalComparisonRun.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanHistoricalComparisonRun.created_at).desc(), col(ScanHistoricalComparisonRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)
