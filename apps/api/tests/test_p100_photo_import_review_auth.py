"""P100-20 photo import review auth: token-based detection list."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import User
from app.models.acquisition import Acquisition
from app.models.photo_import import PhotoImportDetectedBook, PhotoImportImage, PhotoImportSession
from app.services.photo_import_session_service import create_photo_import_session


def _open_acquisition(session: Session, owner_id: int) -> Acquisition:
    from decimal import Decimal

    acq = Acquisition(
        user_id=owner_id,
        acquisition_type="OTHER",
        seller_name="Test",
        total_paid=Decimal("0"),
        shipping_paid=Decimal("0"),
        tax_paid=Decimal("0"),
        status="OPEN",
    )
    session.add(acq)
    session.commit()
    session.refresh(acq)
    return acq


def _add_detection(session: Session, *, import_row: PhotoImportSession, image_id: int, label: str) -> None:
    session.add(
        PhotoImportDetectedBook(
            session_id=int(import_row.id),
            image_id=image_id,
            user_id=int(import_row.user_id),
            ai_series=label,
            status="detected",
        )
    )
    session.commit()


def test_unauthenticated_get_session_counts(client: TestClient, session: Session) -> None:
    user = User(email="p100-20-session@example.com", password_hash="hash", is_active=True)
    session.add(user)
    session.commit()
    session.refresh(user)

    created = create_photo_import_session(
        session, owner_user_id=int(user.id), acquisition_id=int(_open_acquisition(session, int(user.id)).id or 0)
    )
    resp = client.get(f"/api/v1/photo-import/sessions/{created.session_token}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["session_token"] == created.session_token
    assert body["uploaded_photo_count"] == 0


def test_unauthenticated_list_detections_by_valid_token(client: TestClient, session: Session) -> None:
    user = User(email="p100-20-detect@example.com", password_hash="hash", is_active=True)
    session.add(user)
    session.commit()
    session.refresh(user)

    created = create_photo_import_session(
        session, owner_user_id=int(user.id), acquisition_id=int(_open_acquisition(session, int(user.id)).id or 0)
    )
    import_row = session.get(PhotoImportSession, created.id)
    assert import_row is not None

    img = PhotoImportImage(
        session_id=int(import_row.id),
        user_id=int(user.id),
        storage_path="data/photo_import/x.jpg",
        original_filename="x.jpg",
        mime_type="image/jpeg",
        file_size=1,
        status="processed",
    )
    session.add(img)
    session.commit()
    session.refresh(img)

    _add_detection(session, import_row=import_row, image_id=int(img.id), label="Alpha")
    _add_detection(session, import_row=import_row, image_id=int(img.id), label="Beta")

    resp = client.get(f"/api/v1/photo-import/sessions/{created.session_token}/detections")
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 2


def test_list_detections_invalid_token_404(client: TestClient) -> None:
    resp = client.get("/api/v1/photo-import/sessions/not-a-real-token/detections")
    assert resp.status_code == 404


def test_list_detections_expired_token_410(client: TestClient, session: Session) -> None:
    user = User(email="p100-20-expired@example.com", password_hash="hash", is_active=True)
    session.add(user)
    session.commit()
    session.refresh(user)

    past = datetime.now(timezone.utc) - timedelta(hours=1)
    import_row = PhotoImportSession(
        user_id=int(user.id),
        session_token="expiredtok123456789012345678901234567890",
        expires_at=past,
        status="review_ready",
    )
    session.add(import_row)
    session.commit()

    resp = client.get(f"/api/v1/photo-import/sessions/{import_row.session_token}/detections")
    assert resp.status_code == 410


def test_session_token_only_returns_own_detections(client: TestClient, session: Session) -> None:
    user = User(email="p100-20-isolation@example.com", password_hash="hash", is_active=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    owner_id = int(user.id)

    acq = _open_acquisition(session, owner_id)
    session_a = create_photo_import_session(session, owner_user_id=owner_id, acquisition_id=int(acq.id or 0))
    session_b = create_photo_import_session(session, owner_user_id=owner_id, acquisition_id=int(acq.id or 0))
    row_a = session.get(PhotoImportSession, session_a.id)
    row_b = session.get(PhotoImportSession, session_b.id)
    assert row_a is not None and row_b is not None

    for row in (row_a, row_b):
        img = PhotoImportImage(
            session_id=int(row.id),
            user_id=owner_id,
            storage_path=f"data/photo_import/{row.id}.jpg",
            original_filename="one.jpg",
            mime_type="image/jpeg",
            file_size=1,
            status="processed",
        )
        session.add(img)
        session.commit()
        session.refresh(img)
        _add_detection(session, import_row=row, image_id=int(img.id), label=f"session-{row.id}")

    resp_a = client.get(f"/api/v1/photo-import/sessions/{session_a.session_token}/detections")
    resp_b = client.get(f"/api/v1/photo-import/sessions/{session_b.session_token}/detections")
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    assert len(resp_a.json()) == 1
    assert len(resp_b.json()) == 1
    assert resp_a.json()[0]["session_id"] == session_a.id
    assert resp_b.json()[0]["session_id"] == session_b.id
