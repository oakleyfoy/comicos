"""P100 single-comic fast capture mode."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest import mock

from PIL import Image
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401

from app.models.photo_import import (
    CAPTURE_MODE_GROUP,
    CAPTURE_MODE_SINGLE_COMIC,
    PhotoImportDetectedBook,
    PhotoImportImage,
    PhotoImportSession,
)
from app.services.photo_import_ai_recognition_service import (
    resolve_single_comic_book,
    run_ai_recognition_for_image,
)


def test_single_comic_upload_creates_one_detection(tmp_path, monkeypatch) -> None:
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

    src = api_root / "data" / "photo_import" / "solo.jpg"
    src.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (400, 600), color=(20, 20, 20)).save(src, format="JPEG")
    rel_path = str(src.relative_to(api_root)).replace("\\", "/")

    six_books = {
        "books": [
            {
                "bbox": {"x": i * 0.16, "y": 0.1, "width": 0.14, "height": 0.8},
                "series_guess": f"Series {i + 1}",
                "confidence": 0.5 + i * 0.05,
            }
            for i in range(6)
        ]
    }

    expires = datetime(2099, 1, 1, tzinfo=timezone.utc)
    with mock.patch.object(ai_mod, "_call_openai_vision", return_value=six_books):
        with mock.patch.object(ai_mod, "resolve_books_for_image") as resolve_group:
            with Session(engine) as session:
                session.add(
                    PhotoImportSession(
                        id=1,
                        user_id=1,
                        session_token="single",
                        expires_at=expires,
                        capture_mode=CAPTURE_MODE_SINGLE_COMIC,
                    )
                )
                session.add(
                    PhotoImportImage(
                        id=20,
                        session_id=1,
                        user_id=1,
                        storage_path=rel_path,
                        mime_type="image/jpeg",
                        file_size=1,
                    )
                )
                session.commit()
                run_ai_recognition_for_image(session, image_id=20)
                resolve_group.assert_not_called()
                rows = session.exec(select(PhotoImportDetectedBook).where(PhotoImportDetectedBook.image_id == 20)).all()
                assert len(rows) == 1
                assert rows[0].ai_series == "Series 6"


def test_multiple_single_comic_uploads_create_multiple_detections(tmp_path, monkeypatch) -> None:
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

    expires = datetime(2099, 1, 1, tzinfo=timezone.utc)
    payload = {
        "books": [
            {
                "bbox": {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.8},
                "series_guess": "Solo",
                "confidence": 0.9,
            }
        ]
    }

    with mock.patch.object(ai_mod, "_call_openai_vision", return_value=payload):
        with Session(engine) as session:
            session.add(
                PhotoImportSession(
                    id=2,
                    user_id=1,
                    session_token="multi",
                    expires_at=expires,
                    capture_mode=CAPTURE_MODE_SINGLE_COMIC,
                )
            )
            for image_id in (30, 31, 32):
                src = api_root / "data" / "photo_import" / f"{image_id}.jpg"
                src.parent.mkdir(parents=True, exist_ok=True)
                Image.new("RGB", (400, 600), color=(30, 30, 30)).save(src, format="JPEG")
                rel_path = str(src.relative_to(api_root)).replace("\\", "/")
                session.add(
                    PhotoImportImage(
                        id=image_id,
                        session_id=2,
                        user_id=1,
                        storage_path=rel_path,
                        mime_type="image/jpeg",
                        file_size=1,
                    )
                )
            session.commit()
            for image_id in (30, 31, 32):
                run_ai_recognition_for_image(session, image_id=image_id)
            rows = session.exec(select(PhotoImportDetectedBook).where(PhotoImportDetectedBook.session_id == 2)).all()
            assert len(rows) == 3
            assert len({row.image_id for row in rows}) == 3


def test_group_mode_still_uses_segmentation_pipeline(tmp_path, monkeypatch) -> None:
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

    src = api_root / "data" / "photo_import" / "group.jpg"
    src.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1200, 800), color=(40, 40, 40)).save(src, format="JPEG")
    rel_path = str(src.relative_to(api_root)).replace("\\", "/")

    six_books = {
        "books": [
            {
                "bbox": {"x": i * 0.16, "y": 0.1, "width": 0.14, "height": 0.8},
                "series_guess": f"Series {i + 1}",
                "confidence": 0.7,
            }
            for i in range(6)
        ]
    }

    expires = datetime(2099, 1, 1, tzinfo=timezone.utc)
    with mock.patch.object(ai_mod, "_call_openai_vision", return_value=six_books):
        with mock.patch.object(ai_mod, "resolve_books_for_image", wraps=ai_mod.resolve_books_for_image) as resolve_group:
            with Session(engine) as session:
                session.add(
                    PhotoImportSession(
                        id=4,
                        user_id=1,
                        session_token="group",
                        expires_at=expires,
                        capture_mode=CAPTURE_MODE_GROUP,
                    )
                )
                session.add(
                    PhotoImportImage(
                        id=40,
                        session_id=4,
                        user_id=1,
                        storage_path=rel_path,
                        mime_type="image/jpeg",
                        file_size=1,
                    )
                )
                session.commit()
                run_ai_recognition_for_image(session, image_id=40)
                resolve_group.assert_called_once()
                rows = session.exec(select(PhotoImportDetectedBook).where(PhotoImportDetectedBook.image_id == 40)).all()
                assert len(rows) == 6


def test_resolve_single_comic_does_not_split() -> None:
    books_raw = [
        {"bbox": {"x": 0, "y": 0, "width": 0.2, "height": 0.5}, "series_guess": "A", "confidence": 0.2},
        {"bbox": {"x": 0.2, "y": 0, "width": 0.2, "height": 0.5}, "series_guess": "B", "confidence": 0.95},
    ]
    books, meta = resolve_single_comic_book(image_id=1, books_raw=books_raw, raw_response={})
    assert len(books) == 1
    assert books[0]["series_guess"] == "B"
    assert books[0]["bbox"] == {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}
    assert meta.get("single_comic") is True
