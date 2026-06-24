"""P100 image upload + processing orchestration."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image
from sqlmodel import Session

from app.models.photo_import import (
    IMAGE_ROLE_BARCODE,
    IMAGE_ROLE_BARCODE_PRIMARY,
    IMAGE_ROLE_COVER,
    IMAGE_STATUS_FAILED,
    IMAGE_STATUS_UPLOADED,
    PhotoImportImage,
    PhotoImportSession,
)
from app.schemas.photo_import import PhotoImportImageRead
from app.services.photo_import_session_service import (
    activate_session,
    get_session_by_token_or_404,
    refresh_session_counts,
)
from app.services.photo_import_sandbox_flags import photo_import_vision_sandbox_enabled
from app.services.photo_import_storage_service import (
    relative_path_under_repo_root,
    resolve_photo_import_storage_path,
    upload_storage_dir,
)

logger = logging.getLogger(__name__)
MAX_BATCH_FILES = 10
MAX_FILE_BYTES = 15 * 1024 * 1024


def image_to_read(row: PhotoImportImage) -> PhotoImportImageRead:
    return PhotoImportImageRead(
        id=int(row.id or 0),
        session_id=int(row.session_id),
        original_filename=row.original_filename,
        mime_type=row.mime_type,
        file_size=int(row.file_size),
        width=row.width,
        height=row.height,
        status=row.status,
        image_role=str(getattr(row, "image_role", None) or IMAGE_ROLE_COVER),
        pair_cover_image_id=getattr(row, "pair_cover_image_id", None),
        created_at=row.created_at,
    )


async def _save_one_upload(
    session: Session,
    *,
    import_row: PhotoImportSession,
    upload: UploadFile,
    image_role: str = IMAGE_ROLE_COVER,
    pair_cover_image_id: int | None = None,
) -> PhotoImportImage:
    if not upload.content_type or not upload.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only image uploads are allowed")
    raw = await upload.read()
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image too large")
    width: int | None = None
    height: int | None = None
    try:
        with Image.open(__import__("io").BytesIO(raw)) as img:
            width, height = img.size
    except OSError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image file") from None

    ext = Path(upload.filename or "photo.jpg").suffix or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    dest_dir = upload_storage_dir(user_id=int(import_row.user_id), session_id=int(import_row.id or 0))
    dest_path = dest_dir / filename
    dest_path.write_bytes(raw)
    storage_rel = relative_path_under_repo_root(dest_path)

    row = PhotoImportImage(
        session_id=int(import_row.id or 0),
        user_id=int(import_row.user_id),
        original_filename=upload.filename or filename,
        storage_path=storage_rel,
        mime_type=upload.content_type or "image/jpeg",
        file_size=len(raw),
        width=width,
        height=height,
        status=IMAGE_STATUS_UPLOADED,
        image_role=image_role,
        pair_cover_image_id=pair_cover_image_id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    resolved = resolve_photo_import_storage_path(storage_rel, image_id=int(row.id or 0))
    logger.info(
        "photo_import.upload.saved image_id=%s role=%s pair_cover=%s exists=%s",
        row.id,
        image_role,
        pair_cover_image_id,
        resolved.is_file(),
    )
    return row


async def upload_barcode_companion_image(
    session: Session,
    *,
    token: str,
    cover_image_id: int,
    upload: UploadFile,
) -> PhotoImportImageRead:
    import_row = get_session_by_token_or_404(session, token=token)
    cover = session.get(PhotoImportImage, cover_image_id)
    if cover is None or int(cover.session_id) != int(import_row.id or 0):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cover photo not found")
    if str(getattr(cover, "image_role", IMAGE_ROLE_COVER) or IMAGE_ROLE_COVER) == IMAGE_ROLE_BARCODE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot attach barcode to a barcode photo")

    activate_session(session, import_row)
    row = await _save_one_upload(
        session,
        import_row=import_row,
        upload=upload,
        image_role=IMAGE_ROLE_BARCODE,
        pair_cover_image_id=cover_image_id,
    )
    refresh_session_counts(session, session_id=int(import_row.id or 0))
    return image_to_read(row)


async def upload_session_images(
    session: Session,
    *,
    token: str,
    files: list[UploadFile],
    defer_gpt_processing: bool = True,
    scan_intent: str = "cover",
) -> tuple[list[PhotoImportImageRead], list[int]]:
    if len(files) > MAX_BATCH_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"At most {MAX_BATCH_FILES} photos per batch",
        )
    import_row = get_session_by_token_or_404(session, token=token)
    activate_session(session, import_row)
    saved: list[PhotoImportImageRead] = []
    pending_image_ids: list[int] = []
    intent = (scan_intent or "cover").strip().lower()
    image_role = IMAGE_ROLE_BARCODE_PRIMARY if intent == "barcode" else IMAGE_ROLE_COVER
    for upload in files:
        row = await _save_one_upload(
            session,
            import_row=import_row,
            upload=upload,
            image_role=image_role,
        )
        logger.info(
            "photo_import.upload.process image_id=%s session_id=%s vision_sandbox=%s defer=%s",
            row.id,
            import_row.id,
            photo_import_vision_sandbox_enabled(),
            defer_gpt_processing,
        )
        if defer_gpt_processing:
            pending_image_ids.append(int(row.id or 0))
        else:
            try:
                from app.services.photo_import_processing_service import process_photo_import_image

                process_photo_import_image(session, image_id=int(row.id or 0))
                session.refresh(row)
            except Exception:
                row.status = IMAGE_STATUS_FAILED
                session.add(row)
                session.commit()
                session.refresh(row)
        saved.append(image_to_read(row))

    refresh_session_counts(session, session_id=int(import_row.id or 0))
    return saved, pending_image_ids
