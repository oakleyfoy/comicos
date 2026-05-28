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
    ScanSurfaceDefectArtifact,
    ScanSurfaceDefectEvidence,
    ScanSurfaceDefectHistory,
    ScanSurfaceDefectIssue,
    ScanSurfaceDefectRun,
)
from app.schemas.scan_surface_defects import (
    ScanSurfaceDefectArtifactRead,
    ScanSurfaceDefectEvidenceListResponse,
    ScanSurfaceDefectEvidenceRead,
    ScanSurfaceDefectFailureListResponse,
    ScanSurfaceDefectHistoryRead,
    ScanSurfaceDefectIssueListResponse,
    ScanSurfaceDefectIssueRead,
    ScanSurfaceDefectRunCreate,
    ScanSurfaceDefectRunDetail,
    ScanSurfaceDefectRunListResponse,
    ScanSurfaceDefectRunRead,
)
from app.services.scan_defects import _load_source_preview, _resolve_normalization_artifact_path

ENGINE_VERSION = "P40-09-v1"
_PREVIEW_MAX = 420
_LOW_CONFIDENCE_THRESHOLD = 0.35

SURFACE_REGION_ORDER = (
    "FULL_COVER",
    "CENTER_SURFACE",
    "TITLE_AREA",
    "PRICE_BOX_AREA",
)
OPTIONAL_CONTEXT_REGION_ORDER = (
    "SPINE_REGION",
    "TOP_EDGE",
    "BOTTOM_EDGE",
    "LEFT_EDGE",
    "RIGHT_EDGE",
)
REGION_PROCESS_ORDER = SURFACE_REGION_ORDER + OPTIONAL_CONTEXT_REGION_ORDER


@dataclass(frozen=True)
class _RegionIsolation:
    region: ScanDefectRegion
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
    surface_area_ratio: float
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
    from app.models.scan_surface_defects import utc_now as _utc_now

    return _utc_now()


def clamp_scan_surface_defect_pagination(*, limit: int, offset: int) -> tuple[int, int]:
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


def _resolve_surface_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.scan_surface_defects_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("scan surface defect storage path escapes configured root")
    return target


def _artifact_storage_path(
    *,
    owner_user_id: int,
    scan_image_id: int,
    surface_defect_run_id: int,
    artifact_type: str,
    ext: str,
) -> str:
    safe_type = artifact_type.lower()
    return f"scan-surface-defects/{owner_user_id}/{scan_image_id}/{surface_defect_run_id}/{safe_type}{ext}".replace("\\", "/")


def _save_artifact_bytes(settings: Settings, *, relative_path: str, body: bytes) -> None:
    target = _resolve_surface_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)


def _artifact_preview_data_url(settings: Settings, row: ScanSurfaceDefectArtifact) -> str | None:
    if not row.storage_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        return None
    try:
        body = _resolve_surface_storage_path(settings, row.storage_path).read_bytes()
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
    return REGION_PROCESS_ORDER.index(region_type)


def isolate_surface_regions(
    *,
    image: Image.Image,
    regions: list[ScanDefectRegion],
) -> tuple[dict[str, _RegionIsolation], dict[str, _RegionIsolation]]:
    region_map = {row.region_type: row for row in regions}
    required: dict[str, _RegionIsolation] = {}
    optional: dict[str, _RegionIsolation] = {}
    rgb = _image_to_rgb(image)
    for region_type in SURFACE_REGION_ORDER:
        row = region_map.get(region_type)
        if row is None:
            continue
        required[region_type] = _RegionIsolation(
            region=row,
            crop=rgb.crop((row.x_min, row.y_min, row.x_max + 1, row.y_max + 1)),
        )
    for region_type in OPTIONAL_CONTEXT_REGION_ORDER:
        row = region_map.get(region_type)
        if row is None:
            continue
        optional[region_type] = _RegionIsolation(
            region=row,
            crop=rgb.crop((row.x_min, row.y_min, row.x_max + 1, row.y_max + 1)),
        )
    return required, optional


def _grid_steps(width: int, height: int) -> tuple[int, int]:
    return max(14, width // 4), max(16, height // 5)


def _classify_surface_evidence(
    *,
    brightness_delta: float,
    contrast_delta: float,
    color_dev: float,
    texture_variance: float,
    edge_energy_delta: float,
    aspect_ratio: float,
) -> tuple[str, str]:
    if edge_energy_delta >= 0.34 and aspect_ratio >= 1.9:
        return "SURFACE_CREASE", "TEXTURE_ANOMALY"
    if color_dev >= 0.3 and brightness_delta >= 0.18:
        return "STAIN_DISCOLORATION", "COLOR_ANOMALY"
    if color_dev >= 0.24 and contrast_delta >= 0.12:
        return "COLOR_BREAK", "COLOR_ANOMALY"
    if brightness_delta >= 0.25 and contrast_delta <= 0.14:
        return "GLOSS_INTERRUPTION", "REFLECTIVITY_ANOMALY"
    if texture_variance >= 0.28 and contrast_delta >= 0.12:
        return "SCUFF_RUB", "TEXTURE_ANOMALY"
    if edge_energy_delta >= 0.24 and brightness_delta >= 0.12:
        return "INK_LOSS", "CONTRAST_ANOMALY"
    if brightness_delta >= 0.14 and texture_variance <= 0.12:
        return "PRESSURE_MARK", "SURFACE_ANOMALY"
    if contrast_delta >= 0.18 and aspect_ratio < 1.8:
        return "SURFACE_DENT", "SURFACE_ANOMALY"
    return "PRINT_NOISE_ANOMALY", "TEXTURE_ANOMALY"


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
                float(measurements["local_brightness_delta"]) * 0.2
                + float(measurements["local_contrast_delta"]) * 0.2
                + float(measurements["color_channel_deviation"]) * 0.22
                + float(measurements["texture_variance"]) * 0.18
                + float(measurements["cluster_density"]) * 0.2,
            ),
        ),
        6,
    )


def _region_overlap_payload(
    *,
    x_min: int,
    y_min: int,
    x_max: int,
    y_max: int,
    regions: dict[str, _RegionIsolation],
) -> dict[str, float]:
    area = max(1, (x_max - x_min + 1) * (y_max - y_min + 1))
    overlaps: dict[str, float] = {}
    for region_type, iso in regions.items():
        row = iso.region
        ox0 = max(x_min, row.x_min)
        oy0 = max(y_min, row.y_min)
        ox1 = min(x_max, row.x_max)
        oy1 = min(y_max, row.y_max)
        if ox1 < ox0 or oy1 < oy0:
            continue
        overlaps[region_type] = round(((ox1 - ox0 + 1) * (oy1 - oy0 + 1)) / area, 6)
    return overlaps


def _distance_from_cover_edge(
    *,
    full_cover: ScanDefectRegion | None,
    x_min: int,
    y_min: int,
    x_max: int,
    y_max: int,
) -> int:
    if full_cover is None:
        return 0
    return min(
        max(0, x_min - full_cover.x_min),
        max(0, y_min - full_cover.y_min),
        max(0, full_cover.x_max - x_max),
        max(0, full_cover.y_max - y_max),
    )


def calculate_surface_measurements(
    *,
    local_box: tuple[int, int, int, int],
    crop: Image.Image,
    full_cover: ScanDefectRegion | None,
    region: ScanDefectRegion,
    baseline_rgb: tuple[float, float, float],
    baseline_brightness: float,
    baseline_stddev: float,
    baseline_edge: float,
    contextual_regions: dict[str, _RegionIsolation],
) -> dict[str, Any]:
    lx0, ly0, lx1, ly1 = local_box
    segment = crop.crop((lx0, ly0, lx1, ly1))
    rgb_stat = ImageStat.Stat(segment)
    gray = segment.convert("L")
    gray_stat = ImageStat.Stat(gray)
    edge_stat = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES))
    pixel_area = max(1, (lx1 - lx0) * (ly1 - ly0))
    mean_r = float(rgb_stat.mean[0]) if rgb_stat.mean else 0.0
    mean_g = float(rgb_stat.mean[1]) if len(rgb_stat.mean) > 1 else 0.0
    mean_b = float(rgb_stat.mean[2]) if len(rgb_stat.mean) > 2 else 0.0
    brightness = float(gray_stat.mean[0]) if gray_stat.mean else 0.0
    stddev = float(gray_stat.stddev[0]) if gray_stat.stddev else 0.0
    edge_mean = float(edge_stat.mean[0]) if edge_stat.mean else 0.0
    color_dev = max(abs(mean_r - baseline_rgb[0]), abs(mean_g - baseline_rgb[1]), abs(mean_b - baseline_rgb[2])) / 128.0
    brightness_delta = abs(brightness - baseline_brightness) / 128.0
    contrast_delta = abs(stddev - baseline_stddev) / max(1.0, baseline_stddev + 8.0)
    texture_variance = stddev / max(1.0, baseline_stddev + 6.0)
    cluster_density = edge_mean / max(1.0, baseline_edge + 8.0)
    abs_x_min = region.x_min + lx0
    abs_y_min = region.y_min + ly0
    abs_x_max = region.x_min + lx1 - 1
    abs_y_max = region.y_min + ly1 - 1
    line_length = max(abs_x_max - abs_x_min + 1, abs_y_max - abs_y_min + 1)
    line_orientation = round(math.degrees(math.atan2(abs_y_max - abs_y_min, abs_x_max - abs_x_min + 0.0001)), 6)
    overlaps = _region_overlap_payload(
        x_min=abs_x_min,
        y_min=abs_y_min,
        x_max=abs_x_max,
        y_max=abs_y_max,
        regions=contextual_regions,
    )
    return {
        "pixel_area": pixel_area,
        "surface_area_ratio": round(pixel_area / max(1, region.width_px * region.height_px), 6),
        "local_brightness_delta": round(brightness_delta, 6),
        "local_contrast_delta": round(contrast_delta, 6),
        "color_channel_deviation": round(color_dev, 6),
        "texture_variance": round(texture_variance, 6),
        "line_length": line_length,
        "line_orientation": line_orientation,
        "cluster_density": round(cluster_density, 6),
        "distance_from_nearest_edge": _distance_from_cover_edge(
            full_cover=full_cover,
            x_min=abs_x_min,
            y_min=abs_y_min,
            x_max=abs_x_max,
            y_max=abs_y_max,
        ),
        "overlap_with_major_regions": overlaps,
        "normalized_relative_size": round(pixel_area / max(1, (full_cover.width_px * full_cover.height_px) if full_cover else pixel_area), 6),
        "raw_brightness": round(brightness, 6),
        "raw_edge_energy": round(edge_mean, 6),
    }


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


def _line_candidates(region: _RegionIsolation) -> list[tuple[int, int, int, int]]:
    crop = region.crop
    gray = crop.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    scores: list[float] = []
    for y in range(crop.height):
        row = edges.crop((0, y, crop.width, y + 1))
        stat = ImageStat.Stat(row)
        scores.append(float(stat.mean[0]) if stat.mean else 0.0)
    if not scores:
        return []
    ordered = sorted(scores)
    median = ordered[len(ordered) // 2]
    threshold = median + max(6.0, median * 0.25)
    lines: list[tuple[int, int, int, int]] = []
    start: int | None = None
    for idx, score in enumerate(scores):
        if score >= threshold:
            if start is None:
                start = idx
        elif start is not None:
            if idx - start >= 2:
                lines.append((0, start, crop.width, idx))
            start = None
    if start is not None and crop.height - start >= 2:
        lines.append((0, start, crop.width, crop.height))
    return lines


def detect_surface_anomalies(
    *,
    regions: dict[str, _RegionIsolation],
    contextual_regions: dict[str, _RegionIsolation],
    defect_evidence: list[ScanDefectEvidence],
) -> list[_EvidenceDraft]:
    drafts: list[_EvidenceDraft] = []
    full_cover = regions.get("FULL_COVER").region if "FULL_COVER" in regions else None
    overlap_regions = {**regions, **contextual_regions}
    for region_type in SURFACE_REGION_ORDER:
        isolation = regions.get(region_type)
        if isolation is None:
            continue
        crop = isolation.crop
        region = isolation.region
        rgb_stat = ImageStat.Stat(crop)
        gray = crop.convert("L")
        gray_stat = ImageStat.Stat(gray)
        edge_stat = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES))
        baseline_rgb = (
            float(rgb_stat.mean[0]) if rgb_stat.mean else 0.0,
            float(rgb_stat.mean[1]) if len(rgb_stat.mean) > 1 else 0.0,
            float(rgb_stat.mean[2]) if len(rgb_stat.mean) > 2 else 0.0,
        )
        baseline_brightness = float(gray_stat.mean[0]) if gray_stat.mean else 0.0
        baseline_stddev = float(gray_stat.stddev[0]) if gray_stat.stddev else 0.0
        baseline_edge = float(edge_stat.mean[0]) if edge_stat.mean else 0.0
        step_x, step_y = _grid_steps(crop.width, crop.height)
        for top in range(0, crop.height, step_y):
            for left in range(0, crop.width, step_x):
                right = min(crop.width, left + step_x)
                bottom = min(crop.height, top + step_y)
                if right - left < 6 or bottom - top < 6:
                    continue
                measurements = calculate_surface_measurements(
                    local_box=(left, top, right, bottom),
                    crop=crop,
                    full_cover=full_cover,
                    region=region,
                    baseline_rgb=baseline_rgb,
                    baseline_brightness=baseline_brightness,
                    baseline_stddev=baseline_stddev,
                    baseline_edge=baseline_edge,
                    contextual_regions=overlap_regions,
                )
                brightness_delta = float(measurements["local_brightness_delta"])
                contrast_delta = float(measurements["local_contrast_delta"])
                color_dev = float(measurements["color_channel_deviation"])
                texture_variance = float(measurements["texture_variance"])
                cluster_density = float(measurements["cluster_density"])
                signal_strength = max(brightness_delta, contrast_delta, color_dev, texture_variance - 1.0, cluster_density - 1.0)
                if signal_strength < 0.12:
                    continue
                aspect_ratio = max(right - left, bottom - top) / max(1, min(right - left, bottom - top))
                evidence_type, evidence_category = _classify_surface_evidence(
                    brightness_delta=brightness_delta,
                    contrast_delta=contrast_delta,
                    color_dev=color_dev,
                    texture_variance=max(0.0, texture_variance - 1.0),
                    edge_energy_delta=max(0.0, cluster_density - 1.0),
                    aspect_ratio=aspect_ratio,
                )
                confidence = _confidence_score(measurements)
                severity = _severity_hint(float(measurements["normalized_relative_size"]), min(1.0, signal_strength))
                abs_x_min = region.x_min + left
                abs_y_min = region.y_min + top
                abs_x_max = region.x_min + right - 1
                abs_y_max = region.y_min + bottom - 1
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
                        surface_area_ratio=float(measurements["surface_area_ratio"]),
                        confidence_score=confidence,
                        severity_hint=severity,
                        measurement_json=measurements,
                        metadata_json={"grid_box_local": [left, top, right, bottom]},
                        defect_evidence_id=_overlap_defect_evidence(
                            defect_evidence=defect_evidence,
                            x_min=abs_x_min,
                            y_min=abs_y_min,
                            x_max=abs_x_max,
                            y_max=abs_y_max,
                        ),
                    )
                )
        if region_type == "CENTER_SURFACE":
            for left, top, right, bottom in _line_candidates(isolation):
                measurements = calculate_surface_measurements(
                    local_box=(left, top, right, bottom),
                    crop=crop,
                    full_cover=full_cover,
                    region=region,
                    baseline_rgb=baseline_rgb,
                    baseline_brightness=baseline_brightness,
                    baseline_stddev=baseline_stddev,
                    baseline_edge=baseline_edge,
                    contextual_regions=overlap_regions,
                )
                abs_x_min = region.x_min + left
                abs_y_min = region.y_min + top
                abs_x_max = region.x_min + right - 1
                abs_y_max = region.y_min + bottom - 1
                drafts.append(
                    _EvidenceDraft(
                        region_type=region_type,
                        evidence_type="SURFACE_CREASE",
                        evidence_category="TEXTURE_ANOMALY",
                        x_min=abs_x_min,
                        y_min=abs_y_min,
                        x_max=abs_x_max,
                        y_max=abs_y_max,
                        width_px=max(1, abs_x_max - abs_x_min + 1),
                        height_px=max(1, abs_y_max - abs_y_min + 1),
                        surface_area_ratio=float(measurements["surface_area_ratio"]),
                        confidence_score=_confidence_score(measurements),
                        severity_hint=_severity_hint(float(measurements["normalized_relative_size"]), float(measurements["cluster_density"])),
                        measurement_json=measurements,
                        metadata_json={"line_candidate": True},
                        defect_evidence_id=_overlap_defect_evidence(
                            defect_evidence=defect_evidence,
                            x_min=abs_x_min,
                            y_min=abs_y_min,
                            x_max=abs_x_max,
                            y_max=abs_y_max,
                        ),
                    )
                )
    return drafts


def segment_surface_evidence(drafts: list[_EvidenceDraft]) -> list[_EvidenceDraft]:
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
                surface_area_ratio=row.surface_area_ratio,
                confidence_score=row.confidence_score,
                severity_hint=row.severity_hint,
                measurement_json={**row.measurement_json, "evidence_rank": rank},
                metadata_json={**row.metadata_json, "evidence_rank": rank},
                defect_evidence_id=row.defect_evidence_id,
            )
        )
    return ranked


def build_surface_defect_manifest(
    *,
    defect_run: ScanDefectRun,
    required_regions: dict[str, _RegionIsolation],
    optional_regions: dict[str, _RegionIsolation],
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
        "surface_regions": [
            {
                "region_type": key,
                "region_checksum": required_regions[key].region.region_checksum,
                "bbox": [
                    required_regions[key].region.x_min,
                    required_regions[key].region.y_min,
                    required_regions[key].region.x_max,
                    required_regions[key].region.y_max,
                ],
            }
            for key in SURFACE_REGION_ORDER
            if key in required_regions
        ],
        "context_regions": [
            {
                "region_type": key,
                "region_checksum": optional_regions[key].region.region_checksum,
                "bbox": [
                    optional_regions[key].region.x_min,
                    optional_regions[key].region.y_min,
                    optional_regions[key].region.x_max,
                    optional_regions[key].region.y_max,
                ],
            }
            for key in OPTIONAL_CONTEXT_REGION_ORDER
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


def _build_region_montage(regions: dict[str, _RegionIsolation], order: tuple[str, ...]) -> bytes:
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


def _build_surface_texture_map(required_regions: dict[str, _RegionIsolation]) -> bytes:
    center = required_regions.get("CENTER_SURFACE") or required_regions.get("FULL_COVER")
    if center is None:
        return _minimal_png()
    gray = center.crop.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    contrast = gray.filter(ImageFilter.DETAIL)
    rendered = Image.merge("RGB", (edges, contrast, gray))
    rendered.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
    buf = io.BytesIO()
    rendered.save(buf, format="PNG")
    return buf.getvalue()


def _build_surface_overlay(image: Image.Image, evidence: list[_EvidenceDraft]) -> bytes:
    rendered = _image_to_rgb(image)
    draw = ImageDraw.Draw(rendered)
    palette = {"MINOR": "#eab308", "MODERATE": "#f97316", "MAJOR": "#ef4444"}
    for row in evidence:
        draw.rectangle((row.x_min, row.y_min, row.x_max, row.y_max), outline=palette.get(row.severity_hint, "#ffffff"), width=2)
    buf = io.BytesIO()
    rendered.save(buf, format="PNG")
    return buf.getvalue()


def _build_debug_preview(image: Image.Image, evidence: list[_EvidenceDraft]) -> bytes:
    rendered = _image_to_rgb(image)
    draw = ImageDraw.Draw(rendered)
    for row in evidence[:16]:
        draw.rectangle((row.x_min, row.y_min, row.x_max, row.y_max), outline="#38bdf8", width=2)
    preview = rendered.copy()
    preview.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
    buf = io.BytesIO()
    preview.save(buf, format="PNG")
    return buf.getvalue()


def _artifact_drafts_for_run(
    *,
    image: Image.Image,
    required_regions: dict[str, _RegionIsolation],
    evidence: list[_EvidenceDraft],
    measurement_export: dict[str, Any],
) -> list[_ArtifactDraft]:
    if not required_regions:
        tiny = _minimal_png()
        return [
            _ArtifactDraft("SURFACE_REGION_PREVIEW", tiny, {"placeholder": True}, ".png"),
            _ArtifactDraft("SURFACE_TEXTURE_MAP", tiny, {"placeholder": True}, ".png"),
            _ArtifactDraft("SURFACE_DEFECT_OVERLAY", _build_surface_overlay(image, evidence), {"format": "png"}, ".png"),
            _ArtifactDraft("SURFACE_MEASUREMENT_EXPORT", _serialize_json_artifact(measurement_export), {"format": "json"}, ".json"),
            _ArtifactDraft("SURFACE_DEBUG_PREVIEW", tiny, {"placeholder": True}, ".png"),
        ]
    return [
        _ArtifactDraft(
            "SURFACE_REGION_PREVIEW",
            _build_region_montage(required_regions, SURFACE_REGION_ORDER),
            {"format": "png", "region_count": len(required_regions)},
            ".png",
        ),
        _ArtifactDraft("SURFACE_TEXTURE_MAP", _build_surface_texture_map(required_regions), {"format": "png"}, ".png"),
        _ArtifactDraft(
            "SURFACE_DEFECT_OVERLAY",
            _build_surface_overlay(image, evidence),
            {"format": "png", "evidence_count": len(evidence)},
            ".png",
        ),
        _ArtifactDraft(
            "SURFACE_MEASUREMENT_EXPORT",
            _serialize_json_artifact(measurement_export),
            {"format": "json", "evidence_count": len(evidence)},
            ".json",
        ),
        _ArtifactDraft("SURFACE_DEBUG_PREVIEW", _build_debug_preview(image, evidence), {"format": "png"}, ".png"),
    ]


def _build_issues(
    *,
    required_regions: dict[str, _RegionIsolation],
    evidence: list[_EvidenceDraft],
    defect_run: ScanDefectRun,
) -> list[_IssueDraft]:
    issues: list[_IssueDraft] = []
    missing_regions = [key for key in SURFACE_REGION_ORDER if key not in required_regions]
    if missing_regions:
        issues.append(
            _IssueDraft(
                issue_type="SURFACE_REGION_MISSING",
                severity="ERROR" if len(missing_regions) >= 2 else "WARNING",
                issue_message="One or more required surface regions were missing from the defect foundation manifest.",
                metadata_json={"missing_regions": missing_regions},
            )
        )
    if not required_regions:
        issues.append(
            _IssueDraft(
                issue_type="SURFACE_DETECTION_FAILED",
                severity="ERROR",
                issue_message="Surface region isolation failed.",
                metadata_json={},
            )
        )
        return issues
    stddevs: list[float] = []
    light_ratios: list[float] = []
    channel_spread: list[float] = []
    for iso in required_regions.values():
        gray = iso.crop.convert("L")
        stat = ImageStat.Stat(gray)
        rgb = ImageStat.Stat(iso.crop)
        stddevs.append(float(stat.stddev[0]) if stat.stddev else 0.0)
        histogram = gray.histogram()
        total = max(1, iso.crop.width * iso.crop.height)
        light_ratios.append(sum(histogram[230:]) / total)
        if rgb.mean and len(rgb.mean) >= 3:
            channel_spread.append(max(rgb.mean) - min(rgb.mean))
    if light_ratios and sum(light_ratios) / len(light_ratios) > 0.18:
        issues.append(
            _IssueDraft(
                issue_type="EXCESSIVE_GLARE",
                severity="WARNING",
                issue_message="Surface regions show glare that may reduce reliable anomaly segmentation.",
                metadata_json={"mean_light_ratio": round(sum(light_ratios) / len(light_ratios), 6)},
            )
        )
    if stddevs and sum(stddevs) / len(stddevs) < 18:
        issues.append(
            _IssueDraft(
                issue_type="LOW_CONTRAST_SURFACE",
                severity="WARNING",
                issue_message="Surface contrast is low for stable surface segmentation.",
                metadata_json={"mean_stddev": round(sum(stddevs) / len(stddevs), 6)},
            )
        )
    if channel_spread and max(channel_spread) > 70:
        issues.append(
            _IssueDraft(
                issue_type="COLOR_CHANNEL_INSTABILITY",
                severity="INFO",
                issue_message="Surface regions show broad channel divergence that may inflate color anomaly counts.",
                metadata_json={"max_channel_spread": round(max(channel_spread), 6)},
            )
        )
    if evidence and all(row.confidence_score < _LOW_CONFIDENCE_THRESHOLD for row in evidence):
        issues.append(
            _IssueDraft(
                issue_type="LOW_SURFACE_CONFIDENCE",
                severity="WARNING",
                issue_message="All surface evidence rows remain below the confidence floor.",
                metadata_json={"low_confidence_count": len(evidence)},
            )
        )
    if not evidence:
        issues.append(
            _IssueDraft(
                issue_type="SURFACE_SEGMENTATION_FAILED",
                severity="INFO",
                issue_message="No surface anomalies exceeded the deterministic threshold.",
                metadata_json={"segment_count": 0},
            )
        )
    if any(iso.region.width_px < 80 or iso.region.height_px < 80 for iso in required_regions.values()):
        issues.append(
            _IssueDraft(
                issue_type="INSUFFICIENT_SURFACE_RESOLUTION",
                severity="INFO",
                issue_message="One or more surface regions are small enough to reduce fine-detail stability.",
                metadata_json={},
            )
        )
    if len(evidence) > 18:
        issues.append(
            _IssueDraft(
                issue_type="EXCESSIVE_PRINT_NOISE",
                severity="INFO",
                issue_message="Surface detection produced a high number of anomaly candidates that may include print noise.",
                metadata_json={"evidence_count": len(evidence)},
            )
        )
    return issues


def _resolve_defect_run(session: Session, *, owner_user_id: int, payload: ScanSurfaceDefectRunCreate) -> ScanDefectRun:
    stmt = select(ScanDefectRun).where(
        ScanDefectRun.owner_user_id == owner_user_id,
        ScanDefectRun.scan_image_id == payload.scan_image_id,
        ScanDefectRun.defect_status == "COMPLETE",
    )
    if payload.defect_run_id is not None:
        stmt = stmt.where(ScanDefectRun.id == payload.defect_run_id)
    defect_run = session.exec(stmt.order_by(col(ScanDefectRun.id).desc())).first()
    if defect_run is None:
        raise HTTPException(status_code=409, detail="A complete defect foundation run is required before surface defect detection.")
    return defect_run


def _detail_from_run(session: Session, settings: Settings, run: ScanSurfaceDefectRun) -> ScanSurfaceDefectRunDetail:
    evidence = session.exec(
        select(ScanSurfaceDefectEvidence)
        .where(ScanSurfaceDefectEvidence.surface_defect_run_id == run.id)
        .order_by(col(ScanSurfaceDefectEvidence.evidence_rank), col(ScanSurfaceDefectEvidence.id))
    ).all()
    artifacts = session.exec(
        select(ScanSurfaceDefectArtifact)
        .where(ScanSurfaceDefectArtifact.surface_defect_run_id == run.id)
        .order_by(col(ScanSurfaceDefectArtifact.id))
    ).all()
    issues = session.exec(
        select(ScanSurfaceDefectIssue)
        .where(ScanSurfaceDefectIssue.surface_defect_run_id == run.id)
        .order_by(col(ScanSurfaceDefectIssue.id))
    ).all()
    history = session.exec(
        select(ScanSurfaceDefectHistory)
        .where(ScanSurfaceDefectHistory.surface_defect_run_id == run.id)
        .order_by(col(ScanSurfaceDefectHistory.id))
    ).all()
    defect_run = session.get(ScanDefectRun, int(run.defect_run_id))
    source_artifact = session.get(ScanNormalizationArtifact, int(defect_run.source_artifact_id)) if defect_run else None
    art_reads = [
        ScanSurfaceDefectArtifactRead.model_validate(row).model_copy(
            update={"preview_data_url": _artifact_preview_data_url(settings, row)}
        )
        for row in artifacts
    ]
    scan_image = session.get(ScanImage, int(run.scan_image_id))
    norm_run = session.get(ScanNormalizationRun, int(defect_run.normalization_run_id)) if defect_run else None
    boundary_run = session.get(ScanBoundaryRun, int(defect_run.boundary_run_id)) if defect_run else None
    run_data = ScanSurfaceDefectRunRead.model_validate(run).model_dump()
    return ScanSurfaceDefectRunDetail(
        **run_data,
        evidence=[ScanSurfaceDefectEvidenceRead.model_validate(row) for row in evidence],
        artifacts=art_reads,
        issues=[ScanSurfaceDefectIssueRead.model_validate(row) for row in issues],
        history=[ScanSurfaceDefectHistoryRead.model_validate(row) for row in history],
        original_scan_checksum=scan_image.sha256_checksum if scan_image else None,
        normalization_checksum=norm_run.normalization_checksum if norm_run else None,
        boundary_checksum=boundary_run.boundary_checksum if boundary_run else None,
        defect_checksum=defect_run.defect_checksum if defect_run else None,
        source_preview_data_url=_load_source_preview(settings, source_artifact) if source_artifact else None,
        surface_region_preview_data_url=next((a.preview_data_url for a in art_reads if a.artifact_type == "SURFACE_REGION_PREVIEW"), None),
        evidence_summary=dict(run.output_manifest_json.get("evidence_summary") or {}),
    )


def run_scan_surface_defect_detection(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: ScanSurfaceDefectRunCreate,
) -> tuple[ScanSurfaceDefectRunDetail, bool]:
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
        raise HTTPException(status_code=409, detail="Normalized source artifact is not available for surface defect detection.") from exc

    required_regions, optional_regions = isolate_surface_regions(image=image, regions=defect_regions)
    drafts = detect_surface_anomalies(
        regions=required_regions,
        contextual_regions=optional_regions,
        defect_evidence=defect_evidence,
    )
    evidence = segment_surface_evidence(drafts)
    issues = _build_issues(required_regions=required_regions, evidence=evidence, defect_run=defect_run)
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
        evidence=evidence,
        measurement_export=measurement_export,
    )
    provisional_manifest, surface_defect_checksum = build_surface_defect_manifest(
        defect_run=defect_run,
        required_regions=required_regions,
        optional_regions=optional_regions,
        evidence=evidence,
        issues=issues,
        artifact_checksums=[
            {"artifact_type": row.artifact_type, "artifact_checksum": _sha256_bytes(row.body)} for row in provisional_artifacts
        ],
    )
    manifest_artifact = _ArtifactDraft("SURFACE_DEFECT_MANIFEST", _serialize_json_artifact(provisional_manifest), {"format": "json"}, ".json")
    artifacts = provisional_artifacts + [manifest_artifact]

    existing = session.exec(
        select(ScanSurfaceDefectRun).where(
            ScanSurfaceDefectRun.owner_user_id == owner_user_id,
            ScanSurfaceDefectRun.surface_defect_checksum == surface_defect_checksum,
        )
    ).first()
    if existing is not None:
        return _detail_from_run(session, settings, existing), False

    run = ScanSurfaceDefectRun(
        owner_user_id=owner_user_id,
        scan_image_id=int(defect_run.scan_image_id),
        defect_run_id=int(defect_run.id or 0),
        source_checksum=defect_run.source_checksum,
        surface_defect_checksum=surface_defect_checksum,
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
            ScanSurfaceDefectEvidence(
                owner_user_id=owner_user_id,
                surface_defect_run_id=int(run.id or 0),
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
                surface_area_ratio=row.surface_area_ratio,
                measurement_json=row.measurement_json,
                metadata_json=row.metadata_json,
            )
        )
    for row in issues:
        session.add(
            ScanSurfaceDefectIssue(
                owner_user_id=owner_user_id,
                surface_defect_run_id=int(run.id or 0),
                issue_type=row.issue_type,
                severity=row.severity,
                issue_message=row.issue_message,
                metadata_json=row.metadata_json,
            )
        )
    history_rows = [
        _HistoryDraft("SURFACE_DEFECT_RUN_CREATED", "Created deterministic surface defect detection run.", {"surface_defect_checksum": surface_defect_checksum}),
        _HistoryDraft("SURFACE_REGIONS_ISOLATED", "Isolated required surface regions from defect foundation geometry.", {"region_count": len(required_regions)}),
        _HistoryDraft("SURFACE_ANOMALIES_SEGMENTED", "Segmented probable surface-level evidence candidates.", {"evidence_count": len(evidence)}),
        _HistoryDraft("SURFACE_DEFECT_MANIFEST_WRITTEN", "Persisted replay-safe surface defect manifest and artifacts.", {"artifact_count": len(artifacts)}),
    ]
    for row in history_rows:
        session.add(
            ScanSurfaceDefectHistory(
                owner_user_id=owner_user_id,
                surface_defect_run_id=int(run.id or 0),
                event_type=row.event_type,
                event_message=row.event_message,
                event_checksum=_hash_payload(
                    {
                        "surface_defect_run_id": int(run.id or 0),
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
            surface_defect_run_id=int(run.id or 0),
            artifact_type=row.artifact_type,
            ext=row.ext,
        )
        _save_artifact_bytes(settings, relative_path=relative_path, body=row.body)
        session.add(
            ScanSurfaceDefectArtifact(
                owner_user_id=owner_user_id,
                surface_defect_run_id=int(run.id or 0),
                artifact_type=row.artifact_type,
                storage_path=relative_path,
                artifact_checksum=_sha256_bytes(row.body),
                metadata_json=row.metadata_json,
            )
        )
    session.commit()
    session.refresh(run)
    return _detail_from_run(session, settings, run), True


def get_scan_surface_defect_run_owner(session: Session, settings: Settings, *, owner_user_id: int, run_id: int) -> ScanSurfaceDefectRunDetail:
    row = session.get(ScanSurfaceDefectRun, run_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Surface defect run not found.")
    return _detail_from_run(session, settings, row)


def get_scan_surface_defect_artifact_owner(session: Session, settings: Settings, *, owner_user_id: int, artifact_id: int) -> ScanSurfaceDefectArtifactRead:
    row = session.get(ScanSurfaceDefectArtifact, artifact_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Surface defect artifact not found.")
    return ScanSurfaceDefectArtifactRead.model_validate(row).model_copy(
        update={"preview_data_url": _artifact_preview_data_url(settings, row)}
    )


def _run_list_response(rows: list[ScanSurfaceDefectRun], *, limit: int, offset: int, total_items: int) -> ScanSurfaceDefectRunListResponse:
    status_counts = {status: sum(1 for row in rows if row.detection_status == status) for status in sorted({row.detection_status for row in rows})}
    low_confidence = sum(int((row.output_manifest_json.get("evidence_summary") or {}).get("low_confidence_count") or 0) for row in rows)
    high_density = sum(int((row.output_manifest_json.get("evidence_summary") or {}).get("major_count") or 0) for row in rows)
    return ScanSurfaceDefectRunListResponse(
        items=[ScanSurfaceDefectRunRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        status_counts=status_counts,
        low_confidence_count=low_confidence,
        high_density_surface_count=high_density,
    )


def list_scan_surface_defect_runs_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanSurfaceDefectRunListResponse:
    limit, offset = clamp_scan_surface_defect_pagination(limit=limit, offset=offset)
    stmt = select(ScanSurfaceDefectRun).where(ScanSurfaceDefectRun.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanSurfaceDefectRun).where(ScanSurfaceDefectRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanSurfaceDefectRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanSurfaceDefectRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanSurfaceDefectRun.created_at).desc(), col(ScanSurfaceDefectRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_surface_defect_runs_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanSurfaceDefectRunListResponse:
    limit, offset = clamp_scan_surface_defect_pagination(limit=limit, offset=offset)
    stmt = select(ScanSurfaceDefectRun)
    count_stmt = select(func.count()).select_from(ScanSurfaceDefectRun)
    if owner_user_id is not None:
        stmt = stmt.where(ScanSurfaceDefectRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanSurfaceDefectRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanSurfaceDefectRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanSurfaceDefectRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanSurfaceDefectRun.created_at).desc(), col(ScanSurfaceDefectRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_surface_defect_evidence_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    surface_defect_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanSurfaceDefectEvidenceListResponse:
    limit, offset = clamp_scan_surface_defect_pagination(limit=limit, offset=offset)
    stmt = select(ScanSurfaceDefectEvidence).join(
        ScanSurfaceDefectRun,
        ScanSurfaceDefectRun.id == ScanSurfaceDefectEvidence.surface_defect_run_id,
    ).where(ScanSurfaceDefectEvidence.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanSurfaceDefectEvidence).join(
        ScanSurfaceDefectRun,
        ScanSurfaceDefectRun.id == ScanSurfaceDefectEvidence.surface_defect_run_id,
    ).where(ScanSurfaceDefectEvidence.owner_user_id == owner_user_id)
    if surface_defect_run_id is not None:
        stmt = stmt.where(ScanSurfaceDefectEvidence.surface_defect_run_id == surface_defect_run_id)
        count_stmt = count_stmt.where(ScanSurfaceDefectEvidence.surface_defect_run_id == surface_defect_run_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanSurfaceDefectRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanSurfaceDefectRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanSurfaceDefectEvidence.evidence_rank), col(ScanSurfaceDefectEvidence.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanSurfaceDefectEvidenceListResponse(
        items=[ScanSurfaceDefectEvidenceRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        evidence_type_counts={key: sum(1 for row in rows if row.evidence_type == key) for key in sorted({row.evidence_type for row in rows})},
        evidence_category_counts={key: sum(1 for row in rows if row.evidence_category == key) for key in sorted({row.evidence_category for row in rows})},
        severity_hint_counts={key: sum(1 for row in rows if row.severity_hint == key) for key in sorted({row.severity_hint for row in rows})},
        low_confidence_count=sum(1 for row in rows if float(row.confidence_score) < _LOW_CONFIDENCE_THRESHOLD),
    )


def list_scan_surface_defect_issues_owner(
    session: Session,
    *,
    owner_user_id: int,
    surface_defect_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanSurfaceDefectIssueListResponse:
    limit, offset = clamp_scan_surface_defect_pagination(limit=limit, offset=offset)
    stmt = select(ScanSurfaceDefectIssue).where(ScanSurfaceDefectIssue.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanSurfaceDefectIssue).where(ScanSurfaceDefectIssue.owner_user_id == owner_user_id)
    if surface_defect_run_id is not None:
        stmt = stmt.where(ScanSurfaceDefectIssue.surface_defect_run_id == surface_defect_run_id)
        count_stmt = count_stmt.where(ScanSurfaceDefectIssue.surface_defect_run_id == surface_defect_run_id)
    rows = session.exec(stmt.order_by(col(ScanSurfaceDefectIssue.created_at), col(ScanSurfaceDefectIssue.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanSurfaceDefectIssueListResponse(
        items=[ScanSurfaceDefectIssueRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        issue_type_counts={key: sum(1 for row in rows if row.issue_type == key) for key in sorted({row.issue_type for row in rows})},
    )


def list_scan_surface_defect_issues_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanSurfaceDefectIssueListResponse:
    limit, offset = clamp_scan_surface_defect_pagination(limit=limit, offset=offset)
    stmt = select(ScanSurfaceDefectIssue)
    count_stmt = select(func.count()).select_from(ScanSurfaceDefectIssue)
    if owner_user_id is not None:
        stmt = stmt.where(ScanSurfaceDefectIssue.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanSurfaceDefectIssue.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanSurfaceDefectIssue.created_at), col(ScanSurfaceDefectIssue.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanSurfaceDefectIssueListResponse(
        items=[ScanSurfaceDefectIssueRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        issue_type_counts={key: sum(1 for row in rows if row.issue_type == key) for key in sorted({row.issue_type for row in rows})},
    )


def list_scan_surface_defect_failures_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanSurfaceDefectFailureListResponse:
    limit, offset = clamp_scan_surface_defect_pagination(limit=limit, offset=offset)
    stmt = select(ScanSurfaceDefectRun).where(ScanSurfaceDefectRun.detection_status == "FAILED")
    count_stmt = select(func.count()).select_from(ScanSurfaceDefectRun).where(ScanSurfaceDefectRun.detection_status == "FAILED")
    if owner_user_id is not None:
        stmt = stmt.where(ScanSurfaceDefectRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanSurfaceDefectRun.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanSurfaceDefectRun.created_at).desc(), col(ScanSurfaceDefectRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanSurfaceDefectFailureListResponse(
        items=[ScanSurfaceDefectRunRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )
