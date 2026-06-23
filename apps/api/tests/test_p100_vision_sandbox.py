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


def test_parse_sandbox_rejects_subtitle_as_issue_number() -> None:
    from app.services.photo_import_vision_sandbox_service import _parse_sandbox_payload

    row = _parse_sandbox_payload(
        {
            "publisher": "Marvel",
            "series": "The Initiative",
            "issue_number": "The Initiative",
            "confidence": 0.8,
            "reasoning": "Cover art",
        }
    )
    assert row.issue_number is None


def test_parse_sandbox_keeps_issue_number_even_at_zero_confidence() -> None:
    from app.services.photo_import_vision_sandbox_service import _parse_sandbox_payload

    # We no longer blank low-confidence issue numbers: dropping them turned valid reads
    # into empty fields. Sticker/noise filtering is handled by the prompts instead.
    row = _parse_sandbox_payload(
        {
            "publisher": "DC",
            "series": "Superman",
            "issue_number": "1",
            "confidence": 0,
            "reasoning": "Green price sticker visible",
        }
    )
    assert row.issue_number == "1"


def test_parse_sandbox_keeps_issue_one_when_reasoning_confirms() -> None:
    from app.services.photo_import_vision_sandbox_service import _parse_sandbox_payload

    row = _parse_sandbox_payload(
        {
            "publisher": "DC",
            "series": "Justice League",
            "issue_number": "1",
            "confidence": 0,
            "reasoning": "Printed issue #1 in the corner box",
        }
    )
    assert row.issue_number == "1"
