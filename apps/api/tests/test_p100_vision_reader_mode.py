"""P100-25 pure GPT vision reader mode."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest import mock

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401

from app.main import app
from app.models.photo_import import PhotoImportCandidate, PhotoImportDetectedBook, PhotoImportImage, PhotoImportSession
from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.services.photo_import_processing_service import process_photo_import_image
from app.services.photo_import_sandbox_flags import assert_photo_import_matching_allowed
from app.services.photo_import_vision_sandbox_service import VisionSandboxReadResult


def test_confirm_blocked_in_sandbox(monkeypatch) -> None:
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


def test_sandbox_does_not_call_catalog_scoring(tmp_path, monkeypatch) -> None:
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
        issue_title="Take Flight",
        variant_description="",
        year="2017",
        cover_date="",
        barcode="",
        confidence=0.91,
        reasoning="Cover art match",
        possible_alternates=["The Falcon"],
        raw_response={"parsed": {}},
        raw_response_text="{}",
    )

    with mock.patch(
        "app.services.photo_import_vision_sandbox_service.read_comic_with_gpt_vision",
        return_value=fake,
    ):
        with mock.patch(
            "app.services.photo_import_candidate_service.generate_scored_candidates",
        ) as gen:
            with Session(engine) as session:
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
                gen.assert_not_called()
                assert session.exec(select(PhotoImportCandidate)).first() is None
                assert session.exec(select(PhotoImportDetectedBook)).first() is None
                read = session.exec(select(PhotoImportVisionRead)).one()
                assert read.series == "Falcon"
                assert read.possible_alternates == ["The Falcon"]

    get_settings.cache_clear()


def test_vision_read_api_returns_gpt_fields(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PHOTO_IMPORT_VISION_SANDBOX", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as session:
            yield session

    from app.db.session import get_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with Session(engine) as session:
            session.add(
                PhotoImportSession(
                    id=1,
                    user_id=1,
                    session_token="tok-api",
                    expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
                )
            )
            session.add(
                PhotoImportImage(
                    id=1,
                    session_id=1,
                    user_id=1,
                    storage_path="x.jpg",
                    mime_type="image/jpeg",
                    file_size=1,
                )
            )
            session.add(
                PhotoImportVisionRead(
                    session_id=1,
                    image_id=1,
                    publisher="Vertigo",
                    series="Preacher",
                    issue_number="58",
                    confidence=0.94,
                    reasoning="Trade dress",
                    possible_alternates=["Preacher (1995)"],
                )
            )
            session.commit()
        client = TestClient(app)
        res = client.get("/api/v1/photo-import/vision-read/1?session_token=tok-api")
        assert res.status_code == 200
        body = res.json()
        assert body["series"] == "Preacher"
        assert body["issue_number"] == "58"
        assert body["possible_alternates"] == ["Preacher (1995)"]
        assert "catalog" not in str(body).lower()
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
