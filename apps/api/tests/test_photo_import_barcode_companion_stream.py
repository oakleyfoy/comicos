"""Quick vision stream for barcode companion skips GPT."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest import mock

from PIL import Image
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401

from app.models.photo_import import IMAGE_ROLE_BARCODE, PhotoImportImage, PhotoImportSession
from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.services.photo_import_vision_stream_service import iter_vision_read_sse


def test_barcode_companion_stream_skips_gpt(tmp_path, monkeypatch) -> None:
    import app.services.photo_import_storage_service as storage_mod

    api_root = tmp_path / "api"
    api_root.mkdir()
    monkeypatch.setattr(storage_mod, "REPO_ROOT", api_root)

    src = api_root / "bc.jpg"
    Image.new("RGB", (100, 50), color=(1, 1, 1)).save(src, format="JPEG")
    rel = str(src.relative_to(api_root)).replace("\\", "/")

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

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
                id=5,
                session_id=1,
                user_id=1,
                storage_path=rel,
                mime_type="image/jpeg",
                file_size=1,
                image_role=IMAGE_ROLE_BARCODE,
                pair_cover_image_id=10,
            )
        )
        session.commit()

        fake_read = PhotoImportVisionRead(
            id=1,
            session_id=1,
            image_id=10,
            series="Superman",
            issue_number="39",
            barcode="761941343730",
        )

        with mock.patch(
            "app.services.photo_import_barcode_companion_service.apply_barcode_companion_bytes",
            return_value=(10, [fake_read]),
        ):
            with mock.patch(
                "app.services.photo_import_vision_stream_service.stream_comic_vision_text",
            ) as gpt_stream:
                events = list(iter_vision_read_sse(session, image_id=5, force=True))

    gpt_stream.assert_not_called()
    assert any("barcode_companion" in e for e in events)
