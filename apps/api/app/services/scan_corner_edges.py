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
    ScanCornerEdgeArtifact,
    ScanCornerEdgeEvidence,
    ScanCornerEdgeHistory,
    ScanCornerEdgeIssue,
    ScanCornerEdgeRun,
    ScanDefectEvidence,
    ScanDefectRegion,
    ScanDefectRun,
    ScanImage,
    ScanNormalizationArtifact,
    ScanNormalizationRun,
)
from app.schemas.scan_corner_edges import (
    ScanCornerEdgeArtifactRead,
    ScanCornerEdgeEvidenceListResponse,
    ScanCornerEdgeEvidenceRead,
    ScanCornerEdgeFailureListResponse,
    ScanCornerEdgeHistoryRead,
    ScanCornerEdgeIssueListResponse,
    ScanCornerEdgeIssueRead,
    ScanCornerEdgeRunCreate,
    ScanCornerEdgeRunDetail,
    ScanCornerEdgeRunListResponse,
    ScanCornerEdgeRunRead,
)
from app.services.scan_defects import _load_source_preview, _resolve_normalization_artifact_path

ENGINE_VERSION = "P40-08-v1"
_PREVIEW_MAX = 420
_LOW_CONFIDENCE_THRESHOLD = 0.35

CORNER_REGION_ORDER = (
    "TOP_LEFT_CORNER",
    "TOP_RIGHT_CORNER",
    "BOTTOM_LEFT_CORNER",
    "BOTTOM_RIGHT_CORNER",
)
EDGE_REGION_ORDER = ("TOP_EDGE", "BOTTOM_EDGE", "LEFT_EDGE", "RIGHT_EDGE")
REGION_PROCESS_ORDER = CORNER_REGION_ORDER + EDGE_REGION_ORDER


@dataclass(frozen=True)
class _RegionIsolation:
    region: ScanDefectRegion
    crop: Image.Image


@dataclass(frozen=True)
class _EvidenceDraft:
    region_type: str
    evidence_type: str
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    width_px: int
    height_px: int
    edge_distance_px: int
    corner_overlap_ratio: float
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
    from app.models.scan_corner_edges import utc_now as _utc_now

    return _utc_now()


def clamp_scan_corner_edge_pagination(*, limit: int, offset: int) -> tuple[int, int]:
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


def _resolve_corner_edge_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.scan_corner_edges_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("scan corner edge storage path escapes configured root")
    return target


def _artifact_storage_path(
    *,
    owner_user_id: int,
    scan_image_id: int,
    corner_edge_run_id: int,
    artifact_type: str,
    ext: str,
) -> str:
    safe_type = artifact_type.lower()
    return f"scan-corner-edges/{owner_user_id}/{scan_image_id}/{corner_edge_run_id}/{safe_type}{ext}".replace("\\", "/")


def _save_artifact_bytes(settings: Settings, *, relative_path: str, body: bytes) -> None:
    target = _resolve_corner_edge_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(body)


def _artifact_preview_data_url(settings: Settings, row: ScanCornerEdgeArtifact) -> str | None:
    if not row.storage_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        return None
    try:
        body = _resolve_corner_edge_storage_path(settings, row.storage_path).read_bytes()
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


def isolate_corner_regions(
    *,
    image: Image.Image,
    regions: list[ScanDefectRegion],
) -> dict[str, _RegionIsolation]:
    region_map = {row.region_type: row for row in regions}
    isolated: dict[str, _RegionIsolation] = {}
    rgb = _image_to_rgb(image)
    for region_type in CORNER_REGION_ORDER:
        row = region_map.get(region_type)
        if row is None:
            continue
        crop = rgb.crop((row.x_min, row.y_min, row.x_max + 1, row.y_max + 1))
        isolated[region_type] = _RegionIsolation(region=row, crop=crop)
    return isolated


def isolate_edge_regions(
    *,
    image: Image.Image,
    regions: list[ScanDefectRegion],
) -> dict[str, _RegionIsolation]:
    region_map = {row.region_type: row for row in regions}
    isolated: dict[str, _RegionIsolation] = {}
    rgb = _image_to_rgb(image)
    for region_type in EDGE_REGION_ORDER:
        row = region_map.get(region_type)
        if row is None:
            continue
        crop = rgb.crop((row.x_min, row.y_min, row.x_max + 1, row.y_max + 1))
        isolated[region_type] = _RegionIsolation(region=row, crop=crop)
    return isolated


def _corner_outer_box(region_type: str, width: int, height: int) -> tuple[int, int, int, int]:
    band_w = max(2, int(width * 0.44))
    band_h = max(2, int(height * 0.44))
    if region_type == "TOP_LEFT_CORNER":
        return (0, 0, band_w, band_h)
    if region_type == "TOP_RIGHT_CORNER":
        return (max(0, width - band_w), 0, width, band_h)
    if region_type == "BOTTOM_LEFT_CORNER":
        return (0, max(0, height - band_h), band_w, height)
    return (max(0, width - band_w), max(0, height - band_h), width, height)


def _edge_distance_for_region(region_type: str, region: ScanDefectRegion, local_box: tuple[int, int, int, int]) -> int:
    lx0, ly0, _, _ = local_box
    if region_type.endswith("_CORNER"):
        return min(lx0, ly0)
    if region_type == "TOP_EDGE":
        return ly0
    if region_type == "BOTTOM_EDGE":
        return max(0, region.height_px - ly0)
    if region_type == "LEFT_EDGE":
        return lx0
    return max(0, region.width_px - lx0)


def _classify_corner_evidence(*, contour_dev: float, sharpness: float, break_ratio: float) -> str:
    if contour_dev >= 0.28:
        return "CORNER_ROUNDING"
    if sharpness <= 0.22:
        return "CORNER_BLUNTING"
    if break_ratio >= 0.18:
        return "BORDER_BREAK"
    return "CORNER_BLUNTING"


def _classify_edge_evidence(*, break_ratio: float, color_delta: float, localized: bool) -> str:
    if color_delta >= 0.24:
        return "EDGE_COLOR_BREAK"
    if localized and break_ratio >= 0.14:
        return "EDGE_CHIP"
    if break_ratio >= 0.2:
        return "BORDER_BREAK"
    if break_ratio >= 0.11:
        return "EDGE_FLAKE"
    if break_ratio >= 0.07:
        return "EDGE_STRESS"
    return "BORDER_ROUGHNESS"


def _severity_hint(normalized_size: float, break_ratio: float) -> str:
    score = normalized_size * 0.5 + break_ratio * 0.5
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
                float(measurements["border_break_ratio"]) * 0.45
                + float(measurements["contour_deviation"]) * 0.3
                + float(measurements["normalized_relative_size"]) * 0.25,
            ),
        ),
        6,
    )


def calculate_corner_edge_measurements(
    *,
    region: ScanDefectRegion,
    crop: Image.Image,
    local_box: tuple[int, int, int, int],
    outer_mean: float,
    inner_mean: float,
    edge_mean: float,
    continuity: float,
) -> dict[str, Any]:
    lx0, ly0, lx1, ly1 = local_box
    segment = crop.crop((lx0, ly0, lx1, ly1))
    gray = segment.convert("L")
    stat = ImageStat.Stat(gray)
    area = max(1, (lx1 - lx0) * (ly1 - ly0))
    brightness_variance = float(stat.stddev[0]) if stat.stddev else 0.0
    brightness_delta = abs(outer_mean - inner_mean) / 128.0
    contrast_delta = abs(float(stat.mean[0]) - inner_mean) / 128.0 if stat.mean else 0.0
    contour_dev = abs(outer_mean - inner_mean) / max(1.0, inner_mean + 8.0)
    break_ratio = max(0.0, (edge_mean - inner_mean) / max(1.0, inner_mean + 10.0))
    normalized_size = area / max(1, region.width_px * region.height_px)
    overlap = area / max(1, region.width_px * region.height_px)
    return {
        "pixel_area": area,
        "edge_distance_px": _edge_distance_for_region(region.region_type, region, local_box),
        "contour_deviation": round(min(1.0, contour_dev), 6),
        "edge_continuity_score": round(max(0.0, min(1.0, continuity)), 6),
        "border_break_ratio": round(min(1.0, break_ratio), 6),
        "brightness_delta": round(brightness_delta, 6),
        "contrast_delta": round(contrast_delta, 6),
        "brightness_variance": round(brightness_variance, 6),
        "corner_overlap_ratio": round(overlap, 6),
        "normalized_relative_size": round(normalized_size, 6),
        "raw_outer_mean": round(outer_mean, 6),
        "raw_inner_mean": round(inner_mean, 6),
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
        if row.evidence_category not in {"EDGE_ANOMALY", "CORNER_ANOMALY", "SURFACE_ANOMALY"}:
            continue
        overlap_top = max(y_min, row.y_min)
        overlap_bottom = min(y_max, row.y_max)
        overlap_left = max(x_min, row.x_min)
        overlap_right = min(x_max, row.x_max)
        if overlap_bottom < overlap_top or overlap_right < overlap_left:
            continue
        overlap = ((overlap_bottom - overlap_top + 1) * (overlap_right - overlap_left + 1)) / area
        if overlap > best_overlap:
            best_overlap = overlap
            best_id = int(row.id or 0)
    return best_id


def detect_corner_wear(
    *,
    isolation: _RegionIsolation,
    defect_evidence: list[ScanDefectEvidence],
) -> list[_EvidenceDraft]:
    region = isolation.region
    crop = isolation.crop
    width, height = crop.size
    if width < 2 or height < 2:
        return []
    gray = crop.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    outer = _corner_outer_box(region.region_type, width, height)
    ox0, oy0, ox1, oy1 = outer
    inner = (
        max(0, ox0 + max(2, int(width * 0.18))),
        max(0, oy0 + max(2, int(height * 0.18))),
        min(width, ox1),
        min(height, oy1),
    )
    if inner[2] <= inner[0] or inner[3] <= inner[1]:
        return []
    outer_stat = ImageStat.Stat(edges.crop(outer))
    inner_stat = ImageStat.Stat(edges.crop(inner))
    outer_mean = float(outer_stat.mean[0]) if outer_stat.mean else 0.0
    inner_mean = float(inner_stat.mean[0]) if inner_stat.mean else 0.0
    contour_dev = abs(outer_mean - inner_mean) / max(1.0, inner_mean + 6.0)
    if contour_dev < 0.055:
        return []
    sharpness = inner_mean / max(1.0, outer_mean + 4.0)
    break_ratio = max(0.0, (outer_mean - inner_mean) / max(1.0, inner_mean + 8.0))
    evidence_type = _classify_corner_evidence(contour_dev=contour_dev, sharpness=sharpness, break_ratio=break_ratio)
    measurements = calculate_corner_edge_measurements(
        region=region,
        crop=crop,
        local_box=outer,
        outer_mean=outer_mean,
        inner_mean=inner_mean,
        edge_mean=outer_mean,
        continuity=1.0 - min(1.0, break_ratio),
    )
    confidence = _confidence_score(measurements)
    severity = _severity_hint(float(measurements["normalized_relative_size"]), float(measurements["border_break_ratio"]))
    abs_x_min = region.x_min + ox0
    abs_y_min = region.y_min + oy0
    abs_x_max = region.x_min + ox1 - 1
    abs_y_max = region.y_min + oy1 - 1
    return [
        _EvidenceDraft(
            region_type=region.region_type,
            evidence_type=evidence_type,
            x_min=abs_x_min,
            y_min=abs_y_min,
            x_max=abs_x_max,
            y_max=abs_y_max,
            width_px=max(1, abs_x_max - abs_x_min + 1),
            height_px=max(1, abs_y_max - abs_y_min + 1),
            edge_distance_px=int(measurements["edge_distance_px"]),
            corner_overlap_ratio=float(measurements["corner_overlap_ratio"]),
            confidence_score=confidence,
            severity_hint=severity,
            measurement_json=measurements,
            metadata_json={"outer_box_local": list(outer), "sharpness_ratio": round(sharpness, 6)},
            defect_evidence_id=_overlap_defect_evidence(
                defect_evidence=defect_evidence,
                x_min=abs_x_min,
                y_min=abs_y_min,
                x_max=abs_x_max,
                y_max=abs_y_max,
            ),
        )
    ]


def _edge_scan_scores(region_type: str, crop: Image.Image) -> list[float]:
    gray = crop.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    width, height = crop.size
    scores: list[float] = []
    if region_type in {"TOP_EDGE", "BOTTOM_EDGE"}:
        y = 0 if region_type == "TOP_EDGE" else height - 1
        for x in range(width):
            row = edges.crop((x, y, x + 1, y + 1))
            stat = ImageStat.Stat(row)
            scores.append(float(stat.mean[0]) if stat.mean else 0.0)
        return scores
    x = 0 if region_type == "LEFT_EDGE" else width - 1
    for y in range(height):
        col_img = edges.crop((x, y, x + 1, y + 1))
        stat = ImageStat.Stat(col_img)
        scores.append(float(stat.mean[0]) if stat.mean else 0.0)
    return scores


def detect_edge_wear(
    *,
    isolation: _RegionIsolation,
    defect_evidence: list[ScanDefectEvidence],
) -> list[_EvidenceDraft]:
    region = isolation.region
    crop = isolation.crop
    scores = _edge_scan_scores(region.region_type, crop)
    if not scores:
        return []
    ordered = sorted(scores)
    median = ordered[len(ordered) // 2]
    threshold = median + max(5.0, median * 0.26)
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
    drafts: list[_EvidenceDraft] = []
    width, height = crop.size
    gray = crop.convert("L")
    inner_mean = float(ImageStat.Stat(gray).mean[0]) if ImageStat.Stat(gray).mean else 0.0
    for start_idx, end_idx, peak_score in segments:
        if region.region_type in {"TOP_EDGE", "BOTTOM_EDGE"}:
            lx0, lx1 = start_idx, end_idx + 1
            ly0, ly1 = (0, max(1, int(height * 0.38))) if region.region_type == "TOP_EDGE" else (max(0, height - int(height * 0.38)), height)
        else:
            ly0, ly1 = start_idx, end_idx + 1
            lx0, lx1 = (0, max(1, int(width * 0.38))) if region.region_type == "LEFT_EDGE" else (max(0, width - int(width * 0.38)), width)
        localized = (end_idx - start_idx + 1) <= max(3, len(scores) // 8)
        break_ratio = (peak_score - median) / max(1.0, median + 10.0)
        color_delta = abs(peak_score - inner_mean) / 128.0
        evidence_type = _classify_edge_evidence(break_ratio=break_ratio, color_delta=color_delta, localized=localized)
        measurements = calculate_corner_edge_measurements(
            region=region,
            crop=crop,
            local_box=(lx0, ly0, lx1, ly1),
            outer_mean=peak_score,
            inner_mean=median,
            edge_mean=peak_score,
            continuity=1.0 - min(1.0, break_ratio),
        )
        confidence = _confidence_score(measurements)
        severity = _severity_hint(float(measurements["normalized_relative_size"]), float(measurements["border_break_ratio"]))
        abs_x_min = region.x_min + lx0
        abs_y_min = region.y_min + ly0
        abs_x_max = region.x_min + min(width, lx1) - 1
        abs_y_max = region.y_min + min(height, ly1) - 1
        drafts.append(
            _EvidenceDraft(
                region_type=region.region_type,
                evidence_type=evidence_type,
                x_min=abs_x_min,
                y_min=abs_y_min,
                x_max=abs_x_max,
                y_max=abs_y_max,
                width_px=max(1, abs_x_max - abs_x_min + 1),
                height_px=max(1, abs_y_max - abs_y_min + 1),
                edge_distance_px=int(measurements["edge_distance_px"]),
                corner_overlap_ratio=float(measurements["corner_overlap_ratio"]),
                confidence_score=confidence,
                severity_hint=severity,
                measurement_json=measurements,
                metadata_json={"segment_index": [start_idx, end_idx], "peak_score": round(peak_score, 6)},
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


def segment_evidence(drafts: list[_EvidenceDraft]) -> list[_EvidenceDraft]:
    ordered = sorted(
        drafts,
        key=lambda row: (
            _region_index(row.region_type),
            row.y_min,
            row.x_min,
            row.evidence_type,
        ),
    )
    ranked: list[_EvidenceDraft] = []
    for rank, row in enumerate(ordered, start=1):
        ranked.append(
            _EvidenceDraft(
                region_type=row.region_type,
                evidence_type=row.evidence_type,
                x_min=row.x_min,
                y_min=row.y_min,
                x_max=row.x_max,
                y_max=row.y_max,
                width_px=row.width_px,
                height_px=row.height_px,
                edge_distance_px=row.edge_distance_px,
                corner_overlap_ratio=row.corner_overlap_ratio,
                confidence_score=row.confidence_score,
                severity_hint=row.severity_hint,
                measurement_json={**row.measurement_json, "evidence_rank": rank},
                metadata_json={**row.metadata_json, "evidence_rank": rank},
                defect_evidence_id=row.defect_evidence_id,
            )
        )
    return ranked


def build_corner_edge_manifest(
    *,
    defect_run: ScanDefectRun,
    evidence: list[_EvidenceDraft],
    issues: list[_IssueDraft],
    artifact_checksums: list[dict[str, str]],
    corner_regions: dict[str, _RegionIsolation],
    edge_regions: dict[str, _RegionIsolation],
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
        "corner_regions": [
            {
                "region_type": key,
                "region_checksum": corner_regions[key].region.region_checksum,
                "bbox": [
                    corner_regions[key].region.x_min,
                    corner_regions[key].region.y_min,
                    corner_regions[key].region.x_max,
                    corner_regions[key].region.y_max,
                ],
            }
            for key in CORNER_REGION_ORDER
            if key in corner_regions
        ],
        "edge_regions": [
            {
                "region_type": key,
                "region_checksum": edge_regions[key].region.region_checksum,
                "bbox": [
                    edge_regions[key].region.x_min,
                    edge_regions[key].region.y_min,
                    edge_regions[key].region.x_max,
                    edge_regions[key].region.y_max,
                ],
            }
            for key in EDGE_REGION_ORDER
            if key in edge_regions
        ],
        "evidence": [
            {
                "evidence_rank": int(row.measurement_json.get("evidence_rank") or idx + 1),
                "evidence_type": row.evidence_type,
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
            "corner_count": sum(1 for row in evidence if "CORNER" in row.region_type),
            "edge_count": sum(1 for row in evidence if row.region_type in EDGE_REGION_ORDER),
        },
    }
    return manifest, _hash_payload(manifest)


def _build_region_montage(isolated: dict[str, _RegionIsolation], order: tuple[str, ...]) -> bytes:
    tiles = [isolated[key].crop.copy() for key in order if key in isolated]
    if not tiles:
        return _minimal_png()
    tile_w = max(t.width for t in tiles)
    tile_h = max(t.height for t in tiles)
    cols = 2 if len(tiles) > 1 else 1
    rows = (len(tiles) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * tile_w, rows * tile_h), (18, 18, 24))
    for idx, tile in enumerate(tiles):
        tile.thumbnail((tile_w, tile_h))
        ox = (idx % cols) * tile_w
        oy = (idx // cols) * tile_h
        canvas.paste(tile, (ox, oy))
    canvas.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def _build_border_continuity_map(image: Image.Image, regions: dict[str, _RegionIsolation]) -> bytes:
    rendered = _image_to_rgb(image)
    edges = rendered.convert("L").filter(ImageFilter.FIND_EDGES)
    edge_rgb = Image.merge("RGB", (edges, edges, edges))
    blended = Image.blend(rendered, edge_rgb, 0.72)
    draw = ImageDraw.Draw(blended)
    for key in REGION_PROCESS_ORDER:
        if key not in regions:
            continue
        row = regions[key].region
        draw.rectangle((row.x_min, row.y_min, row.x_max, row.y_max), outline="#38bdf8", width=1)
    preview = blended.copy()
    preview.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
    buf = io.BytesIO()
    preview.save(buf, format="PNG")
    return buf.getvalue()


def _build_corner_edge_overlay(image: Image.Image, evidence: list[_EvidenceDraft]) -> bytes:
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
    for row in evidence[:12]:
        draw.rectangle((row.x_min, row.y_min, row.x_max, row.y_max), outline="#ef4444", width=2)
    preview = rendered.copy()
    preview.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
    buf = io.BytesIO()
    preview.save(buf, format="PNG")
    return buf.getvalue()


def _build_issues(
    *,
    corner_regions: dict[str, _RegionIsolation],
    edge_regions: dict[str, _RegionIsolation],
    evidence: list[_EvidenceDraft],
    defect_run: ScanDefectRun,
) -> list[_IssueDraft]:
    issues: list[_IssueDraft] = []
    missing_corners = [key for key in CORNER_REGION_ORDER if key not in corner_regions]
    missing_edges = [key for key in EDGE_REGION_ORDER if key not in edge_regions]
    if missing_corners:
        issues.append(
            _IssueDraft(
                issue_type="CORNER_REGION_MISSING",
                severity="ERROR" if len(missing_corners) == len(CORNER_REGION_ORDER) else "WARNING",
                issue_message="One or more corner regions were missing from the defect foundation manifest.",
                metadata_json={"missing_regions": missing_corners},
            )
        )
    if missing_edges:
        issues.append(
            _IssueDraft(
                issue_type="EDGE_REGION_MISSING",
                severity="ERROR" if len(missing_edges) == len(EDGE_REGION_ORDER) else "WARNING",
                issue_message="One or more edge regions were missing from the defect foundation manifest.",
                metadata_json={"missing_regions": missing_edges},
            )
        )
    if not corner_regions and not edge_regions:
        issues.append(
            _IssueDraft(
                issue_type="EDGE_DETECTION_FAILED",
                severity="ERROR",
                issue_message="Corner and edge region isolation failed.",
                metadata_json={},
            )
        )
        return issues
    combined = {**corner_regions, **edge_regions}
    stddevs: list[float] = []
    light_ratios: list[float] = []
    for iso in combined.values():
        gray = iso.crop.convert("L")
        stat = ImageStat.Stat(gray)
        stddevs.append(float(stat.stddev[0]) if stat.stddev else 0.0)
        histogram = gray.histogram()
        total = max(1, iso.crop.width * iso.crop.height)
        light_ratios.append(sum(histogram[230:]) / total)
    if light_ratios and sum(light_ratios) / len(light_ratios) > 0.18:
        issues.append(
            _IssueDraft(
                issue_type="EXCESSIVE_GLARE",
                severity="WARNING",
                issue_message="Border regions show glare that may reduce wear detection reliability.",
                metadata_json={"mean_light_ratio": round(sum(light_ratios) / len(light_ratios), 6)},
            )
        )
    if stddevs and sum(stddevs) / len(stddevs) < 16:
        issues.append(
            _IssueDraft(
                issue_type="LOW_CONTRAST_EDGES",
                severity="WARNING",
                issue_message="Border region contrast is low for stable edge segmentation.",
                metadata_json={"mean_stddev": round(sum(stddevs) / len(stddevs), 6)},
            )
        )
    corner_low = [row for row in evidence if "CORNER" in row.region_type and row.confidence_score < _LOW_CONFIDENCE_THRESHOLD]
    edge_low = [row for row in evidence if row.region_type in EDGE_REGION_ORDER and row.confidence_score < _LOW_CONFIDENCE_THRESHOLD]
    if corner_low and len(corner_low) == sum(1 for row in evidence if "CORNER" in row.region_type):
        issues.append(
            _IssueDraft(
                issue_type="LOW_CORNER_CONFIDENCE",
                severity="WARNING",
                issue_message="All corner wear evidence rows remain below the confidence floor.",
                metadata_json={"low_confidence_count": len(corner_low)},
            )
        )
    if edge_low and len(edge_low) == sum(1 for row in evidence if row.region_type in EDGE_REGION_ORDER):
        issues.append(
            _IssueDraft(
                issue_type="LOW_EDGE_CONFIDENCE",
                severity="WARNING",
                issue_message="All edge wear evidence rows remain below the confidence floor.",
                metadata_json={"low_confidence_count": len(edge_low)},
            )
        )
    if not evidence:
        issues.append(
            _IssueDraft(
                issue_type="BORDER_SEGMENTATION_FAILED",
                severity="INFO",
                issue_message="No corner or edge wear segments exceeded the deterministic threshold.",
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


def _artifact_drafts_for_run(
    *,
    image: Image.Image,
    corner_regions: dict[str, _RegionIsolation],
    edge_regions: dict[str, _RegionIsolation],
    evidence: list[_EvidenceDraft],
    measurement_export: dict[str, Any],
) -> list[_ArtifactDraft]:
    combined = {**corner_regions, **edge_regions}
    if not combined:
        tiny = _minimal_png()
        return [
            _ArtifactDraft("CORNER_REGION_PREVIEW", tiny, {"placeholder": True}, ".png"),
            _ArtifactDraft("EDGE_REGION_PREVIEW", tiny, {"placeholder": True}, ".png"),
            _ArtifactDraft("CORNER_EDGE_OVERLAY", _build_corner_edge_overlay(image, evidence), {"format": "png"}, ".png"),
            _ArtifactDraft("BORDER_CONTINUITY_MAP", tiny, {"placeholder": True}, ".png"),
            _ArtifactDraft("CORNER_EDGE_DEBUG_PREVIEW", tiny, {"placeholder": True}, ".png"),
        ]
    return [
        _ArtifactDraft(
            "CORNER_REGION_PREVIEW",
            _build_region_montage(corner_regions, CORNER_REGION_ORDER),
            {"format": "png", "region_count": len(corner_regions)},
            ".png",
        ),
        _ArtifactDraft(
            "EDGE_REGION_PREVIEW",
            _build_region_montage(edge_regions, EDGE_REGION_ORDER),
            {"format": "png", "region_count": len(edge_regions)},
            ".png",
        ),
        _ArtifactDraft(
            "CORNER_EDGE_OVERLAY",
            _build_corner_edge_overlay(image, evidence),
            {"format": "png", "evidence_count": len(evidence)},
            ".png",
        ),
        _ArtifactDraft(
            "BORDER_CONTINUITY_MAP",
            _build_border_continuity_map(image, combined),
            {"format": "png"},
            ".png",
        ),
        _ArtifactDraft(
            "CORNER_EDGE_DEBUG_PREVIEW",
            _build_debug_preview(image, evidence),
            {"format": "png"},
            ".png",
        ),
    ]


def _resolve_defect_run(session: Session, *, owner_user_id: int, payload: ScanCornerEdgeRunCreate) -> ScanDefectRun:
    stmt = select(ScanDefectRun).where(
        ScanDefectRun.owner_user_id == owner_user_id,
        ScanDefectRun.scan_image_id == payload.scan_image_id,
        ScanDefectRun.defect_status == "COMPLETE",
    )
    if payload.defect_run_id is not None:
        stmt = stmt.where(ScanDefectRun.id == payload.defect_run_id)
    defect_run = session.exec(stmt.order_by(col(ScanDefectRun.id).desc())).first()
    if defect_run is None:
        raise HTTPException(status_code=409, detail="A complete defect foundation run is required before corner/edge detection.")
    return defect_run


def _detail_from_run(session: Session, settings: Settings, run: ScanCornerEdgeRun) -> ScanCornerEdgeRunDetail:
    evidence = session.exec(
        select(ScanCornerEdgeEvidence)
        .where(ScanCornerEdgeEvidence.corner_edge_run_id == run.id)
        .order_by(col(ScanCornerEdgeEvidence.evidence_rank), col(ScanCornerEdgeEvidence.id))
    ).all()
    artifacts = session.exec(
        select(ScanCornerEdgeArtifact)
        .where(ScanCornerEdgeArtifact.corner_edge_run_id == run.id)
        .order_by(col(ScanCornerEdgeArtifact.id))
    ).all()
    issues = session.exec(
        select(ScanCornerEdgeIssue).where(ScanCornerEdgeIssue.corner_edge_run_id == run.id).order_by(col(ScanCornerEdgeIssue.id))
    ).all()
    history = session.exec(
        select(ScanCornerEdgeHistory).where(ScanCornerEdgeHistory.corner_edge_run_id == run.id).order_by(col(ScanCornerEdgeHistory.id))
    ).all()
    defect_run = session.get(ScanDefectRun, int(run.defect_run_id))
    source_artifact = session.get(ScanNormalizationArtifact, int(defect_run.source_artifact_id)) if defect_run else None
    art_reads = [
        ScanCornerEdgeArtifactRead.model_validate(row).model_copy(
            update={"preview_data_url": _artifact_preview_data_url(settings, row)}
        )
        for row in artifacts
    ]
    scan_image = session.get(ScanImage, int(run.scan_image_id))
    norm_run = session.get(ScanNormalizationRun, int(defect_run.normalization_run_id)) if defect_run else None
    boundary_run = session.get(ScanBoundaryRun, int(defect_run.boundary_run_id)) if defect_run else None
    run_data = ScanCornerEdgeRunRead.model_validate(run).model_dump()
    return ScanCornerEdgeRunDetail(
        **run_data,
        evidence=[ScanCornerEdgeEvidenceRead.model_validate(row) for row in evidence],
        artifacts=art_reads,
        issues=[ScanCornerEdgeIssueRead.model_validate(row) for row in issues],
        history=[ScanCornerEdgeHistoryRead.model_validate(row) for row in history],
        original_scan_checksum=scan_image.sha256_checksum if scan_image else None,
        normalization_checksum=norm_run.normalization_checksum if norm_run else None,
        boundary_checksum=boundary_run.boundary_checksum if boundary_run else None,
        defect_checksum=defect_run.defect_checksum if defect_run else None,
        source_preview_data_url=_load_source_preview(settings, source_artifact) if source_artifact else None,
        corner_region_preview_data_url=next((a.preview_data_url for a in art_reads if a.artifact_type == "CORNER_REGION_PREVIEW"), None),
        edge_region_preview_data_url=next((a.preview_data_url for a in art_reads if a.artifact_type == "EDGE_REGION_PREVIEW"), None),
        evidence_summary=dict(run.output_manifest_json.get("evidence_summary") or {}),
    )


def run_scan_corner_edge_detection(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: ScanCornerEdgeRunCreate,
) -> tuple[ScanCornerEdgeRunDetail, bool]:
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
        raise HTTPException(status_code=409, detail="Normalized source artifact is not available for corner/edge detection.") from exc

    corner_regions = isolate_corner_regions(image=image, regions=defect_regions)
    edge_regions = isolate_edge_regions(image=image, regions=defect_regions)
    drafts: list[_EvidenceDraft] = []
    for key in CORNER_REGION_ORDER:
        if key in corner_regions:
            drafts.extend(detect_corner_wear(isolation=corner_regions[key], defect_evidence=defect_evidence))
    for key in EDGE_REGION_ORDER:
        if key in edge_regions:
            drafts.extend(detect_edge_wear(isolation=edge_regions[key], defect_evidence=defect_evidence))
    evidence = segment_evidence(drafts)
    issues = _build_issues(
        corner_regions=corner_regions,
        edge_regions=edge_regions,
        evidence=evidence,
        defect_run=defect_run,
    )
    measurement_export = {
        "evidence": [
            {
                "evidence_rank": int(row.measurement_json.get("evidence_rank") or 0),
                "evidence_type": row.evidence_type,
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
        corner_regions=corner_regions,
        edge_regions=edge_regions,
        evidence=evidence,
        measurement_export=measurement_export,
    )
    provisional_manifest, corner_edge_checksum = build_corner_edge_manifest(
        defect_run=defect_run,
        evidence=evidence,
        issues=issues,
        artifact_checksums=[
            {"artifact_type": row.artifact_type, "artifact_checksum": _sha256_bytes(row.body)} for row in provisional_artifacts
        ],
        corner_regions=corner_regions,
        edge_regions=edge_regions,
    )
    manifest_artifact = _ArtifactDraft("CORNER_EDGE_MANIFEST", _serialize_json_artifact(provisional_manifest), {"format": "json"}, ".json")
    artifacts = provisional_artifacts + [manifest_artifact]

    existing = session.exec(
        select(ScanCornerEdgeRun).where(
            ScanCornerEdgeRun.owner_user_id == owner_user_id,
            ScanCornerEdgeRun.corner_edge_checksum == corner_edge_checksum,
        )
    ).first()
    if existing is not None:
        return _detail_from_run(session, settings, existing), False

    input_manifest = {
        "scan_image_id": defect_run.scan_image_id,
        "defect_run_id": defect_run.id,
        "defect_checksum": defect_run.defect_checksum,
        "source_checksum": defect_run.source_checksum,
    }
    run = ScanCornerEdgeRun(
        owner_user_id=owner_user_id,
        scan_image_id=int(defect_run.scan_image_id),
        defect_run_id=int(defect_run.id or 0),
        source_checksum=defect_run.source_checksum,
        corner_edge_checksum=corner_edge_checksum,
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
            ScanCornerEdgeEvidence(
                owner_user_id=owner_user_id,
                corner_edge_run_id=int(run.id or 0),
                defect_evidence_id=row.defect_evidence_id,
                evidence_rank=int(row.measurement_json.get("evidence_rank") or 0),
                evidence_type=row.evidence_type,
                confidence_score=row.confidence_score,
                severity_hint=row.severity_hint,
                region_type=row.region_type,
                x_min=row.x_min,
                y_min=row.y_min,
                x_max=row.x_max,
                y_max=row.y_max,
                width_px=row.width_px,
                height_px=row.height_px,
                edge_distance_px=row.edge_distance_px,
                corner_overlap_ratio=row.corner_overlap_ratio,
                measurement_json=row.measurement_json,
                metadata_json=row.metadata_json,
            )
        )
    for row in issues:
        session.add(
            ScanCornerEdgeIssue(
                owner_user_id=owner_user_id,
                corner_edge_run_id=int(run.id or 0),
                issue_type=row.issue_type,
                severity=row.severity,
                issue_message=row.issue_message,
                metadata_json=row.metadata_json,
            )
        )
    history_rows = [
        _HistoryDraft("CORNER_EDGE_RUN_CREATED", "Created deterministic corner/edge wear detection run.", {"corner_edge_checksum": corner_edge_checksum}),
        _HistoryDraft("CORNER_REGIONS_ISOLATED", "Isolated corner regions from defect foundation geometry.", {"corner_count": len(corner_regions)}),
        _HistoryDraft("EDGE_REGIONS_ISOLATED", "Isolated edge regions from defect foundation geometry.", {"edge_count": len(edge_regions)}),
        _HistoryDraft("CORNER_EDGE_MANIFEST_WRITTEN", "Persisted replay-safe corner/edge manifest and artifacts.", {"artifact_count": len(artifacts)}),
    ]
    for row in history_rows:
        session.add(
            ScanCornerEdgeHistory(
                owner_user_id=owner_user_id,
                corner_edge_run_id=int(run.id or 0),
                event_type=row.event_type,
                event_message=row.event_message,
                event_checksum=_hash_payload(
                    {
                        "corner_edge_run_id": int(run.id or 0),
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
            corner_edge_run_id=int(run.id or 0),
            artifact_type=row.artifact_type,
            ext=row.ext,
        )
        _save_artifact_bytes(settings, relative_path=relative_path, body=row.body)
        session.add(
            ScanCornerEdgeArtifact(
                owner_user_id=owner_user_id,
                corner_edge_run_id=int(run.id or 0),
                artifact_type=row.artifact_type,
                storage_path=relative_path,
                artifact_checksum=_sha256_bytes(row.body),
                metadata_json=row.metadata_json,
            )
        )
    session.commit()
    session.refresh(run)
    return _detail_from_run(session, settings, run), True


def get_scan_corner_edge_run_owner(session: Session, settings: Settings, *, owner_user_id: int, run_id: int) -> ScanCornerEdgeRunDetail:
    row = session.get(ScanCornerEdgeRun, run_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Corner/edge run not found.")
    return _detail_from_run(session, settings, row)


def get_scan_corner_edge_artifact_owner(session: Session, settings: Settings, *, owner_user_id: int, artifact_id: int) -> ScanCornerEdgeArtifactRead:
    row = session.get(ScanCornerEdgeArtifact, artifact_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Corner/edge artifact not found.")
    return ScanCornerEdgeArtifactRead.model_validate(row).model_copy(
        update={"preview_data_url": _artifact_preview_data_url(settings, row)}
    )


def _run_list_response(rows: list[ScanCornerEdgeRun], *, limit: int, offset: int, total_items: int) -> ScanCornerEdgeRunListResponse:
    status_counts = {status: sum(1 for row in rows if row.detection_status == status) for status in sorted({row.detection_status for row in rows})}
    low_confidence = sum(int((row.output_manifest_json.get("evidence_summary") or {}).get("low_confidence_count") or 0) for row in rows)
    high_density = sum(int((row.output_manifest_json.get("evidence_summary") or {}).get("major_count") or 0) for row in rows)
    return ScanCornerEdgeRunListResponse(
        items=[ScanCornerEdgeRunRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        status_counts=status_counts,
        low_confidence_count=low_confidence,
        high_density_wear_count=high_density,
    )


def list_scan_corner_edge_runs_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanCornerEdgeRunListResponse:
    limit, offset = clamp_scan_corner_edge_pagination(limit=limit, offset=offset)
    stmt = select(ScanCornerEdgeRun).where(ScanCornerEdgeRun.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanCornerEdgeRun).where(ScanCornerEdgeRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanCornerEdgeRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanCornerEdgeRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanCornerEdgeRun.created_at).desc(), col(ScanCornerEdgeRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_corner_edge_runs_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanCornerEdgeRunListResponse:
    limit, offset = clamp_scan_corner_edge_pagination(limit=limit, offset=offset)
    stmt = select(ScanCornerEdgeRun)
    count_stmt = select(func.count()).select_from(ScanCornerEdgeRun)
    if owner_user_id is not None:
        stmt = stmt.where(ScanCornerEdgeRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanCornerEdgeRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanCornerEdgeRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanCornerEdgeRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanCornerEdgeRun.created_at).desc(), col(ScanCornerEdgeRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return _run_list_response(rows, limit=limit, offset=offset, total_items=total_items)


def list_scan_corner_edge_evidence_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    corner_edge_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanCornerEdgeEvidenceListResponse:
    limit, offset = clamp_scan_corner_edge_pagination(limit=limit, offset=offset)
    stmt = select(ScanCornerEdgeEvidence).join(
        ScanCornerEdgeRun,
        ScanCornerEdgeRun.id == ScanCornerEdgeEvidence.corner_edge_run_id,
    ).where(ScanCornerEdgeEvidence.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanCornerEdgeEvidence).join(
        ScanCornerEdgeRun,
        ScanCornerEdgeRun.id == ScanCornerEdgeEvidence.corner_edge_run_id,
    ).where(ScanCornerEdgeEvidence.owner_user_id == owner_user_id)
    if corner_edge_run_id is not None:
        stmt = stmt.where(ScanCornerEdgeEvidence.corner_edge_run_id == corner_edge_run_id)
        count_stmt = count_stmt.where(ScanCornerEdgeEvidence.corner_edge_run_id == corner_edge_run_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanCornerEdgeRun.scan_image_id == scan_image_id)
        count_stmt = count_stmt.where(ScanCornerEdgeRun.scan_image_id == scan_image_id)
    rows = session.exec(stmt.order_by(col(ScanCornerEdgeEvidence.evidence_rank), col(ScanCornerEdgeEvidence.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanCornerEdgeEvidenceListResponse(
        items=[ScanCornerEdgeEvidenceRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        evidence_type_counts={key: sum(1 for row in rows if row.evidence_type == key) for key in sorted({row.evidence_type for row in rows})},
        severity_hint_counts={key: sum(1 for row in rows if row.severity_hint == key) for key in sorted({row.severity_hint for row in rows})},
        low_confidence_count=sum(1 for row in rows if float(row.confidence_score) < _LOW_CONFIDENCE_THRESHOLD),
    )


def list_scan_corner_edge_issues_owner(
    session: Session,
    *,
    owner_user_id: int,
    corner_edge_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanCornerEdgeIssueListResponse:
    limit, offset = clamp_scan_corner_edge_pagination(limit=limit, offset=offset)
    stmt = select(ScanCornerEdgeIssue).where(ScanCornerEdgeIssue.owner_user_id == owner_user_id)
    count_stmt = select(func.count()).select_from(ScanCornerEdgeIssue).where(ScanCornerEdgeIssue.owner_user_id == owner_user_id)
    if corner_edge_run_id is not None:
        stmt = stmt.where(ScanCornerEdgeIssue.corner_edge_run_id == corner_edge_run_id)
        count_stmt = count_stmt.where(ScanCornerEdgeIssue.corner_edge_run_id == corner_edge_run_id)
    rows = session.exec(stmt.order_by(col(ScanCornerEdgeIssue.created_at), col(ScanCornerEdgeIssue.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanCornerEdgeIssueListResponse(
        items=[ScanCornerEdgeIssueRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        issue_type_counts={key: sum(1 for row in rows if row.issue_type == key) for key in sorted({row.issue_type for row in rows})},
    )


def list_scan_corner_edge_issues_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanCornerEdgeIssueListResponse:
    limit, offset = clamp_scan_corner_edge_pagination(limit=limit, offset=offset)
    stmt = select(ScanCornerEdgeIssue)
    count_stmt = select(func.count()).select_from(ScanCornerEdgeIssue)
    if owner_user_id is not None:
        stmt = stmt.where(ScanCornerEdgeIssue.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanCornerEdgeIssue.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanCornerEdgeIssue.created_at), col(ScanCornerEdgeIssue.id)).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanCornerEdgeIssueListResponse(
        items=[ScanCornerEdgeIssueRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
        issue_type_counts={key: sum(1 for row in rows if row.issue_type == key) for key in sorted({row.issue_type for row in rows})},
    )


def list_scan_corner_edge_failures_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanCornerEdgeFailureListResponse:
    limit, offset = clamp_scan_corner_edge_pagination(limit=limit, offset=offset)
    stmt = select(ScanCornerEdgeRun).where(ScanCornerEdgeRun.detection_status == "FAILED")
    count_stmt = select(func.count()).select_from(ScanCornerEdgeRun).where(ScanCornerEdgeRun.detection_status == "FAILED")
    if owner_user_id is not None:
        stmt = stmt.where(ScanCornerEdgeRun.owner_user_id == owner_user_id)
        count_stmt = count_stmt.where(ScanCornerEdgeRun.owner_user_id == owner_user_id)
    rows = session.exec(stmt.order_by(col(ScanCornerEdgeRun.created_at).desc(), col(ScanCornerEdgeRun.id).desc()).offset(offset).limit(limit)).all()
    total_items = int(session.exec(count_stmt).one())
    return ScanCornerEdgeFailureListResponse(
        items=[ScanCornerEdgeRunRead.model_validate(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )
