"""Cover + barcode companion pairing for photo import."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest import mock

from PIL import Image
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401

from app.models.photo_import import (
    IMAGE_ROLE_BARCODE,
    IMAGE_ROLE_COVER,
    IMAGE_STATUS_PROCESSED,
    PhotoImportImage,
    PhotoImportSession,
)
from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.services.photo_import_barcode_companion_service import apply_barcode_companion_bytes


def test_barcode_companion_merges_into_cover_read_and_rematches(tmp_path, monkeypatch) -> None:
    import app.services.photo_import_storage_service as storage_mod

    api_root = tmp_path / "api"
    api_root.mkdir()
    monkeypatch.setattr(storage_mod, "REPO_ROOT", api_root)

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
        cover = PhotoImportImage(
            id=10,
            session_id=1,
            user_id=1,
            storage_path="cover.jpg",
            mime_type="image/jpeg",
            file_size=1,
            image_role=IMAGE_ROLE_COVER,
            status=IMAGE_STATUS_PROCESSED,
        )
        barcode_img = PhotoImportImage(
            id=11,
            session_id=1,
            user_id=1,
            storage_path="barcode.jpg",
            mime_type="image/jpeg",
            file_size=1,
            image_role=IMAGE_ROLE_BARCODE,
            pair_cover_image_id=10,
            status="uploaded",
        )
        read = PhotoImportVisionRead(
            id=20,
            session_id=1,
            image_id=10,
            series="Superman",
            issue_number="39",
            confidence=0.9,
        )
        session.add(cover)
        session.add(barcode_img)
        session.add(read)
        session.commit()

        extraction = {
            "barcode": "761941343730",
            "method": "local_decode",
            "confidence": 0.95,
            "barcode_type": "upc_a",
            "crop_used": "full",
            "error": None,
        }
        with mock.patch(
            "app.services.photo_import_barcode_companion_service.extract_barcode_from_image",
            return_value=extraction,
        ):
            with mock.patch(
                "app.services.photo_import_catalog_match_service.match_and_apply",
            ) as match_fn:
                cover_id, rows = apply_barcode_companion_bytes(
                    session,
                    barcode_image=barcode_img,
                    image_bytes=b"fake-barcode-bytes",
                )

    assert cover_id == 10
    assert len(rows) == 1
    assert rows[0].barcode == "761941343730"
    match_fn.assert_called_once()
