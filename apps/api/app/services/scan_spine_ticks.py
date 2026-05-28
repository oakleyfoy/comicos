from __future__ import annotations

import base64
import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageFilter, ImageStat, UnidentifiedImageError
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models import (
    ScanBoundaryRun,
    ScanDefectEvidence,
    ScanDefectRegion,
    ScanDefectRun,
    ScanImage,
    ScanNormalizationArtifact,
    ScanNormalizationRun,
    ScanSpineTickArtifact,
    ScanSpineTickEvidence,
    ScanSpineTickHistory,
    ScanSpineTickIssue,
    ScanSpineTickRun,
)
from app.schemas.scan_spine_ticks import (
    ScanSpineTickArtifactRead,
    ScanSpineTickEvidenceListResponse,
    ScanSpineTickEvidenceRead,
    ScanSpineTickFailureListResponse,
    ScanSpineTickHistoryRead,
    ScanSpineTickIssueListResponse,
    ScanSpineTickIssueRead,
    ScanSpineTickRunCreate,
    ScanSpineTickRunDetail,
    ScanSpineTickRunListResponse,
    ScanSpineTickRunRead,
)
from app.services.scan_defects import _load_source_preview, _resolve_normalization_artifact_path

ENGINE_VERSION = "P40-07-v1"
_PREVIEW_MAX = 420
_LOW_CONFIDENCE_THRESHOLD = 0.35


@dataclass(frozen=True)
class _SpineIsolation:
    region_id: int
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    width_px: int
    height_px: int
    region_checksum: str
    edge_orientation_degrees: float
    spine_edge_x: int
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _TickDraft:
    tick_rank: int
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    width_px: int
    height_px: int
    angle_degrees: float
    edge_distance_px: int
    spine_overlap_ratio: float
    confidence_score: float
    severity_hint: str
    measurement_json: dict[str, Any]
    metadata_json: dict[str, Any]
    defect_evidence_id: int | None


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
    from app.models.scan_spine_ticks import utc_now as _utc_now

    return _utc_now()


def clamp_scan_spine_tick_pagination(*, limit: int, offset: int) -> tuple[int, int]:
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


def _resolve_spine_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.scan_spine_ticks_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("scan spine tick storage path escapes configured root")
    return target


def _artifact_storage_path(
    *,
    owner_user_id: int,
    scan_image_id: int,
    spine_tick_run_id: int,
    artifact_type: str,
    ext: str,
) -> str:
    safe_type = artifact_type.lower()
    return f"scan-spine-ticks/{owner_user_id}/{scan_image_id}/{spine_tick_run_id}/{safe_type}{ext}".replace("\\", "/")


def _save_artifact_bytes(settings: Settings, *, relative_path: str, body: bytes) -> None:
    target = _resolve_spine_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)


def _artifact_preview_data_url(settings: Settings, row: ScanSpineTickArtifact) -> str | None:
    if not row.storage_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        return None
    try:
        body = _resolve_spine_storage_path(settings, row.storage_path).read_bytes()
    except OSError:
        return None
    return f"data:image/png;base64,{base64.b64encode(body).decode('ascii')}"


def _image_to_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image.copy()
    return image.convert("RGB")


def _serialize_json_artifact(payload: Any) -> bytes:
    return json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"), indent=2).encode("utf-8")


def isolate_spine_region(
    *,
    image: Image.Image,
    spine_region: ScanDefectRegion,
) -> tuple[_SpineIsolation, Image.Image]:
    x_min, y_min, x_max, y_max = spine_region.x_min, spine_region.y_min, spine_region.x_max, spine_region.y_max
    crop = _image_to_rgb(image).crop((x_min, y_min, x_max + 1, y_max + 1))
    gray = crop.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    column_energy = [float(ImageStat.Stat(edges.crop((x, 0, x + 1, crop.height))).mean[0] or 0.0) for x in range(crop.width)]
    spine_edge_x = int(column_energy.index(max(column_energy))) if column_energy else 0
    orientation = 90.0 if crop.height >= crop.width else 0.0
    return (
        _SpineIsolation(
            region_id=int(spine_region.id or 0),
            x_min=x_min,
            y_min=y_min,
            x_max=x_max,
            y_max=y_max,
            width_px=spine_region.width_px,
            height_px=spine_region.height_px,
            region_checksum=spine_region.region_checksum,
            edge_orientation_degrees=orientation,
            spine_edge_x=spine_edge_x,
            metadata_json={
                "region_type": spine_region.region_type,
                "spine_edge_x_relative": round(spine_edge_x / max(1, crop.width), 6),
            },
        ),
        crop,
    )


def _row_disruption_scores(crop: Image.Image) -> list[float]:
    gray = crop.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    width = max(1, crop.width)
    scores: list[float] = []
    for y in range(crop.height):
        row = edges.crop((0, y, width, y + 1))
        stat = ImageStat.Stat(row)
        scores.append(float(stat.mean[0]) if stat.mean else 0.0)
    return scores


def detect_spine_edge_anomalies(*, crop: Image.Image, isolation: _SpineIsolation) -> list[tuple[int, int, float]]:
    scores = _row_disruption_scores(crop)
    if not scores:
        return []
    ordered = sorted(scores)
    median = ordered[len(ordered) // 2]
    threshold = median + max(6.0, median * 0.28)
    segments: list[tuple[int, int, float]] = []
    start: int | None = None
    peak = 0.0
    for y, score in enumerate(scores):
        if score >= threshold:
            if start is None:
                start = y
                peak = score
            else:
                peak = max(peak, score)
        elif start is not None:
            segments.append((start, y - 1, peak))
            start = None
            peak = 0.0
    if start is not None:
        segments.append((start, crop.height - 1, peak))
    return segments


def calculate_spine_measurements(
    *,
    crop: Image.Image,
    isolation: _SpineIsolation,
    y_min_local: int,
    y_max_local: int,
    peak_score: float,
    scores: list[float],
) -> dict[str, Any]:
    segment = crop.crop((0, y_min_local, crop.width, y_max_local + 1))
    gray = segment.convert("L")
    stat = ImageStat.Stat(gray)
    edge_stat = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES))
    baseline = sorted(scores)[len(scores) // 2] if scores else 0.0
    brightness_variance = float(stat.stddev[0]) if stat.stddev else 0.0
    contrast_delta = abs(brightness_variance - baseline) / 128.0
    edge_disruption = (peak_score - baseline) / max(1.0, baseline + 12.0)
    penetration = min(1.0, segment.width / max(1, crop.width))
    pixel_length = max(1, y_max_local - y_min_local + 1)
    pixel_width = max(1, segment.width)
    normalized_size = pixel_length / max(1, isolation.height_px)
    return {
        "pixel_length": pixel_length,
        "pixel_width": pixel_width,
        "orientation_angle_degrees": isolation.edge_orientation_degrees,
        "spine_penetration_depth": round(penetration, 6),
        "brightness_variance": round(brightness_variance, 6),
        "contrast_delta": round(contrast_delta, 6),
        "edge_disruption_ratio": round(min(1.0, edge_disruption), 6),
        "edge_sharpness_delta": round(float(edge_stat.mean[0]) if edge_stat.mean else 0.0, 6),
        "overlap_with_spine_boundary": round(penetration, 6),
        "normalized_relative_size": round(normalized_size, 6),
        "raw_peak_score": round(peak_score, 6),
        "raw_baseline_score": round(baseline, 6),
    }


def _severity_hint(normalized_size: float, edge_disruption: float) -> str:
    score = normalized_size * 0.55 + edge_disruption * 0.45
    if score >= 0.22:
        return "MAJOR"
    if score >= 0.1:
        return "MODERATE"
    return "MINOR"


def _confidence_score(measurements: dict[str, Any]) -> float:
    return round(
        min(
            1.0,
            max(
                0.05,
                float(measurements["edge_disruption_ratio"]) * 0.55
                + float(measurements["normalized_relative_size"]) * 0.25
                + float(measurements["contrast_delta"]) * 0.2,
            ),
        ),
        6,
    )


def _overlap_evidence_id(
    *,
    defect_evidence: list[ScanDefectEvidence],
    y_min: int,
    y_max: int,
) -> int | None:
    best_id: int | None = None
    best_overlap = 0.0
    for row in defect_evidence:
        if row.evidence_category not in {"SPINE_ANOMALY", "EDGE_ANOMALY"}:
            continue
        overlap_top = max(y_min, row.y_min)
        overlap_bottom = min(y_max, row.y_max)
        if overlap_bottom < overlap_top:
            continue
        overlap = (overlap_bottom - overlap_top + 1) / max(1, y_max - y_min + 1)
        if overlap > best_overlap:
            best_overlap = overlap
            best_id = int(row.id or 0)
    return best_id


def segment_spine_ticks(
    *,
    image: Image.Image,
    crop: Image.Image,
    isolation: _SpineIsolation,
    segments: list[tuple[int, int, float]],
    defect_evidence: list[ScanDefectEvidence],
) -> list[_TickDraft]:
    scores = _row_disruption_scores(crop)
    drafts: list[_TickDraft] = []
    for rank, (y0, y1, peak) in enumerate(segments, start=1):
        measurements = calculate_spine_measurements(
            crop=crop,
            isolation=isolation,
            y_min_local=y0,
            y_max_local=y1,
            peak_score=peak,
            scores=scores,
        )
        confidence = _confidence_score(measurements)
        severity = _severity_hint(float(measurements["normalized_relative_size"]), float(measurements["edge_disruption_ratio"]))
        abs_y_min = isolation.y_min + y0
        abs_y_max = isolation.y_min + y1
        width_px = max(1, isolation.x_max - isolation.x_min + 1)
        height_px = max(1, abs_y_max - abs_y_min + 1)
        overlap_ratio = round(height_px / max(1, isolation.height_px), 6)
        drafts.append(
            _TickDraft(
                tick_rank=rank,
                x_min=isolation.x_min,
                y_min=abs_y_min,
                x_max=isolation.x_max,
                y_max=abs_y_max,
                width_px=width_px,
                height_px=height_px,
                angle_degrees=isolation.edge_orientation_degrees,
                edge_distance_px=abs(isolation.spine_edge_x),
                spine_overlap_ratio=overlap_ratio,
                confidence_score=confidence,
                severity_hint=severity,
                measurement_json=measurements,
                metadata_json={"segment_local_y": [y0, y1], "peak_score": round(peak, 6)},
                defect_evidence_id=_overlap_evidence_id(
                    defect_evidence=defect_evidence,
                    y_min=abs_y_min,
                    y_max=abs_y_max,
                ),
            )
        )
    return sorted(drafts, key=lambda row: (row.tick_rank, row.y_min, row.y_max))


def build_spine_tick_manifest(
    *,
    defect_run: ScanDefectRun,
    isolation: _SpineIsolation,
    evidence: list[_TickDraft],
    issues: list[_IssueDraft],
    artifact_checksums: list[dict[str, str]],
) -> tuple[dict[str, Any], str]:
    manifest: dict[str, Any] = {
        "engine_version": ENGINE_VERSION,
        "lineage": {
            "original_scan_checksum": defect_run.input_manifest_json.get("lineage", {}).get("original_scan_checksum"),
            "normalization_checksum": defect_run.input_manifest_json.get("lineage", {}).get("normalization_checksum"),
            "boundary_checksum": defect_run.input_manifest_json.get("lineage", {}).get("boundary_checksum"),
            "defect_checksum": defect_run.defect_checksum,
            "source_checksum": defect_run.source_checksum,
        },
        "spine_region": {
            "region_id": isolation.region_id,
            "region_checksum": isolation.region_checksum,
            "bbox": [isolation.x_min, isolation.y_min, isolation.x_max, isolation.y_max],
            "edge_orientation_degrees": isolation.edge_orientation_degrees,
            "metadata_json": isolation.metadata_json,
        },
        "evidence": [
            {
                "tick_rank": row.tick_rank,
                "bbox": [row.x_min, row.y_min, row.x_max, row.y_max],
                "confidence_score": row.confidence_score,
                "severity_hint": row.severity_hint,
                "measurement_json": row.measurement_json,
                "defect_evidence_id": row.defect_evidence_id,
            }
            for row in evidence
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
        "evidence_summary": {
            "total_tick_count": len(evidence),
            "low_confidence_count": sum(1 for row in evidence if row.confidence_score < _LOW_CONFIDENCE_THRESHOLD),
            "major_count": sum(1 for row in evidence if row.severity_hint == "MAJOR"),
        },
    }
    return manifest, _hash_payload(manifest)


def _minimal_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (12, 12, 16)).save(buf, format="PNG")
    return buf.getvalue()


def _artifact_drafts_for_run(
    *,
    image: Image.Image,
    crop: Image.Image | None,
    isolation: _SpineIsolation | None,
    evidence: list[_TickDraft],
    measurement_export: dict[str, Any],
) -> list[_ArtifactDraft]:
    if crop is not None and isolation is not None:
        return [
            _ArtifactDraft("SPINE_REGION_PREVIEW", _build_spine_region_preview(crop), {"format": "png"}, ".png"),
            _ArtifactDraft("SPINE_EDGE_MAP", _build_spine_edge_map(crop), {"format": "png"}, ".png"),
            _ArtifactDraft(
                "SPINE_TICK_OVERLAY",
                _build_spine_tick_overlay(image, evidence),
                {"format": "png", "tick_count": len(evidence)},
                ".png",
            ),
            _ArtifactDraft(
                "SPINE_MEASUREMENT_EXPORT",
                _serialize_json_artifact(measurement_export),
                {"format": "json", "tick_count": len(evidence)},
                ".json",
            ),
            _ArtifactDraft(
                "SPINE_DEBUG_PREVIEW",
                _build_debug_preview(image, isolation, evidence),
                {"format": "png"},
                ".png",
            ),
        ]
    tiny = _minimal_png()
    return [
        _ArtifactDraft("SPINE_REGION_PREVIEW", tiny, {"format": "png", "placeholder": True}, ".png"),
        _ArtifactDraft("SPINE_EDGE_MAP", tiny, {"format": "png", "placeholder": True}, ".png"),
        _ArtifactDraft("SPINE_TICK_OVERLAY", _build_spine_tick_overlay(image, evidence), {"format": "png", "tick_count": 0}, ".png"),
        _ArtifactDraft("SPINE_MEASUREMENT_EXPORT", _serialize_json_artifact(measurement_export), {"format": "json", "tick_count": 0}, ".json"),
        _ArtifactDraft("SPINE_DEBUG_PREVIEW", tiny, {"format": "png", "placeholder": True}, ".png"),
    ]


def _build_spine_region_preview(crop: Image.Image) -> bytes:
    preview = crop.copy()
    preview.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
    buf = io.BytesIO()
    preview.save(buf, format="PNG")
    return buf.getvalue()


def _build_spine_edge_map(crop: Image.Image) -> bytes:
    edges = crop.convert("L").filter(ImageFilter.FIND_EDGES)
    rendered = Image.new("RGB", crop.size, (20, 20, 28))
    edge_rgb = Image.merge("RGB", (edges, edges, edges))
    rendered = Image.blend(rendered, edge_rgb, 0.85)
    buf = io.BytesIO()
    rendered.save(buf, format="PNG")
    return buf.getvalue()


def _build_spine_tick_overlay(image: Image.Image, evidence: list[_TickDraft]) -> bytes:
    rendered = _image_to_rgb(image)
    draw = ImageDraw.Draw(rendered)
    palette = {"MINOR": "#eab308", "MODERATE": "#f97316", "MAJOR": "#ef4444"}
    for row in evidence:
        draw.rectangle((row.x_min, row.y_min, row.x_max, row.y_max), outline=palette.get(row.severity_hint, "#ffffff"), width=3)
    buf = io.BytesIO()
    rendered.save(buf, format="PNG")
    return buf.getvalue()


def _build_debug_preview(image: Image.Image, isolation: _SpineIsolation, evidence: list[_TickDraft]) -> bytes:
    rendered = _image_to_rgb(image)
    draw = ImageDraw.Draw(rendered)
    draw.rectangle((isolation.x_min, isolation.y_min, isolation.x_max, isolation.y_max), outline="#38bdf8", width=2)
    for row in evidence[:8]:
        draw.rectangle((row.x_min, row.y_min, row.x_max, row.y_max), outline="#ef4444", width=2)
    preview = rendered.copy()
    preview.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
    buf = io.BytesIO()
    preview.save(buf, format="PNG")
    return buf.getvalue()


def _build_issues(
    *,
    spine_region: ScanDefectRegion | None,
    isolation: _SpineIsolation | None,
    crop: Image.Image | None,
    segments: list[tuple[int, int, float]],
    evidence: list[_TickDraft],
    defect_run: ScanDefectRun,
) -> list[_IssueDraft]:
    issues: list[_IssueDraft] = []
    if spine_region is None:
        issues.append(
            _IssueDraft(
                issue_type="SPINE_REGION_MISSING",
                severity="ERROR",
                issue_message="Defect foundation did not provide a SPINE_REGION for tick analysis.",
                metadata_json={},
            )
        )
        return issues
    if crop is None or isolation is None:
        issues.append(
            _IssueDraft(
                issue_type="SPINE_TICK_DETECTION_FAILED",
                severity="ERROR",
                issue_message="Spine region isolation failed.",
                metadata_json={},
            )
        )
        return issues
    gray = crop.convert("L")
    stat = ImageStat.Stat(gray)
    mean_brightness = float(stat.mean[0]) if stat.mean else 0.0
    stddev = float(stat.stddev[0]) if stat.stddev else 0.0
    histogram = gray.histogram()
    total = max(1, crop.width * crop.height)
    light_ratio = sum(histogram[230:]) / total
    if light_ratio > 0.2 and mean_brightness > 185:
        issues.append(
            _IssueDraft(
                issue_type="EXCESSIVE_GLARE",
                severity="WARNING",
                issue_message="Spine region brightness suggests glare that may reduce tick detection reliability.",
                metadata_json={"light_ratio": round(light_ratio, 6), "mean_brightness": round(mean_brightness, 6)},
            )
        )
    if stddev < 18:
        issues.append(
            _IssueDraft(
                issue_type="LOW_CONTRAST_SPINE",
                severity="WARNING",
                issue_message="Spine region contrast is low for stable edge segmentation.",
                metadata_json={"brightness_stddev": round(stddev, 6), "threshold": 18},
            )
        )
    edge_sum = sum(_row_disruption_scores(crop))
    if edge_sum < crop.height * 2:
        issues.append(
            _IssueDraft(
                issue_type="NO_SPINE_EDGE_FOUND",
                severity="WARNING",
                issue_message="Spine edge energy is too weak for confident tick segmentation.",
                metadata_json={"edge_sum": round(edge_sum, 6)},
            )
        )
    if not segments:
        issues.append(
            _IssueDraft(
                issue_type="EDGE_SEGMENTATION_FAILED",
                severity="INFO",
                issue_message="No perpendicular spine stress segments exceeded the deterministic threshold.",
                metadata_json={"segment_count": 0},
            )
        )
    low_conf = sum(1 for row in evidence if row.confidence_score < _LOW_CONFIDENCE_THRESHOLD)
    if evidence and low_conf == len(evidence):
        issues.append(
            _IssueDraft(
                issue_type="LOW_SPINE_CONFIDENCE",
                severity="WARNING",
                issue_message="All spine tick evidence rows remain below the confidence floor.",
                metadata_json={"low_confidence_count": low_conf},
            )
        )
    angle = abs(float(defect_run.output_manifest_json.get("geometry", {}).get("angle_degrees", 0) or 0))
    if angle > 8:
        issues.append(
            _IssueDraft(
                issue_type="UNSTABLE_SPINE_GEOMETRY",
                severity="INFO",
                issue_message="Upstream cover geometry angle may reduce spine tick alignment confidence.",
                metadata_json={"angle_degrees": round(angle, 6)},
            )
        )
    margin_sum = sum(
        int(value)
        for value in (defect_run.output_manifest_json.get("lineage", {}) or {}).values()
        if isinstance(value, int)
    )
    if margin_sum == 0:
        bg_issues = [row for row in (defect_run.output_manifest_json.get("issues") or []) if row.get("issue_type") == "EXCESSIVE_BACKGROUND_ARTIFACTS"]
        if bg_issues:
            issues.append(
                _IssueDraft(
                    issue_type="EXCESSIVE_BACKGROUND_NOISE",
                    severity="INFO",
                    issue_message="Defect foundation reported background artifacts near the cover boundary.",
                    metadata_json={"upstream_issue_count": len(bg_issues)},
                )
            )
    return issues


def _resolve_defect_run(session: Session, *, owner_user_id: int, payload: ScanSpineTickRunCreate) -> ScanDefectRun:
    stmt = select(ScanDefectRun).where(
        ScanDefectRun.owner_user_id == owner_user_id,
        ScanDefectRun.scan_image_id == payload.scan_image_id,
        ScanDefectRun.defect_status == "COMPLETE",
    )
    if payload.defect_run_id is not None:
        stmt = stmt.where(ScanDefectRun.id == payload.defect_run_id)
    defect_run = session.exec(stmt.order_by(col(ScanDefectRun.id).desc())).first()
    if defect_run is None:
        raise HTTPException(status_code=409, detail="A complete defect foundation run is required before spine tick detection.")
    return defect_run


def _detail_from_run(session: Session, settings: Settings, run: ScanSpineTickRun) -> ScanSpineTickRunDetail:
    evidence = session.exec(
        select(ScanSpineTickEvidence)
        .where(ScanSpineTickEvidence.spine_tick_run_id == run.id)
        .order_by(col(ScanSpineTickEvidence.tick_rank), col(ScanSpineTickEvidence.id))
    ).all()
    artifacts = session.exec(
        select(ScanSpineTickArtifact)
        .where(ScanSpineTickArtifact.spine_tick_run_id == run.id)
        .order_by(col(ScanSpineTickArtifact.id))
    ).all()
    issues = session.exec(
        select(ScanSpineTickIssue).where(ScanSpineTickIssue.spine_tick_run_id == run.id).order_by(col(ScanSpineTickIssue.id))
    ).all()
    history = session.exec(
        select(ScanSpineTickHistory).where(ScanSpineTickHistory.spine_tick_run_id == run.id).order_by(col(ScanSpineTickHistory.id))
    ).all()
    defect_run = session.get(ScanDefectRun, int(run.defect_run_id))
    source_artifact = session.get(ScanNormalizationArtifact, int(defect_run.source_artifact_id)) if defect_run else None
    art_reads = [
        ScanSpineTickArtifactRead.model_validate(row).model_copy(
            update={"preview_data_url": _artifact_preview_data_url(settings, row)}
        )
        for row in artifacts
    ]
    spine_preview = next((a.preview_data_url for a in art_reads if a.artifact_type == "SPINE_REGION_PREVIEW"), None)
    run_data = ScanSpineTickRunRead.model_validate(run).model_dump()
    return ScanSpineTickRunDetail(
        **run_data,
        evidence=[ScanSpineTickEvidenceRead.model_validate(row) for row in evidence],
        artifacts=art_reads,
        issues=[ScanSpineTickIssueRead.model_validate(row) for row in issues],
        history=[ScanSpineTickHistoryRead.model_validate(row) for row in history],
        original_scan_checksum=session.get(ScanImage, int(run.scan_image_id)).sha256_checksum if session.get(ScanImage, int(run.scan_image_id)) else None,
        normalization_checksum=session.get(ScanNormalizationRun, int(defect_run.normalization_run_id)).normalization_checksum if defect_run and session.get(ScanNormalizationRun, int(defect_run.normalization_run_id)) else None,
        boundary_checksum=session.get(ScanBoundaryRun, int(defect_run.boundary_run_id)).boundary_checksum if defect_run and session.get(ScanBoundaryRun, int(defect_run.boundary_run_id)) else None,
        defect_checksum=defect_run.defect_checksum if defect_run else None,
        source_preview_data_url=_load_source_preview(settings, source_artifact) if source_artifact else None,
        spine_region_preview_data_url=spine_preview,
        evidence_summary=dict(run.output_manifest_json.get("evidence_summary") or {}),
    )


def run_scan_spine_tick_detection(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: ScanSpineTickRunCreate,
) -> tuple[ScanSpineTickRunDetail, bool]:
    defect_run = _resolve_defect_run(session, owner_user_id=owner_user_id, payload=payload)
    source_artifact = session.get(ScanNormalizationArtifact, int(defect_run.source_artifact_id))
    if source_artifact is None:
        raise HTTPException(status_code=409, detail="Defect run is missing its normalized source artifact.")
    spine_region = session.exec(
        select(ScanDefectRegion).where(
            ScanDefectRegion.defect_run_id == defect_run.id,
            ScanDefectRegion.region_type == "SPINE_REGION",
        )
    ).first()
    defect_evidence = session.exec(
        select(ScanDefectEvidence).where(ScanDefectEvidence.defect_run_id == defect_run.id).order_by(col(ScanDefectEvidence.id))
    ).all()

    try:
        with Image.open(_resolve_normalization_artifact_path(settings, source_artifact)) as image_fp:
            image = _image_to_rgb(image_fp)
    except (FileNotFoundError, OSError, ValueError, UnidentifiedImageError) as exc:
        raise HTTPException(status_code=409, detail="Normalized source artifact is not available for spine tick detection.") from exc

    isolation: _SpineIsolation | None = None
    crop: Image.Image | None = None
    segments: list[tuple[int, int, float]] = []
    evidence: list[_TickDraft] = []
    if spine_region is not None:
        isolation, crop = isolate_spine_region(image=image, spine_region=spine_region)
        segments = detect_spine_edge_anomalies(crop=crop, isolation=isolation)
        evidence = segment_spine_ticks(
            image=image,
            crop=crop,
            isolation=isolation,
            segments=segments,
            defect_evidence=defect_evidence,
        )

    issues = _build_issues(
        spine_region=spine_region,
        isolation=isolation,
        crop=crop,
        segments=segments,
        evidence=evidence,
        defect_run=defect_run,
    )

    measurement_export = {
        "ticks": [
            {
                "tick_rank": row.tick_rank,
                "measurement_json": row.measurement_json,
                "confidence_score": row.confidence_score,
                "severity_hint": row.severity_hint,
            }
            for row in evidence
        ]
    }
    provisional_artifacts = _artifact_drafts_for_run(
        image=image,
        crop=crop,
        isolation=isolation,
        evidence=evidence,
        measurement_export=measurement_export,
    )

    provisional_manifest, spine_tick_checksum = build_spine_tick_manifest(
        defect_run=defect_run,
        isolation=isolation
        or _SpineIsolation(0, 0, 0, 0, 0, 0, 0, "", 0.0, 0, {}),
        evidence=evidence,
        issues=issues,
        artifact_checksums=[
            {"artifact_type": row.artifact_type, "artifact_checksum": _sha256_bytes(row.body)} for row in provisional_artifacts
        ],
    )
    manifest_artifact = _ArtifactDraft("SPINE_TICK_MANIFEST", _serialize_json_artifact(provisional_manifest), {"format": "json"}, ".json")
    artifacts = provisional_artifacts + [manifest_artifact]

    existing = session.exec(
        select(ScanSpineTickRun).where(
            ScanSpineTickRun.owner_user_id == owner_user_id,
            ScanSpineTickRun.spine_tick_checksum == spine_tick_checksum,
        )
    ).first()
    if existing is not None:
        return _detail_from_run(session, settings, existing), False

    input_manifest = {
        "scan_image_id": defect_run.scan_image_id,
        "defect_run_id": defect_run.id,
        "defect_checksum": defect_run.defect_checksum,
        "source_checksum": defect_run.source_checksum,
        "spine_region_checksum": spine_region.region_checksum if spine_region else None,
    }
    run = ScanSpineTickRun(
        owner_user_id=owner_user_id,
        scan_image_id=int(defect_run.scan_image_id),
        defect_run_id=int(defect_run.id or 0),
        source_checksum=defect_run.source_checksum,
        spine_tick_checksum=spine_tick_checksum,
        detection_status="COMPLETE",
        engine_version=ENGINE_VERSION,
        input_manifest_json=input_manifest,
        output_manifest_json=provisional_manifest,
        completed_at=utc_now(),
    )
    session.add(run)
    session.flush()

    for row in evidence:
        session.add(
            ScanSpineTickEvidence(
                owner_user_id=owner_user_id,
                spine_tick_run_id=int(run.id or 0),
                defect_evidence_id=row.defect_evidence_id,
                tick_rank=row.tick_rank,
                confidence_score=row.confidence_score,
                severity_hint=row.severity_hint,
                x_min=row.x_min,
                y_min=row.y_min,
                x_max=row.x_max,
                y_max=row.y_max,
                width_px=row.width_px,
                height_px=row.height_px,
                angle_degrees=row.angle_degrees,
                edge_distance_px=row.edge_distance_px,
                spine_overlap_ratio=row.spine_overlap_ratio,
                measurement_json=row.measurement_json,
                metadata_json=row.metadata_json,
            )
        )
    for row in issues:
        session.add(
            ScanSpineTickIssue(
                owner_user_id=owner_user_id,
                spine_tick_run_id=int(run.id or 0),
                issue_type=row.issue_type,
                severity=row.severity,
                issue_message=row.issue_message,
                metadata_json=row.metadata_json,
            )
        )
    history_rows = [
        _HistoryDraft("SPINE_TICK_RUN_CREATED", "Created deterministic spine tick detection run.", {"spine_tick_checksum": spine_tick_checksum}),
        _HistoryDraft("SPINE_REGION_ISOLATED", "Isolated SPINE_REGION from defect foundation geometry.", {"region_present": spine_region is not None}),
        _HistoryDraft("SPINE_TICKS_SEGMENTED", "Segmented probable spine stress evidence.", {"tick_count": len(evidence)}),
        _HistoryDraft("SPINE_MANIFEST_WRITTEN", "Persisted replay-safe spine tick manifest and artifacts.", {"artifact_count": len(artifacts)}),
    ]
    for row in history_rows:
        session.add(
            ScanSpineTickHistory(
                owner_user_id=owner_user_id,
                spine_tick_run_id=int(run.id or 0),
                event_type=row.event_type,
                event_message=row.event_message,
                event_checksum=_hash_payload(
                    {
                        "spine_tick_run_id": int(run.id or 0),
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
            spine_tick_run_id=int(run.id or 0),
            artifact_type=row.artifact_type,
            ext=row.ext,
        )
        _save_artifact_bytes(settings, relative_path=relative_path, body=row.body)
        session.add(
            ScanSpineTickArtifact(
                owner_user_id=owner_user_id,
                spine_tick_run_id=int(run.id or 0),
                artifact_type=row.artifact_type,
                storage_path=relative_path,
                artifact_checksum=_sha256_bytes(row.body),
                metadata_json=row.metadata_json,
            )
        )
    session.commit()
    session.refresh(run)
    return _detail_from_run(session, settings, run), True


def get_scan_spine_tick_run_owner(session: Session, settings: Settings, *, owner_user_id: int, run_id: int) -> ScanSpineTickRunDetail:
    row = session.get(ScanSpineTickRun, run_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Spine tick run not found.")
    return _detail_from_run(session, settings, row)


def get_scan_spine_tick_artifact_owner(session: Session, settings: Settings, *, owner_user_id: int, artifact_id: int) -> ScanSpineTickArtifactRead:
    row = session.get(ScanSpineTickArtifact, artifact_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Spine tick artifact not found.")
    return ScanSpineTickArtifactRead.model_validate(row).model_copy(
        update={"preview_data_url": _artifact_preview_data_url(settings, row)}
    )


def _run_list_response(rows: list[ScanSpineTickRun], *, limit: int, offset: int, total_items: int) -> ScanSpineTickRunListResponse:
    status_counts = {status: sum(1 for row in rows if row.detection_status == status) for status in sorted({row.detection_status for row in rows})}
    low_confidence = sum(int((row.output_manifest_json.get("evidence_summary") or {}).get("low_confidence_count") or 0) for row in rows)
    high_density = sum(int((row.output_manifest_json.get("evidence_summary") or {}).get("major_count") or 0) for row in rows)
    return ScanSpineTickRunListResponse(
        items=[ScanSpineTickRunRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        status_counts=status_counts,
        low_confidence_count=low_confidence,
        high_density_anomaly_count=high_density,
    )


def list_scan_spine_tick_runs_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanSpineTickRunListResponse:
    limit, offset = clamp_scan_spine_tick_pagination(limit=limit, offset=offset)
    stmt = select(ScanSpineTickRun).where(ScanSpineTickRun.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanSpineTickRun).where(ScanSpineTickRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanSpineTickRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanSpineTickRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanSpineTickRun.created_at).desc(), col(ScanSpineTickRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_spine_tick_runs_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanSpineTickRunListResponse:
    limit, offset = clamp_scan_spine_tick_pagination(limit=limit, offset=offset)
    stmt = select(ScanSpineTickRun)
    count_stmt = select(func.count()).select_from(ScanSpineTickRun)
    if owner_user_id is not None:
        stmt = stmt.where(ScanSpineTickRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanSpineTickRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanSpineTickRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanSpineTickRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanSpineTickRun.created_at).desc(), col(ScanSpineTickRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_spine_tick_evidence_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    spine_tick_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanSpineTickEvidenceListResponse:
    limit, offset = clamp_scan_spine_tick_pagination(limit=limit, offset=offset)
    stmt = select(ScanSpineTickEvidence).join(
        ScanSpineTickRun,
        ScanSpineTickRun.id == ScanSpineTickEvidence.spine_tick_run_id,
    ).where(ScanSpineTickEvidence.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanSpineTickEvidence).join(
        ScanSpineTickRun,
        ScanSpineTickRun.id == ScanSpineTickEvidence.spine_tick_run_id,
    ).where(ScanSpineTickEvidence.owner_user_id == owner_user_id)
    if spine_tick_run_id is not None:
        stmt = stmt.where(ScanSpineTickEvidence.spine_tick_run_id == spine_tick_run_id)
        count_stmt = count_stmt.where(ScanSpineTickEvidence.spine_tick_run_id == spine_tick_run_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanSpineTickRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanSpineTickRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanSpineTickEvidence.tick_rank), col(ScanSpineTickEvidence.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanSpineTickEvidenceListResponse(
        items=[ScanSpineTickEvidenceRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        severity_hint_counts={key: sum(1 for row in rows if row.severity_hint == key) for key in sorted({row.severity_hint for row in rows})},
        low_confidence_count=sum(1 for row in rows if float(row.confidence_score) < _LOW_CONFIDENCE_THRESHOLD),
    )


def list_scan_spine_tick_issues_owner(
    session: Session,
    *,
    owner_user_id: int,
    spine_tick_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanSpineTickIssueListResponse:
    limit, offset = clamp_scan_spine_tick_pagination(limit=limit, offset=offset)
    stmt = select(ScanSpineTickIssue).where(ScanSpineTickIssue.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanSpineTickIssue).where(ScanSpineTickIssue.owner_user_id == owner_user_id)
    if spine_tick_run_id is not None:
        stmt = stmt.where(ScanSpineTickIssue.spine_tick_run_id == spine_tick_run_id)
        count_stmt = count_stmt.where(ScanSpineTickIssue.spine_tick_run_id == spine_tick_run_id)
    rows = session.exec(stmt.order_by(col(ScanSpineTickIssue.created_at), col(ScanSpineTickIssue.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanSpineTickIssueListResponse(
        items=[ScanSpineTickIssueRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        issue_type_counts={key: sum(1 for row in rows if row.issue_type == key) for key in sorted({row.issue_type for row in rows})},
    )


def list_scan_spine_tick_issues_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanSpineTickIssueListResponse:
    limit, offset = clamp_scan_spine_tick_pagination(limit=limit, offset=offset)
    stmt = select(ScanSpineTickIssue)
    count_stmt = select(func.count()).select_from(ScanSpineTickIssue)
    if owner_user_id is not None:
        stmt = stmt.where(ScanSpineTickIssue.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanSpineTickIssue.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanSpineTickIssue.created_at), col(ScanSpineTickIssue.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanSpineTickIssueListResponse(
        items=[ScanSpineTickIssueRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        issue_type_counts={key: sum(1 for row in rows if row.issue_type == key) for key in sorted({row.issue_type for row in rows})},
    )


def list_scan_spine_tick_failures_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanSpineTickFailureListResponse:
    limit, offset = clamp_scan_spine_tick_pagination(limit=limit, offset=offset)
    stmt = select(ScanSpineTickRun).where(ScanSpineTickRun.detection_status == "FAILED")
    count_stmt = select(func.count()).select_from(ScanSpineTickRun).where(ScanSpineTickRun.detection_status == "FAILED")
    if owner_user_id is not None:
        stmt = stmt.where(ScanSpineTickRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanSpineTickRun.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanSpineTickRun.created_at).desc(), col(ScanSpineTickRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanSpineTickFailureListResponse(
        items=[ScanSpineTickRunRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )
