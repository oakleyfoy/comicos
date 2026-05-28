from __future__ import annotations

import base64
import hashlib
import io
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError
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
    ScanStructuralDamageArtifact,
    ScanStructuralDamageEvidence,
    ScanStructuralDamageHistory,
    ScanStructuralDamageIssue,
    ScanStructuralDamageRun,
)
from app.schemas.scan_structural_damage import (
    ScanStructuralDamageArtifactRead,
    ScanStructuralDamageEvidenceListResponse,
    ScanStructuralDamageEvidenceRead,
    ScanStructuralDamageFailureListResponse,
    ScanStructuralDamageHistoryRead,
    ScanStructuralDamageIssueListResponse,
    ScanStructuralDamageIssueRead,
    ScanStructuralDamageRunCreate,
    ScanStructuralDamageRunDetail,
    ScanStructuralDamageRunListResponse,
    ScanStructuralDamageRunRead,
)
from app.services.scan_defects import _load_source_preview, _resolve_normalization_artifact_path

ENGINE_VERSION = "P40-10-v1"
_PREVIEW_MAX = 420
_LOW_CONFIDENCE_THRESHOLD = 0.35

REQUIRED_REGION_ORDER = (
    "FULL_COVER",
    "SPINE_REGION",
    "CENTER_SURFACE",
    "TOP_EDGE",
    "BOTTOM_EDGE",
    "LEFT_EDGE",
    "RIGHT_EDGE",
)
OPTIONAL_REGION_ORDER = ("STAPLE_ZONE_TOP", "STAPLE_ZONE_BOTTOM", "TITLE_AREA")
ALL_REGION_ORDER = REQUIRED_REGION_ORDER + OPTIONAL_REGION_ORDER


@dataclass(frozen=True)
class _AnalysisRegion:
    region_type: str
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    width_px: int
    height_px: int
    region_checksum: str
    inferred: bool
    metadata_json: dict[str, Any]
    crop: Image.Image


@dataclass(frozen=True)
class _EvidenceDraft:
    region_type: str
    evidence_type: str
    evidence_category: str
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    width_px: int
    height_px: int
    structural_area_ratio: float
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
    from app.models.scan_structural_damage import utc_now as _utc_now

    return _utc_now()


def clamp_scan_structural_damage_pagination(*, limit: int, offset: int) -> tuple[int, int]:
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


def _resolve_structural_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.scan_structural_damage_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("scan structural damage storage path escapes configured root")
    return target


def _artifact_storage_path(
    *,
    owner_user_id: int,
    scan_image_id: int,
    structural_damage_run_id: int,
    artifact_type: str,
    ext: str,
) -> str:
    safe_type = artifact_type.lower()
    return f"scan-structural-damage/{owner_user_id}/{scan_image_id}/{structural_damage_run_id}/{safe_type}{ext}".replace("\\", "/")


def _save_artifact_bytes(settings: Settings, *, relative_path: str, body: bytes) -> None:
    target = _resolve_structural_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)


def _artifact_preview_data_url(settings: Settings, row: ScanStructuralDamageArtifact) -> str | None:
    if not row.storage_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        return None
    try:
        body = _resolve_structural_storage_path(settings, row.storage_path).read_bytes()
    except OSError:
        return None
    return f"data:image/png;base64,{base64.b64encode(body).decode('ascii')}"


def _image_to_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image.copy()
    return image.convert("RGB")


def _serialize_json_artifact(payload: Any) -> bytes:
    return json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"), indent=2).encode("utf-8")


def _minimal_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (12, 12, 16)).save(buf, format="PNG")
    return buf.getvalue()


def _region_index(region_type: str) -> int:
    return ALL_REGION_ORDER.index(region_type)


def _build_region(
    *,
    image: Image.Image,
    region_type: str,
    x_min: int,
    y_min: int,
    x_max: int,
    y_max: int,
    inferred: bool,
    metadata_json: dict[str, Any],
    checksum_seed: str,
) -> _AnalysisRegion:
    crop = image.crop((x_min, y_min, x_max + 1, y_max + 1))
    checksum = _hash_payload(
        {
            "seed": checksum_seed,
            "region_type": region_type,
            "bbox": [x_min, y_min, x_max, y_max],
            "inferred": inferred,
            "metadata_json": metadata_json,
        }
    )
    return _AnalysisRegion(
        region_type=region_type,
        x_min=x_min,
        y_min=y_min,
        x_max=x_max,
        y_max=y_max,
        width_px=max(1, x_max - x_min + 1),
        height_px=max(1, y_max - y_min + 1),
        region_checksum=checksum,
        inferred=inferred,
        metadata_json=metadata_json,
        crop=crop,
    )


def isolate_structural_regions(
    *,
    image: Image.Image,
    regions: list[ScanDefectRegion],
) -> tuple[dict[str, _AnalysisRegion], dict[str, _AnalysisRegion]]:
    region_map = {row.region_type: row for row in regions}
    required: dict[str, _AnalysisRegion] = {}
    optional: dict[str, _AnalysisRegion] = {}
    rgb = _image_to_rgb(image)

    for region_type in REQUIRED_REGION_ORDER:
        row = region_map.get(region_type)
        if row is None:
            continue
        required[region_type] = _build_region(
            image=rgb,
            region_type=region_type,
            x_min=row.x_min,
            y_min=row.y_min,
            x_max=row.x_max,
            y_max=row.y_max,
            inferred=False,
            metadata_json={"source": "p40-06-region", "region_id": row.id},
            checksum_seed=row.region_checksum,
        )

    title_area = region_map.get("TITLE_AREA")
    if title_area is not None:
        optional["TITLE_AREA"] = _build_region(
            image=rgb,
            region_type="TITLE_AREA",
            x_min=title_area.x_min,
            y_min=title_area.y_min,
            x_max=title_area.x_max,
            y_max=title_area.y_max,
            inferred=False,
            metadata_json={"source": "p40-06-region", "region_id": title_area.id},
            checksum_seed=title_area.region_checksum,
        )

    full_cover = required.get("FULL_COVER")
    spine = required.get("SPINE_REGION")
    if full_cover is not None and spine is not None:
        staple_width = min(max(spine.width_px + 6, 12), max(12, full_cover.width_px // 6))
        staple_height = max(16, full_cover.height_px // 10)
        staple_x_center = (spine.x_min + spine.x_max) // 2
        x_min = max(full_cover.x_min, staple_x_center - staple_width // 2)
        x_max = min(full_cover.x_max, x_min + staple_width - 1)
        top_anchor_y = full_cover.y_min + max(10, full_cover.height_px // 8)
        bottom_anchor_y = full_cover.y_max - max(10, full_cover.height_px // 8) - staple_height + 1
        optional["STAPLE_ZONE_TOP"] = _build_region(
            image=rgb,
            region_type="STAPLE_ZONE_TOP",
            x_min=x_min,
            y_min=max(full_cover.y_min, top_anchor_y),
            x_max=x_max,
            y_max=min(full_cover.y_max, max(full_cover.y_min, top_anchor_y) + staple_height - 1),
            inferred=True,
            metadata_json={"source": "inferred-from-spine", "spine_region_checksum": spine.region_checksum},
            checksum_seed=spine.region_checksum,
        )
        optional["STAPLE_ZONE_BOTTOM"] = _build_region(
            image=rgb,
            region_type="STAPLE_ZONE_BOTTOM",
            x_min=x_min,
            y_min=max(full_cover.y_min, bottom_anchor_y),
            x_max=x_max,
            y_max=min(full_cover.y_max, max(full_cover.y_min, bottom_anchor_y) + staple_height - 1),
            inferred=True,
            metadata_json={"source": "inferred-from-spine", "spine_region_checksum": spine.region_checksum},
            checksum_seed=spine.region_checksum,
        )

    return required, optional


def _region_overlap_payload(
    *,
    x_min: int,
    y_min: int,
    x_max: int,
    y_max: int,
    regions: dict[str, _AnalysisRegion],
) -> dict[str, float]:
    area = max(1, (x_max - x_min + 1) * (y_max - y_min + 1))
    overlaps: dict[str, float] = {}
    for region_type, region in regions.items():
        ox0 = max(x_min, region.x_min)
        oy0 = max(y_min, region.y_min)
        ox1 = min(x_max, region.x_max)
        oy1 = min(y_max, region.y_max)
        if ox1 < ox0 or oy1 < oy0:
            continue
        overlaps[region_type] = round(((ox1 - ox0 + 1) * (oy1 - oy0 + 1)) / area, 6)
    return overlaps


def _distance_from_spine(*, spine: _AnalysisRegion | None, x_min: int, x_max: int) -> int:
    if spine is None:
        return 0
    if x_max < spine.x_min:
        return spine.x_min - x_max
    if x_min > spine.x_max:
        return x_min - spine.x_max
    return 0


def _staple_zone_proximity(*, staple_regions: dict[str, _AnalysisRegion], x_min: int, y_min: int, x_max: int, y_max: int) -> int:
    if not staple_regions:
        return 0
    center_x = (x_min + x_max) // 2
    center_y = (y_min + y_max) // 2
    distances: list[int] = []
    for region in staple_regions.values():
        region_center_x = (region.x_min + region.x_max) // 2
        region_center_y = (region.y_min + region.y_max) // 2
        distances.append(abs(center_x - region_center_x) + abs(center_y - region_center_y))
    return min(distances) if distances else 0


def _overlap_defect_evidence(
    *,
    defect_evidence: list[ScanDefectEvidence],
    x_min: int,
    y_min: int,
    x_max: int,
    y_max: int,
) -> int | None:
    best_id: int | None = None
    best_overlap = 0.0
    area = max(1, (x_max - x_min + 1) * (y_max - y_min + 1))
    for row in defect_evidence:
        if row.evidence_category not in {"SURFACE_ANOMALY", "EDGE_ANOMALY", "SPINE_ANOMALY", "CORNER_ANOMALY"}:
            continue
        ox0 = max(x_min, row.x_min)
        oy0 = max(y_min, row.y_min)
        ox1 = min(x_max, row.x_max)
        oy1 = min(y_max, row.y_max)
        if ox1 < ox0 or oy1 < oy0:
            continue
        overlap = ((ox1 - ox0 + 1) * (oy1 - oy0 + 1)) / area
        if overlap > best_overlap:
            best_overlap = overlap
            best_id = int(row.id or 0)
    return best_id


def _scan_axis_segments(region: _AnalysisRegion, axis: str) -> list[tuple[int, int, float]]:
    gray = region.crop.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    scores: list[float] = []
    if axis == "horizontal":
        for y in range(region.crop.height):
            stat = ImageStat.Stat(edges.crop((0, y, region.crop.width, y + 1)))
            scores.append(float(stat.mean[0]) if stat.mean else 0.0)
    else:
        for x in range(region.crop.width):
            stat = ImageStat.Stat(edges.crop((x, 0, x + 1, region.crop.height)))
            scores.append(float(stat.mean[0]) if stat.mean else 0.0)
    if not scores:
        return []
    ordered = sorted(scores)
    median = ordered[len(ordered) // 2]
    threshold = median + max(6.0, median * 0.28)
    segments: list[tuple[int, int, float]] = []
    start: int | None = None
    peak = 0.0
    for idx, score in enumerate(scores):
        if score >= threshold:
            if start is None:
                start = idx
                peak = score
            else:
                peak = max(peak, score)
        elif start is not None:
            segments.append((start, idx - 1, peak))
            start = None
            peak = 0.0
    if start is not None:
        segments.append((start, len(scores) - 1, peak))
    return segments


def _classify_line_evidence(*, region_type: str, axis: str, span_ratio: float) -> tuple[str, str]:
    if region_type in {"SPINE_REGION", "CENTER_SURFACE"} and span_ratio >= 0.45:
        return "MAJOR_CREASE", "STRUCTURAL_ANOMALY"
    if axis == "vertical" and region_type == "SPINE_REGION":
        return "STRUCTURAL_BEND", "GEOMETRY_ANOMALY"
    if span_ratio >= 0.32:
        return "FOLD_LINE", "SURFACE_DEFORMATION"
    return "LARGE_SURFACE_DEFORMATION", "SURFACE_DEFORMATION"


def _classify_edge_evidence(*, region_type: str, warp_signal: float, tear_signal: float, alignment_signal: float) -> tuple[str, str]:
    if tear_signal >= 0.22:
        return "TEAR_LIKE_DISCONTINUITY", "EDGE_DISCONTINUITY"
    if alignment_signal >= 0.2:
        return "COVER_OFFSET_ANOMALY", "ALIGNMENT_ANOMALY"
    if region_type in {"LEFT_EDGE", "RIGHT_EDGE"} and warp_signal >= 0.18:
        return "COVER_CURL", "SURFACE_DEFORMATION"
    return "COVER_WARP", "GEOMETRY_ANOMALY"


def _severity_hint(normalized_size: float, signal_strength: float) -> str:
    score = normalized_size * 0.45 + signal_strength * 0.55
    if score >= 0.24:
        return "MAJOR"
    if score >= 0.11:
        return "MODERATE"
    return "MINOR"


def _confidence_score(measurements: dict[str, Any]) -> float:
    return round(
        min(
            1.0,
            max(
                0.05,
                float(measurements["alignment_delta"]) * 0.18
                + float(measurements["contour_shift_magnitude"]) * 0.18
                + float(measurements["warp_curl_variance"]) * 0.18
                + min(1.0, float(measurements["line_length"]) / 300.0) * 0.22
                + float(measurements["normalized_relative_size"]) * 0.24,
            ),
        ),
        6,
    )


def calculate_structural_measurements(
    *,
    local_box: tuple[int, int, int, int],
    region: _AnalysisRegion,
    full_cover: _AnalysisRegion | None,
    spine: _AnalysisRegion | None,
    staple_regions: dict[str, _AnalysisRegion],
    major_regions: dict[str, _AnalysisRegion],
    edge_stat_mean: float,
    local_brightness: float,
    baseline_brightness: float,
    baseline_stddev: float,
    baseline_edge: float,
    deformation_angle: float,
) -> dict[str, Any]:
    lx0, ly0, lx1, ly1 = local_box
    pixel_area = max(1, (lx1 - lx0) * (ly1 - ly0))
    line_length = max(lx1 - lx0, ly1 - ly0)
    line_curvature = 0.0 if lx1 - lx0 == 0 or ly1 - ly0 == 0 else round(abs((lx1 - lx0) - (ly1 - ly0)) / max(1, line_length), 6)
    edge_displacement = abs(local_brightness - baseline_brightness) / 128.0
    alignment_delta = abs(edge_stat_mean - baseline_edge) / max(1.0, baseline_edge + 6.0)
    contour_shift = abs(edge_stat_mean - baseline_edge) / max(1.0, baseline_edge + 10.0)
    warp_curl_variance = abs(edge_stat_mean - baseline_stddev) / max(1.0, baseline_stddev + 6.0)
    abs_x_min = region.x_min + lx0
    abs_y_min = region.y_min + ly0
    abs_x_max = region.x_min + lx1 - 1
    abs_y_max = region.y_min + ly1 - 1
    overlap_regions = _region_overlap_payload(
        x_min=abs_x_min,
        y_min=abs_y_min,
        x_max=abs_x_max,
        y_max=abs_y_max,
        regions=major_regions,
    )
    return {
        "pixel_area": pixel_area,
        "structural_area_ratio": round(pixel_area / max(1, region.width_px * region.height_px), 6),
        "line_length": line_length,
        "line_curvature": line_curvature,
        "deformation_angle": round(deformation_angle, 6),
        "edge_displacement": round(edge_displacement, 6),
        "alignment_delta": round(alignment_delta, 6),
        "contour_shift_magnitude": round(contour_shift, 6),
        "staple_zone_proximity": _staple_zone_proximity(
            staple_regions=staple_regions,
            x_min=abs_x_min,
            y_min=abs_y_min,
            x_max=abs_x_max,
            y_max=abs_y_max,
        ),
        "warp_curl_variance": round(warp_curl_variance, 6),
        "normalized_relative_size": round(pixel_area / max(1, (full_cover.width_px * full_cover.height_px) if full_cover else pixel_area), 6),
        "distance_from_spine": _distance_from_spine(spine=spine, x_min=abs_x_min, x_max=abs_x_max),
        "overlap_with_major_regions": overlap_regions,
        "raw_edge_energy": round(edge_stat_mean, 6),
    }


def detect_structural_anomalies(
    *,
    required_regions: dict[str, _AnalysisRegion],
    optional_regions: dict[str, _AnalysisRegion],
    defect_evidence: list[ScanDefectEvidence],
) -> list[_EvidenceDraft]:
    drafts: list[_EvidenceDraft] = []
    full_cover = required_regions.get("FULL_COVER")
    spine = required_regions.get("SPINE_REGION")
    staple_regions = {k: v for k, v in optional_regions.items() if k.startswith("STAPLE_ZONE_")}
    major_regions = {**required_regions, **{k: v for k, v in optional_regions.items() if k == "TITLE_AREA"}}

    for region_type in ("FULL_COVER", "CENTER_SURFACE", "SPINE_REGION"):
        region = required_regions.get(region_type)
        if region is None:
            continue
        gray = region.crop.convert("L")
        gray_stat = ImageStat.Stat(gray)
        baseline_brightness = float(gray_stat.mean[0]) if gray_stat.mean else 0.0
        baseline_stddev = float(gray_stat.stddev[0]) if gray_stat.stddev else 0.0
        baseline_edge = float(ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0])
        for axis in ("horizontal", "vertical"):
            segments = _scan_axis_segments(region, axis)
            for start, end, peak in segments:
                span_ratio = (end - start + 1) / max(1, region.height_px if axis == "horizontal" else region.width_px)
                if span_ratio < 0.08:
                    continue
                if axis == "horizontal":
                    ly0 = max(0, start - 1)
                    ly1 = min(region.height_px, end + 2)
                    lx0, lx1 = 0, region.width_px
                    angle = 0.0
                else:
                    lx0 = max(0, start - 1)
                    lx1 = min(region.width_px, end + 2)
                    ly0, ly1 = 0, region.height_px
                    angle = 90.0
                measurements = calculate_structural_measurements(
                    local_box=(lx0, ly0, lx1, ly1),
                    region=region,
                    full_cover=full_cover,
                    spine=spine,
                    staple_regions=staple_regions,
                    major_regions=major_regions,
                    edge_stat_mean=peak,
                    local_brightness=peak,
                    baseline_brightness=baseline_brightness,
                    baseline_stddev=baseline_stddev,
                    baseline_edge=baseline_edge,
                    deformation_angle=angle,
                )
                evidence_type, evidence_category = _classify_line_evidence(region_type=region_type, axis=axis, span_ratio=span_ratio)
                confidence = _confidence_score(measurements)
                severity = _severity_hint(float(measurements["normalized_relative_size"]), min(1.0, span_ratio + float(measurements["alignment_delta"])))
                abs_x_min = region.x_min + lx0
                abs_y_min = region.y_min + ly0
                abs_x_max = region.x_min + lx1 - 1
                abs_y_max = region.y_min + ly1 - 1
                drafts.append(
                    _EvidenceDraft(
                        region_type=region_type,
                        evidence_type=evidence_type,
                        evidence_category=evidence_category,
                        x_min=abs_x_min,
                        y_min=abs_y_min,
                        x_max=abs_x_max,
                        y_max=abs_y_max,
                        width_px=max(1, abs_x_max - abs_x_min + 1),
                        height_px=max(1, abs_y_max - abs_y_min + 1),
                        structural_area_ratio=float(measurements["structural_area_ratio"]),
                        confidence_score=confidence,
                        severity_hint=severity,
                        measurement_json=measurements,
                        metadata_json={"axis": axis, "span_ratio": round(span_ratio, 6)},
                        defect_evidence_id=_overlap_defect_evidence(
                            defect_evidence=defect_evidence,
                            x_min=abs_x_min,
                            y_min=abs_y_min,
                            x_max=abs_x_max,
                            y_max=abs_y_max,
                        ),
                    )
                )

    for region_type in ("TOP_EDGE", "BOTTOM_EDGE", "LEFT_EDGE", "RIGHT_EDGE"):
        region = required_regions.get(region_type)
        if region is None:
            continue
        gray = region.crop.convert("L")
        edge_image = gray.filter(ImageFilter.FIND_EDGES)
        base_stat = ImageStat.Stat(gray)
        edge_stat = ImageStat.Stat(edge_image)
        brightness = float(base_stat.mean[0]) if base_stat.mean else 0.0
        stddev = float(base_stat.stddev[0]) if base_stat.stddev else 0.0
        edge_mean = float(edge_stat.mean[0]) if edge_stat.mean else 0.0
        outer_band = gray.crop((0, 0, region.width_px, max(1, region.height_px // 3))) if region_type == "TOP_EDGE" else (
            gray.crop((0, max(0, region.height_px - max(1, region.height_px // 3)), region.width_px, region.height_px))
            if region_type == "BOTTOM_EDGE"
            else gray.crop((0, 0, max(1, region.width_px // 3), region.height_px))
            if region_type == "LEFT_EDGE"
            else gray.crop((max(0, region.width_px - max(1, region.width_px // 3)), 0, region.width_px, region.height_px))
        )
        outer_mean = float(ImageStat.Stat(outer_band).mean[0]) if ImageStat.Stat(outer_band).mean else brightness
        warp_signal = abs(outer_mean - brightness) / 128.0
        tear_signal = abs(edge_mean - stddev) / max(1.0, stddev + 6.0)
        alignment_signal = abs(edge_mean - brightness) / 128.0
        if max(warp_signal, tear_signal, alignment_signal) < 0.08:
            continue
        evidence_type, evidence_category = _classify_edge_evidence(
            region_type=region_type,
            warp_signal=warp_signal,
            tear_signal=tear_signal,
            alignment_signal=alignment_signal,
        )
        if region_type in {"TOP_EDGE", "BOTTOM_EDGE"}:
            local_box = (0, 0, region.width_px, max(8, region.height_px // 2))
            angle = 0.0
        else:
            local_box = (0, 0, max(8, region.width_px // 2), region.height_px)
            angle = 90.0
        measurements = calculate_structural_measurements(
            local_box=local_box,
            region=region,
            full_cover=full_cover,
            spine=spine,
            staple_regions=staple_regions,
            major_regions=major_regions,
            edge_stat_mean=edge_mean,
            local_brightness=outer_mean,
            baseline_brightness=brightness,
            baseline_stddev=stddev,
            baseline_edge=edge_mean,
            deformation_angle=angle,
        )
        confidence = _confidence_score(measurements)
        severity = _severity_hint(float(measurements["normalized_relative_size"]), min(1.0, max(warp_signal, tear_signal, alignment_signal)))
        abs_x_min = region.x_min + local_box[0]
        abs_y_min = region.y_min + local_box[1]
        abs_x_max = region.x_min + local_box[2] - 1
        abs_y_max = region.y_min + local_box[3] - 1
        drafts.append(
            _EvidenceDraft(
                region_type=region_type,
                evidence_type=evidence_type,
                evidence_category=evidence_category,
                x_min=abs_x_min,
                y_min=abs_y_min,
                x_max=abs_x_max,
                y_max=abs_y_max,
                width_px=max(1, abs_x_max - abs_x_min + 1),
                height_px=max(1, abs_y_max - abs_y_min + 1),
                structural_area_ratio=float(measurements["structural_area_ratio"]),
                confidence_score=confidence,
                severity_hint=severity,
                measurement_json=measurements,
                metadata_json={
                    "warp_signal": round(warp_signal, 6),
                    "tear_signal": round(tear_signal, 6),
                    "alignment_signal": round(alignment_signal, 6),
                },
                defect_evidence_id=_overlap_defect_evidence(
                    defect_evidence=defect_evidence,
                    x_min=abs_x_min,
                    y_min=abs_y_min,
                    x_max=abs_x_max,
                    y_max=abs_y_max,
                ),
            )
        )

    if full_cover is not None and required_regions.get("TOP_EDGE") and required_regions.get("BOTTOM_EDGE"):
        top_edge = required_regions["TOP_EDGE"]
        bottom_edge = required_regions["BOTTOM_EDGE"]
        top_mean = float(ImageStat.Stat(top_edge.crop.convert("L")).mean[0])
        bottom_mean = float(ImageStat.Stat(bottom_edge.crop.convert("L")).mean[0])
        alignment_delta = abs(top_mean - bottom_mean) / 128.0
        if alignment_delta >= 0.08:
            local_box = (0, 0, full_cover.width_px, max(24, full_cover.height_px // 6))
            measurements = calculate_structural_measurements(
                local_box=local_box,
                region=full_cover,
                full_cover=full_cover,
                spine=spine,
                staple_regions=staple_regions,
                major_regions=major_regions,
                edge_stat_mean=alignment_delta * 128.0,
                local_brightness=top_mean,
                baseline_brightness=bottom_mean,
                baseline_stddev=float(ImageStat.Stat(full_cover.crop.convert("L")).stddev[0]),
                baseline_edge=float(ImageStat.Stat(full_cover.crop.convert("L").filter(ImageFilter.FIND_EDGES)).mean[0]),
                deformation_angle=0.0,
            )
            drafts.append(
                _EvidenceDraft(
                    region_type="FULL_COVER",
                    evidence_type="STRUCTURAL_ALIGNMENT_SHIFT" if alignment_delta < 0.18 else "COVER_OFFSET_ANOMALY",
                    evidence_category="ALIGNMENT_ANOMALY",
                    x_min=full_cover.x_min,
                    y_min=full_cover.y_min,
                    x_max=full_cover.x_max,
                    y_max=min(full_cover.y_max, full_cover.y_min + local_box[3] - 1),
                    width_px=full_cover.width_px,
                    height_px=local_box[3],
                    structural_area_ratio=float(measurements["structural_area_ratio"]),
                    confidence_score=_confidence_score(measurements),
                    severity_hint=_severity_hint(float(measurements["normalized_relative_size"]), min(1.0, alignment_delta)),
                    measurement_json=measurements,
                    metadata_json={"top_bottom_alignment_delta": round(alignment_delta, 6)},
                    defect_evidence_id=None,
                )
            )

    for staple_name in ("STAPLE_ZONE_TOP", "STAPLE_ZONE_BOTTOM"):
        region = optional_regions.get(staple_name)
        if region is None:
            continue
        gray = region.crop.convert("L")
        edge_mean = float(ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0])
        brightness = float(ImageStat.Stat(gray).mean[0])
        stress_signal = abs(edge_mean - brightness) / 128.0
        if stress_signal < 0.09:
            continue
        measurements = calculate_structural_measurements(
            local_box=(0, 0, region.width_px, region.height_px),
            region=region,
            full_cover=full_cover,
            spine=spine,
            staple_regions=staple_regions,
            major_regions=major_regions,
            edge_stat_mean=edge_mean,
            local_brightness=brightness,
            baseline_brightness=brightness,
            baseline_stddev=float(ImageStat.Stat(gray).stddev[0]),
            baseline_edge=edge_mean,
            deformation_angle=90.0,
        )
        drafts.append(
            _EvidenceDraft(
                region_type=staple_name,
                evidence_type="STAPLE_REGION_STRESS",
                evidence_category="STRUCTURAL_ANOMALY",
                x_min=region.x_min,
                y_min=region.y_min,
                x_max=region.x_max,
                y_max=region.y_max,
                width_px=region.width_px,
                height_px=region.height_px,
                structural_area_ratio=float(measurements["structural_area_ratio"]),
                confidence_score=_confidence_score(measurements),
                severity_hint=_severity_hint(float(measurements["normalized_relative_size"]), min(1.0, stress_signal)),
                measurement_json=measurements,
                metadata_json={"inferred_region": region.inferred, "stress_signal": round(stress_signal, 6)},
                defect_evidence_id=_overlap_defect_evidence(
                    defect_evidence=defect_evidence,
                    x_min=region.x_min,
                    y_min=region.y_min,
                    x_max=region.x_max,
                    y_max=region.y_max,
                ),
            )
        )

    return drafts


def segment_structural_evidence(drafts: list[_EvidenceDraft]) -> list[_EvidenceDraft]:
    ordered = sorted(
        drafts,
        key=lambda row: (
            _region_index(row.region_type),
            row.y_min,
            row.x_min,
            row.evidence_category,
            row.evidence_type,
        ),
    )
    ranked: list[_EvidenceDraft] = []
    for rank, row in enumerate(ordered, start=1):
        ranked.append(
            _EvidenceDraft(
                region_type=row.region_type,
                evidence_type=row.evidence_type,
                evidence_category=row.evidence_category,
                x_min=row.x_min,
                y_min=row.y_min,
                x_max=row.x_max,
                y_max=row.y_max,
                width_px=row.width_px,
                height_px=row.height_px,
                structural_area_ratio=row.structural_area_ratio,
                confidence_score=row.confidence_score,
                severity_hint=row.severity_hint,
                measurement_json={**row.measurement_json, "evidence_rank": rank},
                metadata_json={**row.metadata_json, "evidence_rank": rank},
                defect_evidence_id=row.defect_evidence_id,
            )
        )
    return ranked


def build_structural_damage_manifest(
    *,
    defect_run: ScanDefectRun,
    required_regions: dict[str, _AnalysisRegion],
    optional_regions: dict[str, _AnalysisRegion],
    evidence: list[_EvidenceDraft],
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
        "required_regions": [
            {
                "region_type": key,
                "region_checksum": required_regions[key].region_checksum,
                "bbox": [required_regions[key].x_min, required_regions[key].y_min, required_regions[key].x_max, required_regions[key].y_max],
                "metadata_json": required_regions[key].metadata_json,
            }
            for key in REQUIRED_REGION_ORDER
            if key in required_regions
        ],
        "optional_regions": [
            {
                "region_type": key,
                "region_checksum": optional_regions[key].region_checksum,
                "bbox": [optional_regions[key].x_min, optional_regions[key].y_min, optional_regions[key].x_max, optional_regions[key].y_max],
                "inferred": optional_regions[key].inferred,
                "metadata_json": optional_regions[key].metadata_json,
            }
            for key in OPTIONAL_REGION_ORDER
            if key in optional_regions
        ],
        "evidence": [
            {
                "evidence_rank": int(row.measurement_json.get("evidence_rank") or idx + 1),
                "evidence_type": row.evidence_type,
                "evidence_category": row.evidence_category,
                "region_type": row.region_type,
                "bbox": [row.x_min, row.y_min, row.x_max, row.y_max],
                "confidence_score": row.confidence_score,
                "severity_hint": row.severity_hint,
                "measurement_json": row.measurement_json,
                "defect_evidence_id": row.defect_evidence_id,
            }
            for idx, row in enumerate(evidence)
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
            "total_evidence_count": len(evidence),
            "low_confidence_count": sum(1 for row in evidence if row.confidence_score < _LOW_CONFIDENCE_THRESHOLD),
            "major_count": sum(1 for row in evidence if row.severity_hint == "MAJOR"),
            "category_counts": {
                key: sum(1 for row in evidence if row.evidence_category == key)
                for key in sorted({row.evidence_category for row in evidence})
            },
        },
    }
    return manifest, _hash_payload(manifest)


def _build_region_montage(regions: dict[str, _AnalysisRegion], order: tuple[str, ...]) -> bytes:
    tiles = [regions[key].crop.copy() for key in order if key in regions]
    if not tiles:
        return _minimal_png()
    tile_w = max(tile.width for tile in tiles)
    tile_h = max(tile.height for tile in tiles)
    cols = 2 if len(tiles) > 1 else 1
    rows = (len(tiles) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * tile_w, rows * tile_h), (18, 18, 24))
    for idx, tile in enumerate(tiles):
        tile.thumbnail((tile_w, tile_h))
        canvas.paste(tile, ((idx % cols) * tile_w, (idx // cols) * tile_h))
    canvas.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def _build_deformation_map(required_regions: dict[str, _AnalysisRegion], optional_regions: dict[str, _AnalysisRegion]) -> bytes:
    center = required_regions.get("CENTER_SURFACE") or required_regions.get("FULL_COVER")
    if center is None:
        return _minimal_png()
    gray = center.crop.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    solar = ImageOps.solarize(gray, threshold=96)
    rendered = Image.merge("RGB", (edges, solar, gray))
    if "STAPLE_ZONE_TOP" in optional_regions or "STAPLE_ZONE_BOTTOM" in optional_regions:
        draw = ImageDraw.Draw(rendered)
        for name in ("STAPLE_ZONE_TOP", "STAPLE_ZONE_BOTTOM"):
            staple = optional_regions.get(name)
            if staple is None:
                continue
            rel_x0 = staple.x_min - center.x_min
            rel_y0 = staple.y_min - center.y_min
            rel_x1 = staple.x_max - center.x_min
            rel_y1 = staple.y_max - center.y_min
            draw.rectangle((rel_x0, rel_y0, rel_x1, rel_y1), outline="#f59e0b", width=2)
    rendered.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
    buf = io.BytesIO()
    rendered.save(buf, format="PNG")
    return buf.getvalue()


def _build_overlay(image: Image.Image, evidence: list[_EvidenceDraft]) -> bytes:
    rendered = _image_to_rgb(image)
    draw = ImageDraw.Draw(rendered)
    palette = {"MINOR": "#eab308", "MODERATE": "#f97316", "MAJOR": "#ef4444"}
    for row in evidence:
        draw.rectangle((row.x_min, row.y_min, row.x_max, row.y_max), outline=palette.get(row.severity_hint, "#ffffff"), width=2)
    buf = io.BytesIO()
    rendered.save(buf, format="PNG")
    return buf.getvalue()


def _build_debug_preview(image: Image.Image, evidence: list[_EvidenceDraft], optional_regions: dict[str, _AnalysisRegion]) -> bytes:
    rendered = _image_to_rgb(image)
    draw = ImageDraw.Draw(rendered)
    for row in evidence[:16]:
        draw.rectangle((row.x_min, row.y_min, row.x_max, row.y_max), outline="#22d3ee", width=2)
    for name in ("STAPLE_ZONE_TOP", "STAPLE_ZONE_BOTTOM"):
        region = optional_regions.get(name)
        if region is None:
            continue
        draw.rectangle((region.x_min, region.y_min, region.x_max, region.y_max), outline="#f59e0b", width=2)
    rendered.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
    buf = io.BytesIO()
    rendered.save(buf, format="PNG")
    return buf.getvalue()


def _artifact_drafts_for_run(
    *,
    image: Image.Image,
    required_regions: dict[str, _AnalysisRegion],
    optional_regions: dict[str, _AnalysisRegion],
    evidence: list[_EvidenceDraft],
    measurement_export: dict[str, Any],
) -> list[_ArtifactDraft]:
    if not required_regions:
        tiny = _minimal_png()
        return [
            _ArtifactDraft("STRUCTURAL_REGION_PREVIEW", tiny, {"placeholder": True}, ".png"),
            _ArtifactDraft("STRUCTURAL_DEFORMATION_MAP", tiny, {"placeholder": True}, ".png"),
            _ArtifactDraft("STRUCTURAL_DAMAGE_OVERLAY", _build_overlay(image, evidence), {"format": "png"}, ".png"),
            _ArtifactDraft("STRUCTURAL_MEASUREMENT_EXPORT", _serialize_json_artifact(measurement_export), {"format": "json"}, ".json"),
            _ArtifactDraft("STRUCTURAL_DEBUG_PREVIEW", tiny, {"placeholder": True}, ".png"),
        ]
    all_regions = {**required_regions, **optional_regions}
    return [
        _ArtifactDraft(
            "STRUCTURAL_REGION_PREVIEW",
            _build_region_montage(all_regions, ALL_REGION_ORDER),
            {"format": "png", "region_count": len(all_regions)},
            ".png",
        ),
        _ArtifactDraft("STRUCTURAL_DEFORMATION_MAP", _build_deformation_map(required_regions, optional_regions), {"format": "png"}, ".png"),
        _ArtifactDraft(
            "STRUCTURAL_DAMAGE_OVERLAY",
            _build_overlay(image, evidence),
            {"format": "png", "evidence_count": len(evidence)},
            ".png",
        ),
        _ArtifactDraft(
            "STRUCTURAL_MEASUREMENT_EXPORT",
            _serialize_json_artifact(measurement_export),
            {"format": "json", "evidence_count": len(evidence)},
            ".json",
        ),
        _ArtifactDraft("STRUCTURAL_DEBUG_PREVIEW", _build_debug_preview(image, evidence, optional_regions), {"format": "png"}, ".png"),
    ]


def _build_issues(
    *,
    required_regions: dict[str, _AnalysisRegion],
    optional_regions: dict[str, _AnalysisRegion],
    evidence: list[_EvidenceDraft],
    defect_run: ScanDefectRun,
) -> list[_IssueDraft]:
    issues: list[_IssueDraft] = []
    missing_required = [key for key in REQUIRED_REGION_ORDER if key not in required_regions]
    if missing_required:
        issues.append(
            _IssueDraft(
                issue_type="STRUCTURAL_REGION_MISSING",
                severity="ERROR" if len(missing_required) >= 2 else "WARNING",
                issue_message="One or more required structural regions were missing from the defect foundation manifest.",
                metadata_json={"missing_regions": missing_required},
            )
        )
    if not required_regions:
        issues.append(
            _IssueDraft(
                issue_type="STRUCTURAL_DETECTION_FAILED",
                severity="ERROR",
                issue_message="Structural region isolation failed.",
                metadata_json={},
            )
        )
        return issues
    if "STAPLE_ZONE_TOP" not in optional_regions or "STAPLE_ZONE_BOTTOM" not in optional_regions:
        issues.append(
            _IssueDraft(
                issue_type="STAPLE_REGION_UNCERTAIN",
                severity="INFO",
                issue_message="Staple analysis regions could not be fully derived from spine geometry.",
                metadata_json={},
            )
        )
    gray_stats: list[tuple[float, float]] = []
    light_ratios: list[float] = []
    for region in required_regions.values():
        gray = region.crop.convert("L")
        stat = ImageStat.Stat(gray)
        gray_stats.append((float(stat.mean[0]) if stat.mean else 0.0, float(stat.stddev[0]) if stat.stddev else 0.0))
        histogram = gray.histogram()
        total = max(1, region.width_px * region.height_px)
        light_ratios.append(sum(histogram[230:]) / total)
    if light_ratios and sum(light_ratios) / len(light_ratios) > 0.18:
        issues.append(
            _IssueDraft(
                issue_type="EXCESSIVE_GLARE",
                severity="WARNING",
                issue_message="Structural regions show glare that may reduce geometry stability.",
                metadata_json={"mean_light_ratio": round(sum(light_ratios) / len(light_ratios), 6)},
            )
        )
    if gray_stats:
        means = [item[0] for item in gray_stats]
        stddevs = [item[1] for item in gray_stats]
        if max(means) - min(means) > 60:
            issues.append(
                _IssueDraft(
                    issue_type="LOW_ALIGNMENT_CONFIDENCE",
                    severity="INFO",
                    issue_message="Region brightness asymmetry suggests alignment diagnostics may be noisy.",
                    metadata_json={"brightness_spread": round(max(means) - min(means), 6)},
                )
            )
        if sum(stddevs) / len(stddevs) < 14:
            issues.append(
                _IssueDraft(
                    issue_type="GEOMETRY_ANALYSIS_FAILED",
                    severity="INFO",
                    issue_message="Structural edge contrast is low for stable geometry segmentation.",
                    metadata_json={"mean_stddev": round(sum(stddevs) / len(stddevs), 6)},
                )
            )
    if evidence and all(row.confidence_score < _LOW_CONFIDENCE_THRESHOLD for row in evidence):
        issues.append(
            _IssueDraft(
                issue_type="LOW_STRUCTURAL_CONFIDENCE",
                severity="WARNING",
                issue_message="All structural evidence rows remain below the confidence floor.",
                metadata_json={"low_confidence_count": len(evidence)},
            )
        )
    if not evidence:
        issues.append(
            _IssueDraft(
                issue_type="STRUCTURAL_SEGMENTATION_FAILED",
                severity="INFO",
                issue_message="No structural anomalies exceeded the deterministic threshold.",
                metadata_json={"segment_count": 0},
            )
        )
    bg_issues = [
        row
        for row in (defect_run.output_manifest_json.get("issues") or [])
        if isinstance(row, dict) and row.get("issue_type") == "EXCESSIVE_BACKGROUND_ARTIFACTS"
    ]
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


def _resolve_defect_run(session: Session, *, owner_user_id: int, payload: ScanStructuralDamageRunCreate) -> ScanDefectRun:
    stmt = select(ScanDefectRun).where(
        ScanDefectRun.owner_user_id == owner_user_id,
        ScanDefectRun.scan_image_id == payload.scan_image_id,
        ScanDefectRun.defect_status == "COMPLETE",
    )
    if payload.defect_run_id is not None:
        stmt = stmt.where(ScanDefectRun.id == payload.defect_run_id)
    defect_run = session.exec(stmt.order_by(col(ScanDefectRun.id).desc())).first()
    if defect_run is None:
        raise HTTPException(status_code=409, detail="A complete defect foundation run is required before structural damage detection.")
    return defect_run


def _detail_from_run(session: Session, settings: Settings, run: ScanStructuralDamageRun) -> ScanStructuralDamageRunDetail:
    evidence = session.exec(
        select(ScanStructuralDamageEvidence)
        .where(ScanStructuralDamageEvidence.structural_damage_run_id == run.id)
        .order_by(col(ScanStructuralDamageEvidence.evidence_rank), col(ScanStructuralDamageEvidence.id))
    ).all()
    artifacts = session.exec(
        select(ScanStructuralDamageArtifact)
        .where(ScanStructuralDamageArtifact.structural_damage_run_id == run.id)
        .order_by(col(ScanStructuralDamageArtifact.id))
    ).all()
    issues = session.exec(
        select(ScanStructuralDamageIssue)
        .where(ScanStructuralDamageIssue.structural_damage_run_id == run.id)
        .order_by(col(ScanStructuralDamageIssue.id))
    ).all()
    history = session.exec(
        select(ScanStructuralDamageHistory)
        .where(ScanStructuralDamageHistory.structural_damage_run_id == run.id)
        .order_by(col(ScanStructuralDamageHistory.id))
    ).all()
    defect_run = session.get(ScanDefectRun, int(run.defect_run_id))
    source_artifact = session.get(ScanNormalizationArtifact, int(defect_run.source_artifact_id)) if defect_run else None
    art_reads = [
        ScanStructuralDamageArtifactRead.model_validate(row).model_copy(
            update={"preview_data_url": _artifact_preview_data_url(settings, row)}
        )
        for row in artifacts
    ]
    scan_image = session.get(ScanImage, int(run.scan_image_id))
    norm_run = session.get(ScanNormalizationRun, int(defect_run.normalization_run_id)) if defect_run else None
    boundary_run = session.get(ScanBoundaryRun, int(defect_run.boundary_run_id)) if defect_run else None
    run_data = ScanStructuralDamageRunRead.model_validate(run).model_dump()
    return ScanStructuralDamageRunDetail(
        **run_data,
        evidence=[ScanStructuralDamageEvidenceRead.model_validate(row) for row in evidence],
        artifacts=art_reads,
        issues=[ScanStructuralDamageIssueRead.model_validate(row) for row in issues],
        history=[ScanStructuralDamageHistoryRead.model_validate(row) for row in history],
        original_scan_checksum=scan_image.sha256_checksum if scan_image else None,
        normalization_checksum=norm_run.normalization_checksum if norm_run else None,
        boundary_checksum=boundary_run.boundary_checksum if boundary_run else None,
        defect_checksum=defect_run.defect_checksum if defect_run else None,
        source_preview_data_url=_load_source_preview(settings, source_artifact) if source_artifact else None,
        structural_region_preview_data_url=next((a.preview_data_url for a in art_reads if a.artifact_type == "STRUCTURAL_REGION_PREVIEW"), None),
        evidence_summary=dict(run.output_manifest_json.get("evidence_summary") or {}),
    )


def run_scan_structural_damage_detection(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: ScanStructuralDamageRunCreate,
) -> tuple[ScanStructuralDamageRunDetail, bool]:
    defect_run = _resolve_defect_run(session, owner_user_id=owner_user_id, payload=payload)
    source_artifact = session.get(ScanNormalizationArtifact, int(defect_run.source_artifact_id))
    if source_artifact is None:
        raise HTTPException(status_code=409, detail="Defect run is missing its normalized source artifact.")
    defect_regions = session.exec(
        select(ScanDefectRegion).where(ScanDefectRegion.defect_run_id == defect_run.id).order_by(col(ScanDefectRegion.id))
    ).all()
    defect_evidence = session.exec(
        select(ScanDefectEvidence).where(ScanDefectEvidence.defect_run_id == defect_run.id).order_by(col(ScanDefectEvidence.id))
    ).all()
    try:
        with Image.open(_resolve_normalization_artifact_path(settings, source_artifact)) as image_fp:
            image = _image_to_rgb(image_fp)
    except (FileNotFoundError, OSError, ValueError, UnidentifiedImageError) as exc:
        raise HTTPException(status_code=409, detail="Normalized source artifact is not available for structural damage detection.") from exc

    required_regions, optional_regions = isolate_structural_regions(image=image, regions=defect_regions)
    evidence = segment_structural_evidence(
        detect_structural_anomalies(
            required_regions=required_regions,
            optional_regions=optional_regions,
            defect_evidence=defect_evidence,
        )
    )
    issues = _build_issues(required_regions=required_regions, optional_regions=optional_regions, evidence=evidence, defect_run=defect_run)
    measurement_export = {
        "evidence": [
            {
                "evidence_rank": int(row.measurement_json.get("evidence_rank") or 0),
                "evidence_type": row.evidence_type,
                "evidence_category": row.evidence_category,
                "region_type": row.region_type,
                "measurement_json": row.measurement_json,
                "confidence_score": row.confidence_score,
                "severity_hint": row.severity_hint,
            }
            for row in evidence
        ]
    }
    provisional_artifacts = _artifact_drafts_for_run(
        image=image,
        required_regions=required_regions,
        optional_regions=optional_regions,
        evidence=evidence,
        measurement_export=measurement_export,
    )
    provisional_manifest, structural_damage_checksum = build_structural_damage_manifest(
        defect_run=defect_run,
        required_regions=required_regions,
        optional_regions=optional_regions,
        evidence=evidence,
        issues=issues,
        artifact_checksums=[
            {"artifact_type": row.artifact_type, "artifact_checksum": _sha256_bytes(row.body)} for row in provisional_artifacts
        ],
    )
    manifest_artifact = _ArtifactDraft("STRUCTURAL_DAMAGE_MANIFEST", _serialize_json_artifact(provisional_manifest), {"format": "json"}, ".json")
    artifacts = provisional_artifacts + [manifest_artifact]

    existing = session.exec(
        select(ScanStructuralDamageRun).where(
            ScanStructuralDamageRun.owner_user_id == owner_user_id,
            ScanStructuralDamageRun.structural_damage_checksum == structural_damage_checksum,
        )
    ).first()
    if existing is not None:
        return _detail_from_run(session, settings, existing), False

    run = ScanStructuralDamageRun(
        owner_user_id=owner_user_id,
        scan_image_id=int(defect_run.scan_image_id),
        defect_run_id=int(defect_run.id or 0),
        source_checksum=defect_run.source_checksum,
        structural_damage_checksum=structural_damage_checksum,
        detection_status="COMPLETE",
        engine_version=ENGINE_VERSION,
        input_manifest_json={
            "scan_image_id": defect_run.scan_image_id,
            "defect_run_id": defect_run.id,
            "defect_checksum": defect_run.defect_checksum,
            "source_checksum": defect_run.source_checksum,
        },
        output_manifest_json=provisional_manifest,
        completed_at=utc_now(),
    )
    session.add(run)
    session.flush()

    for row in evidence:
        session.add(
            ScanStructuralDamageEvidence(
                owner_user_id=owner_user_id,
                structural_damage_run_id=int(run.id or 0),
                defect_evidence_id=row.defect_evidence_id,
                evidence_rank=int(row.measurement_json.get("evidence_rank") or 0),
                evidence_type=row.evidence_type,
                evidence_category=row.evidence_category,
                confidence_score=row.confidence_score,
                severity_hint=row.severity_hint,
                region_type=row.region_type,
                x_min=row.x_min,
                y_min=row.y_min,
                x_max=row.x_max,
                y_max=row.y_max,
                width_px=row.width_px,
                height_px=row.height_px,
                structural_area_ratio=row.structural_area_ratio,
                measurement_json=row.measurement_json,
                metadata_json=row.metadata_json,
            )
        )
    for row in issues:
        session.add(
            ScanStructuralDamageIssue(
                owner_user_id=owner_user_id,
                structural_damage_run_id=int(run.id or 0),
                issue_type=row.issue_type,
                severity=row.severity,
                issue_message=row.issue_message,
                metadata_json=row.metadata_json,
            )
        )
    history_rows = [
        _HistoryDraft("STRUCTURAL_DAMAGE_RUN_CREATED", "Created deterministic structural damage detection run.", {"structural_damage_checksum": structural_damage_checksum}),
        _HistoryDraft("STRUCTURAL_REGIONS_ISOLATED", "Isolated structural analysis regions from defect foundation geometry.", {"required_region_count": len(required_regions)}),
        _HistoryDraft("STRUCTURAL_EVIDENCE_SEGMENTED", "Segmented probable structural evidence candidates.", {"evidence_count": len(evidence)}),
        _HistoryDraft("STRUCTURAL_DAMAGE_MANIFEST_WRITTEN", "Persisted replay-safe structural damage manifest and artifacts.", {"artifact_count": len(artifacts)}),
    ]
    for row in history_rows:
        session.add(
            ScanStructuralDamageHistory(
                owner_user_id=owner_user_id,
                structural_damage_run_id=int(run.id or 0),
                event_type=row.event_type,
                event_message=row.event_message,
                event_checksum=_hash_payload(
                    {
                        "structural_damage_run_id": int(run.id or 0),
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
            structural_damage_run_id=int(run.id or 0),
            artifact_type=row.artifact_type,
            ext=row.ext,
        )
        _save_artifact_bytes(settings, relative_path=relative_path, body=row.body)
        session.add(
            ScanStructuralDamageArtifact(
                owner_user_id=owner_user_id,
                structural_damage_run_id=int(run.id or 0),
                artifact_type=row.artifact_type,
                storage_path=relative_path,
                artifact_checksum=_sha256_bytes(row.body),
                metadata_json=row.metadata_json,
            )
        )
    session.commit()
    session.refresh(run)
    return _detail_from_run(session, settings, run), True


def get_scan_structural_damage_run_owner(session: Session, settings: Settings, *, owner_user_id: int, run_id: int) -> ScanStructuralDamageRunDetail:
    row = session.get(ScanStructuralDamageRun, run_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Structural damage run not found.")
    return _detail_from_run(session, settings, row)


def get_scan_structural_damage_artifact_owner(session: Session, settings: Settings, *, owner_user_id: int, artifact_id: int) -> ScanStructuralDamageArtifactRead:
    row = session.get(ScanStructuralDamageArtifact, artifact_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Structural damage artifact not found.")
    return ScanStructuralDamageArtifactRead.model_validate(row).model_copy(
        update={"preview_data_url": _artifact_preview_data_url(settings, row)}
    )


def _run_list_response(rows: list[ScanStructuralDamageRun], *, limit: int, offset: int, total_items: int) -> ScanStructuralDamageRunListResponse:
    status_counts = {status: sum(1 for row in rows if row.detection_status == status) for status in sorted({row.detection_status for row in rows})}
    low_confidence = sum(int((row.output_manifest_json.get("evidence_summary") or {}).get("low_confidence_count") or 0) for row in rows)
    major_count = sum(int((row.output_manifest_json.get("evidence_summary") or {}).get("major_count") or 0) for row in rows)
    return ScanStructuralDamageRunListResponse(
        items=[ScanStructuralDamageRunRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        status_counts=status_counts,
        low_confidence_count=low_confidence,
        major_structural_count=major_count,
    )


def list_scan_structural_damage_runs_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanStructuralDamageRunListResponse:
    limit, offset = clamp_scan_structural_damage_pagination(limit=limit, offset=offset)
    stmt = select(ScanStructuralDamageRun).where(ScanStructuralDamageRun.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanStructuralDamageRun).where(ScanStructuralDamageRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanStructuralDamageRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanStructuralDamageRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanStructuralDamageRun.created_at).desc(), col(ScanStructuralDamageRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_structural_damage_runs_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanStructuralDamageRunListResponse:
    limit, offset = clamp_scan_structural_damage_pagination(limit=limit, offset=offset)
    stmt = select(ScanStructuralDamageRun)
    count_stmt = select(func.count()).select_from(ScanStructuralDamageRun)
    if owner_user_id is not None:
        stmt = stmt.where(ScanStructuralDamageRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanStructuralDamageRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanStructuralDamageRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanStructuralDamageRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanStructuralDamageRun.created_at).desc(), col(ScanStructuralDamageRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_structural_damage_evidence_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    structural_damage_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanStructuralDamageEvidenceListResponse:
    limit, offset = clamp_scan_structural_damage_pagination(limit=limit, offset=offset)
    stmt = select(ScanStructuralDamageEvidence).join(
        ScanStructuralDamageRun,
        ScanStructuralDamageRun.id == ScanStructuralDamageEvidence.structural_damage_run_id,
    ).where(ScanStructuralDamageEvidence.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanStructuralDamageEvidence).join(
        ScanStructuralDamageRun,
        ScanStructuralDamageRun.id == ScanStructuralDamageEvidence.structural_damage_run_id,
    ).where(ScanStructuralDamageEvidence.owner_user_id == owner_user_id)
    if structural_damage_run_id is not None:
        stmt = stmt.where(ScanStructuralDamageEvidence.structural_damage_run_id == structural_damage_run_id)
        count_stmt = count_stmt.where(ScanStructuralDamageEvidence.structural_damage_run_id == structural_damage_run_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanStructuralDamageRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanStructuralDamageRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanStructuralDamageEvidence.evidence_rank), col(ScanStructuralDamageEvidence.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanStructuralDamageEvidenceListResponse(
        items=[ScanStructuralDamageEvidenceRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        evidence_type_counts={key: sum(1 for row in rows if row.evidence_type == key) for key in sorted({row.evidence_type for row in rows})},
        evidence_category_counts={key: sum(1 for row in rows if row.evidence_category == key) for key in sorted({row.evidence_category for row in rows})},
        severity_hint_counts={key: sum(1 for row in rows if row.severity_hint == key) for key in sorted({row.severity_hint for row in rows})},
        low_confidence_count=sum(1 for row in rows if float(row.confidence_score) < _LOW_CONFIDENCE_THRESHOLD),
    )


def list_scan_structural_damage_issues_owner(
    session: Session,
    *,
    owner_user_id: int,
    structural_damage_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanStructuralDamageIssueListResponse:
    limit, offset = clamp_scan_structural_damage_pagination(limit=limit, offset=offset)
    stmt = select(ScanStructuralDamageIssue).where(ScanStructuralDamageIssue.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanStructuralDamageIssue).where(ScanStructuralDamageIssue.owner_user_id == owner_user_id)
    if structural_damage_run_id is not None:
        stmt = stmt.where(ScanStructuralDamageIssue.structural_damage_run_id == structural_damage_run_id)
        count_stmt = count_stmt.where(ScanStructuralDamageIssue.structural_damage_run_id == structural_damage_run_id)
    rows = session.exec(stmt.order_by(col(ScanStructuralDamageIssue.created_at), col(ScanStructuralDamageIssue.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanStructuralDamageIssueListResponse(
        items=[ScanStructuralDamageIssueRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        issue_type_counts={key: sum(1 for row in rows if row.issue_type == key) for key in sorted({row.issue_type for row in rows})},
    )


def list_scan_structural_damage_issues_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanStructuralDamageIssueListResponse:
    limit, offset = clamp_scan_structural_damage_pagination(limit=limit, offset=offset)
    stmt = select(ScanStructuralDamageIssue)
    count_stmt = select(func.count()).select_from(ScanStructuralDamageIssue)
    if owner_user_id is not None:
        stmt = stmt.where(ScanStructuralDamageIssue.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanStructuralDamageIssue.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanStructuralDamageIssue.created_at), col(ScanStructuralDamageIssue.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanStructuralDamageIssueListResponse(
        items=[ScanStructuralDamageIssueRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        issue_type_counts={key: sum(1 for row in rows if row.issue_type == key) for key in sorted({row.issue_type for row in rows})},
    )


def list_scan_structural_damage_failures_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanStructuralDamageFailureListResponse:
    limit, offset = clamp_scan_structural_damage_pagination(limit=limit, offset=offset)
    stmt = select(ScanStructuralDamageRun).where(ScanStructuralDamageRun.detection_status == "FAILED")
    count_stmt = select(func.count()).select_from(ScanStructuralDamageRun).where(ScanStructuralDamageRun.detection_status == "FAILED")
    if owner_user_id is not None:
        stmt = stmt.where(ScanStructuralDamageRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanStructuralDamageRun.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanStructuralDamageRun.created_at).desc(), col(ScanStructuralDamageRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanStructuralDamageFailureListResponse(
        items=[ScanStructuralDamageRunRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )
