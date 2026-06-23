"""Folder import queue + background kick endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.photo_import import (
    IMAGE_STATUS_PROCESSED,
    IMAGE_STATUS_PROCESSING,
    IMAGE_STATUS_UPLOADED,
    PhotoImportImage,
    PhotoImportSession,
)
from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.services.photo_import_folder_pipeline_service import FOLDER_IMPORT_SOURCE_DEVICE
from test_inventory import auth_headers, register_and_login


def _folder_session(client: TestClient, token: str) -> dict:
    res = client.post(
        "/api/v1/photo-import/sessions",
        headers=auth_headers(token),
        json={"source_device": FOLDER_IMPORT_SOURCE_DEVICE, "capture_mode": "single_comic"},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _add_image(session: Session, *, session_id: int, user_id: int, status: str) -> PhotoImportImage:
    row = PhotoImportImage(
        session_id=session_id,
        user_id=user_id,
        original_filename="cover.jpg",
        storage_path="data/photo_import/cover.jpg",
        status=status,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def test_folder_queue_status_reflects_images_and_reads(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "folder-queue@example.com")
    created = _folder_session(client, token)
    import_row = session.exec(
        select(PhotoImportSession).where(PhotoImportSession.session_token == created["session_token"])
    ).one()
    user_id = int(import_row.user_id)
    session_id = int(import_row.id or 0)

    _add_image(session, session_id=session_id, user_id=user_id, status=IMAGE_STATUS_UPLOADED)
    _add_image(session, session_id=session_id, user_id=user_id, status=IMAGE_STATUS_PROCESSING)
    proc = _add_image(session, session_id=session_id, user_id=user_id, status=IMAGE_STATUS_PROCESSED)

    read = PhotoImportVisionRead(
        session_id=session_id,
        image_id=int(proc.id or 0),
        series="Test",
        issue_number="1",
        added_to_inventory=False,
    )
    session.add(read)
    session.commit()

    res = client.get(
        f"/api/v1/photo-import/sessions/{created['session_token']}/folder-queue",
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["pending_uploads"] == 1
    assert body["processing"] == 1
    assert body["processed"] == 1
    assert body["vision_reads"] == 1
    assert body["pending_inventory"] == 1
    assert body["queue_empty"] is False


def test_folder_process_pending_starts_uploaded_images(client: TestClient, session: Session, monkeypatch) -> None:
    token = register_and_login(client, "folder-kick@example.com")
    created = _folder_session(client, token)
    import_row = session.exec(
        select(PhotoImportSession).where(PhotoImportSession.session_token == created["session_token"])
    ).one()
    user_id = int(import_row.user_id)
    session_id = int(import_row.id or 0)
    img = _add_image(session, session_id=session_id, user_id=user_id, status=IMAGE_STATUS_UPLOADED)

    started: list[int] = []

    def fake_pipeline(image_id: int, owner_user_id: int, session_token: str) -> None:
        started.append(image_id)

    monkeypatch.setattr(
        "app.services.photo_import_folder_pipeline_service._run_image_pipeline",
        fake_pipeline,
    )

    res = client.post(
        f"/api/v1/photo-import/sessions/{created['session_token']}/folder-process-pending?limit=1",
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["started_image_ids"] == [int(img.id or 0)]
    assert payload["queue"]["processing"] == 1
    assert started == [int(img.id or 0)]


def test_folder_reset_vision_requeues_processed_images(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "folder-reset@example.com")
    created = _folder_session(client, token)
    import_row = session.exec(
        select(PhotoImportSession).where(PhotoImportSession.session_token == created["session_token"])
    ).one()
    user_id = int(import_row.user_id)
    session_id = int(import_row.id or 0)
    img = _add_image(session, session_id=session_id, user_id=user_id, status=IMAGE_STATUS_PROCESSED)
    session.add(
        PhotoImportVisionRead(
            session_id=session_id,
            image_id=int(img.id or 0),
            series="Test",
            issue_number="1",
            added_to_inventory=False,
        )
    )
    session.commit()

    res = client.post(
        f"/api/v1/photo-import/sessions/{created['session_token']}/folder-reset-vision",
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["images_reset"] == 1
    assert body["queue"]["pending_uploads"] == 1
    session.refresh(img)
    assert img.status == IMAGE_STATUS_UPLOADED
    assert session.exec(select(PhotoImportVisionRead).where(PhotoImportVisionRead.image_id == img.id)).all() == []
