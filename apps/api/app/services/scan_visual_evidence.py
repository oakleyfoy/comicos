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
    ScanDefectEvidence,
    ScanDefectRun,
    ScanGradingAssistanceCategory,
    ScanGradingAssistanceFinding,
    ScanGradingAssistanceIssue,
    ScanGradingAssistanceRun,
    ScanImage,
    ScanNormalizationArtifact,
    ScanNormalizationRun,
    ScanOcrCandidate,
    ScanOcrRun,
    ScanOcrTextRegion,
    ScanReconciliationCandidate,
    ScanReconciliationDecision,
    ScanReconciliationRun,
    ScanVisualEvidenceAnnotation,
    ScanVisualEvidenceArtifact,
    ScanVisualEvidenceHistory,
    ScanVisualEvidenceIssue,
    ScanVisualEvidenceItem,
    ScanVisualEvidencePackage,
    ScanVisualEvidenceRun,
)
from app.schemas.scan_visual_evidence import (
    ScanVisualEvidenceAnnotationListResponse,
    ScanVisualEvidenceAnnotationRead,
    ScanVisualEvidenceArtifactRead,
    ScanVisualEvidenceFailureListResponse,
    ScanVisualEvidenceHistoryRead,
    ScanVisualEvidenceIssueListResponse,
    ScanVisualEvidenceIssueRead,
    ScanVisualEvidenceItemListResponse,
    ScanVisualEvidenceItemRead,
    ScanVisualEvidencePackageListResponse,
    ScanVisualEvidencePackageRead,
    ScanVisualEvidenceRunCreate,
    ScanVisualEvidenceRunDetail,
    ScanVisualEvidenceRunListResponse,
    ScanVisualEvidenceRunRead,
)
from app.services.scan_defects import _load_source_preview, _resolve_normalization_artifact_path

ENGINE_VERSION = "P40-13-v1"
_PREVIEW_MAX = 480
_PACKAGE_ORDER = (
    "DEFECT_EVIDENCE_PACKAGE",
    "GRADING_SUPPORT_PACKAGE",
    "OCR_IDENTITY_PACKAGE",
    "AUTHENTICATION_PREP_PACKAGE",
    "FULL_REVIEW_PACKAGE",
)
_LOW_CONFIDENCE = 0.35


@dataclass(frozen=True)
class _PackageDraft:
    package_type: str
    package_status: str
    package_title: str
    package_summary: str
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _ItemDraft:
    package_type: str
    item_key: str
    source_system: str
    source_record_id: int
    item_type: str
    item_title: str
    item_summary: str
    confidence_score: float
    severity_hint: str | None
    region_type: str | None
    x_min: int | None
    y_min: int | None
    x_max: int | None
    y_max: int | None
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _AnnotationDraft:
    item_key: str
    annotation_type: str
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    label: str
    confidence_score: float
    display_order: int
    style_hint: str
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


def utc_now():
    from app.models.scan_visual_evidence import utc_now as _utc_now

    return _utc_now()


def clamp_scan_visual_evidence_pagination(*, limit: int, offset: int) -> tuple[int, int]:
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


def _resolve_visual_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.scan_visual_evidence_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("scan visual evidence storage path escapes configured root")
    return target


def _artifact_storage_path(
    *,
    owner_user_id: int,
    scan_image_id: int,
    visual_evidence_run_id: int,
    artifact_type: str,
    ext: str,
) -> str:
    safe_type = artifact_type.lower()
    return f"scan-visual-evidence/{owner_user_id}/{scan_image_id}/{visual_evidence_run_id}/{safe_type}{ext}".replace("\\", "/")


def _save_artifact_bytes(settings: Settings, *, relative_path: str, body: bytes) -> None:
    target = _resolve_visual_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)


def _artifact_preview_data_url(settings: Settings, row: ScanVisualEvidenceArtifact) -> str | None:
    if not row.storage_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        return None
    try:
        body = _resolve_visual_storage_path(settings, row.storage_path).read_bytes()
    except OSError:
        return None
    return f"data:image/png;base64,{base64.b64encode(body).decode('ascii')}"


def _serialize_json_artifact(payload: Any) -> bytes:
    return json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"), indent=2).encode("utf-8")


def _image_to_rgb(image: Image.Image) -> Image.Image:
    return image.copy().convert("RGB") if image.mode != "RGB" else image.copy()


def _round_box(x_min: int, y_min: int, x_max: int, y_max: int) -> tuple[int, int, int, int]:
    return int(x_min), int(y_min), int(x_max), int(y_max)


def _valid_box(x_min: int | None, y_min: int | None, x_max: int | None, y_max: int | None) -> bool:
    if x_min is None or y_min is None or x_max is None or y_max is None:
        return False
    return x_max >= x_min and y_max >= y_min


def _resolve_defect_run(session: Session, *, owner_user_id: int, scan_image_id: int) -> ScanDefectRun:
    row = session.exec(
        select(ScanDefectRun)
        .where(
            ScanDefectRun.owner_user_id == owner_user_id,
            ScanDefectRun.scan_image_id == scan_image_id,
            ScanDefectRun.defect_status == "COMPLETE",
        )
        .order_by(col(ScanDefectRun.id).desc())
    ).first()
    if row is None:
        raise HTTPException(status_code=409, detail="A complete defect foundation run is required before visual evidence generation.")
    return row


def _resolve_aggregation_run(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int,
    aggregation_run_id: int | None,
) -> ScanDefectAggregationRun | None:
    stmt = select(ScanDefectAggregationRun).where(
        ScanDefectAggregationRun.owner_user_id == owner_user_id,
        ScanDefectAggregationRun.scan_image_id == scan_image_id,
        ScanDefectAggregationRun.aggregation_status == "COMPLETE",
    )
    if aggregation_run_id is not None:
        stmt = stmt.where(ScanDefectAggregationRun.id == aggregation_run_id)
    return session.exec(stmt.order_by(col(ScanDefectAggregationRun.id).desc())).first()


def _resolve_grading_run(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int,
    grading_assistance_run_id: int | None,
    aggregation_run_id: int | None,
) -> ScanGradingAssistanceRun | None:
    stmt = select(ScanGradingAssistanceRun).where(
        ScanGradingAssistanceRun.owner_user_id == owner_user_id,
        ScanGradingAssistanceRun.scan_image_id == scan_image_id,
        ScanGradingAssistanceRun.assistance_status == "COMPLETE",
    )
    if grading_assistance_run_id is not None:
        stmt = stmt.where(ScanGradingAssistanceRun.id == grading_assistance_run_id)
    if aggregation_run_id is not None and grading_assistance_run_id is None:
        stmt = stmt.where(ScanGradingAssistanceRun.aggregation_run_id == aggregation_run_id)
    return session.exec(stmt.order_by(col(ScanGradingAssistanceRun.id).desc())).first()


def _load_ocr_run(session: Session, *, boundary_run_id: int) -> ScanOcrRun | None:
    return session.exec(
        select(ScanOcrRun)
        .where(ScanOcrRun.boundary_run_id == boundary_run_id, ScanOcrRun.ocr_status == "COMPLETE")
        .order_by(col(ScanOcrRun.id).desc())
    ).first()


def _load_reconciliation_run(session: Session, *, owner_user_id: int, scan_image_id: int) -> ScanReconciliationRun | None:
    return session.exec(
        select(ScanReconciliationRun)
        .where(
            ScanReconciliationRun.owner_user_id == owner_user_id,
            ScanReconciliationRun.scan_image_id == scan_image_id,
            ScanReconciliationRun.reconciliation_status != "FAILED",
        )
        .order_by(col(ScanReconciliationRun.id).desc())
    ).first()


def build_evidence_packages(
    *,
    has_defect_items: bool,
    has_grading: bool,
    has_ocr: bool,
    has_reconciliation: bool,
    item_counts: dict[str, int],
) -> list[_PackageDraft]:
    packages: list[_PackageDraft] = []
    if has_defect_items:
        packages.append(
            _PackageDraft(
                package_type="DEFECT_EVIDENCE_PACKAGE",
                package_status="COMPLETE",
                package_title="Defect evidence package",
                package_summary=f"Deterministic defect and aggregation evidence callouts ({item_counts.get('DEFECT_EVIDENCE_PACKAGE', 0)} items).",
                metadata_json={"item_count": item_counts.get("DEFECT_EVIDENCE_PACKAGE", 0)},
            )
        )
    if has_grading:
        packages.append(
            _PackageDraft(
                package_type="GRADING_SUPPORT_PACKAGE",
                package_status="COMPLETE",
                package_title="Grading support package",
                package_summary=f"Support-range and review-flag visual summaries ({item_counts.get('GRADING_SUPPORT_PACKAGE', 0)} items).",
                metadata_json={"item_count": item_counts.get("GRADING_SUPPORT_PACKAGE", 0)},
            )
        )
    if has_ocr:
        packages.append(
            _PackageDraft(
                package_type="OCR_IDENTITY_PACKAGE",
                package_status="COMPLETE",
                package_title="OCR identity package",
                package_summary=f"OCR region and candidate identity evidence ({item_counts.get('OCR_IDENTITY_PACKAGE', 0)} items).",
                metadata_json={"item_count": item_counts.get("OCR_IDENTITY_PACKAGE", 0)},
            )
        )
    if has_reconciliation:
        packages.append(
            _PackageDraft(
                package_type="AUTHENTICATION_PREP_PACKAGE",
                package_status="COMPLETE",
                package_title="Authentication prep package",
                package_summary=f"Reconciliation candidate context for review ({item_counts.get('AUTHENTICATION_PREP_PACKAGE', 0)} items).",
                metadata_json={"item_count": item_counts.get("AUTHENTICATION_PREP_PACKAGE", 0)},
            )
        )
    packages.append(
        _PackageDraft(
            package_type="FULL_REVIEW_PACKAGE",
            package_status="COMPLETE" if packages else "PARTIAL",
            package_title="Full review package",
            package_summary="Unified review packet combining all available upstream visual evidence packages.",
            metadata_json={
                "included_package_types": [row.package_type for row in packages if row.package_type != "FULL_REVIEW_PACKAGE"],
                "item_count": item_counts.get("FULL_REVIEW_PACKAGE", 0),
            },
        )
    )
    return sorted(packages, key=lambda row: _PACKAGE_ORDER.index(row.package_type) if row.package_type in _PACKAGE_ORDER else 999)


def create_visual_evidence_items(
    *,
    defect_evidence: list[ScanDefectEvidence],
    clusters: list[ScanDefectAggregateCluster],
    grading_findings: list[ScanGradingAssistanceFinding],
    grading_categories: list[ScanGradingAssistanceCategory],
    cluster_by_id: dict[int, ScanDefectAggregateCluster],
    boundary_run: ScanBoundaryRun | None,
    ocr_regions: list[ScanOcrTextRegion],
    ocr_candidates: list[ScanOcrCandidate],
    recon_candidates: list[ScanReconciliationCandidate],
    recon_decisions: list[ScanReconciliationDecision],
) -> list[_ItemDraft]:
    items: list[_ItemDraft] = []

    if boundary_run is not None:
        geometry = dict((boundary_run.output_manifest_json or {}).get("geometry") or {})
        cover = geometry.get("cover_bbox") or geometry.get("full_cover_bbox")
        if isinstance(cover, dict):
            x_min, y_min, x_max, y_max = _round_box(int(cover.get("x_min", 0)), int(cover.get("y_min", 0)), int(cover.get("x_max", 1)), int(cover.get("y_max", 1)))
            items.append(
                _ItemDraft(
                    package_type="DEFECT_EVIDENCE_PACKAGE",
                    item_key=f"P40_03_BOUNDARY:{boundary_run.id}:COVER",
                    source_system="P40_03_BOUNDARY",
                    source_record_id=int(boundary_run.id or 0),
                    item_type="BOUNDARY_GEOMETRY",
                    item_title="Cover boundary geometry",
                    item_summary="Boundary-derived cover geometry for visual review context.",
                    confidence_score=round(
                        float(((boundary_run.output_manifest_json or {}).get("detection") or {}).get("confidence_score") or 0.0),
                        6,
                    ),
                    severity_hint=None,
                    region_type="FULL_COVER",
                    x_min=x_min,
                    y_min=y_min,
                    x_max=x_max,
                    y_max=y_max,
                    metadata_json={"boundary_checksum": boundary_run.boundary_checksum},
                )
            )

    for row in sorted(defect_evidence, key=lambda r: (r.id or 0)):
        items.append(
            _ItemDraft(
                package_type="DEFECT_EVIDENCE_PACKAGE",
                item_key=f"P40_06_DEFECT_FOUNDATION:{row.id}:{row.evidence_type}",
                source_system="P40_06_DEFECT_FOUNDATION",
                source_record_id=int(row.id or 0),
                item_type=str(row.evidence_type),
                item_title=str(row.evidence_type).replace("_", " ").title(),
                item_summary=f"Defect foundation evidence {row.evidence_category} with confidence {float(row.confidence_score):.3f}.",
                confidence_score=round(float(row.confidence_score), 6),
                severity_hint=str(row.severity_hint),
                region_type=str(row.evidence_category),
                x_min=int(row.x_min),
                y_min=int(row.y_min),
                x_max=int(row.x_max),
                y_max=int(row.y_max),
                metadata_json=dict(row.metadata_json or {}),
            )
        )

    for row in sorted(clusters, key=lambda r: (r.cluster_rank, r.id or 0)):
        items.append(
            _ItemDraft(
                package_type="DEFECT_EVIDENCE_PACKAGE",
                item_key=f"P40_11_AGGREGATION:{row.id}:{row.cluster_type}",
                source_system="P40_11_AGGREGATION",
                source_record_id=int(row.id or 0),
                item_type=str(row.cluster_type),
                item_title=f"{row.cluster_region} cluster",
                item_summary=f"Aggregation cluster {row.cluster_type} with severity {row.aggregate_severity_hint}.",
                confidence_score=round(float(row.cluster_confidence), 6),
                severity_hint=str(row.aggregate_severity_hint),
                region_type=str(row.cluster_region),
                x_min=int(row.x_min),
                y_min=int(row.y_min),
                x_max=int(row.x_max),
                y_max=int(row.y_max),
                metadata_json=dict(row.metadata_json or {}),
            )
        )

    for row in sorted(grading_findings, key=lambda r: (r.category_id, r.id or 0)):
        cluster = row.metadata_json or {}
        bbox = cluster.get("bbox") if isinstance(cluster.get("bbox"), dict) else {}
        items.append(
            _ItemDraft(
                package_type="GRADING_SUPPORT_PACKAGE",
                item_key=f"P40_12_GRADING_ASSISTANCE:{row.id}:{row.finding_type}",
                source_system="P40_12_GRADING_ASSISTANCE",
                source_record_id=int(row.id or 0),
                item_type=str(row.finding_type),
                item_title=str(row.finding_type).replace("_", " ").title(),
                item_summary=row.finding_text[:1024],
                confidence_score=round(float(row.confidence_score), 6),
                severity_hint=str(row.finding_severity_hint),
                region_type=str((row.metadata_json or {}).get("cluster_region") or "SUPPORT"),
                x_min=int(bbox.get("x_min")) if bbox.get("x_min") is not None else None,
                y_min=int(bbox.get("y_min")) if bbox.get("y_min") is not None else None,
                x_max=int(bbox.get("x_max")) if bbox.get("x_max") is not None else None,
                y_max=int(bbox.get("y_max")) if bbox.get("y_max") is not None else None,
                metadata_json={
                    "grade_pressure_hint": row.grade_pressure_hint,
                    "source_cluster_id": row.source_cluster_id,
                },
            )
        )

    for row in sorted(grading_categories, key=lambda r: (r.category_type, r.id or 0)):
        if row.category_type == "OVERALL_SUPPORT":
            continue
        items.append(
            _ItemDraft(
                package_type="GRADING_SUPPORT_PACKAGE",
                item_key=f"P40_12_GRADING_ASSISTANCE:CAT:{row.id}:{row.category_type}",
                source_system="P40_12_GRADING_ASSISTANCE",
                source_record_id=int(row.id or 0),
                item_type="CATEGORY_SUPPORT",
                item_title=f"{row.category_type} support range",
                item_summary=row.summary_text[:1024],
                confidence_score=round(float(row.confidence_score), 6),
                severity_hint=None,
                region_type=str(row.category_type),
                x_min=None,
                y_min=None,
                x_max=None,
                y_max=None,
                metadata_json={
                    "suggested_range_low": row.suggested_range_low,
                    "suggested_range_high": row.suggested_range_high,
                    "category_status": row.category_status,
                },
            )
        )

    for row in sorted(ocr_regions, key=lambda r: (r.region_type, r.id or 0)):
        items.append(
            _ItemDraft(
                package_type="OCR_IDENTITY_PACKAGE",
                item_key=f"P40_04_OCR:REGION:{row.id}",
                source_system="P40_04_OCR",
                source_record_id=int(row.id or 0),
                item_type="OCR_TEXT_REGION",
                item_title=f"OCR {row.region_type}",
                item_summary=(row.extracted_text or "")[:256] or "OCR text region evidence.",
                confidence_score=round(float(row.confidence_score), 6),
                severity_hint=None,
                region_type=str(row.region_type),
                x_min=int(row.x_min),
                y_min=int(row.y_min),
                x_max=int(row.x_max),
                y_max=int(row.y_max),
                metadata_json=dict(row.metadata_json or {}),
            )
        )

    for row in sorted(ocr_candidates, key=lambda r: (r.candidate_type, r.id or 0)):
        items.append(
            _ItemDraft(
                package_type="OCR_IDENTITY_PACKAGE",
                item_key=f"P40_04_OCR:CAND:{row.id}",
                source_system="P40_04_OCR",
                source_record_id=int(row.id or 0),
                item_type="OCR_CANDIDATE",
                item_title=f"OCR candidate {row.candidate_type}",
                item_summary=(row.candidate_value or "")[:256],
                confidence_score=round(float(row.confidence_score), 6),
                severity_hint=None,
                region_type=str(row.candidate_type),
                x_min=None,
                y_min=None,
                x_max=None,
                y_max=None,
                metadata_json=dict(row.metadata_json or {}),
            )
        )

    for row in sorted(recon_candidates, key=lambda r: (r.candidate_rank, r.id or 0)):
        items.append(
            _ItemDraft(
                package_type="AUTHENTICATION_PREP_PACKAGE",
                item_key=f"P40_05_RECONCILIATION:CAND:{row.id}",
                source_system="P40_05_RECONCILIATION",
                source_record_id=int(row.id or 0),
                item_type="RECONCILIATION_CANDIDATE",
                item_title=f"Candidate rank {row.candidate_rank}",
                item_summary=f"{row.series_title or 'Unknown series'} #{row.issue_number or '?'}",
                confidence_score=round(float(row.confidence_score), 6),
                severity_hint=None,
                region_type="IDENTITY",
                x_min=None,
                y_min=None,
                x_max=None,
                y_max=None,
                metadata_json=dict(row.metadata_json or {}),
            )
        )

    for row in sorted(recon_decisions, key=lambda r: r.id or 0):
        items.append(
            _ItemDraft(
                package_type="AUTHENTICATION_PREP_PACKAGE",
                item_key=f"P40_05_RECONCILIATION:DEC:{row.id}",
                source_system="P40_05_RECONCILIATION",
                source_record_id=int(row.id or 0),
                item_type="RECONCILIATION_DECISION",
                item_title="Reconciliation decision",
                item_summary=f"{row.decision_status}: {row.decision_reason}"[:1024],
                confidence_score=round(float(row.final_confidence_score), 6),
                severity_hint=None,
                region_type="IDENTITY",
                x_min=None,
                y_min=None,
                x_max=None,
                y_max=None,
                metadata_json={"selected_candidate_id": row.selected_candidate_id},
            )
        )

    for pkg in _PACKAGE_ORDER:
        subset = [item for item in items if item.package_type == pkg]
        if not subset:
            continue
        items.append(
            _ItemDraft(
                package_type="FULL_REVIEW_PACKAGE",
                item_key=f"FULL_REVIEW:{pkg}",
                source_system="P40_13_VISUAL_EVIDENCE",
                source_record_id=0,
                item_type="PACKAGE_SUMMARY",
                item_title=pkg.replace("_", " ").title(),
                item_summary=f"Includes {len(subset)} evidence items from {pkg}.",
                confidence_score=round(sum(i.confidence_score for i in subset) / max(1, len(subset)), 6),
                severity_hint=None,
                region_type="SUMMARY",
                x_min=None,
                y_min=None,
                x_max=None,
                y_max=None,
                metadata_json={"source_package_type": pkg, "source_item_count": len(subset)},
            )
        )

    return sorted(items, key=lambda row: (_PACKAGE_ORDER.index(row.package_type), row.item_key))


def create_annotations(
    *,
    items: list[_ItemDraft],
    grading_issues: list[ScanGradingAssistanceIssue],
) -> tuple[list[_AnnotationDraft], list[_IssueDraft]]:
    annotations: list[_AnnotationDraft] = []
    issues: list[_IssueDraft] = []
    order = 0
    for item in items:
        if not _valid_box(item.x_min, item.y_min, item.x_max, item.y_max):
            continue
        x_min, y_min, x_max, y_max = _round_box(item.x_min, item.y_min, item.x_max, item.y_max)
        if x_max - x_min > 10000 or y_max - y_min > 10000:
            issues.append(
                _IssueDraft(
                    issue_type="ANNOTATION_GEOMETRY_INVALID",
                    severity="WARNING",
                    issue_message=f"Skipped invalid geometry for item {item.item_key}.",
                    metadata_json={"item_key": item.item_key},
                )
            )
            continue
        order += 1
        annotations.append(
            _AnnotationDraft(
                item_key=item.item_key,
                annotation_type="BOUNDING_BOX",
                x_min=x_min,
                y_min=y_min,
                x_max=x_max,
                y_max=y_max,
                label=item.item_title[:255],
                confidence_score=item.confidence_score,
                display_order=order,
                style_hint="evidence_bbox",
                metadata_json={"source_system": item.source_system},
            )
        )
        if item.package_type == "DEFECT_EVIDENCE_PACKAGE" and item.source_system == "P40_11_AGGREGATION":
            order += 1
            annotations.append(
                _AnnotationDraft(
                    item_key=item.item_key,
                    annotation_type="REGION_HIGHLIGHT",
                    x_min=x_min,
                    y_min=y_min,
                    x_max=x_max,
                    y_max=y_max,
                    label=f"{item.region_type} highlight",
                    confidence_score=item.confidence_score,
                    display_order=order,
                    style_hint="cluster_highlight",
                    metadata_json={"cluster_region": item.region_type},
                )
            )
        if item.package_type == "GRADING_SUPPORT_PACKAGE" and item.item_type != "CATEGORY_SUPPORT":
            order += 1
            cx = (x_min + x_max) // 2
            cy = max(0, y_min - 8)
            annotations.append(
                _AnnotationDraft(
                    item_key=item.item_key,
                    annotation_type="CALLOUT",
                    x_min=cx,
                    y_min=cy,
                    x_max=cx,
                    y_max=cy,
                    label=(item.metadata_json or {}).get("grade_pressure_hint", "SUPPORT"),
                    confidence_score=item.confidence_score,
                    display_order=order,
                    style_hint="grading_callout",
                    metadata_json={"finding_type": item.item_type},
                )
            )

    for issue in grading_issues:
        if issue.issue_type != "REVIEW_REQUIRED":
            continue
        order += 1
        annotations.append(
            _AnnotationDraft(
                item_key=f"REVIEW_FLAG:{issue.id}",
                annotation_type="REVIEW_FLAG",
                x_min=8,
                y_min=8 + (order * 4),
                x_max=24,
                y_max=24 + (order * 4),
                label="Review required",
                confidence_score=0.5,
                display_order=order,
                style_hint="review_flag",
                metadata_json={"issue_type": issue.issue_type, "grading_issue_id": int(issue.id or 0)},
            )
        )

    return sorted(annotations, key=lambda row: (row.display_order, row.item_key, row.annotation_type)), issues


def generate_visual_overlays(
    image: Image.Image,
    annotations: list[_AnnotationDraft],
    *,
    package_type: str | None = None,
) -> bytes:
    rendered = _image_to_rgb(image)
    draw = ImageDraw.Draw(rendered)
    palette = {
        "evidence_bbox": "#38bdf8",
        "cluster_highlight": "#22c55e",
        "grading_callout": "#a78bfa",
        "review_flag": "#ef4444",
    }
    for ann in annotations:
        if package_type and ann.style_hint == "review_flag" and package_type != "FULL_REVIEW_PACKAGE":
            continue
        color = palette.get(ann.style_hint, "#ffffff")
        if ann.annotation_type == "CALLOUT":
            draw.ellipse((ann.x_min - 4, ann.y_min - 4, ann.x_max + 4, ann.y_max + 4), outline=color, width=2)
            draw.text((ann.x_min, ann.y_min), str(ann.label)[:32], fill=color)
            continue
        draw.rectangle((ann.x_min, ann.y_min, ann.x_max, ann.y_max), outline=color, width=2)
        draw.text((ann.x_min, max(0, ann.y_min - 12)), str(ann.label)[:48], fill=color)
    rendered.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
    buf = io.BytesIO()
    rendered.save(buf, format="PNG")
    return buf.getvalue()


def build_visual_evidence_manifest(
    *,
    lineage: dict[str, Any],
    packages: list[_PackageDraft],
    items: list[_ItemDraft],
    annotations: list[_AnnotationDraft],
    issues: list[_IssueDraft],
    artifact_checksums: list[dict[str, str]],
) -> tuple[dict[str, Any], str]:
    manifest = {
        "engine_version": ENGINE_VERSION,
        "upstream_lineage": lineage,
        "packages": [
            {
                "package_type": row.package_type,
                "package_status": row.package_status,
                "package_title": row.package_title,
                "package_summary": row.package_summary,
                "metadata_json": row.metadata_json,
            }
            for row in packages
        ],
        "items": [
            {
                "package_type": row.package_type,
                "item_key": row.item_key,
                "source_system": row.source_system,
                "source_record_id": row.source_record_id,
                "item_type": row.item_type,
                "item_title": row.item_title,
                "item_summary": row.item_summary,
                "confidence_score": row.confidence_score,
                "severity_hint": row.severity_hint,
                "region_type": row.region_type,
                "metadata_json": row.metadata_json,
            }
            for row in items
        ],
        "annotations": [
            {
                "item_key": row.item_key,
                "annotation_type": row.annotation_type,
                "x_min": row.x_min,
                "y_min": row.y_min,
                "x_max": row.x_max,
                "y_max": row.y_max,
                "label": row.label,
                "confidence_score": row.confidence_score,
                "display_order": row.display_order,
                "style_hint": row.style_hint,
                "metadata_json": row.metadata_json,
            }
            for row in annotations
        ],
        "issues": [
            {
                "issue_type": row.issue_type,
                "severity": row.severity,
                "issue_message": row.issue_message,
                "metadata_json": row.metadata_json,
            }
            for row in issues
        ],
        "artifact_checksums": artifact_checksums,
    }
    return manifest, _hash_payload(manifest)


def _build_issues(
    *,
    items: list[_ItemDraft],
    annotations: list[_AnnotationDraft],
    annotation_issues: list[_IssueDraft],
    aggregation_run: ScanDefectAggregationRun | None,
    grading_run: ScanGradingAssistanceRun | None,
    packages: list[_PackageDraft],
) -> list[_IssueDraft]:
    issues = list(annotation_issues)
    if not items:
        issues.append(
            _IssueDraft(
                issue_type="UPSTREAM_EVIDENCE_MISSING",
                severity="ERROR",
                issue_message="No upstream evidence items were available for visual packaging.",
                metadata_json={},
            )
        )
    if aggregation_run is None:
        issues.append(
            _IssueDraft(
                issue_type="AGGREGATION_MISSING",
                severity="INFO",
                issue_message="Aggregation run was not available; defect-only visual evidence was packaged.",
                metadata_json={},
            )
        )
    if grading_run is None:
        issues.append(
            _IssueDraft(
                issue_type="GRADING_ASSISTANCE_MISSING",
                severity="INFO",
                issue_message="Grading assistance was not available; grading support package omitted.",
                metadata_json={},
            )
        )
    if items and not annotations:
        issues.append(
            _IssueDraft(
                issue_type="ANNOTATION_GEOMETRY_INVALID",
                severity="WARNING",
                issue_message="No drawable annotations were produced from available evidence geometry.",
                metadata_json={},
            )
        )
    low_conf = sum(1 for row in items if row.confidence_score < _LOW_CONFIDENCE)
    if low_conf:
        issues.append(
            _IssueDraft(
                issue_type="LOW_EVIDENCE_CONFIDENCE",
                severity="WARNING",
                issue_message="One or more evidence items have low confidence for visual review.",
                metadata_json={"low_confidence_item_count": low_conf},
            )
        )
    full_pkg = next((row for row in packages if row.package_type == "FULL_REVIEW_PACKAGE"), None)
    if full_pkg and full_pkg.package_status != "COMPLETE":
        issues.append(
            _IssueDraft(
                issue_type="REVIEW_PACKET_INCOMPLETE",
                severity="WARNING",
                issue_message="Full review packet is partial because upstream packages were missing.",
                metadata_json={},
            )
        )
    return issues


def _artifact_drafts_for_run(
    *,
    image: Image.Image,
    packages: list[_PackageDraft],
    items: list[_ItemDraft],
    annotations: list[_AnnotationDraft],
    manifest: dict[str, Any],
) -> list[_ArtifactDraft]:
    overlay = generate_visual_overlays(image, annotations)
    review_packet = {
        "packages": [row.metadata_json for row in packages],
        "item_count": len(items),
        "annotation_count": len(annotations),
    }
    package_report = [
        {
            "package_type": row.package_type,
            "package_status": row.package_status,
            "package_title": row.package_title,
            "package_summary": row.package_summary,
            "metadata_json": row.metadata_json,
        }
        for row in packages
    ]
    annotation_export = [
        {
            "item_key": row.item_key,
            "annotation_type": row.annotation_type,
            "x_min": row.x_min,
            "y_min": row.y_min,
            "x_max": row.x_max,
            "y_max": row.y_max,
            "label": row.label,
            "confidence_score": row.confidence_score,
            "display_order": row.display_order,
            "style_hint": row.style_hint,
            "metadata_json": row.metadata_json,
        }
        for row in annotations
    ]
    return [
        _ArtifactDraft("VISUAL_EVIDENCE_OVERLAY", overlay, {"format": "png"}, ".png"),
        _ArtifactDraft("EVIDENCE_PACKAGE_REPORT", _serialize_json_artifact(package_report), {"format": "json"}, ".json"),
        _ArtifactDraft("ANNOTATION_EXPORT", _serialize_json_artifact(annotation_export), {"format": "json"}, ".json"),
        _ArtifactDraft("REVIEW_PACKET_JSON", _serialize_json_artifact(review_packet), {"format": "json"}, ".json"),
        _ArtifactDraft("VISUAL_EVIDENCE_DEBUG_PREVIEW", overlay, {"format": "png"}, ".png"),
    ]


def _detail_from_run(session: Session, settings: Settings, run: ScanVisualEvidenceRun) -> ScanVisualEvidenceRunDetail:
    packages = session.exec(
        select(ScanVisualEvidencePackage)
        .where(ScanVisualEvidencePackage.visual_evidence_run_id == run.id)
        .order_by(col(ScanVisualEvidencePackage.id))
    ).all()
    items = session.exec(
        select(ScanVisualEvidenceItem)
        .where(ScanVisualEvidenceItem.visual_evidence_run_id == run.id)
        .order_by(col(ScanVisualEvidenceItem.package_id), col(ScanVisualEvidenceItem.item_rank))
    ).all()
    annotations = session.exec(
        select(ScanVisualEvidenceAnnotation)
        .where(ScanVisualEvidenceAnnotation.visual_evidence_run_id == run.id)
        .order_by(col(ScanVisualEvidenceAnnotation.display_order), col(ScanVisualEvidenceAnnotation.id))
    ).all()
    artifacts = session.exec(
        select(ScanVisualEvidenceArtifact)
        .where(ScanVisualEvidenceArtifact.visual_evidence_run_id == run.id)
        .order_by(col(ScanVisualEvidenceArtifact.id))
    ).all()
    issues = session.exec(
        select(ScanVisualEvidenceIssue).where(ScanVisualEvidenceIssue.visual_evidence_run_id == run.id).order_by(col(ScanVisualEvidenceIssue.id))
    ).all()
    history = session.exec(
        select(ScanVisualEvidenceHistory).where(ScanVisualEvidenceHistory.visual_evidence_run_id == run.id).order_by(col(ScanVisualEvidenceHistory.id))
    ).all()
    defect_run = None
    if run.aggregation_run_id:
        agg = session.get(ScanDefectAggregationRun, int(run.aggregation_run_id))
        defect_run_id = (agg.input_manifest_json or {}).get("defect_run_id") if agg else None
        if defect_run_id:
            defect_run = session.get(ScanDefectRun, int(defect_run_id))
    if defect_run is None:
        defect_run = session.exec(
            select(ScanDefectRun)
            .where(ScanDefectRun.owner_user_id == run.owner_user_id, ScanDefectRun.scan_image_id == run.scan_image_id)
            .order_by(col(ScanDefectRun.id).desc())
        ).first()
    scan_image = session.get(ScanImage, int(run.scan_image_id))
    norm_run = session.get(ScanNormalizationRun, int(defect_run.normalization_run_id)) if defect_run else None
    boundary_run = session.get(ScanBoundaryRun, int(defect_run.boundary_run_id)) if defect_run else None
    source_artifact = session.get(ScanNormalizationArtifact, int(defect_run.source_artifact_id)) if defect_run else None
    ocr_run = _load_ocr_run(session, boundary_run_id=int(boundary_run.id or 0)) if boundary_run else None
    recon_run = _load_reconciliation_run(session, owner_user_id=int(run.owner_user_id), scan_image_id=int(run.scan_image_id))
    grading_run = session.get(ScanGradingAssistanceRun, int(run.grading_assistance_run_id)) if run.grading_assistance_run_id else None
    agg_run = session.get(ScanDefectAggregationRun, int(run.aggregation_run_id)) if run.aggregation_run_id else None
    art_reads = [
        ScanVisualEvidenceArtifactRead.model_validate(row).model_copy(update={"preview_data_url": _artifact_preview_data_url(settings, row)})
        for row in artifacts
    ]
    overlay = next((row for row in art_reads if row.artifact_type == "VISUAL_EVIDENCE_OVERLAY"), None)
    lineage = dict((run.output_manifest_json or {}).get("upstream_lineage") or {})
    return ScanVisualEvidenceRunDetail(
        **ScanVisualEvidenceRunRead.model_validate(run).model_dump(),
        packages=[ScanVisualEvidencePackageRead.model_validate(row) for row in packages],
        items=[ScanVisualEvidenceItemRead.model_validate(row) for row in items],
        annotations=[ScanVisualEvidenceAnnotationRead.model_validate(row) for row in annotations],
        artifacts=art_reads,
        issues=[ScanVisualEvidenceIssueRead.model_validate(row) for row in issues],
        history=[ScanVisualEvidenceHistoryRead.model_validate(row) for row in history],
        original_scan_checksum=scan_image.sha256_checksum if scan_image else None,
        normalization_checksum=norm_run.normalization_checksum if norm_run else None,
        boundary_checksum=boundary_run.boundary_checksum if boundary_run else None,
        ocr_checksum=ocr_run.ocr_checksum if ocr_run else None,
        reconciliation_checksum=recon_run.reconciliation_checksum if recon_run else lineage.get("reconciliation_checksum"),
        defect_checksum=lineage.get("defect_checksum"),
        aggregation_checksum=agg_run.aggregation_checksum if agg_run else lineage.get("aggregation_checksum"),
        grading_assistance_checksum=grading_run.grading_assistance_checksum if grading_run else lineage.get("grading_assistance_checksum"),
        source_preview_data_url=_load_source_preview(settings, source_artifact) if source_artifact else None,
        overlay_preview_data_url=overlay.preview_data_url if overlay else None,
    )


def run_scan_visual_evidence_generation(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: ScanVisualEvidenceRunCreate,
) -> tuple[ScanVisualEvidenceRunDetail, bool]:
    defect_run = _resolve_defect_run(session, owner_user_id=owner_user_id, scan_image_id=payload.scan_image_id)
    aggregation_run = _resolve_aggregation_run(
        session,
        owner_user_id=owner_user_id,
        scan_image_id=payload.scan_image_id,
        aggregation_run_id=payload.aggregation_run_id,
    )
    grading_run = _resolve_grading_run(
        session,
        owner_user_id=owner_user_id,
        scan_image_id=payload.scan_image_id,
        grading_assistance_run_id=payload.grading_assistance_run_id,
        aggregation_run_id=int(aggregation_run.id or 0) if aggregation_run else None,
    )
    boundary_run = session.get(ScanBoundaryRun, int(defect_run.boundary_run_id))
    source_artifact = session.get(ScanNormalizationArtifact, int(defect_run.source_artifact_id))
    if source_artifact is None:
        raise HTTPException(status_code=409, detail="Defect run is missing its normalized source artifact.")
    try:
        with Image.open(_resolve_normalization_artifact_path(settings, source_artifact)) as image_fp:
            image = _image_to_rgb(image_fp)
    except (FileNotFoundError, OSError, ValueError, UnidentifiedImageError) as exc:
        raise HTTPException(status_code=409, detail="Normalized source artifact is not available for visual evidence.") from exc

    defect_evidence = session.exec(
        select(ScanDefectEvidence).where(ScanDefectEvidence.defect_run_id == defect_run.id).order_by(col(ScanDefectEvidence.id))
    ).all()
    clusters: list[ScanDefectAggregateCluster] = []
    if aggregation_run is not None:
        clusters = session.exec(
            select(ScanDefectAggregateCluster)
            .where(ScanDefectAggregateCluster.aggregation_run_id == aggregation_run.id)
            .order_by(col(ScanDefectAggregateCluster.cluster_rank), col(ScanDefectAggregateCluster.id))
        ).all()

    grading_findings: list[ScanGradingAssistanceFinding] = []
    grading_categories: list[ScanGradingAssistanceCategory] = []
    grading_issues: list[ScanGradingAssistanceIssue] = []
    if grading_run is not None:
        grading_findings = session.exec(
            select(ScanGradingAssistanceFinding)
            .where(ScanGradingAssistanceFinding.grading_assistance_run_id == grading_run.id)
            .order_by(col(ScanGradingAssistanceFinding.category_id), col(ScanGradingAssistanceFinding.id))
        ).all()
        grading_categories = session.exec(
            select(ScanGradingAssistanceCategory)
            .where(ScanGradingAssistanceCategory.grading_assistance_run_id == grading_run.id)
            .order_by(col(ScanGradingAssistanceCategory.id))
        ).all()
        grading_issues = session.exec(
            select(ScanGradingAssistanceIssue)
            .where(ScanGradingAssistanceIssue.grading_assistance_run_id == grading_run.id)
            .order_by(col(ScanGradingAssistanceIssue.id))
        ).all()

    ocr_run = _load_ocr_run(session, boundary_run_id=int(boundary_run.id or 0)) if boundary_run else None
    ocr_regions: list[ScanOcrTextRegion] = []
    ocr_candidates: list[ScanOcrCandidate] = []
    if ocr_run is not None:
        ocr_regions = session.exec(
            select(ScanOcrTextRegion).where(ScanOcrTextRegion.ocr_run_id == ocr_run.id).order_by(col(ScanOcrTextRegion.id))
        ).all()
        ocr_candidates = session.exec(
            select(ScanOcrCandidate).where(ScanOcrCandidate.ocr_run_id == ocr_run.id).order_by(col(ScanOcrCandidate.id))
        ).all()

    recon_run = _load_reconciliation_run(session, owner_user_id=owner_user_id, scan_image_id=payload.scan_image_id)
    recon_candidates: list[ScanReconciliationCandidate] = []
    recon_decisions: list[ScanReconciliationDecision] = []
    if recon_run is not None:
        recon_candidates = session.exec(
            select(ScanReconciliationCandidate)
            .where(ScanReconciliationCandidate.reconciliation_run_id == recon_run.id)
            .order_by(col(ScanReconciliationCandidate.candidate_rank))
        ).all()
        recon_decisions = session.exec(
            select(ScanReconciliationDecision)
            .where(ScanReconciliationDecision.reconciliation_run_id == recon_run.id)
            .order_by(col(ScanReconciliationDecision.id))
        ).all()

    cluster_by_id = {int(row.id or 0): row for row in clusters}
    item_drafts = create_visual_evidence_items(
        defect_evidence=defect_evidence,
        clusters=clusters,
        grading_findings=grading_findings,
        grading_categories=grading_categories,
        cluster_by_id=cluster_by_id,
        boundary_run=boundary_run,
        ocr_regions=ocr_regions,
        ocr_candidates=ocr_candidates,
        recon_candidates=recon_candidates,
        recon_decisions=recon_decisions,
    )
    item_counts = {pkg: sum(1 for row in item_drafts if row.package_type == pkg) for pkg in _PACKAGE_ORDER}
    packages = build_evidence_packages(
        has_defect_items=any(row.package_type == "DEFECT_EVIDENCE_PACKAGE" for row in item_drafts),
        has_grading=grading_run is not None,
        has_ocr=ocr_run is not None,
        has_reconciliation=recon_run is not None,
        item_counts=item_counts,
    )
    annotations, annotation_issues = create_annotations(items=item_drafts, grading_issues=grading_issues)
    issues = _build_issues(
        items=item_drafts,
        annotations=annotations,
        annotation_issues=annotation_issues,
        aggregation_run=aggregation_run,
        grading_run=grading_run,
        packages=packages,
    )

    agg_lineage = dict((aggregation_run.output_manifest_json or {}).get("upstream_lineage") or {}) if aggregation_run else {}
    lineage = {
        **agg_lineage,
        "defect_checksum": defect_run.defect_checksum,
        "aggregation_checksum": aggregation_run.aggregation_checksum if aggregation_run else None,
        "grading_assistance_checksum": grading_run.grading_assistance_checksum if grading_run else None,
        "ocr_checksum": ocr_run.ocr_checksum if ocr_run else None,
        "reconciliation_checksum": recon_run.reconciliation_checksum if recon_run else None,
        "boundary_checksum": boundary_run.boundary_checksum if boundary_run else None,
        "source_checksum": defect_run.source_checksum,
    }

    provisional_artifacts = _artifact_drafts_for_run(
        image=image,
        packages=packages,
        items=item_drafts,
        annotations=annotations,
        manifest={},
    )
    provisional_manifest, visual_evidence_checksum = build_visual_evidence_manifest(
        lineage=lineage,
        packages=packages,
        items=item_drafts,
        annotations=annotations,
        issues=issues,
        artifact_checksums=[{"artifact_type": row.artifact_type, "artifact_checksum": _sha256_bytes(row.body)} for row in provisional_artifacts],
    )
    manifest_artifact = _ArtifactDraft("VISUAL_EVIDENCE_MANIFEST", _serialize_json_artifact(provisional_manifest), {"format": "json"}, ".json")
    artifacts = provisional_artifacts + [manifest_artifact]

    existing = session.exec(
        select(ScanVisualEvidenceRun).where(
            ScanVisualEvidenceRun.owner_user_id == owner_user_id,
            ScanVisualEvidenceRun.visual_evidence_checksum == visual_evidence_checksum,
        )
    ).first()
    if existing is not None:
        return _detail_from_run(session, settings, existing), False

    run = ScanVisualEvidenceRun(
        owner_user_id=owner_user_id,
        scan_image_id=payload.scan_image_id,
        aggregation_run_id=int(aggregation_run.id or 0) if aggregation_run else None,
        grading_assistance_run_id=int(grading_run.id or 0) if grading_run else None,
        source_checksum=defect_run.source_checksum,
        visual_evidence_checksum=visual_evidence_checksum,
        evidence_status="COMPLETE",
        engine_version=ENGINE_VERSION,
        input_manifest_json={
            "scan_image_id": payload.scan_image_id,
            "aggregation_run_id": aggregation_run.id if aggregation_run else None,
            "grading_assistance_run_id": grading_run.id if grading_run else None,
            "defect_run_id": defect_run.id,
        },
        output_manifest_json=provisional_manifest,
        completed_at=utc_now(),
    )
    session.add(run)
    session.flush()

    package_id_by_type: dict[str, int] = {}
    for pkg in packages:
        row = ScanVisualEvidencePackage(
            owner_user_id=owner_user_id,
            visual_evidence_run_id=int(run.id or 0),
            package_type=pkg.package_type,
            package_status=pkg.package_status,
            package_title=pkg.package_title,
            package_summary=pkg.package_summary,
            metadata_json=pkg.metadata_json,
        )
        session.add(row)
        session.flush()
        package_id_by_type[pkg.package_type] = int(row.id or 0)

    item_id_by_key: dict[str, int] = {}
    rank_by_package: dict[str, int] = {}
    for item in item_drafts:
        rank_by_package[item.package_type] = rank_by_package.get(item.package_type, 0) + 1
        row = ScanVisualEvidenceItem(
            owner_user_id=owner_user_id,
            visual_evidence_run_id=int(run.id or 0),
            package_id=package_id_by_type[item.package_type],
            item_rank=rank_by_package[item.package_type],
            source_system=item.source_system,
            source_record_id=item.source_record_id,
            item_type=item.item_type,
            item_title=item.item_title,
            item_summary=item.item_summary,
            confidence_score=item.confidence_score,
            severity_hint=item.severity_hint,
            region_type=item.region_type,
            metadata_json=item.metadata_json,
        )
        session.add(row)
        session.flush()
        item_id_by_key[item.item_key] = int(row.id or 0)

    for ann in annotations:
        item_id = item_id_by_key.get(ann.item_key)
        if item_id is None and ann.item_key.startswith("REVIEW_FLAG:"):
            item_id = next(iter(item_id_by_key.values()), None)
        if item_id is None:
            continue
        session.add(
            ScanVisualEvidenceAnnotation(
                owner_user_id=owner_user_id,
                visual_evidence_run_id=int(run.id or 0),
                item_id=item_id,
                annotation_type=ann.annotation_type,
                x_min=ann.x_min,
                y_min=ann.y_min,
                x_max=ann.x_max,
                y_max=ann.y_max,
                label=ann.label,
                confidence_score=ann.confidence_score,
                display_order=ann.display_order,
                style_hint=ann.style_hint,
                metadata_json=ann.metadata_json,
            )
        )

    for issue in issues:
        session.add(
            ScanVisualEvidenceIssue(
                owner_user_id=owner_user_id,
                visual_evidence_run_id=int(run.id or 0),
                issue_type=issue.issue_type,
                severity=issue.severity,
                issue_message=issue.issue_message,
                metadata_json=issue.metadata_json,
            )
        )

    history_rows = [
        _HistoryDraft("VISUAL_EVIDENCE_RUN_CREATED", "Created deterministic visual evidence run.", {"visual_evidence_checksum": visual_evidence_checksum}),
        _HistoryDraft("UPSTREAM_CONTEXT_LOADED", "Loaded upstream scan, defect, aggregation, and grading context.", {"item_count": len(item_drafts)}),
        _HistoryDraft("PACKAGES_BUILT", "Built review evidence packages and item cards.", {"package_count": len(packages)}),
        _HistoryDraft("OVERLAYS_WRITTEN", "Persisted replay-safe overlays and review packet exports.", {"artifact_count": len(artifacts)}),
    ]
    for row in history_rows:
        session.add(
            ScanVisualEvidenceHistory(
                owner_user_id=owner_user_id,
                visual_evidence_run_id=int(run.id or 0),
                event_type=row.event_type,
                event_message=row.event_message,
                event_checksum=_hash_payload(
                    {
                        "visual_evidence_run_id": int(run.id or 0),
                        "event_type": row.event_type,
                        "event_message": row.event_message,
                        "metadata_json": row.metadata_json,
                    }
                ),
                metadata_json=row.metadata_json,
            )
        )

    session.flush()
    for row in artifacts:
        relative_path = _artifact_storage_path(
            owner_user_id=owner_user_id,
            scan_image_id=payload.scan_image_id,
            visual_evidence_run_id=int(run.id or 0),
            artifact_type=row.artifact_type,
            ext=row.ext,
        )
        _save_artifact_bytes(settings, relative_path=relative_path, body=row.body)
        session.add(
            ScanVisualEvidenceArtifact(
                owner_user_id=owner_user_id,
                visual_evidence_run_id=int(run.id or 0),
                artifact_type=row.artifact_type,
                storage_path=relative_path,
                artifact_checksum=_sha256_bytes(row.body),
                metadata_json=row.metadata_json,
            )
        )

    session.commit()
    session.refresh(run)
    return _detail_from_run(session, settings, run), True


def get_scan_visual_evidence_run_owner(session: Session, settings: Settings, *, owner_user_id: int, run_id: int) -> ScanVisualEvidenceRunDetail:
    row = session.get(ScanVisualEvidenceRun, run_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Visual evidence run not found.")
    return _detail_from_run(session, settings, row)


def get_scan_visual_evidence_artifact_owner(session: Session, settings: Settings, *, owner_user_id: int, artifact_id: int) -> ScanVisualEvidenceArtifactRead:
    row = session.get(ScanVisualEvidenceArtifact, artifact_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Visual evidence artifact not found.")
    return ScanVisualEvidenceArtifactRead.model_validate(row).model_copy(update={"preview_data_url": _artifact_preview_data_url(settings, row)})


def _run_list_response(rows: list[ScanVisualEvidenceRun], *, limit: int, offset: int, total_items: int) -> ScanVisualEvidenceRunListResponse:
    status_counts = {status: sum(1 for row in rows if row.evidence_status == status) for status in sorted({row.evidence_status for row in rows})}
    incomplete = sum(
        1
        for row in rows
        if any(issue.get("issue_type") == "REVIEW_PACKET_INCOMPLETE" for issue in (row.output_manifest_json.get("issues") or []))
    )
    low_conf = sum(
        1
        for row in rows
        if any(issue.get("issue_type") == "LOW_EVIDENCE_CONFIDENCE" for issue in (row.output_manifest_json.get("issues") or []))
    )
    return ScanVisualEvidenceRunListResponse(
        items=[ScanVisualEvidenceRunRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        status_counts=status_counts,
        incomplete_review_packet_count=incomplete,
        low_confidence_package_count=low_conf,
    )


def list_scan_visual_evidence_runs_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanVisualEvidenceRunListResponse:
    limit, offset = clamp_scan_visual_evidence_pagination(limit=limit, offset=offset)
    stmt = select(ScanVisualEvidenceRun).where(ScanVisualEvidenceRun.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanVisualEvidenceRun).where(ScanVisualEvidenceRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanVisualEvidenceRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanVisualEvidenceRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanVisualEvidenceRun.created_at).desc(), col(ScanVisualEvidenceRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_visual_evidence_runs_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanVisualEvidenceRunListResponse:
    limit, offset = clamp_scan_visual_evidence_pagination(limit=limit, offset=offset)
    stmt = select(ScanVisualEvidenceRun)
    count_stmt = select(func.count()).select_from(ScanVisualEvidenceRun)
    if owner_user_id is not None:
        stmt = stmt.where(ScanVisualEvidenceRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanVisualEvidenceRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanVisualEvidenceRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanVisualEvidenceRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanVisualEvidenceRun.created_at).desc(), col(ScanVisualEvidenceRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_visual_evidence_packages_owner(
    session: Session,
    *,
    owner_user_id: int,
    visual_evidence_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanVisualEvidencePackageListResponse:
    limit, offset = clamp_scan_visual_evidence_pagination(limit=limit, offset=offset)
    stmt = select(ScanVisualEvidencePackage).where(ScanVisualEvidencePackage.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanVisualEvidencePackage).where(ScanVisualEvidencePackage.owner_user_id == owner_user_id)
    if visual_evidence_run_id is not None:
        stmt = stmt.where(ScanVisualEvidencePackage.visual_evidence_run_id == visual_evidence_run_id)
        count_stmt = count_stmt.where(ScanVisualEvidencePackage.visual_evidence_run_id == visual_evidence_run_id)
    rows = session.exec(stmt.order_by(col(ScanVisualEvidencePackage.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanVisualEvidencePackageListResponse(
        items=[ScanVisualEvidencePackageRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        package_type_counts={key: sum(1 for row in rows if row.package_type == key) for key in sorted({row.package_type for row in rows})},
    )


def list_scan_visual_evidence_items_owner(
    session: Session,
    *,
    owner_user_id: int,
    visual_evidence_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanVisualEvidenceItemListResponse:
    limit, offset = clamp_scan_visual_evidence_pagination(limit=limit, offset=offset)
    stmt = select(ScanVisualEvidenceItem).where(ScanVisualEvidenceItem.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanVisualEvidenceItem).where(ScanVisualEvidenceItem.owner_user_id == owner_user_id)
    if visual_evidence_run_id is not None:
        stmt = stmt.where(ScanVisualEvidenceItem.visual_evidence_run_id == visual_evidence_run_id)
        count_stmt = count_stmt.where(ScanVisualEvidenceItem.visual_evidence_run_id == visual_evidence_run_id)
    rows = session.exec(stmt.order_by(col(ScanVisualEvidenceItem.package_id), col(ScanVisualEvidenceItem.item_rank)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanVisualEvidenceItemListResponse(
        items=[ScanVisualEvidenceItemRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        source_system_counts={key: sum(1 for row in rows if row.source_system == key) for key in sorted({row.source_system for row in rows})},
    )


def list_scan_visual_evidence_annotations_owner(
    session: Session,
    *,
    owner_user_id: int,
    visual_evidence_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanVisualEvidenceAnnotationListResponse:
    limit, offset = clamp_scan_visual_evidence_pagination(limit=limit, offset=offset)
    stmt = select(ScanVisualEvidenceAnnotation).where(ScanVisualEvidenceAnnotation.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanVisualEvidenceAnnotation).where(ScanVisualEvidenceAnnotation.owner_user_id == owner_user_id)
    if visual_evidence_run_id is not None:
        stmt = stmt.where(ScanVisualEvidenceAnnotation.visual_evidence_run_id == visual_evidence_run_id)
        count_stmt = count_stmt.where(ScanVisualEvidenceAnnotation.visual_evidence_run_id == visual_evidence_run_id)
    rows = session.exec(stmt.order_by(col(ScanVisualEvidenceAnnotation.display_order), col(ScanVisualEvidenceAnnotation.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanVisualEvidenceAnnotationListResponse(
        items=[ScanVisualEvidenceAnnotationRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        annotation_type_counts={key: sum(1 for row in rows if row.annotation_type == key) for key in sorted({row.annotation_type for row in rows})},
    )


def list_scan_visual_evidence_issues_owner(
    session: Session,
    *,
    owner_user_id: int,
    visual_evidence_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanVisualEvidenceIssueListResponse:
    limit, offset = clamp_scan_visual_evidence_pagination(limit=limit, offset=offset)
    stmt = select(ScanVisualEvidenceIssue).where(ScanVisualEvidenceIssue.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanVisualEvidenceIssue).where(ScanVisualEvidenceIssue.owner_user_id == owner_user_id)
    if visual_evidence_run_id is not None:
        stmt = stmt.where(ScanVisualEvidenceIssue.visual_evidence_run_id == visual_evidence_run_id)
        count_stmt = count_stmt.where(ScanVisualEvidenceIssue.visual_evidence_run_id == visual_evidence_run_id)
    rows = session.exec(stmt.order_by(col(ScanVisualEvidenceIssue.created_at), col(ScanVisualEvidenceIssue.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanVisualEvidenceIssueListResponse(
        items=[ScanVisualEvidenceIssueRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        issue_type_counts={key: sum(1 for row in rows if row.issue_type == key) for key in sorted({row.issue_type for row in rows})},
    )


def list_scan_visual_evidence_issues_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanVisualEvidenceIssueListResponse:
    limit, offset = clamp_scan_visual_evidence_pagination(limit=limit, offset=offset)
    stmt = select(ScanVisualEvidenceIssue)
    count_stmt = select(func.count()).select_from(ScanVisualEvidenceIssue)
    if owner_user_id is not None:
        stmt = stmt.where(ScanVisualEvidenceIssue.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanVisualEvidenceIssue.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanVisualEvidenceIssue.created_at), col(ScanVisualEvidenceIssue.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanVisualEvidenceIssueListResponse(
        items=[ScanVisualEvidenceIssueRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        issue_type_counts={key: sum(1 for row in rows if row.issue_type == key) for key in sorted({row.issue_type for row in rows})},
    )


def list_scan_visual_evidence_failures_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanVisualEvidenceFailureListResponse:
    limit, offset = clamp_scan_visual_evidence_pagination(limit=limit, offset=offset)
    stmt = select(ScanVisualEvidenceRun).where(ScanVisualEvidenceRun.evidence_status == "FAILED")
    count_stmt = select(func.count()).select_from(ScanVisualEvidenceRun).where(ScanVisualEvidenceRun.evidence_status == "FAILED")
    if owner_user_id is not None:
        stmt = stmt.where(ScanVisualEvidenceRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanVisualEvidenceRun.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanVisualEvidenceRun.created_at).desc(), col(ScanVisualEvidenceRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanVisualEvidenceFailureListResponse(
        items=[ScanVisualEvidenceRunRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )
