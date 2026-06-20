"""P100 photo import session lifecycle."""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta, timezone

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models.photo_import import (
    CAPTURE_MODE_GROUP,
    CAPTURE_MODE_SINGLE_COMIC,
    PhotoImportSession,
    SESSION_STATUS_ACTIVE,
    SESSION_STATUS_COMPLETED,
    SESSION_STATUS_CREATED,
    SESSION_STATUS_EXPIRED,
    SESSION_STATUS_REVIEW_READY,
    utc_now,
)
from app.schemas.photo_import import PhotoImportSessionRead

logger = logging.getLogger(__name__)

SESSION_TTL_HOURS = 4


def normalize_capture_mode(value: str | None) -> str:
    if value == CAPTURE_MODE_GROUP:
        return CAPTURE_MODE_GROUP
    return CAPTURE_MODE_SINGLE_COMIC


def _public_base_url() -> str:
    from app.core.config import get_settings

    return get_settings().frontend_url.rstrip("/")


def _session_urls(token: str) -> tuple[str, str]:
    from app.services.photo_import_sandbox_flags import photo_import_vision_sandbox_enabled

    base = _public_base_url()
    mobile = f"{base}/photo-import/mobile/{token}" if base else f"/photo-import/mobile/{token}"
    if photo_import_vision_sandbox_enabled():
        review = f"{base}/add-comics/photo/sandbox/session/{token}" if base else f"/add-comics/photo/sandbox/session/{token}"
    else:
        review = f"{base}/add-comics/photo/session/{token}" if base else f"/add-comics/photo/session/{token}"
    return mobile, review


def _expire_stale(session_row: PhotoImportSession) -> None:
    if session_row.status in {SESSION_STATUS_COMPLETED, SESSION_STATUS_EXPIRED}:
        return
    expires = session_row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= utc_now():
        session_row.status = SESSION_STATUS_EXPIRED


def get_session_by_token_or_404(session: Session, *, token: str) -> PhotoImportSession:
    row = session.exec(select(PhotoImportSession).where(PhotoImportSession.session_token == token)).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo import session not found")
    _expire_stale(row)
    session.add(row)
    session.commit()
    session.refresh(row)
    if row.status == SESSION_STATUS_EXPIRED:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Photo import session expired")
    return row


def assert_session_owner(row: PhotoImportSession, *, owner_user_id: int) -> None:
    if int(row.user_id) != int(owner_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your photo import session")


def create_photo_import_session(
    session: Session,
    *,
    owner_user_id: int,
    source_device: str | None = None,
    capture_mode: str | None = None,
) -> PhotoImportSessionRead:
    token = secrets.token_urlsafe(32)
    now = utc_now()
    row = PhotoImportSession(
        user_id=owner_user_id,
        session_token=token,
        status=SESSION_STATUS_CREATED,
        created_at=now,
        expires_at=now + timedelta(hours=SESSION_TTL_HOURS),
        source_device=source_device,
        capture_mode=normalize_capture_mode(capture_mode),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return session_to_read(row)


def activate_session(session: Session, row: PhotoImportSession) -> PhotoImportSession:
    if row.status == SESSION_STATUS_CREATED:
        row.status = SESSION_STATUS_ACTIVE
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def session_to_read(row: PhotoImportSession) -> PhotoImportSessionRead:
    from app.services.photo_import_sandbox_flags import photo_import_vision_sandbox_enabled

    mobile, review = _session_urls(row.session_token)
    sandbox = photo_import_vision_sandbox_enabled()
    logger.info(
        "photo_import.session_response token=%s vision_sandbox=%s desktop_review_url=%s",
        row.session_token,
        sandbox,
        review,
    )
    return PhotoImportSessionRead(
        id=int(row.id or 0),
        session_token=row.session_token,
        status=row.status,
        created_at=row.created_at,
        expires_at=row.expires_at,
        last_seen_at=row.last_seen_at,
        source_device=row.source_device,
        confirmed_count=int(row.confirmed_count),
        uploaded_photo_count=int(row.uploaded_photo_count),
        detected_book_count=int(row.detected_book_count),
        capture_mode=normalize_capture_mode(row.capture_mode),
        mobile_url=mobile,
        desktop_review_url=review,
        vision_sandbox=sandbox,
    )


def heartbeat_session(
    session: Session,
    *,
    token: str,
    source_device: str | None = None,
    capture_mode: str | None = None,
) -> PhotoImportSessionRead:
    row = get_session_by_token_or_404(session, token=token)
    row.last_seen_at = utc_now()
    if source_device:
        row.source_device = source_device
    if capture_mode is not None:
        row.capture_mode = normalize_capture_mode(capture_mode)
    activate_session(session, row)
    session.add(row)
    session.commit()
    session.refresh(row)
    return session_to_read(row)


def complete_session(session: Session, *, owner_user_id: int, token: str) -> PhotoImportSessionRead:
    row = get_session_by_token_or_404(session, token=token)
    assert_session_owner(row, owner_user_id=owner_user_id)
    row.status = SESSION_STATUS_COMPLETED
    session.add(row)
    session.commit()
    session.refresh(row)
    return session_to_read(row)


def refresh_session_counts(session: Session, *, session_id: int) -> None:
    from sqlmodel import func

    from app.models.photo_import import PhotoImportDetectedBook, PhotoImportImage
    from app.services.photo_import_sandbox_flags import photo_import_vision_sandbox_enabled
    from app.services.photo_import_vision_accuracy_service import count_vision_reads_for_session

    row = session.get(PhotoImportSession, session_id)
    if row is None:
        return
    uploads = session.exec(
        select(func.count(PhotoImportImage.id)).where(PhotoImportImage.session_id == session_id)
    ).one()
    if photo_import_vision_sandbox_enabled():
        vision_count = count_vision_reads_for_session(session, session_id=session_id)
        row.uploaded_photo_count = int(uploads or 0)
        row.detected_book_count = vision_count
    else:
        detections = session.exec(
            select(func.count(PhotoImportDetectedBook.id)).where(
                PhotoImportDetectedBook.session_id == session_id,
                PhotoImportDetectedBook.status != "rejected",
            )
        ).one()
        row.uploaded_photo_count = int(uploads or 0)
        row.detected_book_count = int(detections or 0)
    if row.detected_book_count > 0 and row.status not in {SESSION_STATUS_COMPLETED, SESSION_STATUS_EXPIRED}:
        row.status = SESSION_STATUS_REVIEW_READY
    session.add(row)
    session.commit()
