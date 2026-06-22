from __future__ import annotations

from datetime import datetime, timezone
from unittest import mock

from PIL import Image
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401

from app.models.photo_import import (
    IMAGE_STATUS_PROCESSED,
    PhotoImportImage,
    PhotoImportSession,
)
from app.services.photo_import_ai_recognition_service import _abs_path
from app.services.photo_import_processing_service import process_photo_import_image
from app.services.photo_import_storage_service import (
    relative_path_under_repo_root,
    resolve_photo_import_storage_path,
    upload_storage_dir,
)


def test_upload_path_resolves_under_canonical_api_root(tmp_path, monkeypatch) -> None:
    import app.services.photo_import_storage_service as storage_mod

    api_root = tmp_path / "api"
    api_root.mkdir()
    monkeypatch.setattr(storage_mod, "REPO_ROOT", api_root)
    monkeypatch.setattr(storage_mod, "LEGACY_APPS_ROOT", tmp_path / "apps")
    monkeypatch.setattr(storage_mod, "PHOTO_IMPORT_ROOT", api_root / "data" / "photo_import")

    dest_dir = upload_storage_dir(user_id=1, session_id=99)
    dest_path = dest_dir / "photo.jpg"
    Image.new("RGB", (100, 100), color=(1, 2, 3)).save(dest_path, format="JPEG")
    rel = relative_path_under_repo_root(dest_path)

    resolved = resolve_photo_import_storage_path(rel)
    assert resolved.is_file()
    assert resolved == dest_path
    assert _abs_path(rel).is_file()


def test_legacy_apps_data_path_still_resolves(tmp_path, monkeypatch) -> None:
    import app.services.photo_import_storage_service as storage_mod

    api_root = tmp_path / "api"
    api_root.mkdir()
    legacy_root = tmp_path / "apps"
    legacy_root.mkdir()
    monkeypatch.setattr(storage_mod, "REPO_ROOT", api_root)
    monkeypatch.setattr(storage_mod, "LEGACY_APPS_ROOT", legacy_root)

    rel = "data/photo_import/1/2/legacy.png"
    legacy_file = legacy_root / rel
    legacy_file.parent.mkdir(parents=True)
    Image.new("RGB", (50, 50), color=(9, 9, 9)).save(legacy_file, format="PNG")

    assert not (api_root / rel).is_file()
    resolved = resolve_photo_import_storage_path(rel)
    assert resolved.is_file()
    assert resolved == legacy_file


def test_process_photo_import_image_opens_uploaded_file(tmp_path, monkeypatch) -> None:
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

    dest_dir = upload_storage_dir(user_id=1, session_id=5)
    dest_path = dest_dir / "group.jpg"
    Image.new("RGB", (400, 300), color=(40, 40, 40)).save(dest_path, format="JPEG")
    rel = relative_path_under_repo_root(dest_path)

    one_book = {
        "books": [
            {
                "bbox": {"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.8},
                "series_guess": "Test Series",
                "confidence": 0.5,
            }
        ]
    }

    from app.models.photo_import_vision_read import PhotoImportVisionRead
    from app.services.photo_import_vision_sandbox_service import VisionSandboxReadResult

    fake_vision = VisionSandboxReadResult(
        publisher="Test Pub",
        series="Test Series",
        issue_number="1",
        issue_title="",
        variant_description="",
        year="",
        cover_date="",
        barcode="",
        confidence=0.5,
        reasoning="test",
        possible_alternates=[],
        raw_response={"parsed": {}},
        raw_response_text="{}",
    )

    expires = datetime(2099, 1, 1, tzinfo=timezone.utc)
    with mock.patch(
        "app.services.photo_import_vision_sandbox_service.read_comics_with_gpt_vision",
        return_value=[fake_vision],
    ):
        with Session(engine) as session:
            session.add(PhotoImportSession(id=5, user_id=1, session_token="tok", expires_at=expires))
            session.add(
                PhotoImportImage(
                    id=20,
                    session_id=5,
                    user_id=1,
                    storage_path=rel,
                    mime_type="image/jpeg",
                    file_size=1,
                    status="uploaded",
                )
            )
            session.commit()
            process_photo_import_image(session, image_id=20)
            img = session.get(PhotoImportImage, 20)
            assert img is not None
            assert img.status == IMAGE_STATUS_PROCESSED
            read = session.exec(select(PhotoImportVisionRead).where(PhotoImportVisionRead.image_id == 20)).first()
            assert read is not None
            assert read.series == "Test Series"
