"""P100 GPT review actions on vision reads: edit fields, add to inventory, re-read.

These power the phone-photo review page now that recognition is pure GPT vision
(no catalog candidates). Adding to inventory routes through the acquisition
placeholder path since there is no catalog issue id.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlmodel import Session

from app.models.photo_import import PhotoImportImage, PhotoImportSession
from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.schemas.acquisition import AddPlaceholderIssuePayload
from app.schemas.photo_import import (
    PhotoImportVisionReadInventoryResponse,
    PhotoImportVisionReadUpdatePayload,
)
from app.services.acquisition.acquisition_inventory_service import add_placeholder_issue
from app.services.photo_import_session_service import assert_session_owner, refresh_session_counts
from app.services.photo_import_storage_service import resolve_photo_import_storage_path
from app.services.photo_import_vision_read_api_service import vision_read_to_payload
from app.services.photo_import_vision_sandbox_service import read_comic_with_gpt_vision

logger = logging.getLogger(__name__)

_MAX_LENGTHS = {
    "publisher": 256,
    "series": 512,
    "issue_number": 64,
    "issue_title": 512,
    "variant_description": 512,
    "year": 16,
    "cover_date": 32,
    "barcode": 64,
}


def _load_owned_read(
    session: Session,
    *,
    read_id: int,
    owner_user_id: int,
) -> tuple[PhotoImportVisionRead, PhotoImportSession]:
    row = session.get(PhotoImportVisionRead, read_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vision read not found")
    import_row = session.get(PhotoImportSession, int(row.session_id))
    if import_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vision read not found")
    assert_session_owner(import_row, owner_user_id=owner_user_id)
    return row, import_row


def update_vision_read_fields(
    session: Session,
    *,
    read_id: int,
    owner_user_id: int,
    payload: PhotoImportVisionReadUpdatePayload,
) -> PhotoImportVisionRead:
    row, _ = _load_owned_read(session, read_id=read_id, owner_user_id=owner_user_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if isinstance(value, str):
            value = value.strip()
            limit = _MAX_LENGTHS.get(field)
            if limit:
                value = value[:limit]
            value = value or None
        setattr(row, field, value)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _ensure_session_acquisition(session: Session, import_row: PhotoImportSession) -> int:
    # Imported lazily to avoid a circular import with the detection service.
    from app.services.photo_import_detection_service import _ensure_session_acquisition as ensure

    return ensure(session, import_row)


def add_vision_read_to_inventory(
    session: Session,
    *,
    read_id: int,
    owner_user_id: int,
) -> PhotoImportVisionReadInventoryResponse:
    row, import_row = _load_owned_read(session, read_id=read_id, owner_user_id=owner_user_id)

    title = (row.series or row.issue_title or row.publisher or "").strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add a series or title before adding to inventory",
        )

    acquisition_id = _ensure_session_acquisition(session, import_row)
    note_bits = [b for b in [row.variant_description, f"GPT confidence {row.confidence}" if row.confidence else None] if b]
    result = add_placeholder_issue(
        session,
        owner_user_id=owner_user_id,
        acquisition_id=acquisition_id,
        payload=AddPlaceholderIssuePayload(
            title=title,
            issue_number=(row.issue_number or "").strip(),
            publisher=(row.publisher or None),
            quantity=1,
            notes="; ".join(note_bits) or None,
        ),
    )
    copy_ids: list[int] = []
    for item in result.results:
        copy_ids.extend(int(i) for i in item.inventory_copy_ids)

    row.added_to_inventory = True
    session.add(row)
    import_row.confirmed_count += len(copy_ids)
    session.add(import_row)
    session.commit()
    session.refresh(row)
    refresh_session_counts(session, session_id=int(import_row.id or 0))
    logger.info(
        "photo_import.vision_read.added_to_inventory read_id=%s acquisition_id=%s copies=%s",
        read_id,
        acquisition_id,
        copy_ids,
    )
    return PhotoImportVisionReadInventoryResponse(
        vision_read=vision_read_to_payload(row),
        acquisition_id=acquisition_id,
        created_count=result.created_count,
        inventory_copy_ids=copy_ids,
    )


def reread_vision_read(
    session: Session,
    *,
    read_id: int,
    owner_user_id: int,
) -> PhotoImportVisionRead:
    """Re-run GPT on the same photo and overwrite this read in place."""
    row, _ = _load_owned_read(session, read_id=read_id, owner_user_id=owner_user_id)
    image = session.get(PhotoImportImage, int(row.image_id))
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo import image not found")
    path = resolve_photo_import_storage_path(image.storage_path, image_id=int(image.id or 0))
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original image not found")

    result = read_comic_with_gpt_vision(path.read_bytes(), image_id=int(image.id or 0))
    row.publisher = result.publisher[:256] or None
    row.series = result.series[:512] or None
    row.issue_number = result.issue_number[:64] if result.issue_number else None
    row.issue_title = result.issue_title[:512] or None
    row.variant_description = result.variant_description[:512] or None
    row.year = result.year[:16] or None
    row.cover_date = result.cover_date[:32] or None
    row.barcode = result.barcode[:64] or None
    row.confidence = result.confidence
    row.reasoning = result.reasoning or None
    row.possible_alternates = result.possible_alternates or None
    row.raw_response = result.raw_response
    row.raw_response_text = result.raw_response_text
    row.is_correct = None
    row.feedback_notes = None
    session.add(row)
    session.commit()
    session.refresh(row)
    logger.info("photo_import.vision_read.reread read_id=%s series=%r issue=%r", read_id, row.series, row.issue_number)
    return row
