"""P100 GPT review actions on vision reads: edit fields, add to inventory, re-read.

These power the phone-photo review page now that recognition is pure GPT vision
(no catalog candidates). Adding to inventory creates an owned copy in the main
collection model so the comic shows up in the Inventory grid and counts toward
collection value.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlmodel import Session

from app.models.photo_import import PhotoImportImage, PhotoImportSession
from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.schemas.photo_import import (
    PhotoImportVisionReadInventoryResponse,
    PhotoImportVisionReadUpdatePayload,
)
from app.services.photo_import_catalog_match_service import (
    choose_match_for_read,
    match_and_apply,
)
from app.services.photo_import_acquisition_service import create_catalog_copy_from_vision_read
from app.services.photo_import_session_service import assert_session_owner, refresh_session_counts
from app.services.photo_import_vision_read_api_service import vision_read_to_payload
from app.services.photo_import_vision_sandbox_service import run_vision_sandbox_for_image

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


def add_vision_read_to_inventory(
    session: Session,
    *,
    read_id: int,
    owner_user_id: int,
) -> PhotoImportVisionReadInventoryResponse:
    row, import_row = _load_owned_read(session, read_id=read_id, owner_user_id=owner_user_id)

    if row.added_to_inventory:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This photo is already in your collection",
        )

    title = (row.series or row.issue_title or row.publisher or "").strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add a series or title before adding to inventory",
        )

    image = session.get(PhotoImportImage, int(row.image_id))
    source_image_url = getattr(image, "storage_path", None) if image is not None else None

    acquisition_id, copy_id = create_catalog_copy_from_vision_read(
        session,
        read=row,
        import_row=import_row,
        owner_user_id=owner_user_id,
        source_image_url=source_image_url,
    )
    copy_ids = [copy_id]

    row.added_to_inventory = True
    session.add(row)
    import_row.confirmed_count += len(copy_ids)
    session.add(import_row)
    session.commit()
    session.refresh(row)
    refresh_session_counts(session, session_id=int(import_row.id or 0))
    logger.info(
        "photo_import.vision_read.added_to_inventory read_id=%s copies=%s",
        read_id,
        copy_ids,
    )
    return PhotoImportVisionReadInventoryResponse(
        vision_read=vision_read_to_payload(row),
        acquisition_id=acquisition_id,
        created_count=len(copy_ids),
        inventory_copy_ids=copy_ids,
    )


def reread_vision_read(
    session: Session,
    *,
    read_id: int,
    owner_user_id: int,
) -> list[PhotoImportVisionRead]:
    """Re-run GPT on the photo this read came from: clear-and-rebuild all its books."""
    row, _ = _load_owned_read(session, read_id=read_id, owner_user_id=owner_user_id)
    image_id = int(row.image_id)
    image = session.get(PhotoImportImage, image_id)
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo import image not found")
    rows = run_vision_sandbox_for_image(session, image_id=image_id)
    logger.info("photo_import.vision_read.reread image_id=%s books=%d", image_id, len(rows))
    return rows


def _catalog_match_with_ondemand_fallback(session: Session, read: PhotoImportVisionRead) -> None:
    """Local catalog match first; if missing, one ComicVine on-demand import + rematch."""
    match_and_apply(session, read)
    if read.catalog_issue_id is None:
        from app.services.photo_import_comicvine_ondemand_service import try_comicvine_ondemand_for_read

        try_comicvine_ondemand_for_read(session, read)


def catalog_match_vision_read(
    session: Session,
    *,
    read_id: int,
    owner_user_id: int,
) -> PhotoImportVisionRead:
    """Match GPT to local catalog, then ComicVine on-demand once if still unmatched."""
    row, _ = _load_owned_read(session, read_id=read_id, owner_user_id=owner_user_id)
    _catalog_match_with_ondemand_fallback(session, row)
    session.commit()
    session.refresh(row)
    return row


def catalog_match_session_reads(
    session: Session,
    *,
    session_token: str,
    owner_user_id: int,
    read_ids: list[int],
) -> list[PhotoImportVisionRead]:
    from app.models.photo_import import PhotoImportSession
    from sqlmodel import select

    import_row = session.exec(
        select(PhotoImportSession).where(PhotoImportSession.session_token == session_token)
    ).first()
    if import_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    assert_session_owner(import_row, owner_user_id=owner_user_id)

    updated: list[PhotoImportVisionRead] = []
    for read_id in read_ids:
        row = session.get(PhotoImportVisionRead, int(read_id))
        if row is None or int(row.session_id) != int(import_row.id or 0):
            continue
        _catalog_match_with_ondemand_fallback(session, row)
        updated.append(row)
    session.commit()
    for row in updated:
        session.refresh(row)
    return updated


def rematch_vision_read(
    session: Session,
    *,
    read_id: int,
    owner_user_id: int,
) -> PhotoImportVisionRead:
    """Re-run the catalog match for a read (e.g. after editing series/issue/barcode)."""
    return catalog_match_vision_read(session, read_id=read_id, owner_user_id=owner_user_id)


def choose_vision_read_match(
    session: Session,
    *,
    read_id: int,
    owner_user_id: int,
    catalog_issue_id: int,
) -> PhotoImportVisionRead:
    """Manually pin a read to one of its alternate catalog issues."""
    row, _ = _load_owned_read(session, read_id=read_id, owner_user_id=owner_user_id)
    choose_match_for_read(session, row, catalog_issue_id=catalog_issue_id)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def add_all_session_reads_to_inventory(
    session: Session,
    *,
    session_token: str,
    owner_user_id: int,
) -> list[PhotoImportVisionReadInventoryResponse]:
    """Add every not-yet-added read in a session to the collection."""
    from app.models.photo_import import PhotoImportSession
    from sqlmodel import select

    import_row = session.exec(
        select(PhotoImportSession).where(PhotoImportSession.session_token == session_token)
    ).first()
    if import_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    assert_session_owner(import_row, owner_user_id=owner_user_id)

    rows = session.exec(
        select(PhotoImportVisionRead)
        .where(
            PhotoImportVisionRead.session_id == int(import_row.id or 0),
            PhotoImportVisionRead.added_to_inventory == False,  # noqa: E712
        )
        .order_by(PhotoImportVisionRead.id.asc())
    ).all()

    responses: list[PhotoImportVisionReadInventoryResponse] = []
    for row in rows:
        title = (row.series or row.issue_title or row.publisher or "").strip()
        if not title:
            continue
        try:
            responses.append(
                add_vision_read_to_inventory(
                    session, read_id=int(row.id or 0), owner_user_id=owner_user_id
                )
            )
        except HTTPException:
            continue
    return responses
