"""Regression tests for barcode vs cover fingerprint confidence hierarchy."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401

from app.models.asset_ledger import User
from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc
from app.models.intake_queue import (
    ITEM_AUTO_MATCHED,
    ITEM_NEEDS_REVIEW,
    IntakeSession,
    IntakeSessionItem,
    MATCH_SOURCE_CATALOG_UPC,
)
from app.services.intake_barcode_confidence import (
    CoverFingerprintOutcome,
    evaluate_cover_fingerprint_vs_barcode,
    is_validated_full_upc_exact_match,
)
import app.services.intake_worker_service as worker

FULL = "76194134192703921"


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_dc_superman_39(session: Session) -> int:
    pub = CatalogPublisher(name="DC Comics", normalized_name="dc comics")
    session.add(pub)
    session.commit()
    series = CatalogSeries(name="Superman", normalized_name="superman", publisher_id=pub.id)
    session.add(series)
    session.commit()
    issue = CatalogIssue(
        series_id=int(series.id),
        publisher_id=pub.id,
        issue_number="39",
        normalized_issue_number="39",
        cover_date=date(2015, 4, 1),
    )
    session.add(issue)
    session.commit()
    return int(issue.id)


def test_validated_full_upc_exact_match() -> None:
    assert is_validated_full_upc_exact_match(
        FULL, publisher="DC Comics", issue_number="39", year="2015"
    )


def test_evaluate_strong_barcode_94_fingerprint_is_informational_only(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = _engine()
    img = tmp_path / "c.jpg"
    Image.new("RGB", (10, 10), color=(0, 0, 0)).save(img, format="JPEG")
    with Session(engine) as session:
        issue_id = _seed_dc_superman_39(session)
        other_id = issue_id + 999
        monkeypatch.setattr(
            "app.services.intake_barcode_confidence.fingerprint_match_score_for_crop_path",
            lambda *a, **k: 10.0,
        )
        monkeypatch.setattr(
            "app.services.intake_barcode_confidence.search_catalog_fingerprint_hits_for_crop_path",
            lambda *a, **k: [SimpleNamespace(issue_id=other_id, confidence=0.94)],
        )
        outcome = evaluate_cover_fingerprint_vs_barcode(
            session,
            image_path=img,
            catalog_issue_id=issue_id,
            barcode_validation_strong=True,
            intake_item_id=1,
        )
        assert outcome.disagrees is True
        assert outcome.blocks_auto_match is False
        assert outcome.info_message is not None
        assert "94%" in outcome.info_message


def test_evaluate_weak_barcode_999_fingerprint_blocks(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = _engine()
    img = tmp_path / "c.jpg"
    Image.new("RGB", (10, 10), color=(0, 0, 0)).save(img, format="JPEG")
    with Session(engine) as session:
        issue_id = _seed_dc_superman_39(session)
        other_id = issue_id + 1
        monkeypatch.setattr(
            "app.services.intake_barcode_confidence.fingerprint_match_score_for_crop_path",
            lambda *a, **k: 10.0,
        )
        monkeypatch.setattr(
            "app.services.intake_barcode_confidence.search_catalog_fingerprint_hits_for_crop_path",
            lambda *a, **k: [SimpleNamespace(issue_id=other_id, confidence=0.999)],
        )
        outcome = evaluate_cover_fingerprint_vs_barcode(
            session,
            image_path=img,
            catalog_issue_id=issue_id,
            barcode_validation_strong=False,
        )
        assert outcome.blocks_auto_match is True


def test_worker_auto_matched_despite_94_fingerprint_disagreement(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.p105_comic_barcode_read_service import ComicBarcodeReadResult

    engine = _engine()
    with Session(engine) as session:
        session.add(User(id=1, email="o@example.com", password_hash="x"))
        session.commit()
        issue_id = _seed_dc_superman_39(session)
        session.add(
            CatalogUpc(
                issue_id=issue_id,
                upc=FULL,
                normalized_upc=FULL,
                source="test",
            )
        )
        intake = IntakeSession(
            user_id=1,
            session_token="t",
            status="active",
            expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        session.add(intake)
        session.commit()
        item = IntakeSessionItem(
            session_id=int(intake.id),
            user_id=1,
            storage_path="scan.jpg",
            status="queued",
        )
        session.add(item)
        session.commit()

        img = tmp_path / "scan.jpg"
        Image.new("RGB", (800, 1200), color=(1, 1, 1)).save(img, format="JPEG")
        monkeypatch.setattr(worker, "resolve_photo_import_storage_path", lambda *a, **k: img)
        supp = FULL[12:17]
        monkeypatch.setattr(
            worker,
            "read_comic_barcode_from_image_bytes",
            lambda *a, **k: ComicBarcodeReadResult(
                main_upc=FULL[:12],
                reconstructed_full=FULL,
                final_supplement=supp,
                decoded_supplement=supp,
                supplement_decode_confidence=0.99,
                confidence_main=0.95,
            ),
        )
        monkeypatch.setattr(
            worker,
            "evaluate_cover_fingerprint_vs_barcode",
            lambda *a, **k: CoverFingerprintOutcome(
                blocks_auto_match=False,
                info_message="Cover fingerprint favors another issue (94%). Review if desired.",
                fingerprint_issue_id=issue_id + 1,
                fingerprint_confidence=0.94,
                disagrees=True,
            ),
        )

        status = worker.process_intake_item(session, item_id=int(item.id))
        session.refresh(item)
        assert status == ITEM_AUTO_MATCHED
        assert item.match_source == MATCH_SOURCE_CATALOG_UPC
        assert item.reason is not None
        assert "Cover fingerprint favors" in item.reason


def test_fingerprint_only_no_barcode_does_not_auto_match_catalog(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.p105_comic_barcode_read_service import ComicBarcodeReadResult

    engine = _engine()
    with Session(engine) as session:
        session.add(User(id=1, email="o@example.com", password_hash="x"))
        session.commit()
        _seed_dc_superman_39(session)
        intake = IntakeSession(
            user_id=1,
            session_token="t",
            status="active",
            expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        session.add(intake)
        session.commit()
        item = IntakeSessionItem(session_id=int(intake.id), user_id=1, storage_path="scan.jpg", status="queued")
        session.add(item)
        session.commit()

        img = tmp_path / "scan.jpg"
        Image.new("RGB", (800, 1200), color=(1, 1, 1)).save(img, format="JPEG")
        monkeypatch.setattr(worker, "resolve_photo_import_storage_path", lambda *a, **k: img)
        monkeypatch.setattr(
            worker,
            "read_comic_barcode_from_image_bytes",
            lambda *a, **k: ComicBarcodeReadResult(main_upc="", reconstructed_full=""),
        )
        monkeypatch.setattr(worker, "extract_barcode_from_image", lambda *a, **k: {"barcode": None})

        status = worker.process_intake_item(session, item_id=int(item.id))
        assert status != ITEM_AUTO_MATCHED
