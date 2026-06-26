"""Async intake queue: non-blocking enqueue, background identification, barcode learning."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from starlette.datastructures import Headers, UploadFile

import app.models  # noqa: F401

from app.models.asset_ledger import User
from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.models.intake_queue import (
    ComicIssueBarcode,
    ITEM_AUTO_MATCHED,
    ITEM_FAILED,
    ITEM_NEEDS_REVIEW,
    ITEM_QUEUED,
    ITEM_READY_FOR_REVIEW,
    IntakeSession,
    IntakeSessionItem,
)
import app.services.intake_worker_service as worker
import app.services.intake_queue_service as svc

FULL_BARCODE = "76194134192703921"  # DC prefix + 03921 -> Superman #39


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


def _intake_session(session: Session) -> IntakeSession:
    row = IntakeSession(
        user_id=1,
        session_token="tok-intake",
        status="active",
        expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _fake_jpeg(tmp_path) -> str:
    # Full-resolution scan: large enough to clear the recognition min-size guard.
    p = tmp_path / "scan.jpg"
    Image.new("RGB", (800, 1200), color=(2, 2, 2)).save(p, format="JPEG")
    return str(p)


def _jpeg_bytes(width: int, height: int) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (width, height), color=(8, 8, 8)).save(buf, format="JPEG")
    return buf.getvalue()


def test_worker_auto_matches_via_learned_barcode(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_user(session)
        issue_id = _seed_dc_superman_39(session)
        session.add(ComicIssueBarcode(normalized_barcode=FULL_BARCODE, catalog_issue_id=issue_id, source="manual"))
        session.commit()
        intake = _intake_session(session)
        item = _queued_item(session, session_id=int(intake.id), storage_path="ignored.jpg")

        jpeg = _fake_jpeg(tmp_path)
        monkeypatch.setattr(worker, "extract_barcode_from_image", lambda *a, **k: {"barcode": FULL_BARCODE})
        monkeypatch.setattr(worker, "resolve_photo_import_storage_path", lambda *a, **k: __import__("pathlib").Path(jpeg))

        result = worker.process_intake_item(session, item_id=int(item.id))

        assert result == ITEM_AUTO_MATCHED
        session.refresh(item)
        assert item.selected_catalog_issue_id == issue_id
        assert item.match_source == "learned_barcode"
        learned = session.exec(
            select(ComicIssueBarcode).where(ComicIssueBarcode.normalized_barcode == FULL_BARCODE)
        ).one()
        assert learned.times_seen == 2  # bumped on a confirmed re-sighting


def test_worker_needs_review_when_no_match(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_user(session)
        intake = _intake_session(session)
        item = _queued_item(session, session_id=int(intake.id), storage_path="ignored.jpg")

        jpeg = _fake_jpeg(tmp_path)
        monkeypatch.setattr(worker, "extract_barcode_from_image", lambda *a, **k: {"barcode": FULL_BARCODE})
        monkeypatch.setattr(worker, "resolve_photo_import_storage_path", lambda *a, **k: __import__("pathlib").Path(jpeg))
        monkeypatch.setattr(worker, "lookup_comicvine_by_barcode", lambda _b: {"matched": False})

        result = worker.process_intake_item(session, item_id=int(item.id))

        assert result == ITEM_NEEDS_REVIEW
        session.refresh(item)
        assert item.selected_catalog_issue_id is None
        assert item.normalized_barcode == FULL_BARCODE


def test_worker_rejects_wrong_publisher(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_user(session)
        intake = _intake_session(session)
        item = _queued_item(session, session_id=int(intake.id), storage_path="ignored.jpg")

        jpeg = _fake_jpeg(tmp_path)
        monkeypatch.setattr(worker, "extract_barcode_from_image", lambda *a, **k: {"barcode": FULL_BARCODE})
        monkeypatch.setattr(worker, "resolve_photo_import_storage_path", lambda *a, **k: __import__("pathlib").Path(jpeg))
        monkeypatch.setattr(
            worker,
            "lookup_comicvine_by_barcode",
            lambda _b: {"matched": True, "publisher": "Harvey", "issue_number": "13", "cover_date": "1952-01-01"},
        )

        result = worker.process_intake_item(session, item_id=int(item.id))

        assert result == ITEM_NEEDS_REVIEW  # safe-match validation refuses the DC->Harvey match
        session.refresh(item)
        assert item.selected_catalog_issue_id is None


def test_accept_learns_barcode_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_user(session)
        issue_id = _seed_dc_superman_39(session)
        intake = _intake_session(session)
        item = _queued_item(session, session_id=int(intake.id), storage_path="x.jpg")
        item.status = ITEM_READY_FOR_REVIEW
        item.normalized_barcode = FULL_BARCODE
        item.selected_catalog_issue_id = issue_id
        item.match_source = "comicvine"
        session.add(item)
        session.commit()

        svc.accept_intake_item(session, item_id=int(item.id), owner_user_id=1)

        learned = session.exec(
            select(ComicIssueBarcode).where(ComicIssueBarcode.normalized_barcode == FULL_BARCODE)
        ).one()
        assert learned.catalog_issue_id == issue_id
        session.refresh(item)
        assert item.status == ITEM_AUTO_MATCHED


def test_choose_issue_learns_and_accepts() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_user(session)
        issue_id = _seed_dc_superman_39(session)
        intake = _intake_session(session)
        item = _queued_item(session, session_id=int(intake.id), storage_path="x.jpg")
        item.status = ITEM_NEEDS_REVIEW
        item.normalized_barcode = FULL_BARCODE
        session.add(item)
        session.commit()

        svc.choose_intake_item_issue(
            session, item_id=int(item.id), owner_user_id=1, catalog_issue_id=issue_id
        )

        session.refresh(item)
        assert item.selected_catalog_issue_id == issue_id
        assert item.status == ITEM_AUTO_MATCHED
        learned = session.exec(
            select(ComicIssueBarcode).where(ComicIssueBarcode.normalized_barcode == FULL_BARCODE)
        ).one()
        assert learned.catalog_issue_id == issue_id


def test_search_catalog_issues_finds_series() -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_user(session)
        issue_id = _seed_dc_superman_39(session)

        results = svc.search_catalog_issues(session, query="superman", issue_number="39")

        assert any(r["catalog_issue_id"] == issue_id for r in results)
        assert all(r["series"] == "Superman" for r in results)


def test_import_and_accept_links_local_issue(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    import app.services.catalog_ingestion_service as cat_ing
    import app.services.comicvine_catalog_importer as cv_imp

    engine = _engine()
    with Session(engine) as session:
        _seed_user(session)
        issue_id = _seed_dc_superman_39(session)
        issue = session.get(CatalogIssue, issue_id)
        series_id = int(issue.series_id)
        intake = _intake_session(session)
        item = _queued_item(session, session_id=int(intake.id), storage_path="x.jpg")
        item.status = ITEM_READY_FOR_REVIEW
        item.normalized_barcode = FULL_BARCODE
        item.matched_series = "Superman"
        item.matched_issue_number = "39"
        item.matched_publisher = "DC Comics"
        item.matched_year = "2015"
        session.add(item)
        session.commit()

        class FakeImporter:
            def initialize_or_explain(self):
                return None

            def search_issues_by_barcode(self, _b):
                return []

            def volume_id_from_issue_api_row(self, _row):
                return None

            def search_volumes(self, _q, *, limit=30):
                return [{"id": 4242, "name": "Superman", "start_year": 2011}]

            def import_single_volume(self, _session, *, comicvine_volume_id, import_issues):
                return SimpleNamespace(imported_series_ids=[series_id], created_issues=0)

        monkeypatch.setattr(cv_imp, "ComicVineCatalogImporter", FakeImporter)
        monkeypatch.setattr(
            cat_ing, "catalog_series_id_for_comicvine_volume", lambda _session, **k: series_id
        )

        svc.import_and_accept_intake_item(session, item_id=int(item.id), owner_user_id=1)

        session.refresh(item)
        assert item.selected_catalog_issue_id == issue_id
        assert item.status == ITEM_AUTO_MATCHED
        assert item.match_source == "comicvine"
        learned = session.exec(
            select(ComicIssueBarcode).where(ComicIssueBarcode.normalized_barcode == FULL_BARCODE)
        ).one()
        assert learned.catalog_issue_id == issue_id


def test_enqueue_is_nonblocking_and_increments_count(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_user(session)
        intake = _intake_session(session)

        kicked: list[int] = []
        monkeypatch.setattr(svc, "run_intake_item_async", lambda item_id: kicked.append(item_id))
        monkeypatch.setattr(svc, "_intake_storage_dir", lambda **k: tmp_path)
        monkeypatch.setattr(svc, "relative_path_under_repo_root", lambda p: f"data/intake/test/{p.name}")

        upload = UploadFile(
            filename="scan.jpg",
            file=BytesIO(_jpeg_bytes(800, 1200)),
            headers=Headers({"content-type": "image/jpeg"}),
        )

        item = asyncio.run(svc.enqueue_intake_item(session, token="tok-intake", upload=upload))

        assert item.status == ITEM_QUEUED
        assert kicked == [int(item.id)]
        session.refresh(intake)
        assert intake.scanned_count == 1


def test_enqueue_flags_tiny_thumbnail_and_skips_worker(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_user(session)
        intake = _intake_session(session)

        kicked: list[int] = []
        monkeypatch.setattr(svc, "run_intake_item_async", lambda item_id: kicked.append(item_id))
        monkeypatch.setattr(svc, "_intake_storage_dir", lambda **k: tmp_path)
        monkeypatch.setattr(svc, "relative_path_under_repo_root", lambda p: f"data/intake/test/{p.name}")

        upload = UploadFile(
            filename="thumb.jpg",
            file=BytesIO(_jpeg_bytes(40, 20)),
            headers=Headers({"content-type": "image/jpeg"}),
        )

        item = asyncio.run(svc.enqueue_intake_item(session, token="tok-intake", upload=upload))

        assert item.status == ITEM_FAILED
        assert kicked == []  # never enters the recognition pipeline
        assert item.error and "too small" in item.error.lower()
        assert "40x20" in item.error


def test_worker_rejects_thumbnail_before_barcode_ocr(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _engine()
    with Session(engine) as session:
        _seed_user(session)
        intake = _intake_session(session)
        item = _queued_item(session, session_id=int(intake.id), storage_path="ignored.jpg")

        tiny = tmp_path / "thumb.jpg"
        Image.new("RGB", (40, 20), color=(2, 2, 2)).save(tiny, format="JPEG")

        called: list[int] = []
        monkeypatch.setattr(worker, "extract_barcode_from_image", lambda *a, **k: called.append(1) or {"barcode": FULL_BARCODE})
        monkeypatch.setattr(worker, "resolve_photo_import_storage_path", lambda *a, **k: tiny)

        result = worker.process_intake_item(session, item_id=int(item.id))

        assert result == ITEM_FAILED
        assert called == []  # OCR/barcode extraction never runs on a thumbnail
        session.refresh(item)
        assert item.reason and "too small" in item.reason.lower()
        assert "40x20" in item.reason
