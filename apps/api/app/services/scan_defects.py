from __future__ import annotations

import base64
import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat, UnidentifiedImageError
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models import (
    ScanBoundaryArtifact,
    ScanBoundaryRun,
    ScanDefectArtifact,
    ScanDefectEvidence,
    ScanDefectHistory,
    ScanDefectIssue,
    ScanDefectRegion,
    ScanDefectRun,
    ScanImage,
    ScanNormalizationArtifact,
    ScanNormalizationRun,
    ScanOcrRun,
    ScanReconciliationRun,
)
from app.schemas.scan_defects import (
    ScanDefectArtifactRead,
    ScanDefectEvidenceListResponse,
    ScanDefectEvidenceRead,
    ScanDefectFailureListResponse,
    ScanDefectHistoryRead,
    ScanDefectIssueListResponse,
    ScanDefectIssueRead,
    ScanDefectRegionListResponse,
    ScanDefectRegionRead,
    ScanDefectRunCreate,
    ScanDefectRunDetail,
    ScanDefectRunListResponse,
    ScanDefectRunRead,
)

DETECTION_ENGINE_VERSION = "P40-06-v1"
_PREVIEW_MAX = 420
_QUALITY_GATE_TYPES = frozenset(
    {
        "LOW_RESOLUTION",
        "LOW_DPI",
        "EXCESSIVE_BLUR",
        "EXCESSIVE_GLARE",
        "OVEREXPOSED_IMAGE",
        "UNDEREXPOSED_IMAGE",
        "INSUFFICIENT_CONTRAST",
        "PARTIAL_COVER",
        "BAD_BOUNDARY_GEOMETRY",
        "COLOR_SHIFT_DETECTED",
    }
)
_REGION_ORDER = (
    "FULL_COVER",
    "SPINE_REGION",
    "TOP_EDGE",
    "BOTTOM_EDGE",
    "LEFT_EDGE",
    "RIGHT_EDGE",
    "TOP_LEFT_CORNER",
    "TOP_RIGHT_CORNER",
    "BOTTOM_LEFT_CORNER",
    "BOTTOM_RIGHT_CORNER",
    "CENTER_SURFACE",
    "TITLE_AREA",
    "PRICE_BOX_AREA",
)


@dataclass(frozen=True)
class _RegionDraft:
    region_type: str
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    width_px: int
    height_px: int
    region_checksum: str
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _EvidenceDraft:
    region_type: str
    evidence_type: str
    evidence_category: str
    severity_hint: str
    confidence_score: float
    x_min: int
    y_min: int
    x_max: int
    y_max: int
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


@dataclass(frozen=True)
class _DefectContext:
    scan_image: ScanImage
    normalization_run: ScanNormalizationRun
    boundary_run: ScanBoundaryRun
    source_artifact: ScanNormalizationArtifact
    ocr_run: ScanOcrRun | None
    reconciliation_run: ScanReconciliationRun | None


def utc_now():
    from app.models.scan_defects import utc_now as _utc_now

    return _utc_now()


def clamp_scan_defect_pagination(*, limit: int, offset: int) -> tuple[int, int]:
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


def _resolve_normalization_artifact_path(settings: Settings, row: ScanNormalizationArtifact) -> Path:
    base = settings.scan_normalization_storage_root.resolve()
    target = (base / row.storage_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("normalization artifact path escapes configured root")
    return target


def _resolve_defect_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.scan_defects_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("scan defect storage path escapes configured root")
    return target


def _artifact_storage_path(
    *,
    owner_user_id: int,
    scan_image_id: int,
    defect_run_id: int,
    artifact_type: str,
    ext: str,
) -> str:
    safe_type = artifact_type.lower()
    return f"scan-defects/{owner_user_id}/{scan_image_id}/{defect_run_id}/{safe_type}{ext}".replace("\\", "/")


def _load_source_preview(settings: Settings, source_artifact: ScanNormalizationArtifact) -> str | None:
    try:
        with Image.open(_resolve_normalization_artifact_path(settings, source_artifact)) as image:
            preview = image.copy()
            if preview.mode not in {"RGB", "RGBA", "L"}:
                preview = preview.convert("RGB")
            preview.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
            rendered = io.BytesIO()
            preview.save(rendered, format="PNG")
            return f"data:image/png;base64,{base64.b64encode(rendered.getvalue()).decode('ascii')}"
    except (FileNotFoundError, OSError, ValueError, UnidentifiedImageError):
        return None


def _artifact_preview_data_url(settings: Settings, row: ScanDefectArtifact) -> str | None:
    if not row.storage_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        return None
    try:
        body = _resolve_defect_storage_path(settings, row.storage_path).read_bytes()
    except OSError:
        return None
    return f"data:image/png;base64,{base64.b64encode(body).decode('ascii')}"


def _save_artifact_bytes(settings: Settings, *, relative_path: str, body: bytes) -> None:
    target = _resolve_defect_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)


def _image_to_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image.copy()
    return image.convert("RGB")


def _clamp_box(x_min: int, y_min: int, x_max: int, y_max: int, *, max_width: int, max_height: int) -> tuple[int, int, int, int]:
    left = max(0, min(x_min, max_width - 1))
    top = max(0, min(y_min, max_height - 1))
    right = max(left + 1, min(x_max, max_width - 1))
    bottom = max(top + 1, min(y_max, max_height - 1))
    return left, top, right, bottom


def _bbox_from_boundary(boundary_run: ScanBoundaryRun, *, image: Image.Image) -> tuple[int, int, int, int]:
    geometry = dict(boundary_run.output_manifest_json.get("geometry") or {})
    if not geometry:
        raise HTTPException(status_code=409, detail="Boundary geometry is required for defect analysis.")
    x_min = int(geometry.get("x_min", 0))
    y_min = int(geometry.get("y_min", 0))
    x_max = int(geometry.get("x_max", image.width - 1))
    y_max = int(geometry.get("y_max", image.height - 1))
    return _clamp_box(x_min, y_min, x_max, y_max, max_width=image.width, max_height=image.height)


def _region_box_payload(*, region_type: str, x_min: int, y_min: int, x_max: int, y_max: int) -> dict[str, Any]:
    return {
        "region_type": region_type,
        "x_min": x_min,
        "y_min": y_min,
        "x_max": x_max,
        "y_max": y_max,
        "width_px": max(1, x_max - x_min + 1),
        "height_px": max(1, y_max - y_min + 1),
    }


def derive_condition_regions(
    *,
    boundary_run: ScanBoundaryRun,
    image: Image.Image,
    source_checksum: str,
) -> list[_RegionDraft]:
    left, top, right, bottom = _bbox_from_boundary(boundary_run, image=image)
    cover_width = max(1, right - left + 1)
    cover_height = max(1, bottom - top + 1)
    edge_band = max(12, int(round(min(cover_width, cover_height) * 0.08)))
    corner_band = max(edge_band, int(round(min(cover_width, cover_height) * 0.16)))
    spine_width = max(14, int(round(cover_width * 0.10)))
    title_height = max(18, int(round(cover_height * 0.20)))
    price_width = max(18, int(round(cover_width * 0.24)))
    price_height = max(18, int(round(cover_height * 0.16)))

    box_map: dict[str, tuple[int, int, int, int]] = {
        "FULL_COVER": (left, top, right, bottom),
        "SPINE_REGION": (left, top, min(right, left + spine_width - 1), bottom),
        "TOP_EDGE": (left, top, right, min(bottom, top + edge_band - 1)),
        "BOTTOM_EDGE": (left, max(top, bottom - edge_band + 1), right, bottom),
        "LEFT_EDGE": (left, top, min(right, left + edge_band - 1), bottom),
        "RIGHT_EDGE": (max(left, right - edge_band + 1), top, right, bottom),
        "TOP_LEFT_CORNER": (left, top, min(right, left + corner_band - 1), min(bottom, top + corner_band - 1)),
        "TOP_RIGHT_CORNER": (max(left, right - corner_band + 1), top, right, min(bottom, top + corner_band - 1)),
        "BOTTOM_LEFT_CORNER": (left, max(top, bottom - corner_band + 1), min(right, left + corner_band - 1), bottom),
        "BOTTOM_RIGHT_CORNER": (max(left, right - corner_band + 1), max(top, bottom - corner_band + 1), right, bottom),
        "CENTER_SURFACE": (
            min(right, left + edge_band),
            min(bottom, top + title_height),
            max(left, right - edge_band),
            max(top, bottom - edge_band),
        ),
        "TITLE_AREA": (left, top, right, min(bottom, top + title_height - 1)),
        "PRICE_BOX_AREA": (left, top, min(right, left + price_width - 1), min(bottom, top + price_height - 1)),
    }

    drafts: list[_RegionDraft] = []
    for region_type in _REGION_ORDER:
        x_min, y_min, x_max, y_max = _clamp_box(*box_map[region_type], max_width=image.width, max_height=image.height)
        payload = _region_box_payload(region_type=region_type, x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)
        payload["source_checksum"] = source_checksum
        drafts.append(
            _RegionDraft(
                region_type=region_type,
                x_min=x_min,
                y_min=y_min,
                x_max=x_max,
                y_max=y_max,
                width_px=payload["width_px"],
                height_px=payload["height_px"],
                region_checksum=_hash_payload(payload),
                metadata_json={
                    "relative_cover_width_ratio": round(payload["width_px"] / max(1, cover_width), 6),
                    "relative_cover_height_ratio": round(payload["height_px"] / max(1, cover_height), 6),
                    "cover_bbox": [left, top, right, bottom],
                },
            )
        )
    return drafts


def _image_stats(image: Image.Image, box: tuple[int, int, int, int]) -> dict[str, float]:
    crop = image.crop((box[0], box[1], box[2] + 1, box[3] + 1))
    gray = crop.convert("L")
    gray_stat = ImageStat.Stat(gray)
    rgb_stat = ImageStat.Stat(_image_to_rgb(crop))
    histogram = gray.histogram()
    total_pixels = max(1, gray.width * gray.height)
    dark_ratio = sum(histogram[:25]) / total_pixels
    light_ratio = sum(histogram[230:]) / total_pixels
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_stat = ImageStat.Stat(edges)
    channel_means = [float(value) for value in (rgb_stat.mean if rgb_stat.mean else [0.0, 0.0, 0.0])]
    channel_stddev = [float(value) for value in (rgb_stat.stddev if rgb_stat.stddev else [0.0, 0.0, 0.0])]
    return {
        "mean_brightness": round(float(gray_stat.mean[0]) if gray_stat.mean else 0.0, 6),
        "brightness_stddev": round(float(gray_stat.stddev[0]) if gray_stat.stddev else 0.0, 6),
        "dark_ratio": round(dark_ratio, 6),
        "light_ratio": round(light_ratio, 6),
        "edge_mean": round(float(edge_stat.mean[0]) if edge_stat.mean else 0.0, 6),
        "edge_stddev": round(float(edge_stat.stddev[0]) if edge_stat.stddev else 0.0, 6),
        "red_mean": round(channel_means[0], 6),
        "green_mean": round(channel_means[1], 6),
        "blue_mean": round(channel_means[2], 6),
        "red_stddev": round(channel_stddev[0], 6),
        "green_stddev": round(channel_stddev[1], 6),
        "blue_stddev": round(channel_stddev[2], 6),
    }


def run_scan_quality_gates(
    *,
    scan_image: ScanImage,
    boundary_run: ScanBoundaryRun,
    image: Image.Image,
    cover_region: _RegionDraft,
) -> list[_IssueDraft]:
    stats = _image_stats(image, (cover_region.x_min, cover_region.y_min, cover_region.x_max, cover_region.y_max))
    issues: list[_IssueDraft] = []
    min_dim = min(image.width, image.height)
    if min_dim < 900:
        issues.append(
            _IssueDraft(
                issue_type="LOW_RESOLUTION",
                severity="WARNING",
                issue_message="Normalized source resolution is below the defect-foundation target.",
                metadata_json={"min_dimension_px": min_dim, "threshold_px": 900},
            )
        )
    dpi_values = [value for value in (scan_image.dpi_x, scan_image.dpi_y) if isinstance(value, int) and value > 0]
    min_dpi = min(dpi_values) if dpi_values else None
    if min_dpi is not None and min_dpi < 220:
        issues.append(
            _IssueDraft(
                issue_type="LOW_DPI",
                severity="WARNING",
                issue_message="Scan DPI is below the minimum deterministic quality floor.",
                metadata_json={"min_dpi": min_dpi, "threshold_dpi": 220},
            )
        )
    if stats["edge_mean"] < 7.5:
        issues.append(
            _IssueDraft(
                issue_type="EXCESSIVE_BLUR",
                severity="WARNING",
                issue_message="Edge sharpness is too soft for reliable defect anchoring.",
                metadata_json={"edge_mean": stats["edge_mean"], "threshold": 7.5},
            )
        )
    if stats["light_ratio"] > 0.18 and stats["mean_brightness"] > 180:
        issues.append(
            _IssueDraft(
                issue_type="EXCESSIVE_GLARE",
                severity="WARNING",
                issue_message="High-brightness cover regions suggest glare or reflective washout.",
                metadata_json={"light_ratio": stats["light_ratio"], "mean_brightness": stats["mean_brightness"]},
            )
        )
    if stats["mean_brightness"] > 218 or stats["light_ratio"] > 0.32:
        issues.append(
            _IssueDraft(
                issue_type="OVEREXPOSED_IMAGE",
                severity="WARNING",
                issue_message="Brightness distribution indicates overexposure risk.",
                metadata_json={"light_ratio": stats["light_ratio"], "mean_brightness": stats["mean_brightness"]},
            )
        )
    if stats["mean_brightness"] < 60 or stats["dark_ratio"] > 0.40:
        issues.append(
            _IssueDraft(
                issue_type="UNDEREXPOSED_IMAGE",
                severity="WARNING",
                issue_message="Brightness distribution indicates underexposure risk.",
                metadata_json={"dark_ratio": stats["dark_ratio"], "mean_brightness": stats["mean_brightness"]},
            )
        )
    if stats["brightness_stddev"] < 34:
        issues.append(
            _IssueDraft(
                issue_type="INSUFFICIENT_CONTRAST",
                severity="WARNING",
                issue_message="Contrast is too low for stable anomaly anchoring.",
                metadata_json={"brightness_stddev": stats["brightness_stddev"], "threshold": 34},
            )
        )
    coverage_ratio = float(boundary_run.output_manifest_json.get("geometry", {}).get("cover_coverage_ratio") or 0.0)
    if coverage_ratio < 0.68:
        issues.append(
            _IssueDraft(
                issue_type="PARTIAL_COVER",
                severity="WARNING",
                issue_message="Boundary geometry indicates partial cover capture.",
                metadata_json={"cover_coverage_ratio": round(coverage_ratio, 6), "threshold": 0.68},
            )
        )
    boundary_confidence = float(boundary_run.output_manifest_json.get("detection", {}).get("confidence_score") or 0.0)
    if boundary_confidence < 0.45:
        issues.append(
            _IssueDraft(
                issue_type="BAD_BOUNDARY_GEOMETRY",
                severity="WARNING",
                issue_message="Boundary confidence is too low for stable defect region derivation.",
                metadata_json={"boundary_confidence": round(boundary_confidence, 6), "threshold": 0.45},
            )
        )
    channel_means = [stats["red_mean"], stats["green_mean"], stats["blue_mean"]]
    if max(channel_means) - min(channel_means) > 32:
        issues.append(
            _IssueDraft(
                issue_type="COLOR_SHIFT_DETECTED",
                severity="INFO",
                issue_message="Channel means suggest scanner-side color drift.",
                metadata_json={"channel_means": channel_means, "spread": round(max(channel_means) - min(channel_means), 6)},
            )
        )
    return issues


def _region_category(region_type: str) -> str:
    if region_type == "SPINE_REGION":
        return "SPINE_ANOMALY"
    if "CORNER" in region_type:
        return "CORNER_ANOMALY"
    if region_type in {"TOP_EDGE", "BOTTOM_EDGE", "LEFT_EDGE", "RIGHT_EDGE"}:
        return "EDGE_ANOMALY"
    if region_type in {"TITLE_AREA", "PRICE_BOX_AREA"}:
        return "GEOMETRY_ANOMALY"
    return "SURFACE_ANOMALY"


def _dominant_metric(metrics: dict[str, float]) -> tuple[str, float]:
    ordered = sorted(metrics.items(), key=lambda item: (-item[1], item[0]))
    return ordered[0]


def _severity_hint(score: float) -> str:
    if score >= 0.72:
        return "HIGH"
    if score >= 0.4:
        return "MEDIUM"
    return "LOW"


def calculate_evidence_measurements(
    *,
    region: _RegionDraft,
    cover_region: _RegionDraft,
    region_stats: dict[str, float],
    cover_stats: dict[str, float],
) -> dict[str, Any]:
    area = region.width_px * region.height_px
    cover_area = max(1, cover_region.width_px * cover_region.height_px)
    center_x = region.x_min + (region.width_px / 2)
    center_y = region.y_min + (region.height_px / 2)
    rel_x = (center_x - cover_region.x_min) / max(1, cover_region.width_px)
    rel_y = (center_y - cover_region.y_min) / max(1, cover_region.height_px)
    nearest_edge = min(
        abs(region.x_min - cover_region.x_min),
        abs(region.y_min - cover_region.y_min),
        abs(cover_region.x_max - region.x_max),
        abs(cover_region.y_max - region.y_max),
    )
    brightness_delta = abs(region_stats["mean_brightness"] - cover_stats["mean_brightness"]) / 255.0
    contrast_delta = abs(region_stats["brightness_stddev"] - cover_stats["brightness_stddev"]) / 128.0
    edge_delta = abs(region_stats["edge_mean"] - cover_stats["edge_mean"]) / 64.0
    color_delta = (
        max(
            abs(region_stats["red_mean"] - cover_stats["red_mean"]),
            abs(region_stats["green_mean"] - cover_stats["green_mean"]),
            abs(region_stats["blue_mean"] - cover_stats["blue_mean"]),
        )
        / 255.0
    )
    anomaly_ratio = min(1.0, max(brightness_delta, contrast_delta, edge_delta, color_delta) * (area / cover_area) * 4)
    normalized_severity = min(1.0, (brightness_delta * 0.28) + (contrast_delta * 0.24) + (edge_delta * 0.28) + (color_delta * 0.20))
    return {
        "pixel_area": area,
        "bounding_box": [region.x_min, region.y_min, region.x_max, region.y_max],
        "relative_cover_position": {
            "x_ratio": round(rel_x, 6),
            "y_ratio": round(rel_y, 6),
        },
        "distance_from_nearest_edge_px": int(nearest_edge),
        "region_overlap": {
            "region_type": region.region_type,
            "cover_region_type": cover_region.region_type,
        },
        "contrast_delta": round(contrast_delta, 6),
        "brightness_delta": round(brightness_delta, 6),
        "edge_sharpness_delta": round(edge_delta, 6),
        "color_shift_delta": round(color_delta, 6),
        "anomaly_area_ratio": round(anomaly_ratio, 6),
        "normalized_severity_hint": round(normalized_severity, 6),
    }


def detect_baseline_visual_anomalies(
    *,
    image: Image.Image,
    regions: list[_RegionDraft],
) -> list[_EvidenceDraft]:
    region_map = {row.region_type: row for row in regions}
    cover_region = region_map["FULL_COVER"]
    cover_stats = _image_stats(image, (cover_region.x_min, cover_region.y_min, cover_region.x_max, cover_region.y_max))
    evidence_rows: list[_EvidenceDraft] = []
    for region in regions:
        if region.region_type == "FULL_COVER":
            continue
        region_stats = _image_stats(image, (region.x_min, region.y_min, region.x_max, region.y_max))
        measurements = calculate_evidence_measurements(
            region=region,
            cover_region=cover_region,
            region_stats=region_stats,
            cover_stats=cover_stats,
        )
        metrics = {
            "BRIGHTNESS_DELTA": float(measurements["brightness_delta"]),
            "CONTRAST_DELTA": float(measurements["contrast_delta"]),
            "EDGE_SHARPNESS_DELTA": float(measurements["edge_sharpness_delta"]),
            "COLOR_SHIFT_DELTA": float(measurements["color_shift_delta"]),
        }
        evidence_type, dominant_score = _dominant_metric(metrics)
        category = _region_category(region.region_type)
        if category == "SURFACE_ANOMALY" and evidence_type == "COLOR_SHIFT_DELTA":
            category = "COLOR_ANOMALY"
        elif category == "SURFACE_ANOMALY" and evidence_type == "CONTRAST_DELTA":
            category = "CONTRAST_ANOMALY"
        elif category == "GEOMETRY_ANOMALY" and evidence_type == "EDGE_SHARPNESS_DELTA":
            category = "GEOMETRY_ANOMALY"
        confidence_score = round(
            min(
                1.0,
                max(
                    0.05,
                    dominant_score * 0.68 + float(measurements["normalized_severity_hint"]) * 0.32,
                ),
            ),
            6,
        )
        evidence_rows.append(
            _EvidenceDraft(
                region_type=region.region_type,
                evidence_type=evidence_type,
                evidence_category=category,
                severity_hint=_severity_hint(confidence_score),
                confidence_score=confidence_score,
                x_min=region.x_min,
                y_min=region.y_min,
                x_max=region.x_max,
                y_max=region.y_max,
                measurement_json=measurements,
                metadata_json={
                    "region_type": region.region_type,
                    "cover_baseline_stats": cover_stats,
                    "region_stats": region_stats,
                },
            )
        )
    return sorted(
        evidence_rows,
        key=lambda row: (
            _REGION_ORDER.index(row.region_type),
            row.evidence_category,
            row.evidence_type,
            -row.confidence_score,
        ),
    )


def _build_region_map_artifact(image: Image.Image, *, regions: list[_RegionDraft]) -> bytes:
    rendered = _image_to_rgb(image)
    draw = ImageDraw.Draw(rendered)
    palette = {
        "FULL_COVER": "#38bdf8",
        "SPINE_REGION": "#f97316",
        "TOP_EDGE": "#eab308",
        "BOTTOM_EDGE": "#eab308",
        "LEFT_EDGE": "#eab308",
        "RIGHT_EDGE": "#eab308",
        "TOP_LEFT_CORNER": "#22c55e",
        "TOP_RIGHT_CORNER": "#22c55e",
        "BOTTOM_LEFT_CORNER": "#22c55e",
        "BOTTOM_RIGHT_CORNER": "#22c55e",
        "CENTER_SURFACE": "#a855f7",
        "TITLE_AREA": "#14b8a6",
        "PRICE_BOX_AREA": "#ef4444",
    }
    for region in regions:
        draw.rectangle((region.x_min, region.y_min, region.x_max, region.y_max), outline=palette.get(region.region_type, "#ffffff"), width=3)
    buffer = io.BytesIO()
    rendered.save(buffer, format="PNG")
    return buffer.getvalue()


def _build_evidence_overlay_artifact(image: Image.Image, *, evidence: list[_EvidenceDraft]) -> bytes:
    rendered = _image_to_rgb(image)
    draw = ImageDraw.Draw(rendered)
    palette = {
        "EDGE_ANOMALY": "#f59e0b",
        "CORNER_ANOMALY": "#22c55e",
        "SPINE_ANOMALY": "#f97316",
        "SURFACE_ANOMALY": "#a855f7",
        "COLOR_ANOMALY": "#06b6d4",
        "CONTRAST_ANOMALY": "#84cc16",
        "GEOMETRY_ANOMALY": "#ef4444",
    }
    for row in evidence:
        draw.rectangle((row.x_min, row.y_min, row.x_max, row.y_max), outline=palette.get(row.evidence_category, "#ffffff"), width=3)
    buffer = io.BytesIO()
    rendered.save(buffer, format="PNG")
    return buffer.getvalue()


def _build_debug_preview_artifact(image: Image.Image, *, regions: list[_RegionDraft], evidence: list[_EvidenceDraft]) -> bytes:
    rendered = _image_to_rgb(image)
    draw = ImageDraw.Draw(rendered)
    for region in regions:
        draw.rectangle((region.x_min, region.y_min, region.x_max, region.y_max), outline="#ffffff", width=1)
    for row in evidence[:6]:
        draw.rectangle((row.x_min, row.y_min, row.x_max, row.y_max), outline="#ef4444", width=4)
    buffer = io.BytesIO()
    rendered.save(buffer, format="PNG")
    return buffer.getvalue()


def build_defect_manifest(
    *,
    context: _DefectContext,
    regions: list[_RegionDraft],
    evidence: list[_EvidenceDraft],
    issues: list[_IssueDraft],
    artifact_checksums: list[dict[str, str]],
) -> tuple[dict[str, Any], str]:
    quality_gates = [row for row in issues if row.issue_type in _QUALITY_GATE_TYPES]
    evidence_summary = {
        "total_evidence_count": len(evidence),
        "low_confidence_count": sum(1 for row in evidence if row.confidence_score < 0.35),
        "high_confidence_count": sum(1 for row in evidence if row.confidence_score >= 0.7),
        "category_counts": {
            category: sum(1 for row in evidence if row.evidence_category == category)
            for category in sorted({row.evidence_category for row in evidence})
        },
    }
    manifest: dict[str, Any] = {
        "detection_engine_version": DETECTION_ENGINE_VERSION,
        "lineage": {
            "original_scan_checksum": context.scan_image.sha256_checksum,
            "normalization_checksum": context.normalization_run.normalization_checksum,
            "boundary_checksum": context.boundary_run.boundary_checksum,
            "ocr_checksum": context.ocr_run.ocr_checksum if context.ocr_run else None,
            "reconciliation_checksum": context.reconciliation_run.reconciliation_checksum if context.reconciliation_run else None,
            "source_checksum": context.source_checksum if hasattr(context, "source_checksum") else context.source_artifact.artifact_checksum,
        },
        "condition_regions": [
            {
                "region_type": row.region_type,
                "bbox": [row.x_min, row.y_min, row.x_max, row.y_max],
                "region_checksum": row.region_checksum,
                "metadata": row.metadata_json,
            }
            for row in regions
        ],
        "scan_quality_gates": [
            {
                "issue_type": row.issue_type,
                "severity": row.severity,
                "issue_message": row.issue_message,
                "metadata_json": row.metadata_json,
            }
            for row in quality_gates
        ],
        "evidence": [
            {
                "region_type": row.region_type,
                "evidence_type": row.evidence_type,
                "evidence_category": row.evidence_category,
                "severity_hint": row.severity_hint,
                "confidence_score": row.confidence_score,
                "bbox": [row.x_min, row.y_min, row.x_max, row.y_max],
                "measurement_json": row.measurement_json,
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
        "evidence_summary": evidence_summary,
    }
    return manifest, _hash_payload(manifest)


def _serialize_json_artifact(payload: Any) -> bytes:
    return json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"), indent=2).encode("utf-8")


def _make_history(event_type: str, event_message: str, metadata_json: dict[str, Any]) -> _HistoryDraft:
    return _HistoryDraft(event_type=event_type, event_message=event_message, metadata_json=metadata_json)


def _resolve_context(session: Session, *, owner_user_id: int, payload: ScanDefectRunCreate) -> _DefectContext:
    scan_image = session.get(ScanImage, payload.scan_image_id)
    if scan_image is None or int(scan_image.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan image not found.")

    boundary_stmt = select(ScanBoundaryRun).where(
        ScanBoundaryRun.owner_user_id == owner_user_id,
        ScanBoundaryRun.scan_image_id == payload.scan_image_id,
        ScanBoundaryRun.boundary_status == "COMPLETE",
    )
    if payload.boundary_run_id is not None:
        boundary_stmt = boundary_stmt.where(ScanBoundaryRun.id == payload.boundary_run_id)
    boundary_run = session.exec(boundary_stmt.order_by(col(ScanBoundaryRun.id).desc())).first()
    if boundary_run is None:
        raise HTTPException(status_code=409, detail="A complete boundary run is required before defect analysis.")

    normalization_run = session.get(ScanNormalizationRun, int(boundary_run.normalization_run_id))
    if normalization_run is None:
        raise HTTPException(status_code=409, detail="Boundary run is missing its normalization lineage.")

    source_artifact = session.get(ScanNormalizationArtifact, int(boundary_run.source_artifact_id))
    if source_artifact is None:
        raise HTTPException(status_code=409, detail="Boundary run is missing its normalized source artifact.")

    ocr_run: ScanOcrRun | None = None
    if payload.ocr_run_id is not None:
        ocr_run = session.get(ScanOcrRun, payload.ocr_run_id)
        if ocr_run is None or int(ocr_run.owner_user_id) != owner_user_id or int(ocr_run.scan_image_id) != payload.scan_image_id:
            raise HTTPException(status_code=404, detail="OCR run not found.")
    else:
        ocr_run = session.exec(
            select(ScanOcrRun)
            .where(
                ScanOcrRun.owner_user_id == owner_user_id,
                ScanOcrRun.scan_image_id == payload.scan_image_id,
                ScanOcrRun.boundary_run_id == boundary_run.id,
                ScanOcrRun.ocr_status == "COMPLETE",
            )
            .order_by(col(ScanOcrRun.id).desc())
        ).first()

    reconciliation_run: ScanReconciliationRun | None = None
    if payload.reconciliation_run_id is not None:
        reconciliation_run = session.get(ScanReconciliationRun, payload.reconciliation_run_id)
        if reconciliation_run is None or int(reconciliation_run.owner_user_id) != owner_user_id or int(reconciliation_run.scan_image_id) != payload.scan_image_id:
            raise HTTPException(status_code=404, detail="Reconciliation run not found.")
    else:
        reconciliation_run = session.exec(
            select(ScanReconciliationRun)
            .where(
                ScanReconciliationRun.owner_user_id == owner_user_id,
                ScanReconciliationRun.scan_image_id == payload.scan_image_id,
                ScanReconciliationRun.boundary_run_id == boundary_run.id,
                ScanReconciliationRun.reconciliation_status != "FAILED",
            )
            .order_by(col(ScanReconciliationRun.id).desc())
        ).first()

    return _DefectContext(
        scan_image=scan_image,
        normalization_run=normalization_run,
        boundary_run=boundary_run,
        source_artifact=source_artifact,
        ocr_run=ocr_run,
        reconciliation_run=reconciliation_run,
    )


def _detail_from_run(session: Session, settings: Settings, run: ScanDefectRun) -> ScanDefectRunDetail:
    regions = session.exec(
        select(ScanDefectRegion)
        .where(ScanDefectRegion.defect_run_id == run.id)
        .order_by(col(ScanDefectRegion.id))
    ).all()
    evidence = session.exec(
        select(ScanDefectEvidence)
        .where(ScanDefectEvidence.defect_run_id == run.id)
        .order_by(col(ScanDefectEvidence.id))
    ).all()
    artifacts = session.exec(
        select(ScanDefectArtifact)
        .where(ScanDefectArtifact.defect_run_id == run.id)
        .order_by(col(ScanDefectArtifact.id))
    ).all()
    issues = session.exec(
        select(ScanDefectIssue)
        .where(ScanDefectIssue.defect_run_id == run.id)
        .order_by(col(ScanDefectIssue.id))
    ).all()
    history = session.exec(
        select(ScanDefectHistory)
        .where(ScanDefectHistory.defect_run_id == run.id)
        .order_by(col(ScanDefectHistory.id))
    ).all()

    art_reads = [
        ScanDefectArtifactRead.model_validate(row).model_copy(
            update={"preview_data_url": _artifact_preview_data_url(settings, row)}
        )
        for row in artifacts
    ]
    run_data = ScanDefectRunRead.model_validate(run).model_dump()
    quality_gates = [
        {
            "issue_type": row.issue_type,
            "severity": row.severity,
            "issue_message": row.issue_message,
            "metadata_json": row.metadata_json,
        }
        for row in issues
        if row.issue_type in _QUALITY_GATE_TYPES
    ]
    quality_gate_counts = {
        issue_type: sum(1 for row in issues if row.issue_type == issue_type)
        for issue_type in sorted({row.issue_type for row in issues if row.issue_type in _QUALITY_GATE_TYPES})
    }
    return ScanDefectRunDetail(
        **run_data,
        regions=[ScanDefectRegionRead.model_validate(row) for row in regions],
        evidence=[ScanDefectEvidenceRead.model_validate(row) for row in evidence],
        artifacts=art_reads,
        issues=[ScanDefectIssueRead.model_validate(row) for row in issues],
        history=[ScanDefectHistoryRead.model_validate(row) for row in history],
        original_scan_checksum=session.get(ScanImage, int(run.scan_image_id)).sha256_checksum if session.get(ScanImage, int(run.scan_image_id)) else None,
        normalization_checksum=session.get(ScanNormalizationRun, int(run.normalization_run_id)).normalization_checksum if session.get(ScanNormalizationRun, int(run.normalization_run_id)) else None,
        boundary_checksum=session.get(ScanBoundaryRun, int(run.boundary_run_id)).boundary_checksum if session.get(ScanBoundaryRun, int(run.boundary_run_id)) else None,
        ocr_checksum=session.get(ScanOcrRun, int(run.ocr_run_id)).ocr_checksum if run.ocr_run_id and session.get(ScanOcrRun, int(run.ocr_run_id)) else None,
        reconciliation_checksum=session.get(ScanReconciliationRun, int(run.reconciliation_run_id)).reconciliation_checksum if run.reconciliation_run_id and session.get(ScanReconciliationRun, int(run.reconciliation_run_id)) else None,
        source_preview_data_url=_load_source_preview(settings, session.get(ScanNormalizationArtifact, int(run.source_artifact_id))) if session.get(ScanNormalizationArtifact, int(run.source_artifact_id)) else None,
        quality_gates=quality_gates,
        evidence_summary=dict(run.output_manifest_json.get("evidence_summary") or {}),
        quality_gate_counts=quality_gate_counts,
    )


def run_scan_defect_foundation(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: ScanDefectRunCreate,
) -> tuple[ScanDefectRunDetail, bool]:
    context = _resolve_context(session, owner_user_id=owner_user_id, payload=payload)
    try:
        with Image.open(_resolve_normalization_artifact_path(settings, context.source_artifact)) as image_fp:
            image = _image_to_rgb(image_fp)
    except (FileNotFoundError, OSError, ValueError, UnidentifiedImageError) as exc:
        raise HTTPException(status_code=409, detail="Normalized source artifact is not available for defect analysis.") from exc

    regions = derive_condition_regions(
        boundary_run=context.boundary_run,
        image=image,
        source_checksum=context.source_artifact.artifact_checksum,
    )
    if not regions:
        raise HTTPException(status_code=409, detail="Defect region derivation failed.")

    issues = run_scan_quality_gates(
        scan_image=context.scan_image,
        boundary_run=context.boundary_run,
        image=image,
        cover_region=regions[0],
    )
    evidence = detect_baseline_visual_anomalies(image=image, regions=regions)
    if not evidence:
        issues.append(
            _IssueDraft(
                issue_type="LOW_EVIDENCE_CONFIDENCE",
                severity="INFO",
                issue_message="No provisional baseline evidence exceeded the minimum anchoring floor.",
                metadata_json={"minimum_confidence_floor": 0.05},
            )
        )
    if any(row.issue_type in _QUALITY_GATE_TYPES for row in issues):
        issues.append(
            _IssueDraft(
                issue_type="QUALITY_GATE_FAILED",
                severity="WARNING",
                issue_message="One or more scan-quality gates reduce defect-foundation reliability.",
                metadata_json={"quality_gate_count": sum(1 for row in issues if row.issue_type in _QUALITY_GATE_TYPES)},
            )
        )
    if sum(1 for row in issues if row.issue_type in _QUALITY_GATE_TYPES) >= 2:
        issues.append(
            _IssueDraft(
                issue_type="INSUFFICIENT_IMAGE_QUALITY",
                severity="WARNING",
                issue_message="Compound scan-quality issues make downstream defect specialization less reliable.",
                metadata_json={"quality_gate_count": sum(1 for row in issues if row.issue_type in _QUALITY_GATE_TYPES)},
            )
        )
    low_conf_evidence = sum(1 for row in evidence if row.confidence_score < 0.35)
    if low_conf_evidence:
        issues.append(
            _IssueDraft(
                issue_type="LOW_EVIDENCE_CONFIDENCE",
                severity="INFO",
                issue_message="Baseline evidence contains low-confidence anchors that should remain visible for replay safety.",
                metadata_json={"low_confidence_count": low_conf_evidence},
            )
        )
    margin_sum = sum(int(value) for value in (context.boundary_run.output_manifest_json.get("background", {}).get("scan_margins") or {}).values())
    if margin_sum > int(round((image.width + image.height) * 0.4)):
        issues.append(
            _IssueDraft(
                issue_type="EXCESSIVE_BACKGROUND_ARTIFACTS",
                severity="INFO",
                issue_message="Boundary margins suggest meaningful background remains around the detected cover.",
                metadata_json={"margin_sum_px": margin_sum},
            )
        )
    if context.reconciliation_run and context.ocr_run and int(context.reconciliation_run.ocr_run_id) != int(context.ocr_run.id or 0):
        issues.append(
            _IssueDraft(
                issue_type="UNSTABLE_INPUT_LINEAGE",
                severity="WARNING",
                issue_message="Selected reconciliation run does not align with the resolved OCR lineage.",
                metadata_json={
                    "ocr_run_id": int(context.ocr_run.id or 0),
                    "reconciliation_ocr_run_id": int(context.reconciliation_run.ocr_run_id or 0),
                },
            )
        )

    provisional_artifacts = [
        _ArtifactDraft(
            artifact_type="DEFECT_REGION_MAP",
            body=_build_region_map_artifact(image, regions=regions),
            metadata_json={"format": "png", "region_count": len(regions)},
            ext=".png",
        ),
        _ArtifactDraft(
            artifact_type="QUALITY_GATE_REPORT",
            body=_serialize_json_artifact(
                {
                    "quality_gates": [
                        {
                            "issue_type": row.issue_type,
                            "severity": row.severity,
                            "message": row.issue_message,
                            "metadata_json": row.metadata_json,
                        }
                        for row in issues
                        if row.issue_type in _QUALITY_GATE_TYPES
                    ]
                }
            ),
            metadata_json={"format": "json", "quality_gate_count": sum(1 for row in issues if row.issue_type in _QUALITY_GATE_TYPES)},
            ext=".json",
        ),
        _ArtifactDraft(
            artifact_type="BASELINE_EVIDENCE_OVERLAY",
            body=_build_evidence_overlay_artifact(image, evidence=evidence),
            metadata_json={"format": "png", "evidence_count": len(evidence)},
            ext=".png",
        ),
        _ArtifactDraft(
            artifact_type="DEFECT_DEBUG_PREVIEW",
            body=_build_debug_preview_artifact(image, regions=regions, evidence=evidence),
            metadata_json={"format": "png", "highlighted_evidence_count": min(len(evidence), 6)},
            ext=".png",
        ),
    ]

    provisional_manifest, defect_checksum = build_defect_manifest(
        context=context,
        regions=regions,
        evidence=evidence,
        issues=issues,
        artifact_checksums=[
            {"artifact_type": row.artifact_type, "artifact_checksum": _sha256_bytes(row.body)}
            for row in provisional_artifacts
        ],
    )
    manifest_artifact = _ArtifactDraft(
        artifact_type="DEFECT_MANIFEST",
        body=_serialize_json_artifact(provisional_manifest),
        metadata_json={"format": "json"},
        ext=".json",
    )
    artifacts = provisional_artifacts + [manifest_artifact]

    existing = session.exec(
        select(ScanDefectRun).where(
            ScanDefectRun.owner_user_id == owner_user_id,
            ScanDefectRun.defect_checksum == defect_checksum,
        )
    ).first()
    if existing is not None:
        return _detail_from_run(session, settings, existing), False

    input_manifest = {
        "scan_image_id": context.scan_image.id,
        "normalization_run_id": context.normalization_run.id,
        "boundary_run_id": context.boundary_run.id,
        "ocr_run_id": context.ocr_run.id if context.ocr_run else None,
        "reconciliation_run_id": context.reconciliation_run.id if context.reconciliation_run else None,
        "source_artifact_id": context.source_artifact.id,
        "lineage": {
            "original_scan_checksum": context.scan_image.sha256_checksum,
            "normalization_checksum": context.normalization_run.normalization_checksum,
            "boundary_checksum": context.boundary_run.boundary_checksum,
            "ocr_checksum": context.ocr_run.ocr_checksum if context.ocr_run else None,
            "reconciliation_checksum": context.reconciliation_run.reconciliation_checksum if context.reconciliation_run else None,
            "source_checksum": context.source_artifact.artifact_checksum,
        },
    }
    run = ScanDefectRun(
        owner_user_id=owner_user_id,
        scan_image_id=int(context.scan_image.id or 0),
        normalization_run_id=int(context.normalization_run.id or 0),
        boundary_run_id=int(context.boundary_run.id or 0),
        ocr_run_id=int(context.ocr_run.id or 0) if context.ocr_run else None,
        reconciliation_run_id=int(context.reconciliation_run.id or 0) if context.reconciliation_run else None,
        source_artifact_id=int(context.source_artifact.id or 0),
        source_checksum=context.source_artifact.artifact_checksum,
        defect_checksum=defect_checksum,
        defect_status="COMPLETE",
        detection_engine_version=DETECTION_ENGINE_VERSION,
        input_manifest_json=input_manifest,
        output_manifest_json=provisional_manifest,
        completed_at=utc_now(),
    )
    session.add(run)
    session.flush()

    region_ids: dict[str, int] = {}
    for row in regions:
        region_model = ScanDefectRegion(
            owner_user_id=owner_user_id,
            defect_run_id=int(run.id or 0),
            region_type=row.region_type,
            x_min=row.x_min,
            y_min=row.y_min,
            x_max=row.x_max,
            y_max=row.y_max,
            width_px=row.width_px,
            height_px=row.height_px,
            region_checksum=row.region_checksum,
            metadata_json=row.metadata_json,
        )
        session.add(region_model)
        session.flush()
        region_ids[row.region_type] = int(region_model.id or 0)

    for row in evidence:
        session.add(
            ScanDefectEvidence(
                owner_user_id=owner_user_id,
                defect_run_id=int(run.id or 0),
                region_id=region_ids[row.region_type],
                evidence_type=row.evidence_type,
                evidence_category=row.evidence_category,
                severity_hint=row.severity_hint,
                confidence_score=row.confidence_score,
                x_min=row.x_min,
                y_min=row.y_min,
                x_max=row.x_max,
                y_max=row.y_max,
                measurement_json=row.measurement_json,
                metadata_json=row.metadata_json,
            )
        )

    for row in issues:
        session.add(
            ScanDefectIssue(
                owner_user_id=owner_user_id,
                defect_run_id=int(run.id or 0),
                issue_type=row.issue_type,
                severity=row.severity,
                issue_message=row.issue_message,
                metadata_json=row.metadata_json,
            )
        )

    history_rows = [
        _make_history("DEFECT_RUN_CREATED", "Created deterministic defect-foundation run.", {"defect_checksum": defect_checksum}),
        _make_history("CONDITION_REGIONS_DERIVED", "Derived stable condition regions from cover geometry.", {"region_count": len(regions)}),
        _make_history(
            "QUALITY_GATES_EVALUATED",
            "Evaluated deterministic scan-quality gates.",
            {"quality_gate_count": sum(1 for row in issues if row.issue_type in _QUALITY_GATE_TYPES)},
        ),
        _make_history("BASELINE_EVIDENCE_RECORDED", "Recorded provisional baseline anomaly evidence.", {"evidence_count": len(evidence)}),
        _make_history("DEFECT_MANIFEST_WRITTEN", "Persisted replay-safe defect manifest and artifacts.", {"artifact_count": len(artifacts)}),
    ]
    for row in history_rows:
        session.add(
            ScanDefectHistory(
                owner_user_id=owner_user_id,
                defect_run_id=int(run.id or 0),
                event_type=row.event_type,
                event_message=row.event_message,
                event_checksum=_hash_payload(
                    {
                        "defect_run_id": int(run.id or 0),
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
            scan_image_id=int(context.scan_image.id or 0),
            defect_run_id=int(run.id or 0),
            artifact_type=row.artifact_type,
            ext=row.ext,
        )
        _save_artifact_bytes(settings, relative_path=relative_path, body=row.body)
        session.add(
            ScanDefectArtifact(
                owner_user_id=owner_user_id,
                defect_run_id=int(run.id or 0),
                artifact_type=row.artifact_type,
                storage_path=relative_path,
                artifact_checksum=_sha256_bytes(row.body),
                metadata_json=row.metadata_json,
            )
        )

    session.commit()
    session.refresh(run)
    return _detail_from_run(session, settings, run), True


def get_scan_defect_run_owner(session: Session, settings: Settings, *, owner_user_id: int, run_id: int) -> ScanDefectRunDetail:
    row = session.get(ScanDefectRun, run_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Defect run not found.")
    return _detail_from_run(session, settings, row)


def get_scan_defect_artifact_owner(session: Session, settings: Settings, *, owner_user_id: int, artifact_id: int) -> ScanDefectArtifactRead:
    row = session.get(ScanDefectArtifact, artifact_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Defect artifact not found.")
    return ScanDefectArtifactRead.model_validate(row).model_copy(
        update={"preview_data_url": _artifact_preview_data_url(settings, row)}
    )


def _run_list_response(rows: list[ScanDefectRun], *, limit: int, offset: int, total_items: int) -> ScanDefectRunListResponse:
    status_counts = {
        status_key: sum(1 for row in rows if row.defect_status == status_key)
        for status_key in sorted({row.defect_status for row in rows})
    }
    quality_gate_failure_count = sum(
        1
        for row in rows
        if any(issue.get("issue_type") == "QUALITY_GATE_FAILED" for issue in row.output_manifest_json.get("issues") or [])
    )
    low_confidence_evidence_count = sum(int((row.output_manifest_json.get("evidence_summary") or {}).get("low_confidence_count") or 0) for row in rows)
    return ScanDefectRunListResponse(
        items=[ScanDefectRunRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        status_counts=status_counts,
        quality_gate_failure_count=quality_gate_failure_count,
        low_confidence_evidence_count=low_confidence_evidence_count,
    )


def list_scan_defect_runs_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanDefectRunListResponse:
    limit, offset = clamp_scan_defect_pagination(limit=limit, offset=offset)
    stmt = select(ScanDefectRun).where(ScanDefectRun.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanDefectRun).where(ScanDefectRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanDefectRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanDefectRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanDefectRun.created_at).desc(), col(ScanDefectRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_defect_runs_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanDefectRunListResponse:
    limit, offset = clamp_scan_defect_pagination(limit=limit, offset=offset)
    stmt = select(ScanDefectRun)
    count_stmt = select(func.count()).select_from(ScanDefectRun)
    if owner_user_id is not None:
        stmt = stmt.where(ScanDefectRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanDefectRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanDefectRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanDefectRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanDefectRun.created_at).desc(), col(ScanDefectRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_defect_evidence_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    defect_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanDefectEvidenceListResponse:
    limit, offset = clamp_scan_defect_pagination(limit=limit, offset=offset)
    stmt = select(ScanDefectEvidence).join(ScanDefectRun, ScanDefectRun.id == ScanDefectEvidence.defect_run_id).where(ScanDefectEvidence.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanDefectEvidence).join(ScanDefectRun, ScanDefectRun.id == ScanDefectEvidence.defect_run_id).where(ScanDefectEvidence.owner_user_id == owner_user_id)
    if defect_run_id is not None:
        stmt = stmt.where(ScanDefectEvidence.defect_run_id == defect_run_id)
        count_stmt = count_stmt.where(ScanDefectEvidence.defect_run_id == defect_run_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanDefectRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanDefectRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanDefectEvidence.created_at), col(ScanDefectEvidence.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    category_counts = {
        key: sum(1 for row in rows if row.evidence_category == key)
        for key in sorted({row.evidence_category for row in rows})
    }
    return ScanDefectEvidenceListResponse(
        items=[ScanDefectEvidenceRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        category_counts=category_counts,
        low_confidence_count=sum(1 for row in rows if float(row.confidence_score) < 0.35),
    )


def list_scan_defect_regions_owner(
    session: Session,
    *,
    owner_user_id: int,
    defect_run_id: int | None,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanDefectRegionListResponse:
    limit, offset = clamp_scan_defect_pagination(limit=limit, offset=offset)
    stmt = select(ScanDefectRegion).join(ScanDefectRun, ScanDefectRun.id == ScanDefectRegion.defect_run_id).where(ScanDefectRegion.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanDefectRegion).join(ScanDefectRun, ScanDefectRun.id == ScanDefectRegion.defect_run_id).where(ScanDefectRegion.owner_user_id == owner_user_id)
    if defect_run_id is not None:
        stmt = stmt.where(ScanDefectRegion.defect_run_id == defect_run_id)
        count_stmt = count_stmt.where(ScanDefectRegion.defect_run_id == defect_run_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanDefectRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanDefectRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanDefectRegion.created_at), col(ScanDefectRegion.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanDefectRegionListResponse(
        items=[ScanDefectRegionRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        region_type_counts={
            key: sum(1 for row in rows if row.region_type == key)
            for key in sorted({row.region_type for row in rows})
        },
    )


def list_scan_defect_issues_owner(
    session: Session,
    *,
    owner_user_id: int,
    defect_run_id: int | None,
    limit: int,
    offset: int,
    only_quality_gates: bool = False,
) -> ScanDefectIssueListResponse:
    limit, offset = clamp_scan_defect_pagination(limit=limit, offset=offset)
    stmt = select(ScanDefectIssue).where(ScanDefectIssue.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanDefectIssue).where(ScanDefectIssue.owner_user_id == owner_user_id)
    if defect_run_id is not None:
        stmt = stmt.where(ScanDefectIssue.defect_run_id == defect_run_id)
        count_stmt = count_stmt.where(ScanDefectIssue.defect_run_id == defect_run_id)
    if only_quality_gates:
        stmt = stmt.where(col(ScanDefectIssue.issue_type).in_(tuple(sorted(_QUALITY_GATE_TYPES))))
        count_stmt = count_stmt.where(col(ScanDefectIssue.issue_type).in_(tuple(sorted(_QUALITY_GATE_TYPES))))
    rows = session.exec(stmt.order_by(col(ScanDefectIssue.created_at), col(ScanDefectIssue.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanDefectIssueListResponse(
        items=[ScanDefectIssueRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        issue_type_counts={key: sum(1 for row in rows if row.issue_type == key) for key in sorted({row.issue_type for row in rows})},
    )


def list_scan_defect_issues_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
    only_quality_gates: bool = False,
) -> ScanDefectIssueListResponse:
    limit, offset = clamp_scan_defect_pagination(limit=limit, offset=offset)
    stmt = select(ScanDefectIssue)
    count_stmt = select(func.count()).select_from(ScanDefectIssue)
    if owner_user_id is not None:
        stmt = stmt.where(ScanDefectIssue.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanDefectIssue.owner_user_id == owner_user_id)
    if only_quality_gates:
        stmt = stmt.where(col(ScanDefectIssue.issue_type).in_(tuple(sorted(_QUALITY_GATE_TYPES))))
        count_stmt = count_stmt.where(col(ScanDefectIssue.issue_type).in_(tuple(sorted(_QUALITY_GATE_TYPES))))
    rows = session.exec(stmt.order_by(col(ScanDefectIssue.created_at), col(ScanDefectIssue.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanDefectIssueListResponse(
        items=[ScanDefectIssueRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        issue_type_counts={key: sum(1 for row in rows if row.issue_type == key) for key in sorted({row.issue_type for row in rows})},
    )


def list_scan_defect_failures_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanDefectFailureListResponse:
    limit, offset = clamp_scan_defect_pagination(limit=limit, offset=offset)
    stmt = select(ScanDefectRun).where(ScanDefectRun.defect_status == "FAILED")
    count_stmt = select(func.count()).select_from(ScanDefectRun).where(ScanDefectRun.defect_status == "FAILED")
    if owner_user_id is not None:
        stmt = stmt.where(ScanDefectRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanDefectRun.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanDefectRun.created_at).desc(), col(ScanDefectRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanDefectFailureListResponse(
        items=[ScanDefectRunRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )
