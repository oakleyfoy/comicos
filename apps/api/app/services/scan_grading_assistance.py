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
    ScanDefectAggregationArtifact,
    ScanDefectAggregationIssue,
    ScanDefectAggregationRun,
    ScanDefectAggregateEvidence,
    ScanDefectAggregateCluster,
    ScanDefectIssue,
    ScanDefectRun,
    ScanGradingAssistanceArtifact,
    ScanGradingAssistanceCategory,
    ScanGradingAssistanceFinding,
    ScanGradingAssistanceHistory,
    ScanGradingAssistanceIssue,
    ScanGradingAssistanceRun,
    ScanImage,
    ScanNormalizationArtifact,
    ScanNormalizationRun,
    ScanReconciliationRun,
)
from app.schemas.scan_grading_assistance import (
    ScanGradingAssistanceArtifactRead,
    ScanGradingAssistanceCategoryListResponse,
    ScanGradingAssistanceCategoryRead,
    ScanGradingAssistanceFailureListResponse,
    ScanGradingAssistanceFindingListResponse,
    ScanGradingAssistanceFindingRead,
    ScanGradingAssistanceHistoryRead,
    ScanGradingAssistanceIssueListResponse,
    ScanGradingAssistanceIssueRead,
    ScanGradingAssistanceRunCreate,
    ScanGradingAssistanceRunDetail,
    ScanGradingAssistanceRunListResponse,
    ScanGradingAssistanceRunRead,
)
from app.services.grading_rubric import (
    CATEGORY_WEIGHTING,
    REVIEW_REQUIRED_THRESHOLDS,
    RUBRIC_VERSION,
    PRESSURE_SCORES,
    pressure_hint_from_inputs,
    quality_issue_score,
    score_from_pressure,
    summarize_category_status,
    support_band_for_score,
)
from app.services.scan_defects import _load_source_preview, _resolve_normalization_artifact_path

ENGINE_VERSION = "P40-12-v1"
_PREVIEW_MAX = 420
_CATEGORY_ORDER = ("SPINE", "CORNERS", "EDGES", "SURFACE", "STRUCTURE", "PRESENTATION", "OVERALL_SUPPORT")


@dataclass(frozen=True)
class _ReviewFlag:
    flag_type: str
    severity: str
    message: str
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _FindingDraft:
    category_type: str
    source_cluster_id: int | None
    source_detector: str
    finding_type: str
    finding_severity_hint: str
    confidence_score: float
    grade_pressure_hint: str
    finding_text: str
    measurement_json: dict[str, Any]
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _CategoryDraft:
    category_type: str
    category_status: str
    suggested_range_low: float
    suggested_range_high: float
    confidence_score: float
    evidence_count: int
    summary_text: str
    measurement_json: dict[str, Any]
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
    from app.models.scan_grading_assistance import utc_now as _utc_now

    return _utc_now()


def clamp_scan_grading_assistance_pagination(*, limit: int, offset: int) -> tuple[int, int]:
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


def _resolve_grading_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.scan_grading_assistance_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("scan grading assistance storage path escapes configured root")
    return target


def _artifact_storage_path(
    *,
    owner_user_id: int,
    scan_image_id: int,
    grading_assistance_run_id: int,
    artifact_type: str,
    ext: str,
) -> str:
    safe_type = artifact_type.lower()
    return f"scan-grading-assistance/{owner_user_id}/{scan_image_id}/{grading_assistance_run_id}/{safe_type}{ext}".replace("\\", "/")


def _save_artifact_bytes(settings: Settings, *, relative_path: str, body: bytes) -> None:
    target = _resolve_grading_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)


def _artifact_preview_data_url(settings: Settings, row: ScanGradingAssistanceArtifact) -> str | None:
    if not row.storage_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        return None
    try:
        body = _resolve_grading_storage_path(settings, row.storage_path).read_bytes()
    except OSError:
        return None
    return f"data:image/png;base64,{base64.b64encode(body).decode('ascii')}"


def _serialize_json_artifact(payload: Any) -> bytes:
    return json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"), indent=2).encode("utf-8")


def _minimal_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (12, 12, 16)).save(buf, format="PNG")
    return buf.getvalue()


def _image_to_rgb(image: Image.Image) -> Image.Image:
    return image.copy().convert("RGB") if image.mode != "RGB" else image.copy()


def _resolve_aggregation_run(session: Session, *, owner_user_id: int, payload: ScanGradingAssistanceRunCreate) -> ScanDefectAggregationRun:
    stmt = select(ScanDefectAggregationRun).where(
        ScanDefectAggregationRun.owner_user_id == owner_user_id,
        ScanDefectAggregationRun.scan_image_id == payload.scan_image_id,
        ScanDefectAggregationRun.aggregation_status == "COMPLETE",
    )
    if payload.aggregation_run_id is not None:
        stmt = stmt.where(ScanDefectAggregationRun.id == payload.aggregation_run_id)
    row = session.exec(stmt.order_by(col(ScanDefectAggregationRun.id).desc())).first()
    if row is None:
        raise HTTPException(status_code=409, detail="A complete defect aggregation run is required before grading assistance.")
    return row


def _resolve_reconciliation_run(
    session: Session,
    *,
    owner_user_id: int,
    payload: ScanGradingAssistanceRunCreate,
) -> ScanReconciliationRun | None:
    if payload.reconciliation_run_id is not None:
        row = session.get(ScanReconciliationRun, payload.reconciliation_run_id)
        if row is None or int(row.owner_user_id) != owner_user_id:
            raise HTTPException(status_code=404, detail="Reconciliation run not found.")
        return row
    stmt = select(ScanReconciliationRun).where(
        ScanReconciliationRun.owner_user_id == owner_user_id,
        ScanReconciliationRun.scan_image_id == payload.scan_image_id,
        ScanReconciliationRun.reconciliation_status != "FAILED",
    )
    return session.exec(stmt.order_by(col(ScanReconciliationRun.id).desc())).first()


def _cluster_status_hint(cluster: ScanDefectAggregateCluster) -> str:
    cluster_type = str(cluster.cluster_type)
    if cluster_type == "SPINE_CLUSTER":
        return "SPINE_STRESS_SUPPORT"
    if cluster_type == "CORNER_CLUSTER":
        return "CORNER_WEAR_SUPPORT"
    if cluster_type == "EDGE_CLUSTER":
        return "EDGE_WEAR_SUPPORT"
    if cluster_type == "STRUCTURAL_CLUSTER":
        return "STRUCTURAL_DAMAGE_SUPPORT"
    return "SURFACE_DEFECT_SUPPORT"


def _map_cluster_to_category(cluster: ScanDefectAggregateCluster) -> tuple[str, ...]:
    mapping = {
        "SPINE": ("SPINE",),
        "CORNER": ("CORNERS",),
        "EDGE": ("EDGES",),
        "SURFACE": ("SURFACE",),
        "STRUCTURAL": ("STRUCTURE",),
        "MIXED": ("SURFACE", "STRUCTURE"),
    }
    categories = mapping.get(str(cluster.cluster_region), ("SURFACE",))
    if "STRUCTURE" not in categories:
        return categories + ("PRESENTATION",)
    return categories + ("PRESENTATION",)


def map_evidence_to_categories(
    *,
    clusters: list[ScanDefectAggregateCluster],
    aggregation_evidence: list[dict[str, Any]],
    defect_issues: list[ScanDefectIssue],
    aggregation_issues: list[ScanDefectAggregationIssue],
) -> tuple[dict[str, list[_FindingDraft]], list[_ReviewFlag]]:
    findings_by_category: dict[str, list[_FindingDraft]] = {category: [] for category in _CATEGORY_ORDER}
    review_flags: list[_ReviewFlag] = []

    evidence_lookup: dict[int, list[dict[str, Any]]] = {}
    for row in aggregation_evidence:
        evidence_lookup.setdefault(int(row["cluster_id"]), []).append(row)

    for cluster in clusters:
        categories = _map_cluster_to_category(cluster)
        dominant_detector = str((cluster.metadata_json or {}).get("dominant_detector") or "P40_11_AGGREGATION")
        pressure_hint = pressure_hint_from_inputs(
            severity_hint=str(cluster.aggregate_severity_hint),
            confidence_score=float(cluster.cluster_confidence),
            weight=CATEGORY_WEIGHTING.get(categories[0], 1.0),
        )
        supporting_sources = sorted({row["source_detector"] for row in evidence_lookup.get(int(cluster.id or 0), [])})
        for category in categories:
            findings_by_category[category].append(
                _FindingDraft(
                    category_type=category,
                    source_cluster_id=int(cluster.id or 0),
                    source_detector=dominant_detector,
                    finding_type=_cluster_status_hint(cluster),
                    finding_severity_hint=str(cluster.aggregate_severity_hint),
                    confidence_score=round(float(cluster.cluster_confidence), 6),
                    grade_pressure_hint=pressure_hint,
                    finding_text=f"{cluster.cluster_type} mapped into {category} support with {len(evidence_lookup.get(int(cluster.id or 0), []))} source evidence references.",
                    measurement_json=dict(cluster.measurement_json or {}),
                    metadata_json={
                        "cluster_type": cluster.cluster_type,
                        "cluster_region": cluster.cluster_region,
                        "supporting_sources": supporting_sources,
                    },
                )
            )

    scan_quality_issue_types = {
        "LOW_RESOLUTION",
        "LOW_DPI",
        "EXCESSIVE_BLUR",
        "EXCESSIVE_GLARE",
        "OVEREXPOSED_IMAGE",
        "UNDEREXPOSED_IMAGE",
        "INSUFFICIENT_CONTRAST",
        "QUALITY_GATE_FAILED",
        "INSUFFICIENT_IMAGE_QUALITY",
    }
    for issue in defect_issues:
        if issue.issue_type not in scan_quality_issue_types:
            continue
        pressure = "HIGH" if quality_issue_score(issue.issue_type) >= REVIEW_REQUIRED_THRESHOLDS["scan_quality_issue_score"] else "MODERATE"
        findings_by_category["PRESENTATION"].append(
            _FindingDraft(
                category_type="PRESENTATION",
                source_cluster_id=None,
                source_detector="P40_06_DEFECT_FOUNDATION",
                finding_type="SCAN_QUALITY_LIMITATION",
                finding_severity_hint="MODERATE",
                confidence_score=0.6,
                grade_pressure_hint=pressure,
                finding_text=issue.issue_message,
                measurement_json={"quality_issue_score": quality_issue_score(issue.issue_type)},
                metadata_json={"issue_type": issue.issue_type},
            )
        )
        review_flags.append(
            _ReviewFlag(
                flag_type="LOW_SCAN_QUALITY",
                severity="WARNING",
                message=issue.issue_message,
                metadata_json={"issue_type": issue.issue_type},
            )
        )

    for issue in aggregation_issues:
        if issue.issue_type in {"GEOMETRY_CONFLICT", "OVERLAPPING_REGION_CONFLICT"}:
            findings_by_category["OVERALL_SUPPORT"].append(
                _FindingDraft(
                    category_type="OVERALL_SUPPORT",
                    source_cluster_id=None,
                    source_detector="P40_11_AGGREGATION",
                    finding_type="EVIDENCE_CONFLICT",
                    finding_severity_hint="MODERATE",
                    confidence_score=0.55,
                    grade_pressure_hint="HIGH",
                    finding_text=issue.issue_message,
                    measurement_json={},
                    metadata_json={"issue_type": issue.issue_type},
                )
            )
            review_flags.append(
                _ReviewFlag(
                    flag_type="CONFLICTING_EVIDENCE",
                    severity="WARNING",
                    message=issue.issue_message,
                    metadata_json={"issue_type": issue.issue_type},
                )
            )
        if issue.issue_type == "LOW_CLUSTER_CONFIDENCE":
            review_flags.append(
                _ReviewFlag(
                    flag_type="LOW_CONFIDENCE_ACROSS_MAJOR_REGIONS",
                    severity="WARNING",
                    message=issue.issue_message,
                    metadata_json={"issue_type": issue.issue_type},
                )
            )

    return findings_by_category, review_flags


def calculate_category_support_ranges(
    *,
    findings_by_category: dict[str, list[_FindingDraft]],
    review_flags: list[_ReviewFlag],
) -> tuple[list[_CategoryDraft], list[_ReviewFlag]]:
    category_drafts: list[_CategoryDraft] = []
    mutable_flags = list(review_flags)
    for category in _CATEGORY_ORDER[:-1]:
        findings = sorted(
            findings_by_category.get(category, []),
            key=lambda row: (row.source_cluster_id or 0, row.finding_type, row.grade_pressure_hint, row.finding_text),
        )
        evidence_count = sum(1 for finding in findings if finding.source_cluster_id is not None)
        insufficient = evidence_count == 0
        confidence = round(sum(finding.confidence_score for finding in findings) / max(1, len(findings)), 6)
        weighted_pressure = sum(score_from_pressure(finding.grade_pressure_hint) * finding.confidence_score for finding in findings)
        normalized_score = round(
            min(1.0, (weighted_pressure / max(1, len(findings)))) * CATEGORY_WEIGHTING.get(category, 1.0),
            6,
        )
        review_required = insufficient or confidence < REVIEW_REQUIRED_THRESHOLDS["category_mean_confidence_floor"]
        if category == "STRUCTURE" and any(finding.finding_severity_hint == "MAJOR" for finding in findings) and REVIEW_REQUIRED_THRESHOLDS["major_structure_requires_review"]:
            review_required = True
            mutable_flags.append(
                _ReviewFlag(
                    flag_type="HIGH_SEVERITY_STRUCTURAL_EVIDENCE",
                    severity="WARNING",
                    message="Major structural evidence requires human review before relying on the support band.",
                    metadata_json={"category_type": category},
                )
            )
        band = support_band_for_score(normalized_score=normalized_score, review_required=review_required, insufficient_evidence=insufficient)
        if insufficient:
            mutable_flags.append(
                _ReviewFlag(
                    flag_type="INSUFFICIENT_EVIDENCE",
                    severity="INFO",
                    message=f"{category} lacked enough upstream evidence for a narrow support range.",
                    metadata_json={"category_type": category},
                )
            )
        summary = (
            f"{category} support range {band['low']:.1f}-{band['high']:.1f} from {evidence_count} evidence-linked findings."
            if not insufficient
            else f"{category} has insufficient evidence for a narrow support range."
        )
        category_drafts.append(
            _CategoryDraft(
                category_type=category,
                category_status=summarize_category_status(support_band_status=str(band["status"]), review_required=review_required),
                suggested_range_low=float(band["low"]),
                suggested_range_high=float(band["high"]),
                confidence_score=confidence,
                evidence_count=evidence_count,
                summary_text=summary,
                measurement_json={
                    "mean_confidence": confidence,
                    "pressure_score": normalized_score,
                    "grade_pressure_distribution": {
                        key: sum(1 for finding in findings if finding.grade_pressure_hint == key)
                        for key in ("NONE", "LOW", "MODERATE", "HIGH", "SEVERE")
                    },
                },
                metadata_json={"support_band_label": band["label"]},
            )
        )
    return category_drafts, mutable_flags


def generate_review_required_flags(
    *,
    categories: list[_CategoryDraft],
    clusters: list[ScanDefectAggregateCluster],
    review_flags: list[_ReviewFlag],
) -> list[_ReviewFlag]:
    mutable = list(review_flags)
    mixed_ratio = sum(1 for cluster in clusters if cluster.cluster_type == "MIXED_CLUSTER") / max(1, len(clusters))
    if mixed_ratio >= REVIEW_REQUIRED_THRESHOLDS["mixed_cluster_ratio"]:
        mutable.append(
            _ReviewFlag(
                flag_type="AMBIGUOUS_AGGREGATION_CLUSTERS",
                severity="INFO",
                message="Mixed aggregation clusters widen the support range and require review.",
                metadata_json={"mixed_cluster_ratio": round(mixed_ratio, 6)},
            )
        )
    weak_categories = [category.category_type for category in categories if category.confidence_score < REVIEW_REQUIRED_THRESHOLDS["category_mean_confidence_floor"]]
    if weak_categories:
        mutable.append(
            _ReviewFlag(
                flag_type="LOW_CONFIDENCE_ACROSS_MAJOR_REGIONS",
                severity="WARNING",
                message="Several major grading categories have low confidence support.",
                metadata_json={"categories": weak_categories},
            )
        )
    unique: dict[tuple[str, str], _ReviewFlag] = {}
    for flag in mutable:
        unique[(flag.flag_type, flag.message)] = flag
    return list(unique.values())


def calculate_overall_support_range(
    *,
    categories: list[_CategoryDraft],
    review_flags: list[_ReviewFlag],
    findings_by_category: dict[str, list[_FindingDraft]],
) -> tuple[_CategoryDraft, list[_FindingDraft]]:
    scoped = [category for category in categories if category.category_type != "PRESENTATION"]
    if not scoped:
        band = support_band_for_score(normalized_score=1.0, review_required=True, insufficient_evidence=True)
        overall = _CategoryDraft(
            category_type="OVERALL_SUPPORT",
            category_status="INSUFFICIENT_EVIDENCE",
            suggested_range_low=float(band["low"]),
            suggested_range_high=float(band["high"]),
            confidence_score=0.0,
            evidence_count=0,
            summary_text="Overall support range is limited because no category evidence was available.",
            measurement_json={},
            metadata_json={"support_band_label": band["label"]},
        )
        return overall, []

    weakest_low = min(category.suggested_range_low for category in scoped)
    weakest_high = min(category.suggested_range_high for category in scoped)
    mean_confidence = round(sum(category.confidence_score for category in scoped) / max(1, len(scoped)), 6)
    review_required = any(category.category_status == "REVIEW_REQUIRED" for category in scoped) or bool(review_flags)
    support_score = min(1.0, 10.0 - weakest_high) / 10.0 + (0.1 if review_required else 0.0)
    band = support_band_for_score(normalized_score=support_score, review_required=review_required, insufficient_evidence=False)
    low = min(float(band["low"]), weakest_low)
    high = min(float(band["high"]), weakest_high)
    limiting_categories = [category.category_type for category in scoped if category.suggested_range_high == weakest_high or category.category_status == "REVIEW_REQUIRED"]
    overall = _CategoryDraft(
        category_type="OVERALL_SUPPORT",
        category_status=summarize_category_status(support_band_status=str(band["status"]), review_required=review_required),
        suggested_range_low=round(low, 1),
        suggested_range_high=round(high, 1),
        confidence_score=mean_confidence,
        evidence_count=sum(category.evidence_count for category in scoped),
        summary_text=f"Support Range: {round(low,1):.1f}-{round(high,1):.1f}; limited by {', '.join(sorted(set(limiting_categories)))}.",
        measurement_json={
            "mean_confidence": mean_confidence,
            "limiting_categories": sorted(set(limiting_categories)),
            "review_flag_count": len(review_flags),
        },
        metadata_json={"support_band_label": band["label"]},
    )
    overall_findings = sorted(findings_by_category.get("OVERALL_SUPPORT", []), key=lambda row: (row.source_cluster_id or 0, row.finding_type, row.finding_text))
    if review_required:
        overall_findings.append(
            _FindingDraft(
                category_type="OVERALL_SUPPORT",
                source_cluster_id=None,
                source_detector="P40_12_GRADING_ASSISTANCE",
                finding_type="REVIEW_REQUIRED_FLAG",
                finding_severity_hint="MODERATE",
                confidence_score=mean_confidence,
                grade_pressure_hint="HIGH",
                finding_text="Review required because scan quality, evidence conflict, or category confidence widened the support range.",
                measurement_json={"review_flag_count": len(review_flags)},
                metadata_json={"limiting_categories": sorted(set(limiting_categories))},
            )
        )
    return overall, overall_findings


def _build_issues(
    *,
    defect_issues: list[ScanDefectIssue],
    aggregation_issues: list[ScanDefectAggregationIssue],
    categories: list[_CategoryDraft],
    review_flags: list[_ReviewFlag],
) -> list[_IssueDraft]:
    issues: list[_IssueDraft] = []
    if not categories:
        issues.append(
            _IssueDraft(
                issue_type="GRADING_ASSISTANCE_FAILED",
                severity="ERROR",
                issue_message="No grading assistance categories were produced.",
                metadata_json={},
            )
        )
        return issues
    if any(issue.issue_type in {"LOW_RESOLUTION", "LOW_DPI", "EXCESSIVE_BLUR", "EXCESSIVE_GLARE", "INSUFFICIENT_IMAGE_QUALITY"} for issue in defect_issues):
        issues.append(
            _IssueDraft(
                issue_type="LOW_SCAN_QUALITY",
                severity="WARNING",
                issue_message="Scan quality limitations widened one or more support ranges.",
                metadata_json={"source_issue_count": sum(1 for issue in defect_issues if issue.issue_type in {"LOW_RESOLUTION", "LOW_DPI", "EXCESSIVE_BLUR", "EXCESSIVE_GLARE", "INSUFFICIENT_IMAGE_QUALITY"})},
            )
        )
    if any(category.category_status == "INSUFFICIENT_EVIDENCE" for category in categories):
        issues.append(
            _IssueDraft(
                issue_type="INSUFFICIENT_EVIDENCE",
                severity="INFO",
                issue_message="At least one grading category had insufficient evidence for a narrow support band.",
                metadata_json={"categories": [category.category_type for category in categories if category.category_status == "INSUFFICIENT_EVIDENCE"]},
            )
        )
    if any(issue.issue_type in {"GEOMETRY_CONFLICT", "OVERLAPPING_REGION_CONFLICT"} for issue in aggregation_issues):
        issues.append(
            _IssueDraft(
                issue_type="EVIDENCE_CONFLICT",
                severity="WARNING",
                issue_message="Aggregation reported conflicts that require review during grading assistance.",
                metadata_json={},
            )
        )
    if any(category.category_status == "REVIEW_REQUIRED" for category in categories) or review_flags:
        issues.append(
            _IssueDraft(
                issue_type="REVIEW_REQUIRED",
                severity="WARNING",
                issue_message="Human review is required before relying on the suggested support range.",
                metadata_json={"review_flag_count": len(review_flags)},
            )
        )
    if sum(category.confidence_score for category in categories) / max(1, len(categories)) < 0.45:
        issues.append(
            _IssueDraft(
                issue_type="LOW_GRADING_CONFIDENCE",
                severity="WARNING",
                issue_message="Mean grading assistance confidence is low.",
                metadata_json={"mean_confidence": round(sum(category.confidence_score for category in categories) / max(1, len(categories)), 6)},
            )
        )
    return issues


def build_grading_assistance_manifest(
    *,
    aggregation_run: ScanDefectAggregationRun,
    reconciliation_run: ScanReconciliationRun | None,
    categories: list[_CategoryDraft],
    findings: list[_FindingDraft],
    review_flags: list[_ReviewFlag],
    issues: list[_IssueDraft],
    artifact_checksums: list[dict[str, str]],
) -> tuple[dict[str, Any], str]:
    aggregation_lineage = dict((aggregation_run.output_manifest_json or {}).get("upstream_lineage") or {})
    manifest = {
        "engine_version": ENGINE_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "upstream_lineage": {
            **aggregation_lineage,
            "aggregation_checksum": aggregation_run.aggregation_checksum,
            "reconciliation_checksum": reconciliation_run.reconciliation_checksum if reconciliation_run else None,
            "source_checksum": aggregation_run.source_checksum,
        },
        "category_summaries": [
            {
                "category_type": category.category_type,
                "category_status": category.category_status,
                "suggested_range_low": category.suggested_range_low,
                "suggested_range_high": category.suggested_range_high,
                "confidence_score": category.confidence_score,
                "evidence_count": category.evidence_count,
                "summary_text": category.summary_text,
                "measurement_json": category.measurement_json,
            }
            for category in categories
        ],
        "findings": [
            {
                "category_type": finding.category_type,
                "source_cluster_id": finding.source_cluster_id,
                "source_detector": finding.source_detector,
                "finding_type": finding.finding_type,
                "finding_severity_hint": finding.finding_severity_hint,
                "confidence_score": finding.confidence_score,
                "grade_pressure_hint": finding.grade_pressure_hint,
                "finding_text": finding.finding_text,
                "measurement_json": finding.measurement_json,
                "metadata_json": finding.metadata_json,
            }
            for finding in findings
        ],
        "review_flags": [
            {
                "flag_type": flag.flag_type,
                "severity": flag.severity,
                "message": flag.message,
                "metadata_json": flag.metadata_json,
            }
            for flag in review_flags
        ],
        "issues": [
            {
                "issue_type": issue.issue_type,
                "severity": issue.severity,
                "issue_message": issue.issue_message,
                "metadata_json": issue.metadata_json,
            }
            for issue in issues
        ],
        "artifact_checksums": artifact_checksums,
        "overall_support": next((category.measurement_json for category in categories if category.category_type == "OVERALL_SUPPORT"), {}),
    }
    return manifest, _hash_payload(manifest)


def _build_debug_preview(image: Image.Image, clusters: list[ScanDefectAggregateCluster], categories: list[_CategoryDraft]) -> bytes:
    rendered = _image_to_rgb(image)
    draw = ImageDraw.Draw(rendered)
    palette = {"STRONG": "#22c55e", "ACCEPTABLE": "#84cc16", "LIMITED": "#f59e0b", "REVIEW_REQUIRED": "#ef4444", "INSUFFICIENT_EVIDENCE": "#64748b"}
    status_by_region = {
        "SPINE": next((category.category_status for category in categories if category.category_type == "SPINE"), "LIMITED"),
        "CORNERS": next((category.category_status for category in categories if category.category_type == "CORNERS"), "LIMITED"),
        "EDGES": next((category.category_status for category in categories if category.category_type == "EDGES"), "LIMITED"),
        "SURFACE": next((category.category_status for category in categories if category.category_type == "SURFACE"), "LIMITED"),
        "STRUCTURE": next((category.category_status for category in categories if category.category_type == "STRUCTURE"), "LIMITED"),
        "MIXED": "REVIEW_REQUIRED",
    }
    for cluster in clusters:
        draw.rectangle(
            (cluster.x_min, cluster.y_min, cluster.x_max, cluster.y_max),
            outline=palette.get(status_by_region.get(str(cluster.cluster_region), "LIMITED"), "#ffffff"),
            width=2,
        )
    rendered.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
    buf = io.BytesIO()
    rendered.save(buf, format="PNG")
    return buf.getvalue()


def _artifact_drafts_for_run(
    *,
    image: Image.Image,
    clusters: list[ScanDefectAggregateCluster],
    categories: list[_CategoryDraft],
    findings: list[_FindingDraft],
    review_flags: list[_ReviewFlag],
) -> list[_ArtifactDraft]:
    overall = next((category for category in categories if category.category_type == "OVERALL_SUPPORT"), None)
    return [
        _ArtifactDraft(
            "GRADING_SUPPORT_REPORT",
            _serialize_json_artifact({"overall_support": overall.measurement_json if overall else {}, "categories": [category.measurement_json for category in categories]}),
            {"format": "json"},
            ".json",
        ),
        _ArtifactDraft(
            "CATEGORY_SUMMARY_EXPORT",
            _serialize_json_artifact([{ "category_type": category.category_type, "summary_text": category.summary_text, "suggested_range_low": category.suggested_range_low, "suggested_range_high": category.suggested_range_high, "category_status": category.category_status } for category in categories]),
            {"format": "json"},
            ".json",
        ),
        _ArtifactDraft(
            "EVIDENCE_TO_GRADE_MAP",
            _serialize_json_artifact([{ "category_type": finding.category_type, "source_cluster_id": finding.source_cluster_id, "source_detector": finding.source_detector, "grade_pressure_hint": finding.grade_pressure_hint, "finding_type": finding.finding_type } for finding in findings]),
            {"format": "json"},
            ".json",
        ),
        _ArtifactDraft(
            "REVIEW_REQUIRED_REPORT",
            _serialize_json_artifact([{ "flag_type": flag.flag_type, "severity": flag.severity, "message": flag.message } for flag in review_flags]),
            {"format": "json"},
            ".json",
        ),
        _ArtifactDraft("GRADING_DEBUG_PREVIEW", _build_debug_preview(image, clusters, categories), {"format": "png"}, ".png"),
    ]


def _detail_from_run(session: Session, settings: Settings, run: ScanGradingAssistanceRun) -> ScanGradingAssistanceRunDetail:
    categories = session.exec(
        select(ScanGradingAssistanceCategory)
        .where(ScanGradingAssistanceCategory.grading_assistance_run_id == run.id)
        .order_by(col(ScanGradingAssistanceCategory.id))
    ).all()
    findings = session.exec(
        select(ScanGradingAssistanceFinding)
        .where(ScanGradingAssistanceFinding.grading_assistance_run_id == run.id)
        .order_by(col(ScanGradingAssistanceFinding.category_id), col(ScanGradingAssistanceFinding.id))
    ).all()
    artifacts = session.exec(
        select(ScanGradingAssistanceArtifact)
        .where(ScanGradingAssistanceArtifact.grading_assistance_run_id == run.id)
        .order_by(col(ScanGradingAssistanceArtifact.id))
    ).all()
    issues = session.exec(
        select(ScanGradingAssistanceIssue)
        .where(ScanGradingAssistanceIssue.grading_assistance_run_id == run.id)
        .order_by(col(ScanGradingAssistanceIssue.id))
    ).all()
    history = session.exec(
        select(ScanGradingAssistanceHistory)
        .where(ScanGradingAssistanceHistory.grading_assistance_run_id == run.id)
        .order_by(col(ScanGradingAssistanceHistory.id))
    ).all()
    aggregation_run = session.get(ScanDefectAggregationRun, int(run.aggregation_run_id))
    defect_run_id = aggregation_run.input_manifest_json.get("defect_run_id") if aggregation_run else None
    defect_run = session.get(ScanDefectRun, int(defect_run_id)) if defect_run_id else None
    scan_image = session.get(ScanImage, int(run.scan_image_id))
    norm_run = session.get(ScanNormalizationRun, int(defect_run.normalization_run_id)) if defect_run else None
    boundary_run = session.get(ScanBoundaryRun, int(defect_run.boundary_run_id)) if defect_run else None
    source_artifact = session.get(ScanNormalizationArtifact, int(defect_run.source_artifact_id)) if defect_run else None
    art_reads = [
        ScanGradingAssistanceArtifactRead.model_validate(row).model_copy(update={"preview_data_url": _artifact_preview_data_url(settings, row)})
        for row in artifacts
    ]
    run_data = ScanGradingAssistanceRunRead.model_validate(run).model_dump()
    output = run.output_manifest_json or {}
    lineage = dict(output.get("upstream_lineage") or {})
    overall_support = next((category.measurement_json for category in categories if category.category_type == "OVERALL_SUPPORT"), {})
    return ScanGradingAssistanceRunDetail(
        **run_data,
        categories=[ScanGradingAssistanceCategoryRead.model_validate(row) for row in categories],
        findings=[ScanGradingAssistanceFindingRead.model_validate(row) for row in findings],
        artifacts=art_reads,
        issues=[ScanGradingAssistanceIssueRead.model_validate(row) for row in issues],
        history=[ScanGradingAssistanceHistoryRead.model_validate(row) for row in history],
        original_scan_checksum=scan_image.sha256_checksum if scan_image else None,
        normalization_checksum=norm_run.normalization_checksum if norm_run else None,
        boundary_checksum=boundary_run.boundary_checksum if boundary_run else None,
        defect_checksum=lineage.get("defect_checksum"),
        spine_tick_checksum=lineage.get("spine_tick_checksum"),
        corner_edge_checksum=lineage.get("corner_edge_checksum"),
        surface_defect_checksum=lineage.get("surface_defect_checksum"),
        structural_damage_checksum=lineage.get("structural_damage_checksum"),
        aggregation_checksum=lineage.get("aggregation_checksum"),
        reconciliation_checksum=lineage.get("reconciliation_checksum"),
        source_preview_data_url=_load_source_preview(settings, source_artifact) if source_artifact else None,
        overall_support=overall_support,
        review_flags=list(output.get("review_flags") or []),
    )


def run_scan_grading_assistance(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: ScanGradingAssistanceRunCreate,
) -> tuple[ScanGradingAssistanceRunDetail, bool]:
    aggregation_run = _resolve_aggregation_run(session, owner_user_id=owner_user_id, payload=payload)
    reconciliation_run = _resolve_reconciliation_run(session, owner_user_id=owner_user_id, payload=payload)
    defect_run_id = aggregation_run.input_manifest_json.get("defect_run_id")
    defect_run = session.get(ScanDefectRun, int(defect_run_id)) if defect_run_id else None
    if defect_run is None:
        raise HTTPException(status_code=409, detail="Aggregation input is missing its upstream defect run reference.")
    source_artifact = session.get(ScanNormalizationArtifact, int(defect_run.source_artifact_id))
    if source_artifact is None:
        raise HTTPException(status_code=409, detail="Defect run is missing its normalized source artifact.")
    try:
        with Image.open(_resolve_normalization_artifact_path(settings, source_artifact)) as image_fp:
            image = _image_to_rgb(image_fp)
    except (FileNotFoundError, OSError, ValueError, UnidentifiedImageError) as exc:
        raise HTTPException(status_code=409, detail="Normalized source artifact is not available for grading assistance.") from exc

    clusters = session.exec(
        select(ScanDefectAggregateCluster)
        .where(ScanDefectAggregateCluster.aggregation_run_id == aggregation_run.id)
        .order_by(col(ScanDefectAggregateCluster.cluster_rank), col(ScanDefectAggregateCluster.id))
    ).all()
    aggregate_evidence_rows = session.exec(
        select(ScanDefectAggregateEvidence)
        .where(ScanDefectAggregateEvidence.aggregation_run_id == aggregation_run.id)
        .order_by(col(ScanDefectAggregateEvidence.cluster_id), col(ScanDefectAggregateEvidence.id))
    ).all()
    aggregate_evidence = [
        {
            "cluster_id": int(row.cluster_id),
            "source_detector": row.source_detector,
            "source_evidence_id": int(row.source_evidence_id),
            "evidence_type": row.evidence_type,
            "confidence_score": float(row.confidence_score),
            "contribution_weight": float(row.contribution_weight),
            "metadata_json": dict(row.metadata_json or {}),
        }
        for row in aggregate_evidence_rows
    ]
    defect_issues = session.exec(
        select(ScanDefectIssue).where(ScanDefectIssue.defect_run_id == defect_run.id).order_by(col(ScanDefectIssue.id))
    ).all()
    aggregation_issues = session.exec(
        select(ScanDefectAggregationIssue).where(ScanDefectAggregationIssue.aggregation_run_id == aggregation_run.id).order_by(col(ScanDefectAggregationIssue.id))
    ).all()

    findings_by_category, review_flags = map_evidence_to_categories(
        clusters=clusters,
        aggregation_evidence=aggregate_evidence,
        defect_issues=defect_issues,
        aggregation_issues=aggregation_issues,
    )
    category_drafts, review_flags = calculate_category_support_ranges(findings_by_category=findings_by_category, review_flags=review_flags)
    review_flags = generate_review_required_flags(categories=category_drafts, clusters=clusters, review_flags=review_flags)
    overall_category, overall_findings = calculate_overall_support_range(categories=category_drafts, review_flags=review_flags, findings_by_category=findings_by_category)
    categories = category_drafts + [overall_category]
    findings = []
    for category in _CATEGORY_ORDER[:-1]:
        findings.extend(findings_by_category.get(category, []))
    findings.extend(overall_findings)
    findings = sorted(findings, key=lambda row: (_CATEGORY_ORDER.index(row.category_type), row.source_cluster_id or 0, row.finding_type, row.finding_text))
    issues = _build_issues(defect_issues=defect_issues, aggregation_issues=aggregation_issues, categories=categories, review_flags=review_flags)
    provisional_artifacts = _artifact_drafts_for_run(image=image, clusters=clusters, categories=categories, findings=findings, review_flags=review_flags)
    provisional_manifest, grading_assistance_checksum = build_grading_assistance_manifest(
        aggregation_run=aggregation_run,
        reconciliation_run=reconciliation_run,
        categories=categories,
        findings=findings,
        review_flags=review_flags,
        issues=issues,
        artifact_checksums=[{"artifact_type": row.artifact_type, "artifact_checksum": _sha256_bytes(row.body)} for row in provisional_artifacts],
    )
    manifest_artifact = _ArtifactDraft("GRADING_ASSISTANCE_MANIFEST", _serialize_json_artifact(provisional_manifest), {"format": "json"}, ".json")
    artifacts = provisional_artifacts + [manifest_artifact]

    existing = session.exec(
        select(ScanGradingAssistanceRun).where(
            ScanGradingAssistanceRun.owner_user_id == owner_user_id,
            ScanGradingAssistanceRun.grading_assistance_checksum == grading_assistance_checksum,
        )
    ).first()
    if existing is not None:
        return _detail_from_run(session, settings, existing), False

    run = ScanGradingAssistanceRun(
        owner_user_id=owner_user_id,
        scan_image_id=int(aggregation_run.scan_image_id),
        aggregation_run_id=int(aggregation_run.id or 0),
        reconciliation_run_id=int(reconciliation_run.id or 0) if reconciliation_run else None,
        source_checksum=aggregation_run.source_checksum,
        grading_assistance_checksum=grading_assistance_checksum,
        assistance_status="COMPLETE",
        engine_version=ENGINE_VERSION,
        rubric_version=RUBRIC_VERSION,
        input_manifest_json={
            "scan_image_id": aggregation_run.scan_image_id,
            "aggregation_run_id": aggregation_run.id,
            "reconciliation_run_id": reconciliation_run.id if reconciliation_run else None,
            "source_checksum": aggregation_run.source_checksum,
        },
        output_manifest_json=provisional_manifest,
        completed_at=utc_now(),
    )
    session.add(run)
    session.flush()

    category_id_map: dict[str, int] = {}
    for category in categories:
        category_row = ScanGradingAssistanceCategory(
            owner_user_id=owner_user_id,
            grading_assistance_run_id=int(run.id or 0),
            category_type=category.category_type,
            category_status=category.category_status,
            suggested_range_low=category.suggested_range_low,
            suggested_range_high=category.suggested_range_high,
            confidence_score=category.confidence_score,
            evidence_count=category.evidence_count,
            summary_text=category.summary_text,
            measurement_json=category.measurement_json,
            metadata_json=category.metadata_json,
        )
        session.add(category_row)
        session.flush()
        category_id_map[category.category_type] = int(category_row.id or 0)

    for finding in findings:
        session.add(
            ScanGradingAssistanceFinding(
                owner_user_id=owner_user_id,
                grading_assistance_run_id=int(run.id or 0),
                category_id=category_id_map[finding.category_type],
                source_cluster_id=finding.source_cluster_id,
                source_detector=finding.source_detector,
                finding_type=finding.finding_type,
                finding_severity_hint=finding.finding_severity_hint,
                confidence_score=finding.confidence_score,
                grade_pressure_hint=finding.grade_pressure_hint,
                finding_text=finding.finding_text,
                measurement_json=finding.measurement_json,
                metadata_json=finding.metadata_json,
            )
        )

    for issue in issues:
        session.add(
            ScanGradingAssistanceIssue(
                owner_user_id=owner_user_id,
                grading_assistance_run_id=int(run.id or 0),
                issue_type=issue.issue_type,
                severity=issue.severity,
                issue_message=issue.issue_message,
                metadata_json=issue.metadata_json,
            )
        )

    history_rows = [
        _HistoryDraft("GRADING_ASSISTANCE_RUN_CREATED", "Created deterministic grading assistance run.", {"grading_assistance_checksum": grading_assistance_checksum}),
        _HistoryDraft("AGGREGATION_CONTEXT_LOADED", "Loaded aggregation clusters, scan-quality issues, and optional reconciliation context.", {"cluster_count": len(clusters)}),
        _HistoryDraft("CATEGORY_SUPPORT_CALCULATED", "Mapped evidence into grading support categories and support bands.", {"category_count": len(categories)}),
        _HistoryDraft("GRADING_ASSISTANCE_MANIFEST_WRITTEN", "Persisted replay-safe grading assistance manifest and artifacts.", {"artifact_count": len(artifacts)}),
    ]
    for row in history_rows:
        session.add(
            ScanGradingAssistanceHistory(
                owner_user_id=owner_user_id,
                grading_assistance_run_id=int(run.id or 0),
                event_type=row.event_type,
                event_message=row.event_message,
                event_checksum=_hash_payload(
                    {
                        "grading_assistance_run_id": int(run.id or 0),
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
            scan_image_id=int(aggregation_run.scan_image_id),
            grading_assistance_run_id=int(run.id or 0),
            artifact_type=row.artifact_type,
            ext=row.ext,
        )
        _save_artifact_bytes(settings, relative_path=relative_path, body=row.body)
        session.add(
            ScanGradingAssistanceArtifact(
                owner_user_id=owner_user_id,
                grading_assistance_run_id=int(run.id or 0),
                artifact_type=row.artifact_type,
                storage_path=relative_path,
                artifact_checksum=_sha256_bytes(row.body),
                metadata_json=row.metadata_json,
            )
        )
    session.commit()
    session.refresh(run)
    return _detail_from_run(session, settings, run), True


def get_scan_grading_assistance_run_owner(session: Session, settings: Settings, *, owner_user_id: int, run_id: int) -> ScanGradingAssistanceRunDetail:
    row = session.get(ScanGradingAssistanceRun, run_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Grading assistance run not found.")
    return _detail_from_run(session, settings, row)


def get_scan_grading_assistance_artifact_owner(session: Session, settings: Settings, *, owner_user_id: int, artifact_id: int) -> ScanGradingAssistanceArtifactRead:
    row = session.get(ScanGradingAssistanceArtifact, artifact_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Grading assistance artifact not found.")
    return ScanGradingAssistanceArtifactRead.model_validate(row).model_copy(update={"preview_data_url": _artifact_preview_data_url(settings, row)})


def _run_list_response(rows: list[ScanGradingAssistanceRun], *, limit: int, offset: int, total_items: int) -> ScanGradingAssistanceRunListResponse:
    status_counts = {status: sum(1 for row in rows if row.assistance_status == status) for status in sorted({row.assistance_status for row in rows})}
    review_required_count = sum(
        1
        for row in rows
        if any(category.get("category_status") == "REVIEW_REQUIRED" for category in (row.output_manifest_json.get("category_summaries") or []))
    )
    low_confidence = sum(
        1
        for row in rows
        if any(float(category.get("confidence_score") or 0.0) < 0.4 for category in (row.output_manifest_json.get("category_summaries") or []))
    )
    return ScanGradingAssistanceRunListResponse(
        items=[ScanGradingAssistanceRunRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        status_counts=status_counts,
        review_required_count=review_required_count,
        low_confidence_support_count=low_confidence,
    )


def list_scan_grading_assistance_runs_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanGradingAssistanceRunListResponse:
    limit, offset = clamp_scan_grading_assistance_pagination(limit=limit, offset=offset)
    stmt = select(ScanGradingAssistanceRun).where(ScanGradingAssistanceRun.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanGradingAssistanceRun).where(ScanGradingAssistanceRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanGradingAssistanceRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanGradingAssistanceRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanGradingAssistanceRun.created_at).desc(), col(ScanGradingAssistanceRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_grading_assistance_runs_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanGradingAssistanceRunListResponse:
    limit, offset = clamp_scan_grading_assistance_pagination(limit=limit, offset=offset)
    stmt = select(ScanGradingAssistanceRun)
    count_stmt = select(func.count()).select_from(ScanGradingAssistanceRun)
    if owner_user_id is not None:
        stmt = stmt.where(ScanGradingAssistanceRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanGradingAssistanceRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanGradingAssistanceRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanGradingAssistanceRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanGradingAssistanceRun.created_at).desc(), col(ScanGradingAssistanceRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_grading_assistance_categories_owner(
    session: Session,
    *,
    owner_user_id: int,
    grading_assistance_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanGradingAssistanceCategoryListResponse:
    limit, offset = clamp_scan_grading_assistance_pagination(limit=limit, offset=offset)
    stmt = select(ScanGradingAssistanceCategory).where(ScanGradingAssistanceCategory.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanGradingAssistanceCategory).where(ScanGradingAssistanceCategory.owner_user_id == owner_user_id)
    if grading_assistance_run_id is not None:
        stmt = stmt.where(ScanGradingAssistanceCategory.grading_assistance_run_id == grading_assistance_run_id)
        count_stmt = count_stmt.where(ScanGradingAssistanceCategory.grading_assistance_run_id == grading_assistance_run_id)
    rows = session.exec(stmt.order_by(col(ScanGradingAssistanceCategory.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanGradingAssistanceCategoryListResponse(
        items=[ScanGradingAssistanceCategoryRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        category_type_counts={key: sum(1 for row in rows if row.category_type == key) for key in sorted({row.category_type for row in rows})},
        category_status_counts={key: sum(1 for row in rows if row.category_status == key) for key in sorted({row.category_status for row in rows})},
    )


def list_scan_grading_assistance_findings_owner(
    session: Session,
    *,
    owner_user_id: int,
    grading_assistance_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanGradingAssistanceFindingListResponse:
    limit, offset = clamp_scan_grading_assistance_pagination(limit=limit, offset=offset)
    stmt = select(ScanGradingAssistanceFinding).where(ScanGradingAssistanceFinding.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanGradingAssistanceFinding).where(ScanGradingAssistanceFinding.owner_user_id == owner_user_id)
    if grading_assistance_run_id is not None:
        stmt = stmt.where(ScanGradingAssistanceFinding.grading_assistance_run_id == grading_assistance_run_id)
        count_stmt = count_stmt.where(ScanGradingAssistanceFinding.grading_assistance_run_id == grading_assistance_run_id)
    rows = session.exec(stmt.order_by(col(ScanGradingAssistanceFinding.category_id), col(ScanGradingAssistanceFinding.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanGradingAssistanceFindingListResponse(
        items=[ScanGradingAssistanceFindingRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        finding_type_counts={key: sum(1 for row in rows if row.finding_type == key) for key in sorted({row.finding_type for row in rows})},
        grade_pressure_hint_counts={key: sum(1 for row in rows if row.grade_pressure_hint == key) for key in sorted({row.grade_pressure_hint for row in rows})},
    )


def list_scan_grading_assistance_issues_owner(
    session: Session,
    *,
    owner_user_id: int,
    grading_assistance_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanGradingAssistanceIssueListResponse:
    limit, offset = clamp_scan_grading_assistance_pagination(limit=limit, offset=offset)
    stmt = select(ScanGradingAssistanceIssue).where(ScanGradingAssistanceIssue.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanGradingAssistanceIssue).where(ScanGradingAssistanceIssue.owner_user_id == owner_user_id)
    if grading_assistance_run_id is not None:
        stmt = stmt.where(ScanGradingAssistanceIssue.grading_assistance_run_id == grading_assistance_run_id)
        count_stmt = count_stmt.where(ScanGradingAssistanceIssue.grading_assistance_run_id == grading_assistance_run_id)
    rows = session.exec(stmt.order_by(col(ScanGradingAssistanceIssue.created_at), col(ScanGradingAssistanceIssue.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanGradingAssistanceIssueListResponse(
        items=[ScanGradingAssistanceIssueRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        issue_type_counts={key: sum(1 for row in rows if row.issue_type == key) for key in sorted({row.issue_type for row in rows})},
    )


def list_scan_grading_assistance_issues_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanGradingAssistanceIssueListResponse:
    limit, offset = clamp_scan_grading_assistance_pagination(limit=limit, offset=offset)
    stmt = select(ScanGradingAssistanceIssue)
    count_stmt = select(func.count()).select_from(ScanGradingAssistanceIssue)
    if owner_user_id is not None:
        stmt = stmt.where(ScanGradingAssistanceIssue.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanGradingAssistanceIssue.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanGradingAssistanceIssue.created_at), col(ScanGradingAssistanceIssue.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanGradingAssistanceIssueListResponse(
        items=[ScanGradingAssistanceIssueRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        issue_type_counts={key: sum(1 for row in rows if row.issue_type == key) for key in sorted({row.issue_type for row in rows})},
    )


def list_scan_grading_assistance_failures_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanGradingAssistanceFailureListResponse:
    limit, offset = clamp_scan_grading_assistance_pagination(limit=limit, offset=offset)
    stmt = select(ScanGradingAssistanceRun).where(ScanGradingAssistanceRun.assistance_status == "FAILED")
    count_stmt = select(func.count()).select_from(ScanGradingAssistanceRun).where(ScanGradingAssistanceRun.assistance_status == "FAILED")
    if owner_user_id is not None:
        stmt = stmt.where(ScanGradingAssistanceRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanGradingAssistanceRun.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanGradingAssistanceRun.created_at).desc(), col(ScanGradingAssistanceRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanGradingAssistanceFailureListResponse(
        items=[ScanGradingAssistanceRunRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )
