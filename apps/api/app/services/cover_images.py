"""Persist and serve comic cover images (deterministic hashing, filesystem storage)."""

from __future__ import annotations

import hashlib
import io
import math
import re
import subprocess
from subprocess import TimeoutExpired
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Literal

from collections import defaultdict

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError, features
from sqlalchemy import and_, case, func, or_
from sqlmodel import Session, select

from app.core.config import Settings, get_settings
from app.models import (
    ComicIssue,
    ComicTitle,
    CoverImage,
    CoverImageBarcodeCandidate,
    CoverImageDerivative,
    CoverImageFingerprint,
    CoverImageLinkDecision,
    CoverImageMatchCandidate,
    CoverImageOcrCandidate,
    CoverImageOcrQualityAnalysis,
    CoverImageOcrReconciliationWarning,
    CoverImageOcrRegion,
    CoverImageOcrResult,
    DraftImport,
    InventoryCopy,
    Publisher,
    User,
    Variant,
)
from app.schemas.cover_link_decisions import CoverImageLinkDecisionRead
from app.schemas.ai import ParseOrderResponse
from app.schemas.cover_images import (
    CoverImageBarcodeCandidateExtractResponse,
    CoverImageBarcodeCandidateRead,
    CoverImageBarcodeCandidateReviewCounts,
    CoverImageFingerprintGenerateResponse,
    CoverImageFingerprintRead,
    CoverImageMatchCandidateGenerateResponse,
    CoverImageMatchGroupRead,
    CoverImageMatchCandidateRead,
    CoverImageOcrQualityAnalysisRead,
    CoverImageOcrQualityAnalysisResponse,
    CoverImageOcrSnapshotRead,
    CoverImageOcrRegionRead,
    CoverImageOcrRegionExtractResponse,
    CoverImageOcrCandidateRead,
    CoverImageOcrCandidateExtractResponse,
    CoverImageOcrCandidateReviewCounts,
    CoverImageOcrReconciliationResponse,
    CoverImageOcrReconciliationWarningCounts,
    CoverImageOcrReconciliationWarningRead,
    CoverImageOcrVisibility,
    CoverImageRead,
    CoverImageDerivativeRead,
    CoverImageOcrResultRead,
    StructuredProcessingErrorRead,
    OpsCoverDuplicateGroup,
    OpsCoverDuplicateMember,
    OpsCoverImageRecentRow,
)
from app.services.metadata_audits import record_metadata_audit
from app.services.cover_link_decisions import (
    active_cover_link_decisions_for_pairs,
    cover_link_decision_entity_to_read,
    cover_link_pair_key,
)
from app.services.ocr_pipeline_runtime import PipelineStepTimeout, run_with_thread_deadline, validate_pipeline_image_bytes
from app.services.ops_access import is_ops_admin_user
from app.services.processing_errors import (
    classify_exception,
    dumps_structured_error,
    structured_error_to_persistent,
    try_parse_structured_error,
    public_safe_message,
)
from app.tasks.queue import cover_image_ocr_job_ui_status

PIL_FORMAT_TO_MIME = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "GIF": "image/gif",
    "WEBP": "image/webp",
}

MIME_TO_SUFFIX = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}

DERIVATIVE_LONGEST_SIDE = {
    "thumb": 240,
    "medium": 900,
}

OCR_ENGINE_NAME = "tesseract"


def _resolve_ocr_engine_cmd() -> str:
    """Resolve the Tesseract executable, honoring the TESSERACT_CMD setting.

    Falls back to the bare ``tesseract`` name (resolved via PATH) when the
    setting is empty. This lets hosts without tesseract on PATH still run OCR
    by pointing TESSERACT_CMD at the installed binary.
    """
    try:
        configured = (get_settings().tesseract_cmd or "").strip()
    except Exception:  # noqa: BLE001 - settings must never block OCR resolution
        configured = ""
    return configured or OCR_ENGINE_NAME
OCR_SOURCE_PROCESSING_VERSION = "cover-image-processing-v1"
OCR_NORMALIZATION_VERSION = "cover-image-ocr-normalization-v1"
OCR_REPLAY_REASON_MAX_CHARS = 500
OCR_REGION_EXTRACTION_VERSION = "cover-image-ocr-region-extraction-v1"
OCR_CANDIDATE_EXTRACTION_VERSION = "cover-image-ocr-candidate-extraction-v1"
OCR_CANDIDATE_REVIEW_NOTES_MAX_CHARS = 4000
BARCODE_CANDIDATE_EXTRACTION_VERSION = "cover-image-barcode-candidate-extraction-v1"
FINGERPRINT_EXTRACTION_VERSION = "cover-image-fingerprint-extraction-v1"
MATCH_CANDIDATE_EXTRACTION_VERSION = "cover-image-match-candidate-extraction-v1"
MATCH_CANDIDATE_CONFIDENCE_VERSION = "cover-match-confidence-v1"
MATCH_CANDIDATE_RANKING_VERSION = "cover-match-ranking-v1"
# Fingerprint tiers for deterministic review clustering (aligned with ranking bonuses in this module).
MATCH_GROUP_FP_NEAR_IDENTICAL_PHASH = 0.985
MATCH_GROUP_FP_NEAR_IDENTICAL_AVG = 0.985
MATCH_GROUP_FP_STRONG_PHASH = 0.94
MATCH_GROUP_FP_STRONG_MAX = 0.94
MATCH_GROUP_FP_MODERATE_PHASH = 0.88
MATCH_GROUP_FP_MODERATE_MAX = 0.88
MATCH_GROUP_FP_DIVERGENT_UPPER = 0.86
OCR_QUALITY_ANALYSIS_EXTRACTION_VERSION = "cover-image-ocr-quality-analysis-v1"
OCR_RECONCILIATION_LOW_CONFIDENCE_THRESHOLD = 0.65
OCR_REGION_TYPES: tuple[str, ...] = (
    "full_cover",
    "title_region",
    "issue_region",
    "publisher_region",
    "barcode_region",
    "lower_text_region",
)
KNOWN_PUBLISHERS: tuple[str, ...] = (
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
OCR_QUALITY_INFO_THRESHOLD = 0.8
OCR_QUALITY_WARNING_THRESHOLD = 0.5
OCR_QUALITY_MIN_WIDTH = 700
OCR_QUALITY_MIN_HEIGHT = 1000
OCR_QUALITY_BLUR_INFO_THRESHOLD = 120.0
OCR_QUALITY_BLUR_WARNING_THRESHOLD = 40.0
OCR_QUALITY_CONTRAST_INFO_THRESHOLD = 55.0
OCR_QUALITY_CONTRAST_WARNING_THRESHOLD = 28.0
OCR_QUALITY_CROP_BORDER_FRACTION = 0.1


def sha256_raw_bytes(content: bytes) -> str:
    """SHA-256 of raw file bytes."""
    return hashlib.sha256(content).hexdigest()


def decode_cover_image_upload_bytes_optional(
    content: bytes, declared_content_type: str | None
) -> tuple[int, int, str] | None:
    """Return ``(width, height, mime)`` for supported uploads, otherwise ``None`` (corrupt/blocked types).

    Mirrors :func:`extract_image_dimensions_and_mime` without raising — safe for deterministic batch ingestion.
    """
    declared = (declared_content_type or "").split(";")[0].strip().lower() or None
    if declared and declared not in MIME_TO_SUFFIX:
        declared = None

    inferred_from_pil: str | None = None
    width: int | None = None
    height: int | None = None
    try:
        with Image.open(io.BytesIO(content)) as img:
            width, height = int(img.width), int(img.height)
            normalized_fmt = (img.format or "").upper()
            inferred_from_pil = PIL_FORMAT_TO_MIME.get(normalized_fmt)
    except (UnidentifiedImageError, OSError, ValueError):
        return None

    mime = inferred_from_pil or declared
    if mime is None or mime not in MIME_TO_SUFFIX:
        return None
    if width is None or height is None or width < 1 or height < 1:
        return None
    return width, height, mime


def ensure_content_addressable_cover_blob(settings: Settings, mime_type: str, sha256_hex: str, body: bytes) -> str:
    """Persists deterministic storage if missing; skips rewrite when blob already stored.

    Uses the same content-addressable layout as cover uploads (sha256 keyed).
    """
    storage_rel = deterministic_relative_storage_path(mime_type, sha256_hex)
    abs_path = resolve_filesystem_path(settings, storage_rel.replace("\\", "/"))
    if not abs_path.is_file():
        atomic_write_bytes(abs_path, body)
    return storage_rel.replace("\\", "/")


def persist_cover_bytes_for_inventory_copy(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    inventory_copy_id: int,
    body: bytes,
    mime_type: str,
    sha256_hex: str,
    image_width: int,
    image_height: int,
    original_filename: str | None,
    source_type: str = "upload",
) -> CoverImage:
    """Create (or reuse) a cover-image row wired to inventory; writes blob when needed (no OCR auto-enqueue).

    Mirrors :func:`persist_cover_upload` linkage rules without requiring an upload handle.
    """
    row = session.exec(
        select(InventoryCopy).where(
            InventoryCopy.id == inventory_copy_id,
            InventoryCopy.user_id == owner_user_id,
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Inventory copy not found")

    reused = session.exec(
        select(CoverImage).where(
            CoverImage.inventory_copy_id == inventory_copy_id,
            CoverImage.sha256_hash == sha256_hex,
        )
    ).first()
    if reused is not None:
        return reused

    storage_rel = ensure_content_addressable_cover_blob(settings, mime_type, sha256_hex, body)
    entity = CoverImage(
        inventory_copy_id=inventory_copy_id,
        draft_import_id=None,
        canonical_series_id=None,
        source_type=source_type,
        original_filename=(original_filename or "").strip()[:510] or None,
        storage_path=storage_rel,
        mime_type=mime_type,
        image_width=image_width,
        image_height=image_height,
        file_size=len(body),
        sha256_hash=sha256_hex,
        processing_status="pending",
        processing_error=None,
        processed_at=None,
        metadata_refreshed_at=None,
        matching_status="not_ready",
        matching_notes=None,
        ready_for_matching_at=None,
    )
    session.add(entity)
    session.commit()
    session.refresh(entity)
    return entity


def extract_image_dimensions_and_mime(
    content: bytes, declared_content_type: str | None
) -> tuple[int | None, int | None, str]:
    """Infer mime from Pillow; width/height may be missing after decode failures."""
    declared = (declared_content_type or "").split(";")[0].strip().lower() or None
    if declared and declared not in MIME_TO_SUFFIX:
        declared = None

    inferred_from_pil: str | None = None
    width: int | None = None
    height: int | None = None
    try:
        with Image.open(io.BytesIO(content)) as img:
            width, height = int(img.width), int(img.height)
            normalized_fmt = (img.format or "").upper()
            inferred_from_pil = PIL_FORMAT_TO_MIME.get(normalized_fmt)
    except (UnidentifiedImageError, OSError, ValueError):
        pass

    mime = inferred_from_pil or declared
    if mime is None or mime not in MIME_TO_SUFFIX:
        raise HTTPException(
            status_code=415,
            detail="Unsupported or unreadable image. Allowed types: jpeg, png, webp, gif.",
        )

    return width, height, mime


def deterministic_relative_storage_path(mime_type: str, sha256_hex: str) -> str:
    """Content-addressable relative path: ``{aa}/{fullhash}.{ext}``."""
    suffix = MIME_TO_SUFFIX[mime_type]
    return f"{sha256_hex[:2]}/{sha256_hex}.{suffix}"


def resolve_filesystem_path(settings: Settings, storage_path_relative: str) -> Path:
    """Resolve a DB storage path safely under the configured root."""
    base = settings.cover_images_storage_root.resolve()
    target = (base / storage_path_relative).resolve()
    if not target.is_relative_to(base):
        raise HTTPException(status_code=500, detail="Invalid storage path.")
    return target


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".partial")
    try:
        tmp_path.write_bytes(content)
        tmp_path.replace(path)
    except OSError:
        tmp_path.unlink(missing_ok=True)
        raise


def cover_fetch_path(cover_image_id: int) -> str:
    return f"/files/cover-images/{cover_image_id}"


def cover_derivative_fetch_path(cover_image_id: int, derivative_type: str) -> str:
    return f"/files/cover-images/{cover_image_id}/derivatives/{derivative_type}"


def cover_ocr_region_fetch_path(cover_image_id: int, region_type: str) -> str:
    return f"/files/cover-images/{cover_image_id}/ocr-regions/{region_type}"


def _derivative_output_spec() -> tuple[str, str, str, dict[str, object]]:
    if features.check("webp"):
        return ("WEBP", "image/webp", "webp", {"lossless": True, "method": 6})
    return ("PNG", "image/png", "png", {"compress_level": 9})


def deterministic_derivative_storage_path(
    cover_image_id: int,
    derivative_type: str,
    extension: str,
) -> str:
    return f"derivatives/{cover_image_id}/{derivative_type}.{extension}"


def deterministic_ocr_region_storage_path(
    cover_image_id: int,
    region_type: str,
    extension: str,
) -> str:
    return f"ocr_regions/{cover_image_id}/{region_type}.{extension}"


def _read_cover_source_bytes_verified(settings: Settings, cover: CoverImage) -> bytes:
    abs_path = resolve_filesystem_path(settings, cover.storage_path)
    if not abs_path.is_file():
        raise ValueError("Cover image file missing on disk")
    body = abs_path.read_bytes()
    computed_sha = sha256_raw_bytes(body)
    if computed_sha != cover.sha256_hash:
        raise ValueError("Stored cover image SHA-256 does not match file contents")
    return body


def _prepare_derivative_image(img: Image.Image, *, derivative_type: str, output_format: str) -> Image.Image:
    max_side = DERIVATIVE_LONGEST_SIDE[derivative_type]
    derived = img.copy()
    derived.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    if output_format == "PNG":
        if derived.mode == "P":
            derived = derived.convert("RGBA" if "transparency" in img.info else "RGB")
        return derived
    if derived.mode not in {"RGB", "RGBA", "L"}:
        return derived.convert("RGBA" if "transparency" in img.info else "RGB")
    return derived


def render_cover_derivative_bytes(
    original_body: bytes,
    *,
    derivative_type: Literal["thumb", "medium"],
) -> tuple[bytes, int, int, str]:
    output_format, mime_type, _, save_kwargs = _derivative_output_spec()
    with Image.open(io.BytesIO(original_body)) as img:
        derived = _prepare_derivative_image(
            img,
            derivative_type=derivative_type,
            output_format=output_format,
        )
        if output_format == "WEBP" and derived.mode == "P":
            derived = derived.convert("RGBA" if "transparency" in img.info else "RGB")
        buffer = io.BytesIO()
        derived.save(buffer, format=output_format, **save_kwargs)
        payload = buffer.getvalue()
        return payload, int(derived.width), int(derived.height), mime_type


def cover_derivative_entity_to_read(row: CoverImageDerivative) -> CoverImageDerivativeRead:
    if row.id is None:
        raise ValueError("cover image derivative must be flushed before serialization")
    return CoverImageDerivativeRead(
        id=row.id,
        derivative_type=row.derivative_type,  # type: ignore[arg-type]
        mime_type=row.mime_type,
        image_width=row.image_width,
        image_height=row.image_height,
        file_size=row.file_size,
        sha256_hash=row.sha256_hash,
        generated_at=row.generated_at,
        created_at=row.created_at,
        fetch_path=cover_derivative_fetch_path(row.cover_image_id, row.derivative_type),
    )


def cover_ocr_region_entity_to_read(row: CoverImageOcrRegion) -> CoverImageOcrRegionRead:
    if row.id is None:
        raise ValueError("cover image OCR region must be flushed before serialization")
    return CoverImageOcrRegionRead(
        id=row.id,
        cover_image_id=row.cover_image_id,
        derivative_id=row.derivative_id,
        region_type=row.region_type,  # type: ignore[arg-type]
        storage_path=row.storage_path,
        mime_type=row.mime_type,
        image_width=row.image_width,
        image_height=row.image_height,
        file_size=row.file_size,
        sha256_hash=row.sha256_hash,
        extraction_version=row.extraction_version,
        created_at=row.created_at,
        fetch_path=cover_ocr_region_fetch_path(row.cover_image_id, row.region_type),
    )


def cover_ocr_candidate_entity_to_read(row: CoverImageOcrCandidate) -> CoverImageOcrCandidateRead:
    if row.id is None:
        raise ValueError("cover image OCR candidate must be flushed before serialization")
    return CoverImageOcrCandidateRead(
        id=row.id,
        cover_image_id=row.cover_image_id,
        ocr_result_id=row.ocr_result_id,
        candidate_type=row.candidate_type,  # type: ignore[arg-type]
        raw_candidate_text=row.raw_candidate_text,
        normalized_candidate_text=row.normalized_candidate_text,
        confidence_score=row.confidence_score,
        extraction_source=row.extraction_source,  # type: ignore[arg-type]
        extraction_version=row.extraction_version,
        created_at=row.created_at,
        review_status=row.review_status,  # type: ignore[arg-type]
        reviewed_at=row.reviewed_at,
        reviewed_by_user_id=row.reviewed_by_user_id,
        review_notes=row.review_notes,
    )


def cover_barcode_candidate_entity_to_read(
    row: CoverImageBarcodeCandidate,
) -> CoverImageBarcodeCandidateRead:
    if row.id is None:
        raise ValueError("cover image barcode candidate must be flushed before serialization")
    return CoverImageBarcodeCandidateRead(
        id=row.id,
        cover_image_id=row.cover_image_id,
        source_ocr_result_id=row.source_ocr_result_id,
        source_ocr_candidate_id=row.source_ocr_candidate_id,
        raw_barcode_value=row.raw_barcode_value,
        normalized_upc_value=row.normalized_upc_value,
        barcode_type=row.barcode_type,  # type: ignore[arg-type]
        confidence=row.confidence,
        extraction_version=row.extraction_version,
        review_state=row.review_state,  # type: ignore[arg-type]
        reviewed_at=row.reviewed_at,
        reviewed_by_user_id=row.reviewed_by_user_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def cover_fingerprint_entity_to_read(row: CoverImageFingerprint) -> CoverImageFingerprintRead:
    if row.id is None:
        raise ValueError("cover image fingerprint must be flushed before serialization")
    return CoverImageFingerprintRead(
        id=row.id,
        cover_image_id=row.cover_image_id,
        fingerprint_type=row.fingerprint_type,  # type: ignore[arg-type]
        fingerprint_value=row.fingerprint_value,
        derivative_type=row.derivative_type,  # type: ignore[arg-type]
        image_width=row.image_width,
        image_height=row.image_height,
        image_sha256=row.image_sha256,
        extraction_version=row.extraction_version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def cover_ocr_quality_analysis_entity_to_read(
    row: CoverImageOcrQualityAnalysis,
) -> CoverImageOcrQualityAnalysisRead:
    if row.id is None:
        raise ValueError("cover image OCR quality analysis must be flushed before serialization")
    return CoverImageOcrQualityAnalysisRead(
        id=row.id,
        cover_image_id=row.cover_image_id,
        source_ocr_result_id=row.source_ocr_result_id,
        quality_type=row.quality_type,  # type: ignore[arg-type]
        deterministic_score=row.deterministic_score,
        severity=row.severity,  # type: ignore[arg-type]
        detail_json=row.detail_json or {},
        extraction_version=row.extraction_version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def cover_match_candidate_entity_to_read(
    row: CoverImageMatchCandidate,
    *,
    active_link_decision: CoverImageLinkDecisionRead | None = None,
) -> CoverImageMatchCandidateRead:
    if row.id is None:
        raise ValueError("cover image match candidate must be flushed before serialization")
    breakdown = row.scoring_breakdown_json or {}
    return CoverImageMatchCandidateRead(
        id=row.id,
        source_cover_image_id=row.source_cover_image_id,
        candidate_cover_image_id=row.candidate_cover_image_id,
        candidate_type=row.candidate_type,  # type: ignore[arg-type]
        confidence_bucket=row.confidence_bucket,  # type: ignore[arg-type]
        deterministic_score=row.deterministic_score,
        normalized_confidence_score=row.normalized_confidence_score,
        confidence_version=row.confidence_version,
        scoring_breakdown_json=breakdown,
        matched_signal_count=row.matched_signal_count,
        hard_match_flags_json=row.hard_match_flags_json or {},
        weak_signal_flags_json=row.weak_signal_flags_json or {},
        ranking_score=row.ranking_score,
        ranking_version=row.ranking_version,
        ranking_reason_json=row.ranking_reason_json or {},
        candidate_rank=row.candidate_rank,
        grouping_key=row.grouping_key,
        grouping_type=row.grouping_type,  # type: ignore[arg-type]
        grouping_confidence_bucket=row.grouping_confidence_bucket,  # type: ignore[arg-type]
        grouping_reason_summary=row.grouping_reason_summary,
        matched_signals=row.matched_signals or {},
        contributing_signals=list(breakdown.get("contributing_signals") or []),
        penalties=list(breakdown.get("penalties") or []),
        matched_fields=[str(v) for v in (breakdown.get("matched_fields") or [])],
        failed_fields=[str(v) for v in (breakdown.get("failed_fields") or [])],
        confidence_explanation_summary=(
            str(breakdown.get("confidence_explanation_summary"))
            if breakdown.get("confidence_explanation_summary") is not None
            else None
        ),
        extraction_version=row.extraction_version,
        created_at=row.created_at,
        updated_at=row.updated_at,
        dismissed_at=row.dismissed_at,
        acknowledged_at=row.acknowledged_at,
        active_link_decision=active_link_decision,
    )


def cover_ocr_reconciliation_warning_entity_to_read(
    row: CoverImageOcrReconciliationWarning,
) -> CoverImageOcrReconciliationWarningRead:
    if row.id is None:
        raise ValueError("cover image OCR reconciliation warning must be flushed before serialization")
    return CoverImageOcrReconciliationWarningRead(
        id=row.id,
        cover_image_id=row.cover_image_id,
        inventory_copy_id=row.inventory_copy_id,
        ocr_candidate_id=row.ocr_candidate_id,
        warning_type=row.warning_type,  # type: ignore[arg-type]
        severity=row.severity,  # type: ignore[arg-type]
        current_metadata_value=row.current_metadata_value,
        candidate_value=row.candidate_value,
        message=row.message,
        status=row.status,  # type: ignore[arg-type]
        created_at=row.created_at,
        resolved_at=row.resolved_at,
        resolved_by_user_id=row.resolved_by_user_id,
    )


def _derivative_reads_by_cover_id(
    session: Session,
    cover_image_ids: list[int],
) -> dict[int, list[CoverImageDerivativeRead]]:
    if not cover_image_ids:
        return {}
    rows = session.exec(
        select(CoverImageDerivative)
        .where(CoverImageDerivative.cover_image_id.in_(cover_image_ids))
        .order_by(CoverImageDerivative.created_at.asc(), CoverImageDerivative.id.asc())
    ).all()
    out: dict[int, list[CoverImageDerivativeRead]] = {cover_id: [] for cover_id in cover_image_ids}
    for row in rows:
        out.setdefault(row.cover_image_id, []).append(cover_derivative_entity_to_read(row))
    return out


def _ocr_region_reads_by_cover_id(
    session: Session,
    cover_image_ids: list[int],
) -> dict[int, list[CoverImageOcrRegionRead]]:
    if not cover_image_ids:
        return {}
    rows = session.exec(
        select(CoverImageOcrRegion)
        .where(CoverImageOcrRegion.cover_image_id.in_(cover_image_ids))
        .order_by(CoverImageOcrRegion.region_type.asc(), CoverImageOcrRegion.id.asc())
    ).all()
    out: dict[int, list[CoverImageOcrRegionRead]] = {cover_id: [] for cover_id in cover_image_ids}
    for row in rows:
        out.setdefault(row.cover_image_id, []).append(cover_ocr_region_entity_to_read(row))
    return out


def _ocr_candidate_reads_by_cover_id(
    session: Session,
    cover_image_ids: list[int],
) -> dict[int, list[CoverImageOcrCandidateRead]]:
    if not cover_image_ids:
        return {}
    rows = session.exec(
        select(CoverImageOcrCandidate)
        .where(CoverImageOcrCandidate.cover_image_id.in_(cover_image_ids))
        .order_by(CoverImageOcrCandidate.created_at.desc(), CoverImageOcrCandidate.id.desc())
    ).all()
    out: dict[int, list[CoverImageOcrCandidateRead]] = {cover_id: [] for cover_id in cover_image_ids}
    for row in rows:
        out.setdefault(row.cover_image_id, []).append(cover_ocr_candidate_entity_to_read(row))
    return out


def _barcode_candidate_reads_by_cover_id(
    session: Session,
    cover_image_ids: list[int],
) -> dict[int, list[CoverImageBarcodeCandidateRead]]:
    if not cover_image_ids:
        return {}
    rows = session.exec(
        select(CoverImageBarcodeCandidate)
        .where(CoverImageBarcodeCandidate.cover_image_id.in_(cover_image_ids))
        .order_by(CoverImageBarcodeCandidate.updated_at.desc(), CoverImageBarcodeCandidate.id.desc())
    ).all()
    out: dict[int, list[CoverImageBarcodeCandidateRead]] = {cover_id: [] for cover_id in cover_image_ids}
    for row in rows:
        out.setdefault(row.cover_image_id, []).append(cover_barcode_candidate_entity_to_read(row))
    return out


def _fingerprint_reads_by_cover_id(
    session: Session,
    cover_image_ids: list[int],
) -> dict[int, list[CoverImageFingerprintRead]]:
    if not cover_image_ids:
        return {}
    rows = session.exec(
        select(CoverImageFingerprint)
        .where(CoverImageFingerprint.cover_image_id.in_(cover_image_ids))
        .order_by(CoverImageFingerprint.fingerprint_type.asc(), CoverImageFingerprint.id.asc())
    ).all()
    out: dict[int, list[CoverImageFingerprintRead]] = {cover_id: [] for cover_id in cover_image_ids}
    for row in rows:
        out.setdefault(row.cover_image_id, []).append(cover_fingerprint_entity_to_read(row))
    return out


def _ocr_quality_analysis_reads_by_cover_id(
    session: Session,
    cover_image_ids: list[int],
) -> dict[int, list[CoverImageOcrQualityAnalysisRead]]:
    if not cover_image_ids:
        return {}
    rows = session.exec(
        select(CoverImageOcrQualityAnalysis)
        .where(CoverImageOcrQualityAnalysis.cover_image_id.in_(cover_image_ids))
        .order_by(
            case(
                (CoverImageOcrQualityAnalysis.severity == "critical", 0),
                (CoverImageOcrQualityAnalysis.severity == "warning", 1),
                else_=2,
            ),
            case(
                (CoverImageOcrQualityAnalysis.quality_type == "overall_quality", 0),
                else_=1,
            ),
            CoverImageOcrQualityAnalysis.deterministic_score.asc(),
            CoverImageOcrQualityAnalysis.id.asc(),
        )
    ).all()
    out: dict[int, list[CoverImageOcrQualityAnalysisRead]] = {cover_id: [] for cover_id in cover_image_ids}
    for row in rows:
        out.setdefault(row.cover_image_id, []).append(cover_ocr_quality_analysis_entity_to_read(row))
    return out


def _match_candidate_reads_by_cover_id(
    session: Session,
    cover_image_ids: list[int],
) -> dict[int, list[CoverImageMatchCandidateRead]]:
    if not cover_image_ids:
        return {}
    rows = session.exec(
        select(CoverImageMatchCandidate)
        .where(CoverImageMatchCandidate.source_cover_image_id.in_(cover_image_ids))
        .order_by(
            case((CoverImageMatchCandidate.dismissed_at.is_(None), 0), else_=1),
            case((CoverImageMatchCandidate.acknowledged_at.is_(None), 0), else_=1),
            CoverImageMatchCandidate.candidate_rank.asc(),
            CoverImageMatchCandidate.ranking_score.desc(),
            CoverImageMatchCandidate.normalized_confidence_score.desc(),
            CoverImageMatchCandidate.matched_signal_count.desc(),
            CoverImageMatchCandidate.candidate_cover_image_id.asc(),
            CoverImageMatchCandidate.id.asc(),
        )
    ).all()
    decision_map = active_cover_link_decisions_for_pairs(
        session,
        pairs=[(row.source_cover_image_id, row.candidate_cover_image_id) for row in rows],
    )
    decision_read_map = {
        key: cover_link_decision_entity_to_read(session, decision)
        for key, decision in decision_map.items()
    }
    out: dict[int, list[CoverImageMatchCandidateRead]] = {cover_id: [] for cover_id in cover_image_ids}
    for row in rows:
        pair_key = cover_link_pair_key(row.source_cover_image_id, row.candidate_cover_image_id)
        out.setdefault(row.source_cover_image_id, []).append(
            cover_match_candidate_entity_to_read(
                row,
                active_link_decision=decision_read_map.get(pair_key),
            )
        )
    return out


def _ocr_reconciliation_warning_reads_by_cover_id(
    session: Session,
    cover_image_ids: list[int],
) -> dict[int, list[CoverImageOcrReconciliationWarningRead]]:
    if not cover_image_ids:
        return {}
    rows = session.exec(
        select(CoverImageOcrReconciliationWarning)
        .where(CoverImageOcrReconciliationWarning.cover_image_id.in_(cover_image_ids))
        .order_by(
            case(
                (CoverImageOcrReconciliationWarning.status == "open", 0),
                (CoverImageOcrReconciliationWarning.status == "acknowledged", 1),
                else_=2,
            ),
            case(
                (CoverImageOcrReconciliationWarning.severity == "critical", 0),
                (CoverImageOcrReconciliationWarning.severity == "warning", 1),
                else_=2,
            ),
            CoverImageOcrReconciliationWarning.created_at.desc(),
            CoverImageOcrReconciliationWarning.id.desc(),
        )
    ).all()
    out: dict[int, list[CoverImageOcrReconciliationWarningRead]] = {
        cover_id: [] for cover_id in cover_image_ids
    }
    for row in rows:
        out.setdefault(row.cover_image_id, []).append(
            cover_ocr_reconciliation_warning_entity_to_read(row)
        )
    return out


def list_cover_derivative_reads_for_cover(
    session: Session,
    cover_image_id: int,
) -> list[CoverImageDerivativeRead]:
    return _derivative_reads_by_cover_id(session, [cover_image_id]).get(cover_image_id, [])


def list_cover_ocr_region_reads_for_cover(
    session: Session,
    cover_image_id: int,
) -> list[CoverImageOcrRegionRead]:
    return _ocr_region_reads_by_cover_id(session, [cover_image_id]).get(cover_image_id, [])


def list_cover_ocr_candidate_reads_for_cover(
    session: Session,
    cover_image_id: int,
) -> list[CoverImageOcrCandidateRead]:
    return _ocr_candidate_reads_by_cover_id(session, [cover_image_id]).get(cover_image_id, [])


def cover_ocr_result_entity_to_read(row: CoverImageOcrResult) -> CoverImageOcrResultRead:
    if row.id is None:
        raise ValueError("cover image OCR result must be flushed before serialization")
    return CoverImageOcrResultRead(
        id=row.id,
        cover_image_id=row.cover_image_id,
        ocr_engine=row.ocr_engine,
        ocr_engine_version=row.ocr_engine_version,
        processing_status=row.processing_status,  # type: ignore[arg-type]
        raw_text=row.raw_text,
        normalized_text=row.normalized_text,
        confidence_score=row.confidence_score,
        processing_error=public_safe_message(row.processing_error),
        structured_processing_error=(
            StructuredProcessingErrorRead(
                error_code=parsed.error_code,
                error_type=parsed.error_type,
                safe_message=parsed.safe_message,
                retryable=parsed.retryable,
                occurred_at=parsed.occurred_at,
            )
            if (parsed := try_parse_structured_error(row.processing_error))
            else None
        ),
        processed_at=row.processed_at,
        created_at=row.created_at,
        source_cover_image_sha256=row.source_cover_image_sha256,
        source_thumb_derivative_sha256=row.source_thumb_derivative_sha256,
        source_medium_derivative_sha256=row.source_medium_derivative_sha256,
        source_processing_version=row.source_processing_version,
        normalization_version=row.normalization_version,
        replay_of_ocr_result_id=row.replay_of_ocr_result_id,
        replay_reason=row.replay_reason,
        snapshot=build_cover_image_ocr_snapshot_read(row),
    )


def build_cover_image_ocr_snapshot_read(row: CoverImageOcrResult) -> CoverImageOcrSnapshotRead:
    return CoverImageOcrSnapshotRead(
        ocr_engine=row.ocr_engine,
        ocr_engine_version=row.ocr_engine_version,
        raw_text=row.raw_text,
        normalized_text=row.normalized_text,
        confidence_score=row.confidence_score,
        source_cover_image_sha256=row.source_cover_image_sha256,
        source_thumb_derivative_sha256=row.source_thumb_derivative_sha256,
        source_medium_derivative_sha256=row.source_medium_derivative_sha256,
        source_processing_version=row.source_processing_version,
        normalization_version=row.normalization_version,
        created_at=row.created_at,
    )


def _trim_replay_reason(replay_reason: str | None) -> str | None:
    if replay_reason is None:
        return None
    trimmed = replay_reason.strip()
    if not trimmed:
        return None
    return trimmed[:OCR_REPLAY_REASON_MAX_CHARS]


def normalize_ocr_candidate_text(value: str) -> str | None:
    trimmed = value.strip()
    if not trimmed:
        return None
    collapsed = re.sub(r"\s+", " ", trimmed)
    return collapsed.upper()


def _candidate_key(
    *,
    candidate_type: str,
    raw_candidate_text: str,
    extraction_source: str,
) -> tuple[str, str, str]:
    return (
        candidate_type,
        raw_candidate_text.strip(),
        extraction_source,
    )


def _derive_title_and_issue_candidates(text: str) -> list[tuple[str, str]]:
    match = re.search(
        r"(?P<title>[A-Z0-9][A-Z0-9 '&:/\.-]+?)\s+#\s*(?P<issue>\d{1,4}[A-Z]?)\b",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return []
    title = match.group("title").strip(" -:#")
    issue = match.group("issue").strip()
    out: list[tuple[str, str]] = []
    if title:
        out.append(("title", title))
    if issue:
        out.append(("issue_number", issue))
    return out


def _derive_barcode_candidates(text: str) -> list[str]:
    numbers = re.findall(r"\b\d{12}\b", re.sub(r"[^\d]", " ", text))
    return list(dict.fromkeys(numbers))


def _derive_publisher_candidates(text: str) -> list[str]:
    normalized = normalize_ocr_candidate_text(text) or ""
    hits = [publisher for publisher in KNOWN_PUBLISHERS if publisher in normalized]
    return list(dict.fromkeys(hits))


def _build_ocr_candidate_rows(
    *,
    cover_image_id: int,
    ocr_result_id: int,
    extraction_source: str,
    source_text: str,
    max_candidates: int | None = None,
) -> list[CoverImageOcrCandidate]:
    normalized_source = normalize_ocr_candidate_text(source_text) or ""
    rows: list[CoverImageOcrCandidate] = []
    seen: set[tuple[str, str, str]] = set()

    for candidate_type, raw_value in _derive_title_and_issue_candidates(normalized_source):
        key = _candidate_key(
            candidate_type=candidate_type,
            raw_candidate_text=raw_value,
            extraction_source=extraction_source,
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            CoverImageOcrCandidate(
                cover_image_id=cover_image_id,
                ocr_result_id=ocr_result_id,
                candidate_type=candidate_type,
                raw_candidate_text=raw_value,
                normalized_candidate_text=normalize_ocr_candidate_text(raw_value),
                confidence_score=None,
                extraction_source=extraction_source,
                extraction_version=OCR_CANDIDATE_EXTRACTION_VERSION,
            )
        )

    for raw_value in _derive_publisher_candidates(normalized_source):
        key = _candidate_key(
            candidate_type="publisher",
            raw_candidate_text=raw_value,
            extraction_source=extraction_source,
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            CoverImageOcrCandidate(
                cover_image_id=cover_image_id,
                ocr_result_id=ocr_result_id,
                candidate_type="publisher",
                raw_candidate_text=raw_value,
                normalized_candidate_text=normalize_ocr_candidate_text(raw_value),
                confidence_score=None,
                extraction_source=extraction_source,
                extraction_version=OCR_CANDIDATE_EXTRACTION_VERSION,
            )
        )

    for raw_value in _derive_barcode_candidates(normalized_source):
        key = _candidate_key(
            candidate_type="barcode",
            raw_candidate_text=raw_value,
            extraction_source=extraction_source,
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            CoverImageOcrCandidate(
                cover_image_id=cover_image_id,
                ocr_result_id=ocr_result_id,
                candidate_type="barcode",
                raw_candidate_text=raw_value,
                normalized_candidate_text=normalize_ocr_candidate_text(raw_value),
                confidence_score=None,
                extraction_source=extraction_source,
                extraction_version=OCR_CANDIDATE_EXTRACTION_VERSION,
            )
        )
    if max_candidates is not None:
        cap = max(0, int(max_candidates))
        if len(rows) > cap:
            return rows[:cap]
    return rows


def get_latest_cover_image_ocr_result_for_cover(
    session: Session,
    cover_image_id: int,
) -> CoverImageOcrResult | None:
    return session.exec(
        select(CoverImageOcrResult)
        .where(CoverImageOcrResult.cover_image_id == cover_image_id)
        .order_by(CoverImageOcrResult.id.desc())
    ).first()


def get_latest_cover_image_ocr_result_for_cover_or_409(
    session: Session,
    cover_image_id: int,
) -> CoverImageOcrResult:
    row = get_latest_cover_image_ocr_result_for_cover(session, cover_image_id)
    if row is None:
        raise HTTPException(status_code=409, detail="No prior OCR result exists to replay.")
    return row


def persist_cover_image_ocr_source_snapshot(
    session: Session,
    *,
    ocr_result_id: int,
    cover_image_id: int,
) -> CoverImageOcrResult:
    row = get_cover_image_ocr_result_or_404(session, ocr_result_id)
    cover = get_cover_entity_or_404(session, cover_image_id)
    derivative_reads = list_cover_derivative_reads_for_cover(session, cover_image_id)
    thumb_sha = next(
        (item.sha256_hash for item in derivative_reads if item.derivative_type == "thumb"),
        None,
    )
    medium_sha = next(
        (item.sha256_hash for item in derivative_reads if item.derivative_type == "medium"),
        None,
    )
    row.source_cover_image_sha256 = cover.sha256_hash
    row.source_thumb_derivative_sha256 = thumb_sha
    row.source_medium_derivative_sha256 = medium_sha
    row.source_processing_version = OCR_SOURCE_PROCESSING_VERSION
    row.normalization_version = OCR_NORMALIZATION_VERSION
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def extract_ocr_candidates_for_ocr_result(
    session: Session,
    *,
    cover_image_id: int,
    ocr_result_id: int,
) -> list[CoverImageOcrCandidateRead]:
    ocr_row = get_cover_image_ocr_result_or_404(session, ocr_result_id)
    if ocr_row.cover_image_id != cover_image_id:
        raise ValueError("OCR result row does not belong to the requested cover image.")

    pending_rows = _build_ocr_candidate_rows(
        cover_image_id=cover_image_id,
        ocr_result_id=ocr_result_id,
        extraction_source="full_cover",
        source_text=ocr_row.raw_text,
        max_candidates=get_settings().cover_ocr_max_candidates_per_extract,
    )

    for row in pending_rows:
        session.add(row)
    session.commit()
    for row in pending_rows:
        session.refresh(row)
    return [cover_ocr_candidate_entity_to_read(row) for row in pending_rows]


def extract_cover_image_ocr_candidates_for_owner(
    session: Session,
    *,
    current_user: User,
    cover_image_id: int,
) -> CoverImageOcrCandidateExtractResponse:
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )
    latest = get_latest_cover_image_ocr_result_for_cover_or_409(session, cover_image_id)
    candidates = extract_ocr_candidates_for_ocr_result(
        session,
        cover_image_id=cover_image_id,
        ocr_result_id=latest.id,
    )
    return CoverImageOcrCandidateExtractResponse(
        cover_image_id=cover_image_id,
        candidate_count=len(candidates),
        candidates=candidates,
    )


def extract_cover_image_ocr_candidates_for_ops(
    session: Session,
    *,
    cover_image_id: int,
) -> CoverImageOcrCandidateExtractResponse:
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=cover_image_id)
    latest = get_latest_cover_image_ocr_result_for_cover_or_409(session, cover_image_id)
    candidates = extract_ocr_candidates_for_ocr_result(
        session,
        cover_image_id=cover_image_id,
        ocr_result_id=latest.id,
    )
    return CoverImageOcrCandidateExtractResponse(
        cover_image_id=cover_image_id,
        candidate_count=len(candidates),
        candidates=candidates,
    )


def normalize_barcode_candidate_value(raw_value: str) -> tuple[str, str] | None:
    trimmed = raw_value.strip()
    if not trimmed:
        return None
    collapsed = re.sub(r"[\s-]+", "", trimmed)
    digits_only = re.sub(r"\D+", "", collapsed)
    if not digits_only:
        return None
    if len(digits_only) == 12:
        return digits_only, "upc_a"
    if len(digits_only) in {6, 8}:
        return digits_only, "upc_e"
    return None


def _derive_barcode_raw_values_from_text(
    raw_text: str,
    *,
    scan_max_chars: int,
    max_values: int,
) -> list[str]:
    clipped = raw_text[: max(0, int(scan_max_chars))]
    values: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(
        r"(?i)\b(?:UPC(?:-?[AE])?|BARCODE)\s*[:#-]?\s*((?:\d[\d\s-]{4,18}\d))",
        clipped,
    ):
        if len(values) >= max_values:
            break
        raw = match.group(1)
        if raw not in seen:
            values.append(raw)
            seen.add(raw)
    for match in re.finditer(r"(?<!\d)(?:\d[\d\s-]{10,22}\d)(?!\d)", clipped):
        if len(values) >= max_values:
            break
        raw = match.group(0)
        normalized = normalize_barcode_candidate_value(raw)
        if normalized is None or len(normalized[0]) != 12:
            continue
        if raw not in seen:
            values.append(raw)
            seen.add(raw)
    return values


def _barcode_candidate_signature(
    *,
    normalized_upc_value: str,
    source_ocr_result_id: int | None,
    source_ocr_candidate_id: int | None,
    extraction_version: str,
) -> tuple[str, int | None, int | None, str]:
    return (
        normalized_upc_value,
        source_ocr_result_id,
        source_ocr_candidate_id,
        extraction_version,
    )


def _barcode_candidate_snapshot_public(row: CoverImageBarcodeCandidate) -> dict[str, object]:
    return {
        "review_state": row.review_state,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at is not None else None,
        "reviewed_by_user_id": row.reviewed_by_user_id,
        "normalized_upc_value": row.normalized_upc_value,
        "barcode_type": row.barcode_type,
        "cover_image_id": row.cover_image_id,
    }


def list_cover_barcode_candidate_reads_for_cover(
    session: Session,
    cover_image_id: int,
) -> list[CoverImageBarcodeCandidateRead]:
    return _barcode_candidate_reads_by_cover_id(session, [cover_image_id]).get(cover_image_id, [])


def _latest_barcode_candidate_rows_for_ocr_result(
    session: Session,
    *,
    cover_image_id: int,
    ocr_result_id: int,
) -> list[CoverImageOcrCandidate]:
    return session.exec(
        select(CoverImageOcrCandidate)
        .where(
            CoverImageOcrCandidate.cover_image_id == cover_image_id,
            CoverImageOcrCandidate.ocr_result_id == ocr_result_id,
            CoverImageOcrCandidate.candidate_type == "barcode",
        )
        .order_by(CoverImageOcrCandidate.id.asc())
    ).all()


def extract_cover_image_barcode_candidates_for_cover(
    session: Session,
    *,
    cover_image_id: int,
    actor_user_id: int | None = None,
) -> CoverImageBarcodeCandidateExtractResponse:
    settings = get_settings()
    latest = get_latest_cover_image_ocr_result_for_cover_or_409(session, cover_image_id)
    ocr_candidate_rows = _latest_barcode_candidate_rows_for_ocr_result(
        session,
        cover_image_id=cover_image_id,
        ocr_result_id=latest.id,
    )
    existing_rows = session.exec(
        select(CoverImageBarcodeCandidate).where(CoverImageBarcodeCandidate.cover_image_id == cover_image_id)
    ).all()
    existing_by_signature = {
        _barcode_candidate_signature(
            normalized_upc_value=row.normalized_upc_value,
            source_ocr_result_id=row.source_ocr_result_id,
            source_ocr_candidate_id=row.source_ocr_candidate_id,
            extraction_version=row.extraction_version,
        ): row
        for row in existing_rows
        if row.id is not None
    }
    now = _processing_now()
    emitted_signatures: set[tuple[str, int | None, int | None, str]] = set()
    candidate_normalized_values: set[str] = set()

    for ocr_candidate in ocr_candidate_rows:
        normalized = normalize_barcode_candidate_value(ocr_candidate.raw_candidate_text)
        if normalized is None:
            continue
        normalized_upc_value, barcode_type = normalized
        candidate_normalized_values.add(normalized_upc_value)
        signature = _barcode_candidate_signature(
            normalized_upc_value=normalized_upc_value,
            source_ocr_result_id=ocr_candidate.ocr_result_id,
            source_ocr_candidate_id=ocr_candidate.id,
            extraction_version=BARCODE_CANDIDATE_EXTRACTION_VERSION,
        )
        emitted_signatures.add(signature)
        existing = existing_by_signature.get(signature)
        if existing is None:
            created = CoverImageBarcodeCandidate(
                cover_image_id=cover_image_id,
                source_ocr_result_id=ocr_candidate.ocr_result_id,
                source_ocr_candidate_id=ocr_candidate.id,
                raw_barcode_value=ocr_candidate.raw_candidate_text,
                normalized_upc_value=normalized_upc_value,
                barcode_type=barcode_type,
                confidence=ocr_candidate.confidence_score,
                extraction_version=BARCODE_CANDIDATE_EXTRACTION_VERSION,
                review_state="pending",
                reviewed_at=None,
                reviewed_by_user_id=None,
                created_at=now,
                updated_at=now,
            )
            session.add(created)
            session.flush()
            record_metadata_audit(
                session,
                entity_type="barcode_candidate",
                entity_id=created.id,
                action="barcode_candidate_created",
                before_snapshot=None,
                after_snapshot=cover_barcode_candidate_entity_to_read(created),
                actor_user_id=actor_user_id,
            )
            existing_by_signature[signature] = created
            continue
        existing.raw_barcode_value = ocr_candidate.raw_candidate_text
        existing.barcode_type = barcode_type
        existing.confidence = ocr_candidate.confidence_score
        existing.updated_at = now
        session.add(existing)

    try:
        raw_barcode_hints = run_with_thread_deadline(
            float(settings.cover_barcode_derive_regex_timeout_seconds),
            lambda: _derive_barcode_raw_values_from_text(
                latest.raw_text or "",
                scan_max_chars=int(settings.cover_barcode_raw_derive_scan_max_chars),
                max_values=max(1, int(settings.cover_barcode_candidate_emit_max_per_extract)),
            ),
            stage="barcode_regex_derivation",
        )
    except PipelineStepTimeout:
        raise HTTPException(
            status_code=409,
            detail="Barcode derivation from OCR text exceeded the bounded deadline.",
        ) from None

    for raw_value in raw_barcode_hints:
        normalized = normalize_barcode_candidate_value(raw_value)
        if normalized is None:
            continue
        normalized_upc_value, barcode_type = normalized
        if normalized_upc_value in candidate_normalized_values:
            continue
        signature = _barcode_candidate_signature(
            normalized_upc_value=normalized_upc_value,
            source_ocr_result_id=latest.id,
            source_ocr_candidate_id=None,
            extraction_version=BARCODE_CANDIDATE_EXTRACTION_VERSION,
        )
        emitted_signatures.add(signature)
        existing = existing_by_signature.get(signature)
        if existing is None:
            created = CoverImageBarcodeCandidate(
                cover_image_id=cover_image_id,
                source_ocr_result_id=latest.id,
                source_ocr_candidate_id=None,
                raw_barcode_value=raw_value,
                normalized_upc_value=normalized_upc_value,
                barcode_type=barcode_type,
                confidence=latest.confidence_score,
                extraction_version=BARCODE_CANDIDATE_EXTRACTION_VERSION,
                review_state="pending",
                reviewed_at=None,
                reviewed_by_user_id=None,
                created_at=now,
                updated_at=now,
            )
            session.add(created)
            session.flush()
            record_metadata_audit(
                session,
                entity_type="barcode_candidate",
                entity_id=created.id,
                action="barcode_candidate_created",
                before_snapshot=None,
                after_snapshot=cover_barcode_candidate_entity_to_read(created),
                actor_user_id=actor_user_id,
            )
            existing_by_signature[signature] = created
            continue
        existing.raw_barcode_value = raw_value
        existing.barcode_type = barcode_type
        existing.confidence = latest.confidence_score
        existing.updated_at = now
        session.add(existing)

    session.commit()
    candidates = list_cover_barcode_candidate_reads_for_cover(session, cover_image_id)
    return CoverImageBarcodeCandidateExtractResponse(
        cover_image_id=cover_image_id,
        candidate_count=len(candidates),
        candidates=candidates,
    )


def extract_cover_image_barcode_candidates_for_owner(
    session: Session,
    *,
    current_user: User,
    cover_image_id: int,
) -> CoverImageBarcodeCandidateExtractResponse:
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )
    return extract_cover_image_barcode_candidates_for_cover(
        session,
        cover_image_id=cover_image_id,
        actor_user_id=current_user.id,
    )


def extract_cover_image_barcode_candidates_for_ops(
    session: Session,
    *,
    cover_image_id: int,
    actor_user_id: int | None = None,
) -> CoverImageBarcodeCandidateExtractResponse:
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=cover_image_id)
    return extract_cover_image_barcode_candidates_for_cover(
        session,
        cover_image_id=cover_image_id,
        actor_user_id=actor_user_id,
    )


def get_cover_image_barcode_candidate_or_404(
    session: Session,
    barcode_candidate_id: int,
) -> CoverImageBarcodeCandidate:
    row = session.get(CoverImageBarcodeCandidate, barcode_candidate_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Barcode candidate not found")
    return row


def _set_barcode_candidate_review_state(
    session: Session,
    *,
    row: CoverImageBarcodeCandidate,
    review_state: Literal["approved", "rejected"],
    actor_user_id: int,
) -> CoverImageBarcodeCandidateRead:
    if row.id is None:
        raise ValueError("barcode candidate must be flushed before review updates")
    before = _barcode_candidate_snapshot_public(row)
    row.review_state = review_state
    row.reviewed_at = _processing_now()
    row.reviewed_by_user_id = actor_user_id
    row.updated_at = row.reviewed_at
    session.add(row)
    record_metadata_audit(
        session,
        entity_type="barcode_candidate",
        entity_id=row.id,
        action=f"barcode_candidate_{review_state}",
        before_snapshot=before,
        after_snapshot=_barcode_candidate_snapshot_public(row),
        actor_user_id=actor_user_id,
    )
    session.commit()
    session.refresh(row)
    return cover_barcode_candidate_entity_to_read(row)


def approve_cover_image_barcode_candidate_for_owner(
    session: Session,
    *,
    current_user: User,
    barcode_candidate_id: int,
) -> CoverImageBarcodeCandidateRead:
    row = get_cover_image_barcode_candidate_or_404(session, barcode_candidate_id)
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=row.cover_image_id,
    )
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return _set_barcode_candidate_review_state(
        session,
        row=row,
        review_state="approved",
        actor_user_id=current_user.id,
    )


def reject_cover_image_barcode_candidate_for_owner(
    session: Session,
    *,
    current_user: User,
    barcode_candidate_id: int,
) -> CoverImageBarcodeCandidateRead:
    row = get_cover_image_barcode_candidate_or_404(session, barcode_candidate_id)
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=row.cover_image_id,
    )
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return _set_barcode_candidate_review_state(
        session,
        row=row,
        review_state="rejected",
        actor_user_id=current_user.id,
    )


def approve_cover_image_barcode_candidate_for_ops(
    session: Session,
    *,
    barcode_candidate_id: int,
    actor_user_id: int,
) -> CoverImageBarcodeCandidateRead:
    row = get_cover_image_barcode_candidate_or_404(session, barcode_candidate_id)
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=row.cover_image_id)
    return _set_barcode_candidate_review_state(
        session,
        row=row,
        review_state="approved",
        actor_user_id=actor_user_id,
    )


def reject_cover_image_barcode_candidate_for_ops(
    session: Session,
    *,
    barcode_candidate_id: int,
    actor_user_id: int,
) -> CoverImageBarcodeCandidateRead:
    row = get_cover_image_barcode_candidate_or_404(session, barcode_candidate_id)
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=row.cover_image_id)
    return _set_barcode_candidate_review_state(
        session,
        row=row,
        review_state="rejected",
        actor_user_id=actor_user_id,
    )


def normalize_fingerprint_hex(bits: list[bool]) -> str:
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    width = max(1, len(bits) // 4)
    return f"{value:0{width}x}"


def hamming_distance_hex(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def _grayscale_pixels_from_image_bytes(image_bytes: bytes, *, size: tuple[int, int]) -> list[float]:
    with Image.open(io.BytesIO(image_bytes)) as img:
        grayscale = img.convert("L").resize(size, Image.Resampling.LANCZOS)
        return [float(value) for value in grayscale.getdata()]


def _image_dimensions_from_bytes(image_bytes: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(image_bytes)) as img:
        return int(img.width), int(img.height)


def _dct_1d(values: list[float]) -> list[float]:
    size = len(values)
    out: list[float] = []
    factor = math.pi / (2.0 * size)
    for k in range(size):
        coeff = math.sqrt(1.0 / size) if k == 0 else math.sqrt(2.0 / size)
        total = 0.0
        for n, value in enumerate(values):
            total += value * math.cos((2 * n + 1) * k * factor)
        out.append(coeff * total)
    return out


def _matrix_from_flat(values: list[float], width: int, height: int) -> list[list[float]]:
    return [values[row * width : (row + 1) * width] for row in range(height)]


def _transpose_matrix(values: list[list[float]]) -> list[list[float]]:
    return [list(column) for column in zip(*values, strict=False)]


def generate_average_hash(image_bytes: bytes) -> str:
    pixels = _grayscale_pixels_from_image_bytes(image_bytes, size=(8, 8))
    avg = sum(pixels) / len(pixels)
    return normalize_fingerprint_hex([value > avg for value in pixels])


def generate_difference_hash(image_bytes: bytes) -> str:
    pixels = _grayscale_pixels_from_image_bytes(image_bytes, size=(9, 8))
    rows = _matrix_from_flat(pixels, 9, 8)
    bits: list[bool] = []
    for row in rows:
        for idx in range(8):
            bits.append(row[idx] > row[idx + 1])
    return normalize_fingerprint_hex(bits)


def generate_perceptual_hash(image_bytes: bytes) -> str:
    pixels = _grayscale_pixels_from_image_bytes(image_bytes, size=(32, 32))
    matrix = _matrix_from_flat(pixels, 32, 32)
    dct_rows = [_dct_1d(row) for row in matrix]
    dct_cols = _transpose_matrix([_dct_1d(column) for column in _transpose_matrix(dct_rows)])
    top_left = [dct_cols[row][col] for row in range(8) for col in range(8)]
    threshold = float(median(top_left[1:])) if len(top_left) > 1 else 0.0
    return normalize_fingerprint_hex([value > threshold for value in top_left])


def _read_derivative_bytes_verified(settings: Settings, row: CoverImageDerivative) -> bytes:
    abs_path = resolve_filesystem_path(settings, row.storage_path)
    if not abs_path.is_file():
        raise ValueError("Cover image derivative file missing on disk")
    body = abs_path.read_bytes()
    computed_sha = sha256_raw_bytes(body)
    if computed_sha != row.sha256_hash:
        raise ValueError("Stored derivative SHA-256 does not match file contents")
    return body


def _cover_fingerprint_source(
    session: Session,
    *,
    settings: Settings,
    cover: CoverImage,
) -> tuple[str, bytes, int, int, str | None]:
    medium = session.exec(
        select(CoverImageDerivative).where(
            CoverImageDerivative.cover_image_id == cover.id,
            CoverImageDerivative.derivative_type == "medium",
        )
    ).first()
    if medium is not None:
        try:
            payload = _read_derivative_bytes_verified(settings, medium)
            width = int(medium.image_width) if medium.image_width is not None else _image_dimensions_from_bytes(payload)[0]
            height = int(medium.image_height) if medium.image_height is not None else _image_dimensions_from_bytes(payload)[1]
            validate_pipeline_image_bytes(
                settings=settings,
                body=payload,
                mime_type=medium.mime_type or cover.mime_type,
                declared_width=width,
                declared_height=height,
                stage="fingerprint_derivative_medium",
            )
            return "medium", payload, width, height, medium.sha256_hash
        except ValueError:
            pass
    payload = _read_cover_source_bytes_verified(settings, cover)
    validate_pipeline_image_bytes(
        settings=settings,
        body=payload,
        mime_type=cover.mime_type,
        declared_width=cover.image_width,
        declared_height=cover.image_height,
        stage="fingerprint_cover_source_bytes",
    )
    width, height = _image_dimensions_from_bytes(payload)
    return "original", payload, width, height, cover.sha256_hash


def list_cover_fingerprint_reads_for_cover(
    session: Session,
    cover_image_id: int,
) -> list[CoverImageFingerprintRead]:
    return _fingerprint_reads_by_cover_id(session, [cover_image_id]).get(cover_image_id, [])


def generate_cover_image_fingerprints_for_cover(
    session: Session,
    *,
    settings: Settings,
    cover_image_id: int,
    actor_user_id: int | None = None,
) -> CoverImageFingerprintGenerateResponse:
    cover = get_cover_entity_or_404(session, cover_image_id)
    try:
        derivative_type, payload, image_width, image_height, image_sha256 = _cover_fingerprint_source(
            session,
            settings=settings,
            cover=cover,
        )
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    generators = {
        "ahash": generate_average_hash,
        "dhash": generate_difference_hash,
        "phash": generate_perceptual_hash,
    }
    existing_rows = session.exec(
        select(CoverImageFingerprint)
        .where(CoverImageFingerprint.cover_image_id == cover_image_id)
        .order_by(CoverImageFingerprint.id.asc())
    ).all()
    existing_by_type = {row.fingerprint_type: row for row in existing_rows}
    now = _processing_now()

    for fingerprint_type, generator in generators.items():
        try:
            fingerprint_value = run_with_thread_deadline(
                float(settings.cover_fingerprint_generation_thread_timeout_seconds),
                lambda ft=fingerprint_type, gen=generator: gen(payload),
                stage=f"fingerprint_{fingerprint_type}",
            )
        except PipelineStepTimeout:
            raise HTTPException(
                status_code=409,
                detail=f"Fingerprint {fingerprint_type} generation exceeded the bounded deadline.",
            ) from None
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=f"Fingerprint generation failed: {exc}") from exc
        row = existing_by_type.get(fingerprint_type)
        if row is None:
            row = CoverImageFingerprint(
                cover_image_id=cover_image_id,
                fingerprint_type=fingerprint_type,
                fingerprint_value=fingerprint_value,
                derivative_type=derivative_type,
                image_width=image_width,
                image_height=image_height,
                image_sha256=image_sha256,
                extraction_version=FINGERPRINT_EXTRACTION_VERSION,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.flush()
            record_metadata_audit(
                session,
                entity_type="cover_fingerprint",
                entity_id=row.id,
                action="cover_fingerprint_created",
                before_snapshot=None,
                after_snapshot=cover_fingerprint_entity_to_read(row),
                actor_user_id=actor_user_id,
            )
            continue

        before = cover_fingerprint_entity_to_read(row)
        changed = (
            row.fingerprint_value != fingerprint_value
            or row.derivative_type != derivative_type
            or row.image_width != image_width
            or row.image_height != image_height
            or row.image_sha256 != image_sha256
            or row.extraction_version != FINGERPRINT_EXTRACTION_VERSION
        )
        row.fingerprint_value = fingerprint_value
        row.derivative_type = derivative_type
        row.image_width = image_width
        row.image_height = image_height
        row.image_sha256 = image_sha256
        row.extraction_version = FINGERPRINT_EXTRACTION_VERSION
        row.updated_at = now
        session.add(row)
        if changed:
            session.flush()
            record_metadata_audit(
                session,
                entity_type="cover_fingerprint",
                entity_id=row.id,
                action="cover_fingerprint_regenerated",
                before_snapshot=before,
                after_snapshot=cover_fingerprint_entity_to_read(row),
                actor_user_id=actor_user_id,
            )

    session.commit()
    fingerprints = list_cover_fingerprint_reads_for_cover(session, cover_image_id)
    return CoverImageFingerprintGenerateResponse(
        cover_image_id=cover_image_id,
        fingerprint_count=len(fingerprints),
        fingerprints=fingerprints,
    )


def generate_cover_image_fingerprints_for_owner(
    session: Session,
    *,
    settings: Settings,
    current_user: User,
    cover_image_id: int,
) -> CoverImageFingerprintGenerateResponse:
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )
    return generate_cover_image_fingerprints_for_cover(
        session,
        settings=settings,
        cover_image_id=cover_image_id,
        actor_user_id=current_user.id,
    )


def generate_cover_image_fingerprints_for_ops(
    session: Session,
    *,
    settings: Settings,
    cover_image_id: int,
    actor_user_id: int | None = None,
) -> CoverImageFingerprintGenerateResponse:
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=cover_image_id)
    return generate_cover_image_fingerprints_for_cover(
        session,
        settings=settings,
        cover_image_id=cover_image_id,
        actor_user_id=actor_user_id,
    )


def list_cover_ocr_quality_analysis_reads_for_cover(
    session: Session,
    cover_image_id: int,
) -> list[CoverImageOcrQualityAnalysisRead]:
    return _ocr_quality_analysis_reads_by_cover_id(session, [cover_image_id]).get(cover_image_id, [])


def _clamp_quality_score(value: float) -> float:
    return round(max(0.0, min(value, 1.0)), 4)


def _quality_severity_for_score(score: float) -> Literal["info", "warning", "critical"]:
    if score >= OCR_QUALITY_INFO_THRESHOLD:
        return "info"
    if score >= OCR_QUALITY_WARNING_THRESHOLD:
        return "warning"
    return "critical"


def _quality_score_from_thresholds(
    value: float,
    *,
    info_threshold: float,
    warning_threshold: float,
) -> float:
    if value >= info_threshold:
        return 1.0
    if value <= warning_threshold:
        return _clamp_quality_score(value / warning_threshold if warning_threshold > 0 else 0.0)
    span = info_threshold - warning_threshold
    if span <= 0:
        return 1.0
    normalized = (value - warning_threshold) / span
    return _clamp_quality_score(0.5 + (normalized * 0.5))


def _laplacian_variance(image_bytes: bytes) -> float:
    pixels = _grayscale_pixels_from_image_bytes(image_bytes, size=(64, 64))
    rows = _matrix_from_flat(pixels, 64, 64)
    values: list[float] = []
    for y in range(1, 63):
        for x in range(1, 63):
            center = rows[y][x] * 4.0
            value = center - rows[y - 1][x] - rows[y + 1][x] - rows[y][x - 1] - rows[y][x + 1]
            values.append(value)
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return round(variance, 4)


def _grayscale_stddev(image_bytes: bytes) -> float:
    pixels = _grayscale_pixels_from_image_bytes(image_bytes, size=(64, 64))
    if not pixels:
        return 0.0
    mean = sum(pixels) / len(pixels)
    variance = sum((value - mean) ** 2 for value in pixels) / len(pixels)
    return round(math.sqrt(variance), 4)


def _border_and_empty_space_metrics(image_bytes: bytes) -> tuple[float, float, float]:
    pixels = _grayscale_pixels_from_image_bytes(image_bytes, size=(64, 64))
    rows = _matrix_from_flat(pixels, 64, 64)
    border_width = max(1, int(64 * OCR_QUALITY_CROP_BORDER_FRACTION))
    border_pixels: list[float] = []
    for y in range(64):
        for x in range(64):
            if x < border_width or x >= 64 - border_width or y < border_width or y >= 64 - border_width:
                border_pixels.append(rows[y][x])
    if not border_pixels:
        return 0.0, 0.0, 0.0
    border_white_ratio = sum(1 for value in border_pixels if value >= 245.0) / len(border_pixels)
    border_black_ratio = sum(1 for value in border_pixels if value <= 10.0) / len(border_pixels)
    border_extreme_ratio = round(max(border_white_ratio, border_black_ratio), 4)

    empty_white_ratio = sum(1 for value in pixels if value >= 245.0) / len(pixels)
    empty_black_ratio = sum(1 for value in pixels if value <= 10.0) / len(pixels)
    empty_space_ratio = round(max(empty_white_ratio, empty_black_ratio), 4)
    return border_extreme_ratio, round(empty_white_ratio, 4), empty_space_ratio


def _ocr_quality_snapshot_public(row: CoverImageOcrQualityAnalysis) -> dict[str, object]:
    return {
        "cover_image_id": row.cover_image_id,
        "source_ocr_result_id": row.source_ocr_result_id,
        "quality_type": row.quality_type,
        "deterministic_score": row.deterministic_score,
        "severity": row.severity,
        "detail_json": row.detail_json or {},
        "extraction_version": row.extraction_version,
    }


def _ocr_quality_signature(*, cover_image_id: int, quality_type: str) -> tuple[int, str, str]:
    return (
        cover_image_id,
        quality_type,
        OCR_QUALITY_ANALYSIS_EXTRACTION_VERSION,
    )


def _build_ocr_quality_analysis_specs(
    *,
    cover: CoverImage,
    derivative_type: str,
    image_bytes: bytes,
    source_ocr_result: CoverImageOcrResult | None,
) -> list[dict[str, object]]:
    width = int(cover.image_width or 0)
    height = int(cover.image_height or 0)
    if width <= 0 or height <= 0:
        width, height = _image_dimensions_from_bytes(image_bytes)

    blur_variance = _laplacian_variance(image_bytes)
    blur_score = _quality_score_from_thresholds(
        blur_variance,
        info_threshold=OCR_QUALITY_BLUR_INFO_THRESHOLD,
        warning_threshold=OCR_QUALITY_BLUR_WARNING_THRESHOLD,
    )

    resolution_score = _clamp_quality_score(
        min(width / OCR_QUALITY_MIN_WIDTH, height / OCR_QUALITY_MIN_HEIGHT, 1.0)
    )

    contrast_stddev = _grayscale_stddev(image_bytes)
    contrast_score = _quality_score_from_thresholds(
        contrast_stddev,
        info_threshold=OCR_QUALITY_CONTRAST_INFO_THRESHOLD,
        warning_threshold=OCR_QUALITY_CONTRAST_WARNING_THRESHOLD,
    )

    border_ratio, empty_white_ratio, empty_space_ratio = _border_and_empty_space_metrics(image_bytes)
    aspect_ratio = round(width / height, 4) if height > 0 else 0.0
    aspect_penalty = min(abs(aspect_ratio - 0.67) / 0.33, 1.0) if aspect_ratio > 0 else 1.0
    crop_score = _clamp_quality_score(
        1.0 - min(1.0, (border_ratio * 0.6) + (empty_space_ratio * 0.25) + (aspect_penalty * 0.15))
    )

    raw_text = (source_ocr_result.raw_text if source_ocr_result is not None else "") or ""
    normalized_text = raw_text.strip()
    nonspace = re.sub(r"\s+", "", normalized_text)
    alnum_count = sum(1 for char in nonspace if char.isalnum())
    weird_count = sum(1 for char in nonspace if not char.isalnum())
    token_count = len(re.findall(r"[A-Za-z0-9]+", normalized_text))
    malformed_ratio = weird_count / max(1, len(nonspace))
    confidence_component = _clamp_quality_score(float(source_ocr_result.confidence_score or 0.0))
    text_length_component = _clamp_quality_score(alnum_count / 24.0)
    token_component = _clamp_quality_score(token_count / 6.0)
    readability_score = _clamp_quality_score(
        (confidence_component * 0.55)
        + (text_length_component * 0.3)
        + (token_component * 0.15)
        - min(0.35, malformed_ratio * 0.5)
    )
    if not normalized_text:
        readability_score = 0.0
    elif alnum_count < 6 or token_count < 2:
        readability_score = min(readability_score, 0.2)

    overall_score = _clamp_quality_score(
        (blur_score * 0.3)
        + (readability_score * 0.3)
        + (resolution_score * 0.2)
        + (contrast_score * 0.1)
        + (crop_score * 0.1)
    )

    base_detail = {
        "image_source": derivative_type,
        "image_width": width,
        "image_height": height,
    }
    source_ocr_result_id = source_ocr_result.id if source_ocr_result is not None else None
    return [
        {
            "quality_type": "blur_detection",
            "deterministic_score": blur_score,
            "severity": _quality_severity_for_score(blur_score),
            "detail_json": {
                **base_detail,
                "laplacian_variance": blur_variance,
                "threshold_info": OCR_QUALITY_BLUR_INFO_THRESHOLD,
                "threshold_warning": OCR_QUALITY_BLUR_WARNING_THRESHOLD,
            },
            "source_ocr_result_id": source_ocr_result_id,
        },
        {
            "quality_type": "low_resolution",
            "deterministic_score": resolution_score,
            "severity": _quality_severity_for_score(resolution_score),
            "detail_json": {
                **base_detail,
                "min_width_threshold": OCR_QUALITY_MIN_WIDTH,
                "min_height_threshold": OCR_QUALITY_MIN_HEIGHT,
            },
            "source_ocr_result_id": source_ocr_result_id,
        },
        {
            "quality_type": "low_contrast",
            "deterministic_score": contrast_score,
            "severity": _quality_severity_for_score(contrast_score),
            "detail_json": {
                **base_detail,
                "grayscale_stddev": contrast_stddev,
                "threshold_info": OCR_QUALITY_CONTRAST_INFO_THRESHOLD,
                "threshold_warning": OCR_QUALITY_CONTRAST_WARNING_THRESHOLD,
            },
            "source_ocr_result_id": source_ocr_result_id,
        },
        {
            "quality_type": "unreadable_ocr",
            "deterministic_score": readability_score,
            "severity": _quality_severity_for_score(readability_score),
            "detail_json": {
                "source_ocr_result_id": source_ocr_result_id,
                "ocr_confidence": source_ocr_result.confidence_score if source_ocr_result is not None else None,
                "raw_text_length": len(raw_text),
                "alnum_count": alnum_count,
                "token_count": token_count,
                "malformed_ratio": round(malformed_ratio, 4),
            },
            "source_ocr_result_id": source_ocr_result_id,
        },
        {
            "quality_type": "crop_quality",
            "deterministic_score": crop_score,
            "severity": _quality_severity_for_score(crop_score),
            "detail_json": {
                **base_detail,
                "aspect_ratio": aspect_ratio,
                "border_extreme_ratio": border_ratio,
                "empty_space_ratio": empty_space_ratio,
                "empty_white_ratio": empty_white_ratio,
            },
            "source_ocr_result_id": source_ocr_result_id,
        },
        {
            "quality_type": "overall_quality",
            "deterministic_score": overall_score,
            "severity": _quality_severity_for_score(overall_score),
            "detail_json": {
                "component_scores": {
                    "blur_detection": blur_score,
                    "low_resolution": resolution_score,
                    "low_contrast": contrast_score,
                    "unreadable_ocr": readability_score,
                    "crop_quality": crop_score,
                }
            },
            "source_ocr_result_id": source_ocr_result_id,
        },
    ]


def analyze_cover_image_ocr_quality_for_cover(
    session: Session,
    *,
    settings: Settings,
    cover_image_id: int,
    actor_user_id: int | None = None,
) -> CoverImageOcrQualityAnalysisResponse:
    cover = get_cover_entity_or_404(session, cover_image_id)
    try:
        derivative_type, image_bytes, _, _, _ = _cover_fingerprint_source(
            session,
            settings=settings,
            cover=cover,
        )
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    source_ocr_result = session.exec(
        select(CoverImageOcrResult)
        .where(CoverImageOcrResult.cover_image_id == cover_image_id)
        .order_by(CoverImageOcrResult.created_at.desc(), CoverImageOcrResult.id.desc())
    ).first()
    try:
        specs = run_with_thread_deadline(
            float(settings.cover_quality_analysis_thread_timeout_seconds),
            lambda: _build_ocr_quality_analysis_specs(
                cover=cover,
                derivative_type=derivative_type,
                image_bytes=image_bytes,
                source_ocr_result=source_ocr_result,
            ),
            stage="ocr_quality_specs",
        )
    except PipelineStepTimeout:
        raise HTTPException(
            status_code=409,
            detail="OCR quality analysis exceeded the bounded deadline.",
        ) from None
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=f"OCR quality analysis failed: {exc}") from exc

    existing_rows = session.exec(
        select(CoverImageOcrQualityAnalysis)
        .where(CoverImageOcrQualityAnalysis.cover_image_id == cover_image_id)
        .order_by(CoverImageOcrQualityAnalysis.id.asc())
    ).all()
    existing_by_signature = {
        _ocr_quality_signature(cover_image_id=row.cover_image_id, quality_type=row.quality_type): row
        for row in existing_rows
    }
    now = _processing_now()

    for spec in specs:
        quality_type = str(spec["quality_type"])
        signature = _ocr_quality_signature(cover_image_id=cover_image_id, quality_type=quality_type)
        row = existing_by_signature.get(signature)
        score = float(spec["deterministic_score"])
        severity = str(spec["severity"])
        detail_json = dict(spec["detail_json"])
        source_ocr_result_id = (
            int(spec["source_ocr_result_id"]) if spec["source_ocr_result_id"] is not None else None
        )
        if row is None:
            row = CoverImageOcrQualityAnalysis(
                cover_image_id=cover_image_id,
                source_ocr_result_id=source_ocr_result_id,
                quality_type=quality_type,
                deterministic_score=score,
                severity=severity,
                detail_json=detail_json,
                extraction_version=OCR_QUALITY_ANALYSIS_EXTRACTION_VERSION,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.flush()
            record_metadata_audit(
                session,
                entity_type="ocr_quality_analysis",
                entity_id=row.id,
                action="ocr_quality_analysis_created",
                before_snapshot=None,
                after_snapshot=_ocr_quality_snapshot_public(row),
                actor_user_id=actor_user_id,
            )
            continue

        before = _ocr_quality_snapshot_public(row)
        changed = (
            row.source_ocr_result_id != source_ocr_result_id
            or row.deterministic_score != score
            or row.severity != severity
            or (row.detail_json or {}) != detail_json
            or row.extraction_version != OCR_QUALITY_ANALYSIS_EXTRACTION_VERSION
        )
        row.source_ocr_result_id = source_ocr_result_id
        row.deterministic_score = score
        row.severity = severity
        row.detail_json = detail_json
        row.extraction_version = OCR_QUALITY_ANALYSIS_EXTRACTION_VERSION
        row.updated_at = now
        session.add(row)
        if changed:
            session.flush()
            record_metadata_audit(
                session,
                entity_type="ocr_quality_analysis",
                entity_id=row.id,
                action="ocr_quality_analysis_regenerated",
                before_snapshot=before,
                after_snapshot=_ocr_quality_snapshot_public(row),
                actor_user_id=actor_user_id,
            )

    session.commit()
    analyses = list_cover_ocr_quality_analysis_reads_for_cover(session, cover_image_id)
    return CoverImageOcrQualityAnalysisResponse(
        cover_image_id=cover_image_id,
        analysis_count=len(analyses),
        analyses=analyses,
    )


def analyze_cover_image_ocr_quality_for_owner(
    session: Session,
    *,
    settings: Settings,
    current_user: User,
    cover_image_id: int,
) -> CoverImageOcrQualityAnalysisResponse:
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )
    return analyze_cover_image_ocr_quality_for_cover(
        session,
        settings=settings,
        cover_image_id=cover_image_id,
        actor_user_id=current_user.id,
    )


def analyze_cover_image_ocr_quality_for_ops(
    session: Session,
    *,
    settings: Settings,
    cover_image_id: int,
    actor_user_id: int | None = None,
) -> CoverImageOcrQualityAnalysisResponse:
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=cover_image_id)
    return analyze_cover_image_ocr_quality_for_cover(
        session,
        settings=settings,
        cover_image_id=cover_image_id,
        actor_user_id=actor_user_id,
    )


def _ocr_quality_analysis_count_by_cover_id(
    session: Session,
    cover_image_ids: list[int],
) -> dict[int, int]:
    if not cover_image_ids:
        return {}
    rows = session.exec(
        select(
            CoverImageOcrQualityAnalysis.cover_image_id,
            func.count(CoverImageOcrQualityAnalysis.id),
        )
        .where(CoverImageOcrQualityAnalysis.cover_image_id.in_(cover_image_ids))
        .group_by(CoverImageOcrQualityAnalysis.cover_image_id)
    ).all()
    return {int(cover_id): int(count) for cover_id, count in rows}


def _match_candidate_snapshot_public(row: CoverImageMatchCandidate) -> dict[str, object]:
    return {
        "source_cover_image_id": row.source_cover_image_id,
        "candidate_cover_image_id": row.candidate_cover_image_id,
        "candidate_type": row.candidate_type,
        "confidence_bucket": row.confidence_bucket,
        "deterministic_score": row.deterministic_score,
        "normalized_confidence_score": row.normalized_confidence_score,
        "confidence_version": row.confidence_version,
        "scoring_breakdown_json": row.scoring_breakdown_json or {},
        "matched_signal_count": row.matched_signal_count,
        "hard_match_flags_json": row.hard_match_flags_json or {},
        "weak_signal_flags_json": row.weak_signal_flags_json or {},
        "ranking_score": row.ranking_score,
        "ranking_version": row.ranking_version,
        "ranking_reason_json": row.ranking_reason_json or {},
        "candidate_rank": row.candidate_rank,
        "grouping_key": row.grouping_key,
        "grouping_type": row.grouping_type,
        "grouping_confidence_bucket": row.grouping_confidence_bucket,
        "grouping_reason_summary": row.grouping_reason_summary,
        "matched_signals": row.matched_signals or {},
        "extraction_version": row.extraction_version,
        "dismissed_at": row.dismissed_at.isoformat() if row.dismissed_at is not None else None,
        "acknowledged_at": row.acknowledged_at.isoformat() if row.acknowledged_at is not None else None,
    }


def list_cover_match_candidate_reads_for_cover(
    session: Session,
    cover_image_id: int,
) -> list[CoverImageMatchCandidateRead]:
    return _match_candidate_reads_by_cover_id(session, [cover_image_id]).get(cover_image_id, [])


def get_cover_match_group(
    session: Session,
    *,
    grouping_key: str,
) -> CoverImageMatchGroupRead:
    rows = session.exec(
        select(CoverImageMatchCandidate)
        .where(CoverImageMatchCandidate.grouping_key == grouping_key)
        .order_by(
            CoverImageMatchCandidate.candidate_rank.asc(),
            CoverImageMatchCandidate.ranking_score.desc(),
            CoverImageMatchCandidate.normalized_confidence_score.desc(),
            CoverImageMatchCandidate.matched_signal_count.desc(),
            CoverImageMatchCandidate.candidate_cover_image_id.asc(),
            CoverImageMatchCandidate.id.asc(),
        )
    ).all()
    if not rows:
        raise HTTPException(status_code=404, detail="Match group not found")
    first = rows[0]
    if first.grouping_type is None or first.grouping_confidence_bucket is None:
        raise HTTPException(status_code=404, detail="Match group not found")
    decision_map = active_cover_link_decisions_for_pairs(
        session,
        pairs=[(row.source_cover_image_id, row.candidate_cover_image_id) for row in rows],
    )
    decision_read_map = {
        key: cover_link_decision_entity_to_read(session, decision)
        for key, decision in decision_map.items()
    }
    candidates = [
        cover_match_candidate_entity_to_read(
            row,
            active_link_decision=decision_read_map.get(
                cover_link_pair_key(row.source_cover_image_id, row.candidate_cover_image_id)
            ),
        )
        for row in rows
    ]
    return CoverImageMatchGroupRead(
        grouping_key=grouping_key,
        grouping_type=first.grouping_type,  # type: ignore[arg-type]
        grouping_confidence_bucket=first.grouping_confidence_bucket,  # type: ignore[arg-type]
        grouping_reason_summary=first.grouping_reason_summary,
        candidate_count=len(candidates),
        candidates=candidates,
    )


def _fingerprint_distance_score(distance: int, max_distance: int) -> float:
    bounded = max(0, min(distance, max_distance))
    return round((max_distance - bounded) / max_distance, 4)


def _bucket_for_match_score(score: float) -> Literal["very_high", "high", "medium", "low", "very_low"]:
    if score >= 0.9:
        return "very_high"
    if score >= 0.72:
        return "high"
    if score >= 0.45:
        return "medium"
    if score >= 0.2:
        return "low"
    return "very_low"


def _match_candidate_signature(
    *,
    source_cover_image_id: int,
    candidate_cover_image_id: int,
    candidate_type: str,
) -> tuple[int, int, str, str]:
    return (
        source_cover_image_id,
        candidate_cover_image_id,
        candidate_type,
        MATCH_CANDIDATE_EXTRACTION_VERSION,
    )


def _cover_match_candidate_count_by_cover_id(
    session: Session,
    cover_image_ids: list[int],
) -> dict[int, int]:
    if not cover_image_ids:
        return {}
    rows = session.exec(
        select(
            CoverImageMatchCandidate.source_cover_image_id,
            func.count(CoverImageMatchCandidate.id),
        )
        .where(CoverImageMatchCandidate.source_cover_image_id.in_(cover_image_ids))
        .group_by(CoverImageMatchCandidate.source_cover_image_id)
    ).all()
    return {int(cover_id): int(count) for cover_id, count in rows}


def _open_cover_match_candidate_count_by_cover_id(
    session: Session,
    cover_image_ids: list[int],
) -> dict[int, int]:
    if not cover_image_ids:
        return {}
    rows = session.exec(
        select(
            CoverImageMatchCandidate.source_cover_image_id,
            func.count(CoverImageMatchCandidate.id),
        )
        .where(
            CoverImageMatchCandidate.source_cover_image_id.in_(cover_image_ids),
            CoverImageMatchCandidate.dismissed_at.is_(None),
            CoverImageMatchCandidate.acknowledged_at.is_(None),
        )
        .group_by(CoverImageMatchCandidate.source_cover_image_id)
    ).all()
    return {int(cover_id): int(count) for cover_id, count in rows}


def _selected_ocr_candidates_for_matching(
    rows: list[CoverImageOcrCandidate],
) -> dict[int, dict[str, dict[str, object]]]:
    selected_rows_by_cover: dict[int, dict[str, CoverImageOcrCandidate]] = defaultdict(dict)
    for row in rows:
        if not _candidate_is_reconciliation_ready(row):
            continue
        if row.candidate_type not in {"title", "issue_number", "publisher"}:
            continue
        current = selected_rows_by_cover[row.cover_image_id].get(row.candidate_type)
        if current is None or _candidate_selection_sort_key(row) > _candidate_selection_sort_key(current):
            selected_rows_by_cover[row.cover_image_id][row.candidate_type] = row
    normalized: dict[int, dict[str, dict[str, object]]] = {}
    for cover_id, grouped in selected_rows_by_cover.items():
        payload: dict[str, dict[str, object]] = {}
        for candidate_type, row in grouped.items():
            preferred = _preferred_candidate_value(row)
            if preferred is None:
                continue
            raw_value = preferred.strip()
            normalized_value = (
                _normalize_reconciliation_issue_number(raw_value)
                if candidate_type == "issue_number"
                else _normalize_reconciliation_text(raw_value)
            )
            if normalized_value is None:
                continue
            payload[candidate_type] = {
                "raw": raw_value,
                "normalized": normalized_value,
                "review_status": row.review_status,
                "confidence_score": row.confidence_score,
            }
        if payload:
            normalized[cover_id] = payload
    return normalized


def _barcode_facts_for_cover(rows: list[CoverImageBarcodeCandidate]) -> dict[int, dict[str, object]]:
    out: dict[int, dict[str, object]] = defaultdict(
        lambda: {
            "approved_barcodes": set(),
            "malformed_values": [],
        }
    )
    for row in rows:
        if row.review_state == "rejected":
            continue
        value = (row.normalized_upc_value or "").strip()
        if value:
            approved = out[row.cover_image_id]["approved_barcodes"]
            assert isinstance(approved, set)
            approved.add(value)
        elif row.barcode_type == "unknown" or not (row.raw_barcode_value or "").strip().isdigit():
            malformed = out[row.cover_image_id]["malformed_values"]
            assert isinstance(malformed, list)
            malformed.append((row.raw_barcode_value or "").strip() or "unknown")
    return out


def _fingerprints_for_cover(rows: list[CoverImageFingerprint]) -> dict[int, dict[str, CoverImageFingerprint]]:
    out: dict[int, dict[str, CoverImageFingerprint]] = defaultdict(dict)
    for row in rows:
        out[row.cover_image_id][row.fingerprint_type] = row
    return out


def _quality_rows_for_cover(
    rows: list[CoverImageOcrQualityAnalysis],
) -> dict[int, list[CoverImageOcrQualityAnalysis]]:
    latest_by_cover: dict[int, dict[str, CoverImageOcrQualityAnalysis]] = defaultdict(dict)
    for row in rows:
        current = latest_by_cover[row.cover_image_id].get(row.quality_type)
        if current is None or (row.updated_at, row.id or -1) > (current.updated_at, current.id or -1):
            latest_by_cover[row.cover_image_id][row.quality_type] = row
    return {
        cover_id: sorted(grouped.values(), key=lambda item: (item.quality_type, item.id or -1))
        for cover_id, grouped in latest_by_cover.items()
    }


def _open_warning_rows_for_cover(
    rows: list[CoverImageOcrReconciliationWarning],
) -> dict[int, list[CoverImageOcrReconciliationWarning]]:
    out: dict[int, list[CoverImageOcrReconciliationWarning]] = defaultdict(list)
    for row in rows:
        if row.status == "open":
            out[row.cover_image_id].append(row)
    return out


def _signal_entry(
    *,
    signal: str,
    label: str,
    weight: float,
    detail: str,
    value: object | None = None,
) -> dict[str, object]:
    payload = {
        "signal": signal,
        "label": label,
        "weight": round(weight, 4),
        "detail": detail,
    }
    if value is not None:
        payload["value"] = value
    return payload


def _dedupe_sorted_strs(values: list[str]) -> list[str]:
    return sorted({value for value in values if value})


def _clamp_normalized_confidence(score: float) -> float:
    return round(max(0.0, min(1.0, score)), 4)


def _build_fingerprint_signals(
    left: dict[str, CoverImageFingerprint],
    right: dict[str, CoverImageFingerprint],
) -> dict[str, object]:
    positive = 0.0
    contributing_signals: list[dict[str, object]] = []
    matched_signals: dict[str, object] = {}
    matched_fields: list[str] = []
    failed_fields: list[str] = []
    hard_flags: dict[str, object] = {}
    weak_flags: dict[str, object] = {}
    thresholds = {
        "phash": ((0.94, 0.22, True), (0.88, 0.16, False), (0.8, 0.1, False)),
        "ahash": ((0.92, 0.08, False), (0.86, 0.05, False)),
        "dhash": ((0.92, 0.08, False), (0.86, 0.05, False)),
    }

    for fingerprint_type in ("phash", "ahash", "dhash"):
        left_row = left.get(fingerprint_type)
        right_row = right.get(fingerprint_type)
        if left_row is None or right_row is None:
            continue
        distance = hamming_distance_hex(left_row.fingerprint_value, right_row.fingerprint_value)
        similarity = _fingerprint_distance_score(distance, len(left_row.fingerprint_value) * 4)
        matched_signals[f"{fingerprint_type}_distance"] = distance
        matched_signals[f"{fingerprint_type}_similarity"] = similarity
        applied = False
        for threshold, weight, is_hard in thresholds[fingerprint_type]:
            if similarity >= threshold:
                positive += weight
                entry = _signal_entry(
                    signal=f"{fingerprint_type}_similarity",
                    label=f"{fingerprint_type.upper()} similarity",
                    weight=weight,
                    detail=f"Hamming similarity {similarity:.2f} (distance {distance}).",
                    value={"distance": distance, "similarity": similarity},
                )
                contributing_signals.append(entry)
                matched_fields.append(fingerprint_type)
                if is_hard:
                    hard_flags[f"{fingerprint_type}_similarity"] = similarity
                else:
                    weak_flags[f"{fingerprint_type}_similarity"] = similarity
                applied = True
                break
        if not applied:
            failed_fields.append(f"{fingerprint_type}_similarity")

    return {
        "positive_score": round(positive, 4),
        "contributing_signals": contributing_signals,
        "matched_signals": matched_signals,
        "matched_fields": _dedupe_sorted_strs(matched_fields),
        "failed_fields": _dedupe_sorted_strs(failed_fields),
        "hard_flags": hard_flags,
        "weak_flags": weak_flags,
    }


def _build_ocr_match_signals(
    left: dict[str, dict[str, object]] | None,
    right: dict[str, dict[str, object]] | None,
) -> dict[str, object]:
    if not left or not right:
        return {
            "positive_score": 0.0,
            "contributing_signals": [],
            "matched_signals": {},
            "matched_fields": [],
            "failed_fields": [],
            "hard_flags": {},
            "weak_flags": {},
        }

    positive = 0.0
    contributing_signals: list[dict[str, object]] = []
    matched_signals: dict[str, object] = {}
    matched_fields: list[str] = []
    failed_fields: list[str] = []
    hard_flags: dict[str, object] = {}
    weak_flags: dict[str, object] = {}

    left_title = left.get("title")
    right_title = right.get("title")
    if left_title is not None and right_title is not None:
        left_raw = str(left_title.get("raw") or "").strip()
        right_raw = str(right_title.get("raw") or "").strip()
        left_norm = str(left_title.get("normalized") or "").strip()
        right_norm = str(right_title.get("normalized") or "").strip()
        if left_raw and right_raw and left_raw == right_raw:
            positive += 0.16
            contributing_signals.append(
                _signal_entry(
                    signal="ocr_title_exact_match",
                    label="Exact OCR title match",
                    weight=0.16,
                    detail="Selected OCR title candidates match exactly.",
                    value=left_raw,
                )
            )
            matched_fields.append("title")
            hard_flags["ocr_title_exact_match"] = True
            matched_signals["title_exact_match"] = True
        if left_norm and right_norm and left_norm == right_norm:
            positive += 0.08
            contributing_signals.append(
                _signal_entry(
                    signal="ocr_title_normalized_match",
                    label="Normalized OCR title match",
                    weight=0.08,
                    detail="Selected OCR title candidates normalize to the same value.",
                    value=left_norm,
                )
            )
            matched_fields.append("title")
            weak_flags["ocr_title_normalized_match"] = True
            matched_signals["title_normalized_match"] = True
        elif left_norm and right_norm:
            failed_fields.append("title")

    for field_name, weight, label in (
        ("issue_number", 0.16, "Exact OCR issue match"),
        ("publisher", 0.08, "Exact OCR publisher match"),
    ):
        left_payload = left.get(field_name)
        right_payload = right.get(field_name)
        if left_payload is None or right_payload is None:
            continue
        left_norm = str(left_payload.get("normalized") or "").strip()
        right_norm = str(right_payload.get("normalized") or "").strip()
        if left_norm and right_norm and left_norm == right_norm:
            positive += weight
            contributing_signals.append(
                _signal_entry(
                    signal=f"ocr_{field_name}_exact_match",
                    label=label,
                    weight=weight,
                    detail=f"Selected OCR {field_name.replace('_', ' ')} candidates match.",
                    value=left_norm,
                )
            )
            matched_fields.append(field_name)
            hard_flags[f"ocr_{field_name}_exact_match"] = True
            matched_signals[f"{field_name}_match"] = True
        elif left_norm and right_norm:
            failed_fields.append(field_name)

    return {
        "positive_score": round(positive, 4),
        "contributing_signals": contributing_signals,
        "matched_signals": matched_signals,
        "matched_fields": _dedupe_sorted_strs(matched_fields),
        "failed_fields": _dedupe_sorted_strs(failed_fields),
        "hard_flags": hard_flags,
        "weak_flags": weak_flags,
    }


def _build_barcode_match_signals(
    left: dict[str, object] | None,
    right: dict[str, object] | None,
) -> dict[str, object]:
    left_barcodes = set(left.get("approved_barcodes", set())) if left is not None else set()
    right_barcodes = set(right.get("approved_barcodes", set())) if right is not None else set()
    matches = sorted(left_barcodes & right_barcodes)
    if not matches:
        return {
            "positive_score": 0.0,
            "contributing_signals": [],
            "matched_signals": {},
            "matched_fields": [],
            "failed_fields": ["barcode"] if left_barcodes and right_barcodes else [],
            "hard_flags": {},
            "weak_flags": {},
        }

    return {
        "positive_score": 0.72,
        "contributing_signals": [
            _signal_entry(
                signal="barcode_exact_match",
                label="Exact UPC match",
                weight=0.72,
                detail="Approved barcode candidates overlap exactly.",
                value=matches,
            )
        ],
        "matched_signals": {"barcode_matches": matches},
        "matched_fields": ["barcode"],
        "failed_fields": [],
        "hard_flags": {"barcode_exact_match": matches},
        "weak_flags": {},
    }


def _quality_penalties_for_cover(
    *,
    cover_label: str,
    rows: list[CoverImageOcrQualityAnalysis],
) -> list[dict[str, object]]:
    penalties: list[dict[str, object]] = []
    for row in rows:
        if row.severity not in {"warning", "critical"}:
            continue
        if row.quality_type == "unreadable_ocr":
            weight = 0.22 if row.severity == "critical" else 0.12
        elif row.quality_type == "overall_quality":
            weight = 0.16 if row.severity == "critical" else 0.08
        else:
            weight = 0.08 if row.severity == "critical" else 0.04
        penalties.append(
            _signal_entry(
                signal=f"{cover_label}_{row.quality_type}_penalty",
                label=f"{cover_label.title()} OCR quality penalty",
                weight=-weight,
                detail=(
                    f"{cover_label.title()} cover quality flagged {row.quality_type.replace('_', ' ')} "
                    f"with {row.severity} severity."
                ),
                value={"quality_type": row.quality_type, "severity": row.severity},
            )
        )
    return penalties


def _warning_penalties_for_cover(
    *,
    cover_label: str,
    rows: list[CoverImageOcrReconciliationWarning],
    matched_fields: list[str],
) -> list[dict[str, object]]:
    penalties: list[dict[str, object]] = []
    relevant_types = {
        "title": {"title_mismatch", "missing_metadata", "low_confidence_candidate"},
        "issue_number": {"issue_number_mismatch", "missing_metadata", "low_confidence_candidate"},
        "publisher": {"publisher_mismatch", "missing_metadata", "low_confidence_candidate"},
        "barcode": {"barcode_present", "low_confidence_candidate"},
    }
    relevant_warning_types = set().union(*(relevant_types.get(field, set()) for field in matched_fields))
    for row in rows:
        if row.warning_type not in relevant_warning_types:
            continue
        if row.severity == "critical":
            weight = 0.16
        elif row.severity == "warning":
            weight = 0.08
        else:
            weight = 0.04
        penalties.append(
            _signal_entry(
                signal=f"{cover_label}_{row.warning_type}_penalty",
                label=f"{cover_label.title()} reconciliation warning penalty",
                weight=-weight,
                detail=row.message,
                value={"warning_type": row.warning_type, "severity": row.severity},
            )
        )
    return penalties


def _barcode_malformed_penalties(
    *,
    cover_label: str,
    facts: dict[str, object] | None,
) -> list[dict[str, object]]:
    if facts is None:
        return []
    malformed_values = list(facts.get("malformed_values") or [])
    if not malformed_values:
        return []
    return [
        _signal_entry(
            signal=f"{cover_label}_barcode_malformed_penalty",
            label=f"{cover_label.title()} malformed barcode penalty",
            weight=-0.08,
            detail=f"{cover_label.title()} cover has malformed barcode candidates that reduce trust.",
            value=malformed_values[:5],
        )
    ]


def _confidence_summary(
    *,
    contributing_signals: list[dict[str, object]],
    penalties: list[dict[str, object]],
) -> str:
    signal_labels = [str(item["label"]) for item in contributing_signals[:3]]
    penalty_labels = [str(item["label"]) for item in penalties[:2]]
    if signal_labels and penalty_labels:
        return f"Signals: {', '.join(signal_labels)}. Penalties: {', '.join(penalty_labels)}."
    if signal_labels:
        return f"Signals: {', '.join(signal_labels)}. No penalties applied."
    if penalty_labels:
        return f"No positive signals survived scoring. Penalties: {', '.join(penalty_labels)}."
    return "No deterministic confidence signals were recorded."


def _compose_match_confidence_spec(
    *,
    source_cover_image_id: int,
    candidate_cover_image_id: int,
    candidate_type: str,
    signal_bundle: dict[str, object],
    source_barcode_facts: dict[str, object] | None,
    candidate_barcode_facts: dict[str, object] | None,
    source_quality_rows: list[CoverImageOcrQualityAnalysis],
    candidate_quality_rows: list[CoverImageOcrQualityAnalysis],
    source_warning_rows: list[CoverImageOcrReconciliationWarning],
    candidate_warning_rows: list[CoverImageOcrReconciliationWarning],
) -> dict[str, object] | None:
    positive_score = float(signal_bundle["positive_score"])
    if positive_score <= 0:
        return None

    matched_fields = list(signal_bundle["matched_fields"])
    failed_fields = list(signal_bundle["failed_fields"])
    penalties: list[dict[str, object]] = []

    if candidate_type in {"barcode_similarity", "combined_similarity"}:
        penalties.extend(_barcode_malformed_penalties(cover_label="source", facts=source_barcode_facts))
        penalties.extend(_barcode_malformed_penalties(cover_label="candidate", facts=candidate_barcode_facts))
    if candidate_type in {"ocr_similarity", "combined_similarity"}:
        penalties.extend(_quality_penalties_for_cover(cover_label="source", rows=source_quality_rows))
        penalties.extend(_quality_penalties_for_cover(cover_label="candidate", rows=candidate_quality_rows))
        penalties.extend(
            _warning_penalties_for_cover(
                cover_label="source",
                rows=source_warning_rows,
                matched_fields=matched_fields,
            )
        )
        penalties.extend(
            _warning_penalties_for_cover(
                cover_label="candidate",
                rows=candidate_warning_rows,
                matched_fields=matched_fields,
            )
        )

    penalty_total = round(sum(abs(float(item["weight"])) for item in penalties), 4)
    normalized_score = _clamp_normalized_confidence(positive_score - penalty_total)
    breakdown = {
        "contributing_signals": list(signal_bundle["contributing_signals"]),
        "penalties": penalties,
        "matched_fields": _dedupe_sorted_strs(matched_fields),
        "failed_fields": _dedupe_sorted_strs(failed_fields),
        "positive_score_total": round(positive_score, 4),
        "penalty_total": penalty_total,
        "confidence_explanation_summary": _confidence_summary(
            contributing_signals=list(signal_bundle["contributing_signals"]),
            penalties=penalties,
        ),
    }
    matched_signals = dict(signal_bundle["matched_signals"])
    matched_signals["confidence_summary"] = breakdown["confidence_explanation_summary"]

    return {
        "source_cover_image_id": source_cover_image_id,
        "candidate_cover_image_id": candidate_cover_image_id,
        "candidate_type": candidate_type,
        "deterministic_score": round(positive_score, 4),
        "normalized_confidence_score": normalized_score,
        "confidence_version": MATCH_CANDIDATE_CONFIDENCE_VERSION,
        "matched_signals": matched_signals,
        "scoring_breakdown_json": breakdown,
        "matched_signal_count": len(list(signal_bundle["contributing_signals"])),
        "hard_match_flags_json": dict(signal_bundle["hard_flags"]),
        "weak_signal_flags_json": dict(signal_bundle["weak_flags"]),
    }


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _ocr_identity_tokens(
    source_ocr: dict[str, dict[str, object]] | None,
    candidate_ocr: dict[str, dict[str, object]] | None,
) -> list[str]:
    if not source_ocr or not candidate_ocr:
        return []
    tokens: list[str] = []
    for field_name in ("title", "issue_number", "publisher"):
        left = str((source_ocr.get(field_name) or {}).get("normalized") or "").strip().lower()
        right = str((candidate_ocr.get(field_name) or {}).get("normalized") or "").strip().lower()
        if left and right and left == right:
            tokens.append(f"{field_name}:{left}")
    return tokens


def _shared_approved_barcodes(
    source_barcode_facts: dict[str, object] | None,
    candidate_barcode_facts: dict[str, object] | None,
) -> list[str]:
    left = set(source_barcode_facts.get("approved_barcodes", set())) if source_barcode_facts is not None else set()
    right = set(candidate_barcode_facts.get("approved_barcodes", set())) if candidate_barcode_facts is not None else set()
    return sorted(str(value) for value in (left & right))


def _barcode_uniqueness_state(
    *,
    shared_barcodes: list[str],
    source_barcode_facts: dict[str, object] | None,
    candidate_barcode_facts: dict[str, object] | None,
) -> str:
    if not shared_barcodes:
        return "none"
    left_count = len(set(source_barcode_facts.get("approved_barcodes", set()))) if source_barcode_facts else 0
    right_count = len(set(candidate_barcode_facts.get("approved_barcodes", set()))) if candidate_barcode_facts else 0
    if len(shared_barcodes) == 1 and left_count == 1 and right_count == 1:
        return "unique_shared"
    if len(shared_barcodes) == 1:
        return "shared_with_other_barcodes"
    return "multiple_shared"


def _fingerprint_similarity_metrics(matched_signals: dict[str, object]) -> dict[str, float]:
    values = {
        "phash": _safe_float(matched_signals.get("phash_similarity")),
        "ahash": _safe_float(matched_signals.get("ahash_similarity")),
        "dhash": _safe_float(matched_signals.get("dhash_similarity")),
    }
    present = [value for value in values.values() if value > 0]
    values["max"] = max(present) if present else 0.0
    values["avg"] = round(sum(present) / len(present), 4) if present else 0.0
    return values


def _quantize_fingerprint_grouping_slices(metrics: dict[str, float]) -> list[str]:
    """Quantized pHash / max / average slices for deterministic grouping keys."""
    return sorted(
        [
            f"ph:{round(metrics['phash'], 6)}",
            f"mx:{round(metrics['max'], 6)}",
            f"avg:{round(metrics['avg'], 6)}",
        ]
    )


def _grouping_fp_strong(metrics: dict[str, float]) -> bool:
    return metrics["phash"] >= MATCH_GROUP_FP_STRONG_PHASH or metrics["max"] >= MATCH_GROUP_FP_STRONG_MAX


def _grouping_fp_moderate(metrics: dict[str, float]) -> bool:
    return metrics["phash"] >= MATCH_GROUP_FP_MODERATE_PHASH or metrics["max"] >= MATCH_GROUP_FP_MODERATE_MAX


def _grouping_fp_near_identical(metrics: dict[str, float]) -> bool:
    return (
        metrics["phash"] >= MATCH_GROUP_FP_NEAR_IDENTICAL_PHASH
        or metrics["avg"] >= MATCH_GROUP_FP_NEAR_IDENTICAL_AVG
    )


def _grouping_fp_divergent(metrics: dict[str, float]) -> bool:
    return metrics["max"] > 0 and metrics["max"] < MATCH_GROUP_FP_DIVERGENT_UPPER


def _ranking_conflicts_and_missing(
    *,
    shared_barcodes: list[str],
    hard_flags: dict[str, object],
    matched_signals: dict[str, object],
    breakdown: dict[str, object],
) -> tuple[list[str], list[str]]:
    conflicts = sorted(
        {
            *[
                f"failed:{str(field)}"
                for field in (breakdown.get("failed_fields") or [])
                if str(field).strip()
            ],
            *[
                f"penalty:{str(item.get('label') or item.get('signal') or 'penalty')}"
                for item in (breakdown.get("penalties") or [])
                if isinstance(item, dict)
            ],
        }
    )
    missing: list[str] = []
    if not shared_barcodes:
        missing.append("barcode_exact_match")
    if "phash_similarity" not in matched_signals:
        missing.append("phash_similarity")
    if not bool(hard_flags.get("ocr_title_exact_match")):
        missing.append("ocr_title_exact_match")
    if not bool(hard_flags.get("ocr_issue_number_exact_match")):
        missing.append("ocr_issue_number_exact_match")
    if not bool(hard_flags.get("ocr_publisher_exact_match")):
        missing.append("ocr_publisher_exact_match")
    return conflicts, missing


def _grouping_key_from_tokens(grouping_type: str, tokens: list[str]) -> str:
    seed = f"{grouping_type}|{'|'.join(tokens)}"
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:20]
    return f"{grouping_type}:{digest}"


def _build_match_grouping_spec(
    *,
    spec: dict[str, object],
    source_ocr: dict[str, dict[str, object]] | None,
    candidate_ocr: dict[str, dict[str, object]] | None,
    source_barcode_facts: dict[str, object] | None,
    candidate_barcode_facts: dict[str, object] | None,
) -> dict[str, object] | None:
    hard_flags = dict(spec["hard_match_flags_json"])
    matched_signals = dict(spec["matched_signals"])
    breakdown = dict(spec["scoring_breakdown_json"])
    shared_barcodes = _shared_approved_barcodes(source_barcode_facts, candidate_barcode_facts)
    barcode_uniqueness = _barcode_uniqueness_state(
        shared_barcodes=shared_barcodes,
        source_barcode_facts=source_barcode_facts,
        candidate_barcode_facts=candidate_barcode_facts,
    )
    fingerprint = _fingerprint_similarity_metrics(matched_signals)
    fp_slices = _quantize_fingerprint_grouping_slices(fingerprint)
    normalized_confidence = _safe_float(spec["normalized_confidence_score"])
    penalty_total = _safe_float(breakdown.get("penalty_total"))
    ocr_identity = _ocr_identity_tokens(source_ocr, candidate_ocr)
    biblio_tokens = sorted(ocr_identity)
    title_exact = bool(hard_flags.get("ocr_title_exact_match"))
    issue_exact = bool(hard_flags.get("ocr_issue_number_exact_match"))
    publisher_exact = bool(hard_flags.get("ocr_publisher_exact_match"))
    strong_fp = _grouping_fp_strong(fingerprint)
    moderate_fp = _grouping_fp_moderate(fingerprint)
    near_identical_fp = _grouping_fp_near_identical(fingerprint)
    divergent_fp = _grouping_fp_divergent(fingerprint)

    grouping_type: str | None = None
    grouping_tokens: list[str] = []
    grouping_score = 0.0
    reason_summary: str | None = None
    grouping_signals: list[dict[str, object]] = []

    barcode_join = "|".join(shared_barcodes)

    # 4) Probable variant family: same deterministic bibliographic identity + divergent image signals.
    if title_exact and issue_exact and divergent_fp and ocr_identity:
        grouping_type = "probable_variant_family"
        grouping_tokens = [*biblio_tokens, *fp_slices]
        grouping_score = _clamp_normalized_confidence(
            max(normalized_confidence, 0.58) + (0.05 if publisher_exact else 0.0)
        )
        reason_summary = (
            "Exact OCR title and issue match, but fingerprint agreement diverges, so this is grouped as a probable variant family."
        )
        grouping_signals = [
            _signal_entry(
                signal="group_variant_family",
                label="Variant-family grouping",
                weight=grouping_score,
                detail=reason_summary,
                value={
                    "biblio_identity": biblio_tokens,
                    "phash_similarity": round(fingerprint["phash"], 4),
                    "max_similarity": round(fingerprint["max"], 4),
                    "quantized_slices": fp_slices,
                },
            )
        ]
    # 1) Probable duplicate scan: shared approved UPC + strong fingerprint agreement (never UPC-alone).
    elif shared_barcodes and strong_fp:
        grouping_type = "probable_duplicate_scan"
        grouping_tokens = ["barcodes", barcode_join, *fp_slices]
        grouping_score = _clamp_normalized_confidence(
            max(normalized_confidence, 0.9) + (0.05 if near_identical_fp else 0.03)
        )
        reason_summary = (
            "Exact normalized UPC match paired with strong fingerprint agreement suggests a probable duplicate scan "
            "(duplicate upload or near-identical cover asset)."
        )
        grouping_signals = [
            _signal_entry(
                signal="group_duplicate_scan",
                label="Duplicate-scan grouping",
                weight=grouping_score,
                detail=reason_summary,
                value={
                    "shared_barcodes": shared_barcodes,
                    "barcode_uniqueness": barcode_uniqueness,
                    "phash_similarity": round(fingerprint["phash"], 4),
                    "max_similarity": round(fingerprint["max"], 4),
                    "quantized_slices": fp_slices,
                },
            )
        ]
    # 2) Probable same cover: image-backed clustering (moderate fingerprint or OCR+strong fingerprint), never UPC-only.
    elif (shared_barcodes and moderate_fp) or (
        title_exact and issue_exact and ocr_identity and strong_fp
    ):
        grouping_type = "probable_same_cover"
        grouping_tokens = (
            ["barcodes", barcode_join, *fp_slices] if shared_barcodes and moderate_fp else [*biblio_tokens, *fp_slices]
        )
        grouping_score = _clamp_normalized_confidence(
            max(normalized_confidence, 0.78) + (0.04 if shared_barcodes else 0.0)
        )
        reason_summary = (
            "Shared UPC plus moderate-or-better fingerprints, or exact OCR bibliographic cues with strong fingerprint "
            "agreement — grouped as probable same cover (broader than duplicate scan)."
        )
        grouping_signals = [
            _signal_entry(
                signal="group_same_cover",
                label="Same-cover grouping",
                weight=grouping_score,
                detail=reason_summary,
                value={
                    "shared_barcodes": shared_barcodes,
                    "biblio_identity": biblio_tokens,
                    "phash_similarity": round(fingerprint["phash"], 4),
                    "max_similarity": round(fingerprint["max"], 4),
                    "quantized_slices": fp_slices,
                },
            )
        ]
    # 3) Probable same issue: bibliographic key only (publisher included when pairwise OCR identity matches).
    elif title_exact and issue_exact and ocr_identity:
        grouping_type = "probable_same_issue"
        grouping_tokens = [*biblio_tokens]
        grouping_score = _clamp_normalized_confidence(max(normalized_confidence, 0.62) - min(penalty_total, 0.08))
        reason_summary = "Exact OCR title and issue cues group these candidates bibliographically as a probable same issue."
        grouping_signals = [
            _signal_entry(
                signal="group_same_issue",
                label="Same-issue grouping",
                weight=grouping_score,
                detail=reason_summary,
                value={"biblio_identity": biblio_tokens, "shared_barcodes": shared_barcodes},
            )
        ]

    if grouping_type is None or not grouping_tokens:
        return None

    conflicts, missing = _ranking_conflicts_and_missing(
        shared_barcodes=shared_barcodes,
        hard_flags=hard_flags,
        matched_signals=matched_signals,
        breakdown=breakdown,
    )
    return {
        "grouping_key": _grouping_key_from_tokens(grouping_type, grouping_tokens),
        "grouping_type": grouping_type,
        "grouping_confidence_bucket": _bucket_for_match_score(grouping_score),
        "grouping_reason_summary": reason_summary,
        "signals": grouping_signals,
        "conflicting_signals": conflicts,
        "missing_signals": missing,
    }


def _ranking_summary(
    *,
    factor_labels: list[str],
    conflict_count: int,
    grouping_reason_summary: str | None,
) -> str:
    if grouping_reason_summary and factor_labels:
        return f"Ranked by {', '.join(factor_labels[:3])}. {grouping_reason_summary}"
    if factor_labels:
        suffix = f" Conflicts: {conflict_count}." if conflict_count else ""
        return f"Ranked by {', '.join(factor_labels[:3])}.{suffix}"
    if grouping_reason_summary:
        return grouping_reason_summary
    return "Rank derived from deterministic confidence, exact-match flags, and penalties."


def _enrich_match_candidate_spec(
    *,
    spec: dict[str, object],
    source_ocr: dict[str, dict[str, object]] | None,
    candidate_ocr: dict[str, dict[str, object]] | None,
    source_barcode_facts: dict[str, object] | None,
    candidate_barcode_facts: dict[str, object] | None,
) -> dict[str, object]:
    breakdown = dict(spec["scoring_breakdown_json"])
    matched_signals = dict(spec["matched_signals"])
    hard_flags = dict(spec["hard_match_flags_json"])
    shared_barcodes = _shared_approved_barcodes(source_barcode_facts, candidate_barcode_facts)
    barcode_uniqueness = _barcode_uniqueness_state(
        shared_barcodes=shared_barcodes,
        source_barcode_facts=source_barcode_facts,
        candidate_barcode_facts=candidate_barcode_facts,
    )
    fingerprint = _fingerprint_similarity_metrics(matched_signals)
    penalty_total = _safe_float(breakdown.get("penalty_total"))
    normalized_confidence = _safe_float(spec["normalized_confidence_score"])
    ranking_factors = [
        _signal_entry(
            signal="ranking_base_confidence",
            label="Base normalized confidence",
            weight=normalized_confidence,
            detail=f"Starting from normalized confidence {normalized_confidence:.0%}.",
            value=normalized_confidence,
        )
    ]
    ranking_score = normalized_confidence

    if shared_barcodes:
        barcode_bonus = 0.08
        ranking_score += barcode_bonus
        ranking_factors.append(
            _signal_entry(
                signal="ranking_barcode_match_bonus",
                label="Exact barcode bonus",
                weight=barcode_bonus,
                detail="Shared approved UPCs increase ranking priority.",
                value=shared_barcodes,
            )
        )
        if barcode_uniqueness == "unique_shared":
            ranking_score += 0.04
            ranking_factors.append(
                _signal_entry(
                    signal="ranking_barcode_uniqueness_bonus",
                    label="Unique barcode bonus",
                    weight=0.04,
                    detail="Both covers have one shared approved UPC, so the barcode evidence is highly specific.",
                    value=shared_barcodes[0],
                )
            )
        elif barcode_uniqueness == "shared_with_other_barcodes":
            ranking_score += 0.02
            ranking_factors.append(
                _signal_entry(
                    signal="ranking_barcode_uniqueness_bonus",
                    label="Specific barcode bonus",
                    weight=0.02,
                    detail="A shared approved UPC is present, but at least one side has additional approved barcodes.",
                    value=shared_barcodes[0],
                )
            )

    if bool(hard_flags.get("ocr_title_exact_match")) and bool(hard_flags.get("ocr_issue_number_exact_match")):
        ranking_score += 0.06
        ranking_factors.append(
            _signal_entry(
                signal="ranking_ocr_identity_bonus",
                label="Exact OCR identity bonus",
                weight=0.06,
                detail="Title and issue number match exactly in OCR review data.",
            )
        )

    if fingerprint["phash"] >= MATCH_GROUP_FP_NEAR_IDENTICAL_PHASH:
        fingerprint_bonus = 0.08
        fingerprint_label = "Near-identical pHash bonus"
    elif fingerprint["phash"] >= MATCH_GROUP_FP_STRONG_PHASH or fingerprint["max"] >= MATCH_GROUP_FP_STRONG_MAX:
        fingerprint_bonus = 0.06
        fingerprint_label = "Strong fingerprint bonus"
    elif fingerprint["phash"] >= MATCH_GROUP_FP_MODERATE_PHASH or fingerprint["max"] >= MATCH_GROUP_FP_MODERATE_MAX:
        fingerprint_bonus = 0.03
        fingerprint_label = "Moderate fingerprint bonus"
    else:
        fingerprint_bonus = 0.0
        fingerprint_label = ""
    if fingerprint_bonus > 0:
        ranking_score += fingerprint_bonus
        ranking_factors.append(
            _signal_entry(
                signal="ranking_fingerprint_bonus",
                label=fingerprint_label,
                weight=fingerprint_bonus,
                detail="Fingerprint agreement increases deterministic rank priority.",
                value={"phash_similarity": round(fingerprint["phash"], 4), "max_similarity": round(fingerprint["max"], 4)},
            )
        )

    if penalty_total >= 0.24:
        ranking_score -= 0.06
        ranking_factors.append(
            _signal_entry(
                signal="ranking_penalty_pressure",
                label="Penalty pressure",
                weight=-0.06,
                detail="Open warnings or OCR quality penalties materially reduce ranking priority.",
                value=round(penalty_total, 4),
            )
        )
    elif penalty_total >= 0.12:
        ranking_score -= 0.03
        ranking_factors.append(
            _signal_entry(
                signal="ranking_penalty_pressure",
                label="Penalty pressure",
                weight=-0.03,
                detail="Moderate penalties reduce ranking priority.",
                value=round(penalty_total, 4),
            )
        )

    grouping = _build_match_grouping_spec(
        spec=spec,
        source_ocr=source_ocr,
        candidate_ocr=candidate_ocr,
        source_barcode_facts=source_barcode_facts,
        candidate_barcode_facts=candidate_barcode_facts,
    )
    conflicts, missing = _ranking_conflicts_and_missing(
        shared_barcodes=shared_barcodes,
        hard_flags=hard_flags,
        matched_signals=matched_signals,
        breakdown=breakdown,
    )
    fingerprint_strength = (
        "near_identical"
        if fingerprint["phash"] >= MATCH_GROUP_FP_NEAR_IDENTICAL_PHASH
        else "strong"
        if fingerprint["phash"] >= MATCH_GROUP_FP_STRONG_PHASH or fingerprint["max"] >= MATCH_GROUP_FP_STRONG_MAX
        else "moderate"
        if fingerprint["phash"] >= MATCH_GROUP_FP_MODERATE_PHASH or fingerprint["max"] >= MATCH_GROUP_FP_MODERATE_MAX
        else "weak"
        if fingerprint["max"] > 0
        else "absent"
    )
    reason_json = {
        "ranking_explanation_summary": _ranking_summary(
            factor_labels=[str(item["label"]) for item in ranking_factors],
            conflict_count=len(conflicts),
            grouping_reason_summary=str(grouping["grouping_reason_summary"]) if grouping is not None else None,
        ),
        "ranking_factors": ranking_factors,
        "conflicting_signals": conflicts,
        "missing_signals": missing,
        "fingerprint_agreement_strength": fingerprint_strength,
        "barcode_uniqueness": barcode_uniqueness,
        "tie_break_values": {
            "normalized_confidence_score": normalized_confidence,
            "matched_signal_count": int(spec["matched_signal_count"]),
            "candidate_cover_image_id": int(spec["candidate_cover_image_id"]),
            "candidate_type": str(spec["candidate_type"]),
        },
    }
    if grouping is not None:
        reason_json["grouping"] = grouping

    enriched = dict(spec)
    enriched["ranking_score"] = _clamp_normalized_confidence(ranking_score)
    enriched["ranking_version"] = MATCH_CANDIDATE_RANKING_VERSION
    enriched["ranking_reason_json"] = reason_json
    enriched["grouping_key"] = grouping["grouping_key"] if grouping is not None else None
    enriched["grouping_type"] = grouping["grouping_type"] if grouping is not None else None
    enriched["grouping_confidence_bucket"] = grouping["grouping_confidence_bucket"] if grouping is not None else None
    enriched["grouping_reason_summary"] = grouping["grouping_reason_summary"] if grouping is not None else None
    return enriched


def _assign_candidate_ranks(specs: list[dict[str, object]]) -> list[dict[str, object]]:
    ranked = sorted(
        specs,
        key=lambda spec: (
            -_safe_float(spec.get("ranking_score")),
            -_safe_float(spec.get("normalized_confidence_score")),
            -int(spec.get("matched_signal_count", 0)),
            int(spec.get("candidate_cover_image_id", 0)),
            str(spec.get("candidate_type", "")),
        ),
    )
    for index, spec in enumerate(ranked, start=1):
        spec["candidate_rank"] = index
    return ranked


def _candidate_specs_for_cover_match(
    *,
    source_cover_image_id: int,
    candidate_cover_image_id: int,
    barcode_signals: dict[str, object],
    fingerprint_signals: dict[str, object],
    ocr_signals: dict[str, object],
    source_barcode_facts: dict[str, object] | None,
    candidate_barcode_facts: dict[str, object] | None,
    source_quality_rows: list[CoverImageOcrQualityAnalysis],
    candidate_quality_rows: list[CoverImageOcrQualityAnalysis],
    source_warning_rows: list[CoverImageOcrReconciliationWarning],
    candidate_warning_rows: list[CoverImageOcrReconciliationWarning],
) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    for candidate_type, bundle in (
        ("barcode_similarity", barcode_signals),
        ("fingerprint_similarity", fingerprint_signals),
        ("ocr_similarity", ocr_signals),
    ):
        spec = _compose_match_confidence_spec(
            source_cover_image_id=source_cover_image_id,
            candidate_cover_image_id=candidate_cover_image_id,
            candidate_type=candidate_type,
            signal_bundle=bundle,
            source_barcode_facts=source_barcode_facts,
            candidate_barcode_facts=candidate_barcode_facts,
            source_quality_rows=source_quality_rows,
            candidate_quality_rows=candidate_quality_rows,
            source_warning_rows=source_warning_rows,
            candidate_warning_rows=candidate_warning_rows,
        )
        if spec is not None:
            specs.append(spec)

    active_signal_types = sum(
        float(bundle["positive_score"]) > 0 for bundle in (barcode_signals, fingerprint_signals, ocr_signals)
    )
    if active_signal_types >= 2:
        combined_bundle = {
            "positive_score": round(
                float(barcode_signals["positive_score"])
                + float(fingerprint_signals["positive_score"])
                + float(ocr_signals["positive_score"]),
                4,
            ),
            "contributing_signals": [
                *list(barcode_signals["contributing_signals"]),
                *list(fingerprint_signals["contributing_signals"]),
                *list(ocr_signals["contributing_signals"]),
            ],
            "matched_signals": {
                **dict(barcode_signals["matched_signals"]),
                **dict(fingerprint_signals["matched_signals"]),
                **dict(ocr_signals["matched_signals"]),
            },
            "matched_fields": _dedupe_sorted_strs(
                list(barcode_signals["matched_fields"])
                + list(fingerprint_signals["matched_fields"])
                + list(ocr_signals["matched_fields"])
            ),
            "failed_fields": _dedupe_sorted_strs(
                list(barcode_signals["failed_fields"])
                + list(fingerprint_signals["failed_fields"])
                + list(ocr_signals["failed_fields"])
            ),
            "hard_flags": {
                **dict(barcode_signals["hard_flags"]),
                **dict(fingerprint_signals["hard_flags"]),
                **dict(ocr_signals["hard_flags"]),
            },
            "weak_flags": {
                **dict(barcode_signals["weak_flags"]),
                **dict(fingerprint_signals["weak_flags"]),
                **dict(ocr_signals["weak_flags"]),
            },
        }
        spec = _compose_match_confidence_spec(
            source_cover_image_id=source_cover_image_id,
            candidate_cover_image_id=candidate_cover_image_id,
            candidate_type="combined_similarity",
            signal_bundle=combined_bundle,
            source_barcode_facts=source_barcode_facts,
            candidate_barcode_facts=candidate_barcode_facts,
            source_quality_rows=source_quality_rows,
            candidate_quality_rows=candidate_quality_rows,
            source_warning_rows=source_warning_rows,
            candidate_warning_rows=candidate_warning_rows,
        )
        if spec is not None:
            specs.append(spec)

    return specs


def get_cover_image_match_candidate_or_404(
    session: Session,
    match_candidate_id: int,
) -> CoverImageMatchCandidate:
    row = session.get(CoverImageMatchCandidate, match_candidate_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Cover match candidate not found")
    return row


def generate_cover_image_match_candidates_for_cover(
    session: Session,
    *,
    cover_image_id: int,
    actor_user_id: int | None = None,
) -> CoverImageMatchCandidateGenerateResponse:
    cover = get_cover_entity_or_404(session, cover_image_id)
    source_cover_id = cover.id
    if source_cover_id is None:
        raise HTTPException(status_code=404, detail="Cover image not found")

    all_cover_ids = session.exec(
        select(CoverImage.id).where(
            or_(
                CoverImage.inventory_copy_id.is_not(None),
                CoverImage.draft_import_id.is_not(None),
            )
        )
    ).all()
    candidate_cover_ids = [int(row_id) for row_id in all_cover_ids if row_id is not None and int(row_id) != source_cover_id]
    if not candidate_cover_ids:
        return CoverImageMatchCandidateGenerateResponse(
            cover_image_id=source_cover_id,
            candidate_count=0,
            candidates=[],
        )

    cover_ids_to_load = [source_cover_id, *candidate_cover_ids]
    fingerprint_rows = session.exec(
        select(CoverImageFingerprint)
        .where(CoverImageFingerprint.cover_image_id.in_(cover_ids_to_load))
        .order_by(CoverImageFingerprint.cover_image_id.asc(), CoverImageFingerprint.id.asc())
    ).all()
    barcode_rows = session.exec(
        select(CoverImageBarcodeCandidate)
        .where(CoverImageBarcodeCandidate.cover_image_id.in_(cover_ids_to_load))
        .order_by(CoverImageBarcodeCandidate.cover_image_id.asc(), CoverImageBarcodeCandidate.id.asc())
    ).all()
    ocr_rows = session.exec(
        select(CoverImageOcrCandidate)
        .where(CoverImageOcrCandidate.cover_image_id.in_(cover_ids_to_load))
        .order_by(CoverImageOcrCandidate.cover_image_id.asc(), CoverImageOcrCandidate.id.asc())
    ).all()
    quality_rows = session.exec(
        select(CoverImageOcrQualityAnalysis)
        .where(CoverImageOcrQualityAnalysis.cover_image_id.in_(cover_ids_to_load))
        .order_by(CoverImageOcrQualityAnalysis.cover_image_id.asc(), CoverImageOcrQualityAnalysis.id.asc())
    ).all()
    warning_rows = session.exec(
        select(CoverImageOcrReconciliationWarning)
        .where(CoverImageOcrReconciliationWarning.cover_image_id.in_(cover_ids_to_load))
        .order_by(CoverImageOcrReconciliationWarning.cover_image_id.asc(), CoverImageOcrReconciliationWarning.id.asc())
    ).all()

    fingerprints_by_cover = _fingerprints_for_cover(fingerprint_rows)
    barcodes_by_cover = _barcode_facts_for_cover(barcode_rows)
    ocr_by_cover = _selected_ocr_candidates_for_matching(ocr_rows)
    quality_by_cover = _quality_rows_for_cover(quality_rows)
    warnings_by_cover = _open_warning_rows_for_cover(warning_rows)

    source_fingerprints = fingerprints_by_cover.get(source_cover_id, {})
    source_barcodes = barcodes_by_cover.get(source_cover_id)
    source_ocr = ocr_by_cover.get(source_cover_id)
    if not source_fingerprints and not source_barcodes and not source_ocr:
        return CoverImageMatchCandidateGenerateResponse(
            cover_image_id=source_cover_id,
            candidate_count=0,
            candidates=[],
        )

    existing_rows = session.exec(
        select(CoverImageMatchCandidate)
        .where(CoverImageMatchCandidate.source_cover_image_id == source_cover_id)
        .order_by(CoverImageMatchCandidate.id.asc())
    ).all()
    existing_by_signature = {
        _match_candidate_signature(
            source_cover_image_id=row.source_cover_image_id,
            candidate_cover_image_id=row.candidate_cover_image_id,
            candidate_type=row.candidate_type,
        ): row
        for row in existing_rows
    }

    now = _processing_now()
    desired_signatures: set[tuple[int, int, str, str]] = set()
    pending_specs: list[dict[str, object]] = []
    for candidate_cover_id in candidate_cover_ids:
        barcode_signals = _build_barcode_match_signals(
            source_barcodes,
            barcodes_by_cover.get(candidate_cover_id),
        )
        fingerprint_signals = _build_fingerprint_signals(
            source_fingerprints,
            fingerprints_by_cover.get(candidate_cover_id, {}),
        )
        ocr_signals = _build_ocr_match_signals(source_ocr, ocr_by_cover.get(candidate_cover_id))
        specs = _candidate_specs_for_cover_match(
            source_cover_image_id=source_cover_id,
            candidate_cover_image_id=candidate_cover_id,
            barcode_signals=barcode_signals,
            fingerprint_signals=fingerprint_signals,
            ocr_signals=ocr_signals,
            source_barcode_facts=source_barcodes,
            candidate_barcode_facts=barcodes_by_cover.get(candidate_cover_id),
            source_quality_rows=quality_by_cover.get(source_cover_id, []),
            candidate_quality_rows=quality_by_cover.get(candidate_cover_id, []),
            source_warning_rows=warnings_by_cover.get(source_cover_id, []),
            candidate_warning_rows=warnings_by_cover.get(candidate_cover_id, []),
        )
        for spec in specs:
            pending_specs.append(
                _enrich_match_candidate_spec(
                    spec=spec,
                    source_ocr=source_ocr,
                    candidate_ocr=ocr_by_cover.get(candidate_cover_id),
                    source_barcode_facts=source_barcodes,
                    candidate_barcode_facts=barcodes_by_cover.get(candidate_cover_id),
                )
            )

    for spec in _assign_candidate_ranks(pending_specs):
        signature = _match_candidate_signature(
            source_cover_image_id=source_cover_id,
            candidate_cover_image_id=int(spec["candidate_cover_image_id"]),
            candidate_type=str(spec["candidate_type"]),
        )
        desired_signatures.add(signature)
        confidence_bucket = _bucket_for_match_score(float(spec["normalized_confidence_score"]))
        matched_signals = dict(spec["matched_signals"])
        row = existing_by_signature.get(signature)
        if row is None:
            row = CoverImageMatchCandidate(
                source_cover_image_id=source_cover_id,
                candidate_cover_image_id=int(spec["candidate_cover_image_id"]),
                candidate_type=str(spec["candidate_type"]),
                confidence_bucket=confidence_bucket,
                deterministic_score=float(spec["deterministic_score"]),
                normalized_confidence_score=float(spec["normalized_confidence_score"]),
                confidence_version=str(spec["confidence_version"]),
                scoring_breakdown_json=dict(spec["scoring_breakdown_json"]),
                matched_signal_count=int(spec["matched_signal_count"]),
                hard_match_flags_json=dict(spec["hard_match_flags_json"]),
                weak_signal_flags_json=dict(spec["weak_signal_flags_json"]),
                ranking_score=float(spec["ranking_score"]),
                ranking_version=str(spec["ranking_version"]),
                ranking_reason_json=dict(spec["ranking_reason_json"]),
                candidate_rank=int(spec["candidate_rank"]),
                grouping_key=str(spec["grouping_key"]) if spec.get("grouping_key") else None,
                grouping_type=str(spec["grouping_type"]) if spec.get("grouping_type") else None,
                grouping_confidence_bucket=(
                    str(spec["grouping_confidence_bucket"])
                    if spec.get("grouping_confidence_bucket")
                    else None
                ),
                grouping_reason_summary=(
                    str(spec["grouping_reason_summary"]) if spec.get("grouping_reason_summary") else None
                ),
                matched_signals=matched_signals,
                extraction_version=MATCH_CANDIDATE_EXTRACTION_VERSION,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.flush()
            record_metadata_audit(
                session,
                entity_type="cover_match_candidate",
                entity_id=row.id,
                action="cover_match_candidate_confidence_generated",
                before_snapshot=None,
                after_snapshot=_match_candidate_snapshot_public(row),
                actor_user_id=actor_user_id,
            )
            existing_by_signature[signature] = row
            continue

        before = _match_candidate_snapshot_public(row)
        changed = (
            row.confidence_bucket != confidence_bucket
            or row.deterministic_score != float(spec["deterministic_score"])
            or row.normalized_confidence_score != float(spec["normalized_confidence_score"])
            or row.confidence_version != str(spec["confidence_version"])
            or (row.scoring_breakdown_json or {}) != dict(spec["scoring_breakdown_json"])
            or row.matched_signal_count != int(spec["matched_signal_count"])
            or (row.hard_match_flags_json or {}) != dict(spec["hard_match_flags_json"])
            or (row.weak_signal_flags_json or {}) != dict(spec["weak_signal_flags_json"])
            or row.ranking_score != float(spec["ranking_score"])
            or row.ranking_version != str(spec["ranking_version"])
            or (row.ranking_reason_json or {}) != dict(spec["ranking_reason_json"])
            or row.candidate_rank != int(spec["candidate_rank"])
            or row.grouping_key != (str(spec["grouping_key"]) if spec.get("grouping_key") else None)
            or row.grouping_type != (str(spec["grouping_type"]) if spec.get("grouping_type") else None)
            or row.grouping_confidence_bucket
            != (str(spec["grouping_confidence_bucket"]) if spec.get("grouping_confidence_bucket") else None)
            or row.grouping_reason_summary
            != (str(spec["grouping_reason_summary"]) if spec.get("grouping_reason_summary") else None)
            or (row.matched_signals or {}) != matched_signals
            or row.extraction_version != MATCH_CANDIDATE_EXTRACTION_VERSION
        )
        row.confidence_bucket = confidence_bucket
        row.deterministic_score = float(spec["deterministic_score"])
        row.normalized_confidence_score = float(spec["normalized_confidence_score"])
        row.confidence_version = str(spec["confidence_version"])
        row.scoring_breakdown_json = dict(spec["scoring_breakdown_json"])
        row.matched_signal_count = int(spec["matched_signal_count"])
        row.hard_match_flags_json = dict(spec["hard_match_flags_json"])
        row.weak_signal_flags_json = dict(spec["weak_signal_flags_json"])
        row.ranking_score = float(spec["ranking_score"])
        row.ranking_version = str(spec["ranking_version"])
        row.ranking_reason_json = dict(spec["ranking_reason_json"])
        row.candidate_rank = int(spec["candidate_rank"])
        row.grouping_key = str(spec["grouping_key"]) if spec.get("grouping_key") else None
        row.grouping_type = str(spec["grouping_type"]) if spec.get("grouping_type") else None
        row.grouping_confidence_bucket = (
            str(spec["grouping_confidence_bucket"]) if spec.get("grouping_confidence_bucket") else None
        )
        row.grouping_reason_summary = (
            str(spec["grouping_reason_summary"]) if spec.get("grouping_reason_summary") else None
        )
        row.matched_signals = matched_signals
        row.extraction_version = MATCH_CANDIDATE_EXTRACTION_VERSION
        row.updated_at = now
        session.add(row)
        if changed:
            session.flush()
            prev_conf = float(before.get("normalized_confidence_score") or 0.0)
            next_conf = row.normalized_confidence_score
            if next_conf > prev_conf:
                action = "cover_match_candidate_confidence_improved"
            elif next_conf < prev_conf:
                action = "cover_match_candidate_confidence_regressed"
            elif before.get("candidate_rank") != row.candidate_rank or before.get("grouping_key") != row.grouping_key:
                action = "cover_match_candidate_ranking_updated"
            else:
                action = "cover_match_candidate_confidence_updated"
            record_metadata_audit(
                session,
                entity_type="cover_match_candidate",
                entity_id=row.id,
                action=action,
                before_snapshot=before,
                after_snapshot=_match_candidate_snapshot_public(row),
                actor_user_id=actor_user_id,
            )

    session.commit()
    candidates = list_cover_match_candidate_reads_for_cover(session, source_cover_id)
    return CoverImageMatchCandidateGenerateResponse(
        cover_image_id=source_cover_id,
        candidate_count=len(candidates),
        candidates=candidates,
    )


def _set_cover_match_candidate_status(
    session: Session,
    *,
    row: CoverImageMatchCandidate,
    action: Literal["acknowledge", "dismiss"],
    actor_user_id: int,
) -> CoverImageMatchCandidateRead:
    before = _match_candidate_snapshot_public(row)
    now = _processing_now()
    if action == "acknowledge":
        row.acknowledged_at = now
        row.dismissed_at = None
    else:
        row.dismissed_at = now
    row.updated_at = now
    session.add(row)
    session.flush()
    record_metadata_audit(
        session,
        entity_type="cover_match_candidate",
        entity_id=row.id,
        action="cover_match_candidate_acknowledged" if action == "acknowledge" else "cover_match_candidate_dismissed",
        before_snapshot=before,
        after_snapshot=_match_candidate_snapshot_public(row),
        actor_user_id=actor_user_id,
    )
    session.commit()
    session.refresh(row)
    return cover_match_candidate_entity_to_read(row)


def generate_cover_image_match_candidates_for_owner(
    session: Session,
    *,
    current_user: User,
    cover_image_id: int,
) -> CoverImageMatchCandidateGenerateResponse:
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )
    return generate_cover_image_match_candidates_for_cover(
        session,
        cover_image_id=cover_image_id,
        actor_user_id=current_user.id,
    )


def generate_cover_image_match_candidates_for_ops(
    session: Session,
    *,
    cover_image_id: int,
    actor_user_id: int,
) -> CoverImageMatchCandidateGenerateResponse:
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=cover_image_id)
    return generate_cover_image_match_candidates_for_cover(
        session,
        cover_image_id=cover_image_id,
        actor_user_id=actor_user_id,
    )


def get_cover_match_group_for_owner(
    session: Session,
    *,
    current_user: User,
    grouping_key: str,
) -> CoverImageMatchGroupRead:
    group = get_cover_match_group(session, grouping_key=grouping_key)
    allowed_candidates: list[CoverImageMatchCandidateRead] = []
    for candidate in group.candidates:
        cover = get_cover_entity_or_404(session, candidate.source_cover_image_id)
        if user_can_download_cover(session, cover, current_user):
            allowed_candidates.append(candidate)
    if not allowed_candidates:
        raise HTTPException(status_code=404, detail="Match group not found")
    return CoverImageMatchGroupRead(
        grouping_key=group.grouping_key,
        grouping_type=group.grouping_type,
        grouping_confidence_bucket=group.grouping_confidence_bucket,
        grouping_reason_summary=group.grouping_reason_summary,
        candidate_count=len(allowed_candidates),
        candidates=allowed_candidates,
    )


def get_cover_match_group_for_ops(
    session: Session,
    *,
    grouping_key: str,
) -> CoverImageMatchGroupRead:
    return get_cover_match_group(session, grouping_key=grouping_key)


def acknowledge_cover_match_candidate_for_owner(
    session: Session,
    *,
    current_user: User,
    match_candidate_id: int,
) -> CoverImageMatchCandidateRead:
    row = get_cover_image_match_candidate_or_404(session, match_candidate_id)
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=row.source_cover_image_id,
    )
    return _set_cover_match_candidate_status(
        session,
        row=row,
        action="acknowledge",
        actor_user_id=current_user.id,
    )


def dismiss_cover_match_candidate_for_owner(
    session: Session,
    *,
    current_user: User,
    match_candidate_id: int,
) -> CoverImageMatchCandidateRead:
    row = get_cover_image_match_candidate_or_404(session, match_candidate_id)
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=row.source_cover_image_id,
    )
    return _set_cover_match_candidate_status(
        session,
        row=row,
        action="dismiss",
        actor_user_id=current_user.id,
    )


def acknowledge_cover_match_candidate_for_ops(
    session: Session,
    *,
    match_candidate_id: int,
    actor_user_id: int,
) -> CoverImageMatchCandidateRead:
    row = get_cover_image_match_candidate_or_404(session, match_candidate_id)
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=row.source_cover_image_id)
    return _set_cover_match_candidate_status(
        session,
        row=row,
        action="acknowledge",
        actor_user_id=actor_user_id,
    )


def dismiss_cover_match_candidate_for_ops(
    session: Session,
    *,
    match_candidate_id: int,
    actor_user_id: int,
) -> CoverImageMatchCandidateRead:
    row = get_cover_image_match_candidate_or_404(session, match_candidate_id)
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=row.source_cover_image_id)
    return _set_cover_match_candidate_status(
        session,
        row=row,
        action="dismiss",
        actor_user_id=actor_user_id,
    )


def get_cover_image_ocr_candidate_or_404(
    session: Session,
    ocr_candidate_id: int,
) -> CoverImageOcrCandidate:
    row = session.get(CoverImageOcrCandidate, ocr_candidate_id)
    if row is None:
        raise HTTPException(status_code=404, detail="OCR candidate not found")
    return row


def _ocr_candidate_review_snapshot_public(row: CoverImageOcrCandidate) -> dict[str, object]:
    return {
        "review_status": row.review_status,
        "review_notes": row.review_notes,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at is not None else None,
        "reviewed_by_user_id": row.reviewed_by_user_id,
        "candidate_type": row.candidate_type,
        "cover_image_id": row.cover_image_id,
    }


def _trim_ocr_candidate_review_notes(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    return trimmed[:OCR_CANDIDATE_REVIEW_NOTES_MAX_CHARS]


def _set_ocr_candidate_review_decision(
    session: Session,
    *,
    row: CoverImageOcrCandidate,
    decision: Literal["approved", "rejected"],
    actor_user_id: int,
) -> CoverImageOcrCandidate:
    before = _ocr_candidate_review_snapshot_public(row)
    row.review_status = decision
    row.reviewed_at = _processing_now()
    row.reviewed_by_user_id = actor_user_id
    session.add(row)
    record_metadata_audit(
        session,
        entity_type="ocr_candidate",
        entity_id=row.id,
        action=f"ocr_candidate_{decision}",
        before_snapshot=before,
        after_snapshot=_ocr_candidate_review_snapshot_public(row),
        actor_user_id=actor_user_id,
    )
    session.commit()
    session.refresh(row)
    return row


def approve_cover_image_ocr_candidate_for_owner(
    session: Session,
    *,
    current_user: User,
    ocr_candidate_id: int,
) -> CoverImageOcrCandidateRead:
    row = get_cover_image_ocr_candidate_or_404(session, ocr_candidate_id)
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=row.cover_image_id,
    )
    _set_ocr_candidate_review_decision(
        session,
        row=row,
        decision="approved",
        actor_user_id=current_user.id,
    )
    return cover_ocr_candidate_entity_to_read(row)


def reject_cover_image_ocr_candidate_for_owner(
    session: Session,
    *,
    current_user: User,
    ocr_candidate_id: int,
) -> CoverImageOcrCandidateRead:
    row = get_cover_image_ocr_candidate_or_404(session, ocr_candidate_id)
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=row.cover_image_id,
    )
    _set_ocr_candidate_review_decision(
        session,
        row=row,
        decision="rejected",
        actor_user_id=current_user.id,
    )
    return cover_ocr_candidate_entity_to_read(row)


def patch_cover_image_ocr_candidate_review_notes_for_owner(
    session: Session,
    *,
    current_user: User,
    ocr_candidate_id: int,
    review_notes: str | None,
) -> CoverImageOcrCandidateRead:
    row = get_cover_image_ocr_candidate_or_404(session, ocr_candidate_id)
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=row.cover_image_id,
    )
    before = _ocr_candidate_review_snapshot_public(row)
    row.review_notes = _trim_ocr_candidate_review_notes(review_notes)
    row.reviewed_at = _processing_now()
    row.reviewed_by_user_id = current_user.id
    session.add(row)
    record_metadata_audit(
        session,
        entity_type="ocr_candidate",
        entity_id=row.id,
        action="ocr_candidate_review_notes_updated",
        before_snapshot=before,
        after_snapshot=_ocr_candidate_review_snapshot_public(row),
        actor_user_id=current_user.id,
    )
    session.commit()
    session.refresh(row)
    return cover_ocr_candidate_entity_to_read(row)


def approve_cover_image_ocr_candidate_for_ops(
    session: Session,
    *,
    ocr_candidate_id: int,
    actor_user_id: int,
) -> CoverImageOcrCandidateRead:
    row = get_cover_image_ocr_candidate_or_404(session, ocr_candidate_id)
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=row.cover_image_id)
    _set_ocr_candidate_review_decision(
        session,
        row=row,
        decision="approved",
        actor_user_id=actor_user_id,
    )
    return cover_ocr_candidate_entity_to_read(row)


def reject_cover_image_ocr_candidate_for_ops(
    session: Session,
    *,
    ocr_candidate_id: int,
    actor_user_id: int,
) -> CoverImageOcrCandidateRead:
    row = get_cover_image_ocr_candidate_or_404(session, ocr_candidate_id)
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=row.cover_image_id)
    _set_ocr_candidate_review_decision(
        session,
        row=row,
        decision="rejected",
        actor_user_id=actor_user_id,
    )
    return cover_ocr_candidate_entity_to_read(row)


def patch_cover_image_ocr_candidate_review_notes_for_ops(
    session: Session,
    *,
    ocr_candidate_id: int,
    review_notes: str | None,
    actor_user_id: int,
) -> CoverImageOcrCandidateRead:
    row = get_cover_image_ocr_candidate_or_404(session, ocr_candidate_id)
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=row.cover_image_id)
    before = _ocr_candidate_review_snapshot_public(row)
    row.review_notes = _trim_ocr_candidate_review_notes(review_notes)
    row.reviewed_at = _processing_now()
    row.reviewed_by_user_id = actor_user_id
    session.add(row)
    record_metadata_audit(
        session,
        entity_type="ocr_candidate",
        entity_id=row.id,
        action="ocr_candidate_review_notes_updated",
        before_snapshot=before,
        after_snapshot=_ocr_candidate_review_snapshot_public(row),
        actor_user_id=actor_user_id,
    )
    session.commit()
    session.refresh(row)
    return cover_ocr_candidate_entity_to_read(row)


def _normalize_reconciliation_text(value: str | None) -> str | None:
    if value is None:
        return None
    compact = re.sub(r"[^A-Z0-9]+", " ", value.upper()).strip()
    return compact or None


def _normalize_reconciliation_issue_number(value: str | None) -> str | None:
    if value is None:
        return None
    compact = value.strip().upper()
    if not compact:
        return None
    compact = compact.replace("ISSUE", "").replace("#", "").replace(" ", "")
    compact = re.sub(r"[^A-Z0-9]+", "", compact)
    if not compact:
        return None
    if compact.isdigit():
        return str(int(compact))
    return compact


def _preferred_candidate_value(row: CoverImageOcrCandidate) -> str | None:
    value = (row.normalized_candidate_text or row.raw_candidate_text or "").strip()
    return value or None


def _candidate_is_reconciliation_ready(row: CoverImageOcrCandidate) -> bool:
    if row.review_status == "rejected":
        return False
    value = _preferred_candidate_value(row)
    if value is None:
        return False
    if row.candidate_type == "issue_number":
        return _normalize_reconciliation_issue_number(value) is not None
    if row.candidate_type in {"title", "publisher", "barcode"}:
        return _normalize_reconciliation_text(value) is not None
    return False


def _candidate_selection_sort_key(row: CoverImageOcrCandidate) -> tuple[int, float, int]:
    review_weight = 2 if row.review_status == "approved" else 1
    confidence = row.confidence_score if row.confidence_score is not None else -1.0
    row_id = row.id if row.id is not None else -1
    return (review_weight, confidence, row_id)


def _selected_ocr_candidates_for_reconciliation(
    rows: list[CoverImageOcrCandidate],
) -> dict[str, CoverImageOcrCandidate]:
    selected: dict[str, CoverImageOcrCandidate] = {}
    for row in rows:
        if not _candidate_is_reconciliation_ready(row):
            continue
        current = selected.get(row.candidate_type)
        if current is None or _candidate_selection_sort_key(row) > _candidate_selection_sort_key(current):
            selected[row.candidate_type] = row
    return selected


def _current_metadata_for_inventory_cover(
    session: Session,
    cover: CoverImage,
) -> dict[str, str | int | None] | None:
    if cover.inventory_copy_id is None:
        return None
    row = session.exec(
        select(
            InventoryCopy.id.label("inventory_copy_id"),
            ComicTitle.name.label("title"),
            Publisher.name.label("publisher"),
            ComicIssue.issue_number.label("issue_number"),
        )
        .join(Variant, InventoryCopy.variant_id == Variant.id)
        .join(ComicIssue, Variant.comic_issue_id == ComicIssue.id)
        .join(ComicTitle, ComicIssue.comic_title_id == ComicTitle.id)
        .join(Publisher, ComicTitle.publisher_id == Publisher.id)
        .where(InventoryCopy.id == cover.inventory_copy_id)
    ).first()
    if row is None:
        return None
    return {
        "inventory_copy_id": row.inventory_copy_id,
        "title": (row.title or "").strip() or None,
        "publisher": (row.publisher or "").strip() or None,
        "issue_number": (row.issue_number or "").strip() or None,
    }


def _current_metadata_for_draft_cover(
    session: Session,
    cover: CoverImage,
) -> dict[str, str | int | None] | None:
    if cover.draft_import_id is None:
        return None
    draft = session.get(DraftImport, cover.draft_import_id)
    if draft is None:
        return None
    parsed = ParseOrderResponse.model_validate(draft.parsed_payload_json)
    if len(parsed.items) != 1:
        return None
    item = parsed.items[0]
    title = (item.canonical_title or item.title or "").strip() or None
    publisher = (item.canonical_publisher or item.publisher or "").strip() or None
    issue_number = (item.canonical_issue_number or item.issue_number or "").strip() or None
    if title is None and publisher is None and issue_number is None:
        return None
    return {
        "inventory_copy_id": None,
        "title": title,
        "publisher": publisher,
        "issue_number": issue_number,
    }


def _current_metadata_for_cover(
    session: Session,
    cover: CoverImage,
) -> dict[str, str | int | None] | None:
    return _current_metadata_for_inventory_cover(session, cover) or _current_metadata_for_draft_cover(
        session,
        cover,
    )


def _warning_severity_for_candidate(
    warning_type: str,
    candidate: CoverImageOcrCandidate,
) -> str:
    if warning_type == "barcode_present":
        return "info"
    if warning_type == "issue_number_mismatch":
        return "critical" if candidate.review_status == "approved" else "warning"
    if warning_type in {"title_mismatch", "publisher_mismatch", "missing_metadata"}:
        return "warning" if candidate.review_status == "approved" else "info"
    if warning_type == "low_confidence_candidate":
        return "warning" if candidate.review_status == "approved" else "info"
    return "warning"


def _warning_signature(
    *,
    warning_type: str,
    ocr_candidate_id: int | None,
    current_metadata_value: str | None,
    candidate_value: str | None,
) -> tuple[str, int | None, str | None, str | None]:
    return (warning_type, ocr_candidate_id, current_metadata_value, candidate_value)


def _warning_signature_from_row(
    row: CoverImageOcrReconciliationWarning,
) -> tuple[str, int | None, str | None, str | None]:
    return _warning_signature(
        warning_type=row.warning_type,
        ocr_candidate_id=row.ocr_candidate_id,
        current_metadata_value=row.current_metadata_value,
        candidate_value=row.candidate_value,
    )


def _build_ocr_reconciliation_warning_specs(
    *,
    cover: CoverImage,
    selected_candidates: dict[str, CoverImageOcrCandidate],
    current_metadata: dict[str, str | int | None] | None,
) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    field_labels = {
        "title": "title",
        "publisher": "publisher",
        "issue_number": "issue number",
    }
    mismatch_warning_types = {
        "title": "title_mismatch",
        "publisher": "publisher_mismatch",
        "issue_number": "issue_number_mismatch",
    }

    for candidate_type in ("title", "publisher", "issue_number"):
        row = selected_candidates.get(candidate_type)
        if row is None or row.id is None:
            continue
        candidate_value = _preferred_candidate_value(row)
        if candidate_value is None:
            continue
        current_value = (
            str(current_metadata.get(candidate_type)).strip()
            if current_metadata is not None and current_metadata.get(candidate_type) is not None
            else None
        )
        if current_value is None:
            specs.append(
                {
                    "cover_image_id": cover.id,
                    "inventory_copy_id": current_metadata.get("inventory_copy_id")
                    if current_metadata is not None
                    else cover.inventory_copy_id,
                    "ocr_candidate_id": row.id,
                    "warning_type": "missing_metadata",
                    "severity": _warning_severity_for_candidate("missing_metadata", row),
                    "current_metadata_value": None,
                    "candidate_value": candidate_value,
                    "message": f"OCR found a {field_labels[candidate_type]} candidate but current metadata is missing.",
                }
            )
        else:
            current_norm = (
                _normalize_reconciliation_issue_number(current_value)
                if candidate_type == "issue_number"
                else _normalize_reconciliation_text(current_value)
            )
            candidate_norm = (
                _normalize_reconciliation_issue_number(candidate_value)
                if candidate_type == "issue_number"
                else _normalize_reconciliation_text(candidate_value)
            )
            if current_norm is not None and candidate_norm is not None and current_norm != candidate_norm:
                warning_type = mismatch_warning_types[candidate_type]
                specs.append(
                    {
                        "cover_image_id": cover.id,
                        "inventory_copy_id": current_metadata.get("inventory_copy_id")
                        if current_metadata is not None
                        else cover.inventory_copy_id,
                        "ocr_candidate_id": row.id,
                        "warning_type": warning_type,
                        "severity": _warning_severity_for_candidate(warning_type, row),
                        "current_metadata_value": current_value,
                        "candidate_value": candidate_value,
                        "message": f"OCR {field_labels[candidate_type]} candidate does not match current metadata.",
                    }
                )
        if (
            row.confidence_score is not None
            and row.confidence_score < OCR_RECONCILIATION_LOW_CONFIDENCE_THRESHOLD
        ):
            specs.append(
                {
                    "cover_image_id": cover.id,
                    "inventory_copy_id": current_metadata.get("inventory_copy_id")
                    if current_metadata is not None
                    else cover.inventory_copy_id,
                    "ocr_candidate_id": row.id,
                    "warning_type": "low_confidence_candidate",
                    "severity": _warning_severity_for_candidate("low_confidence_candidate", row),
                    "current_metadata_value": current_value,
                    "candidate_value": candidate_value,
                    "message": (
                        f"OCR {field_labels[candidate_type]} candidate confidence "
                        f"({row.confidence_score:.2f}) is below the review threshold."
                    ),
                }
            )

    barcode = selected_candidates.get("barcode")
    if barcode is not None and barcode.id is not None:
        barcode_value = _preferred_candidate_value(barcode)
        if barcode_value is not None:
            specs.append(
                {
                    "cover_image_id": cover.id,
                    "inventory_copy_id": current_metadata.get("inventory_copy_id")
                    if current_metadata is not None
                    else cover.inventory_copy_id,
                    "ocr_candidate_id": barcode.id,
                    "warning_type": "barcode_present",
                    "severity": "info",
                    "current_metadata_value": None,
                    "candidate_value": barcode_value,
                    "message": "OCR detected a barcode candidate. Review manually before any metadata action.",
                }
            )
            if (
                barcode.confidence_score is not None
                and barcode.confidence_score < OCR_RECONCILIATION_LOW_CONFIDENCE_THRESHOLD
            ):
                specs.append(
                    {
                        "cover_image_id": cover.id,
                        "inventory_copy_id": current_metadata.get("inventory_copy_id")
                        if current_metadata is not None
                        else cover.inventory_copy_id,
                        "ocr_candidate_id": barcode.id,
                        "warning_type": "low_confidence_candidate",
                        "severity": _warning_severity_for_candidate("low_confidence_candidate", barcode),
                        "current_metadata_value": None,
                        "candidate_value": barcode_value,
                        "message": (
                            f"OCR barcode candidate confidence "
                            f"({barcode.confidence_score:.2f}) is below the review threshold."
                        ),
                    }
                )
    return specs


def list_cover_image_ocr_reconciliation_warnings(
    session: Session,
    *,
    cover_image_id: int,
) -> list[CoverImageOcrReconciliationWarningRead]:
    return _ocr_reconciliation_warning_reads_by_cover_id(session, [cover_image_id]).get(cover_image_id, [])


def _reconcile_cover_image_ocr_metadata(
    session: Session,
    *,
    cover: CoverImage,
    actor_user_id: int,
) -> CoverImageOcrReconciliationResponse:
    candidate_rows = session.exec(
        select(CoverImageOcrCandidate)
        .where(CoverImageOcrCandidate.cover_image_id == cover.id)
        .order_by(CoverImageOcrCandidate.id.asc())
    ).all()
    current_metadata = _current_metadata_for_cover(session, cover)
    selected_candidates = _selected_ocr_candidates_for_reconciliation(candidate_rows)
    desired_specs = _build_ocr_reconciliation_warning_specs(
        cover=cover,
        selected_candidates=selected_candidates,
        current_metadata=current_metadata,
    )
    existing_rows = session.exec(
        select(CoverImageOcrReconciliationWarning).where(
            CoverImageOcrReconciliationWarning.cover_image_id == cover.id
        )
    ).all()
    existing_by_signature = {
        _warning_signature_from_row(row): row for row in existing_rows if row.id is not None
    }
    desired_signatures: set[tuple[str, int | None, str | None, str | None]] = set()
    now = _processing_now()
    for spec in desired_specs:
        signature = _warning_signature(
            warning_type=str(spec["warning_type"]),
            ocr_candidate_id=spec["ocr_candidate_id"],  # type: ignore[arg-type]
            current_metadata_value=spec["current_metadata_value"],  # type: ignore[arg-type]
            candidate_value=spec["candidate_value"],  # type: ignore[arg-type]
        )
        desired_signatures.add(signature)
        row = existing_by_signature.get(signature)
        if row is None:
            row = CoverImageOcrReconciliationWarning(
                cover_image_id=cover.id,
                inventory_copy_id=spec["inventory_copy_id"],  # type: ignore[arg-type]
                ocr_candidate_id=spec["ocr_candidate_id"],  # type: ignore[arg-type]
                warning_type=str(spec["warning_type"]),
                severity=str(spec["severity"]),
                current_metadata_value=spec["current_metadata_value"],  # type: ignore[arg-type]
                candidate_value=spec["candidate_value"],  # type: ignore[arg-type]
                message=str(spec["message"]),
                status="open",
                resolved_at=None,
                resolved_by_user_id=None,
            )
            session.add(row)
            session.flush()
            record_metadata_audit(
                session,
                entity_type="ocr_reconciliation_warning",
                entity_id=row.id,
                action="ocr_reconciliation_warning_created",
                before_snapshot=None,
                after_snapshot=cover_ocr_reconciliation_warning_entity_to_read(row),
                actor_user_id=actor_user_id,
            )
            existing_by_signature[signature] = row
            continue
        row.inventory_copy_id = spec["inventory_copy_id"]  # type: ignore[assignment]
        row.ocr_candidate_id = spec["ocr_candidate_id"]  # type: ignore[assignment]
        row.severity = str(spec["severity"])
        row.message = str(spec["message"])
        if row.status != "open" and row.resolved_by_user_id is None:
            row.status = "open"
            row.resolved_at = None
            row.resolved_by_user_id = None
        session.add(row)

    for row in existing_rows:
        if row.status != "open":
            continue
        if _warning_signature_from_row(row) in desired_signatures:
            continue
        row.status = "dismissed"
        row.resolved_at = now
        row.resolved_by_user_id = None
        session.add(row)

    session.commit()
    warnings = list_cover_image_ocr_reconciliation_warnings(session, cover_image_id=cover.id)
    return CoverImageOcrReconciliationResponse(
        cover_image_id=cover.id,
        warning_count=len(warnings),
        warnings=warnings,
    )


def reconcile_cover_image_ocr_metadata_for_owner(
    session: Session,
    *,
    current_user: User,
    cover_image_id: int,
) -> CoverImageOcrReconciliationResponse:
    cover = get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return _reconcile_cover_image_ocr_metadata(
        session,
        cover=cover,
        actor_user_id=current_user.id,
    )


def reconcile_cover_image_ocr_metadata_for_ops(
    session: Session,
    *,
    cover_image_id: int,
    actor_user_id: int,
) -> CoverImageOcrReconciliationResponse:
    cover = get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=cover_image_id)
    return _reconcile_cover_image_ocr_metadata(
        session,
        cover=cover,
        actor_user_id=actor_user_id,
    )


def get_cover_image_ocr_reconciliation_warning_or_404(
    session: Session,
    warning_id: int,
) -> CoverImageOcrReconciliationWarning:
    row = session.get(CoverImageOcrReconciliationWarning, warning_id)
    if row is None:
        raise HTTPException(status_code=404, detail="OCR reconciliation warning not found")
    return row


def _set_ocr_reconciliation_warning_status(
    session: Session,
    *,
    row: CoverImageOcrReconciliationWarning,
    status_value: Literal["acknowledged", "dismissed"],
    actor_user_id: int,
) -> CoverImageOcrReconciliationWarningRead:
    if row.id is None:
        raise ValueError("OCR reconciliation warning must be flushed before status updates")
    if row.status == status_value:
        return cover_ocr_reconciliation_warning_entity_to_read(row)
    before = cover_ocr_reconciliation_warning_entity_to_read(row)
    row.status = status_value
    row.resolved_at = _processing_now()
    row.resolved_by_user_id = actor_user_id
    session.add(row)
    record_metadata_audit(
        session,
        entity_type="ocr_reconciliation_warning",
        entity_id=row.id,
        action=f"ocr_reconciliation_warning_{status_value}",
        before_snapshot=before,
        after_snapshot=cover_ocr_reconciliation_warning_entity_to_read(row),
        actor_user_id=actor_user_id,
    )
    session.commit()
    session.refresh(row)
    return cover_ocr_reconciliation_warning_entity_to_read(row)


def acknowledge_ocr_reconciliation_warning_for_owner(
    session: Session,
    *,
    current_user: User,
    warning_id: int,
) -> CoverImageOcrReconciliationWarningRead:
    row = get_cover_image_ocr_reconciliation_warning_or_404(session, warning_id)
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=row.cover_image_id,
    )
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return _set_ocr_reconciliation_warning_status(
        session,
        row=row,
        status_value="acknowledged",
        actor_user_id=current_user.id,
    )


def dismiss_ocr_reconciliation_warning_for_owner(
    session: Session,
    *,
    current_user: User,
    warning_id: int,
) -> CoverImageOcrReconciliationWarningRead:
    row = get_cover_image_ocr_reconciliation_warning_or_404(session, warning_id)
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=row.cover_image_id,
    )
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return _set_ocr_reconciliation_warning_status(
        session,
        row=row,
        status_value="dismissed",
        actor_user_id=current_user.id,
    )


def acknowledge_ocr_reconciliation_warning_for_ops(
    session: Session,
    *,
    warning_id: int,
    actor_user_id: int,
) -> CoverImageOcrReconciliationWarningRead:
    row = get_cover_image_ocr_reconciliation_warning_or_404(session, warning_id)
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=row.cover_image_id)
    return _set_ocr_reconciliation_warning_status(
        session,
        row=row,
        status_value="acknowledged",
        actor_user_id=actor_user_id,
    )


def dismiss_ocr_reconciliation_warning_for_ops(
    session: Session,
    *,
    warning_id: int,
    actor_user_id: int,
) -> CoverImageOcrReconciliationWarningRead:
    row = get_cover_image_ocr_reconciliation_warning_or_404(session, warning_id)
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=row.cover_image_id)
    return _set_ocr_reconciliation_warning_status(
        session,
        row=row,
        status_value="dismissed",
        actor_user_id=actor_user_id,
    )


def _latest_ocr_result_reads_by_cover_id(
    session: Session,
    cover_image_ids: list[int],
) -> dict[int, CoverImageOcrResultRead]:
    if not cover_image_ids:
        return {}
    latest_subquery = (
        select(
            CoverImageOcrResult.cover_image_id,
            func.max(CoverImageOcrResult.id).label("latest_id"),
        )
        .where(CoverImageOcrResult.cover_image_id.in_(cover_image_ids))
        .group_by(CoverImageOcrResult.cover_image_id)
    ).subquery()
    rows = session.exec(
        select(CoverImageOcrResult)
        .join(latest_subquery, CoverImageOcrResult.id == latest_subquery.c.latest_id)
        .order_by(CoverImageOcrResult.id.desc())
    ).all()
    return {row.cover_image_id: cover_ocr_result_entity_to_read(row) for row in rows}


_PRIOR_OCR_HISTORY_TIMESTAMP_CAP = 20


def _ocr_run_counts_by_cover_id(session: Session, cover_image_ids: list[int]) -> dict[int, int]:
    if not cover_image_ids:
        return {}
    grouped = session.exec(
        select(CoverImageOcrResult.cover_image_id, func.count(CoverImageOcrResult.id)).where(
            CoverImageOcrResult.cover_image_id.in_(cover_image_ids)
        ).group_by(CoverImageOcrResult.cover_image_id)
    ).all()
    return {int(cid): int(cnt) for cid, cnt in grouped}


def _ocr_prior_created_ats_by_cover_id(
    session: Session,
    cover_image_ids: list[int],
) -> dict[int, list[datetime]]:
    """Ordered ``created_at`` values for OCR runs strictly before each cover's latest OCR row."""
    if not cover_image_ids:
        return {}
    rows = session.exec(
        select(
            CoverImageOcrResult.cover_image_id,
            CoverImageOcrResult.id,
            CoverImageOcrResult.created_at,
        )
        .where(CoverImageOcrResult.cover_image_id.in_(cover_image_ids))
        .order_by(CoverImageOcrResult.cover_image_id, CoverImageOcrResult.id.desc())
    ).all()
    buckets: dict[int, list[datetime]] = defaultdict(list)
    for cover_image_id, _result_id, created_at in rows:
        buckets[int(cover_image_id)].append(created_at)
    out: dict[int, list[datetime]] = {}
    for cid, timestamps in buckets.items():
        pri = timestamps[1 : 1 + _PRIOR_OCR_HISTORY_TIMESTAMP_CAP]
        out[cid] = pri
    return out


def build_cover_image_ocr_visibility(
    *,
    cover: CoverImage,
    job_status: Literal["idle", "queued", "running"],
    run_count: int,
    prior_run_created_ats: list[datetime],
) -> CoverImageOcrVisibility:
    eligible_for_enqueue = (
        cover.matching_status == "ready" and cover.processing_status == "processed"
    )
    return CoverImageOcrVisibility(
        job_status=job_status,
        retry_available=eligible_for_enqueue and job_status == "idle",
        ocr_run_count=run_count,
        prior_run_created_ats=prior_run_created_ats,
    )


def compute_cover_images_ocr_visibility_batch(
    session: Session,
    covers: list[CoverImage],
) -> dict[int, CoverImageOcrVisibility]:
    ids = [row.id for row in covers if row.id is not None]
    if not ids:
        return {}
    counts = _ocr_run_counts_by_cover_id(session, ids)
    priors = _ocr_prior_created_ats_by_cover_id(session, ids)
    out: dict[int, CoverImageOcrVisibility] = {}
    for cover in covers:
        cid = cover.id
        if cid is None:
            continue
        job_status_key = cover_image_ocr_job_ui_status(cid)
        out[cid] = build_cover_image_ocr_visibility(
            cover=cover,
            job_status=job_status_key,
            run_count=counts.get(cid, 0),
            prior_run_created_ats=priors.get(cid, []),
        )
    return out


def compute_cover_image_ocr_visibility(session: Session, cover: CoverImage) -> CoverImageOcrVisibility:
    """Single-cover OCR workflow snapshot (RQ + aggregated history counters)."""
    if cover.id is None:
        raise ValueError("cover image must be flushed before OCR visibility serialization")
    return compute_cover_images_ocr_visibility_batch(session, [cover])[cover.id]


def list_cover_ocr_result_reads_for_cover(
    session: Session,
    cover_image_id: int,
) -> list[CoverImageOcrResultRead]:
    rows = session.exec(
        select(CoverImageOcrResult)
        .where(CoverImageOcrResult.cover_image_id == cover_image_id)
        .order_by(CoverImageOcrResult.created_at.desc(), CoverImageOcrResult.id.desc())
    ).all()
    return [cover_ocr_result_entity_to_read(row) for row in rows]


def _derivative_paths(
    derivatives: list[CoverImageDerivativeRead],
) -> tuple[str | None, str | None]:
    thumb = next(
        (row.fetch_path for row in derivatives if row.derivative_type == "thumb"),
        None,
    )
    medium = next(
        (row.fetch_path for row in derivatives if row.derivative_type == "medium"),
        None,
    )
    return thumb, medium


def _ocr_region_count_by_cover_id(
    session: Session,
    cover_image_ids: list[int],
) -> dict[int, int]:
    if not cover_image_ids:
        return {}
    grouped = session.exec(
        select(CoverImageOcrRegion.cover_image_id, func.count(CoverImageOcrRegion.id))
        .where(CoverImageOcrRegion.cover_image_id.in_(cover_image_ids))
        .group_by(CoverImageOcrRegion.cover_image_id)
    ).all()
    return {int(cover_id): int(count) for cover_id, count in grouped}


def _ocr_candidate_count_by_cover_id(
    session: Session,
    cover_image_ids: list[int],
) -> dict[int, int]:
    if not cover_image_ids:
        return {}
    grouped = session.exec(
        select(CoverImageOcrCandidate.cover_image_id, func.count(CoverImageOcrCandidate.id))
        .where(CoverImageOcrCandidate.cover_image_id.in_(cover_image_ids))
        .group_by(CoverImageOcrCandidate.cover_image_id)
    ).all()
    return {int(cover_id): int(count) for cover_id, count in grouped}


def _barcode_candidate_count_by_cover_id(
    session: Session,
    cover_image_ids: list[int],
) -> dict[int, int]:
    if not cover_image_ids:
        return {}
    grouped = session.exec(
        select(CoverImageBarcodeCandidate.cover_image_id, func.count(CoverImageBarcodeCandidate.id))
        .where(CoverImageBarcodeCandidate.cover_image_id.in_(cover_image_ids))
        .group_by(CoverImageBarcodeCandidate.cover_image_id)
    ).all()
    return {int(cover_id): int(count) for cover_id, count in grouped}


def _fingerprint_count_by_cover_id(
    session: Session,
    cover_image_ids: list[int],
) -> dict[int, int]:
    if not cover_image_ids:
        return {}
    grouped = session.exec(
        select(CoverImageFingerprint.cover_image_id, func.count(CoverImageFingerprint.id))
        .where(CoverImageFingerprint.cover_image_id.in_(cover_image_ids))
        .group_by(CoverImageFingerprint.cover_image_id)
    ).all()
    return {int(cover_id): int(count) for cover_id, count in grouped}


def _ocr_candidate_review_counts_by_cover_id(
    session: Session,
    cover_image_ids: list[int],
) -> dict[int, CoverImageOcrCandidateReviewCounts]:
    if not cover_image_ids:
        return {}
    accumulator: dict[int, dict[str, int]] = {
        int(cid): {"pending": 0, "approved": 0, "rejected": 0} for cid in cover_image_ids
    }
    rows = session.exec(
        select(
            CoverImageOcrCandidate.cover_image_id,
            CoverImageOcrCandidate.review_status,
            func.count(CoverImageOcrCandidate.id),
        )
        .where(CoverImageOcrCandidate.cover_image_id.in_(cover_image_ids))
        .group_by(CoverImageOcrCandidate.cover_image_id, CoverImageOcrCandidate.review_status)
    ).all()
    for cover_id, status, count in rows:
        bucket = accumulator.get(int(cover_id))
        if bucket is None or status not in bucket:
            continue
        bucket[str(status)] += int(count)
    return {
        cid: CoverImageOcrCandidateReviewCounts(
            pending=vals["pending"],
            approved=vals["approved"],
            rejected=vals["rejected"],
        )
        for cid, vals in accumulator.items()
    }


def _barcode_candidate_review_counts_by_cover_id(
    session: Session,
    cover_image_ids: list[int],
) -> dict[int, CoverImageBarcodeCandidateReviewCounts]:
    if not cover_image_ids:
        return {}
    accumulator: dict[int, dict[str, int]] = {
        int(cid): {"pending": 0, "approved": 0, "rejected": 0} for cid in cover_image_ids
    }
    rows = session.exec(
        select(
            CoverImageBarcodeCandidate.cover_image_id,
            CoverImageBarcodeCandidate.review_state,
            func.count(CoverImageBarcodeCandidate.id),
        )
        .where(CoverImageBarcodeCandidate.cover_image_id.in_(cover_image_ids))
        .group_by(CoverImageBarcodeCandidate.cover_image_id, CoverImageBarcodeCandidate.review_state)
    ).all()
    for cover_id, review_state, count in rows:
        bucket = accumulator.get(int(cover_id))
        if bucket is None or review_state not in bucket:
            continue
        bucket[str(review_state)] += int(count)
    return {
        cid: CoverImageBarcodeCandidateReviewCounts(
            pending=vals["pending"],
            approved=vals["approved"],
            rejected=vals["rejected"],
        )
        for cid, vals in accumulator.items()
    }


def _ocr_reconciliation_warning_counts_by_cover_id(
    session: Session,
    cover_image_ids: list[int],
) -> dict[int, CoverImageOcrReconciliationWarningCounts]:
    if not cover_image_ids:
        return {}
    accumulator: dict[int, dict[str, int]] = {
        int(cid): {"open": 0, "acknowledged": 0, "dismissed": 0} for cid in cover_image_ids
    }
    rows = session.exec(
        select(
            CoverImageOcrReconciliationWarning.cover_image_id,
            CoverImageOcrReconciliationWarning.status,
            func.count(CoverImageOcrReconciliationWarning.id),
        )
        .where(CoverImageOcrReconciliationWarning.cover_image_id.in_(cover_image_ids))
        .group_by(
            CoverImageOcrReconciliationWarning.cover_image_id,
            CoverImageOcrReconciliationWarning.status,
        )
    ).all()
    for cover_id, status, count in rows:
        bucket = accumulator.get(int(cover_id))
        if bucket is None or status not in bucket:
            continue
        bucket[str(status)] += int(count)
    return {
        cid: CoverImageOcrReconciliationWarningCounts(
            open=vals["open"],
            acknowledged=vals["acknowledged"],
            dismissed=vals["dismissed"],
        )
        for cid, vals in accumulator.items()
    }


def _sort_cover_reads(reads: list[CoverImageRead]) -> None:
    """Primary first, then newest `created_at`."""
    reads.sort(key=lambda r: (0 if r.is_primary else 1, -r.created_at.timestamp()))


def cover_entity_to_read(
    row: CoverImage,
    *,
    primary_cover_image_id: int | None = None,
    derivatives: list[CoverImageDerivativeRead] | None = None,
    latest_ocr_result: CoverImageOcrResultRead | None = None,
    ocr_visibility: CoverImageOcrVisibility,
    ocr_regions: list[CoverImageOcrRegionRead] | None = None,
    ocr_candidates: list[CoverImageOcrCandidateRead] | None = None,
    barcode_candidates: list[CoverImageBarcodeCandidateRead] | None = None,
    fingerprints: list[CoverImageFingerprintRead] | None = None,
    ocr_quality_analyses: list[CoverImageOcrQualityAnalysisRead] | None = None,
    match_candidates: list[CoverImageMatchCandidateRead] | None = None,
    ocr_reconciliation_warnings: list[CoverImageOcrReconciliationWarningRead] | None = None,
) -> CoverImageRead:
    if row.id is None:
        raise ValueError("cover image must be flushed before serialization")
    is_primary = primary_cover_image_id is not None and row.id == primary_cover_image_id
    derivative_reads = derivatives or []
    thumbnail_fetch_path, medium_fetch_path = _derivative_paths(derivative_reads)
    pe = row.processing_error
    parsed_pe = try_parse_structured_error(pe)
    return CoverImageRead(
        id=row.id,
        inventory_copy_id=row.inventory_copy_id,
        canonical_series_id=row.canonical_series_id,
        draft_import_id=row.draft_import_id,
        source_type=row.source_type,
        original_filename=row.original_filename,
        mime_type=row.mime_type,
        image_width=row.image_width,
        image_height=row.image_height,
        file_size=row.file_size,
        sha256_hash=row.sha256_hash,
        processing_status=row.processing_status,
        processing_error=public_safe_message(pe),
        file_structured_processing_error=(
            StructuredProcessingErrorRead(
                error_code=parsed_pe.error_code,
                error_type=parsed_pe.error_type,
                safe_message=parsed_pe.safe_message,
                retryable=parsed_pe.retryable,
                occurred_at=parsed_pe.occurred_at,
            )
            if parsed_pe is not None
            else None
        ),
        processed_at=row.processed_at,
        metadata_refreshed_at=row.metadata_refreshed_at,
        matching_status=row.matching_status,
        matching_notes=row.matching_notes,
        ready_for_matching_at=row.ready_for_matching_at,
        latest_ocr_result=latest_ocr_result,
        ocr_visibility=ocr_visibility,
        ocr_regions=ocr_regions or [],
        ocr_candidates=ocr_candidates or [],
        barcode_candidates=barcode_candidates or [],
        fingerprints=fingerprints or [],
        ocr_quality_analyses=ocr_quality_analyses or [],
        match_candidates=match_candidates or [],
        ocr_reconciliation_warnings=ocr_reconciliation_warnings or [],
        thumbnail_fetch_path=thumbnail_fetch_path,
        medium_fetch_path=medium_fetch_path,
        derivatives=derivative_reads,
        created_at=row.created_at,
        is_primary=is_primary,
        fetch_path=cover_fetch_path(row.id),
    )


def list_cover_reads_for_inventory(
    session: Session, inventory_copy_id: int
) -> list[CoverImageRead]:
    inv = session.get(InventoryCopy, inventory_copy_id)
    primary_id = inv.primary_cover_image_id if inv else None
    rows = session.exec(
        select(CoverImage)
        .where(CoverImage.inventory_copy_id == inventory_copy_id)
        .order_by(CoverImage.created_at.desc())
    ).all()
    derivatives_by_cover_id = _derivative_reads_by_cover_id(
        session,
        [row.id for row in rows if row.id is not None],
    )
    ocr_regions_by_cover_id = _ocr_region_reads_by_cover_id(
        session,
        [row.id for row in rows if row.id is not None],
    )
    ocr_candidates_by_cover_id = _ocr_candidate_reads_by_cover_id(
        session,
        [row.id for row in rows if row.id is not None],
    )
    barcode_candidates_by_cover_id = _barcode_candidate_reads_by_cover_id(
        session,
        [row.id for row in rows if row.id is not None],
    )
    fingerprints_by_cover_id = _fingerprint_reads_by_cover_id(
        session,
        [row.id for row in rows if row.id is not None],
    )
    ocr_quality_analyses_by_cover_id = _ocr_quality_analysis_reads_by_cover_id(
        session,
        [row.id for row in rows if row.id is not None],
    )
    match_candidates_by_cover_id = _match_candidate_reads_by_cover_id(
        session,
        [row.id for row in rows if row.id is not None],
    )
    ocr_reconciliation_warnings_by_cover_id = _ocr_reconciliation_warning_reads_by_cover_id(
        session,
        [row.id for row in rows if row.id is not None],
    )
    latest_ocr_by_cover_id = _latest_ocr_result_reads_by_cover_id(
        session,
        [row.id for row in rows if row.id is not None],
    )
    ocr_visibility_by_cover_id = compute_cover_images_ocr_visibility_batch(session, list(rows))
    reads = [
        cover_entity_to_read(
            row,
            primary_cover_image_id=primary_id,
            derivatives=derivatives_by_cover_id.get(row.id or -1, []),
            latest_ocr_result=latest_ocr_by_cover_id.get(row.id or -1),
            ocr_visibility=ocr_visibility_by_cover_id[row.id],  # type: ignore[literal-required]
            ocr_regions=ocr_regions_by_cover_id.get(row.id or -1, []),
            ocr_candidates=ocr_candidates_by_cover_id.get(row.id or -1, []),
            barcode_candidates=barcode_candidates_by_cover_id.get(row.id or -1, []),
            fingerprints=fingerprints_by_cover_id.get(row.id or -1, []),
            ocr_quality_analyses=ocr_quality_analyses_by_cover_id.get(row.id or -1, []),
            match_candidates=match_candidates_by_cover_id.get(row.id or -1, []),
            ocr_reconciliation_warnings=ocr_reconciliation_warnings_by_cover_id.get(row.id or -1, []),
        )
        for row in rows
    ]
    _sort_cover_reads(reads)
    return reads


def list_cover_reads_for_draft(session: Session, draft_import_id: int) -> list[CoverImageRead]:
    draft = session.get(DraftImport, draft_import_id)
    primary_id = draft.primary_cover_image_id if draft else None
    rows = session.exec(
        select(CoverImage)
        .where(CoverImage.draft_import_id == draft_import_id)
        .order_by(CoverImage.created_at.desc())
    ).all()
    derivatives_by_cover_id = _derivative_reads_by_cover_id(
        session,
        [row.id for row in rows if row.id is not None],
    )
    ocr_regions_by_cover_id = _ocr_region_reads_by_cover_id(
        session,
        [row.id for row in rows if row.id is not None],
    )
    ocr_candidates_by_cover_id = _ocr_candidate_reads_by_cover_id(
        session,
        [row.id for row in rows if row.id is not None],
    )
    barcode_candidates_by_cover_id = _barcode_candidate_reads_by_cover_id(
        session,
        [row.id for row in rows if row.id is not None],
    )
    fingerprints_by_cover_id = _fingerprint_reads_by_cover_id(
        session,
        [row.id for row in rows if row.id is not None],
    )
    ocr_quality_analyses_by_cover_id = _ocr_quality_analysis_reads_by_cover_id(
        session,
        [row.id for row in rows if row.id is not None],
    )
    match_candidates_by_cover_id = _match_candidate_reads_by_cover_id(
        session,
        [row.id for row in rows if row.id is not None],
    )
    ocr_reconciliation_warnings_by_cover_id = _ocr_reconciliation_warning_reads_by_cover_id(
        session,
        [row.id for row in rows if row.id is not None],
    )
    latest_ocr_by_cover_id = _latest_ocr_result_reads_by_cover_id(
        session,
        [row.id for row in rows if row.id is not None],
    )
    ocr_visibility_by_cover_id = compute_cover_images_ocr_visibility_batch(session, list(rows))
    reads = [
        cover_entity_to_read(
            row,
            primary_cover_image_id=primary_id,
            derivatives=derivatives_by_cover_id.get(row.id or -1, []),
            latest_ocr_result=latest_ocr_by_cover_id.get(row.id or -1),
            ocr_visibility=ocr_visibility_by_cover_id[row.id],  # type: ignore[literal-required]
            ocr_regions=ocr_regions_by_cover_id.get(row.id or -1, []),
            ocr_candidates=ocr_candidates_by_cover_id.get(row.id or -1, []),
            barcode_candidates=barcode_candidates_by_cover_id.get(row.id or -1, []),
            fingerprints=fingerprints_by_cover_id.get(row.id or -1, []),
            ocr_quality_analyses=ocr_quality_analyses_by_cover_id.get(row.id or -1, []),
            match_candidates=match_candidates_by_cover_id.get(row.id or -1, []),
            ocr_reconciliation_warnings=ocr_reconciliation_warnings_by_cover_id.get(row.id or -1, []),
        )
        for row in rows
    ]
    _sort_cover_reads(reads)
    return reads


async def persist_cover_upload(
    session: Session,
    *,
    settings: Settings,
    file: UploadFile,
    inventory_copy_id: int | None,
    draft_import_id: int | None,
    source_type: str,
    current_user: User,
) -> CoverImageRead:
    linked = sum(1 for v in (inventory_copy_id, draft_import_id) if v is not None)
    if linked != 1:
        raise HTTPException(
            status_code=422,
            detail="Specify exactly one linkage target between inventory copy and draft import.",
        )

    canonical_series_id: int | None = None
    if inventory_copy_id is not None:
        row = session.exec(
            select(InventoryCopy).where(
                InventoryCopy.id == inventory_copy_id,
                InventoryCopy.user_id == current_user.id,
            )
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Inventory copy not found")
    elif draft_import_id is not None:
        draft = session.exec(
            select(DraftImport).where(
                DraftImport.id == draft_import_id,
                DraftImport.user_id == current_user.id,
            )
        ).first()
        if draft is None:
            raise HTTPException(status_code=404, detail="Import not found")

    body = await file.read()
    if not body:
        raise HTTPException(status_code=422, detail="Empty upload.")

    if len(body) > settings.cover_images_max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Image exceeds configured limit ({settings.cover_images_max_bytes} bytes).",
        )

    sha = sha256_raw_bytes(body)
    width, height, mime_type = extract_image_dimensions_and_mime(body, file.content_type)
    storage_rel = deterministic_relative_storage_path(mime_type, sha)
    abs_path = resolve_filesystem_path(settings, storage_rel.replace("\\", "/"))

    atomic_write_bytes(abs_path, body)

    display_name = (file.filename or "").strip()[:510]
    entity = CoverImage(
        inventory_copy_id=inventory_copy_id,
        draft_import_id=draft_import_id,
        canonical_series_id=canonical_series_id,
        source_type=source_type,
        original_filename=display_name or None,
        storage_path=storage_rel.replace("\\", "/"),
        mime_type=mime_type,
        image_width=width,
        image_height=height,
        file_size=len(body),
        sha256_hash=sha,
        processing_status="pending",
        processing_error=None,
        processed_at=None,
        metadata_refreshed_at=None,
        matching_status="not_ready",
        matching_notes=None,
        ready_for_matching_at=None,
    )
    session.add(entity)
    session.commit()
    session.refresh(entity)

    primary_cover_image_id: int | None = None
    if inventory_copy_id is not None:
        inv_reload = session.get(InventoryCopy, inventory_copy_id)
        primary_cover_image_id = (
            inv_reload.primary_cover_image_id if inv_reload is not None else None
        )
    elif draft_import_id is not None:
        draft_reload = session.get(DraftImport, draft_import_id)
        primary_cover_image_id = (
            draft_reload.primary_cover_image_id if draft_reload is not None else None
        )
    return cover_entity_to_read(
        entity,
        primary_cover_image_id=primary_cover_image_id,
        ocr_visibility=compute_cover_image_ocr_visibility(session, entity),
        ocr_quality_analyses=list_cover_ocr_quality_analysis_reads_for_cover(session, entity.id or -1),
    )


def _owner_id_expression():
    return case(
        (CoverImage.inventory_copy_id.is_not(None), InventoryCopy.user_id),
        else_=DraftImport.user_id,
    )


def user_can_download_cover(session: Session, cover: CoverImage, current_user: User) -> bool:
    if cover.inventory_copy_id:
        uid = session.exec(
            select(InventoryCopy.user_id).where(InventoryCopy.id == cover.inventory_copy_id)
        ).first()
        return uid == current_user.id
    if cover.draft_import_id:
        uid = session.exec(
            select(DraftImport.user_id).where(DraftImport.id == cover.draft_import_id)
        ).first()
        return uid == current_user.id
    return False


def get_cover_entity_or_404(session: Session, cover_image_id: int) -> CoverImage:
    cover = session.get(CoverImage, cover_image_id)
    if cover is None:
        raise HTTPException(status_code=404, detail="Cover image not found")
    return cover


def _processing_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_ocr_text(raw_text: str) -> str | None:
    trimmed = raw_text.strip()
    if not trimmed:
        return None
    normalized = re.sub(r"[ \t]+", " ", trimmed)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized or None


def get_tesseract_engine_version() -> str | None:
    try:
        result = subprocess.run(
            [_resolve_ocr_engine_cmd(), "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=8.0,
        )
    except (OSError, TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    first_line = (result.stdout or "").splitlines()
    if not first_line:
        return None
    return first_line[0].strip()[:255] or None


def _run_tesseract_ocr_on_cover_path(image_path: Path, *, timeout_seconds: float | None = None) -> str:
    try:
        kwargs: dict[str, object] = {
            "args": [_resolve_ocr_engine_cmd(), str(image_path), "stdout"],
            "capture_output": True,
            "text": True,
            "check": False,
        }
        if timeout_seconds is not None and timeout_seconds > 0:
            kwargs["timeout"] = timeout_seconds
        result = subprocess.run(**kwargs)  # type: ignore[arg-type]
    except OSError as exc:
        raise ValueError("Local Tesseract OCR engine is unavailable on this host.") from exc
    except TimeoutExpired as exc:
        raise ValueError(
            f"OCR tesseract timed out after {getattr(exc, 'timeout', timeout_seconds)!s}s."
        ) from exc
    if result.returncode != 0:
        error_text = (result.stderr or "").strip() or "Tesseract OCR execution failed."
        raise ValueError(error_text[:2000])
    return result.stdout or ""


def _run_tesseract_ocr_with_test_compat(
    image_path: Path,
    *,
    timeout_seconds: float | None = None,
) -> str:
    """Call the OCR runner with timeout support while tolerating legacy one-arg test stubs."""

    try:
        return _run_tesseract_ocr_on_cover_path(image_path, timeout_seconds=timeout_seconds)
    except TypeError as exc:
        if "timeout_seconds" not in str(exc):
            raise
        return _run_tesseract_ocr_on_cover_path(image_path)


def create_pending_cover_image_ocr_result(
    session: Session,
    *,
    cover_image_id: int,
    replay_of_ocr_result_id: int | None = None,
    replay_reason: str | None = None,
) -> CoverImageOcrResultRead:
    row = CoverImageOcrResult(
        cover_image_id=cover_image_id,
        source_cover_image_sha256=None,
        source_thumb_derivative_sha256=None,
        source_medium_derivative_sha256=None,
        source_processing_version=None,
        normalization_version=OCR_NORMALIZATION_VERSION,
        replay_of_ocr_result_id=replay_of_ocr_result_id,
        replay_reason=_trim_replay_reason(replay_reason),
        ocr_engine=OCR_ENGINE_NAME,
        ocr_engine_version=get_tesseract_engine_version(),
        processing_status="pending",
        raw_text="",
        normalized_text=None,
        confidence_score=None,
        processing_error=None,
        processed_at=None,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return cover_ocr_result_entity_to_read(row)


def get_cover_image_ocr_result_or_404(session: Session, ocr_result_id: int) -> CoverImageOcrResult:
    row = session.get(CoverImageOcrResult, ocr_result_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Cover image OCR result not found")
    return row


def mark_cover_image_ocr_processing_started(
    session: Session,
    *,
    ocr_result_id: int,
) -> CoverImageOcrResult:
    row = get_cover_image_ocr_result_or_404(session, ocr_result_id)
    row.processing_status = "processing"
    row.processing_error = None
    row.processing_started_at = _processing_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def mark_cover_image_ocr_processed(
    session: Session,
    *,
    ocr_result_id: int,
    raw_text: str,
    normalized_text: str | None,
    ocr_engine_version: str | None,
    normalization_version: str,
    confidence_score: float | None = None,
) -> CoverImageOcrResult:
    row = get_cover_image_ocr_result_or_404(session, ocr_result_id)
    row.ocr_engine = OCR_ENGINE_NAME
    row.ocr_engine_version = ocr_engine_version
    row.processing_status = "processed"
    row.raw_text = raw_text
    row.normalized_text = normalized_text
    row.confidence_score = confidence_score
    row.processing_error = None
    row.normalization_version = normalization_version
    row.processed_at = _processing_now()
    row.processing_started_at = None
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def mark_cover_image_ocr_failed(
    session: Session,
    *,
    ocr_result_id: int,
    error_message: str,
) -> CoverImageOcrResult:
    row = get_cover_image_ocr_result_or_404(session, ocr_result_id)
    row.ocr_engine = OCR_ENGINE_NAME
    row.processing_status = "failed"
    row.processing_error = error_message[:2000]
    row.processed_at = _processing_now()
    row.processing_started_at = None
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _set_matching_state(
    session: Session,
    *,
    cover: CoverImage,
    status: Literal["not_ready", "ready", "needs_review", "failed"],
    notes: str | None,
) -> CoverImage:
    cover.matching_status = status
    cover.matching_notes = notes[:2000] if notes else None
    cover.ready_for_matching_at = _processing_now() if status == "ready" else None
    session.add(cover)
    session.commit()
    session.refresh(cover)
    return cover


def get_cover_entity_for_processing_by_owner(
    session: Session,
    *,
    current_user: User,
    cover_image_id: int,
) -> CoverImage:
    cover = get_cover_entity_or_404(session, cover_image_id)
    if not user_can_download_cover(session, cover, current_user):
        raise HTTPException(status_code=404, detail="Cover image not found")
    return cover


def get_cover_entity_for_processing_by_ops_or_404(
    session: Session,
    *,
    cover_image_id: int,
) -> CoverImage:
    return get_cover_entity_or_404(session, cover_image_id)


def set_cover_image_processing_failed(
    session: Session,
    *,
    cover: CoverImage,
    error_message: str,
) -> CoverImage:
    cover.processing_status = "failed"
    cover.processing_error = error_message[:2000]
    session.add(cover)
    session.commit()
    session.refresh(cover)
    return cover


def mark_cover_image_processing_succeeded(
    session: Session,
    *,
    cover_image_id: int,
) -> CoverImage:
    cover = get_cover_entity_or_404(session, cover_image_id)
    processed_at = _processing_now()
    cover.processing_status = "processed"
    cover.processing_error = None
    cover.processed_at = processed_at
    if cover.metadata_refreshed_at is None:
        cover.metadata_refreshed_at = processed_at
    session.add(cover)
    session.commit()
    session.refresh(cover)
    return cover


def evaluate_cover_image_matching_readiness(
    session: Session,
    *,
    settings: Settings,
    cover_image_id: int,
) -> CoverImage:
    """Evaluate future P31 readiness using deterministic local rules only."""
    cover = get_cover_entity_or_404(session, cover_image_id)

    if cover.processing_status == "failed":
        return _set_matching_state(
            session,
            cover=cover,
            status="failed",
            notes=cover.processing_error or "Cover processing failed.",
        )

    try:
        _read_cover_source_bytes_verified(settings, cover)
    except ValueError as exc:
        return _set_matching_state(
            session,
            cover=cover,
            status="failed",
            notes=str(exc),
        )

    if cover.processing_status != "processed":
        return _set_matching_state(
            session,
            cover=cover,
            status="not_ready",
            notes="Cover processing has not completed.",
        )

    if cover.mime_type not in MIME_TO_SUFFIX:
        return _set_matching_state(
            session,
            cover=cover,
            status="needs_review",
            notes="Cover MIME type is unsupported for future matching preparation.",
        )

    if cover.image_width is None or cover.image_height is None:
        return _set_matching_state(
            session,
            cover=cover,
            status="needs_review",
            notes="Cover dimensions are missing.",
        )

    derivatives = session.exec(
        select(CoverImageDerivative).where(CoverImageDerivative.cover_image_id == cover_image_id)
    ).all()
    by_type = {row.derivative_type: row for row in derivatives}
    for derivative_type in ("thumb", "medium"):
        derivative = by_type.get(derivative_type)
        if derivative is None:
            return _set_matching_state(
                session,
                cover=cover,
                status="needs_review",
                notes=f"Missing required {derivative_type} derivative.",
            )
        abs_path = resolve_filesystem_path(settings, derivative.storage_path)
        if not abs_path.is_file():
            return _set_matching_state(
                session,
                cover=cover,
                status="needs_review",
                notes=f"Required {derivative_type} derivative file is missing on disk.",
            )

    return _set_matching_state(
        session,
        cover=cover,
        status="ready",
        notes=None,
    )


def validate_cover_image_ready_for_ocr(
    session: Session,
    *,
    settings: Settings,
    cover_image_id: int,
) -> CoverImage:
    cover = get_cover_entity_or_404(session, cover_image_id)
    if cover.matching_status != "ready":
        raise ValueError("Cover image matching readiness must be ready before OCR.")
    if cover.processing_status != "processed":
        raise ValueError("Cover image processing must be processed before OCR.")
    _read_cover_source_bytes_verified(settings, cover)
    return cover


def _crop_box_for_region(
    *,
    region_type: str,
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    def _clamp_box(left: float, top: float, right: float, bottom: float) -> tuple[int, int, int, int]:
        x0 = max(0, min(width - 1, int(round(left))))
        y0 = max(0, min(height - 1, int(round(top))))
        x1 = max(x0 + 1, min(width, int(round(right))))
        y1 = max(y0 + 1, min(height, int(round(bottom))))
        return x0, y0, x1, y1

    if region_type == "full_cover":
        return 0, 0, width, height
    if region_type == "title_region":
        return _clamp_box(0, 0, width, height * 0.25)
    if region_type == "issue_region":
        return _clamp_box(width * 0.68, 0, width, height * 0.22)
    if region_type == "publisher_region":
        return _clamp_box(0, 0, width * 0.35, height * 0.18)
    if region_type == "barcode_region":
        return _clamp_box(width * 0.72, height * 0.78, width, height)
    if region_type == "lower_text_region":
        return _clamp_box(0, height * 0.8, width, height)
    raise ValueError(f"Unsupported OCR region type: {region_type}")


def render_cover_ocr_region_bytes(
    source_body: bytes,
    *,
    region_type: str,
) -> tuple[bytes, int, int, str]:
    output_format, mime_type, _, save_kwargs = _derivative_output_spec()
    with Image.open(io.BytesIO(source_body)) as img:
        working = img.convert("RGBA" if "transparency" in img.info else "RGB")
        left, top, right, bottom = _crop_box_for_region(
            region_type=region_type,
            width=int(working.width),
            height=int(working.height),
        )
        cropped = working.crop((left, top, right, bottom))
        buffer = io.BytesIO()
        cropped.save(buffer, format=output_format, **save_kwargs)
        payload = buffer.getvalue()
        return payload, int(cropped.width), int(cropped.height), mime_type


def get_cover_ocr_region_or_404(
    session: Session,
    *,
    cover_image_id: int,
    region_type: str,
) -> CoverImageOcrRegion:
    row = session.exec(
        select(CoverImageOcrRegion).where(
            CoverImageOcrRegion.cover_image_id == cover_image_id,
            CoverImageOcrRegion.region_type == region_type,
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Cover image OCR region not found")
    return row


def _region_source_for_cover(
    session: Session,
    *,
    settings: Settings,
    cover_image_id: int,
) -> tuple[bytes, int | None]:
    medium = session.exec(
        select(CoverImageDerivative).where(
            CoverImageDerivative.cover_image_id == cover_image_id,
            CoverImageDerivative.derivative_type == "medium",
        )
    ).first()
    if medium is not None:
        medium_path = resolve_filesystem_path(settings, medium.storage_path)
        if medium_path.is_file():
            return medium_path.read_bytes(), medium.id
    cover = get_cover_entity_or_404(session, cover_image_id)
    return _read_cover_source_bytes_verified(settings, cover), None


def generate_cover_image_ocr_region(
    session: Session,
    *,
    settings: Settings,
    cover_image_id: int,
    region_type: str,
) -> CoverImageOcrRegionRead:
    if region_type not in OCR_REGION_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported OCR region type")
    source_body, derivative_id = _region_source_for_cover(
        session,
        settings=settings,
        cover_image_id=cover_image_id,
    )
    region_bytes, width, height, mime_type = render_cover_ocr_region_bytes(
        source_body,
        region_type=region_type,
    )
    sha = sha256_raw_bytes(region_bytes)
    _, _, extension, _ = _derivative_output_spec()
    storage_path = deterministic_ocr_region_storage_path(cover_image_id, region_type, extension)
    abs_path = resolve_filesystem_path(settings, storage_path)
    atomic_write_bytes(abs_path, region_bytes)

    row = session.exec(
        select(CoverImageOcrRegion).where(
            CoverImageOcrRegion.cover_image_id == cover_image_id,
            CoverImageOcrRegion.region_type == region_type,
        )
    ).first()
    if row is None:
        row = CoverImageOcrRegion(
            cover_image_id=cover_image_id,
            derivative_id=derivative_id,
            region_type=region_type,
            storage_path=storage_path,
            mime_type=mime_type,
            image_width=width,
            image_height=height,
            file_size=len(region_bytes),
            sha256_hash=sha,
            extraction_version=OCR_REGION_EXTRACTION_VERSION,
        )
    row.derivative_id = derivative_id
    row.storage_path = storage_path
    row.mime_type = mime_type
    row.image_width = width
    row.image_height = height
    row.file_size = len(region_bytes)
    row.sha256_hash = sha
    row.extraction_version = OCR_REGION_EXTRACTION_VERSION
    session.add(row)
    session.commit()
    session.refresh(row)
    return cover_ocr_region_entity_to_read(row)


def ensure_cover_image_ocr_regions(
    session: Session,
    *,
    settings: Settings,
    cover_image_id: int,
) -> list[CoverImageOcrRegionRead]:
    regions: list[CoverImageOcrRegionRead] = []
    for region_type in OCR_REGION_TYPES:
        regions.append(
            generate_cover_image_ocr_region(
                session,
                settings=settings,
                cover_image_id=cover_image_id,
                region_type=region_type,
            )
        )
    return regions


def extract_cover_image_ocr_regions_for_owner(
    session: Session,
    *,
    settings: Settings,
    current_user: User,
    cover_image_id: int,
) -> CoverImageOcrRegionExtractResponse:
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )
    regions = ensure_cover_image_ocr_regions(
        session,
        settings=settings,
        cover_image_id=cover_image_id,
    )
    return CoverImageOcrRegionExtractResponse(
        cover_image_id=cover_image_id,
        region_count=len(regions),
        regions=regions,
    )


def extract_cover_image_ocr_regions_for_ops(
    session: Session,
    *,
    settings: Settings,
    cover_image_id: int,
) -> CoverImageOcrRegionExtractResponse:
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=cover_image_id)
    regions = ensure_cover_image_ocr_regions(
        session,
        settings=settings,
        cover_image_id=cover_image_id,
    )
    return CoverImageOcrRegionExtractResponse(
        cover_image_id=cover_image_id,
        region_count=len(regions),
        regions=regions,
    )


def run_cover_image_ocr(
    session: Session,
    *,
    settings: Settings,
    cover_image_id: int,
    ocr_result_id: int,
) -> CoverImageOcrResult:
    row = get_cover_image_ocr_result_or_404(session, ocr_result_id)
    if row.cover_image_id != cover_image_id:
        raise ValueError("OCR result row does not belong to the requested cover image.")
    persist_cover_image_ocr_source_snapshot(
        session,
        ocr_result_id=ocr_result_id,
        cover_image_id=cover_image_id,
    )
    cover = validate_cover_image_ready_for_ocr(
        session,
        settings=settings,
        cover_image_id=cover_image_id,
    )
    mark_cover_image_ocr_processing_started(session, ocr_result_id=ocr_result_id)
    abs_path = resolve_filesystem_path(settings, cover.storage_path)
    body = Path(abs_path).read_bytes()
    validate_pipeline_image_bytes(
        settings=settings,
        body=body,
        mime_type=cover.mime_type,
        declared_width=cover.image_width,
        declared_height=cover.image_height,
        stage="cover_ocr_preprocess",
    )
    raw_text = _run_tesseract_ocr_with_test_compat(
        abs_path,
        timeout_seconds=float(settings.cover_ocr_tesseract_timeout_seconds),
    )
    max_chars = int(settings.cover_ocr_max_raw_text_chars)
    if len(raw_text) > max_chars:
        raw_text = raw_text[:max_chars]
    normalized_text = normalize_ocr_text(raw_text)
    return mark_cover_image_ocr_processed(
        session,
        ocr_result_id=ocr_result_id,
        raw_text=raw_text,
        normalized_text=normalized_text,
        ocr_engine_version=get_tesseract_engine_version(),
        normalization_version=OCR_NORMALIZATION_VERSION,
        confidence_score=None,
    )


def refresh_cover_image_file_metadata(
    session: Session,
    *,
    settings: Settings,
    cover_image_id: int,
) -> CoverImage:
    """Refresh file-derived cover metadata only; never mutates linkage or primary pointers."""
    cover = get_cover_entity_or_404(session, cover_image_id)
    cover.processing_status = "processing"
    cover.processing_error = None
    session.add(cover)
    session.commit()

    try:
        body = _read_cover_source_bytes_verified(settings, cover)
        validate_pipeline_image_bytes(
            settings=settings,
            body=body,
            mime_type=cover.mime_type,
            declared_width=cover.image_width,
            declared_height=cover.image_height,
            stage="cover_metadata_refresh",
        )
    except ValueError as exc:
        msg = structured_error_to_persistent(classify_exception(exc, stage="cover_metadata_refresh"))
        return set_cover_image_processing_failed(
            session,
            cover=cover,
            error_message=msg,
        )

    try:
        width, height, mime_type = extract_image_dimensions_and_mime(body, cover.mime_type)
    except HTTPException as exc:
        msg = structured_error_to_persistent(
            classify_exception(ValueError(str(exc.detail)), stage="cover_metadata_refresh_dimensions")
        )
        return set_cover_image_processing_failed(
            session,
            cover=cover,
            error_message=msg,
        )

    refreshed_at = _processing_now()
    cover.image_width = width
    cover.image_height = height
    cover.mime_type = mime_type
    cover.file_size = len(body)
    cover.processing_status = "processing"
    cover.processing_error = None
    cover.metadata_refreshed_at = refreshed_at
    session.add(cover)
    session.commit()
    session.refresh(cover)
    return cover


def get_cover_derivative_or_404(
    session: Session,
    *,
    cover_image_id: int,
    derivative_type: Literal["thumb", "medium"],
) -> CoverImageDerivative:
    row = session.exec(
        select(CoverImageDerivative).where(
            CoverImageDerivative.cover_image_id == cover_image_id,
            CoverImageDerivative.derivative_type == derivative_type,
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Cover image derivative not found")
    return row


def serialize_cover_image_read(session: Session, cover: CoverImage) -> CoverImageRead:
    primary_cover_image_id: int | None = None
    if cover.inventory_copy_id is not None:
        inv = session.get(InventoryCopy, cover.inventory_copy_id)
        primary_cover_image_id = inv.primary_cover_image_id if inv is not None else None
    elif cover.draft_import_id is not None:
        draft = session.get(DraftImport, cover.draft_import_id)
        primary_cover_image_id = draft.primary_cover_image_id if draft is not None else None
    derivatives = list_cover_derivative_reads_for_cover(session, cover.id or -1)
    ocr_regions = list_cover_ocr_region_reads_for_cover(session, cover.id or -1)
    ocr_candidates = list_cover_ocr_candidate_reads_for_cover(session, cover.id or -1)
    barcode_candidates = list_cover_barcode_candidate_reads_for_cover(session, cover.id or -1)
    fingerprints = list_cover_fingerprint_reads_for_cover(session, cover.id or -1)
    ocr_quality_analyses = list_cover_ocr_quality_analysis_reads_for_cover(session, cover.id or -1)
    match_candidates = list_cover_match_candidate_reads_for_cover(session, cover.id or -1)
    ocr_reconciliation_warnings = list_cover_image_ocr_reconciliation_warnings(session, cover_image_id=cover.id or -1)
    latest_ocr_result = _latest_ocr_result_reads_by_cover_id(session, [cover.id or -1]).get(cover.id or -1)
    ocr_visibility = compute_cover_image_ocr_visibility(session, cover)
    return cover_entity_to_read(
        cover,
        primary_cover_image_id=primary_cover_image_id,
        derivatives=derivatives,
        latest_ocr_result=latest_ocr_result,
        ocr_visibility=ocr_visibility,
        ocr_regions=ocr_regions,
        ocr_candidates=ocr_candidates,
        barcode_candidates=barcode_candidates,
        fingerprints=fingerprints,
        ocr_quality_analyses=ocr_quality_analyses,
        match_candidates=match_candidates,
        ocr_reconciliation_warnings=ocr_reconciliation_warnings,
    )


def generate_cover_image_derivative(
    session: Session,
    *,
    settings: Settings,
    cover_image_id: int,
    derivative_type: Literal["thumb", "medium"],
) -> CoverImageDerivativeRead:
    cover = get_cover_entity_or_404(session, cover_image_id)
    existing = session.exec(
        select(CoverImageDerivative).where(
            CoverImageDerivative.cover_image_id == cover_image_id,
            CoverImageDerivative.derivative_type == derivative_type,
        )
    ).first()
    source_body = _read_cover_source_bytes_verified(settings, cover)
    validate_pipeline_image_bytes(
        settings=settings,
        body=source_body,
        mime_type=cover.mime_type,
        declared_width=cover.image_width,
        declared_height=cover.image_height,
        stage="derivative_generation",
    )

    if existing is not None:
        existing_abs_path = resolve_filesystem_path(settings, existing.storage_path)
        if existing_abs_path.is_file():
            return cover_derivative_entity_to_read(existing)

    derivative_bytes, width, height, mime_type = render_cover_derivative_bytes(
        source_body,
        derivative_type=derivative_type,
    )
    derivative_sha = sha256_raw_bytes(derivative_bytes)
    _, _, extension, _ = _derivative_output_spec()
    storage_path = deterministic_derivative_storage_path(cover_image_id, derivative_type, extension)
    abs_path = resolve_filesystem_path(settings, storage_path)
    atomic_write_bytes(abs_path, derivative_bytes)

    row = existing or CoverImageDerivative(
        cover_image_id=cover_image_id,
        derivative_type=derivative_type,
        storage_path=storage_path,
        mime_type=mime_type,
        image_width=width,
        image_height=height,
        file_size=len(derivative_bytes),
        sha256_hash=derivative_sha,
    )
    row.storage_path = storage_path
    row.mime_type = mime_type
    row.image_width = width
    row.image_height = height
    row.file_size = len(derivative_bytes)
    row.sha256_hash = derivative_sha
    row.generated_at = _processing_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return cover_derivative_entity_to_read(row)


def ensure_cover_image_derivatives(
    session: Session,
    *,
    settings: Settings,
    cover_image_id: int,
) -> list[CoverImageDerivativeRead]:
    generated: list[CoverImageDerivativeRead] = []
    for derivative_type in ("thumb", "medium"):
        generated.append(
            generate_cover_image_derivative(
                session,
                settings=settings,
                cover_image_id=cover_image_id,
                derivative_type=derivative_type,
            )
        )
    return generated


def _cover_link_targets(cover: CoverImage) -> tuple[bool, bool]:
    has_inv = cover.inventory_copy_id is not None
    has_draft = cover.draft_import_id is not None
    return has_inv, has_draft


def resolve_cover_lineage_owner_user_id(session: Session, cover: CoverImage) -> int | None:
    """User who owns this cover row via inventory copy or draft import."""
    inv_id = cover.inventory_copy_id
    if inv_id is not None:
        uid = session.exec(select(InventoryCopy.user_id).where(InventoryCopy.id == inv_id)).first()
        return uid
    draft_id = cover.draft_import_id
    if draft_id is not None:
        uid = session.exec(select(DraftImport.user_id).where(DraftImport.id == draft_id)).first()
        return uid
    return None


def _assert_singleton_cover_linkage(cover: CoverImage) -> None:
    has_inv, has_draft = _cover_link_targets(cover)
    if not has_inv and not has_draft:
        raise HTTPException(
            status_code=422,
            detail="Cover image has no linkage; cannot change assignment.",
        )
    if has_inv and has_draft:
        raise HTTPException(
            status_code=422,
            detail="Cover image linkage is ambiguous; refusing assignment.",
        )


def assign_existing_cover_image_to_inventory_copy(
    session: Session,
    *,
    settings: Settings,
    current_user: User,
    inventory_copy_id: int,
    cover_image_id: int,
    set_primary: bool = False,
) -> CoverImageRead:
    """Point an existing ``CoverImage`` row at ``inventory_copy_id`` (DB linkage only).

    Clearing ``draft_import_id`` removes the scan from draft/import listings; storage_path and hashes
    are unchanged.
    """
    caller_ops = is_ops_admin_user(current_user, settings)
    cover = get_cover_entity_or_404(session, cover_image_id)
    _assert_singleton_cover_linkage(cover)

    lineage_owner_id = resolve_cover_lineage_owner_user_id(session, cover)
    inventory = session.get(InventoryCopy, inventory_copy_id)
    if inventory is None:
        raise HTTPException(status_code=404, detail="Inventory copy not found")

    if not caller_ops:
        if inventory.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Inventory copy not found")
        if lineage_owner_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Cover image belongs to another account.",
            )

    old_inventory_id = cover.inventory_copy_id
    old_draft_id = cover.draft_import_id

    if (
        lineage_owner_id is not None
        and inventory.user_id != lineage_owner_id
        and not caller_ops
    ):
        raise HTTPException(
            status_code=422,
            detail="Cover image owner must match the target inventory owner.",
        )

    if old_inventory_id is not None and old_inventory_id != inventory_copy_id:
        old_inv = session.get(InventoryCopy, old_inventory_id)
        if old_inv is not None and old_inv.primary_cover_image_id == cover_image_id:
            old_inv.primary_cover_image_id = None
            session.add(old_inv)

    if old_draft_id is not None:
        draft = session.get(DraftImport, old_draft_id)
        if draft is not None and draft.primary_cover_image_id == cover_image_id:
            draft.primary_cover_image_id = None
            session.add(draft)

    cover.inventory_copy_id = inventory_copy_id
    cover.draft_import_id = None
    session.add(cover)

    refreshed_inv = session.get(InventoryCopy, inventory_copy_id)
    if refreshed_inv is None:
        raise HTTPException(status_code=500, detail="Inventory copy missing after linkage update.")

    if set_primary:
        refreshed_inv.primary_cover_image_id = cover_image_id
        session.add(refreshed_inv)

    session.commit()
    session.refresh(cover)
    session.refresh(refreshed_inv)

    return serialize_cover_image_read(session, cover)


def return_cover_image_to_draft_import(
    session: Session,
    *,
    settings: Settings,
    current_user: User,
    cover_image_id: int,
    draft_import_id: int,
    set_primary: bool = False,
) -> CoverImageRead:
    """Move linkage from inventory back to ``draft_import_id`` (still the same blob row).

    Clears inventory primary pointer when applicable; clears ``inventory_copy_id`` and sets draft FK.
    """
    caller_ops = is_ops_admin_user(current_user, settings)
    cover = get_cover_entity_or_404(session, cover_image_id)
    if cover.inventory_copy_id is None:
        raise HTTPException(
            status_code=422,
            detail="Cover image is not linked to inventory; cannot return to draft/import.",
        )
    inventory = session.get(InventoryCopy, cover.inventory_copy_id)
    draft = session.get(DraftImport, draft_import_id)
    if inventory is None:
        raise HTTPException(status_code=404, detail="Cover image not found")
    if draft is None:
        raise HTTPException(status_code=404, detail="Import not found")

    if not caller_ops:
        if inventory.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Cover image not found")
        if draft.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Import not found")
        if draft.user_id != inventory.user_id:
            raise HTTPException(
                status_code=422,
                detail="Draft import owner must match the inventory copy owner.",
            )

    lineage_owner_id = resolve_cover_lineage_owner_user_id(session, cover)
    if (
        not caller_ops
        and lineage_owner_id is not None
        and lineage_owner_id != draft.user_id
    ):
        raise HTTPException(status_code=403, detail="Cover image belongs to another account.")

    if inventory.primary_cover_image_id == cover_image_id:
        inventory.primary_cover_image_id = None
        session.add(inventory)

    cover.inventory_copy_id = None
    cover.draft_import_id = draft_import_id
    session.add(cover)

    if set_primary:
        draft.primary_cover_image_id = cover_image_id

    session.add(draft)

    session.commit()
    session.refresh(cover)
    session.refresh(draft)

    return serialize_cover_image_read(session, cover)


COVER_CARRY_MULTI_COPY_NOTICE = (
    "This order produced multiple inventory copies. Import-level cover scans were not linked to "
    "individual copies. Open this import history or assign scans manually on each inventory "
    "copy later."
)


def carry_draft_import_cover_images_to_inventory_copy(
    session: Session,
    *,
    draft_import: DraftImport,
    inventory_copy_id: int,
) -> None:
    """Re-point draft-linked covers onto a single inventory copy (confirm carryover).

    Updates DB linkage only; clears ``draft_import.primary_cover_image_id`` and copies primary
    to ``inventory_copy`` when it referenced a migrated cover row.
    """
    draft_pk = draft_import.id
    if draft_pk is None:
        return

    inv = session.get(InventoryCopy, inventory_copy_id)
    if inv is None:
        raise HTTPException(status_code=500, detail="Inventory copy missing during cover carryover.")
    if inv.user_id != draft_import.user_id:
        raise HTTPException(status_code=500, detail="Cover carryover invariant violated (user mismatch).")

    covers = session.exec(
        select(CoverImage).where(CoverImage.draft_import_id == draft_pk)
    ).all()
    if not covers:
        draft_import.primary_cover_image_id = None
        session.add(draft_import)
        return

    migrated_ids: set[int] = {cover.id for cover in covers if cover.id is not None}
    preserved_primary_on_draft = draft_import.primary_cover_image_id

    for cover in covers:
        cover.draft_import_id = None
        cover.inventory_copy_id = inventory_copy_id
        session.add(cover)

    draft_import.primary_cover_image_id = None
    session.add(draft_import)

    if preserved_primary_on_draft is not None and preserved_primary_on_draft in migrated_ids:
        inv.primary_cover_image_id = preserved_primary_on_draft

    session.add(inv)


def set_inventory_primary_cover_image(
    session: Session,
    *,
    current_user: User,
    inventory_copy_id: int,
    cover_image_id: int,
) -> CoverImageRead:
    inv = session.exec(
        select(InventoryCopy).where(
            InventoryCopy.id == inventory_copy_id,
            InventoryCopy.user_id == current_user.id,
        )
    ).first()
    if inv is None:
        raise HTTPException(status_code=404, detail="Inventory copy not found")
    cover = session.get(CoverImage, cover_image_id)
    if cover is None or cover.inventory_copy_id != inventory_copy_id:
        raise HTTPException(status_code=404, detail="Cover image not found")
    inv.primary_cover_image_id = cover_image_id
    session.add(inv)
    session.commit()
    session.refresh(inv)
    session.refresh(cover)
    return serialize_cover_image_read(session, cover)


def set_draft_import_primary_cover_image(
    session: Session,
    *,
    current_user: User,
    draft_import_id: int,
    cover_image_id: int,
) -> CoverImageRead:
    draft = session.exec(
        select(DraftImport).where(
            DraftImport.id == draft_import_id,
            DraftImport.user_id == current_user.id,
        )
    ).first()
    if draft is None:
        raise HTTPException(status_code=404, detail="Import not found")
    cover = session.get(CoverImage, cover_image_id)
    if cover is None or cover.draft_import_id != draft_import_id:
        raise HTTPException(status_code=404, detail="Cover image not found")
    draft.primary_cover_image_id = cover_image_id
    session.add(draft)
    session.commit()
    session.refresh(draft)
    session.refresh(cover)
    return serialize_cover_image_read(session, cover)


def _duplicate_cover_visibility_predicates(
    *,
    source_type: str | None,
    linkage: Literal["inventory", "import", "unlinked"] | None,
) -> list:
    predicates: list = [
        CoverImage.sha256_hash.is_not(None),
        CoverImage.sha256_hash != "",
    ]
    trimmed = (source_type or "").strip()
    if trimmed:
        predicates.append(CoverImage.source_type == trimmed)

    if linkage == "inventory":
        predicates.append(CoverImage.inventory_copy_id.is_not(None))
    elif linkage == "import":
        predicates.append(CoverImage.draft_import_id.is_not(None))
    elif linkage == "unlinked":
        predicates.append(
            and_(CoverImage.inventory_copy_id.is_(None), CoverImage.draft_import_id.is_(None))
        )
    return predicates


def _owner_user_id_for_duplicate_ops_join():
    """Resolve owner user id when a cover is inventory- or draft-linked (orphans → NULL)."""
    return case(
        (CoverImage.inventory_copy_id.is_not(None), InventoryCopy.user_id),
        (CoverImage.draft_import_id.is_not(None), DraftImport.user_id),
        else_=None,
    )


def list_duplicate_cover_image_groups_for_ops(
    session: Session,
    *,
    min_count: int = 2,
    limit: int = 50,
    source_type: str | None = None,
    linkage: Literal["inventory", "import", "unlinked"] | None = None,
) -> list[OpsCoverDuplicateGroup]:
    """Return SHA-256 duplicate groups (≥ min_count rows); read-only aggregation, no row updates."""
    min_c = max(2, min(min_count, 500))
    lim = max(1, min(limit, 100))
    predicates = _duplicate_cover_visibility_predicates(source_type=source_type, linkage=linkage)

    count_label = func.count(CoverImage.id).label("row_count")
    grouped = (
        select(CoverImage.sha256_hash, count_label)
        .where(and_(*predicates))
        .group_by(CoverImage.sha256_hash)
        .having(func.count(CoverImage.id) >= min_c)
    ).subquery()

    hash_ranked = (
        select(grouped.c.sha256_hash, grouped.c.row_count)
        .order_by(grouped.c.row_count.desc(), grouped.c.sha256_hash.asc())
        .limit(lim)
    )
    hash_rows = session.exec(hash_ranked).all()
    if not hash_rows:
        return []

    hashes = [row[0] for row in hash_rows]
    count_by_hash = {row[0]: int(row[1]) for row in hash_rows}

    owner_uid = _owner_user_id_for_duplicate_ops_join()
    combined_predicates = [*predicates, CoverImage.sha256_hash.in_(hashes)]
    detail_stmt = (
        select(
            CoverImage,
            User.email.label("owner_email"),
            InventoryCopy.primary_cover_image_id.label("inv_primary_cover_image_id"),
            DraftImport.primary_cover_image_id.label("draft_primary_cover_image_id"),
        )
        .select_from(CoverImage)
        .outerjoin(InventoryCopy, CoverImage.inventory_copy_id == InventoryCopy.id)
        .outerjoin(DraftImport, CoverImage.draft_import_id == DraftImport.id)
        .outerjoin(User, User.id == owner_uid)
        .where(and_(*combined_predicates))
        .order_by(CoverImage.sha256_hash, CoverImage.created_at.desc())
    )
    detail_rows = session.exec(detail_stmt).all()
    derivatives_by_cover_id = _derivative_reads_by_cover_id(
        session,
        [cover.id for cover, _, _, _ in detail_rows if cover.id is not None],
    )
    covers_for_batch = [cover for cover, _, _, _ in detail_rows if cover.id is not None]
    latest_ocr_by_cover_id = _latest_ocr_result_reads_by_cover_id(
        session,
        [cover.id for cover in covers_for_batch],
    )
    ocr_visibility_by_cover_id = compute_cover_images_ocr_visibility_batch(
        session,
        covers_for_batch,
    )

    by_hash: dict[str, list[OpsCoverDuplicateMember]] = {h: [] for h in hashes}
    for cover, owner_email, inv_pri, draft_pri in detail_rows:
        if cover.id is None:
            continue
        parent_primary = (
            inv_pri if cover.inventory_copy_id is not None else draft_pri
        )
        is_primary = parent_primary is not None and cover.id == parent_primary
        derivatives = derivatives_by_cover_id.get(cover.id, [])
        thumbnail_fetch_path, medium_fetch_path = _derivative_paths(derivatives)
        by_hash[cover.sha256_hash].append(
            OpsCoverDuplicateMember(
                id=cover.id,
                source_type=cover.source_type,
                original_filename=cover.original_filename,
                inventory_copy_id=cover.inventory_copy_id,
                draft_import_id=cover.draft_import_id,
                canonical_series_id=cover.canonical_series_id,
                is_primary=is_primary,
                created_at=cover.created_at,
                file_size=cover.file_size,
                image_width=cover.image_width,
                image_height=cover.image_height,
                owner_email=str(owner_email) if owner_email is not None else None,
                matching_status=cover.matching_status,
                matching_notes=cover.matching_notes,
                ready_for_matching_at=cover.ready_for_matching_at,
                thumbnail_fetch_path=thumbnail_fetch_path,
                medium_fetch_path=medium_fetch_path,
                derivatives=derivatives,
                fetch_path=cover_fetch_path(cover.id),
                latest_ocr_result=latest_ocr_by_cover_id.get(cover.id),
                ocr_visibility=ocr_visibility_by_cover_id[cover.id],
            )
        )

    out: list[OpsCoverDuplicateGroup] = []
    for sha in hashes:
        members = by_hash.get(sha, [])
        out.append(
            OpsCoverDuplicateGroup(
                sha256_hash=sha,
                count=count_by_hash[sha],
                covers=members,
            )
        )
    return out


def list_recent_cover_uploads_for_ops(
    session: Session,
    *,
    limit: int = 50,
    source_type: str | None = None,
    linkage: Literal["inventory", "import"] | None = None,
    matching_status: Literal["not_ready", "ready", "needs_review", "failed"] | None = None,
) -> list[OpsCoverImageRecentRow]:
    capped = max(1, min(limit, 100))
    owner_uid = _owner_id_expression()

    predicates = [
        or_(
            CoverImage.inventory_copy_id.is_not(None),
            CoverImage.draft_import_id.is_not(None),
        )
    ]
    trimmed_source = (source_type or "").strip()
    if trimmed_source:
        predicates.append(CoverImage.source_type == trimmed_source)
    if matching_status is not None:
        predicates.append(CoverImage.matching_status == matching_status)

    if linkage == "inventory":
        predicates.append(CoverImage.inventory_copy_id.is_not(None))
    elif linkage == "import":
        predicates.append(CoverImage.draft_import_id.is_not(None))

    stmt = (
        select(
            CoverImage,
            User.email.label("owner_email"),
            InventoryCopy.primary_cover_image_id.label("inv_primary_cover_image_id"),
            DraftImport.primary_cover_image_id.label("draft_primary_cover_image_id"),
        )
        .select_from(CoverImage)
        .outerjoin(InventoryCopy, CoverImage.inventory_copy_id == InventoryCopy.id)
        .outerjoin(DraftImport, CoverImage.draft_import_id == DraftImport.id)
        .join(User, owner_uid == User.id)
        .where(and_(*predicates))
        .order_by(CoverImage.created_at.desc())
        .limit(capped)
    )
    rows = session.exec(stmt).all()
    derivatives_by_cover_id = _derivative_reads_by_cover_id(
        session,
        [cover.id for cover, _, _, _ in rows if cover.id is not None],
    )
    latest_ocr_by_cover_id = _latest_ocr_result_reads_by_cover_id(
        session,
        [cover.id for cover, _, _, _ in rows if cover.id is not None],
    )
    cover_batch = [cover for cover, _, _, _ in rows if cover.id is not None]
    ocr_visibility_by_cover_id = compute_cover_images_ocr_visibility_batch(session, cover_batch)
    ocr_region_count_by_cover_id = _ocr_region_count_by_cover_id(
        session,
        [cover.id for cover in cover_batch],
    )
    ocr_candidate_count_by_cover_id = _ocr_candidate_count_by_cover_id(
        session,
        [cover.id for cover in cover_batch],
    )
    barcode_candidate_count_by_cover_id = _barcode_candidate_count_by_cover_id(
        session,
        [cover.id for cover in cover_batch],
    )
    fingerprint_count_by_cover_id = _fingerprint_count_by_cover_id(
        session,
        [cover.id for cover in cover_batch],
    )
    ocr_quality_analysis_count_by_cover_id = _ocr_quality_analysis_count_by_cover_id(
        session,
        [cover.id for cover in cover_batch],
    )
    ocr_candidate_review_counts_by_cover_id = _ocr_candidate_review_counts_by_cover_id(
        session,
        [cover.id for cover in cover_batch],
    )
    barcode_candidate_review_counts_by_cover_id = _barcode_candidate_review_counts_by_cover_id(
        session,
        [cover.id for cover in cover_batch],
    )
    match_candidate_count_by_cover_id = _cover_match_candidate_count_by_cover_id(
        session,
        [cover.id for cover in cover_batch],
    )
    open_match_candidate_count_by_cover_id = _open_cover_match_candidate_count_by_cover_id(
        session,
        [cover.id for cover in cover_batch],
    )
    match_candidates_by_cover_id = _match_candidate_reads_by_cover_id(
        session,
        [cover.id for cover in cover_batch],
    )
    ocr_quality_analyses_by_cover_id = _ocr_quality_analysis_reads_by_cover_id(
        session,
        [cover.id for cover in cover_batch],
    )
    ocr_reconciliation_warning_counts_by_cover_id = _ocr_reconciliation_warning_counts_by_cover_id(
        session,
        [cover.id for cover in cover_batch],
    )
    out: list[OpsCoverImageRecentRow] = []
    for cover, owner_email, inv_pri, draft_pri in rows:
        parent_primary = (
            inv_pri if cover.inventory_copy_id is not None else draft_pri
        )
        is_primary = parent_primary is not None and cover.id == parent_primary
        derivatives = derivatives_by_cover_id.get(cover.id or -1, [])
        thumbnail_fetch_path, medium_fetch_path = _derivative_paths(derivatives)
        review_totals = ocr_candidate_review_counts_by_cover_id.get(cover.id, CoverImageOcrCandidateReviewCounts())
        barcode_review_totals = barcode_candidate_review_counts_by_cover_id.get(
            cover.id,
            CoverImageBarcodeCandidateReviewCounts(),
        )
        reconciliation_totals = ocr_reconciliation_warning_counts_by_cover_id.get(
            cover.id,
            CoverImageOcrReconciliationWarningCounts(),
        )
        out.append(
            OpsCoverImageRecentRow(
                id=cover.id,
                original_filename=cover.original_filename,
                source_type=cover.source_type,
                mime_type=cover.mime_type,
                image_width=cover.image_width,
                image_height=cover.image_height,
                file_size=cover.file_size,
                sha256_hash=cover.sha256_hash,
                processing_status=cover.processing_status,
                processing_error=cover.processing_error,
                processed_at=cover.processed_at,
                metadata_refreshed_at=cover.metadata_refreshed_at,
                matching_status=cover.matching_status,
                matching_notes=cover.matching_notes,
                ready_for_matching_at=cover.ready_for_matching_at,
                latest_ocr_result=latest_ocr_by_cover_id.get(cover.id or -1),
                ocr_visibility=ocr_visibility_by_cover_id[cover.id],  # type: ignore[literal-required]
                ocr_region_count=ocr_region_count_by_cover_id.get(cover.id, 0),
                ocr_candidate_count=ocr_candidate_count_by_cover_id.get(cover.id, 0),
                ocr_candidate_review_counts=review_totals,
                has_pending_ocr_candidate_review=review_totals.pending > 0,
                barcode_candidate_count=barcode_candidate_count_by_cover_id.get(cover.id, 0),
                barcode_candidate_review_counts=barcode_review_totals,
                fingerprint_count=fingerprint_count_by_cover_id.get(cover.id, 0),
                ocr_quality_analysis_count=ocr_quality_analysis_count_by_cover_id.get(cover.id, 0),
                ocr_quality_analyses=ocr_quality_analyses_by_cover_id.get(cover.id, []),
                match_candidate_count=match_candidate_count_by_cover_id.get(cover.id, 0),
                open_match_candidate_count=open_match_candidate_count_by_cover_id.get(cover.id, 0),
                match_candidates=match_candidates_by_cover_id.get(cover.id, []),
                ocr_reconciliation_warning_counts=reconciliation_totals,
                open_ocr_reconciliation_warning_count=reconciliation_totals.open,
                thumbnail_fetch_path=thumbnail_fetch_path,
                medium_fetch_path=medium_fetch_path,
                derivatives=derivatives,
                created_at=cover.created_at,
                inventory_copy_id=cover.inventory_copy_id,
                draft_import_id=cover.draft_import_id,
                canonical_series_id=cover.canonical_series_id,
                owner_email=str(owner_email) if owner_email is not None else None,
                is_primary=is_primary,
                fetch_path=cover_fetch_path(cover.id),
            )
        )
    return out
