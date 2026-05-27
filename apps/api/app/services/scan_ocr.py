from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageStat, UnidentifiedImageError
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models import (
    ScanBoundaryArtifact,
    ScanBoundaryIssue,
    ScanBoundaryRun,
    ScanImage,
    ScanNormalizationArtifact,
    ScanNormalizationRun,
    ScanOcrArtifact,
    ScanOcrCandidate,
    ScanOcrHistory,
    ScanOcrIssue,
    ScanOcrRun,
    ScanOcrTextRegion,
)
from app.schemas.scan_ocr import (
    ScanOcrArtifactRead,
    ScanOcrCandidateListResponse,
    ScanOcrCandidateRead,
    ScanOcrFailureListResponse,
    ScanOcrHistoryRead,
    ScanOcrIssueListResponse,
    ScanOcrIssueRead,
    ScanOcrRunCreate,
    ScanOcrRunDetail,
    ScanOcrRunListResponse,
    ScanOcrRunRead,
    ScanOcrTextRegionRead,
)
from app.services.cover_images import (
    _run_tesseract_ocr_with_test_compat,
    get_tesseract_engine_version,
    normalize_ocr_text as normalize_cover_ocr_text,
)

OCR_ENGINE_NAME = "tesseract"
OCR_ENGINE_VERSION_FALLBACK = "unknown"
OCR_EXTRACTION_VERSION = "P40-04-v1"
_PREVIEW_MAX = 420
_LOW_CONFIDENCE_THRESHOLD = 0.55
_REGION_ORDER = ("TITLE", "ISSUE_NUMBER", "PUBLISHER", "DATE", "PRICE_BOX", "LOGO", "GENERIC_TEXT")
_CANDIDATE_ORDER = ("TITLE", "ISSUE_NUMBER", "PUBLISHER", "DATE", "PRICE")
_KNOWN_PUBLISHERS = (
    "MARVEL",
    "DC",
    "DC COMICS",
    "IMAGE",
    "IMAGE COMICS",
    "DARK HORSE",
    "BOOM!",
    "DYNAMITE",
    "IDW",
)


@dataclass(frozen=True)
class _Zone:
    region_type: str
    box: tuple[int, int, int, int]
    rotation_angle: float
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _RegionDraft:
    region_type: str
    extracted_text: str
    normalized_text: str | None
    confidence_score: float
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    width_px: int
    height_px: int
    rotation_angle: float
    metadata_json: dict[str, Any]


@dataclass(frozen=True)
class _CandidateDraft:
    candidate_type: str
    candidate_value: str
    normalized_candidate_value: str | None
    confidence_score: float
    source_region_type: str
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
    from app.models.scan_ocr import utc_now as _utc_now

    return _utc_now()


def clamp_scan_ocr_pagination(*, limit: int, offset: int) -> tuple[int, int]:
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


def _resolve_ocr_storage_path(settings: Settings, relative_path: str) -> Path:
    base = settings.scan_ocr_storage_root.resolve()
    target = (base / relative_path).resolve()
    if base != target and base not in target.parents:
        raise ValueError("scan ocr storage path escapes configured root")
    return target


def _artifact_storage_path(*, owner_user_id: int, scan_image_id: int, ocr_run_id: int, artifact_type: str, ext: str) -> str:
    safe_type = artifact_type.lower()
    return f"scan-ocr/{owner_user_id}/{scan_image_id}/{ocr_run_id}/{safe_type}{ext}".replace("\\", "/")


def _zone_temp_path(*, settings: Settings, source_checksum: str, region_type: str) -> Path:
    safe_region = region_type.lower()
    relative = f"tmp_zones/{source_checksum[:12]}-{safe_region}.png"
    path = _resolve_ocr_storage_path(settings, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


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


def _coerce_box(box: tuple[int, int, int, int], *, width: int, height: int) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    left = max(0, min(left, width - 1))
    top = max(0, min(top, height - 1))
    right = max(left + 1, min(right, width))
    bottom = max(top + 1, min(bottom, height))
    return left, top, right, bottom


def derive_ocr_zones(*, boundary_geometry: dict[str, Any], image_width: int, image_height: int) -> list[_Zone]:
    x_min = int(boundary_geometry.get("x_min") or 0)
    y_min = int(boundary_geometry.get("y_min") or 0)
    x_max = int(boundary_geometry.get("x_max") or max(0, image_width - 1))
    y_max = int(boundary_geometry.get("y_max") or max(0, image_height - 1))
    box = _coerce_box((x_min, y_min, x_max + 1, y_max + 1), width=image_width, height=image_height)
    left, top, right, bottom = box
    width = max(1, right - left)
    height = max(1, bottom - top)
    angle = float(boundary_geometry.get("angle_degrees") or 0.0)

    zones = [
        _Zone("TITLE", _coerce_box((left, top, left + int(width * 0.95), top + int(height * 0.28)), width=image_width, height=image_height), angle, {"zone_strategy": "top_banner"}),
        _Zone("ISSUE_NUMBER", _coerce_box((left + int(width * 0.68), top, right, top + int(height * 0.20)), width=image_width, height=image_height), angle, {"zone_strategy": "top_right_corner"}),
        _Zone("PUBLISHER", _coerce_box((left, bottom - int(height * 0.18), left + int(width * 0.36), bottom), width=image_width, height=image_height), angle, {"zone_strategy": "bottom_left_logo"}),
        _Zone("DATE", _coerce_box((left, top, left + int(width * 0.30), top + int(height * 0.18)), width=image_width, height=image_height), angle, {"zone_strategy": "top_left_date"}),
        _Zone("PRICE_BOX", _coerce_box((left, top, left + int(width * 0.24), top + int(height * 0.16)), width=image_width, height=image_height), angle, {"zone_strategy": "top_left_price"}),
        _Zone("LOGO", _coerce_box((left, top, left + int(width * 0.34), top + int(height * 0.24)), width=image_width, height=image_height), angle, {"zone_strategy": "logo_cluster"}),
        _Zone("GENERIC_TEXT", box, angle, {"zone_strategy": "full_cover"}),
    ]
    return sorted(zones, key=lambda row: _REGION_ORDER.index(row.region_type))


def _save_region_crop_for_ocr(settings: Settings, *, image: Image.Image, zone: _Zone, source_checksum: str) -> Path:
    path = _zone_temp_path(settings=settings, source_checksum=source_checksum, region_type=zone.region_type)
    crop = image.crop(zone.box)
    if not path.exists():
        crop.save(path, format="PNG")
    return path


def _estimate_region_confidence(*, crop: Image.Image, normalized_text: str | None) -> float:
    gray = crop.convert("L")
    stat = ImageStat.Stat(gray)
    spread = float(stat.extrema[0][1] - stat.extrema[0][0]) if stat.extrema else 0.0
    contrast_score = min(1.0, spread / 90.0)
    text_len = len(normalized_text or "")
    text_score = min(1.0, text_len / 18.0) if text_len > 0 else 0.0
    return round(min(1.0, max(0.0, contrast_score * 0.55 + text_score * 0.45)), 6)


def normalize_ocr_text(raw_text: str) -> str | None:
    normalized = normalize_cover_ocr_text(raw_text)
    if normalized is None:
        return None
    normalized = unicodedata.normalize("NFKC", normalized)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip() or None


def extract_text_regions(
    settings: Settings,
    *,
    image: Image.Image,
    zones: list[_Zone],
    source_checksum: str,
    timeout_seconds: float,
) -> list[_RegionDraft]:
    rows: list[_RegionDraft] = []
    for zone in zones:
        path = _save_region_crop_for_ocr(settings, image=image, zone=zone, source_checksum=source_checksum)
        crop = image.crop(zone.box)
        raw_text = _run_tesseract_ocr_with_test_compat(path, timeout_seconds=timeout_seconds)
        normalized_text = normalize_ocr_text(raw_text)
        confidence = _estimate_region_confidence(crop=crop, normalized_text=normalized_text)
        left, top, right, bottom = zone.box
        rows.append(
            _RegionDraft(
                region_type=zone.region_type,
                extracted_text=raw_text,
                normalized_text=normalized_text,
                confidence_score=confidence,
                x_min=left,
                y_min=top,
                x_max=right - 1,
                y_max=bottom - 1,
                width_px=max(1, right - left),
                height_px=max(1, bottom - top),
                rotation_angle=zone.rotation_angle,
                metadata_json=dict(zone.metadata_json),
            )
        )
    return rows


def _normalize_title_candidate(value: str) -> str | None:
    base = normalize_ocr_text(value)
    if base is None:
        return None
    corrected = re.sub(r"(?<=[A-Z])1(?=[A-Z])", "I", base.upper())
    corrected = re.sub(r"(?<=[A-Z])0(?=[A-Z])", "O", corrected)
    return corrected.title().replace("'S", "'s")


def _normalize_issue_candidate(value: str) -> str | None:
    base = normalize_ocr_text(value)
    if base is None:
        return None
    match = re.search(r"#?\s*([0-9]{1,4}[A-Z]?)", base.upper())
    if match is None:
        return None
    return match.group(1)


def _normalize_date_candidate(value: str) -> str | None:
    base = normalize_ocr_text(value)
    if base is None:
        return None
    month_year = re.search(r"\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+([0-9]{2,4})\b", base.upper())
    if month_year is not None:
        return f"{month_year.group(1)} {month_year.group(2)}"
    iso_like = re.search(r"\b([0-9]{1,2})[/-]([0-9]{2,4})\b", base)
    if iso_like is not None:
        return f"{iso_like.group(1)}/{iso_like.group(2)}"
    return None


def _normalize_price_candidate(value: str) -> str | None:
    base = normalize_ocr_text(value)
    if base is None:
        return None
    price = re.search(r"(\$?\d+\.\d{2}|\d+\s?¢)", base.replace(" ", ""))
    if price is None:
        return None
    candidate = price.group(1).replace("¢", "¢")
    if candidate.endswith("¢"):
        return candidate
    return candidate if candidate.startswith("$") else f"${candidate}"


def _candidate_confidence(region_confidence: float, *, bonus: float = 0.0) -> float:
    return round(min(1.0, max(0.0, region_confidence + bonus)), 6)


def generate_ocr_candidates(regions: list[_RegionDraft]) -> list[_CandidateDraft]:
    rows: list[_CandidateDraft] = []
    for region in regions:
        normalized = region.normalized_text
        if not normalized:
            continue
        if region.region_type in {"TITLE", "GENERIC_TEXT"}:
            title_line = normalized.splitlines()[0].strip()
            normalized_title = _normalize_title_candidate(title_line)
            if normalized_title:
                rows.append(
                    _CandidateDraft(
                        candidate_type="TITLE",
                        candidate_value=title_line,
                        normalized_candidate_value=normalized_title,
                        confidence_score=_candidate_confidence(region.confidence_score, bonus=0.08 if region.region_type == "TITLE" else 0.0),
                        source_region_type=region.region_type,
                        metadata_json={"source_region_type": region.region_type},
                    )
                )

        issue_value = _normalize_issue_candidate(normalized)
        if region.region_type in {"ISSUE_NUMBER", "GENERIC_TEXT"} and issue_value:
            rows.append(
                _CandidateDraft(
                    candidate_type="ISSUE_NUMBER",
                    candidate_value=issue_value,
                    normalized_candidate_value=issue_value,
                    confidence_score=_candidate_confidence(region.confidence_score, bonus=0.06 if region.region_type == "ISSUE_NUMBER" else 0.0),
                    source_region_type=region.region_type,
                    metadata_json={"source_region_type": region.region_type},
                )
            )

        if region.region_type in {"PUBLISHER", "GENERIC_TEXT"}:
            upper = normalized.upper()
            for publisher in _KNOWN_PUBLISHERS:
                if publisher in upper:
                    rows.append(
                        _CandidateDraft(
                            candidate_type="PUBLISHER",
                            candidate_value=publisher,
                            normalized_candidate_value=publisher.title(),
                            confidence_score=_candidate_confidence(region.confidence_score, bonus=0.1 if region.region_type == "PUBLISHER" else 0.0),
                            source_region_type=region.region_type,
                            metadata_json={"source_region_type": region.region_type},
                        )
                    )
                    break

        if region.region_type in {"DATE", "GENERIC_TEXT"}:
            date_value = _normalize_date_candidate(normalized)
            if date_value:
                rows.append(
                    _CandidateDraft(
                        candidate_type="DATE",
                        candidate_value=date_value,
                        normalized_candidate_value=date_value,
                        confidence_score=_candidate_confidence(region.confidence_score, bonus=0.06 if region.region_type == "DATE" else 0.0),
                        source_region_type=region.region_type,
                        metadata_json={"source_region_type": region.region_type},
                    )
                )

        if region.region_type in {"PRICE_BOX", "GENERIC_TEXT"}:
            price_value = _normalize_price_candidate(normalized)
            if price_value:
                rows.append(
                    _CandidateDraft(
                        candidate_type="PRICE",
                        candidate_value=price_value,
                        normalized_candidate_value=price_value,
                        confidence_score=_candidate_confidence(region.confidence_score, bonus=0.06 if region.region_type == "PRICE_BOX" else 0.0),
                        source_region_type=region.region_type,
                        metadata_json={"source_region_type": region.region_type},
                    )
                )

    deduped: dict[tuple[str, str, str], _CandidateDraft] = {}
    for row in rows:
        key = (row.candidate_type, row.normalized_candidate_value or "", row.source_region_type)
        existing = deduped.get(key)
        if existing is None or row.confidence_score > existing.confidence_score:
            deduped[key] = row
    return sorted(
        deduped.values(),
        key=lambda row: (_CANDIDATE_ORDER.index(row.candidate_type), -(row.confidence_score), row.normalized_candidate_value or row.candidate_value),
    )


def _artifact_previewable(artifact_type: str) -> bool:
    return artifact_type in {"OCR_OVERLAY", "OCR_REGION_MAP", "OCR_DEBUG_PREVIEW"}


def _build_overlay_artifacts(image: Image.Image, regions: list[_RegionDraft], boundary_geometry: dict[str, Any]) -> list[_ArtifactDraft]:
    rgb = _image_to_rgb(image)

    overlay = rgb.copy()
    overlay_draw = ImageDraw.Draw(overlay)
    for region in regions:
        tone = (40, 200, 120) if region.confidence_score >= _LOW_CONFIDENCE_THRESHOLD else (230, 160, 40)
        overlay_draw.rectangle((region.x_min, region.y_min, region.x_max, region.y_max), outline=tone, width=3)
        overlay_draw.text((region.x_min + 3, region.y_min + 3), region.region_type, fill=tone)
    overlay_buf = io.BytesIO()
    overlay.save(overlay_buf, format="PNG")

    region_map = rgb.copy()
    region_draw = ImageDraw.Draw(region_map)
    for index, region in enumerate(regions, start=1):
        tone = (20 * index % 255, 90 + 15 * index % 165, 150 + 10 * index % 105)
        region_draw.rectangle((region.x_min, region.y_min, region.x_max, region.y_max), outline=tone, width=2)
    region_buf = io.BytesIO()
    region_map.save(region_buf, format="PNG")

    debug = rgb.copy()
    debug_draw = ImageDraw.Draw(debug)
    x_min = int(boundary_geometry.get("x_min") or 0)
    y_min = int(boundary_geometry.get("y_min") or 0)
    x_max = int(boundary_geometry.get("x_max") or max(0, rgb.width - 1))
    y_max = int(boundary_geometry.get("y_max") or max(0, rgb.height - 1))
    debug_draw.rectangle((x_min, y_min, x_max, y_max), outline=(255, 90, 90), width=4)
    debug_buf = io.BytesIO()
    debug.save(debug_buf, format="PNG")

    return [
        _ArtifactDraft("OCR_OVERLAY", overlay_buf.getvalue(), {"region_count": len(regions)}, ".png"),
        _ArtifactDraft("OCR_REGION_MAP", region_buf.getvalue(), {"region_count": len(regions)}, ".png"),
        _ArtifactDraft("OCR_DEBUG_PREVIEW", debug_buf.getvalue(), {"boundary_geometry": dict(boundary_geometry)}, ".png"),
    ]


def _text_export_artifact(regions: list[_RegionDraft], candidates: list[_CandidateDraft]) -> _ArtifactDraft:
    payload = {
        "regions": [
            {
                "region_type": row.region_type,
                "extracted_text": row.extracted_text,
                "normalized_text": row.normalized_text,
                "confidence_score": row.confidence_score,
            }
            for row in regions
        ],
        "candidates": [
            {
                "candidate_type": row.candidate_type,
                "candidate_value": row.candidate_value,
                "normalized_candidate_value": row.normalized_candidate_value,
                "confidence_score": row.confidence_score,
            }
            for row in candidates
        ],
    }
    body = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _ArtifactDraft("OCR_TEXT_EXPORT", body, {"format": "json"}, ".json")


def _manifest_artifact(manifest: dict[str, Any]) -> _ArtifactDraft:
    body = json.dumps(_json_safe(manifest), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _ArtifactDraft("OCR_MANIFEST", body, {"format": "json"}, ".json")


def _build_issues(
    *,
    regions: list[_RegionDraft],
    candidates: list[_CandidateDraft],
    boundary_run: ScanBoundaryRun,
    ocr_error: str | None = None,
) -> list[_IssueDraft]:
    issues: list[_IssueDraft] = []
    if ocr_error:
        issue_type = "OCR_ENGINE_TIMEOUT" if "timed out" in ocr_error.lower() else "OCR_FAILED"
        issues.append(_IssueDraft(issue_type, "ERROR", ocr_error[:512], {"error": ocr_error[:2000]}))
        return issues

    if not any(row.normalized_text for row in regions):
        issues.append(_IssueDraft("OCR_FAILED", "ERROR", "OCR produced no text output.", {}))

    avg_conf = sum(row.confidence_score for row in regions) / max(1, len(regions))
    if avg_conf < _LOW_CONFIDENCE_THRESHOLD:
        issues.append(
            _IssueDraft(
                "LOW_TEXT_CONFIDENCE",
                "WARNING",
                "Average OCR confidence is below the deterministic threshold.",
                {"average_confidence_score": round(avg_conf, 6), "threshold": _LOW_CONFIDENCE_THRESHOLD},
            )
        )

    title_candidates = [row for row in candidates if row.candidate_type == "TITLE"]
    issue_candidates = [row for row in candidates if row.candidate_type == "ISSUE_NUMBER"]
    if not title_candidates:
        issues.append(_IssueDraft("NO_TITLE_DETECTED", "WARNING", "No title candidate was detected.", {}))
    elif len(title_candidates) > 1:
        issues.append(_IssueDraft("MULTIPLE_TITLE_CANDIDATES", "INFO", "Multiple title candidates were detected.", {"count": len(title_candidates)}))
    if not issue_candidates:
        issues.append(_IssueDraft("NO_ISSUE_NUMBER_DETECTED", "WARNING", "No issue-number candidate was detected.", {}))
    elif len(issue_candidates) > 1:
        issues.append(_IssueDraft("MULTIPLE_ISSUE_CANDIDATES", "INFO", "Multiple issue-number candidates were detected.", {"count": len(issue_candidates)}))

    generic_region = next((row for row in regions if row.region_type == "GENERIC_TEXT"), None)
    if generic_region and generic_region.confidence_score < 0.45:
        issues.append(_IssueDraft("LOW_CONTRAST_TEXT", "WARNING", "Low contrast reduced OCR region confidence.", {"confidence_score": generic_region.confidence_score}))

    if any((row.rotation_angle or 0.0) > 10 or (row.rotation_angle or 0.0) < -10 for row in regions):
        issues.append(_IssueDraft("EXTREME_TEXT_ROTATION", "INFO", "Boundary geometry indicates strong residual text rotation.", {}))

    if any("..." in (row.normalized_text or "") for row in regions):
        issues.append(_IssueDraft("PARTIAL_TEXT_DETECTED", "INFO", "OCR output suggests partial text truncation.", {}))

    boundary_issues = list(boundary_run.output_manifest_json.get("issues") or [])
    if any((issue.get("issue_type") == "LOW_CONTRAST_BACKGROUND") for issue in boundary_issues if isinstance(issue, dict)):
        issues.append(_IssueDraft("LOW_CONTRAST_TEXT", "INFO", "Boundary layer reported low contrast background conditions.", {}))
    return issues


def _build_confidence_summary(regions: list[_RegionDraft], candidates: list[_CandidateDraft]) -> dict[str, Any]:
    average_region_confidence = round(sum(row.confidence_score for row in regions) / max(1, len(regions)), 6)
    average_candidate_confidence = round(sum(row.confidence_score for row in candidates) / max(1, len(candidates)), 6) if candidates else 0.0
    return {
        "average_region_confidence": average_region_confidence,
        "average_candidate_confidence": average_candidate_confidence,
        "region_count": len(regions),
        "candidate_count": len(candidates),
        "low_confidence_region_count": sum(1 for row in regions if row.confidence_score < _LOW_CONFIDENCE_THRESHOLD),
    }


def build_ocr_manifest(
    *,
    original_scan_checksum: str,
    normalization_checksum: str,
    boundary_checksum: str,
    source_checksum: str,
    ocr_engine: str,
    ocr_engine_version: str | None,
    regions: list[_RegionDraft],
    candidates: list[_CandidateDraft],
    issues: list[_IssueDraft],
    confidence_summary: dict[str, Any],
    artifact_checksums: list[dict[str, str]],
) -> tuple[dict[str, Any], str]:
    manifest = {
        "ocr_engine": ocr_engine,
        "ocr_engine_version": ocr_engine_version,
        "ocr_extraction_version": OCR_EXTRACTION_VERSION,
        "original_scan_checksum": original_scan_checksum,
        "normalization_checksum": normalization_checksum,
        "boundary_checksum": boundary_checksum,
        "source_checksum": source_checksum,
        "confidence_summary": confidence_summary,
        "regions": [
            {
                "region_type": row.region_type,
                "extracted_text": row.extracted_text,
                "normalized_text": row.normalized_text,
                "confidence_score": row.confidence_score,
                "box": [row.x_min, row.y_min, row.x_max, row.y_max],
                "rotation_angle": row.rotation_angle,
            }
            for row in regions
        ],
        "candidates": [
            {
                "candidate_type": row.candidate_type,
                "candidate_value": row.candidate_value,
                "normalized_candidate_value": row.normalized_candidate_value,
                "confidence_score": row.confidence_score,
                "source_region_type": row.source_region_type,
            }
            for row in candidates
        ],
        "issues": [
            {
                "issue_type": row.issue_type,
                "severity": row.severity,
                "issue_message": row.issue_message,
                "metadata_json": row.metadata_json,
            }
            for row in sorted(issues, key=lambda row: (row.issue_type, row.severity, row.issue_message))
        ],
        "artifact_checksums": sorted(artifact_checksums, key=lambda row: row["artifact_type"]),
    }
    return manifest, _hash_payload(manifest)


def _history_event_checksum(*, ocr_run_id: int, event_type: str, event_message: str, metadata_json: dict[str, Any]) -> str:
    return _hash_payload(
        {
            "ocr_run_id": ocr_run_id,
            "event_type": event_type,
            "event_message": event_message,
            "metadata_json": metadata_json,
        }
    )


def _artifact_read(row: ScanOcrArtifact, *, preview: str | None = None) -> ScanOcrArtifactRead:
    return ScanOcrArtifactRead.model_validate({**row.model_dump(mode="json"), "preview_data_url": preview})


def _region_read(row: ScanOcrTextRegion) -> ScanOcrTextRegionRead:
    return ScanOcrTextRegionRead.model_validate(row, from_attributes=True)


def _candidate_read(row: ScanOcrCandidate) -> ScanOcrCandidateRead:
    return ScanOcrCandidateRead.model_validate(row, from_attributes=True)


def _issue_read(row: ScanOcrIssue) -> ScanOcrIssueRead:
    return ScanOcrIssueRead.model_validate(row, from_attributes=True)


def _history_read(row: ScanOcrHistory) -> ScanOcrHistoryRead:
    return ScanOcrHistoryRead.model_validate(row, from_attributes=True)


def _run_read(row: ScanOcrRun) -> ScanOcrRunRead:
    return ScanOcrRunRead.model_validate(row, from_attributes=True)


def _load_ocr_artifact_preview(settings: Settings, row: ScanOcrArtifact) -> str | None:
    if not _artifact_previewable(row.artifact_type):
        return None
    try:
        path = _resolve_ocr_storage_path(settings, row.storage_path)
        with Image.open(path) as image:
            return _data_url_for_image(_image_to_rgb(image))
    except (FileNotFoundError, OSError, ValueError, UnidentifiedImageError):
        return None


def _resolve_input_context(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int,
    normalization_run_id: int | None,
    boundary_run_id: int | None,
) -> tuple[ScanImage, ScanNormalizationRun, ScanBoundaryRun, ScanNormalizationArtifact]:
    scan_image = session.get(ScanImage, scan_image_id)
    if scan_image is None or scan_image.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan image not found")

    if normalization_run_id is not None:
        normalization_run = session.get(ScanNormalizationRun, normalization_run_id)
        if normalization_run is None or normalization_run.owner_user_id != owner_user_id or normalization_run.scan_image_id != scan_image_id:
            raise HTTPException(status_code=404, detail="Normalization run not found")
    else:
        normalization_run = session.exec(
            select(ScanNormalizationRun)
            .where(
                ScanNormalizationRun.owner_user_id == owner_user_id,
                ScanNormalizationRun.scan_image_id == scan_image_id,
                ScanNormalizationRun.normalization_status == "COMPLETE",
            )
            .order_by(col(ScanNormalizationRun.created_at).desc(), col(ScanNormalizationRun.id).desc())
        ).first()
        if normalization_run is None:
            raise HTTPException(status_code=422, detail="No completed normalization run exists for this scan image")

    if boundary_run_id is not None:
        boundary_run = session.get(ScanBoundaryRun, boundary_run_id)
        if boundary_run is None or boundary_run.owner_user_id != owner_user_id or boundary_run.scan_image_id != scan_image_id:
            raise HTTPException(status_code=404, detail="Boundary run not found")
    else:
        boundary_run = session.exec(
            select(ScanBoundaryRun)
            .where(
                ScanBoundaryRun.owner_user_id == owner_user_id,
                ScanBoundaryRun.scan_image_id == scan_image_id,
                ScanBoundaryRun.boundary_status == "COMPLETE",
            )
            .order_by(col(ScanBoundaryRun.created_at).desc(), col(ScanBoundaryRun.id).desc())
        ).first()
        if boundary_run is None:
            raise HTTPException(status_code=422, detail="No completed boundary run exists for this scan image")

    if boundary_run.normalization_run_id != normalization_run.id:
        raise HTTPException(status_code=422, detail="Boundary run must align with the selected normalization run")

    source_artifact = session.get(ScanNormalizationArtifact, boundary_run.source_artifact_id)
    if source_artifact is None:
        raise HTTPException(status_code=422, detail="Boundary source artifact not found")

    return scan_image, normalization_run, boundary_run, source_artifact


def _persist_failed_run(
    session: Session,
    *,
    owner_user_id: int,
    scan_image: ScanImage,
    normalization_run: ScanNormalizationRun,
    boundary_run: ScanBoundaryRun,
    source_artifact: ScanNormalizationArtifact,
    input_manifest: dict[str, Any],
    error_message: str,
) -> ScanOcrRun:
    ocr_checksum = _hash_payload({**input_manifest, "error_message": error_message, "status": "FAILED"})
    existing = session.exec(
        select(ScanOcrRun)
        .where(ScanOcrRun.owner_user_id == owner_user_id, ScanOcrRun.ocr_checksum == ocr_checksum)
        .order_by(col(ScanOcrRun.created_at).desc(), col(ScanOcrRun.id).desc())
    ).first()
    if existing is not None:
        return existing

    now = utc_now()
    run = ScanOcrRun(
        owner_user_id=owner_user_id,
        scan_image_id=int(scan_image.id or 0),
        normalization_run_id=int(normalization_run.id or 0),
        boundary_run_id=int(boundary_run.id or 0),
        source_artifact_id=int(source_artifact.id or 0),
        source_checksum=source_artifact.artifact_checksum,
        ocr_checksum=ocr_checksum,
        ocr_status="FAILED",
        ocr_engine=OCR_ENGINE_NAME,
        ocr_engine_version=get_tesseract_engine_version() or OCR_ENGINE_VERSION_FALLBACK,
        input_manifest_json=input_manifest,
        output_manifest_json={"error_message": error_message},
        created_at=now,
        completed_at=now,
    )
    session.add(run)
    session.flush()
    session.add(
        ScanOcrIssue(
            owner_user_id=owner_user_id,
            ocr_run_id=int(run.id or 0),
            issue_type="OCR_FAILED",
            severity="ERROR",
            issue_message=error_message[:512],
            metadata_json={"error_message": error_message[:2000]},
            created_at=now,
        )
    )
    session.add(
        ScanOcrHistory(
            owner_user_id=owner_user_id,
            ocr_run_id=int(run.id or 0),
            event_type="FAILED",
            event_message=error_message[:512],
            event_checksum=_history_event_checksum(
                ocr_run_id=int(run.id or 0),
                event_type="FAILED",
                event_message=error_message[:512],
                metadata_json={"error_message": error_message[:2000]},
            ),
            metadata_json={"error_message": error_message[:2000]},
            created_at=now,
        )
    )
    session.commit()
    session.refresh(run)
    return run


def _build_run_detail(
    session: Session,
    settings: Settings,
    *,
    run: ScanOcrRun,
    scan_image: ScanImage,
) -> ScanOcrRunDetail:
    regions = list(
        session.exec(select(ScanOcrTextRegion).where(ScanOcrTextRegion.ocr_run_id == run.id).order_by(col(ScanOcrTextRegion.region_type).asc(), col(ScanOcrTextRegion.id).asc())).all()
    )
    candidates = list(
        session.exec(select(ScanOcrCandidate).where(ScanOcrCandidate.ocr_run_id == run.id).order_by(col(ScanOcrCandidate.candidate_type).asc(), col(ScanOcrCandidate.id).asc())).all()
    )
    artifacts = list(
        session.exec(select(ScanOcrArtifact).where(ScanOcrArtifact.ocr_run_id == run.id).order_by(col(ScanOcrArtifact.artifact_type).asc(), col(ScanOcrArtifact.id).asc())).all()
    )
    issues = list(
        session.exec(select(ScanOcrIssue).where(ScanOcrIssue.ocr_run_id == run.id).order_by(col(ScanOcrIssue.created_at).asc(), col(ScanOcrIssue.id).asc())).all()
    )
    history = list(
        session.exec(select(ScanOcrHistory).where(ScanOcrHistory.ocr_run_id == run.id).order_by(col(ScanOcrHistory.created_at).asc(), col(ScanOcrHistory.id).asc())).all()
    )

    source_preview = None
    source_artifact = session.get(ScanNormalizationArtifact, run.source_artifact_id)
    if source_artifact is not None:
        try:
            with Image.open(_resolve_normalization_artifact_path(settings, source_artifact)) as image:
                source_preview = _data_url_for_image(_image_to_rgb(image))
        except (FileNotFoundError, OSError, ValueError, UnidentifiedImageError):
            source_preview = None

    overlay_preview = None
    region_map_preview = None
    artifact_reads: list[ScanOcrArtifactRead] = []
    for artifact in artifacts:
        preview = _load_ocr_artifact_preview(settings, artifact)
        if artifact.artifact_type == "OCR_OVERLAY":
            overlay_preview = preview
        if artifact.artifact_type == "OCR_REGION_MAP":
            region_map_preview = preview
        artifact_reads.append(_artifact_read(artifact, preview=preview))

    boundary_run = session.get(ScanBoundaryRun, run.boundary_run_id)
    normalization_run = session.get(ScanNormalizationRun, run.normalization_run_id)
    confidence_summary = dict(run.output_manifest_json.get("confidence_summary") or {})
    return ScanOcrRunDetail(
        **_run_read(run).model_dump(),
        regions=[_region_read(row) for row in regions],
        candidates=[_candidate_read(row) for row in candidates],
        artifacts=artifact_reads,
        issues=[_issue_read(row) for row in issues],
        history=[_history_read(row) for row in history],
        original_scan_checksum=scan_image.sha256_checksum,
        normalization_checksum=normalization_run.normalization_checksum if normalization_run is not None else None,
        boundary_checksum=boundary_run.boundary_checksum if boundary_run is not None else None,
        source_preview_data_url=source_preview,
        ocr_overlay_preview_data_url=overlay_preview,
        ocr_region_map_preview_data_url=region_map_preview,
        confidence_summary=confidence_summary,
    )


def run_scan_ocr(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    payload: ScanOcrRunCreate,
) -> tuple[ScanOcrRunDetail, bool]:
    scan_image, normalization_run, boundary_run, source_artifact = _resolve_input_context(
        session,
        owner_user_id=owner_user_id,
        scan_image_id=payload.scan_image_id,
        normalization_run_id=payload.normalization_run_id,
        boundary_run_id=payload.boundary_run_id,
    )

    input_manifest = {
        "scan_image_id": int(scan_image.id or 0),
        "normalization_run_id": int(normalization_run.id or 0),
        "boundary_run_id": int(boundary_run.id or 0),
        "source_artifact_id": int(source_artifact.id or 0),
        "source_checksum": source_artifact.artifact_checksum,
        "normalization_checksum": normalization_run.normalization_checksum,
        "boundary_checksum": boundary_run.boundary_checksum,
        "ocr_engine": OCR_ENGINE_NAME,
        "ocr_extraction_version": OCR_EXTRACTION_VERSION,
    }

    try:
        with Image.open(_resolve_normalization_artifact_path(settings, source_artifact)) as opened:
            image = _image_to_rgb(opened)
            zones = derive_ocr_zones(
                boundary_geometry=dict(boundary_run.output_manifest_json.get("geometry") or {}),
                image_width=image.width,
                image_height=image.height,
            )
            regions = extract_text_regions(
                settings,
                image=image,
                zones=zones,
                source_checksum=source_artifact.artifact_checksum,
                timeout_seconds=float(settings.cover_ocr_tesseract_timeout_seconds),
            )
            candidates = generate_ocr_candidates(regions)
            issues = _build_issues(regions=regions, candidates=candidates, boundary_run=boundary_run)
            confidence_summary = _build_confidence_summary(regions, candidates)
            image_artifacts = _build_overlay_artifacts(image, regions, dict(boundary_run.output_manifest_json.get("geometry") or {}))
    except ValueError as exc:
        failed = _persist_failed_run(
            session,
            owner_user_id=owner_user_id,
            scan_image=scan_image,
            normalization_run=normalization_run,
            boundary_run=boundary_run,
            source_artifact=source_artifact,
            input_manifest=input_manifest,
            error_message=str(exc),
        )
        return _build_run_detail(session, settings, run=failed, scan_image=scan_image), False

    provisional_manifest, _ = build_ocr_manifest(
        original_scan_checksum=scan_image.sha256_checksum,
        normalization_checksum=normalization_run.normalization_checksum,
        boundary_checksum=boundary_run.boundary_checksum,
        source_checksum=source_artifact.artifact_checksum,
        ocr_engine=OCR_ENGINE_NAME,
        ocr_engine_version=get_tesseract_engine_version() or OCR_ENGINE_VERSION_FALLBACK,
        regions=regions,
        candidates=candidates,
        issues=issues,
        confidence_summary=confidence_summary,
        artifact_checksums=[{"artifact_type": row.artifact_type, "artifact_checksum": _sha256_bytes(row.body)} for row in image_artifacts],
    )
    text_export = _text_export_artifact(regions, candidates)
    provisional_artifacts = image_artifacts + [text_export]
    manifest_artifact = _manifest_artifact(provisional_manifest)
    all_artifacts = provisional_artifacts + [manifest_artifact]
    artifact_checksums = [{"artifact_type": row.artifact_type, "artifact_checksum": _sha256_bytes(row.body)} for row in all_artifacts]
    output_manifest, ocr_checksum = build_ocr_manifest(
        original_scan_checksum=scan_image.sha256_checksum,
        normalization_checksum=normalization_run.normalization_checksum,
        boundary_checksum=boundary_run.boundary_checksum,
        source_checksum=source_artifact.artifact_checksum,
        ocr_engine=OCR_ENGINE_NAME,
        ocr_engine_version=get_tesseract_engine_version() or OCR_ENGINE_VERSION_FALLBACK,
        regions=regions,
        candidates=candidates,
        issues=issues,
        confidence_summary=confidence_summary,
        artifact_checksums=artifact_checksums,
    )
    all_artifacts = provisional_artifacts + [_manifest_artifact(output_manifest)]

    existing = session.exec(
        select(ScanOcrRun).where(ScanOcrRun.owner_user_id == owner_user_id, ScanOcrRun.ocr_checksum == ocr_checksum).order_by(col(ScanOcrRun.created_at).desc(), col(ScanOcrRun.id).desc())
    ).first()
    if existing is not None:
        return _build_run_detail(session, settings, run=existing, scan_image=scan_image), False

    now = utc_now()
    engine_version = get_tesseract_engine_version() or OCR_ENGINE_VERSION_FALLBACK
    run = ScanOcrRun(
        owner_user_id=owner_user_id,
        scan_image_id=int(scan_image.id or 0),
        normalization_run_id=int(normalization_run.id or 0),
        boundary_run_id=int(boundary_run.id or 0),
        source_artifact_id=int(source_artifact.id or 0),
        source_checksum=source_artifact.artifact_checksum,
        ocr_checksum=ocr_checksum,
        ocr_status="COMPLETE",
        ocr_engine=OCR_ENGINE_NAME,
        ocr_engine_version=engine_version,
        input_manifest_json=input_manifest,
        output_manifest_json=output_manifest,
        created_at=now,
        completed_at=now,
    )
    session.add(run)
    session.flush()

    region_id_by_type: dict[str, int] = {}
    for region in regions:
        row = ScanOcrTextRegion(
            owner_user_id=owner_user_id,
            ocr_run_id=int(run.id or 0),
            region_type=region.region_type,
            extracted_text=region.extracted_text,
            normalized_text=region.normalized_text,
            confidence_score=region.confidence_score,
            x_min=region.x_min,
            y_min=region.y_min,
            x_max=region.x_max,
            y_max=region.y_max,
            width_px=region.width_px,
            height_px=region.height_px,
            rotation_angle=region.rotation_angle,
            metadata_json=region.metadata_json,
            created_at=now,
        )
        session.add(row)
        session.flush()
        if row.id is not None:
            region_id_by_type[region.region_type] = int(row.id)

    for candidate in candidates:
        session.add(
            ScanOcrCandidate(
                owner_user_id=owner_user_id,
                ocr_run_id=int(run.id or 0),
                candidate_type=candidate.candidate_type,
                candidate_value=candidate.candidate_value,
                normalized_candidate_value=candidate.normalized_candidate_value,
                confidence_score=candidate.confidence_score,
                source_region_id=region_id_by_type.get(candidate.source_region_type),
                metadata_json=candidate.metadata_json,
                created_at=now,
            )
        )

    for artifact in all_artifacts:
        rel_path = _artifact_storage_path(
            owner_user_id=owner_user_id,
            scan_image_id=int(scan_image.id or 0),
            ocr_run_id=int(run.id or 0),
            artifact_type=artifact.artifact_type,
            ext=artifact.ext,
        )
        target = _resolve_ocr_storage_path(settings, rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(artifact.body)
        session.add(
            ScanOcrArtifact(
                owner_user_id=owner_user_id,
                ocr_run_id=int(run.id or 0),
                artifact_type=artifact.artifact_type,
                storage_backend="filesystem",
                storage_path=rel_path,
                artifact_checksum=_sha256_bytes(artifact.body),
                metadata_json=artifact.metadata_json,
                created_at=now,
            )
        )

    for issue in issues:
        session.add(
            ScanOcrIssue(
                owner_user_id=owner_user_id,
                ocr_run_id=int(run.id or 0),
                issue_type=issue.issue_type,
                severity=issue.severity,
                issue_message=issue.issue_message,
                metadata_json=issue.metadata_json,
                created_at=now,
            )
        )

    history_rows = [
        _HistoryDraft("RUN_STARTED", "OCR intelligence run started.", input_manifest),
        _HistoryDraft("REGIONS_EXTRACTED", "OCR text regions extracted.", {"region_count": len(regions)}),
        _HistoryDraft("CANDIDATES_GENERATED", "OCR candidates generated.", {"candidate_count": len(candidates)}),
        _HistoryDraft("RUN_COMPLETED", "OCR intelligence run completed.", {"ocr_checksum": ocr_checksum}),
    ]
    for hist in history_rows:
        session.add(
            ScanOcrHistory(
                owner_user_id=owner_user_id,
                ocr_run_id=int(run.id or 0),
                event_type=hist.event_type,
                event_message=hist.event_message,
                event_checksum=_history_event_checksum(
                    ocr_run_id=int(run.id or 0),
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


def _get_owner_run_or_404(session: Session, *, owner_user_id: int, run_id: int) -> ScanOcrRun:
    row = session.get(ScanOcrRun, run_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan OCR run not found")
    return row


def get_scan_ocr_run_owner(session: Session, settings: Settings, *, owner_user_id: int, run_id: int) -> ScanOcrRunDetail:
    run = _get_owner_run_or_404(session, owner_user_id=owner_user_id, run_id=run_id)
    scan_image = session.get(ScanImage, run.scan_image_id)
    if scan_image is None:
        raise HTTPException(status_code=404, detail="Scan image not found")
    return _build_run_detail(session, settings, run=run, scan_image=scan_image)


def get_scan_ocr_artifact_owner(session: Session, settings: Settings, *, owner_user_id: int, artifact_id: int) -> ScanOcrArtifactRead:
    row = session.get(ScanOcrArtifact, artifact_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan OCR artifact not found")
    return _artifact_read(row, preview=_load_ocr_artifact_preview(settings, row))


def list_scan_ocr_runs_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanOcrRunListResponse:
    limit, offset = clamp_scan_ocr_pagination(limit=limit, offset=offset)
    stmt = select(ScanOcrRun).where(ScanOcrRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanOcrRun.scan_image_id == scan_image_id)
    stmt = stmt.order_by(col(ScanOcrRun.created_at).desc(), col(ScanOcrRun.id).desc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanOcrRun).where(ScanOcrRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        total_stmt = total_stmt.where(ScanOcrRun.scan_image_id == scan_image_id)
    total = session.exec(total_stmt).one()
    counts = session.exec(select(ScanOcrRun.ocr_status, func.count()).where(ScanOcrRun.owner_user_id == owner_user_id).group_by(ScanOcrRun.ocr_status)).all()
    low_confidence_count = sum(1 for row in rows if float((row.output_manifest_json.get("confidence_summary") or {}).get("average_region_confidence") or 1.0) < _LOW_CONFIDENCE_THRESHOLD)
    unresolved = session.exec(select(func.count()).select_from(ScanOcrIssue).where(ScanOcrIssue.owner_user_id == owner_user_id, ScanOcrIssue.severity.in_(("WARNING", "ERROR")))).one()
    return ScanOcrRunListResponse(
        items=[_run_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
        status_counts={str(k): int(v) for k, v in counts},
        low_confidence_count=low_confidence_count,
        unresolved_issue_count=int(unresolved or 0),
    )


def list_scan_ocr_runs_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    scan_image_id: int | None,
    limit: int,
    offset: int,
) -> ScanOcrRunListResponse:
    limit, offset = clamp_scan_ocr_pagination(limit=limit, offset=offset)
    stmt = select(ScanOcrRun)
    if owner_user_id is not None:
        stmt = stmt.where(ScanOcrRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanOcrRun.scan_image_id == scan_image_id)
    stmt = stmt.order_by(col(ScanOcrRun.created_at).desc(), col(ScanOcrRun.id).desc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanOcrRun)
    if owner_user_id is not None:
        total_stmt = total_stmt.where(ScanOcrRun.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        total_stmt = total_stmt.where(ScanOcrRun.scan_image_id == scan_image_id)
    total = session.exec(total_stmt).one()
    counts_stmt = select(ScanOcrRun.ocr_status, func.count()).group_by(ScanOcrRun.ocr_status)
    if owner_user_id is not None:
        counts_stmt = counts_stmt.where(ScanOcrRun.owner_user_id == owner_user_id)
    counts = session.exec(counts_stmt).all()
    unresolved_stmt = select(func.count()).select_from(ScanOcrIssue).where(ScanOcrIssue.severity.in_(("WARNING", "ERROR")))
    if owner_user_id is not None:
        unresolved_stmt = unresolved_stmt.where(ScanOcrIssue.owner_user_id == owner_user_id)
    unresolved = session.exec(unresolved_stmt).one()
    low_confidence_count = sum(1 for row in rows if float((row.output_manifest_json.get("confidence_summary") or {}).get("average_region_confidence") or 1.0) < _LOW_CONFIDENCE_THRESHOLD)
    return ScanOcrRunListResponse(
        items=[_run_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
        status_counts={str(k): int(v) for k, v in counts},
        low_confidence_count=low_confidence_count,
        unresolved_issue_count=int(unresolved or 0),
    )


def list_scan_ocr_candidates_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_image_id: int | None,
    ocr_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanOcrCandidateListResponse:
    limit, offset = clamp_scan_ocr_pagination(limit=limit, offset=offset)
    stmt = select(ScanOcrCandidate).join(ScanOcrRun, ScanOcrRun.id == ScanOcrCandidate.ocr_run_id).where(ScanOcrCandidate.owner_user_id == owner_user_id)
    if scan_image_id is not None:
        stmt = stmt.where(ScanOcrRun.scan_image_id == scan_image_id)
    if ocr_run_id is not None:
        stmt = stmt.where(ScanOcrCandidate.ocr_run_id == ocr_run_id)
    stmt = stmt.order_by(col(ScanOcrCandidate.candidate_type).asc(), col(ScanOcrCandidate.confidence_score).desc(), col(ScanOcrCandidate.id).asc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanOcrCandidate).where(ScanOcrCandidate.owner_user_id == owner_user_id)
    total = session.exec(total_stmt).one()
    counts = session.exec(select(ScanOcrCandidate.candidate_type, func.count()).where(ScanOcrCandidate.owner_user_id == owner_user_id).group_by(ScanOcrCandidate.candidate_type)).all()
    return ScanOcrCandidateListResponse(
        items=[_candidate_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
        candidate_type_counts={str(k): int(v) for k, v in counts},
    )


def list_scan_ocr_issues_owner(
    session: Session,
    *,
    owner_user_id: int,
    ocr_run_id: int | None,
    limit: int,
    offset: int,
) -> ScanOcrIssueListResponse:
    limit, offset = clamp_scan_ocr_pagination(limit=limit, offset=offset)
    stmt = select(ScanOcrIssue).join(ScanOcrRun, ScanOcrRun.id == ScanOcrIssue.ocr_run_id).where(ScanOcrIssue.owner_user_id == owner_user_id)
    if ocr_run_id is not None:
        stmt = stmt.where(ScanOcrIssue.ocr_run_id == ocr_run_id)
    stmt = stmt.order_by(col(ScanOcrIssue.created_at).desc(), col(ScanOcrIssue.id).desc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanOcrIssue).where(ScanOcrIssue.owner_user_id == owner_user_id)
    if ocr_run_id is not None:
        total_stmt = total_stmt.where(ScanOcrIssue.ocr_run_id == ocr_run_id)
    total = session.exec(total_stmt).one()
    counts = session.exec(select(ScanOcrIssue.issue_type, func.count()).where(ScanOcrIssue.owner_user_id == owner_user_id).group_by(ScanOcrIssue.issue_type)).all()
    return ScanOcrIssueListResponse(
        items=[_issue_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
        issue_type_counts={str(k): int(v) for k, v in counts},
    )


def list_scan_ocr_issues_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanOcrIssueListResponse:
    limit, offset = clamp_scan_ocr_pagination(limit=limit, offset=offset)
    stmt = select(ScanOcrIssue)
    if owner_user_id is not None:
        stmt = stmt.where(ScanOcrIssue.owner_user_id == owner_user_id)
    stmt = stmt.order_by(col(ScanOcrIssue.created_at).desc(), col(ScanOcrIssue.id).desc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanOcrIssue)
    if owner_user_id is not None:
        total_stmt = total_stmt.where(ScanOcrIssue.owner_user_id == owner_user_id)
    total = session.exec(total_stmt).one()
    counts_stmt = select(ScanOcrIssue.issue_type, func.count()).group_by(ScanOcrIssue.issue_type)
    if owner_user_id is not None:
        counts_stmt = counts_stmt.where(ScanOcrIssue.owner_user_id == owner_user_id)
    counts = session.exec(counts_stmt).all()
    return ScanOcrIssueListResponse(
        items=[_issue_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
        issue_type_counts={str(k): int(v) for k, v in counts},
    )


def list_scan_ocr_failures_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> ScanOcrFailureListResponse:
    limit, offset = clamp_scan_ocr_pagination(limit=limit, offset=offset)
    stmt = select(ScanOcrRun).where(ScanOcrRun.ocr_status == "FAILED")
    if owner_user_id is not None:
        stmt = stmt.where(ScanOcrRun.owner_user_id == owner_user_id)
    stmt = stmt.order_by(col(ScanOcrRun.created_at).desc(), col(ScanOcrRun.id).desc())
    rows = list(session.exec(stmt.offset(offset).limit(limit)).all())
    total_stmt = select(func.count()).select_from(ScanOcrRun).where(ScanOcrRun.ocr_status == "FAILED")
    if owner_user_id is not None:
        total_stmt = total_stmt.where(ScanOcrRun.owner_user_id == owner_user_id)
    total = session.exec(total_stmt).one()
    return ScanOcrFailureListResponse(
        items=[_run_read(row) for row in rows],
        total_items=int(total or 0),
        limit=limit,
        offset=offset,
    )
