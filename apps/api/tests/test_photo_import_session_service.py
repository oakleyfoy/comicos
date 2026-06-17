"""P100 photo import session tests."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models import User
from app.models.photo_import import PhotoImportSession
from app.services.photo_import_session_service import create_photo_import_session, heartbeat_session


def test_create_and_heartbeat_photo_import_session(session: Session) -> None:
    user = User(email="photo-import@example.com", password_hash="hash", is_active=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    owner_id = int(user.id)
    created = create_photo_import_session(session, owner_user_id=owner_id, source_device="test")
    assert created.session_token
    assert created.uploaded_photo_count == 0

    beat = heartbeat_session(session, token=created.session_token, source_device="iphone")
    assert beat.last_seen_at is not None
    assert beat.source_device == "iphone"

    row = session.exec(
        select(PhotoImportSession).where(PhotoImportSession.session_token == created.session_token)
    ).first()
    assert row is not None
    assert row.status in {"created", "active"}
