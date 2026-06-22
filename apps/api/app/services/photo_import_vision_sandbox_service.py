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
from app.services.comic_vision_read_mode import ComicVisionReadMode, normalize_vision_read_mode, resolve_vision_profile
from app.services.gpt_comic_vision_client import call_comic_vision

logger = logging.getLogger(__name__)

# Back-compat names for tests/docs
from app.services.gpt_comic_identification_prompts import (
    COMIC_IDENTIFICATION_SYSTEM,
    COMIC_IDENTIFICATION_USER,
)

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


def _extract_comics_payloads(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize the model output into a list of per-book dicts.

    Multi-book schema returns ``{"comics": [...]}``. For back-compat we also accept
    a single top-level object (older single-comic schema) and wrap it.
    """
    comics = parsed.get("comics")
    if isinstance(comics, list):
        books = [item for item in comics if isinstance(item, dict)]
        return books
    # Back-compat: a single flat object.
    if any(parsed.get(key) for key in ("series", "publisher", "issue_number", "issue_title")):
        return [parsed]
    return []


def read_comics_with_gpt_vision(
    image_bytes: bytes,
    *,
    image_id: int,
    mode: ComicVisionReadMode | str = ComicVisionReadMode.QUICK,
) -> list[VisionSandboxReadResult]:
    """Call OpenAI vision once and return one result per distinct comic in the photo."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise RecognitionConfigError("OpenAI API key is not configured (settings.openai_api_key is empty)")

    read_mode = normalize_vision_read_mode(mode.value if isinstance(mode, ComicVisionReadMode) else str(mode))
    profile = resolve_vision_profile(settings, read_mode)
    model = str(profile["model"])
    logger.info(
        "photo_import.vision_sandbox.request image_id=%s mode=%s model=%s image_bytes=%d",
        image_id,
        read_mode.value,
        model,
        len(image_bytes),
    )
    parsed, api_payload, api_raw_text, model_used = call_comic_vision(
        image_bytes,
        model=model,
        api_key=settings.openai_api_key,
        log_context=f"photo_import image_id={image_id} mode={read_mode.value}",
        system=str(profile["system"]),
        user=str(profile["user"]),
        image_detail=str(profile["image_detail"]),
        max_image_side_px=int(profile["max_image_side_px"]),
    )
    raw_response = {
        "parsed": parsed,
        "openai_response": api_payload,
        "model_used": model_used,
        "vision_mode": read_mode.value,
    }
    books = _extract_comics_payloads(parsed)
    results: list[VisionSandboxReadResult] = []
    for book in books:
        result = _parse_sandbox_payload(book)
        result.raw_response = raw_response
        result.raw_response_text = api_raw_text
        results.append(result)
    logger.info(
        "photo_import.vision_sandbox.response image_id=%s model_used=%s books=%d",
        image_id,
        model_used,
        len(results),
    )
    return results


def read_comic_with_gpt_vision(image_bytes: bytes, *, image_id: int) -> VisionSandboxReadResult:
    """Single-book read (back-compat): returns the first detected comic.

    Raises if the model found no comic in the image.
    """
    results = read_comics_with_gpt_vision(image_bytes, image_id=image_id)
    if not results:
        raise RecognitionConfigError("GPT vision returned no comics for this image")
    return results[0]


def persist_vision_read(
    session: Session,
    *,
    session_id: int,
    image_id: int,
    result: VisionSandboxReadResult,
    detection_index: int = 0,
    run_match: bool = True,
) -> PhotoImportVisionRead:
    row = PhotoImportVisionRead(
        session_id=session_id,
        image_id=image_id,
        detection_index=detection_index,
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
    session.flush()
    if run_match:
        # Local import avoids a circular import at module load.
        from app.services.photo_import_catalog_match_service import match_and_apply

        match_and_apply(session, row)
    session.commit()
    session.refresh(row)
    return row


def run_vision_sandbox_for_image(
    session: Session,
    *,
    image_id: int,
    mode: ComicVisionReadMode | str = ComicVisionReadMode.QUICK,
) -> list[PhotoImportVisionRead]:
    """Read every comic in the photo, clear any prior reads, and persist + match each."""
    image = session.get(PhotoImportImage, image_id)
    if image is None:
        logger.warning("photo_import.vision_sandbox.image_missing image_id=%s", image_id)
        return []
    path = resolve_photo_import_storage_path(image.storage_path, image_id=image_id)
    if not path.is_file():
        logger.error("photo_import.vision_sandbox.file_missing image_id=%s path=%s", image_id, path)
        return []
    raw = path.read_bytes()
    try:
        results = read_comics_with_gpt_vision(raw, image_id=image_id, mode=mode)
    except Exception as exc:  # noqa: BLE001
        logger.exception("photo_import.vision_sandbox.failed image_id=%s error=%s", image_id, exc)
        raise

    # Clear-and-rebuild: drop any existing reads for this photo first.
    existing = session.exec(
        select(PhotoImportVisionRead).where(PhotoImportVisionRead.image_id == image_id)
    ).all()
    for old in existing:
        session.delete(old)
    if existing:
        session.commit()

    rows: list[PhotoImportVisionRead] = []
    for idx, result in enumerate(results):
        rows.append(
            persist_vision_read(
                session,
                session_id=int(image.session_id),
                image_id=image_id,
                result=result,
                detection_index=idx,
                run_match=False,
            )
        )
    return rows


def vision_reads_for_image(session: Session, *, image_id: int) -> list[PhotoImportVisionRead]:
    return list(
        session.exec(
            select(PhotoImportVisionRead)
            .where(PhotoImportVisionRead.image_id == image_id)
            .order_by(PhotoImportVisionRead.detection_index.asc(), PhotoImportVisionRead.id.asc())
        ).all()
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
            rows = run_vision_sandbox_for_image(session, image_id=image_id)
            image = session.get(PhotoImportImage, image_id)
            if image is not None:
                image.status = IMAGE_STATUS_PROCESSED
                session.add(image)
                session.commit()
            created += len(rows)
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
