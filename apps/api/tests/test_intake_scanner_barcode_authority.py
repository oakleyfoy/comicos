"""Scanner barcode authority: partial UPC, P106 over OCR/fingerprint, decode sanity."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401

from app.core.config import API_ROOT, get_settings
from app.models.asset_ledger import User
from app.models.catalog_master import CatalogUpc
from app.models.intake_queue import ITEM_AUTO_MATCHED, ITEM_NEEDS_REVIEW, ITEM_QUEUED, IntakeSession, IntakeSessionItem
from app.services.intake_barcode_confidence import CoverFingerprintOutcome
from app.services.intake_scanner_barcode_authority_service import (
    PARTIAL_BARCODE_REASON,
    comic_barcode_scan_is_partial,
    find_unique_gcd_one_digit_barcode_variant,
    p106_gap_is_exact_barcode_authority,
    sync_intake_display_from_p106_gap,
)
from app.services.p105_comic_barcode_read_service import ComicBarcodeReadResult
import app.services.intake_worker_service as worker
from app.services.p101_catalog_cache_service import DEFAULT_CACHE_PATH

BLACKS_MYTH = "85647000817200911"
GRIM_GHOST = "85999000201900311"
WILDCORE = "70985304155900511"
WILDCORE_TYPO = "76983304155900511"
DARK_HORSE_12 = "761568002140"


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


def _patch_live_gcd(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.gcd_catalog_import_dashboard_service as gcd_dash

    gcd_path = get_settings().gcd_sqlite_path
    cache_path = API_ROOT / DEFAULT_CACHE_PATH
    monkeypatch.setattr(gcd_dash, "resolve_gcd_path", lambda override=None: gcd_path)
    monkeypatch.setattr(gcd_dash, "resolve_cache_path", lambda override=None: cache_path)


def _worker_mocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, barcode: str, p105: ComicBarcodeReadResult) -> None:
    from PIL import Image

    img = tmp_path / "scan.jpg"
    Image.new("RGB", (800, 1200), color=(3, 3, 3)).save(img, format="JPEG")
    monkeypatch.setattr(worker, "resolve_photo_import_storage_path", lambda *a, **k: img)
    monkeypatch.setattr(worker, "read_comic_barcode_from_image_bytes", lambda *a, **k: p105)
    monkeypatch.setattr(
        worker,
        "evaluate_cover_fingerprint_vs_barcode",
        lambda *a, **k: CoverFingerprintOutcome(
            blocks_auto_match=True,
            info_message="Cover fingerprint strongly suggests a different issue (99%).",
            fingerprint_issue_id=999,
            fingerprint_confidence=0.99,
            disagrees=True,
        ),
    )
    monkeypatch.setattr(worker, "lookup_comicvine_by_barcode", lambda _b: {"matched": True, "series": "Fighting Fronts", "issue_number": "3"})


def _p105_full(barcode: str) -> ComicBarcodeReadResult:
    supp = barcode[12:17]
    return ComicBarcodeReadResult(
        main_upc=barcode[:12],
        reconstructed_full=barcode,
        final_supplement=supp,
        decoded_supplement=supp,
        supplement_decode_confidence=0.99,
        confidence_main=0.95,
        confidence_reconstructed=0.95,
    )


def _p105_twelve_only(upc12: str) -> ComicBarcodeReadResult:
    return ComicBarcodeReadResult(main_upc=upc12, confidence_main=0.92)


def test_partial_twelve_digit_only_is_not_comicvine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert comic_barcode_scan_is_partial(normalized=DARK_HORSE_12, p105=_p105_twelve_only(DARK_HORSE_12))
    _patch_live_gcd(monkeypatch)
    monkeypatch.setattr(worker, "AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP", True)
    _worker_mocks(tmp_path, monkeypatch, barcode=DARK_HORSE_12, p105=_p105_twelve_only(DARK_HORSE_12))
    engine = _engine()
    with Session(engine) as session:
        session.add(User(id=1, email="a@b.com", password_hash="x"))
        session.commit()
        intake = IntakeSession(
            user_id=1,
            session_token="t",
            status="active",
            expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        session.add(intake)
        session.commit()
        session.refresh(intake)
        item = IntakeSessionItem(session_id=int(intake.id), user_id=1, storage_path="x.jpg", status=ITEM_QUEUED)
        session.add(item)
        session.commit()
        session.refresh(item)
        status = worker.process_intake_item(session, item_id=int(item.id))
        session.refresh(item)
        assert status == ITEM_NEEDS_REVIEW
        assert PARTIAL_BARCODE_REASON in (item.reason or "")
        import json

        payload = json.loads(item.barcode_read_json or "{}")
        assert payload.get("partial_barcode") is True


@pytest.mark.skipif(not get_settings().gcd_sqlite_path.is_file(), reason="live GCD required")
def test_p106_exact_beats_fingerprint_and_comicvine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_live_gcd(monkeypatch)
    monkeypatch.setattr(worker, "AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP", True)
    _worker_mocks(tmp_path, monkeypatch, barcode=GRIM_GHOST, p105=_p105_full(GRIM_GHOST))
    engine = _engine()
    with Session(engine) as session:
        session.add(User(id=1, email="a@b.com", password_hash="x"))
        session.commit()
        intake = IntakeSession(user_id=1, session_token="t2", status="active", expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc))
        session.add(intake)
        session.commit()
        session.refresh(intake)
        item = IntakeSessionItem(session_id=int(intake.id), user_id=1, storage_path="x.jpg", status=ITEM_QUEUED)
        session.add(item)
        session.commit()
        session.refresh(item)
        status = worker.process_intake_item(session, item_id=int(item.id))
        session.refresh(item)
        assert status == ITEM_AUTO_MATCHED
        assert "grim ghost" in (item.matched_series or "").lower()
        assert item.matched_issue_number == "3"
        assert "Fighting Fronts" not in (item.matched_series or "")


@pytest.mark.skipif(not get_settings().gcd_sqlite_path.is_file(), reason="live GCD required")
def test_blacks_myth_auto_imports_despite_supplement_encoding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_live_gcd(monkeypatch)
    monkeypatch.setattr(worker, "AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP", True)
    p105 = _p105_full(BLACKS_MYTH)
    monkeypatch.setattr(
        worker,
        "evaluate_cover_fingerprint_vs_barcode",
        lambda *a, **k: CoverFingerprintOutcome(False, None, None, None, False),
    )
    monkeypatch.setattr(worker, "lookup_comicvine_by_barcode", lambda _b: None)
    from PIL import Image

    img = tmp_path / "scan.jpg"
    Image.new("RGB", (800, 1200), color=(1, 1, 1)).save(img, format="JPEG")
    monkeypatch.setattr(worker, "resolve_photo_import_storage_path", lambda *a, **k: img)
    monkeypatch.setattr(worker, "read_comic_barcode_from_image_bytes", lambda *a, **k: p105)
    engine = _engine()
    with Session(engine) as session:
        session.add(User(id=1, email="a@b.com", password_hash="x"))
        session.commit()
        intake = IntakeSession(user_id=1, session_token="t3", status="active", expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc))
        session.add(intake)
        session.commit()
        session.refresh(intake)
        item = IntakeSessionItem(session_id=int(intake.id), user_id=1, storage_path="x.jpg", status=ITEM_QUEUED)
        session.add(item)
        session.commit()
        session.refresh(item)
        status = worker.process_intake_item(session, item_id=int(item.id))
        session.refresh(item)
        assert status == ITEM_AUTO_MATCHED
        assert "black" in (item.matched_series or "").lower()
        upc = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == BLACKS_MYTH)).first()
        assert upc is not None


@pytest.mark.skipif(not get_settings().gcd_sqlite_path.is_file(), reason="live GCD required")
def test_decode_review_flags_likely_misread_upc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gcd_path = get_settings().gcd_sqlite_path
    typo = "80985304155900511"
    assert find_unique_gcd_one_digit_barcode_variant(gcd_path, typo) == WILDCORE
    p105 = _p105_full(typo)
    reason = __import__(
        "app.services.intake_scanner_barcode_authority_service",
        fromlist=["barcode_decode_review_reason"],
    ).barcode_decode_review_reason(p105=p105, normalized=typo, gcd_path=gcd_path)
    assert reason is not None
    assert "809853" not in (reason or "") or WILDCORE in (reason or "")
    assert "misread" in (reason or "").lower() or "rescan" in (reason or "").lower()


def test_p106_gap_sync_overrides_display() -> None:
    item = type(
        "Item",
        (),
        {
            "matched_series": "Fighting Fronts",
            "matched_issue_number": "3",
            "matched_publisher": "Wrong",
            "matched_year": None,
        },
    )()
    gap = {
        "gcd_match_count": 1,
        "exact_barcode_path": True,
        "gcd_matches": [
            {"series": "Grim Ghost", "issue_number": "3", "publisher": "Ardden Entertainment", "year_began": 2010}
        ],
        "gcd_exact_hits": [{"series": "Grim Ghost", "issue_number": "3"}],
    }
    assert p106_gap_is_exact_barcode_authority(gap)
    sync_intake_display_from_p106_gap(item, gap)
    assert item.matched_series == "Grim Ghost"
    assert item.matched_issue_number == "3"
