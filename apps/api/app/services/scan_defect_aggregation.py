from __future__ import annotations

import base64
import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from PIL import Image, ImageColor, ImageDraw, UnidentifiedImageError
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models import (
    ScanBoundaryRun,
    ScanCornerEdgeEvidence,
    ScanCornerEdgeRun,
    ScanDefectAggregateCluster,
    ScanDefectAggregateEvidence,
    ScanDefectAggregationArtifact,
    ScanDefectAggregationHistory,
    ScanDefectAggregationIssue,
    ScanDefectAggregationRun,
    ScanDefectEvidence,
    ScanDefectRegion,
    ScanDefectRun,
    ScanImage,
    ScanNormalizationArtifact,
    ScanNormalizationRun,
    ScanSpineTickEvidence,
    ScanSpineTickRun,
    ScanStructuralDamageEvidence,
    ScanStructuralDamageRun,
    ScanSurfaceDefectEvidence,
    ScanSurfaceDefectRun,
)
from app.schemas.scan_defect_aggregation import (
    ScanDefectAggregateClusterListResponse,
    ScanDefectAggregateClusterRead,
    ScanDefectAggregateEvidenceListResponse,
    ScanDefectAggregateEvidenceRead,
    ScanDefectAggregationArtifactRead,
    ScanDefectAggregationFailureListResponse,
    ScanDefectAggregationHistoryRead,
    ScanDefectAggregationIssueListResponse,
    ScanDefectAggregationIssueRead,
    ScanDefectAggregationRunCreate,
    ScanDefectAggregationRunDetail,
    ScanDefectAggregationRunListResponse,
    ScanDefectAggregationRunRead,
)
from app.services.scan_defects import _load_source_preview, _resolve_normalization_artifact_path

ENGINE_VERSION = "P40-11-v1"
_PREVIEW_MAX = 420
_LOW_CLUSTER_CONFIDENCE = 0.35
_REGION_SUMMARY_ORDER = ("SPINE", "CORNER", "EDGE", "SURFACE", "STRUCTURAL")


@dataclass(frozen=True)
class _UpstreamRunBundle:
    detector: str
    run_id: int
    checksum: str
    evidence: list[Any]


@dataclass(frozen=True)
class _UpstreamEvidence:
    source_detector: str
    source_evidence_id: int
    source_run_id: int
    run_checksum: str
    evidence_rank: int
    evidence_type: str
    evidence_category: str
    severity_hint: str
    confidence_score: float
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    width_px: int
    height_px: int
    area_ratio: float
    region_type: str
    region_group: str
    contribution_seed: float
    measurement_json: dict[str, Any]
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _ClusterDraft:
    cluster_type: str
    cluster_region: str
    cluster_confidence: float
    aggregate_severity_hint: str
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    cluster_area_ratio: float
    measurement_json: dict[str, Any]
    metadata_json: dict[str, Any]
    evidence: list[_UpstreamEvidence]


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
    from app.models.scan_defect_aggregation import utc_now as _utc_now

    return _utc_now()


def clamp_scan_defect_aggregation_pagination(*, limit: int, offset: int) -> tuple[int, int]:
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


def _resolve_aggregation_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.scan_defect_aggregation_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("scan defect aggregation storage path escapes configured root")
    return target


def _artifact_storage_path(
    *,
    owner_user_id: int,
    scan_image_id: int,
    aggregation_run_id: int,
    artifact_type: str,
    ext: str,
) -> str:
    safe_type = artifact_type.lower()
    return f"scan-defect-aggregation/{owner_user_id}/{scan_image_id}/{aggregation_run_id}/{safe_type}{ext}".replace("\\", "/")


def _save_artifact_bytes(settings: Settings, *, relative_path: str, body: bytes) -> None:
    target = _resolve_aggregation_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)


def _artifact_preview_data_url(settings: Settings, row: ScanDefectAggregationArtifact) -> str | None:
    if not row.storage_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        return None
    try:
        body = _resolve_aggregation_storage_path(settings, row.storage_path).read_bytes()
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


def _bbox_area(x_min: int, y_min: int, x_max: int, y_max: int) -> int:
    return max(1, (x_max - x_min + 1) * (y_max - y_min + 1))


def _resolve_defect_run(session: Session, *, owner_user_id: int, payload: ScanDefectAggregationRunCreate) -> ScanDefectRun:
    stmt = select(ScanDefectRun).where(
        ScanDefectRun.owner_user_id == owner_user_id,
        ScanDefectRun.scan_image_id == payload.scan_image_id,
        ScanDefectRun.defect_status == "COMPLETE",
    )
    if payload.defect_run_id is not None:
        stmt = stmt.where(ScanDefectRun.id == payload.defect_run_id)
    row = session.exec(stmt.order_by(col(ScanDefectRun.id).desc())).first()
    if row is None:
        raise HTTPException(status_code=409, detail="A complete defect foundation run is required before defect aggregation.")
    return row


def _load_optional_bundle(
    session: Session,
    *,
    detector: str,
    run_model: Any,
    evidence_model: Any,
    defect_run_id: int,
    checksum_attr: str,
    run_fk_name: str,
    status_attr: str,
    status_value: str,
) -> _UpstreamRunBundle | None:
    stmt = select(run_model).where(
        getattr(run_model, "defect_run_id") == defect_run_id,
        getattr(run_model, status_attr) == status_value,
    )
    run_row = session.exec(stmt.order_by(col(getattr(run_model, "id")).desc())).first()
    if run_row is None:
        return None
    run_id = int(getattr(run_row, "id"))
    evidence_stmt = (
        select(evidence_model)
        .where(getattr(evidence_model, run_fk_name) == run_id)
        .order_by(col(getattr(evidence_model, "id")))
    )
    evidence_rows = session.exec(evidence_stmt).all()
    return _UpstreamRunBundle(
        detector=detector,
        run_id=run_id,
        checksum=str(getattr(run_row, checksum_attr)),
        evidence=evidence_rows,
    )


def _region_group(region_type: str, *, source_detector: str) -> str:
    upper = region_type.upper()
    if source_detector == "P40_10_STRUCTURAL":
        return "STRUCTURAL"
    if "SPINE" in upper:
        return "SPINE"
    if "CORNER" in upper:
        return "CORNER"
    if "EDGE" in upper:
        return "EDGE"
    return "SURFACE"


def _coerce_area_ratio(value: Any) -> float:
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return 0.0


def load_upstream_evidence(
    session: Session,
    *,
    defect_run: ScanDefectRun,
) -> tuple[list[_UpstreamEvidence], dict[str, str | None], list[_IssueDraft], dict[str, Any]]:
    defect_regions = session.exec(
        select(ScanDefectRegion).where(ScanDefectRegion.defect_run_id == defect_run.id).order_by(col(ScanDefectRegion.id))
    ).all()
    region_lookup = {int(row.id or 0): row for row in defect_regions}
    full_cover = next((row for row in defect_regions if row.region_type == "FULL_COVER"), None)
    full_cover_area = _bbox_area(full_cover.x_min, full_cover.y_min, full_cover.x_max, full_cover.y_max) if full_cover else 1

    issues: list[_IssueDraft] = []
    lineage: dict[str, str | None] = {
        "defect_checksum": defect_run.defect_checksum,
        "spine_tick_checksum": None,
        "corner_edge_checksum": None,
        "surface_defect_checksum": None,
        "structural_damage_checksum": None,
    }
    run_ids: dict[str, int | None] = {
        "defect_run_id": int(defect_run.id or 0),
        "spine_tick_run_id": None,
        "corner_edge_run_id": None,
        "surface_defect_run_id": None,
        "structural_damage_run_id": None,
    }

    bundles = {
        "P40_07_SPINE": _load_optional_bundle(
            session,
            detector="P40_07_SPINE",
            run_model=ScanSpineTickRun,
            evidence_model=ScanSpineTickEvidence,
            defect_run_id=int(defect_run.id or 0),
            checksum_attr="spine_tick_checksum",
            run_fk_name="spine_tick_run_id",
            status_attr="detection_status",
            status_value="COMPLETE",
        ),
        "P40_08_CORNER_EDGE": _load_optional_bundle(
            session,
            detector="P40_08_CORNER_EDGE",
            run_model=ScanCornerEdgeRun,
            evidence_model=ScanCornerEdgeEvidence,
            defect_run_id=int(defect_run.id or 0),
            checksum_attr="corner_edge_checksum",
            run_fk_name="corner_edge_run_id",
            status_attr="detection_status",
            status_value="COMPLETE",
        ),
        "P40_09_SURFACE": _load_optional_bundle(
            session,
            detector="P40_09_SURFACE",
            run_model=ScanSurfaceDefectRun,
            evidence_model=ScanSurfaceDefectEvidence,
            defect_run_id=int(defect_run.id or 0),
            checksum_attr="surface_defect_checksum",
            run_fk_name="surface_defect_run_id",
            status_attr="detection_status",
            status_value="COMPLETE",
        ),
        "P40_10_STRUCTURAL": _load_optional_bundle(
            session,
            detector="P40_10_STRUCTURAL",
            run_model=ScanStructuralDamageRun,
            evidence_model=ScanStructuralDamageEvidence,
            defect_run_id=int(defect_run.id or 0),
            checksum_attr="structural_damage_checksum",
            run_fk_name="structural_damage_run_id",
            status_attr="detection_status",
            status_value="COMPLETE",
        ),
    }

    for detector, bundle in bundles.items():
        if bundle is None:
            issues.append(
                _IssueDraft(
                    issue_type="MISSING_UPSTREAM_EVIDENCE",
                    severity="INFO",
                    issue_message=f"{detector} did not have a completed upstream run for this defect foundation input.",
                    metadata_json={"missing_detector": detector},
                )
            )
            continue
        run_ids[detector.lower()] = bundle.run_id
        if detector == "P40_07_SPINE":
            lineage["spine_tick_checksum"] = bundle.checksum
            run_ids["spine_tick_run_id"] = bundle.run_id
        elif detector == "P40_08_CORNER_EDGE":
            lineage["corner_edge_checksum"] = bundle.checksum
            run_ids["corner_edge_run_id"] = bundle.run_id
        elif detector == "P40_09_SURFACE":
            lineage["surface_defect_checksum"] = bundle.checksum
            run_ids["surface_defect_run_id"] = bundle.run_id
        elif detector == "P40_10_STRUCTURAL":
            lineage["structural_damage_checksum"] = bundle.checksum
            run_ids["structural_damage_run_id"] = bundle.run_id

    evidence_rows: list[_UpstreamEvidence] = []

    defect_evidence_rows = session.exec(
        select(ScanDefectEvidence).where(ScanDefectEvidence.defect_run_id == defect_run.id).order_by(col(ScanDefectEvidence.id))
    ).all()
    for idx, row in enumerate(defect_evidence_rows, start=1):
        region = region_lookup.get(int(row.region_id))
        evidence_rows.append(
            _UpstreamEvidence(
                source_detector="P40_06_DEFECT_FOUNDATION",
                source_evidence_id=int(row.id or 0),
                source_run_id=int(defect_run.id or 0),
                run_checksum=defect_run.defect_checksum,
                evidence_rank=idx,
                evidence_type=row.evidence_type,
                evidence_category=row.evidence_category,
                severity_hint=row.severity_hint,
                confidence_score=round(float(row.confidence_score), 6),
                x_min=row.x_min,
                y_min=row.y_min,
                x_max=row.x_max,
                y_max=row.y_max,
                width_px=max(1, row.x_max - row.x_min + 1),
                height_px=max(1, row.y_max - row.y_min + 1),
                area_ratio=round(_bbox_area(row.x_min, row.y_min, row.x_max, row.y_max) / max(1, full_cover_area), 6),
                region_type=region.region_type if region else "UNKNOWN_REGION",
                region_group=_region_group(region.region_type if region else "UNKNOWN_REGION", source_detector="P40_06_DEFECT_FOUNDATION"),
                contribution_seed=0.22,
                measurement_json=dict(row.measurement_json or {}),
                metadata_json=dict(row.metadata_json or {}),
            )
        )

    for detector, bundle in bundles.items():
        if bundle is None:
            continue
        for idx, row in enumerate(bundle.evidence, start=1):
            area_ratio = 0.0
            for key in ("spine_overlap_ratio", "corner_overlap_ratio", "surface_area_ratio", "structural_area_ratio"):
                if hasattr(row, key):
                    area_ratio = _coerce_area_ratio(getattr(row, key))
                    if area_ratio > 0:
                        break
            if area_ratio <= 0:
                area_ratio = round(_bbox_area(row.x_min, row.y_min, row.x_max, row.y_max) / max(1, full_cover_area), 6)
            evidence_rows.append(
                _UpstreamEvidence(
                    source_detector=detector,
                    source_evidence_id=int(row.id or 0),
                    source_run_id=bundle.run_id,
                    run_checksum=bundle.checksum,
                    evidence_rank=int(
                        getattr(row, "tick_rank", None)
                        or getattr(row, "evidence_rank", None)
                        or idx
                    ),
                    evidence_type=str(getattr(row, "evidence_type", "SPINE_TICK" if detector == "P40_07_SPINE" else "UNKNOWN")),
                    evidence_category=str(getattr(row, "evidence_category", detector)),
                    severity_hint=str(getattr(row, "severity_hint", "MINOR")),
                    confidence_score=round(float(getattr(row, "confidence_score", 0.0)), 6),
                    x_min=int(row.x_min),
                    y_min=int(row.y_min),
                    x_max=int(row.x_max),
                    y_max=int(row.y_max),
                    width_px=int(getattr(row, "width_px", max(1, row.x_max - row.x_min + 1))),
                    height_px=int(getattr(row, "height_px", max(1, row.y_max - row.y_min + 1))),
                    area_ratio=area_ratio,
                    region_type=str(getattr(row, "region_type", "SPINE_REGION" if detector == "P40_07_SPINE" else "UNKNOWN_REGION")),
                    region_group=_region_group(str(getattr(row, "region_type", "UNKNOWN_REGION")), source_detector=detector),
                    contribution_seed=0.24 if detector == "P40_10_STRUCTURAL" else 0.2,
                    measurement_json=dict(getattr(row, "measurement_json", {}) or {}),
                    metadata_json=dict(getattr(row, "metadata_json", {}) or {}),
                )
            )

    ordered = sorted(
        evidence_rows,
        key=lambda row: (
            row.region_group,
            row.y_min,
            row.x_min,
            row.source_detector,
            row.evidence_rank,
            row.source_evidence_id,
        ),
    )
    return ordered, lineage, issues, {"run_ids": run_ids, "full_cover_area": full_cover_area}


def _expanded_intersects(a: tuple[int, int, int, int], b: tuple[int, int, int, int], *, padding: int) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return not (ax1 + padding < bx0 or bx1 + padding < ax0 or ay1 + padding < by0 or by1 + padding < ay0)


def _cluster_candidate(cluster: dict[str, Any], evidence: _UpstreamEvidence) -> bool:
    padding = max(12, min(evidence.width_px, evidence.height_px) // 2)
    same_region = cluster["cluster_region"] == evidence.region_group
    compatible = same_region or {cluster["cluster_region"], evidence.region_group} <= {"SURFACE", "STRUCTURAL"}
    if not compatible and cluster["cluster_region"] != "MIXED":
        return False
    return _expanded_intersects(
        (cluster["x_min"], cluster["y_min"], cluster["x_max"], cluster["y_max"]),
        (evidence.x_min, evidence.y_min, evidence.x_max, evidence.y_max),
        padding=padding,
    )


def _cluster_type_for_evidence(evidence: list[_UpstreamEvidence]) -> tuple[str, str]:
    groups = {row.region_group for row in evidence}
    if len(groups) > 1:
        return "MIXED_CLUSTER", "MIXED"
    only = next(iter(groups)) if groups else "SURFACE"
    mapping = {
        "SPINE": "SPINE_CLUSTER",
        "CORNER": "CORNER_CLUSTER",
        "EDGE": "EDGE_CLUSTER",
        "SURFACE": "SURFACE_CLUSTER",
        "STRUCTURAL": "STRUCTURAL_CLUSTER",
    }
    return mapping.get(only, "MIXED_CLUSTER"), only


def calculate_aggregate_severity(*, evidence: list[_UpstreamEvidence], area_ratio: float, cluster_confidence: float) -> str:
    density = min(1.0, len(evidence) / 6.0)
    overlap_factor = min(1.0, sum(row.area_ratio for row in evidence))
    score = density * 0.35 + overlap_factor * 0.3 + cluster_confidence * 0.35 + area_ratio * 0.2
    if score >= 0.58:
        return "MAJOR"
    if score >= 0.28:
        return "MODERATE"
    return "MINOR"


def cluster_related_evidence(
    *,
    evidence_rows: list[_UpstreamEvidence],
    full_cover_area: int,
) -> list[_ClusterDraft]:
    if not evidence_rows:
        return []
    working: list[dict[str, Any]] = []
    for evidence in evidence_rows:
        target: dict[str, Any] | None = None
        for cluster in working:
            if _cluster_candidate(cluster, evidence):
                target = cluster
                break
        if target is None:
            target = {
                "evidence": [],
                "x_min": evidence.x_min,
                "y_min": evidence.y_min,
                "x_max": evidence.x_max,
                "y_max": evidence.y_max,
                "cluster_region": evidence.region_group,
            }
            working.append(target)
        target["evidence"].append(evidence)
        target["x_min"] = min(target["x_min"], evidence.x_min)
        target["y_min"] = min(target["y_min"], evidence.y_min)
        target["x_max"] = max(target["x_max"], evidence.x_max)
        target["y_max"] = max(target["y_max"], evidence.y_max)
        _, cluster_region = _cluster_type_for_evidence(target["evidence"])
        target["cluster_region"] = cluster_region

    drafts: list[_ClusterDraft] = []
    for cluster in working:
        members = sorted(
            cluster["evidence"],
            key=lambda row: (row.source_detector, row.y_min, row.x_min, row.evidence_rank, row.source_evidence_id),
        )
        cluster_type, cluster_region = _cluster_type_for_evidence(members)
        bbox_area = _bbox_area(cluster["x_min"], cluster["y_min"], cluster["x_max"], cluster["y_max"])
        area_ratio = round(bbox_area / max(1, full_cover_area), 6)
        confidence = round(sum(row.confidence_score for row in members) / max(1, len(members)), 6)
        severity = calculate_aggregate_severity(evidence=members, area_ratio=area_ratio, cluster_confidence=confidence)
        source_counts = {key: sum(1 for row in members if row.source_detector == key) for key in sorted({row.source_detector for row in members})}
        evidence_types = {key: sum(1 for row in members if row.evidence_type == key) for key in sorted({row.evidence_type for row in members})}
        overlap_ratio = round(sum(row.area_ratio for row in members), 6)
        drafts.append(
            _ClusterDraft(
                cluster_type=cluster_type,
                cluster_region=cluster_region,
                cluster_confidence=confidence,
                aggregate_severity_hint=severity,
                x_min=cluster["x_min"],
                y_min=cluster["y_min"],
                x_max=cluster["x_max"],
                y_max=cluster["y_max"],
                cluster_area_ratio=area_ratio,
                measurement_json={
                    "evidence_count": len(members),
                    "cluster_bbox_area": bbox_area,
                    "cluster_area_ratio": area_ratio,
                    "cluster_confidence": confidence,
                    "source_detector_counts": source_counts,
                    "evidence_type_counts": evidence_types,
                    "overlap_ratio": overlap_ratio,
                },
                metadata_json={
                    "source_detectors": sorted(source_counts.keys()),
                    "dominant_detector": max(source_counts.items(), key=lambda item: (item[1], item[0]))[0],
                },
                evidence=members,
            )
        )

    return sorted(
        drafts,
        key=lambda row: (
            row.cluster_region,
            row.y_min,
            row.x_min,
            row.cluster_type,
            row.cluster_confidence,
        ),
    )


def generate_condition_region_summary(clusters: list[_ClusterDraft]) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for region in _REGION_SUMMARY_ORDER:
        region_clusters = [row for row in clusters if row.cluster_region == region or (region == "STRUCTURAL" and row.cluster_type == "MIXED_CLUSTER" and "P40_10_STRUCTURAL" in row.metadata_json.get("source_detectors", []))]
        evidence_members = [member for cluster in region_clusters for member in cluster.evidence]
        severity_counts = {key: sum(1 for cluster in region_clusters if cluster.aggregate_severity_hint == key) for key in ("MINOR", "MODERATE", "MAJOR")}
        anomaly_counts = {key: sum(1 for member in evidence_members if member.evidence_category == key) for key in sorted({member.evidence_category for member in evidence_members})}
        summaries[region.lower()] = {
            "evidence_count": len(evidence_members),
            "cluster_count": len(region_clusters),
            "confidence_summary": {
                "mean_confidence": round(sum(member.confidence_score for member in evidence_members) / max(1, len(evidence_members)), 6),
                "max_confidence": round(max((member.confidence_score for member in evidence_members), default=0.0), 6),
            },
            "severity_distribution": severity_counts,
            "dominant_anomaly_categories": [key for key, _ in sorted(anomaly_counts.items(), key=lambda item: (-item[1], item[0]))[:3]],
        }
    return summaries


def _build_issues(
    *,
    evidence_rows: list[_UpstreamEvidence],
    clusters: list[_ClusterDraft],
    initial_issues: list[_IssueDraft],
) -> list[_IssueDraft]:
    issues = list(initial_issues)
    if not evidence_rows:
        issues.append(
            _IssueDraft(
                issue_type="AGGREGATION_FAILED",
                severity="ERROR",
                issue_message="No upstream evidence was available for aggregation.",
                metadata_json={},
            )
        )
        return issues
    if len(evidence_rows) > 40:
        issues.append(
            _IssueDraft(
                issue_type="EVIDENCE_OVERFLOW",
                severity="INFO",
                issue_message="Upstream evidence volume is high and may increase cluster density.",
                metadata_json={"upstream_evidence_count": len(evidence_rows)},
            )
        )
    if not clusters:
        issues.append(
            _IssueDraft(
                issue_type="CLUSTERING_FAILED",
                severity="ERROR",
                issue_message="Evidence normalization completed but produced no aggregate clusters.",
                metadata_json={},
            )
        )
        return issues
    if any(cluster.cluster_confidence < _LOW_CLUSTER_CONFIDENCE for cluster in clusters):
        issues.append(
            _IssueDraft(
                issue_type="LOW_CLUSTER_CONFIDENCE",
                severity="WARNING",
                issue_message="One or more aggregate clusters remain below the confidence floor.",
                metadata_json={"low_confidence_cluster_count": sum(1 for cluster in clusters if cluster.cluster_confidence < _LOW_CLUSTER_CONFIDENCE)},
            )
        )
    out_of_bounds = [
        row.source_evidence_id
        for row in evidence_rows
        if min(row.x_min, row.y_min) < 0 or row.x_max < row.x_min or row.y_max < row.y_min
    ]
    if out_of_bounds:
        issues.append(
            _IssueDraft(
                issue_type="EVIDENCE_NORMALIZATION_FAILED",
                severity="ERROR",
                issue_message="One or more upstream evidence rows could not be normalized into valid geometry.",
                metadata_json={"source_evidence_ids": out_of_bounds},
            )
        )
    conflict_pairs = 0
    for idx, cluster in enumerate(clusters):
        for other in clusters[idx + 1 :]:
            if cluster.cluster_region == other.cluster_region:
                continue
            if _expanded_intersects((cluster.x_min, cluster.y_min, cluster.x_max, cluster.y_max), (other.x_min, other.y_min, other.x_max, other.y_max), padding=0):
                conflict_pairs += 1
    if conflict_pairs:
        issues.append(
            _IssueDraft(
                issue_type="OVERLAPPING_REGION_CONFLICT",
                severity="INFO",
                issue_message="Aggregate clusters overlapped across region groups.",
                metadata_json={"conflict_pair_count": conflict_pairs},
            )
        )
    mixed_count = sum(1 for cluster in clusters if cluster.cluster_type == "MIXED_CLUSTER")
    if mixed_count >= max(2, len(clusters) // 2):
        issues.append(
            _IssueDraft(
                issue_type="GEOMETRY_CONFLICT",
                severity="INFO",
                issue_message="Multiple clusters required mixed-region reconciliation.",
                metadata_json={"mixed_cluster_count": mixed_count},
            )
        )
    return issues


def build_aggregation_manifest(
    *,
    defect_run: ScanDefectRun,
    lineage: dict[str, str | None],
    clusters: list[_ClusterDraft],
    region_summaries: dict[str, Any],
    issues: list[_IssueDraft],
    artifact_checksums: list[dict[str, str]],
) -> tuple[dict[str, Any], str]:
    manifest = {
        "engine_version": ENGINE_VERSION,
        "upstream_lineage": {
            "original_scan_checksum": defect_run.input_manifest_json.get("lineage", {}).get("original_scan_checksum"),
            "normalization_checksum": defect_run.input_manifest_json.get("lineage", {}).get("normalization_checksum"),
            "boundary_checksum": defect_run.input_manifest_json.get("lineage", {}).get("boundary_checksum"),
            **lineage,
            "source_checksum": defect_run.source_checksum,
        },
        "clusters": [
            {
                "cluster_rank": idx + 1,
                "cluster_type": cluster.cluster_type,
                "cluster_region": cluster.cluster_region,
                "aggregate_severity_hint": cluster.aggregate_severity_hint,
                "cluster_confidence": cluster.cluster_confidence,
                "bbox": [cluster.x_min, cluster.y_min, cluster.x_max, cluster.y_max],
                "measurement_json": cluster.measurement_json,
                "source_evidence_refs": [
                    {
                        "source_detector": member.source_detector,
                        "source_evidence_id": member.source_evidence_id,
                        "source_run_id": member.source_run_id,
                        "run_checksum": member.run_checksum,
                        "evidence_type": member.evidence_type,
                    }
                    for member in cluster.evidence
                ],
            }
            for idx, cluster in enumerate(clusters)
        ],
        "region_summaries": region_summaries,
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
        "aggregate_summary": {
            "cluster_count": len(clusters),
            "source_evidence_count": sum(len(cluster.evidence) for cluster in clusters),
            "mixed_cluster_count": sum(1 for cluster in clusters if cluster.cluster_type == "MIXED_CLUSTER"),
        },
    }
    return manifest, _hash_payload(manifest)


def _build_overlay(
    image: Image.Image,
    *,
    clusters: list[_ClusterDraft],
    include_source: bool,
) -> bytes:
    rendered = _image_to_rgb(image)
    draw = ImageDraw.Draw(rendered)
    cluster_palette = {
        "SPINE_CLUSTER": "#22c55e",
        "CORNER_CLUSTER": "#eab308",
        "EDGE_CLUSTER": "#f97316",
        "SURFACE_CLUSTER": "#a855f7",
        "STRUCTURAL_CLUSTER": "#06b6d4",
        "MIXED_CLUSTER": "#ef4444",
    }
    if include_source:
        for cluster in clusters:
            for evidence in cluster.evidence:
                draw.rectangle((evidence.x_min, evidence.y_min, evidence.x_max, evidence.y_max), outline="#94a3b8", width=1)
    for cluster in clusters:
        color = cluster_palette.get(cluster.cluster_type, "#ffffff")
        draw.rectangle((cluster.x_min, cluster.y_min, cluster.x_max, cluster.y_max), outline=color, width=2)
    buf = io.BytesIO()
    rendered.save(buf, format="PNG")
    return buf.getvalue()


def _build_condition_map(clusters: list[_ClusterDraft], image: Image.Image) -> bytes:
    rendered = _image_to_rgb(image)
    overlay = Image.new("RGBA", rendered.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    fill_palette = {
        "SPINE_CLUSTER": (*ImageColor.getrgb("#22c55e"), 64),
        "CORNER_CLUSTER": (*ImageColor.getrgb("#eab308"), 64),
        "EDGE_CLUSTER": (*ImageColor.getrgb("#f97316"), 64),
        "SURFACE_CLUSTER": (*ImageColor.getrgb("#a855f7"), 64),
        "STRUCTURAL_CLUSTER": (*ImageColor.getrgb("#06b6d4"), 64),
        "MIXED_CLUSTER": (*ImageColor.getrgb("#ef4444"), 72),
    }
    for cluster in clusters:
        draw.rectangle((cluster.x_min, cluster.y_min, cluster.x_max, cluster.y_max), fill=fill_palette.get(cluster.cluster_type, (255, 255, 255, 48)))
    merged = Image.alpha_composite(rendered.convert("RGBA"), overlay).convert("RGB")
    buf = io.BytesIO()
    merged.save(buf, format="PNG")
    return buf.getvalue()


def _build_debug_preview(image: Image.Image, clusters: list[_ClusterDraft]) -> bytes:
    rendered = _image_to_rgb(image)
    rendered.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
    draw = ImageDraw.Draw(rendered)
    for cluster in clusters[:12]:
        draw.rectangle((cluster.x_min, cluster.y_min, cluster.x_max, cluster.y_max), outline="#38bdf8", width=1)
    buf = io.BytesIO()
    rendered.save(buf, format="PNG")
    return buf.getvalue()


def _artifact_drafts_for_run(
    *,
    image: Image.Image,
    clusters: list[_ClusterDraft],
    region_summaries: dict[str, Any],
) -> list[_ArtifactDraft]:
    return [
        _ArtifactDraft("AGGREGATE_CONDITION_MAP", _build_condition_map(clusters, image), {"format": "png", "cluster_count": len(clusters)}, ".png"),
        _ArtifactDraft("DEFECT_CLUSTER_OVERLAY", _build_overlay(image, clusters=clusters, include_source=True), {"format": "png", "cluster_count": len(clusters)}, ".png"),
        _ArtifactDraft("REGION_SUMMARY_EXPORT", _serialize_json_artifact(region_summaries), {"format": "json"}, ".json"),
        _ArtifactDraft("AGGREGATION_DEBUG_PREVIEW", _build_debug_preview(image, clusters), {"format": "png"}, ".png"),
    ]


def _detail_from_run(session: Session, settings: Settings, run: ScanDefectAggregationRun) -> ScanDefectAggregationRunDetail:
    clusters = session.exec(
        select(ScanDefectAggregateCluster)
        .where(ScanDefectAggregateCluster.aggregation_run_id == run.id)
        .order_by(col(ScanDefectAggregateCluster.cluster_rank), col(ScanDefectAggregateCluster.id))
    ).all()
    evidence = session.exec(
        select(ScanDefectAggregateEvidence)
        .where(ScanDefectAggregateEvidence.aggregation_run_id == run.id)
        .order_by(col(ScanDefectAggregateEvidence.cluster_id), col(ScanDefectAggregateEvidence.id))
    ).all()
    artifacts = session.exec(
        select(ScanDefectAggregationArtifact)
        .where(ScanDefectAggregationArtifact.aggregation_run_id == run.id)
        .order_by(col(ScanDefectAggregationArtifact.id))
    ).all()
    issues = session.exec(
        select(ScanDefectAggregationIssue)
        .where(ScanDefectAggregationIssue.aggregation_run_id == run.id)
        .order_by(col(ScanDefectAggregationIssue.id))
    ).all()
    history = session.exec(
        select(ScanDefectAggregationHistory)
        .where(ScanDefectAggregationHistory.aggregation_run_id == run.id)
        .order_by(col(ScanDefectAggregationHistory.id))
    ).all()
    defect_run_id = run.input_manifest_json.get("defect_run_id")
    defect_run = session.get(ScanDefectRun, int(defect_run_id)) if defect_run_id else None
    source_artifact = session.get(ScanNormalizationArtifact, int(defect_run.source_artifact_id)) if defect_run else None
    scan_image = session.get(ScanImage, int(run.scan_image_id))
    norm_run = session.get(ScanNormalizationRun, int(defect_run.normalization_run_id)) if defect_run else None
    boundary_run = session.get(ScanBoundaryRun, int(defect_run.boundary_run_id)) if defect_run else None
    art_reads = [
        ScanDefectAggregationArtifactRead.model_validate(row).model_copy(update={"preview_data_url": _artifact_preview_data_url(settings, row)})
        for row in artifacts
    ]
    run_data = ScanDefectAggregationRunRead.model_validate(run).model_dump()
    output = run.output_manifest_json or {}
    lineage = dict(output.get("upstream_lineage") or {})
    return ScanDefectAggregationRunDetail(
        **run_data,
        clusters=[ScanDefectAggregateClusterRead.model_validate(row) for row in clusters],
        evidence=[ScanDefectAggregateEvidenceRead.model_validate(row) for row in evidence],
        artifacts=art_reads,
        issues=[ScanDefectAggregationIssueRead.model_validate(row) for row in issues],
        history=[ScanDefectAggregationHistoryRead.model_validate(row) for row in history],
        original_scan_checksum=scan_image.sha256_checksum if scan_image else None,
        normalization_checksum=norm_run.normalization_checksum if norm_run else None,
        boundary_checksum=boundary_run.boundary_checksum if boundary_run else None,
        defect_checksum=lineage.get("defect_checksum"),
        spine_tick_checksum=lineage.get("spine_tick_checksum"),
        corner_edge_checksum=lineage.get("corner_edge_checksum"),
        surface_defect_checksum=lineage.get("surface_defect_checksum"),
        structural_damage_checksum=lineage.get("structural_damage_checksum"),
        source_preview_data_url=_load_source_preview(settings, source_artifact) if source_artifact else None,
        region_summaries=dict(output.get("region_summaries") or {}),
    )


def run_scan_defect_aggregation(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: ScanDefectAggregationRunCreate,
) -> tuple[ScanDefectAggregationRunDetail, bool]:
    defect_run = _resolve_defect_run(session, owner_user_id=owner_user_id, payload=payload)
    source_artifact = session.get(ScanNormalizationArtifact, int(defect_run.source_artifact_id))
    if source_artifact is None:
        raise HTTPException(status_code=409, detail="Defect run is missing its normalized source artifact.")
    try:
        with Image.open(_resolve_normalization_artifact_path(settings, source_artifact)) as image_fp:
            image = _image_to_rgb(image_fp)
    except (FileNotFoundError, OSError, ValueError, UnidentifiedImageError) as exc:
        raise HTTPException(status_code=409, detail="Normalized source artifact is not available for defect aggregation.") from exc

    evidence_rows, lineage, initial_issues, extra = load_upstream_evidence(session, defect_run=defect_run)
    clusters = cluster_related_evidence(evidence_rows=evidence_rows, full_cover_area=int(extra["full_cover_area"]))
    region_summaries = generate_condition_region_summary(clusters)
    issues = _build_issues(evidence_rows=evidence_rows, clusters=clusters, initial_issues=initial_issues)
    provisional_artifacts = _artifact_drafts_for_run(image=image, clusters=clusters, region_summaries=region_summaries)
    provisional_manifest, aggregation_checksum = build_aggregation_manifest(
        defect_run=defect_run,
        lineage=lineage,
        clusters=clusters,
        region_summaries=region_summaries,
        issues=issues,
        artifact_checksums=[{"artifact_type": row.artifact_type, "artifact_checksum": _sha256_bytes(row.body)} for row in provisional_artifacts],
    )
    manifest_artifact = _ArtifactDraft("AGGREGATION_MANIFEST", _serialize_json_artifact(provisional_manifest), {"format": "json"}, ".json")
    artifacts = provisional_artifacts + [manifest_artifact]

    existing = session.exec(
        select(ScanDefectAggregationRun).where(
            ScanDefectAggregationRun.owner_user_id == owner_user_id,
            ScanDefectAggregationRun.aggregation_checksum == aggregation_checksum,
        )
    ).first()
    if existing is not None:
        return _detail_from_run(session, settings, existing), False

    run = ScanDefectAggregationRun(
        owner_user_id=owner_user_id,
        scan_image_id=int(defect_run.scan_image_id),
        source_checksum=defect_run.source_checksum,
        aggregation_checksum=aggregation_checksum,
        aggregation_status="COMPLETE",
        engine_version=ENGINE_VERSION,
        input_manifest_json={
            "scan_image_id": defect_run.scan_image_id,
            "defect_run_id": defect_run.id,
            "source_checksum": defect_run.source_checksum,
            **extra["run_ids"],
        },
        output_manifest_json=provisional_manifest,
        completed_at=utc_now(),
    )
    session.add(run)
    session.flush()

    cluster_id_map: dict[int, int] = {}
    for rank, cluster in enumerate(clusters, start=1):
        cluster_row = ScanDefectAggregateCluster(
            owner_user_id=owner_user_id,
            aggregation_run_id=int(run.id or 0),
            cluster_rank=rank,
            cluster_type=cluster.cluster_type,
            cluster_region=cluster.cluster_region,
            cluster_confidence=cluster.cluster_confidence,
            aggregate_severity_hint=cluster.aggregate_severity_hint,
            x_min=cluster.x_min,
            y_min=cluster.y_min,
            x_max=cluster.x_max,
            y_max=cluster.y_max,
            cluster_area_ratio=cluster.cluster_area_ratio,
            measurement_json={**cluster.measurement_json, "cluster_rank": rank},
            metadata_json={**cluster.metadata_json, "cluster_rank": rank},
        )
        session.add(cluster_row)
        session.flush()
        cluster_id = int(cluster_row.id or 0)
        cluster_id_map[rank] = cluster_id
        total_seed = sum(member.contribution_seed + member.confidence_score + member.area_ratio for member in cluster.evidence) or 1.0
        for member in cluster.evidence:
            contribution = round((member.contribution_seed + member.confidence_score + member.area_ratio) / total_seed, 6)
            session.add(
                ScanDefectAggregateEvidence(
                    owner_user_id=owner_user_id,
                    aggregation_run_id=int(run.id or 0),
                    cluster_id=cluster_id,
                    source_detector=member.source_detector,
                    source_evidence_id=member.source_evidence_id,
                    evidence_type=member.evidence_type,
                    confidence_score=member.confidence_score,
                    contribution_weight=contribution,
                    metadata_json={
                        "source_run_id": member.source_run_id,
                        "run_checksum": member.run_checksum,
                        "region_type": member.region_type,
                        "region_group": member.region_group,
                        "evidence_rank": member.evidence_rank,
                    },
                )
            )

    for issue in issues:
        session.add(
            ScanDefectAggregationIssue(
                owner_user_id=owner_user_id,
                aggregation_run_id=int(run.id or 0),
                issue_type=issue.issue_type,
                severity=issue.severity,
                issue_message=issue.issue_message,
                metadata_json=issue.metadata_json,
            )
        )
    history_rows = [
        _HistoryDraft("AGGREGATION_RUN_CREATED", "Created deterministic defect aggregation run.", {"aggregation_checksum": aggregation_checksum}),
        _HistoryDraft("UPSTREAM_EVIDENCE_LOADED", "Loaded specialized detector evidence and lineage.", {"source_evidence_count": len(evidence_rows)}),
        _HistoryDraft("EVIDENCE_CLUSTERED", "Clustered overlapping evidence into unified aggregate condition clusters.", {"cluster_count": len(clusters)}),
        _HistoryDraft("AGGREGATION_MANIFEST_WRITTEN", "Persisted replay-safe aggregation manifest and artifacts.", {"artifact_count": len(artifacts)}),
    ]
    for row in history_rows:
        session.add(
            ScanDefectAggregationHistory(
                owner_user_id=owner_user_id,
                aggregation_run_id=int(run.id or 0),
                event_type=row.event_type,
                event_message=row.event_message,
                event_checksum=_hash_payload(
                    {
                        "aggregation_run_id": int(run.id or 0),
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
            scan_image_id=int(defect_run.scan_image_id),
            aggregation_run_id=int(run.id or 0),
            artifact_type=row.artifact_type,
            ext=row.ext,
        )
        _save_artifact_bytes(settings, relative_path=relative_path, body=row.body)
        session.add(
            ScanDefectAggregationArtifact(
                owner_user_id=owner_user_id,
                aggregation_run_id=int(run.id or 0),
                artifact_type=row.artifact_type,
                storage_path=relative_path,
                artifact_checksum=_sha256_bytes(row.body),
                metadata_json=row.metadata_json,
            )
        )
    session.commit()
    session.refresh(run)
    return _detail_from_run(session, settings, run), True


def get_scan_defect_aggregation_run_owner(session: Session, settings: Settings, *, owner_user_id: int, run_id: int) -> ScanDefectAggregationRunDetail:
    row = session.get(ScanDefectAggregationRun, run_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Defect aggregation run not found.")
    return _detail_from_run(session, settings, row)


def get_scan_defect_aggregation_artifact_owner(session: Session, settings: Settings, *, owner_user_id: int, artifact_id: int) -> ScanDefectAggregationArtifactRead:
    row = session.get(ScanDefectAggregationArtifact, artifact_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Defect aggregation artifact not found.")
    return ScanDefectAggregationArtifactRead.model_validate(row).model_copy(update={"preview_data_url": _artifact_preview_data_url(settings, row)})


def _run_list_response(rows: list[ScanDefectAggregationRun], *, limit: int, offset: int, total_items: int) -> ScanDefectAggregationRunListResponse:
    status_counts = {status: sum(1 for row in rows if row.aggregation_status == status) for status in sorted({row.aggregation_status for row in rows})}
    low_confidence_clusters = sum(
        sum(1 for cluster in (row.output_manifest_json.get("clusters") or []) if float(cluster.get("cluster_confidence") or 0.0) < _LOW_CLUSTER_CONFIDENCE)
        for row in rows
    )
    unresolved_issues = sum(len(row.output_manifest_json.get("issues") or []) for row in rows)
    densities = []
    for row in rows:
        cluster_count = int((row.output_manifest_json.get("aggregate_summary") or {}).get("cluster_count") or 0)
        source_count = int((row.output_manifest_json.get("aggregate_summary") or {}).get("source_evidence_count") or 0)
        densities.append(cluster_count / max(1, source_count))
    return ScanDefectAggregationRunListResponse(
        items=[ScanDefectAggregationRunRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        status_counts=status_counts,
        low_confidence_clusters=low_confidence_clusters,
        unresolved_issue_count=unresolved_issues,
        aggregate_anomaly_density=round(sum(densities) / max(1, len(densities)), 6),
    )


def list_scan_defect_aggregation_runs_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanDefectAggregationRunListResponse:
    limit, offset = clamp_scan_defect_aggregation_pagination(limit=limit, offset=offset)
    stmt = select(ScanDefectAggregationRun).where(ScanDefectAggregationRun.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanDefectAggregationRun).where(ScanDefectAggregationRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanDefectAggregationRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanDefectAggregationRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanDefectAggregationRun.created_at).desc(), col(ScanDefectAggregationRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_defect_aggregation_runs_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanDefectAggregationRunListResponse:
    limit, offset = clamp_scan_defect_aggregation_pagination(limit=limit, offset=offset)
    stmt = select(ScanDefectAggregationRun)
    count_stmt = select(func.count()).select_from(ScanDefectAggregationRun)
    if owner_user_id is not None:
        stmt = stmt.where(ScanDefectAggregationRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanDefectAggregationRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanDefectAggregationRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanDefectAggregationRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanDefectAggregationRun.created_at).desc(), col(ScanDefectAggregationRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_defect_aggregate_clusters_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    aggregation_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanDefectAggregateClusterListResponse:
    limit, offset = clamp_scan_defect_aggregation_pagination(limit=limit, offset=offset)
    stmt = select(ScanDefectAggregateCluster).join(
        ScanDefectAggregationRun,
        ScanDefectAggregationRun.id == ScanDefectAggregateCluster.aggregation_run_id,
    ).where(ScanDefectAggregateCluster.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanDefectAggregateCluster).join(
        ScanDefectAggregationRun,
        ScanDefectAggregationRun.id == ScanDefectAggregateCluster.aggregation_run_id,
    ).where(ScanDefectAggregateCluster.owner_user_id == owner_user_id)
    if aggregation_run_id is not None:
        stmt = stmt.where(ScanDefectAggregateCluster.aggregation_run_id == aggregation_run_id)
        count_stmt = count_stmt.where(ScanDefectAggregateCluster.aggregation_run_id == aggregation_run_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanDefectAggregationRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanDefectAggregationRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanDefectAggregateCluster.cluster_rank), col(ScanDefectAggregateCluster.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanDefectAggregateClusterListResponse(
        items=[ScanDefectAggregateClusterRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        cluster_type_counts={key: sum(1 for row in rows if row.cluster_type == key) for key in sorted({row.cluster_type for row in rows})},
        severity_hint_counts={key: sum(1 for row in rows if row.aggregate_severity_hint == key) for key in sorted({row.aggregate_severity_hint for row in rows})},
        mixed_cluster_count=sum(1 for row in rows if row.cluster_type == "MIXED_CLUSTER"),
    )


def list_scan_defect_aggregation_evidence_owner(
    session: Session,
    *,
    owner_user_id: int,
    aggregation_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanDefectAggregateEvidenceListResponse:
    limit, offset = clamp_scan_defect_aggregation_pagination(limit=limit, offset=offset)
    stmt = select(ScanDefectAggregateEvidence).where(ScanDefectAggregateEvidence.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanDefectAggregateEvidence).where(ScanDefectAggregateEvidence.owner_user_id == owner_user_id)
    if aggregation_run_id is not None:
        stmt = stmt.where(ScanDefectAggregateEvidence.aggregation_run_id == aggregation_run_id)
        count_stmt = count_stmt.where(ScanDefectAggregateEvidence.aggregation_run_id == aggregation_run_id)
    rows = session.exec(stmt.order_by(col(ScanDefectAggregateEvidence.cluster_id), col(ScanDefectAggregateEvidence.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanDefectAggregateEvidenceListResponse(
        items=[ScanDefectAggregateEvidenceRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        source_detector_counts={key: sum(1 for row in rows if row.source_detector == key) for key in sorted({row.source_detector for row in rows})},
    )


def list_scan_defect_aggregation_issues_owner(
    session: Session,
    *,
    owner_user_id: int,
    aggregation_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanDefectAggregationIssueListResponse:
    limit, offset = clamp_scan_defect_aggregation_pagination(limit=limit, offset=offset)
    stmt = select(ScanDefectAggregationIssue).where(ScanDefectAggregationIssue.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanDefectAggregationIssue).where(ScanDefectAggregationIssue.owner_user_id == owner_user_id)
    if aggregation_run_id is not None:
        stmt = stmt.where(ScanDefectAggregationIssue.aggregation_run_id == aggregation_run_id)
        count_stmt = count_stmt.where(ScanDefectAggregationIssue.aggregation_run_id == aggregation_run_id)
    rows = session.exec(stmt.order_by(col(ScanDefectAggregationIssue.created_at), col(ScanDefectAggregationIssue.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanDefectAggregationIssueListResponse(
        items=[ScanDefectAggregationIssueRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        issue_type_counts={key: sum(1 for row in rows if row.issue_type == key) for key in sorted({row.issue_type for row in rows})},
    )


def list_scan_defect_aggregation_issues_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanDefectAggregationIssueListResponse:
    limit, offset = clamp_scan_defect_aggregation_pagination(limit=limit, offset=offset)
    stmt = select(ScanDefectAggregationIssue)
    count_stmt = select(func.count()).select_from(ScanDefectAggregationIssue)
    if owner_user_id is not None:
        stmt = stmt.where(ScanDefectAggregationIssue.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanDefectAggregationIssue.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanDefectAggregationIssue.created_at), col(ScanDefectAggregationIssue.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanDefectAggregationIssueListResponse(
        items=[ScanDefectAggregationIssueRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        issue_type_counts={key: sum(1 for row in rows if row.issue_type == key) for key in sorted({row.issue_type for row in rows})},
    )


def list_scan_defect_aggregation_failures_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanDefectAggregationFailureListResponse:
    limit, offset = clamp_scan_defect_aggregation_pagination(limit=limit, offset=offset)
    stmt = select(ScanDefectAggregationRun).where(ScanDefectAggregationRun.aggregation_status == "FAILED")
    count_stmt = select(func.count()).select_from(ScanDefectAggregationRun).where(ScanDefectAggregationRun.aggregation_status == "FAILED")
    if owner_user_id is not None:
        stmt = stmt.where(ScanDefectAggregationRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanDefectAggregationRun.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanDefectAggregationRun.created_at).desc(), col(ScanDefectAggregationRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanDefectAggregationFailureListResponse(
        items=[ScanDefectAggregationRunRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )
