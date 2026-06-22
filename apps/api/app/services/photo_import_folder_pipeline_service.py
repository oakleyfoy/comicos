"""Background folder-import pipeline: drain uploaded photos with GPT + optional inventory."""

from __future__ import annotations

import logging
import threading

from sqlmodel import Session, select

from app.models.photo_import import (
    IMAGE_STATUS_FAILED,
    IMAGE_STATUS_PROCESSED,
    IMAGE_STATUS_PROCESSING,
    IMAGE_STATUS_UPLOADED,
    PhotoImportImage,
    PhotoImportSession,
)
from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.schemas.photo_import import PhotoImportFolderQueueStatusRead, PhotoImportProcessPendingResponse
from app.services.photo_import_session_service import get_session_by_token_or_404, refresh_session_counts
from app.services.photo_import_vision_read_actions_service import (
    add_all_session_reads_to_inventory,
    catalog_match_vision_read,
)

logger = logging.getLogger(__name__)

FOLDER_IMPORT_SOURCE_DEVICE = "folder_import"
MAX_KICK_PER_REQUEST = 3


def folder_queue_status(session: Session, *, import_row: PhotoImportSession) -> PhotoImportFolderQueueStatusRead:
    session_id = int(import_row.id or 0)
    images = session.exec(
        select(PhotoImportImage).where(PhotoImportImage.session_id == session_id)
    ).all()
    pending = sum(1 for row in images if row.status == IMAGE_STATUS_UPLOADED)
    processing = sum(1 for row in images if row.status == IMAGE_STATUS_PROCESSING)
    processed = sum(1 for row in images if row.status == IMAGE_STATUS_PROCESSED)
    failed = sum(1 for row in images if row.status == IMAGE_STATUS_FAILED)

    reads = session.exec(
        select(PhotoImportVisionRead).where(PhotoImportVisionRead.session_id == session_id)
    ).all()
    vision_reads = len(reads)
    not_in_inventory = sum(1 for row in reads if not row.added_to_inventory)

    queue_empty = pending == 0 and processing == 0 and not_in_inventory == 0

    return PhotoImportFolderQueueStatusRead(
        pending_uploads=pending,
        processing=processing,
        processed=processed,
        failed=failed,
        vision_reads=vision_reads,
        pending_inventory=not_in_inventory,
        queue_empty=queue_empty,
    )


def _post_process_image_reads(session: Session, *, image_id: int, owner_user_id: int) -> None:
    reads = session.exec(
        select(PhotoImportVisionRead).where(PhotoImportVisionRead.image_id == image_id)
    ).all()
    for read in reads:
        try:
            catalog_match_vision_read(session, read_id=int(read.id or 0), owner_user_id=owner_user_id)
        except Exception:
            logger.warning("folder_pipeline catalog_match failed read_id=%s", read.id, exc_info=True)


def _run_image_pipeline(image_id: int, owner_user_id: int, session_token: str) -> None:
    from app.db.session import get_engine
    from app.services.photo_import_processing_service import run_photo_import_image_processing

    try:
        run_photo_import_image_processing(image_id, vision_mode="quick")
        with Session(get_engine()) as bg_session:
            _post_process_image_reads(bg_session, image_id=image_id, owner_user_id=owner_user_id)
            import_row = get_session_by_token_or_404(bg_session, token=session_token)
            refresh_session_counts(bg_session, session_id=int(import_row.id or 0))
            try:
                add_all_session_reads_to_inventory(
                    bg_session,
                    session_token=session_token,
                    owner_user_id=owner_user_id,
                )
            except Exception:
                logger.warning("folder_pipeline add_all partial failure session=%s", session_token, exc_info=True)
    except Exception:
        logger.exception("folder_pipeline image failed image_id=%s", image_id)


def kick_folder_process_pending(
    session: Session,
    *,
    token: str,
    owner_user_id: int,
    limit: int = MAX_KICK_PER_REQUEST,
) -> PhotoImportProcessPendingResponse:
    import_row = get_session_by_token_or_404(session, token=token)
    session_id = int(import_row.id or 0)
    capped = max(1, min(int(limit), MAX_KICK_PER_REQUEST))

    in_flight = session.exec(
        select(PhotoImportImage).where(
            PhotoImportImage.session_id == session_id,
            PhotoImportImage.status == IMAGE_STATUS_PROCESSING,
        )
    ).all()
    if in_flight:
        status = folder_queue_status(session, import_row=import_row)
        return PhotoImportProcessPendingResponse(started_image_ids=[], queue=status)

    pending_rows = session.exec(
        select(PhotoImportImage)
        .where(
            PhotoImportImage.session_id == session_id,
            PhotoImportImage.status == IMAGE_STATUS_UPLOADED,
        )
        .order_by(PhotoImportImage.id.asc())
        .limit(capped)
    ).all()

    started: list[int] = []
    for row in pending_rows:
        image_id = int(row.id or 0)
        row.status = IMAGE_STATUS_PROCESSING
        session.add(row)
        started.append(image_id)

    if started:
        session.commit()
        for image_id in started:
            thread = threading.Thread(
                target=_run_image_pipeline,
                args=(image_id, owner_user_id, token),
                name=f"folder-import-{image_id}",
                daemon=True,
            )
            thread.start()

    refresh_session_counts(session, session_id=session_id)
    status = folder_queue_status(session, import_row=import_row)
    return PhotoImportProcessPendingResponse(started_image_ids=started, queue=status)
