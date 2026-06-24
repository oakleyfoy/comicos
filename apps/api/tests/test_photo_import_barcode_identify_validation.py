"""Barcode-primary identify refuses unsafe catalog matches end-to-end."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401

from app.models.photo_import import IMAGE_ROLE_BARCODE_PRIMARY, PhotoImportImage, PhotoImportSession
from app.services import photo_import_barcode_identify_service as svc

SUPERMAN_39_FULL = "76194134192703921"


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
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
            id=7,
            session_id=1,
            user_id=1,
            storage_path="bc.jpg",
            mime_type="image/jpeg",
            file_size=1,
            image_role=IMAGE_ROLE_BARCODE_PRIMARY,
        )
    )
    session.commit()
    return session


def test_modern_dc_barcode_rejects_harvey_record(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    image = session.get(PhotoImportImage, 7)

    monkeypatch.setattr(svc, "extract_barcode_from_image", lambda *a, **k: {"barcode": SUPERMAN_39_FULL})
    monkeypatch.setattr(
        svc,
        "lookup_comicvine_by_barcode",
        lambda _b: {
            "matched": True,
            "publisher": "Harvey",
            "series": "Chamber of Chills Magazine",
            "issue_number": "13",
            "cover_date": "1952-06-01",
            "name": "Chamber of Chills",
        },
    )

    outcome = svc.identify_and_persist_barcode_primary(session, image=image, image_bytes=b"x")

    assert outcome.status == "no_safe_match"
    assert outcome.detected_barcode == SUPERMAN_39_FULL
    assert outcome.rows == []
    assert "Harvey" in outcome.reason


def test_base_upc_only_is_ambiguous(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    image = session.get(PhotoImportImage, 7)

    monkeypatch.setattr(svc, "extract_barcode_from_image", lambda *a, **k: {"barcode": "761941341927"})

    outcome = svc.identify_and_persist_barcode_primary(session, image=image, image_bytes=b"x")

    assert outcome.status == "ambiguous_base_upc"
    assert outcome.detected_barcode == "761941341927"
    assert outcome.rows == []


def test_not_found_when_no_catalog_or_comicvine(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    image = session.get(PhotoImportImage, 7)

    monkeypatch.setattr(svc, "extract_barcode_from_image", lambda *a, **k: {"barcode": SUPERMAN_39_FULL})
    monkeypatch.setattr(svc, "lookup_comicvine_by_barcode", lambda _b: {"matched": False})

    outcome = svc.identify_and_persist_barcode_primary(session, image=image, image_bytes=b"x")

    assert outcome.status == "not_found"
    assert outcome.detected_barcode == SUPERMAN_39_FULL
