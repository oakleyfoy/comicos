"""P100-24 vision sandbox pipeline."""

from __future__ import annotations

from unittest import mock

from PIL import Image
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401

from app.models.photo_import import PhotoImportDetectedBook, PhotoImportImage, PhotoImportSession
from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.services.photo_import_processing_service import process_photo_import_image
from app.services.photo_import_sandbox_flags import assert_photo_import_matching_allowed
from app.services.photo_import_vision_sandbox_service import VisionSandboxReadResult


def test_matching_blocked_when_sandbox_flag(monkeypatch) -> None:
    monkeypatch.setenv("PHOTO_IMPORT_VISION_SANDBOX", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        import pytest
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            assert_photo_import_matching_allowed()
        assert exc.value.status_code == 503
    finally:
        get_settings.cache_clear()


def test_sandbox_skips_detections(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PHOTO_IMPORT_VISION_SANDBOX", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()

    import app.services.photo_import_crop_service as crop_mod
    import app.services.photo_import_storage_service as storage_mod

    api_root = tmp_path / "api"
    api_root.mkdir(exist_ok=True)
    monkeypatch.setattr(storage_mod, "REPO_ROOT", api_root)
    monkeypatch.setattr(storage_mod, "LEGACY_APPS_ROOT", tmp_path / "apps")
    monkeypatch.setattr(storage_mod, "PHOTO_IMPORT_ROOT", api_root / "data" / "photo_import")
    monkeypatch.setattr(crop_mod, "REPO_ROOT", api_root)

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    src = api_root / "data" / "photo_import" / "1.jpg"
    src.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (400, 600), color=(10, 10, 10)).save(src, format="JPEG")
    rel = str(src.relative_to(api_root)).replace("\\", "/")

    fake = VisionSandboxReadResult(
        publisher="Marvel",
        series="Falcon",
        issue_number="1",
        issue_title="",
        variant_description="",
        year="2017",
        cover_date="",
        barcode="",
        confidence=0.9,
        reasoning="Test",
        raw_response={"parsed": {}},
        raw_response_text="{}",
    )

    with mock.patch(
        "app.services.photo_import_vision_sandbox_service.read_comics_with_gpt_vision",
        return_value=[fake],
    ):
        with Session(engine) as session:
            from datetime import datetime, timezone

            session.add(
                PhotoImportSession(
                    id=1,
                    user_id=1,
                    session_token="tok",
                    expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
                )
            )
            session.add(
                PhotoImportImage(
                    id=1,
                    session_id=1,
                    user_id=1,
                    storage_path=rel,
                    mime_type="image/jpeg",
                    file_size=1,
                )
            )
            session.commit()
            process_photo_import_image(session, image_id=1)
            dets = session.exec(select(PhotoImportDetectedBook)).all()
            reads = session.exec(select(PhotoImportVisionRead)).all()
            assert len(dets) == 0
            assert len(reads) == 1
            assert reads[0].series == "Falcon"

    get_settings.cache_clear()
