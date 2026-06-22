"""Server-sent events for streaming GPT vision reads (ChatGPT-style UX)."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

from sqlmodel import Session

from app.models.photo_import import (
    IMAGE_STATUS_FAILED,
    IMAGE_STATUS_PROCESSED,
    IMAGE_STATUS_PROCESSING,
    PhotoImportImage,
)
from app.core.config import get_settings
from app.services.comic_vision_read_mode import ComicVisionReadMode, normalize_vision_read_mode, resolve_vision_profile
from app.services.gpt_comic_vision_client import (
    ComicVisionError,
    parse_streamed_json_content,
    stream_comic_vision_text,
)
from app.services.photo_import_session_service import refresh_session_counts
from app.services.photo_import_vision_read_api_service import vision_read_to_payload
from app.services.photo_import_vision_sandbox_service import (
    read_comics_with_gpt_vision,
    run_vision_sandbox_for_image,
    vision_reads_for_image,
)

logger = logging.getLogger(__name__)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def iter_vision_read_sse(
    session: Session,
    *,
    image_id: int,
    mode: ComicVisionReadMode | str = ComicVisionReadMode.QUICK,
    force: bool = False,
) -> Iterator[str]:
    """Run (or replay) a vision read, streaming token deltas when executing OpenAI."""
    read_mode = normalize_vision_read_mode(mode.value if isinstance(mode, ComicVisionReadMode) else str(mode))
    image = session.get(PhotoImportImage, image_id)
    if image is None:
        yield _sse("error", {"message": "Photo import image not found"})
        return

    existing = vision_reads_for_image(session, image_id=image_id)
    if (
        not force
        and existing
        and str(image.status) == IMAGE_STATUS_PROCESSED
        and read_mode == ComicVisionReadMode.QUICK
    ):
        yield _sse(
            "done",
            {
                "image_id": image_id,
                "image_status": image.status,
                "vision_mode": read_mode.value,
                "reads": [vision_read_to_payload(r).model_dump() for r in existing],
            },
        )
        return

    if str(image.status) == IMAGE_STATUS_PROCESSING and not force:
        yield _sse("status", {"phase": "processing", "message": "Vision read already in progress"})
        return

    image.status = IMAGE_STATUS_PROCESSING
    session.add(image)
    session.commit()

    yield _sse("status", {"phase": "started", "vision_mode": read_mode.value})

    from app.services.photo_import_storage_service import resolve_photo_import_storage_path

    path = resolve_photo_import_storage_path(image.storage_path, image_id=image_id)
    if not path.is_file():
        image.status = IMAGE_STATUS_FAILED
        session.add(image)
        session.commit()
        yield _sse("error", {"message": "Original image file missing"})
        return

    raw = path.read_bytes()
    settings = get_settings()
    if not settings.openai_api_key:
        image.status = IMAGE_STATUS_FAILED
        session.add(image)
        session.commit()
        yield _sse("error", {"message": "OpenAI API key is not configured"})
        return

    profile = resolve_vision_profile(settings, read_mode)
    accumulated = ""
    try:
        if read_mode == ComicVisionReadMode.QUICK:
            for delta in stream_comic_vision_text(
                raw,
                model=str(profile["model"]),
                api_key=settings.openai_api_key,
                log_context=f"photo_import_stream image_id={image_id}",
                system=str(profile["system"]),
                user=str(profile["user"]),
                image_detail=str(profile["image_detail"]),
                max_image_side_px=int(profile["max_image_side_px"]),
            ):
                accumulated += delta
                yield _sse("token", {"text": delta})
            parsed = parse_streamed_json_content(accumulated)
            # Persist using the same path as non-streaming (re-parse payloads).
            from app.services.photo_import_vision_sandbox_service import (
                _extract_comics_payloads,
                _parse_sandbox_payload,
            )

            books = _extract_comics_payloads(parsed)
            if not books:
                raise ComicVisionError("GPT vision returned no comics for this image")
            results = []
            for book in books:
                result = _parse_sandbox_payload(book)
                result.raw_response = {
                    "parsed": parsed,
                    "model_used": profile["model"],
                    "vision_mode": read_mode.value,
                    "streamed": True,
                }
                result.raw_response_text = accumulated
                results.append(result)
            rows = _persist_results(session, image=image, results=results)
        else:
            results = read_comics_with_gpt_vision(raw, image_id=image_id, mode=read_mode)
            rows = _persist_results(session, image=image, results=results)
            if results and results[0].reasoning:
                yield _sse("token", {"text": results[0].reasoning})

        image = session.get(PhotoImportImage, image_id)
        if image is not None:
            image.status = IMAGE_STATUS_PROCESSED
            session.add(image)
            session.commit()
        refresh_session_counts(session, session_id=int(image.session_id) if image else 0)
        yield _sse(
            "done",
            {
                "image_id": image_id,
                "image_status": IMAGE_STATUS_PROCESSED,
                "vision_mode": read_mode.value,
                "reads": [vision_read_to_payload(r).model_dump() for r in rows],
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("photo_import.vision_stream.failed image_id=%s", image_id)
        image = session.get(PhotoImportImage, image_id)
        if image is not None:
            image.status = IMAGE_STATUS_FAILED
            session.add(image)
            session.commit()
        yield _sse("error", {"message": str(exc)})


def _persist_results(session: Session, *, image: PhotoImportImage, results) -> list:
    """Clear prior reads and persist new sandbox results (no catalog match)."""
    from sqlmodel import select

    from app.models.photo_import_vision_read import PhotoImportVisionRead
    from app.services.photo_import_vision_sandbox_service import persist_vision_read

    image_id = int(image.id or 0)
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


def run_vision_read_non_stream(
    session: Session,
    *,
    image_id: int,
    mode: ComicVisionReadMode | str = ComicVisionReadMode.QUICK,
) -> list:
    """Background-friendly entry (no SSE)."""
    image = session.get(PhotoImportImage, image_id)
    if image is None:
        return []
    image.status = IMAGE_STATUS_PROCESSING
    session.add(image)
    session.commit()
    try:
        rows = run_vision_sandbox_for_image(session, image_id=image_id, mode=mode)
        image = session.get(PhotoImportImage, image_id)
        if image is not None:
            image.status = IMAGE_STATUS_PROCESSED
            session.add(image)
            session.commit()
        refresh_session_counts(session, session_id=int(image.session_id) if image else 0)
        return rows
    except Exception:
        image = session.get(PhotoImportImage, image_id)
        if image is not None:
            image.status = IMAGE_STATUS_FAILED
            session.add(image)
            session.commit()
        raise
