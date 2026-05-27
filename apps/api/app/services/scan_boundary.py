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
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat, UnidentifiedImageError
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models import (
    ScanBoundaryArtifact,
    ScanBoundaryHistory,
    ScanBoundaryIssue,
    ScanBoundaryRun,
    ScanImage,
    ScanNormalizationArtifact,
    ScanNormalizationRun,
)
from app.schemas.scan_boundary import (
    ScanBoundaryArtifactRead,
    ScanBoundaryArtifactReadResponse,
    ScanBoundaryFailureListResponse,
    ScanBoundaryHistoryRead,
    ScanBoundaryIssueListResponse,
    ScanBoundaryIssueRead,
    ScanBoundaryRunCreate,
    ScanBoundaryRunDetail,
    ScanBoundaryRunListResponse,
    ScanBoundaryRunRead,
)

ALGORITHM_VERSION = "P40-03-v1"
_PREVIEW_MAX = 420
_CONFIDENCE_LOW_THRESHOLD = 0.45


@dataclass(frozen=True)
class _BoundaryDetection:
    polygon: list[list[int]]
    bbox: tuple[int, int, int, int]
    width: int
    height: int
    aspect_ratio: float
    confidence_score: float
    detection_method: str
    secondary_bbox_count: int


@dataclass(frozen=True)
class _BackgroundSeparation:
    background_color: list[int]
    border_thickness: dict[str, int]
    scan_margins: dict[str, int]
    clipping_indicators: dict[str, bool]


@dataclass(frozen=True)
class _CoverGeometry:
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    top_left: list[int]
    top_right: list[int]
    bottom_right: list[int]
    bottom_left: list[int]
    angle_degrees: float
    aspect_ratio: float
    cover_area_px: int
    image_area_px: int
    cover_coverage_ratio: float
    margin_to_edge: dict[str, int]


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
    width_px: int
    height_px: int
    metadata_json: dict[str, Any]
    ext: str


@dataclass(frozen=True)
class _HistoryDraft:
    event_type: str
    event_message: str
    metadata_json: dict[str, Any]


def utc_now():
    from app.models.scan_boundary import utc_now as _utc_now

    return _utc_now()


def clamp_scan_boundary_pagination(*, limit: int, offset: int) -> tuple[int, int]:
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


def _resolve_boundary_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.scan_boundary_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("scan boundary storage path escapes configured root")
    return target


def _artifact_storage_path(
    *,
    owner_user_id: int,
    scan_image_id: int,
    boundary_run_id: int,
    artifact_type: str,
    ext: str,
) -> str:
    safe_type = artifact_type.lower()
    return f"scan-boundary/{owner_user_id}/{scan_image_id}/{boundary_run_id}/{safe_type}{ext}".replace("\\", "/")


def _data_url_for_image(image: Image.Image) -> str:
    preview = image.copy()
    if preview.mode not in {"RGB", "RGBA", "L"}:
        preview = preview.convert("RGB")
    preview.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
    rendered = io.BytesIO()
    preview.save(rendered, format="PNG")
    encoded = base64.b64encode(rendered.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _image_to_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image.copy()
    return image.convert("RGB")


def _corner_background_color(rgb: Image.Image) -> tuple[int, int, int]:
    corners = [
        rgb.getpixel((0, 0)),
        rgb.getpixel((rgb.width - 1, 0)),
        rgb.getpixel((0, rgb.height - 1)),
        rgb.getpixel((rgb.width - 1, rgb.height - 1)),
    ]
    return tuple(int(round(sum(pixel[idx] for pixel in corners) / len(corners))) for idx in range(3))


def detect_comic_boundary(image: Image.Image) -> _BoundaryDetection:
    rgb = _image_to_rgb(image)
    background_color = _corner_background_color(rgb)
    background = Image.new("RGB", rgb.size, background_color)
    diff = ImageChops.difference(rgb, background).convert("L")
    edges = diff.filter(ImageFilter.FIND_EDGES)
    combined = ImageChops.add(diff, edges, scale=1.0, offset=0)
    mask = combined.point(lambda p: 255 if p >= 14 else 0)
    bbox = mask.getbbox()
    if bbox is None:
        full = (0, 0, rgb.width, rgb.height)
        polygon = [[0, 0], [rgb.width - 1, 0], [rgb.width - 1, rgb.height - 1], [0, rgb.height - 1]]
        return _BoundaryDetection(
            polygon=polygon,
            bbox=full,
            width=rgb.width,
            height=rgb.height,
            aspect_ratio=round(rgb.width / max(1, rgb.height), 6),
            confidence_score=0.0,
            detection_method="edge_contrast_v1",
            secondary_bbox_count=0,
        )

    left, top, right, bottom = bbox
    pad = 4
    left = max(0, left - pad)
    top = max(0, top - pad)
    right = min(rgb.width, right + pad)
    bottom = min(rgb.height, bottom + pad)
    width = max(1, right - left)
    height = max(1, bottom - top)
    area_ratio = (width * height) / max(1, rgb.width * rgb.height)

    border_stat = ImageStat.Stat(diff.crop((0, 0, rgb.width, max(1, top))))
    content_stat = ImageStat.Stat(diff.crop((left, top, right, bottom)))
    border_mean = float(border_stat.mean[0]) if border_stat.mean else 0.0
    content_mean = float(content_stat.mean[0]) if content_stat.mean else 0.0
    contrast_factor = min(1.0, max(0.0, (content_mean - border_mean) / 255.0))
    area_factor = 1.0 if 0.25 <= area_ratio <= 0.98 else max(0.0, 1.0 - abs(area_ratio - 0.72))
    confidence = round(min(1.0, max(0.0, contrast_factor * 0.7 + area_factor * 0.3)), 6)

    secondary_count = 1 if area_ratio < 0.55 and contrast_factor > 0.2 else 0

    polygon = [[left, top], [right - 1, top], [right - 1, bottom - 1], [left, bottom - 1]]
    return _BoundaryDetection(
        polygon=polygon,
        bbox=(left, top, right, bottom),
        width=width,
        height=height,
        aspect_ratio=round(width / max(1, height), 6),
        confidence_score=confidence,
        detection_method="edge_contrast_v1",
        secondary_bbox_count=secondary_count,
    )


def separate_background_region(
    image: Image.Image,
    *,
    bbox: tuple[int, int, int, int],
) -> _BackgroundSeparation:
    rgb = _image_to_rgb(image)
    bg = _corner_background_color(rgb)
    left, top, right, bottom = bbox
    return _BackgroundSeparation(
        background_color=list(bg),
        border_thickness={
            "left_px": left,
            "top_px": top,
            "right_px": max(0, rgb.width - right),
            "bottom_px": max(0, rgb.height - bottom),
        },
        scan_margins={
            "left_px": left,
            "top_px": top,
            "right_px": max(0, rgb.width - right),
            "bottom_px": max(0, rgb.height - bottom),
        },
        clipping_indicators={
            "left_edge": left <= 2,
            "top_edge": top <= 2,
            "right_edge": right >= rgb.width - 2,
            "bottom_edge": bottom >= rgb.height - 2,
        },
    )


def calculate_cover_geometry(
    image: Image.Image,
    *,
    bbox: tuple[int, int, int, int],
    polygon: list[list[int]],
) -> _CoverGeometry:
    rgb = _image_to_rgb(image)
    left, top, right, bottom = bbox
    width = max(1, right - left)
    height = max(1, bottom - top)
    image_area = max(1, rgb.width * rgb.height)
    cover_area = width * height
    tl, tr, br, bl = polygon[0], polygon[1], polygon[2], polygon[3]
    angle = round(math.degrees(math.atan2(tr[1] - tl[1], tr[0] - tl[0])), 4)
    return _CoverGeometry(
        x_min=left,
        y_min=top,
        x_max=right - 1,
        y_max=bottom - 1,
        top_left=list(tl),
        top_right=list(tr),
        bottom_right=list(br),
        bottom_left=list(bl),
        angle_degrees=angle,
        aspect_ratio=round(width / max(1, height), 6),
        cover_area_px=cover_area,
        image_area_px=image_area,
        cover_coverage_ratio=round(cover_area / image_area, 6),
        margin_to_edge={
            "left_px": left,
            "top_px": top,
            "right_px": max(0, rgb.width - right),
            "bottom_px": max(0, rgb.height - bottom),
        },
    )


def build_boundary_manifest(
    *,
    algorithm_version: str,
    original_scan_checksum: str,
    source_checksum: str,
    detection: _BoundaryDetection,
    background: _BackgroundSeparation,
    geometry: _CoverGeometry,
    issues: list[_IssueDraft],
    artifact_checksums: list[dict[str, str]],
) -> tuple[dict[str, Any], str]:
    manifest: dict[str, Any] = {
        "algorithm_version": algorithm_version,
        "original_scan_checksum": original_scan_checksum,
        "source_checksum": source_checksum,
        "detection": {
            "polygon": detection.polygon,
            "bbox": list(detection.bbox),
            "confidence_score": detection.confidence_score,
            "detection_method": detection.detection_method,
            "secondary_bbox_count": detection.secondary_bbox_count,
        },
        "background": {
            "background_color": background.background_color,
            "border_thickness": background.border_thickness,
            "scan_margins": background.scan_margins,
            "clipping_indicators": background.clipping_indicators,
        },
        "geometry": {
            "x_min": geometry.x_min,
            "y_min": geometry.y_min,
            "x_max": geometry.x_max,
            "y_max": geometry.y_max,
            "top_left": geometry.top_left,
            "top_right": geometry.top_right,
            "bottom_right": geometry.bottom_right,
            "bottom_left": geometry.bottom_left,
            "angle_degrees": geometry.angle_degrees,
            "aspect_ratio": geometry.aspect_ratio,
            "cover_area_px": geometry.cover_area_px,
            "image_area_px": geometry.image_area_px,
            "cover_coverage_ratio": geometry.cover_coverage_ratio,
            "margin_to_edge": geometry.margin_to_edge,
        },
        "issues": [
            {
                "issue_type": issue.issue_type,
                "severity": issue.severity,
                "issue_message": issue.issue_message,
                "metadata_json": issue.metadata_json,
            }
            for issue in sorted(issues, key=lambda row: (row.issue_type, row.severity))
        ],
        "artifact_checksums": sorted(artifact_checksums, key=lambda row: row["artifact_type"]),
    }
    return manifest, _hash_payload(manifest)


def _detect_boundary_issues(
    *,
    detection: _BoundaryDetection,
    background: _BackgroundSeparation,
    geometry: _CoverGeometry,
    rgb: Image.Image,
) -> list[_IssueDraft]:
    issues: list[_IssueDraft] = []
    if detection.confidence_score <= 0.05:
        issues.append(
            _IssueDraft(
                issue_type="NO_BOUNDARY_FOUND",
                severity="ERROR",
                issue_message="No reliable comic boundary could be detected.",
                metadata_json={"confidence_score": detection.confidence_score},
            )
        )
    elif detection.confidence_score < _CONFIDENCE_LOW_THRESHOLD:
        issues.append(
            _IssueDraft(
                issue_type="LOW_BOUNDARY_CONFIDENCE",
                severity="WARNING",
                issue_message="Boundary confidence is below the deterministic threshold.",
                metadata_json={"confidence_score": detection.confidence_score, "threshold": _CONFIDENCE_LOW_THRESHOLD},
            )
        )
    if detection.secondary_bbox_count > 0:
        issues.append(
            _IssueDraft(
                issue_type="MULTIPLE_BOUNDARIES_FOUND",
                severity="WARNING",
                issue_message="Secondary boundary regions were detected in the frame.",
                metadata_json={"secondary_bbox_count": detection.secondary_bbox_count},
            )
        )
    if any(background.clipping_indicators.values()):
        issues.append(
            _IssueDraft(
                issue_type="BORDER_CLIPPING",
                severity="INFO",
                issue_message="Cover boundary touches one or more scan edges.",
                metadata_json=background.clipping_indicators,
            )
        )
    if geometry.cover_coverage_ratio < 0.55:
        issues.append(
            _IssueDraft(
                issue_type="PARTIAL_COVER_VISIBLE",
                severity="WARNING",
                issue_message="Detected cover occupies a small portion of the scan frame.",
                metadata_json={"cover_coverage_ratio": geometry.cover_coverage_ratio},
            )
        )
    bg_total = sum(background.border_thickness.values())
    if bg_total > geometry.image_area_px * 0.35:
        issues.append(
            _IssueDraft(
                issue_type="EXCESSIVE_BACKGROUND",
                severity="INFO",
                issue_message="Scanner bed or background margins are large relative to cover area.",
                metadata_json={"border_thickness": background.border_thickness},
            )
        )
    if abs(geometry.angle_degrees) > 8:
        issues.append(
            _IssueDraft(
                issue_type="EXTREME_SKEW_REMAINING",
                severity="WARNING",
                issue_message="Residual skew remains after normalization.",
                metadata_json={"angle_degrees": geometry.angle_degrees},
            )
        )
    gray = rgb.convert("L")
    stat = ImageStat.Stat(gray)
    spread = (float(stat.extrema[0][1]) - float(stat.extrema[0][0])) if stat.extrema else 0.0
    if spread < 40:
        issues.append(
            _IssueDraft(
                issue_type="LOW_CONTRAST_BACKGROUND",
                severity="WARNING",
                issue_message="Low luminance spread reduces boundary contrast.",
                metadata_json={"luminance_spread": round(spread, 2)},
            )
        )
    if geometry.aspect_ratio < 0.55 or geometry.aspect_ratio > 0.85:
        issues.append(
            _IssueDraft(
                issue_type="ASPECT_RATIO_ANOMALY",
                severity="INFO",
                issue_message="Detected cover aspect ratio is outside typical comic bounds.",
                metadata_json={"aspect_ratio": geometry.aspect_ratio},
            )
        )
    if geometry.cover_coverage_ratio < 0.35:
        issues.append(
            _IssueDraft(
                issue_type="COVER_TOO_SMALL_IN_FRAME",
                severity="WARNING",
                issue_message="Cover area is unusually small within the normalized frame.",
                metadata_json={"cover_coverage_ratio": geometry.cover_coverage_ratio},
            )
        )
    if geometry.cover_coverage_ratio > 0.97:
        issues.append(
            _IssueDraft(
                issue_type="COVER_TOO_LARGE_IN_FRAME",
                severity="INFO",
                issue_message="Cover area nearly fills the normalized frame.",
                metadata_json={"cover_coverage_ratio": geometry.cover_coverage_ratio},
            )
        )
    return issues


def _build_artifact_drafts(
    image: Image.Image,
    *,
    detection: _BoundaryDetection,
    geometry: _CoverGeometry,
    background: _BackgroundSeparation,
    manifest: dict[str, Any],
) -> list[_ArtifactDraft]:
    rgb = _image_to_rgb(image)
    left, top, right, bottom = detection.bbox

    overlay = rgb.copy()
    draw = ImageDraw.Draw(overlay)
    draw.polygon([tuple(point) for point in detection.polygon], outline=(0, 255, 120), width=3)
    overlay_buf = io.BytesIO()
    overlay.save(overlay_buf, format="PNG")

    cover_preview = rgb.copy()
    cover_draw = ImageDraw.Draw(cover_preview)
    cover_draw.rectangle((left, top, right - 1, bottom - 1), outline=(255, 80, 80), width=4)
    cover_buf = io.BytesIO()
    cover_preview.save(cover_buf, format="PNG")

    mask = Image.new("L", rgb.size, 255)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rectangle((left, top, right - 1, bottom - 1), fill=0)
    mask_rgb = Image.merge("RGB", (mask, mask, mask))
    mask_buf = io.BytesIO()
    mask_rgb.save(mask_buf, format="PNG")

    manifest_bytes = json.dumps(_json_safe(manifest), sort_keys=True, separators=(",", ":")).encode("utf-8")

    return [
        _ArtifactDraft(
            artifact_type="BOUNDARY_OVERLAY",
            body=overlay_buf.getvalue(),
            width_px=overlay.width,
            height_px=overlay.height,
            metadata_json={"detection_method": detection.detection_method},
            ext=".png",
        ),
        _ArtifactDraft(
            artifact_type="COVER_BOX_PREVIEW",
            body=cover_buf.getvalue(),
            width_px=cover_preview.width,
            height_px=cover_preview.height,
            metadata_json={"bbox": list(detection.bbox)},
            ext=".png",
        ),
        _ArtifactDraft(
            artifact_type="BACKGROUND_MASK",
            body=mask_buf.getvalue(),
            width_px=mask_rgb.width,
            height_px=mask_rgb.height,
            metadata_json={"background_color": background.background_color},
            ext=".png",
        ),
        _ArtifactDraft(
            artifact_type="GEOMETRY_MANIFEST",
            body=manifest_bytes,
            width_px=0,
            height_px=0,
            metadata_json={"format": "json"},
            ext=".json",
        ),
    ]


def _run_read(row: ScanBoundaryRun) -> ScanBoundaryRunRead:
    return ScanBoundaryRunRead.model_validate(row, from_attributes=True)


def _issue_read(row: ScanBoundaryIssue) -> ScanBoundaryIssueRead:
    return ScanBoundaryIssueRead.model_validate(row, from_attributes=True)


def _history_read(row: ScanBoundaryHistory) -> ScanBoundaryHistoryRead:
    return ScanBoundaryHistoryRead.model_validate(row, from_attributes=True)


def _artifact_read(row: ScanBoundaryArtifact, *, preview: str | None = None) -> ScanBoundaryArtifactRead:
    return ScanBoundaryArtifactRead.model_validate(
        {**row.model_dump(mode="json"), "preview_data_url": preview},
    )


def _load_artifact_preview(settings: Settings, row: ScanBoundaryArtifact) -> str | None:
    if row.artifact_type == "GEOMETRY_MANIFEST":
        return None
    try:
        path = _resolve_boundary_storage_path(settings, row.storage_path)
        with Image.open(path) as image:
            return _data_url_for_image(image)
    except (FileNotFoundError, OSError, ValueError, UnidentifiedImageError):
        return None


def _append_history_drafts(
    drafts: list[_HistoryDraft],
    *,
    event_type: str,
    event_message: str,
    metadata_json: dict[str, Any],
) -> None:
    drafts.append(
        _HistoryDraft(
            event_type=event_type,
            event_message=event_message,
            metadata_json=metadata_json,
        )
    )


def _history_event_checksum(
    *,
    boundary_run_id: int,
    event_type: str,
    event_message: str,
    metadata_json: dict[str, Any],
) -> str:
    return _hash_payload(
        {
            "boundary_run_id": boundary_run_id,
            "event_type": event_type,
            "event_message": event_message,
            "metadata_json": metadata_json,
        }
    )


def _resolve_normalization_context(
    session: Session,
    *,
    owner_user_id: int,
    scan_image: ScanImage,
    normalization_run_id: int | None,
) -> tuple[ScanNormalizationRun, ScanNormalizationArtifact]:
    if normalization_run_id is not None:
        norm_run = session.get(ScanNormalizationRun, normalization_run_id)
        if norm_run is None or norm_run.owner_user_id != owner_user_id or norm_run.scan_image_id != scan_image.id:
            raise HTTPException(status_code=404, detail="Normalization run not found")
        if norm_run.normalization_status != "COMPLETE":
            raise HTTPException(status_code=422, detail="Normalization run must be COMPLETE")
    else:
        norm_run = session.exec(
            select(ScanNormalizationRun)
            .where(
                ScanNormalizationRun.owner_user_id == owner_user_id,
                ScanNormalizationRun.scan_image_id == scan_image.id,
                ScanNormalizationRun.normalization_status == "COMPLETE",
            )
            .order_by(col(ScanNormalizationRun.created_at).desc(), col(ScanNormalizationRun.id).desc())
        ).first()
        if norm_run is None:
            raise HTTPException(status_code=422, detail="No completed normalization run exists for this scan image")

    source_artifact = session.exec(
        select(ScanNormalizationArtifact)
        .where(
            ScanNormalizationArtifact.scan_normalization_run_id == norm_run.id,
            ScanNormalizationArtifact.artifact_type == "FINAL_NORMALIZED",
        )
        .order_by(col(ScanNormalizationArtifact.artifact_order).asc(), col(ScanNormalizationArtifact.id).asc())
    ).first()
    if source_artifact is None:
        raise HTTPException(status_code=422, detail="FINAL_NORMALIZED artifact not found for normalization run")
    return norm_run, source_artifact


def _build_run_detail(
    session: Session,
    settings: Settings,
    *,
    run: ScanBoundaryRun,
    scan_image: ScanImage,
) -> ScanBoundaryRunDetail:
    artifacts = list(
        session.exec(
            select(ScanBoundaryArtifact)
            .where(ScanBoundaryArtifact.boundary_run_id == run.id)
            .order_by(col(ScanBoundaryArtifact.artifact_type).asc(), col(ScanBoundaryArtifact.id).asc())
        ).all()
    )
    issues = list(
        session.exec(
            select(ScanBoundaryIssue)
            .where(ScanBoundaryIssue.boundary_run_id == run.id)
            .order_by(col(ScanBoundaryIssue.created_at).asc(), col(ScanBoundaryIssue.id).asc())
        ).all()
    )
    history = list(
        session.exec(
            select(ScanBoundaryHistory)
            .where(ScanBoundaryHistory.boundary_run_id == run.id)
            .order_by(col(ScanBoundaryHistory.created_at).asc(), col(ScanBoundaryHistory.id).asc())
        ).all()
    )
    overlay_preview = None
    cover_preview = None
    artifact_reads: list[ScanBoundaryArtifactRead] = []
    for row in artifacts:
        preview = _load_artifact_preview(settings, row)
        if row.artifact_type == "BOUNDARY_OVERLAY":
            overlay_preview = preview
        if row.artifact_type == "COVER_BOX_PREVIEW":
            cover_preview = preview
        artifact_reads.append(_artifact_read(row, preview=preview))

    source_preview = None
    source_artifact = session.get(ScanNormalizationArtifact, run.source_artifact_id)
    if source_artifact is not None:
        try:
            with Image.open(_resolve_normalization_artifact_path(settings, source_artifact)) as image:
                source_preview = _data_url_for_image(_image_to_rgb(image))
        except (FileNotFoundError, OSError, ValueError, UnidentifiedImageError):
            source_preview = None

    geometry = dict(run.output_manifest_json.get("geometry") or {})
    confidence = (run.output_manifest_json.get("detection") or {}).get("confidence_score")
    return ScanBoundaryRunDetail(
        **_run_read(run).model_dump(),
        artifacts=artifact_reads,
        issues=[_issue_read(row) for row in issues],
        history=[_history_read(row) for row in history],
        original_scan_checksum=scan_image.sha256_checksum,
        normalized_source_checksum=run.source_checksum,
        source_preview_data_url=source_preview,
        boundary_overlay_preview_data_url=overlay_preview,
        cover_box_preview_data_url=cover_preview,
        geometry=geometry,
        confidence_score=float(confidence) if confidence is not None else None,
    )


def run_scan_boundary_mapping(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: ScanBoundaryRunCreate,
) -> tuple[ScanBoundaryRunDetail, bool]:
    scan_image = session.get(ScanImage, payload.scan_image_id)
    if scan_image is None or scan_image.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan image not found")

    norm_run, source_artifact = _resolve_normalization_context(
        session,
        owner_user_id=owner_user_id,
        scan_image=scan_image,
        normalization_run_id=payload.normalization_run_id,
    )

    input_manifest = {
        "scan_image_id": scan_image.id,
        "normalization_run_id": norm_run.id,
        "source_artifact_id": source_artifact.id,
        "source_checksum": source_artifact.artifact_checksum,
        "original_scan_checksum": scan_image.sha256_checksum,
        "algorithm_version": ALGORITHM_VERSION,
    }

    try:
        with Image.open(_resolve_normalization_artifact_path(settings, source_artifact)) as opened:
            rgb = _image_to_rgb(opened)
    except (FileNotFoundError, OSError, ValueError, UnidentifiedImageError) as exc:
        failed = _persist_failed_run(
            session,
            owner_user_id=owner_user_id,
            scan_image=scan_image,
            norm_run=norm_run,
            source_artifact=source_artifact,
            input_manifest=input_manifest,
            error_message=str(exc),
        )
        return _build_run_detail(session, settings, run=failed, scan_image=scan_image), False

    detection = detect_comic_boundary(rgb)
    background = separate_background_region(rgb, bbox=detection.bbox)
    geometry = calculate_cover_geometry(rgb, bbox=detection.bbox, polygon=detection.polygon)
    issues = _detect_boundary_issues(detection=detection, background=background, geometry=geometry, rgb=rgb)

    pre_manifest = {
        "algorithm_version": ALGORITHM_VERSION,
        "original_scan_checksum": scan_image.sha256_checksum,
        "source_checksum": source_artifact.artifact_checksum,
        "detection": {
            "polygon": detection.polygon,
            "bbox": list(detection.bbox),
            "confidence_score": detection.confidence_score,
            "detection_method": detection.detection_method,
        },
        "geometry": geometry.__dict__,
    }
    artifact_drafts = _build_artifact_drafts(
        rgb,
        detection=detection,
        geometry=geometry,
        background=background,
        manifest=pre_manifest,
    )
    artifact_checksum_rows = [
        {"artifact_type": draft.artifact_type, "artifact_checksum": _sha256_bytes(draft.body)}
        for draft in artifact_drafts
    ]
    output_manifest, boundary_checksum = build_boundary_manifest(
        algorithm_version=ALGORITHM_VERSION,
        original_scan_checksum=scan_image.sha256_checksum,
        source_checksum=source_artifact.artifact_checksum,
        detection=detection,
        background=background,
        geometry=geometry,
        issues=issues,
        artifact_checksums=artifact_checksum_rows,
    )

    existing = session.exec(
        select(ScanBoundaryRun)
        .where(
            ScanBoundaryRun.owner_user_id == owner_user_id,
            ScanBoundaryRun.boundary_checksum == boundary_checksum,
        )
        .order_by(col(ScanBoundaryRun.created_at).desc(), col(ScanBoundaryRun.id).desc())
    ).first()
    if existing is not None:
        return _build_run_detail(session, settings, run=existing, scan_image=scan_image), False

    history_drafts: list[_HistoryDraft] = []
    _append_history_drafts(
        history_drafts,
        event_type="RUN_STARTED",
        event_message="Boundary mapping run started.",
        metadata_json=input_manifest,
    )
    _append_history_drafts(
        history_drafts,
        event_type="BOUNDARY_DETECTED",
        event_message="Comic boundary geometry detected.",
        metadata_json={"confidence_score": detection.confidence_score, "bbox": list(detection.bbox)},
    )

    now = utc_now()
    run = ScanBoundaryRun(
        owner_user_id=owner_user_id,
        scan_image_id=int(scan_image.id or 0),
        normalization_run_id=int(norm_run.id or 0),
        source_artifact_id=int(source_artifact.id or 0),
        source_checksum=source_artifact.artifact_checksum,
        boundary_checksum=boundary_checksum,
        boundary_status="COMPLETE",
        algorithm_version=ALGORITHM_VERSION,
        input_manifest_json=input_manifest,
        output_manifest_json=output_manifest,
        created_at=now,
        completed_at=now,
    )
    session.add(run)
    session.flush()

    for draft in artifact_drafts:
        checksum = _sha256_bytes(draft.body)
        rel_path = _artifact_storage_path(
            owner_user_id=owner_user_id,
            scan_image_id=int(scan_image.id or 0),
            boundary_run_id=int(run.id or 0),
            artifact_type=draft.artifact_type,
            ext=draft.ext,
        )
        target = _resolve_boundary_storage_path(settings, rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(draft.body)
        session.add(
            ScanBoundaryArtifact(
                owner_user_id=owner_user_id,
                boundary_run_id=int(run.id or 0),
                scan_image_id=int(scan_image.id or 0),
                artifact_type=draft.artifact_type,
                storage_backend="filesystem",
                storage_path=rel_path,
                artifact_checksum=checksum,
                width_px=draft.width_px or rgb.width,
                height_px=draft.height_px or rgb.height,
                metadata_json=draft.metadata_json,
                created_at=now,
            )
        )
        _append_history_drafts(
            history_drafts,
            event_type="ARTIFACT_CREATED",
            event_message=f"Created {draft.artifact_type} artifact.",
            metadata_json={"artifact_type": draft.artifact_type, "artifact_checksum": checksum},
        )

    for issue in issues:
        session.add(
            ScanBoundaryIssue(
                owner_user_id=owner_user_id,
                boundary_run_id=int(run.id or 0),
                scan_image_id=int(scan_image.id or 0),
                issue_type=issue.issue_type,
                severity=issue.severity,
                issue_message=issue.issue_message,
                metadata_json=issue.metadata_json,
                created_at=now,
            )
        )

    _append_history_drafts(
        history_drafts,
        event_type="RUN_COMPLETED",
        event_message="Boundary mapping run completed.",
        metadata_json={"boundary_checksum": boundary_checksum},
    )

    for hist in history_drafts:
        session.add(
            ScanBoundaryHistory(
                owner_user_id=owner_user_id,
                boundary_run_id=int(run.id or 0),
                scan_image_id=int(scan_image.id or 0),
                event_type=hist.event_type,
                event_message=hist.event_message,
                event_checksum=_history_event_checksum(
                    boundary_run_id=int(run.id or 0),
                    event_type=hist.event_type,
                    event_message=hist.event_message,
                    metadata_json=hist.metadata_json,
                ),
                metadata_json=hist.metadata_json,
                created_at=now,
            )
        )

    session.commit()
    session.refresh(run)
    return _build_run_detail(session, settings, run=run, scan_image=scan_image), True


def _persist_failed_run(
    session: Session,
    *,
    owner_user_id: int,
    scan_image: ScanImage,
    norm_run: ScanNormalizationRun,
    source_artifact: ScanNormalizationArtifact,
    input_manifest: dict[str, Any],
    error_message: str,
) -> ScanBoundaryRun:
    boundary_checksum = _hash_payload({**input_manifest, "error_message": error_message, "status": "FAILED"})
    existing = session.exec(
        select(ScanBoundaryRun)
        .where(
            ScanBoundaryRun.owner_user_id == owner_user_id,
            ScanBoundaryRun.boundary_checksum == boundary_checksum,
        )
        .order_by(col(ScanBoundaryRun.created_at).desc(), col(ScanBoundaryRun.id).desc())
    ).first()
    if existing is not None:
        return existing
    now = utc_now()
    run = ScanBoundaryRun(
        owner_user_id=owner_user_id,
        scan_image_id=int(scan_image.id or 0),
        normalization_run_id=int(norm_run.id or 0),
        source_artifact_id=int(source_artifact.id or 0),
        source_checksum=source_artifact.artifact_checksum,
        boundary_checksum=boundary_checksum,
        boundary_status="FAILED",
        algorithm_version=ALGORITHM_VERSION,
        input_manifest_json=input_manifest,
        output_manifest_json={"error_message": error_message},
        created_at=now,
        completed_at=now,
    )
    session.add(run)
    session.flush()
    session.add(
        ScanBoundaryHistory(
            owner_user_id=owner_user_id,
            boundary_run_id=int(run.id or 0),
            scan_image_id=int(scan_image.id or 0),
            event_type="FAILED",
            event_message=error_message,
            event_checksum=_history_event_checksum(
                boundary_run_id=int(run.id or 0),
                event_type="FAILED",
                event_message=error_message,
                metadata_json={"error_message": error_message},
            ),
            metadata_json={"error_message": error_message},
            created_at=now,
        )
    )
    session.commit()
    session.refresh(run)
    return run


def _get_owner_run_or_404(session: Session, *, owner_user_id: int, run_id: int) -> ScanBoundaryRun:
    row = session.get(ScanBoundaryRun, run_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan boundary run not found")
    return row


def get_scan_boundary_run_owner(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    run_id: int,
) -> ScanBoundaryRunDetail:
    run = _get_owner_run_or_404(session, owner_user_id=owner_user_id, run_id=run_id)
    scan_image = session.get(ScanImage, run.scan_image_id)
    if scan_image is None:
        raise HTTPException(status_code=404, detail="Scan image not found")
    return _build_run_detail(session, settings, run=run, scan_image=scan_image)


def get_scan_boundary_artifact_owner(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    artifact_id: int,
) -> ScanBoundaryArtifactReadResponse:
    row = session.get(ScanBoundaryArtifact, artifact_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan boundary artifact not found")
    return ScanBoundaryArtifactReadResponse(
        artifact=_artifact_read(row, preview=_load_artifact_preview(settings, row)),
    )


def list_scan_boundary_runs_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanBoundaryRunListResponse:
    limit, offset = clamp_scan_boundary_pagination(limit=limit, offset=offset)
    stmt = select(ScanBoundaryRun).where(ScanBoundaryRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanBoundaryRun.scan_image_id == scan_image_id)
    stmt = stmt.order_by(col(ScanBoundaryRun.created_at).desc(), col(ScanBoundaryRun.id).desc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanBoundaryRun).where(ScanBoundaryRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        total_stmt = total_stmt.where(ScanBoundaryRun.scan_image_id == scan_image_id)
    total = session.exec(total_stmt).one()
    counts = session.exec(
        select(ScanBoundaryRun.boundary_status, func.count())
        .where(ScanBoundaryRun.owner_user_id == owner_user_id)
        .group_by(ScanBoundaryRun.boundary_status)
    ).all()
    low_confidence = 0
    for row in rows:
        conf = (row.output_manifest_json.get("detection") or {}).get("confidence_score")
        if conf is not None and float(conf) < _CONFIDENCE_LOW_THRESHOLD:
            low_confidence += 1
    unresolved = session.exec(
        select(func.count())
        .select_from(ScanBoundaryIssue)
        .where(
            ScanBoundaryIssue.owner_user_id == owner_user_id,
            ScanBoundaryIssue.severity.in_(("WARNING", "ERROR")),
        )
    ).one()
    return ScanBoundaryRunListResponse(
        items=[_run_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
        status_counts={str(k): int(v) for k, v in counts},
        low_confidence_run_count=low_confidence,
        unresolved_issue_count=int(unresolved or 0),
    )


def list_scan_boundary_runs_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanBoundaryRunListResponse:
    limit, offset = clamp_scan_boundary_pagination(limit=limit, offset=offset)
    stmt = select(ScanBoundaryRun)
    if owner_user_id is not None:
        stmt = stmt.where(ScanBoundaryRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanBoundaryRun.scan_image_id == scan_image_id)
    stmt = stmt.order_by(col(ScanBoundaryRun.created_at).desc(), col(ScanBoundaryRun.id).desc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanBoundaryRun)
    if owner_user_id is not None:
        total_stmt = total_stmt.where(ScanBoundaryRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        total_stmt = total_stmt.where(ScanBoundaryRun.scan_image_id == scan_image_id)
    total = session.exec(total_stmt).one()
    counts_stmt = select(ScanBoundaryRun.boundary_status, func.count()).group_by(ScanBoundaryRun.boundary_status)
    if owner_user_id is not None:
        counts_stmt = counts_stmt.where(ScanBoundaryRun.owner_user_id == owner_user_id)
    counts = session.exec(counts_stmt).all()
    low_confidence = sum(
        1
        for row in rows
        if float((row.output_manifest_json.get("detection") or {}).get("confidence_score") or 1.0)
        < _CONFIDENCE_LOW_THRESHOLD
    )
    unresolved_stmt = select(func.count()).select_from(ScanBoundaryIssue).where(ScanBoundaryIssue.severity.in_(("WARNING", "ERROR")))
    if owner_user_id is not None:
        unresolved_stmt = unresolved_stmt.where(ScanBoundaryIssue.owner_user_id == owner_user_id)
    unresolved = session.exec(unresolved_stmt).one()
    return ScanBoundaryRunListResponse(
        items=[_run_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
        status_counts={str(k): int(v) for k, v in counts},
        low_confidence_run_count=low_confidence,
        unresolved_issue_count=int(unresolved or 0),
    )


def list_scan_boundary_issues_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    boundary_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanBoundaryIssueListResponse:
    limit, offset = clamp_scan_boundary_pagination(limit=limit, offset=offset)
    stmt = select(ScanBoundaryIssue).where(ScanBoundaryIssue.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanBoundaryIssue.scan_image_id == scan_image_id)
    if boundary_run_id is not None:
        stmt = stmt.where(ScanBoundaryIssue.boundary_run_id == boundary_run_id)
    stmt = stmt.order_by(col(ScanBoundaryIssue.created_at).desc(), col(ScanBoundaryIssue.id).desc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanBoundaryIssue).where(ScanBoundaryIssue.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        total_stmt = total_stmt.where(ScanBoundaryIssue.scan_image_id == scan_image_id)
    if boundary_run_id is not None:
        total_stmt = total_stmt.where(ScanBoundaryIssue.boundary_run_id == boundary_run_id)
    total = session.exec(total_stmt).one()
    counts_stmt = (
        select(ScanBoundaryIssue.issue_type, func.count())
        .where(ScanBoundaryIssue.owner_user_id == owner_user_id)
        .group_by(ScanBoundaryIssue.issue_type)
    )
    counts = session.exec(counts_stmt).all()
    return ScanBoundaryIssueListResponse(
        items=[_issue_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
        issue_type_counts={str(k): int(v) for k, v in counts},
    )


def list_scan_boundary_issues_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    scan_image_id: int | None,
    boundary_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanBoundaryIssueListResponse:
    limit, offset = clamp_scan_boundary_pagination(limit=limit, offset=offset)
    stmt = select(ScanBoundaryIssue)
    if owner_user_id is not None:
        stmt = stmt.where(ScanBoundaryIssue.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanBoundaryIssue.scan_image_id == scan_image_id)
    if boundary_run_id is not None:
        stmt = stmt.where(ScanBoundaryIssue.boundary_run_id == boundary_run_id)
    stmt = stmt.order_by(col(ScanBoundaryIssue.created_at).desc(), col(ScanBoundaryIssue.id).desc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanBoundaryIssue)
    if owner_user_id is not None:
        total_stmt = total_stmt.where(ScanBoundaryIssue.owner_user_id == owner_user_id)
    total = session.exec(total_stmt).one()
    counts = session.exec(select(ScanBoundaryIssue.issue_type, func.count()).group_by(ScanBoundaryIssue.issue_type)).all()
    return ScanBoundaryIssueListResponse(
        items=[_issue_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
        issue_type_counts={str(k): int(v) for k, v in counts},
    )


def list_scan_boundary_failures_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanBoundaryFailureListResponse:
    limit, offset = clamp_scan_boundary_pagination(limit=limit, offset=offset)
    stmt = select(ScanBoundaryRun).where(ScanBoundaryRun.boundary_status == "FAILED")
    if owner_user_id is not None:
        stmt = stmt.where(ScanBoundaryRun.owner_user_id == owner_user_id)
    stmt = stmt.order_by(col(ScanBoundaryRun.created_at).desc(), col(ScanBoundaryRun.id).desc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanBoundaryRun).where(ScanBoundaryRun.boundary_status == "FAILED")
    if owner_user_id is not None:
        total_stmt = total_stmt.where(ScanBoundaryRun.owner_user_id == owner_user_id)
    total = session.exec(total_stmt).one()
    return ScanBoundaryFailureListResponse(
        items=[_run_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
    )
