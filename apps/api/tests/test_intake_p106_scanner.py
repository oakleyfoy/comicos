"""Intake scanner integration with P106 GCD barcode gap resolver."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401

from app.models.asset_ledger import User
from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc
from app.models.intake_queue import (
    ITEM_AUTO_MATCHED,
    ITEM_NEEDS_REVIEW,
    ITEM_QUEUED,
    IntakeSession,
    IntakeSessionItem,
    MATCH_SOURCE_CATALOG_UPC,
)
from app.services.gcd_barcode_import_service import gcd_engine_from
from app.services.intake_barcode_confidence import CoverFingerprintOutcome
from app.services.p105_comic_barcode_read_service import ComicBarcodeReadResult
import app.services.intake_queue_service as svc
import app.services.intake_worker_service as worker

SUPERMAN_19_BC = "76194134192701911"
GCD_ISSUE_ID = 1680372


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


def _gcd_db(tmp_path: Path) -> Path:
    path = tmp_path / "gcd.sqlite"
    engine = gcd_engine_from(str(path))
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE gcd_publisher (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(
            text(
                "CREATE TABLE gcd_series (id INTEGER PRIMARY KEY, name TEXT, year_began INTEGER, publisher_id INTEGER)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE gcd_issue (id INTEGER PRIMARY KEY, number TEXT, barcode TEXT, key_date TEXT, "
                "series_id INTEGER, title TEXT, notes TEXT)"
            )
        )
        conn.execute(text("INSERT INTO gcd_publisher (id, name) VALUES (1, 'DC')"))
        conn.execute(
            text("INSERT INTO gcd_series (id, name, year_began, publisher_id) VALUES (1, 'Superman', 2016, 1)")
        )
        conn.execute(
            text(
                "INSERT INTO gcd_issue (id, number, barcode, key_date, series_id, title, notes) "
                "VALUES (:id, '19', :bc, '2017-05-00', 1, '', '')"
            ),
            {"id": GCD_ISSUE_ID, "bc": SUPERMAN_19_BC},
        )
    return path


def _seed_user(session: Session) -> None:
    session.add(User(id=1, email="o@example.com", password_hash="x"))
    session.commit()


def _intake_session(session: Session) -> IntakeSession:
    row = IntakeSession(
        user_id=1,
        session_token="tok-p106",
        status="active",
        expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _queued_item(session: Session, *, session_id: int, storage_path: str) -> IntakeSessionItem:
    item = IntakeSessionItem(
        session_id=session_id,
        user_id=1,
        storage_path=storage_path,
        status=ITEM_QUEUED,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def _seed_superman_19(session: Session) -> int:
    pub = CatalogPublisher(name="DC", normalized_name="dc")
    session.add(pub)
    session.flush()
    series = CatalogSeries(name="Superman", normalized_name="superman", publisher_id=pub.id, year_began=2016)
    session.add(series)
    session.flush()
    issue = CatalogIssue(
        series_id=int(series.id),
        publisher_id=pub.id,
        issue_number="19",
        normalized_issue_number="19",
        cover_date=date(2017, 5, 1),
    )
    session.add(issue)
    session.commit()
    return int(issue.id)


def _worker_mocks(tmp_path, monkeypatch: pytest.MonkeyPatch, *, barcode: str) -> None:
    from PIL import Image

    img = tmp_path / "scan.jpg"
    Image.new("RGB", (800, 1200), color=(3, 3, 3)).save(img, format="JPEG")
    supp = barcode[12:17]
    monkeypatch.setattr(worker, "resolve_photo_import_storage_path", lambda *a, **k: img)
    monkeypatch.setattr(
        worker,
        "read_comic_barcode_from_image_bytes",
        lambda *a, **k: ComicBarcodeReadResult(
            main_upc=barcode[:12],
            reconstructed_full=barcode,
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
            info_message=None,
            fingerprint_issue_id=None,
            fingerprint_confidence=None,
            disagrees=False,
        ),
    )
    monkeypatch.setattr(worker, "lookup_comicvine_by_barcode", lambda _b: None)


def _patch_gcd_path(monkeypatch: pytest.MonkeyPatch, gcd_path: Path) -> None:
    import app.services.gcd_catalog_import_dashboard_service as gcd_dash

    monkeypatch.setattr(gcd_dash, "resolve_gcd_path", lambda override=None: gcd_path)
    monkeypatch.setattr(gcd_dash, "resolve_cache_path", lambda override=None: None)


@pytest.mark.parametrize("auto_resolve", [False, True])
def test_scanner_p106_diagnose_and_import_accept(
    tmp_path, monkeypatch: pytest.MonkeyPatch, auto_resolve: bool
) -> None:
    gcd_path = _gcd_db(tmp_path)
    _patch_gcd_path(monkeypatch, gcd_path)
    monkeypatch.setattr(worker, "AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP", auto_resolve)
    _worker_mocks(tmp_path, monkeypatch, barcode=SUPERMAN_19_BC)

    engine = _engine()
    with Session(engine) as session:
        _seed_user(session)
        intake = _intake_session(session)
        item = _queued_item(session, session_id=int(intake.id), storage_path="scan.jpg")

        status = worker.process_intake_item(session, item_id=int(item.id))
        session.refresh(item)

        if auto_resolve:
            assert status == ITEM_AUTO_MATCHED
            assert item.selected_catalog_issue_id is not None
            assert item.matched_series == "Superman"
            assert item.matched_issue_number == "19"
            return

        assert status == ITEM_NEEDS_REVIEW
        assert item.matched_series == "Superman"
        gap = (item.barcode_read_json and __import__("json").loads(item.barcode_read_json).get("barcode_gap")) or {}
        assert gap.get("action") == "auto_import_available"
        assert gap.get("gcd_issue_id") == GCD_ISSUE_ID

        svc.import_and_accept_intake_item(session, item_id=int(item.id), owner_user_id=1)
        session.refresh(item)
        assert item.selected_catalog_issue_id is not None
        assert item.status == ITEM_AUTO_MATCHED
        upc = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == SUPERMAN_19_BC)).first()
        assert upc is not None


def test_scanner_p106_auto_attaches_existing_catalog_issue(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    gcd_path = _gcd_db(tmp_path)
    _patch_gcd_path(monkeypatch, gcd_path)
    monkeypatch.setattr(worker, "AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP", False)
    _worker_mocks(tmp_path, monkeypatch, barcode=SUPERMAN_19_BC)

    engine = _engine()
    with Session(engine) as session:
        _seed_user(session)
        issue_id = _seed_superman_19(session)
        intake = _intake_session(session)
        item = _queued_item(session, session_id=int(intake.id), storage_path="scan.jpg")

        status = worker.process_intake_item(session, item_id=int(item.id))
        session.refresh(item)
        assert status == ITEM_NEEDS_REVIEW
        gap = __import__("json").loads(item.barcode_read_json or "{}").get("barcode_gap") or {}
        assert gap.get("action") == "auto_import_available"
        assert gap.get("catalog_issue_id") == issue_id

        svc.import_and_accept_intake_item(session, item_id=int(item.id), owner_user_id=1)
        session.refresh(item)
        assert item.selected_catalog_issue_id == issue_id
        upc = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == SUPERMAN_19_BC)).first()
        assert upc is not None and int(upc.issue_id) == issue_id


def test_scanner_no_gcd_comicvine_fallback(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "other_gcd.sqlite"
    engine = gcd_engine_from(str(path))
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE gcd_publisher (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(
            text(
                "CREATE TABLE gcd_series (id INTEGER PRIMARY KEY, name TEXT, year_began INTEGER, publisher_id INTEGER)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE gcd_issue (id INTEGER PRIMARY KEY, number TEXT, barcode TEXT, key_date TEXT, "
                "series_id INTEGER, title TEXT, notes TEXT)"
            )
        )
        conn.execute(text("INSERT INTO gcd_publisher (id, name) VALUES (1, 'DC')"))
        conn.execute(
            text("INSERT INTO gcd_series (id, name, year_began, publisher_id) VALUES (1, 'Superman', 2016, 1)")
        )
        conn.execute(
            text(
                "INSERT INTO gcd_issue (id, number, barcode, key_date, series_id, title, notes) "
                "VALUES (99, '1', '76194134192700111', '2016-01-00', 1, '', '')"
            )
        )
    _patch_gcd_path(monkeypatch, path)
    monkeypatch.setattr(worker, "AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP", False)
    _worker_mocks(tmp_path, monkeypatch, barcode=SUPERMAN_19_BC)
    monkeypatch.setattr(
        worker,
        "lookup_comicvine_by_barcode",
        lambda _b: {
            "matched": True,
            "publisher": "DC",
            "series": "Superman",
            "issue_number": "19",
            "cover_date": "2017-05-01",
        },
    )

    engine = _engine()
    with Session(engine) as session:
        _seed_user(session)
        intake = _intake_session(session)
        item = _queued_item(session, session_id=int(intake.id), storage_path="scan.jpg")

        status = worker.process_intake_item(session, item_id=int(item.id))
        session.refresh(item)
        assert status in {ITEM_NEEDS_REVIEW, "ready_for_review"}
        gap = __import__("json").loads(item.barcode_read_json or "{}").get("barcode_gap") or {}
        assert gap.get("gcd_match_count") == 0
        assert gap.get("action") == "comicvine_fallback"


def test_scanner_gcd_conflict_review_not_manual_barcode(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "dup_gcd.sqlite"
    engine = gcd_engine_from(str(path))
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE gcd_publisher (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(
            text(
                "CREATE TABLE gcd_series (id INTEGER PRIMARY KEY, name TEXT, year_began INTEGER, publisher_id INTEGER)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE gcd_issue (id INTEGER PRIMARY KEY, number TEXT, barcode TEXT, key_date TEXT, "
                "series_id INTEGER, title TEXT, notes TEXT)"
            )
        )
        conn.execute(text("INSERT INTO gcd_publisher (id, name) VALUES (1, 'DC')"))
        conn.execute(
            text("INSERT INTO gcd_series (id, name, year_began, publisher_id) VALUES (1, 'Superman', 2016, 1)")
        )
        conn.execute(
            text(
                "INSERT INTO gcd_issue (id, number, barcode, key_date, series_id, title, notes) "
                "VALUES (1, '19', :bc, '2017-05-00', 1, '', ''), "
                "(2, '19', :bc, '2017-05-00', 1, '', '')"
            ),
            {"bc": SUPERMAN_19_BC},
        )
    _patch_gcd_path(monkeypatch, path)
    monkeypatch.setattr(worker, "AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP", False)
    _worker_mocks(tmp_path, monkeypatch, barcode=SUPERMAN_19_BC)

    engine = _engine()
    with Session(engine) as session:
        _seed_user(session)
        intake = _intake_session(session)
        item = _queued_item(session, session_id=int(intake.id), storage_path="scan.jpg")

        status = worker.process_intake_item(session, item_id=int(item.id))
        session.refresh(item)
        assert status == ITEM_NEEDS_REVIEW
        gap = __import__("json").loads(item.barcode_read_json or "{}").get("barcode_gap") or {}
        assert gap.get("action") == "review_required"
        assert gap.get("status") == "review_required"
