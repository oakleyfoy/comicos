"""Tests for scanner barcode field test instrumentation."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401

from app.models.asset_ledger import User
from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc
from app.models.intake_queue import (
    ITEM_AUTO_MATCHED,
    ITEM_FAILED,
    ITEM_QUEUED,
    ComicIssueBarcode,
    IntakeSession,
    IntakeSessionItem,
    MATCH_SOURCE_CATALOG_UPC,
)
from app.services.intake_barcode_confidence import CoverFingerprintOutcome
from app.services.p105_comic_barcode_read_service import ComicBarcodeReadResult
from app.services.scanner_barcode_field_test_service import (
    BUCKET_INSTANT_LOCAL,
    BUCKET_NO_GCD,
    BUCKET_P106_IMPORT,
    ScannerBarcodeResolutionTrace,
    append_scanner_barcode_event,
    build_scanner_barcode_event,
    classify_scanner_barcode_bucket,
    load_recent_scanner_barcode_events,
    summarize_scanner_barcode_field_test,
)
import app.services.intake_worker_service as worker

FULL = "76194134192703921"


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


def test_classify_local_upc_and_p106_buckets() -> None:
    local = classify_scanner_barcode_bucket(
        {
            "final_status": ITEM_AUTO_MATCHED,
            "match_source": MATCH_SOURCE_CATALOG_UPC,
            "local_catalog_upc_hit": True,
        }
    )
    assert local == BUCKET_INSTANT_LOCAL

    p106 = classify_scanner_barcode_bucket({"p106_auto_imported": True, "final_status": ITEM_AUTO_MATCHED})
    assert p106 == BUCKET_P106_IMPORT

    no_gcd = classify_scanner_barcode_bucket(
        {
            "p106_called": True,
            "p106_gcd_match_count": 0,
            "p106_gcd_lookup_final_reason": "no_gcd_barcode_match",
            "final_status": "needs_review",
        }
    )
    assert no_gcd == BUCKET_NO_GCD


def test_no_gcd_event_includes_db_path_and_hit_counts(tmp_path: Path) -> None:
    log_path = tmp_path / "log.jsonl"
    diagnosis = {
        "gcd_match_count": 0,
        "gcd_lookup_final_reason": "no_gcd_barcode_match",
        "reason": "no_gcd_barcode_match",
        "status": "unresolved",
        "searched_full_barcode": "76194134194901111",
        "searched_upc12": "761941341949",
        "searched_supplement": "01111",
        "gcd_exact_hits": [],
        "gcd_prefix_hits": [{"gcd_issue_id": 1}],
        "gcd_notes_hits": [],
    }
    trace = ScannerBarcodeResolutionTrace(intake_item_id=1, p106_called=True)
    gcd_file = tmp_path / "gcd.db"
    gcd_file.write_bytes(b"x")
    trace.apply_p106_diagnosis(diagnosis, gcd_path=gcd_file)
    item = IntakeSessionItem(
        id=1,
        session_id=1,
        user_id=1,
        storage_path="x.jpg",
        status=ITEM_FAILED,
        normalized_barcode="76194134194901111",
    )
    event = build_scanner_barcode_event(
        trace=trace,
        item=item,
        final_status="needs_review",
        final_reason="no_gcd_barcode_match",
    )
    append_scanner_barcode_event(event, log_path=log_path)
    loaded = load_recent_scanner_barcode_events(log_path=log_path, limit=10)[0]
    assert loaded["p106_gcd_database_path"]
    assert loaded["p106_gcd_database_modified_at"]
    assert loaded["gcd_exact_hits"] == []
    assert len(loaded["gcd_prefix_hits"]) == 1
    summary = summarize_scanner_barcode_field_test([loaded])
    assert summary["counts"][BUCKET_NO_GCD] == 1


def test_worker_logs_local_upc_hit(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from PIL import Image

    log_path = tmp_path / "field_test.jsonl"
    monkeypatch.setenv("SCANNER_BARCODE_FIELD_TEST_LOG", str(log_path))

    engine = _engine()
    with Session(engine) as session:
        session.add(User(id=1, email="u@x.com", password_hash="x"))
        pub = CatalogPublisher(name="DC", normalized_name="dc")
        session.add(pub)
        session.flush()
        series = CatalogSeries(name="Superman", normalized_name="superman", publisher_id=pub.id)
        session.add(series)
        session.flush()
        issue = CatalogIssue(
            series_id=int(series.id),
            publisher_id=pub.id,
            issue_number="39",
            normalized_issue_number="39",
            cover_date=date(2015, 4, 1),
        )
        session.add(issue)
        session.flush()
        session.add(
            CatalogUpc(
                issue_id=int(issue.id),
                upc=FULL,
                normalized_upc=FULL,
                source="test",
                variant_id=None,
            )
        )
        intake = IntakeSession(
            user_id=1,
            session_token="t",
            status="active",
            expires_at=__import__("datetime").datetime(2099, 1, 1, tzinfo=__import__("datetime").timezone.utc),
        )
        session.add(intake)
        session.commit()
        item = IntakeSessionItem(
            session_id=int(intake.id),
            user_id=1,
            storage_path="scan.jpg",
            status=ITEM_QUEUED,
        )
        session.add(item)
        session.commit()

        img = tmp_path / "scan.jpg"
        Image.new("RGB", (800, 1200), color=(1, 1, 1)).save(img, format="JPEG")
        supp = FULL[12:17]
        monkeypatch.setattr(worker, "resolve_photo_import_storage_path", lambda *a, **k: img)
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
                info_message=None,
                fingerprint_issue_id=None,
                fingerprint_confidence=None,
                disagrees=False,
            ),
        )
        monkeypatch.setattr(worker, "lookup_comicvine_by_barcode", lambda _b: None)

        worker.process_intake_item(session, item_id=int(item.id))

    events = load_recent_scanner_barcode_events(log_path=log_path, limit=5)
    assert len(events) == 1
    assert events[0]["local_catalog_upc_hit"] is True
    assert events[0]["bucket"] == BUCKET_INSTANT_LOCAL


def test_worker_logs_p106_auto_import(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy import text

    from app.services.gcd_barcode_import_service import gcd_engine_from

    log_path = tmp_path / "field_test.jsonl"
    monkeypatch.setenv("SCANNER_BARCODE_FIELD_TEST_LOG", str(log_path))
    bc = "76194134192701911"
    gcd_path = tmp_path / "gcd.sqlite"
    eng = gcd_engine_from(str(gcd_path))
    with eng.begin() as conn:
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
                "VALUES (1680372, '19', :bc, '2017-05-00', 1, '', '')"
            ),
            {"bc": bc},
        )
    import app.services.gcd_catalog_import_dashboard_service as gcd_dash

    monkeypatch.setattr(gcd_dash, "resolve_gcd_path", lambda override=None: gcd_path)
    monkeypatch.setattr(gcd_dash, "resolve_cache_path", lambda override=None: None)

    from PIL import Image

    engine = _engine()
    with Session(engine) as session:
        session.add(User(id=1, email="u@x.com", password_hash="x"))
        intake = IntakeSession(
            user_id=1,
            session_token="t2",
            status="active",
            expires_at=__import__("datetime").datetime(2099, 1, 1, tzinfo=__import__("datetime").timezone.utc),
        )
        session.add(intake)
        session.commit()
        item = IntakeSessionItem(
            session_id=int(intake.id),
            user_id=1,
            storage_path="scan.jpg",
            status=ITEM_QUEUED,
        )
        session.add(item)
        session.commit()

        img = tmp_path / "scan.jpg"
        Image.new("RGB", (800, 1200), color=(2, 2, 2)).save(img, format="JPEG")
        supp = bc[12:17]
        monkeypatch.setattr(worker, "resolve_photo_import_storage_path", lambda *a, **k: img)
        monkeypatch.setattr(
            worker,
            "read_comic_barcode_from_image_bytes",
            lambda *a, **k: ComicBarcodeReadResult(
                main_upc=bc[:12],
                reconstructed_full=bc,
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

        worker.process_intake_item(session, item_id=int(item.id))

    events = load_recent_scanner_barcode_events(log_path=log_path, limit=5)
    assert len(events) == 1
    assert events[0]["p106_called"] is True
    assert events[0]["p106_auto_imported"] is True
    assert events[0]["bucket"] == BUCKET_P106_IMPORT
