from __future__ import annotations

import base64
import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from PIL import Image, ImageChops, ImageOps, ImageStat, UnidentifiedImageError
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models import (
    ScanImage,
    ScanNormalizationArtifact,
    ScanNormalizationHistory,
    ScanNormalizationIssue,
    ScanNormalizationRun,
)
from app.schemas.scan_normalization import (
    ScanNormalizationArtifactRead,
    ScanNormalizationFailureListResponse,
    ScanNormalizationHistoryRead,
    ScanNormalizationIssueListResponse,
    ScanNormalizationIssueRead,
    ScanNormalizationRunListResponse,
    ScanNormalizationRunPayload,
    ScanNormalizationRunRead,
    ScanNormalizationRunSummaryRead,
)

_PREVIEW_MAX = 420
_THUMBNAIL_MAX = 320


@dataclass(frozen=True)
class _ArtifactDraft:
    artifact_type: str
    artifact_order: int
    storage_path: str
    width: int
    height: int
    dpi_x: int | None
    dpi_y: int | None
    artifact_checksum: str
    parent_checksum: str | None
    metadata_json: dict[str, Any]
    parent_order: int | None = None


@dataclass(frozen=True)
class _IssueDraft:
    issue_type: str
    severity: str
    metric_value: str | None
    detail_json: dict[str, Any]


@dataclass(frozen=True)
class _HistoryDraft:
    history_order: int
    stage_name: str
    event_type: str
    from_checksum: str | None
    to_checksum: str | None
    detail_json: dict[str, Any]
    notes: str | None = None


@dataclass(frozen=True)
class _NormalizationPipeline:
    normalization_checksum: str
    orientation_code: str
    rotation_degrees: int
    crop_box: tuple[int, int, int, int]
    perspective_strength: int
    artifacts: list[_ArtifactDraft]
    issues: list[_IssueDraft]
    history: list[_HistoryDraft]
    summary_json: dict[str, Any]


def utc_now():
    from app.models.scan_normalization import utc_now as _utc_now

    return _utc_now()


def clamp_scan_normalization_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value).replace("\\", "/")
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _hash_payload(payload: Any) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _resolve_scan_source_path(settings: Settings, row: ScanImage) -> Path:
    rel = Path(str(row.storage_path))
    if row.storage_backend == "filesystem":
        base = settings.scan_ingestion_storage_root.resolve()
        target = (base / rel).resolve()
        if base != target and base not in target.parents:
            raise ValueError("scan image storage path escapes configured ingestion root")
        return target
    if rel.is_absolute():
        return rel
    candidate = rel.resolve()
    if candidate.exists():
        return candidate
    raise ValueError("scan image source is not available to the normalization engine")


def _resolve_normalization_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.scan_normalization_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("scan normalization storage path escapes configured root")
    return target


def _data_url_for_image(image: Image.Image) -> str:
    preview = image.copy()
    preview.thumbnail((_PREVIEW_MAX, _PREVIEW_MAX))
    rendered = io.BytesIO()
    preview.save(rendered, format="PNG")
    encoded = base64.b64encode(rendered.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _save_png_bytes(
    settings: Settings,
    *,
    relative_path: str,
    image: Image.Image,
    dpi: tuple[int, int] | None = None,
) -> bytes:
    target = _resolve_normalization_storage_path(settings, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rendered = io.BytesIO()
    save_kwargs: dict[str, Any] = {}
    if dpi is not None:
        save_kwargs["dpi"] = dpi
    image.save(rendered, format="PNG", **save_kwargs)
    body = rendered.getvalue()
    if not target.exists():
        target.write_bytes(body)
    return body


def _artifact_storage_path(
    *,
    scan_image_id: int,
    source_checksum: str,
    artifact_type: str,
    artifact_checksum: str,
) -> str:
    return (
        f"artifacts/{scan_image_id}/{artifact_type.lower()}/{source_checksum[:12]}-{artifact_checksum}.png"
    ).replace("\\", "/")


def _image_to_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image.copy()
    return image.convert("RGB")


def _normalize_orientation(image: Image.Image) -> tuple[Image.Image, str, int]:
    rgb = _image_to_rgb(image)
    orientation_code = "portrait"
    rotation_degrees = 0
    exif = image.getexif()
    orientation_tag = int(exif.get(274, 1))
    if orientation_tag == 3:
        rgb = rgb.rotate(180, expand=True)
        orientation_code = "upside_down"
        rotation_degrees = 180
    elif orientation_tag == 6:
        rgb = rgb.rotate(270, expand=True)
        orientation_code = "rotated_right"
        rotation_degrees = 270
    elif orientation_tag == 8:
        rgb = rgb.rotate(90, expand=True)
        orientation_code = "rotated_left"
        rotation_degrees = 90
    elif rgb.width > rgb.height:
        rgb = rgb.rotate(90, expand=True)
        orientation_code = "rotated_left"
        rotation_degrees = 90
    return rgb, orientation_code, rotation_degrees


def _detect_crop_box(image: Image.Image) -> tuple[int, int, int, int]:
    rgb = _image_to_rgb(image)
    corners = [
        rgb.getpixel((0, 0)),
        rgb.getpixel((rgb.width - 1, 0)),
        rgb.getpixel((0, rgb.height - 1)),
        rgb.getpixel((rgb.width - 1, rgb.height - 1)),
    ]
    background_color = tuple(int(round(sum(pixel[idx] for pixel in corners) / len(corners))) for idx in range(3))
    background = Image.new("RGB", rgb.size, background_color)
    diff = ImageChops.difference(rgb, background).convert("L")
    mask = diff.point(lambda p: 255 if p >= 12 else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return (0, 0, rgb.width, rgb.height)
    left, top, right, bottom = bbox
    left = max(0, left - 6)
    top = max(0, top - 6)
    right = min(rgb.width, right + 6)
    bottom = min(rgb.height, bottom + 6)
    area = max(1, (right - left) * (bottom - top))
    if area / max(1, rgb.width * rgb.height) < 0.65:
        return (0, 0, rgb.width, rgb.height)
    return (left, top, right, bottom)


def _normalize_crop(image: Image.Image) -> tuple[Image.Image, tuple[int, int, int, int]]:
    crop_box = _detect_crop_box(image)
    if crop_box == (0, 0, image.width, image.height):
        return image.copy(), crop_box
    return image.crop(crop_box), crop_box


def _normalize_perspective(
    image: Image.Image,
    *,
    crop_box: tuple[int, int, int, int],
    source_size: tuple[int, int],
) -> tuple[Image.Image, int]:
    source_width, source_height = source_size
    left_margin = crop_box[0]
    top_margin = crop_box[1]
    right_margin = max(0, source_width - crop_box[2])
    bottom_margin = max(0, source_height - crop_box[3])
    horizontal_bias = left_margin - right_margin
    vertical_bias = top_margin - bottom_margin
    perspective_strength = min(20, max(abs(horizontal_bias), abs(vertical_bias)))
    if perspective_strength <= 2:
        return image.copy(), 0

    width, height = image.size
    shift_x = max(-12, min(12, horizontal_bias // 2))
    shift_y = max(-12, min(12, vertical_bias // 2))
    quad = (
        max(0, shift_x),
        max(0, shift_y),
        width - max(0, -shift_x) - 1,
        max(0, -shift_y),
        width - max(0, shift_x) - 1,
        height - max(0, shift_y) - 1,
        max(0, -shift_x),
        height - max(0, -shift_y) - 1,
    )
    corrected = image.transform(image.size, Image.Transform.QUAD, quad, resample=Image.Resampling.BICUBIC)
    return corrected, perspective_strength


def _normalize_color(image: Image.Image) -> Image.Image:
    return ImageOps.autocontrast(_image_to_rgb(image), cutoff=1)


def _detect_issues(
    *,
    scan_image: ScanImage,
    crop_box: tuple[int, int, int, int],
    perspective_strength: int,
    final_image: Image.Image,
) -> list[_IssueDraft]:
    issues: list[_IssueDraft] = []
    dpi_candidates = [value for value in (scan_image.dpi_x, scan_image.dpi_y) if isinstance(value, int) and value > 0]
    min_dpi = min(dpi_candidates) if dpi_candidates else None
    if min_dpi is not None and min_dpi < 220:
        issues.append(
            _IssueDraft(
                issue_type="LOW_DPI",
                severity="warning",
                metric_value=str(min_dpi),
                detail_json={"min_dpi": min_dpi},
            )
        )

    gray = final_image.convert("L")
    stat = ImageStat.Stat(gray)
    mean_brightness = float(stat.mean[0]) if stat.mean else 0.0
    histogram = gray.histogram()
    total_pixels = max(1, gray.width * gray.height)
    dark_ratio = sum(histogram[:25]) / total_pixels
    light_ratio = sum(histogram[230:]) / total_pixels
    if perspective_strength >= 10:
        issues.append(
            _IssueDraft(
                issue_type="EXCESSIVE_SKEW",
                severity="warning",
                metric_value=str(perspective_strength),
                detail_json={"perspective_strength": perspective_strength},
            )
        )
    if dark_ratio > 0.30 and mean_brightness < 100:
        issues.append(
            _IssueDraft(
                issue_type="EXTREME_SHADOW",
                severity="warning",
                metric_value=f"{dark_ratio:.4f}",
                detail_json={"dark_ratio": round(dark_ratio, 6), "mean_brightness": round(mean_brightness, 2)},
            )
        )
    if light_ratio > 0.28 and mean_brightness > 220:
        issues.append(
            _IssueDraft(
                issue_type="OVEREXPOSED",
                severity="warning",
                metric_value=f"{light_ratio:.4f}",
                detail_json={"light_ratio": round(light_ratio, 6), "mean_brightness": round(mean_brightness, 2)},
            )
        )
    if dark_ratio > 0.45 or mean_brightness < 45:
        issues.append(
            _IssueDraft(
                issue_type="UNDEREXPOSED",
                severity="warning",
                metric_value=f"{mean_brightness:.2f}",
                detail_json={"dark_ratio": round(dark_ratio, 6), "mean_brightness": round(mean_brightness, 2)},
            )
        )

    full_width = max(1, scan_image.width or final_image.width)
    full_height = max(1, scan_image.height or final_image.height)
    coverage_ratio = ((crop_box[2] - crop_box[0]) * (crop_box[3] - crop_box[1])) / max(1, full_width * full_height)
    if coverage_ratio < 0.80:
        issues.append(
            _IssueDraft(
                issue_type="PARTIAL_SCAN",
                severity="warning",
                metric_value=f"{coverage_ratio:.4f}",
                detail_json={"coverage_ratio": round(coverage_ratio, 6), "crop_box": list(crop_box)},
            )
        )
    if crop_box[0] <= 1 or crop_box[1] <= 1 or crop_box[2] >= full_width - 1 or crop_box[3] >= full_height - 1:
        issues.append(
            _IssueDraft(
                issue_type="BORDER_CLIPPING",
                severity="info",
                metric_value=None,
                detail_json={"crop_box": list(crop_box), "full_size": [full_width, full_height]},
            )
        )
    return issues


def _serialize_issue(issue: _IssueDraft) -> dict[str, Any]:
    return {
        "issue_type": issue.issue_type,
        "severity": issue.severity,
        "metric_value": issue.metric_value,
        "detail_json": issue.detail_json,
    }


def _artifact_read(row: ScanNormalizationArtifact, *, preview_data_url: str | None = None) -> ScanNormalizationArtifactRead:
    return ScanNormalizationArtifactRead.model_validate(
        {**row.model_dump(mode="json"), "preview_data_url": preview_data_url}
    )


def _issue_read(row: ScanNormalizationIssue) -> ScanNormalizationIssueRead:
    return ScanNormalizationIssueRead.model_validate(row, from_attributes=True)


def _history_read(row: ScanNormalizationHistory) -> ScanNormalizationHistoryRead:
    return ScanNormalizationHistoryRead.model_validate(row, from_attributes=True)


def _run_summary_read(row: ScanNormalizationRun) -> ScanNormalizationRunSummaryRead:
    return ScanNormalizationRunSummaryRead.model_validate(row, from_attributes=True)


def _load_artifact_preview(settings: Settings, row: ScanNormalizationArtifact) -> str | None:
    try:
        path = _resolve_normalization_storage_path(settings, row.storage_path)
        with Image.open(path) as image:
            return _data_url_for_image(_image_to_rgb(image))
    except (FileNotFoundError, OSError, ValueError, UnidentifiedImageError):
        return None


def _build_run_detail(
    session: Session,
    settings: Settings,
    *,
    run: ScanNormalizationRun,
) -> ScanNormalizationRunRead:
    artifacts = list(
        session.exec(
            select(ScanNormalizationArtifact)
            .where(ScanNormalizationArtifact.scan_normalization_run_id == run.id)
            .order_by(col(ScanNormalizationArtifact.artifact_order).asc(), col(ScanNormalizationArtifact.id).asc())
        ).all()
    )
    issues = list(
        session.exec(
            select(ScanNormalizationIssue)
            .where(ScanNormalizationIssue.scan_normalization_run_id == run.id)
            .order_by(col(ScanNormalizationIssue.created_at).asc(), col(ScanNormalizationIssue.id).asc())
        ).all()
    )
    history = list(
        session.exec(
            select(ScanNormalizationHistory)
            .where(ScanNormalizationHistory.scan_normalization_run_id == run.id)
            .order_by(col(ScanNormalizationHistory.history_order).asc(), col(ScanNormalizationHistory.id).asc())
        ).all()
    )
    source_preview_data_url: str | None = None
    scan_image = session.get(ScanImage, run.scan_image_id)
    if scan_image is not None:
        try:
            source_path = _resolve_scan_source_path(settings, scan_image)
            with Image.open(source_path) as image:
                source_preview_data_url = _data_url_for_image(_image_to_rgb(image))
        except (FileNotFoundError, OSError, ValueError, UnidentifiedImageError):
            source_preview_data_url = None

    final_preview_data_url: str | None = None
    artifact_reads: list[ScanNormalizationArtifactRead] = []
    for row in artifacts:
        preview = _load_artifact_preview(settings, row) if row.id == run.final_artifact_id else None
        if row.id == run.final_artifact_id:
            final_preview_data_url = preview
        artifact_reads.append(_artifact_read(row, preview_data_url=preview))

    return ScanNormalizationRunRead(
        **_run_summary_read(run).model_dump(),
        artifacts=artifact_reads,
        issues=[_issue_read(row) for row in issues],
        history=[_history_read(row) for row in history],
        source_preview_data_url=source_preview_data_url,
        final_preview_data_url=final_preview_data_url,
    )


def _get_owner_run_or_404(session: Session, *, owner_user_id: int, run_id: int) -> ScanNormalizationRun:
    row = session.get(ScanNormalizationRun, run_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan normalization run not found")
    return row


def _get_owner_artifact_or_404(session: Session, *, owner_user_id: int, artifact_id: int) -> ScanNormalizationArtifact:
    row = session.get(ScanNormalizationArtifact, artifact_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan normalization artifact not found")
    return row


def _build_pipeline(settings: Settings, *, scan_image: ScanImage) -> _NormalizationPipeline:
    source_path = _resolve_scan_source_path(settings, scan_image)
    try:
        with Image.open(source_path) as opened:
            source_rgb = _image_to_rgb(opened)
    except (FileNotFoundError, OSError, ValueError, UnidentifiedImageError) as exc:
        raise ValueError("scan image could not be opened for normalization") from exc

    artifacts: list[_ArtifactDraft] = []
    history: list[_HistoryDraft] = []

    oriented, orientation_code, rotation_degrees = _normalize_orientation(source_rgb)
    rotated_checksum = _sha256_bytes(oriented.tobytes())
    rotated_path = _artifact_storage_path(
        scan_image_id=int(scan_image.id or 0),
        source_checksum=scan_image.sha256_checksum,
        artifact_type="ROTATED",
        artifact_checksum=rotated_checksum,
    )
    _save_png_bytes(settings, relative_path=rotated_path, image=oriented, dpi=(scan_image.dpi_x or 300, scan_image.dpi_y or 300))
    artifacts.append(
        _ArtifactDraft(
            artifact_type="ROTATED",
            artifact_order=1,
            storage_path=rotated_path,
            width=oriented.width,
            height=oriented.height,
            dpi_x=scan_image.dpi_x,
            dpi_y=scan_image.dpi_y,
            artifact_checksum=rotated_checksum,
            parent_checksum=scan_image.sha256_checksum,
            metadata_json={"orientation_code": orientation_code, "rotation_degrees": rotation_degrees},
        )
    )
    history.append(
        _HistoryDraft(
            history_order=1,
            stage_name="orientation",
            event_type="ORIENTATION_NORMALIZED",
            from_checksum=scan_image.sha256_checksum,
            to_checksum=rotated_checksum,
            detail_json={"orientation_code": orientation_code, "rotation_degrees": rotation_degrees},
        )
    )

    cropped, crop_box = _normalize_crop(oriented)
    cropped_checksum = _sha256_bytes(cropped.tobytes())
    cropped_path = _artifact_storage_path(
        scan_image_id=int(scan_image.id or 0),
        source_checksum=scan_image.sha256_checksum,
        artifact_type="CROPPED",
        artifact_checksum=cropped_checksum,
    )
    _save_png_bytes(settings, relative_path=cropped_path, image=cropped, dpi=(scan_image.dpi_x or 300, scan_image.dpi_y or 300))
    artifacts.append(
        _ArtifactDraft(
            artifact_type="CROPPED",
            artifact_order=2,
            storage_path=cropped_path,
            width=cropped.width,
            height=cropped.height,
            dpi_x=scan_image.dpi_x,
            dpi_y=scan_image.dpi_y,
            artifact_checksum=cropped_checksum,
            parent_checksum=rotated_checksum,
            metadata_json={"crop_box": list(crop_box)},
            parent_order=1,
        )
    )
    history.append(
        _HistoryDraft(
            history_order=2,
            stage_name="crop",
            event_type="CROP_NORMALIZED",
            from_checksum=rotated_checksum,
            to_checksum=cropped_checksum,
            detail_json={"crop_box": list(crop_box)},
        )
    )

    perspective_fixed, perspective_strength = _normalize_perspective(
        cropped,
        crop_box=crop_box,
        source_size=(source_rgb.width, source_rgb.height),
    )
    perspective_checksum = _sha256_bytes(perspective_fixed.tobytes())
    perspective_path = _artifact_storage_path(
        scan_image_id=int(scan_image.id or 0),
        source_checksum=scan_image.sha256_checksum,
        artifact_type="PERSPECTIVE_FIXED",
        artifact_checksum=perspective_checksum,
    )
    _save_png_bytes(
        settings,
        relative_path=perspective_path,
        image=perspective_fixed,
        dpi=(scan_image.dpi_x or 300, scan_image.dpi_y or 300),
    )
    artifacts.append(
        _ArtifactDraft(
            artifact_type="PERSPECTIVE_FIXED",
            artifact_order=3,
            storage_path=perspective_path,
            width=perspective_fixed.width,
            height=perspective_fixed.height,
            dpi_x=scan_image.dpi_x,
            dpi_y=scan_image.dpi_y,
            artifact_checksum=perspective_checksum,
            parent_checksum=cropped_checksum,
            metadata_json={"perspective_strength": perspective_strength},
            parent_order=2,
        )
    )
    history.append(
        _HistoryDraft(
            history_order=3,
            stage_name="perspective",
            event_type="PERSPECTIVE_NORMALIZED",
            from_checksum=cropped_checksum,
            to_checksum=perspective_checksum,
            detail_json={"perspective_strength": perspective_strength},
        )
    )

    color_normalized = _normalize_color(perspective_fixed)
    color_checksum = _sha256_bytes(color_normalized.tobytes())
    color_path = _artifact_storage_path(
        scan_image_id=int(scan_image.id or 0),
        source_checksum=scan_image.sha256_checksum,
        artifact_type="COLOR_NORMALIZED",
        artifact_checksum=color_checksum,
    )
    _save_png_bytes(settings, relative_path=color_path, image=color_normalized, dpi=(scan_image.dpi_x or 300, scan_image.dpi_y or 300))
    artifacts.append(
        _ArtifactDraft(
            artifact_type="COLOR_NORMALIZED",
            artifact_order=4,
            storage_path=color_path,
            width=color_normalized.width,
            height=color_normalized.height,
            dpi_x=scan_image.dpi_x,
            dpi_y=scan_image.dpi_y,
            artifact_checksum=color_checksum,
            parent_checksum=perspective_checksum,
            metadata_json={"histogram_cutoff": 1},
            parent_order=3,
        )
    )
    history.append(
        _HistoryDraft(
            history_order=4,
            stage_name="color",
            event_type="COLOR_NORMALIZED",
            from_checksum=perspective_checksum,
            to_checksum=color_checksum,
            detail_json={"histogram_cutoff": 1},
        )
    )

    final_image = color_normalized.copy()
    final_checksum = _sha256_bytes(final_image.tobytes())
    final_path = _artifact_storage_path(
        scan_image_id=int(scan_image.id or 0),
        source_checksum=scan_image.sha256_checksum,
        artifact_type="FINAL_NORMALIZED",
        artifact_checksum=final_checksum,
    )
    _save_png_bytes(settings, relative_path=final_path, image=final_image, dpi=(300, 300))
    artifacts.append(
        _ArtifactDraft(
            artifact_type="FINAL_NORMALIZED",
            artifact_order=5,
            storage_path=final_path,
            width=final_image.width,
            height=final_image.height,
            dpi_x=300,
            dpi_y=300,
            artifact_checksum=final_checksum,
            parent_checksum=color_checksum,
            metadata_json={"lineage_terminal": True},
            parent_order=4,
        )
    )
    history.append(
        _HistoryDraft(
            history_order=5,
            stage_name="final",
            event_type="FINAL_NORMALIZED",
            from_checksum=color_checksum,
            to_checksum=final_checksum,
            detail_json={"dpi": [300, 300]},
        )
    )

    thumbnail = final_image.copy()
    thumbnail.thumbnail((_THUMBNAIL_MAX, _THUMBNAIL_MAX))
    thumb_checksum = _sha256_bytes(thumbnail.tobytes())
    thumb_path = _artifact_storage_path(
        scan_image_id=int(scan_image.id or 0),
        source_checksum=scan_image.sha256_checksum,
        artifact_type="THUMBNAIL",
        artifact_checksum=thumb_checksum,
    )
    _save_png_bytes(settings, relative_path=thumb_path, image=thumbnail, dpi=(150, 150))
    artifacts.append(
        _ArtifactDraft(
            artifact_type="THUMBNAIL",
            artifact_order=6,
            storage_path=thumb_path,
            width=thumbnail.width,
            height=thumbnail.height,
            dpi_x=150,
            dpi_y=150,
            artifact_checksum=thumb_checksum,
            parent_checksum=final_checksum,
            metadata_json={"max_edge_px": _THUMBNAIL_MAX},
            parent_order=5,
        )
    )
    history.append(
        _HistoryDraft(
            history_order=6,
            stage_name="thumbnail",
            event_type="DERIVATIVE_GENERATED",
            from_checksum=final_checksum,
            to_checksum=thumb_checksum,
            detail_json={"max_edge_px": _THUMBNAIL_MAX},
        )
    )

    issues = _detect_issues(
        scan_image=scan_image,
        crop_box=crop_box,
        perspective_strength=perspective_strength,
        final_image=final_image,
    )
    for idx, issue in enumerate(issues, start=7):
        history.append(
            _HistoryDraft(
                history_order=idx,
                stage_name="issues",
                event_type="ISSUE_RECORDED",
                from_checksum=final_checksum,
                to_checksum=final_checksum,
                detail_json=_serialize_issue(issue),
            )
        )

    normalization_checksum = _hash_payload(
        {
            "scan_image_id": scan_image.id,
            "source_sha256_checksum": scan_image.sha256_checksum,
            "orientation_code": orientation_code,
            "rotation_degrees": rotation_degrees,
            "crop_box": list(crop_box),
            "perspective_strength": perspective_strength,
            "artifacts": [
                {
                    "artifact_type": artifact.artifact_type,
                    "artifact_order": artifact.artifact_order,
                    "artifact_checksum": artifact.artifact_checksum,
                    "parent_checksum": artifact.parent_checksum,
                }
                for artifact in artifacts
            ],
            "issues": [_serialize_issue(issue) for issue in issues],
        }
    )
    return _NormalizationPipeline(
        normalization_checksum=normalization_checksum,
        orientation_code=orientation_code,
        rotation_degrees=rotation_degrees,
        crop_box=crop_box,
        perspective_strength=perspective_strength,
        artifacts=artifacts,
        issues=issues,
        history=history,
        summary_json={
            "source_dimensions": [source_rgb.width, source_rgb.height],
            "final_dimensions": [final_image.width, final_image.height],
            "issue_types": [issue.issue_type for issue in issues],
        },
    )


def _persist_failed_run(
    session: Session,
    *,
    owner_user_id: int,
    scan_image: ScanImage,
    error_message: str,
) -> ScanNormalizationRun:
    failure_checksum = _hash_payload(
        {
            "scan_image_id": scan_image.id,
            "source_sha256_checksum": scan_image.sha256_checksum,
            "error_message": error_message,
        }
    )
    existing = session.exec(
        select(ScanNormalizationRun)
        .where(
            ScanNormalizationRun.owner_user_id == owner_user_id,
            ScanNormalizationRun.normalization_checksum == failure_checksum,
        )
        .order_by(col(ScanNormalizationRun.created_at).desc(), col(ScanNormalizationRun.id).desc())
    ).first()
    if existing is not None:
        return existing
    now = utc_now()
    run = ScanNormalizationRun(
        owner_user_id=owner_user_id,
        scan_image_id=int(scan_image.id or 0),
        source_sha256_checksum=scan_image.sha256_checksum,
        normalization_checksum=failure_checksum,
        normalization_status="FAILED",
        orientation_code="portrait",
        rotation_degrees=0,
        crop_left=0,
        crop_top=0,
        crop_right=0,
        crop_bottom=0,
        perspective_strength=0,
        issue_count=0,
        artifact_count=0,
        replayed_from_run_id=None,
        final_artifact_id=None,
        summary_json={"error_message": error_message},
        created_at=now,
        completed_at=now,
    )
    session.add(run)
    session.flush()
    session.add(
        ScanNormalizationHistory(
            scan_normalization_run_id=int(run.id or 0),
            owner_user_id=owner_user_id,
            scan_image_id=int(scan_image.id or 0),
            history_order=0,
            stage_name="run",
            event_type="FAILED",
            from_checksum=scan_image.sha256_checksum,
            to_checksum=failure_checksum,
            detail_json={"error_message": error_message},
            notes=error_message,
            created_at=now,
        )
    )
    session.commit()
    session.refresh(run)
    return run


def _persist_run(
    session: Session,
    *,
    owner_user_id: int,
    scan_image: ScanImage,
    pipeline: _NormalizationPipeline,
) -> ScanNormalizationRun:
    run = ScanNormalizationRun(
        owner_user_id=owner_user_id,
        scan_image_id=int(scan_image.id or 0),
        source_sha256_checksum=scan_image.sha256_checksum,
        normalization_checksum=pipeline.normalization_checksum,
        normalization_status="COMPLETE",
        orientation_code=pipeline.orientation_code,
        rotation_degrees=pipeline.rotation_degrees,
        crop_left=pipeline.crop_box[0],
        crop_top=pipeline.crop_box[1],
        crop_right=max(0, (scan_image.width or pipeline.crop_box[2]) - pipeline.crop_box[2]),
        crop_bottom=max(0, (scan_image.height or pipeline.crop_box[3]) - pipeline.crop_box[3]),
        perspective_strength=pipeline.perspective_strength,
        issue_count=len(pipeline.issues),
        artifact_count=len(pipeline.artifacts),
        replayed_from_run_id=None,
        final_artifact_id=None,
        summary_json=pipeline.summary_json,
        created_at=utc_now(),
        completed_at=utc_now(),
    )
    session.add(run)
    session.flush()

    artifact_id_by_order: dict[int, int] = {}
    final_artifact_id: int | None = None
    for artifact in pipeline.artifacts:
        row = ScanNormalizationArtifact(
            scan_normalization_run_id=int(run.id or 0),
            owner_user_id=owner_user_id,
            scan_image_id=int(scan_image.id or 0),
            parent_artifact_id=artifact_id_by_order.get(artifact.parent_order) if artifact.parent_order is not None else None,
            artifact_type=artifact.artifact_type,
            artifact_order=artifact.artifact_order,
            storage_backend="filesystem",
            storage_path=artifact.storage_path,
            width=artifact.width,
            height=artifact.height,
            dpi_x=artifact.dpi_x,
            dpi_y=artifact.dpi_y,
            artifact_checksum=artifact.artifact_checksum,
            parent_checksum=artifact.parent_checksum,
            normalization_status="COMPLETE",
            metadata_json=artifact.metadata_json,
            created_at=utc_now(),
        )
        session.add(row)
        session.flush()
        if row.id is not None:
            artifact_id_by_order[artifact.artifact_order] = int(row.id)
            if artifact.artifact_type == "FINAL_NORMALIZED":
                final_artifact_id = int(row.id)

    for issue in pipeline.issues:
        session.add(
            ScanNormalizationIssue(
                scan_normalization_run_id=int(run.id or 0),
                owner_user_id=owner_user_id,
                scan_image_id=int(scan_image.id or 0),
                issue_type=issue.issue_type,
                severity=issue.severity,
                normalization_status="COMPLETE",
                metric_value=issue.metric_value,
                detail_json=issue.detail_json,
                created_at=utc_now(),
            )
        )

    for hist in pipeline.history:
        session.add(
            ScanNormalizationHistory(
                scan_normalization_run_id=int(run.id or 0),
                owner_user_id=owner_user_id,
                scan_image_id=int(scan_image.id or 0),
                history_order=hist.history_order,
                stage_name=hist.stage_name,
                event_type=hist.event_type,
                from_checksum=hist.from_checksum,
                to_checksum=hist.to_checksum,
                detail_json=hist.detail_json,
                notes=hist.notes,
                created_at=utc_now(),
            )
        )

    run.final_artifact_id = final_artifact_id
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def run_scan_normalization(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: ScanNormalizationRunPayload,
) -> tuple[ScanNormalizationRunRead, bool]:
    scan_image = session.get(ScanImage, payload.scan_image_id)
    if scan_image is None or scan_image.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan image not found")
    try:
        pipeline = _build_pipeline(settings, scan_image=scan_image)
    except ValueError as exc:
        failed = _persist_failed_run(session, owner_user_id=owner_user_id, scan_image=scan_image, error_message=str(exc))
        return _build_run_detail(session, settings, run=failed), False

    existing = session.exec(
        select(ScanNormalizationRun)
        .where(
            ScanNormalizationRun.owner_user_id == owner_user_id,
            ScanNormalizationRun.normalization_checksum == pipeline.normalization_checksum,
        )
        .order_by(col(ScanNormalizationRun.created_at).desc(), col(ScanNormalizationRun.id).desc())
    ).first()
    if existing is not None:
        return _build_run_detail(session, settings, run=existing), False

    run = _persist_run(session, owner_user_id=owner_user_id, scan_image=scan_image, pipeline=pipeline)
    return _build_run_detail(session, settings, run=run), True


def get_scan_normalization_run_owner(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    run_id: int,
) -> ScanNormalizationRunRead:
    return _build_run_detail(session, settings, run=_get_owner_run_or_404(session, owner_user_id=owner_user_id, run_id=run_id))


def get_scan_normalization_artifact_owner(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    artifact_id: int,
) -> ScanNormalizationArtifactRead:
    row = _get_owner_artifact_or_404(session, owner_user_id=owner_user_id, artifact_id=artifact_id)
    return _artifact_read(row, preview_data_url=_load_artifact_preview(settings, row))


def list_scan_normalization_runs_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanNormalizationRunListResponse:
    limit, offset = clamp_scan_normalization_pagination(limit=limit, offset=offset)
    stmt = select(ScanNormalizationRun).where(ScanNormalizationRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanNormalizationRun.scan_image_id == scan_image_id)
    stmt = stmt.order_by(col(ScanNormalizationRun.created_at).desc(), col(ScanNormalizationRun.id).desc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanNormalizationRun).where(ScanNormalizationRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        total_stmt = total_stmt.where(ScanNormalizationRun.scan_image_id == scan_image_id)
    total = session.exec(total_stmt).one()
    counts_stmt = select(ScanNormalizationRun.normalization_status, func.count()).where(
        ScanNormalizationRun.owner_user_id == owner_user_id
    ).group_by(ScanNormalizationRun.normalization_status)
    if scan_image_id is not None:
        counts_stmt = counts_stmt.where(ScanNormalizationRun.scan_image_id == scan_image_id)
    counts = session.exec(counts_stmt).all()
    replay_count = len({row.normalization_checksum for row in rows})
    return ScanNormalizationRunListResponse(
        items=[_run_summary_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
        status_counts={str(key): int(value) for key, value in counts},
        replay_safe_run_count=replay_count,
    )


def list_scan_normalization_runs_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanNormalizationRunListResponse:
    limit, offset = clamp_scan_normalization_pagination(limit=limit, offset=offset)
    stmt = select(ScanNormalizationRun)
    if owner_user_id is not None:
        stmt = stmt.where(ScanNormalizationRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanNormalizationRun.scan_image_id == scan_image_id)
    stmt = stmt.order_by(col(ScanNormalizationRun.created_at).desc(), col(ScanNormalizationRun.id).desc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanNormalizationRun)
    if owner_user_id is not None:
        total_stmt = total_stmt.where(ScanNormalizationRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        total_stmt = total_stmt.where(ScanNormalizationRun.scan_image_id == scan_image_id)
    total = session.exec(total_stmt).one()
    counts_stmt = select(ScanNormalizationRun.normalization_status, func.count()).group_by(ScanNormalizationRun.normalization_status)
    if owner_user_id is not None:
        counts_stmt = counts_stmt.where(ScanNormalizationRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        counts_stmt = counts_stmt.where(ScanNormalizationRun.scan_image_id == scan_image_id)
    counts = session.exec(counts_stmt).all()
    replay_count = len({row.normalization_checksum for row in rows})
    return ScanNormalizationRunListResponse(
        items=[_run_summary_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
        status_counts={str(key): int(value) for key, value in counts},
        replay_safe_run_count=replay_count,
    )


def list_scan_normalization_issues_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    run_id: int | None,
    limit: int,
    offset: int,
) -> ScanNormalizationIssueListResponse:
    limit, offset = clamp_scan_normalization_pagination(limit=limit, offset=offset)
    stmt = select(ScanNormalizationIssue).where(ScanNormalizationIssue.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanNormalizationIssue.scan_image_id == scan_image_id)
    if run_id is not None:
        stmt = stmt.where(ScanNormalizationIssue.scan_normalization_run_id == run_id)
    stmt = stmt.order_by(col(ScanNormalizationIssue.created_at).desc(), col(ScanNormalizationIssue.id).desc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanNormalizationIssue).where(ScanNormalizationIssue.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        total_stmt = total_stmt.where(ScanNormalizationIssue.scan_image_id == scan_image_id)
    if run_id is not None:
        total_stmt = total_stmt.where(ScanNormalizationIssue.scan_normalization_run_id == run_id)
    total = session.exec(total_stmt).one()
    counts_stmt = select(ScanNormalizationIssue.issue_type, func.count()).where(
        ScanNormalizationIssue.owner_user_id == owner_user_id
    ).group_by(ScanNormalizationIssue.issue_type)
    if scan_image_id is not None:
        counts_stmt = counts_stmt.where(ScanNormalizationIssue.scan_image_id == scan_image_id)
    if run_id is not None:
        counts_stmt = counts_stmt.where(ScanNormalizationIssue.scan_normalization_run_id == run_id)
    counts = session.exec(counts_stmt).all()
    return ScanNormalizationIssueListResponse(
        items=[_issue_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
        issue_type_counts={str(key): int(value) for key, value in counts},
    )


def list_scan_normalization_issues_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    scan_image_id: int | None,
    run_id: int | None,
    limit: int,
    offset: int,
) -> ScanNormalizationIssueListResponse:
    limit, offset = clamp_scan_normalization_pagination(limit=limit, offset=offset)
    stmt = select(ScanNormalizationIssue)
    if owner_user_id is not None:
        stmt = stmt.where(ScanNormalizationIssue.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanNormalizationIssue.scan_image_id == scan_image_id)
    if run_id is not None:
        stmt = stmt.where(ScanNormalizationIssue.scan_normalization_run_id == run_id)
    stmt = stmt.order_by(col(ScanNormalizationIssue.created_at).desc(), col(ScanNormalizationIssue.id).desc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanNormalizationIssue)
    if owner_user_id is not None:
        total_stmt = total_stmt.where(ScanNormalizationIssue.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        total_stmt = total_stmt.where(ScanNormalizationIssue.scan_image_id == scan_image_id)
    if run_id is not None:
        total_stmt = total_stmt.where(ScanNormalizationIssue.scan_normalization_run_id == run_id)
    total = session.exec(total_stmt).one()
    counts_stmt = select(ScanNormalizationIssue.issue_type, func.count()).group_by(ScanNormalizationIssue.issue_type)
    if owner_user_id is not None:
        counts_stmt = counts_stmt.where(ScanNormalizationIssue.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        counts_stmt = counts_stmt.where(ScanNormalizationIssue.scan_image_id == scan_image_id)
    if run_id is not None:
        counts_stmt = counts_stmt.where(ScanNormalizationIssue.scan_normalization_run_id == run_id)
    counts = session.exec(counts_stmt).all()
    return ScanNormalizationIssueListResponse(
        items=[_issue_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
        issue_type_counts={str(key): int(value) for key, value in counts},
    )


def list_scan_normalization_failures_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanNormalizationFailureListResponse:
    limit, offset = clamp_scan_normalization_pagination(limit=limit, offset=offset)
    stmt = select(ScanNormalizationRun).where(ScanNormalizationRun.normalization_status == "FAILED")
    if owner_user_id is not None:
        stmt = stmt.where(ScanNormalizationRun.owner_user_id == owner_user_id)
    stmt = stmt.order_by(col(ScanNormalizationRun.created_at).desc(), col(ScanNormalizationRun.id).desc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanNormalizationRun).where(
        ScanNormalizationRun.normalization_status == "FAILED"
    )
    if owner_user_id is not None:
        total_stmt = total_stmt.where(ScanNormalizationRun.owner_user_id == owner_user_id)
    total = session.exec(total_stmt).one()
    return ScanNormalizationFailureListResponse(
        items=[_run_summary_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
    )
