"""P105 barcode attach / missing-barcode repair queue."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401

from app.models.asset_ledger import User
from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc
from app.models.intake_queue import (
    ComicIssueBarcode,
    ITEM_AUTO_MATCHED,
    ITEM_NEEDS_REVIEW,
    IntakeSession,
    IntakeSessionItem,
    MATCH_SOURCE_CATALOG_UPC,
    MATCH_SOURCE_LEARNED,
)
from app.models.p105_barcode_repair import P105MissingBarcodeQueue, P105_QUEUE_PENDING, P105_QUEUE_RESOLVED
from app.services.p105_barcode_repair_service import (
    BarcodeAttachConflict,
    BarcodeAttachError,
    attach_barcode_to_catalog_issue,
    require_full_direct_market_barcode,
)
import app.services.intake_queue_service as intake_svc
import app.services.intake_worker_service as worker

FULL_BARCODE = "76194134192703921"
BASE_ONLY = "761941341927"


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_user(session: Session) -> None:
    session.add(User(id=1, email="o@example.com", password_hash="x"))
    session.commit()


def _seed_dc_superman_39(session: Session) -> int:
    pub = CatalogPublisher(name="DC Comics", normalized_name="dc comics")
    session.add(pub)
    session.commit()
    series = CatalogSeries(name="Superman", normalized_name="superman", publisher_id=pub.id)
    session.add(series)
    session.commit()
    issue39 = CatalogIssue(
        series_id=int(series.id),
        publisher_id=pub.id,
        issue_number="39",
        normalized_issue_number="39",
        cover_date=date(2015, 4, 1),
    )
    issue13 = CatalogIssue(
        series_id=int(series.id),
        publisher_id=pub.id,
        issue_number="13",
        normalized_issue_number="13",
        cover_date=date(2015, 1, 1),
    )
    session.add(issue39)
    session.add(issue13)
    session.commit()
    return int(issue39.id)


def _intake_item(session: Session, *, barcode: str) -> IntakeSessionItem:
    intake = IntakeSession(
        user_id=1,
        session_token="tok",
        status="active",
        expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    session.add(intake)
    session.commit()
    item = IntakeSessionItem(
        session_id=int(intake.id),
        user_id=1,
        storage_path="scan.jpg",
        status=ITEM_NEEDS_REVIEW,
        normalized_barcode=barcode,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def test_base_only_barcode_cannot_attach() -> None:
    with pytest.raises(BarcodeAttachError, match="Base UPC only"):
        require_full_direct_market_barcode(BASE_ONLY)


def test_attach_creates_learned_and_catalog_upc() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_user(session)
        issue_id = _seed_dc_superman_39(session)
        result = attach_barcode_to_catalog_issue(
            session,
            barcode=FULL_BARCODE,
            catalog_issue_id=issue_id,
            user_id=1,
        )
        session.commit()
        assert result.learned_created is True
        assert result.catalog_upc_created is True
        upc = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == FULL_BARCODE)).one()
        assert int(upc.issue_id) == issue_id
        learned = session.exec(
            select(ComicIssueBarcode).where(ComicIssueBarcode.normalized_barcode == FULL_BARCODE)
        ).one()
        assert learned.catalog_issue_id == issue_id


def test_conflict_cannot_attach_different_issue() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_user(session)
        issue_id = _seed_dc_superman_39(session)
        issue13 = session.exec(select(CatalogIssue).where(CatalogIssue.issue_number == "13")).one()
        attach_barcode_to_catalog_issue(session, barcode=FULL_BARCODE, catalog_issue_id=issue_id, user_id=1)
        session.commit()
        with pytest.raises(BarcodeAttachConflict):
            attach_barcode_to_catalog_issue(
                session,
                barcode=FULL_BARCODE,
                catalog_issue_id=int(issue13.id),
                user_id=1,
            )


def test_choose_missing_upc_creates_mappings_and_reprocesses(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PIL import Image

    from app.services.p105_comic_barcode_read_service import ComicBarcodeReadResult

    engine = _engine()
    with Session(engine) as session:
        _seed_user(session)
        issue_id = _seed_dc_superman_39(session)
        item = _intake_item(session, barcode=FULL_BARCODE)

        img = tmp_path / "scan.jpg"
        Image.new("RGB", (800, 1200), color=(1, 1, 1)).save(img, format="JPEG")
        monkeypatch.setattr(worker, "resolve_photo_import_storage_path", lambda *a, **k: img)
        supp = FULL_BARCODE[12:17]
        monkeypatch.setattr(
            worker,
            "read_comic_barcode_from_image_bytes",
            lambda *a, **k: ComicBarcodeReadResult(
                main_upc=FULL_BARCODE[:12],
                reconstructed_full=FULL_BARCODE,
                final_supplement=supp,
                decoded_supplement=supp,
                supplement_decode_confidence=0.99,
                confidence_main=0.95,
            ),
        )

        intake_svc.choose_intake_item_issue(
            session, item_id=int(item.id), owner_user_id=1, catalog_issue_id=issue_id
        )
        session.refresh(item)
        assert item.status == ITEM_AUTO_MATCHED
        assert item.match_source in {MATCH_SOURCE_LEARNED, MATCH_SOURCE_CATALOG_UPC}
        learned = session.exec(
            select(ComicIssueBarcode).where(ComicIssueBarcode.normalized_barcode == FULL_BARCODE)
        ).one()
        assert learned.catalog_issue_id == issue_id
        upc = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == FULL_BARCODE)).one()
        assert int(upc.issue_id) == issue_id


def test_future_scan_auto_matches_after_learned(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from PIL import Image

    from app.services.p105_comic_barcode_read_service import ComicBarcodeReadResult

    engine = _engine()
    with Session(engine) as session:
        _seed_user(session)
        issue_id = _seed_dc_superman_39(session)
        attach_barcode_to_catalog_issue(session, barcode=FULL_BARCODE, catalog_issue_id=issue_id, user_id=1)
        session.commit()

        item = _intake_item(session, barcode=FULL_BARCODE)
        img = tmp_path / "scan.jpg"
        Image.new("RGB", (800, 1200), color=(1, 1, 1)).save(img, format="JPEG")
        monkeypatch.setattr(worker, "resolve_photo_import_storage_path", lambda *a, **k: img)
        supp = FULL_BARCODE[12:17]
        monkeypatch.setattr(
            worker,
            "read_comic_barcode_from_image_bytes",
            lambda *a, **k: ComicBarcodeReadResult(
                main_upc=FULL_BARCODE[:12],
                reconstructed_full=FULL_BARCODE,
                final_supplement=supp,
                decoded_supplement=supp,
                supplement_decode_confidence=0.99,
                confidence_main=0.95,
            ),
        )

        status = worker.process_intake_item(session, item_id=int(item.id))
        session.refresh(item)
        assert status == ITEM_AUTO_MATCHED
        assert item.match_source == MATCH_SOURCE_LEARNED


def test_worker_enqueues_missing_barcode_queue(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from PIL import Image

    from app.services.p105_comic_barcode_read_service import ComicBarcodeReadResult

    engine = _engine()
    with Session(engine) as session:
        _seed_user(session)
        _seed_dc_superman_39(session)
        item = _intake_item(session, barcode=FULL_BARCODE)
        img = tmp_path / "scan.jpg"
        Image.new("RGB", (800, 1200), color=(1, 1, 1)).save(img, format="JPEG")
        monkeypatch.setattr(worker, "resolve_photo_import_storage_path", lambda *a, **k: img)
        supp = FULL_BARCODE[12:17]
        monkeypatch.setattr(
            worker,
            "read_comic_barcode_from_image_bytes",
            lambda *a, **k: ComicBarcodeReadResult(
                main_upc=FULL_BARCODE[:12],
                reconstructed_full=FULL_BARCODE,
                final_supplement=supp,
                decoded_supplement=supp,
                supplement_decode_confidence=0.99,
                confidence_main=0.95,
            ),
        )
        worker.process_intake_item(session, item_id=int(item.id))
        row = session.exec(
            select(P105MissingBarcodeQueue).where(P105MissingBarcodeQueue.intake_item_id == item.id)
        ).one()
        assert row.barcode == FULL_BARCODE
        assert row.status == P105_QUEUE_PENDING
        assert row.issue_number_from_supplement == "39"

        issue_id = int(
            session.exec(select(CatalogIssue).where(CatalogIssue.issue_number == "39")).one().id
        )
        attach = attach_barcode_to_catalog_issue(
            session, barcode=FULL_BARCODE, catalog_issue_id=issue_id, user_id=1
        )
        from app.services.p105_barcode_repair_service import resolve_missing_barcode_queue

        resolve_missing_barcode_queue(
            session,
            barcode=FULL_BARCODE,
            catalog_issue_id=issue_id,
            intake_item_id=int(item.id),
            attach=attach,
        )
        session.commit()
        session.refresh(row)
        assert row.status == P105_QUEUE_RESOLVED
