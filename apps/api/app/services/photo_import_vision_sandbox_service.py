"""P100-24/25 pure GPT vision read (no catalog, no crop, no OCR)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.photo_import import PhotoImportImage
from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.services.photo_import_ai_recognition_service import RecognitionConfigError
from app.services.photo_import_storage_service import resolve_photo_import_storage_path
from app.services.gpt_comic_identification_prompts import (
    COMIC_IDENTIFICATION_SYSTEM,
    COMIC_IDENTIFICATION_USER,
)
from app.services.gpt_comic_vision_client import call_comic_vision

logger = logging.getLogger(__name__)

# Back-compat names for tests/docs
VISION_SANDBOX_SYSTEM = COMIC_IDENTIFICATION_SYSTEM
VISION_SANDBOX_USER = COMIC_IDENTIFICATION_USER


@dataclass
class VisionSandboxReadResult:
    publisher: str
    series: str
    issue_number: str | None
    issue_title: str
    variant_description: str
    year: str
    cover_date: str
    barcode: str
    confidence: float
    reasoning: str
    raw_response: dict[str, Any]
    raw_response_text: str
    possible_alternates: list[str] = field(default_factory=list)


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in out:
            out.append(text)
    return out


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_sandbox_payload(payload: dict[str, Any]) -> VisionSandboxReadResult:
    issue_raw = payload.get("issue_number")
    issue: str | None = None
    if issue_raw is not None and str(issue_raw).strip().lower() not in {"", "null", "none", "n/a"}:
        issue = _as_str(issue_raw)
    try:
        confidence = float(payload.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return VisionSandboxReadResult(
        publisher=_as_str(payload.get("publisher")),
        series=_as_str(payload.get("series")),
        issue_number=issue,
        issue_title=_as_str(payload.get("issue_title")),
        variant_description=_as_str(payload.get("variant_description")),
        year=_as_str(payload.get("year")),
        cover_date=_as_str(payload.get("cover_date")),
        barcode=_as_str(payload.get("barcode")),
        confidence=max(0.0, min(1.0, confidence)),
        reasoning=_as_str(payload.get("reasoning")),
        possible_alternates=_as_str_list(payload.get("possible_alternates")),
        raw_response=payload,
        raw_response_text="",
    )


def read_comic_with_gpt_vision(image_bytes: bytes, *, image_id: int) -> VisionSandboxReadResult:
    """Call OpenAI vision on the full uploaded image; no catalog or OCR."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise RecognitionConfigError("OpenAI API key is not configured (settings.openai_api_key is empty)")

    model = settings.photo_import_vision_sandbox_model
    logger.info(
        "photo_import.vision_sandbox.request image_id=%s model=%s image_bytes=%d",
        image_id,
        model,
        len(image_bytes),
    )
    parsed, api_payload, api_raw_text, model_used = call_comic_vision(
        image_bytes,
        model=model,
        api_key=settings.openai_api_key,
        log_context=f"photo_import image_id={image_id}",
    )
    result = _parse_sandbox_payload(parsed)
    result.raw_response = {"parsed": parsed, "openai_response": api_payload, "model_used": model_used}
    result.raw_response_text = api_raw_text
    logger.info(
        "photo_import.vision_sandbox.response image_id=%s model_used=%s series=%r issue=%r confidence=%.2f",
        image_id,
        model_used,
        result.series,
        result.issue_number,
        result.confidence,
    )
    return result


def persist_vision_read(
    session: Session,
    *,
    session_id: int,
    image_id: int,
    result: VisionSandboxReadResult,
) -> PhotoImportVisionRead:
    row = PhotoImportVisionRead(
        session_id=session_id,
        image_id=image_id,
        publisher=result.publisher[:256] or None,
        series=result.series[:512] or None,
        issue_number=result.issue_number[:64] if result.issue_number else None,
        issue_title=result.issue_title[:512] or None,
        variant_description=result.variant_description[:512] or None,
        year=result.year[:16] or None,
        cover_date=result.cover_date[:32] or None,
        barcode=result.barcode[:64] or None,
        confidence=result.confidence,
        reasoning=result.reasoning or None,
        possible_alternates=result.possible_alternates or None,
        raw_response=result.raw_response,
        raw_response_text=result.raw_response_text,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def run_vision_sandbox_for_image(session: Session, *, image_id: int) -> PhotoImportVisionRead | None:
    image = session.get(PhotoImportImage, image_id)
    if image is None:
        logger.warning("photo_import.vision_sandbox.image_missing image_id=%s", image_id)
        return None
    path = resolve_photo_import_storage_path(image.storage_path, image_id=image_id)
    if not path.is_file():
        logger.error("photo_import.vision_sandbox.file_missing image_id=%s path=%s", image_id, path)
        return None
    raw = path.read_bytes()
    try:
        result = read_comic_with_gpt_vision(raw, image_id=image_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("photo_import.vision_sandbox.failed image_id=%s error=%s", image_id, exc)
        raise
    return persist_vision_read(
        session,
        session_id=int(image.session_id),
        image_id=image_id,
        result=result,
    )


def latest_vision_read_for_image(session: Session, *, image_id: int) -> PhotoImportVisionRead | None:
    return session.exec(
        select(PhotoImportVisionRead)
        .where(PhotoImportVisionRead.image_id == image_id)
        .order_by(PhotoImportVisionRead.id.desc())
    ).first()


def vision_reads_for_session(session: Session, *, session_id: int) -> list[PhotoImportVisionRead]:
    return list(
        session.exec(
            select(PhotoImportVisionRead)
            .where(PhotoImportVisionRead.session_id == session_id)
            .order_by(PhotoImportVisionRead.id.asc())
        ).all()
    )


def backfill_missing_vision_reads_for_session(session: Session, *, session_id: int) -> int:
    """Create GPT vision reads for session photos that never got one (legacy catalog uploads)."""
    from app.models.photo_import import (
        IMAGE_STATUS_FAILED,
        IMAGE_STATUS_PROCESSED,
        IMAGE_STATUS_UPLOADED,
    )

    images = list(
        session.exec(
            select(PhotoImportImage)
            .where(PhotoImportImage.session_id == session_id)
            .order_by(PhotoImportImage.id.asc())
        ).all()
    )
    created = 0
    for image in images:
        image_id = int(image.id or 0)
        if latest_vision_read_for_image(session, image_id=image_id) is not None:
            continue
        if image.status not in {IMAGE_STATUS_PROCESSED, IMAGE_STATUS_FAILED, IMAGE_STATUS_UPLOADED}:
            continue
        try:
            run_vision_sandbox_for_image(session, image_id=image_id)
            image = session.get(PhotoImportImage, image_id)
            if image is not None:
                image.status = IMAGE_STATUS_PROCESSED
                session.add(image)
                session.commit()
            created += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "photo_import.vision_read.backfill_failed image_id=%s error=%s",
                image_id,
                exc,
            )
    if created:
        from app.services.photo_import_session_service import refresh_session_counts

        refresh_session_counts(session, session_id=session_id)
    return created
