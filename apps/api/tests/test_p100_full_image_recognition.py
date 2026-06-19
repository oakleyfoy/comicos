"""P100-21 recognition uses full uploaded image; crop is display-only in single-comic mode."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest import mock

from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401

from app.models.photo_import import (
    CAPTURE_MODE_SINGLE_COMIC,
    PhotoImportDetectedBook,
    PhotoImportImage,
    PhotoImportSession,
)
from app.services.photo_import_ai_recognition_service import run_ai_recognition_for_image
from app.services.photo_import_detection_service import detection_to_read


def test_single_comic_vision_runs_before_crop_save(tmp_path, monkeypatch) -> None:
    import app.services.photo_import_ai_recognition_service as ai_mod
    import app.services.photo_import_crop_service as crop_mod
    import app.services.photo_import_storage_service as storage_mod

    api_root = tmp_path / "api"
    api_root.mkdir()
    monkeypatch.setattr(storage_mod, "REPO_ROOT", api_root)
    monkeypatch.setattr(storage_mod, "LEGACY_APPS_ROOT", tmp_path / "apps")
    monkeypatch.setattr(storage_mod, "PHOTO_IMPORT_ROOT", api_root / "data" / "photo_import")
    monkeypatch.setattr(crop_mod, "REPO_ROOT", api_root)

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    src = api_root / "data" / "photo_import" / "uploads" / "falcon.jpg"
    src.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (800, 1200), color=(180, 40, 40)).save(src, format="JPEG")
    rel_path = str(src.relative_to(api_root)).replace("\\", "/")
    full_bytes = src.read_bytes()

    call_order: list[str] = []

    def fake_vision(image_bytes: bytes, *, image_id: int) -> dict:
        call_order.append("vision")
        assert image_bytes == full_bytes
        return {
            "books": [
                {
                    "bbox": {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.5},
                    "series_guess": "The Falcon",
                    "confidence": 0.92,
                }
            ]
        }

    def fake_crop(*args, **kwargs):
        call_order.append("crop")
        return crop_mod.extract_and_save_crop(*args, **kwargs)

    expires = datetime(2099, 1, 1, tzinfo=timezone.utc)
    with mock.patch.object(ai_mod, "_call_openai_vision", side_effect=fake_vision):
        with mock.patch.object(ai_mod, "extract_and_save_crop", side_effect=fake_crop):
            with Session(engine) as session:
                session.add(
                    PhotoImportSession(
                        id=1,
                        user_id=1,
                        session_token="full-image-tok",
                        expires_at=expires,
                        capture_mode=CAPTURE_MODE_SINGLE_COMIC,
                    )
                )
                session.add(
                    PhotoImportImage(
                        id=50,
                        session_id=1,
                        user_id=1,
                        storage_path=rel_path,
                        mime_type="image/jpeg",
                        file_size=len(full_bytes),
                    )
                )
                session.commit()
                run_ai_recognition_for_image(session, image_id=50)
                assert call_order == ["vision", "crop"]
                row = session.exec(select(PhotoImportDetectedBook).where(PhotoImportDetectedBook.image_id == 50)).one()
                assert row.ai_series == "The Falcon"


def test_detection_read_exposes_source_image_and_full_image_metadata(tmp_path, monkeypatch) -> None:
    import app.services.photo_import_storage_service as storage_mod

    api_root = tmp_path / "api"
    api_root.mkdir()
    monkeypatch.setattr(storage_mod, "REPO_ROOT", api_root)

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    src = api_root / "data" / "photo_import" / "1" / "1" / "orig.jpg"
    src.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (100, 100), color=(1, 2, 3)).save(src, format="JPEG")
    rel_path = str(src.relative_to(api_root)).replace("\\", "/")

    expires = datetime(2099, 1, 1, tzinfo=timezone.utc)
    token = "read-meta-tok"
    with Session(engine) as session:
        session.add(
            PhotoImportSession(
                id=10,
                user_id=1,
                session_token=token,
                expires_at=expires,
                capture_mode=CAPTURE_MODE_SINGLE_COMIC,
            )
        )
        session.add(
            PhotoImportImage(
                id=60,
                session_id=10,
                user_id=1,
                storage_path=rel_path,
                mime_type="image/jpeg",
                file_size=1,
            )
        )
        session.add(
            PhotoImportDetectedBook(
                id=70,
                session_id=10,
                image_id=60,
                user_id=1,
                ai_series="Test",
            )
        )
        session.commit()
        det = session.get(PhotoImportDetectedBook, 70)
        assert det is not None
        read = detection_to_read(session, det, session_token=token)
        assert read.recognition_source == "full_image"
        assert read.display_crop is True
        assert read.source_image_url == f"/api/v1/photo-import/sessions/{token}/images/60/original"


def test_original_image_endpoint_serves_upload(client: TestClient, session: Session, tmp_path, monkeypatch) -> None:
    import app.services.photo_import_storage_service as storage_mod

    api_root = tmp_path / "api"
    api_root.mkdir()
    monkeypatch.setattr(storage_mod, "REPO_ROOT", api_root)

    src = api_root / "data" / "photo_import" / "9" / "9" / "phone.jpg"
    src.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 64), color=(255, 0, 0)).save(src, format="JPEG")
    rel_path = str(src.relative_to(api_root)).replace("\\", "/")

    expires = datetime(2099, 1, 1, tzinfo=timezone.utc)
    token = "orig-endpoint-tok"
    row = PhotoImportSession(
        user_id=1,
        session_token=token,
        expires_at=expires,
        capture_mode=CAPTURE_MODE_SINGLE_COMIC,
    )
    session.add(row)
    session.flush()
    img = PhotoImportImage(
        session_id=int(row.id),
        user_id=1,
        storage_path=rel_path,
        mime_type="image/jpeg",
        file_size=1,
        original_filename="phone.jpg",
    )
    session.add(img)
    session.commit()
    session.refresh(img)

    resp = client.get(f"/api/v1/photo-import/sessions/{token}/images/{img.id}/original")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("image/")
    assert len(resp.content) > 100
