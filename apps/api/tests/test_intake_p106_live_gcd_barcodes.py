"""Regression: known live GCD barcodes must resolve via P106 in the intake scanner path."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401

from app.core.config import API_ROOT, get_settings
from app.services.p101_catalog_cache_service import DEFAULT_CACHE_PATH
from app.models.asset_ledger import User
from app.models.catalog_master import CatalogUpc
from app.models.intake_queue import (
    ITEM_AUTO_MATCHED,
    ITEM_NEEDS_REVIEW,
    ITEM_QUEUED,
    IntakeSession,
    IntakeSessionItem,
)
from app.services.gcd_barcode_import_service import gcd_engine_from
from app.services.intake_barcode_confidence import CoverFingerprintOutcome
from app.services.p105_comic_barcode_read_service import ComicBarcodeReadResult
from app.services.p106_barcode_gap_resolver_service import diagnose_barcode_gap
import app.services.intake_worker_service as worker

LIVE_GCD_BARCODES = (
    ("76194134192701911", "Superman", "19"),
    ("85647000817200911", "Black's Myth", "4"),
    ("85999000201900311", "Grim Ghost", "3"),
    ("70985304155900511", "Wildcore", "5"),
)


def _live_gcd_path() -> Path:
    return get_settings().gcd_sqlite_path


pytestmark = pytest.mark.skipif(
    not _live_gcd_path().is_file(),
    reason=f"live GCD sqlite missing: {_live_gcd_path()}",
)


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_user(session: Session) -> None:
    session.add(User(id=1, email="live-gcd@example.com", password_hash="x"))
    session.commit()


def _intake_session(session: Session) -> IntakeSession:
    row = IntakeSession(
        user_id=1,
        session_token="tok-live-gcd",
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


def _worker_mocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, barcode: str) -> None:
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


@pytest.mark.parametrize("barcode,expected_series,expected_issue", LIVE_GCD_BARCODES)
def test_live_gcd_diagnose_unique_match(barcode: str, expected_series: str, expected_issue: str) -> None:
    gcd_path = _live_gcd_path()
    engine = _engine()
    with Session(engine) as session:
        diag = diagnose_barcode_gap(session, barcode=barcode, gcd_path=gcd_path, cache_path=None)
    assert int(diag.get("gcd_match_count") or 0) == 1, diag
    assert int(diag.get("gcd_sql_exact_barcode_column_count") or 0) >= 1, diag
    matches = diag.get("gcd_matches") or []
    assert matches
    assert expected_series.lower() in str(matches[0].get("series") or "").lower()
    assert str(matches[0].get("issue_number")) == expected_issue


def _patch_live_gcd_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.gcd_catalog_import_dashboard_service as gcd_dash

    gcd_path = _live_gcd_path()
    cache_path = API_ROOT / DEFAULT_CACHE_PATH
    monkeypatch.setattr(gcd_dash, "resolve_gcd_path", lambda override=None: gcd_path)
    monkeypatch.setattr(gcd_dash, "resolve_cache_path", lambda override=None: cache_path)


@pytest.mark.parametrize("barcode,expected_series,expected_issue", LIVE_GCD_BARCODES)
def test_live_gcd_scanner_auto_resolves_without_comicvine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    barcode: str,
    expected_series: str,
    expected_issue: str,
) -> None:
    _patch_live_gcd_paths(monkeypatch)
    monkeypatch.setattr(worker, "AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP", True)
    _worker_mocks(tmp_path, monkeypatch, barcode=barcode)

    engine = _engine()
    with Session(engine) as session:
        _seed_user(session)
        intake = _intake_session(session)
        item = _queued_item(session, session_id=int(intake.id), storage_path="scan.jpg")

        status = worker.process_intake_item(session, item_id=int(item.id))
        session.refresh(item)

        assert status == ITEM_AUTO_MATCHED, item.reason
        assert item.selected_catalog_issue_id is not None
        assert expected_series.lower() in str(item.matched_series or "").lower()
        assert str(item.matched_issue_number) == expected_issue
        upc = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == barcode)).first()
        assert upc is not None
        gap = __import__("json").loads(item.barcode_read_json or "{}").get("barcode_gap") or {}
        assert gap.get("action") != "comicvine_fallback"
        assert int(gap.get("gcd_match_count") or 0) == 1


def test_display_failure_does_not_force_comicvine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: UI display errors must not discard a successful P106 diagnosis."""
    barcode = LIVE_GCD_BARCODES[0][0]
    _patch_live_gcd_paths(monkeypatch)
    monkeypatch.setattr(worker, "AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP", False)

    def _boom(*_a, **_k):
        raise RuntimeError("display failed")

    monkeypatch.setattr(worker, "_apply_p106_diagnosis_to_intake_item", _boom)
    _worker_mocks(tmp_path, monkeypatch, barcode=barcode)
    monkeypatch.setattr(worker, "lookup_comicvine_by_barcode", lambda _b: {"matched": True, "series": "Wrong"})

    engine = _engine()
    with Session(engine) as session:
        _seed_user(session)
        intake = _intake_session(session)
        item = _queued_item(session, session_id=int(intake.id), storage_path="scan.jpg")
        status = worker.process_intake_item(session, item_id=int(item.id))
        session.refresh(item)
        assert status == ITEM_NEEDS_REVIEW
        assert "GCD match found" in (item.reason or "")
        assert "ComicVine" not in (item.reason or "")
