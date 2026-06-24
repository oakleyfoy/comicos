"""Merge a barcode close-up photo into the GPT vision read for its cover image."""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlmodel import Session

from app.models.photo_import import (
    IMAGE_ROLE_BARCODE,
    IMAGE_STATUS_PROCESSED,
    PhotoImportImage,
)
from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.services.p100_barcode_extraction_service import extract_barcode_from_image
from app.services.photo_import_vision_sandbox_service import vision_reads_for_image

logger = logging.getLogger(__name__)


def is_barcode_companion_image(image: PhotoImportImage) -> bool:
    return (
        str(getattr(image, "image_role", "") or "").strip().lower() == IMAGE_ROLE_BARCODE
        and image.pair_cover_image_id is not None
    )


def apply_barcode_companion_bytes(
    session: Session,
    *,
    barcode_image: PhotoImportImage,
    image_bytes: bytes,
    rematch_catalog: bool = True,
) -> tuple[int, list[PhotoImportVisionRead]]:
    """Decode UPC from companion bytes and attach to cover image vision read(s)."""
    cover_id = int(barcode_image.pair_cover_image_id or 0)
    if cover_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Barcode photo is not linked to a cover")

    cover = session.get(PhotoImportImage, cover_id)
    if cover is None or int(cover.session_id) != int(barcode_image.session_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cover photo for this barcode was not found")

    reads = vision_reads_for_image(session, image_id=cover_id)
    if not reads:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Run the cover GPT read first, then add the barcode close-up",
        )

    logger.info(
        "photo_import.barcode_companion.started barcode_image_id=%s cover_image_id=%s reads=%d",
        barcode_image.id,
        cover_id,
        len(reads),
    )

    extraction = extract_barcode_from_image(
        image_bytes,
        allow_gpt_fallback=False,
        log_context=f"photo_import barcode_companion barcode_image_id={barcode_image.id} cover_image_id={cover_id}",
    )
    code = extraction.get("barcode")
    if not code:
        extraction = extract_barcode_from_image(
            image_bytes,
            allow_gpt_fallback=True,
            log_context=f"photo_import barcode_companion_gpt barcode_image_id={barcode_image.id}",
        )
        code = extraction.get("barcode")

    updated: list[PhotoImportVisionRead] = []
    for read in reads:
        raw = dict(read.raw_response or {})
        raw["barcode_companion_extraction"] = extraction
        raw["barcode_companion_image_id"] = int(barcode_image.id or 0)
        read.raw_response = raw
        if code:
            read.barcode = str(code)[:64]
            note = "Barcode from close-up photo"
            read.reasoning = f"{read.reasoning} {note}".strip() if read.reasoning else note
        session.add(read)
        updated.append(read)

    session.flush()

    if rematch_catalog and code:
        from app.services.photo_import_catalog_match_service import match_and_apply

        for read in updated:
            match_and_apply(session, read)
            session.add(read)

    barcode_image.status = IMAGE_STATUS_PROCESSED
    session.add(barcode_image)
    session.commit()
    for read in updated:
        session.refresh(read)

    logger.info(
        "photo_import.barcode_companion.done cover_image_id=%s barcode=%s matched_reads=%d",
        cover_id,
        code,
        len(updated),
    )
    return cover_id, updated
