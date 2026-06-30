"""Barcode authority miss + unsafe crop → full-cover follow-up; fingerprint only on safe full cover."""

from __future__ import annotations

import json
from datetime import datetime, timezone
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
    ITEM_NEEDS_FULL_COVER_PHOTO,
    ITEM_NEEDS_REVIEW,
    ITEM_QUEUED,
    ITEM_READY_FOR_REVIEW,
    IntakeItemCandidate,
    IntakeSession,
    IntakeSessionItem,
)
from app.services.gcd_barcode_import_service import gcd_engine_from
from app.services.intake_barcode_confidence import CoverFingerprintOutcome
from app.services.intake_full_cover_followup_service import FULL_COVER_USER_MESSAGE
from app.services.intake_fingerprint_image_region_service import REGION_UNKNOWN, assess_fingerprint_image_region
from app.services.p105_comic_barcode_read_service import ComicBarcodeReadResult
from app.services.p105_comic_barcode_regions import BarcodeRegionGeometry
from app.services.p106_1_gcd_non_barcode_recovery_service import P106_1_RECOVERY_STAGE
import app.services.intake_worker_service as worker

MARVEL_BC = "75960620629200111"


def test_unknown_image_region_is_not_fingerprint_safe() -> None:
    region = assess_fingerprint_image_region(None, image_bytes=b"not-a-jpeg")
    assert region.fingerprint_image_region == REGION_UNKNOWN
    assert region.fingerprint_region_safe is False


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


def _empty_marvel_gcd_db(tmp_path: Path) -> Path:
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
        conn.execute(text("INSERT INTO gcd_publisher (id, name) VALUES (1, 'Marvel')"))
        conn.execute(
            text("INSERT INTO gcd_series (id, name, year_began, publisher_id) VALUES (1, 'X-Men', 2024, 1)")
        )
        conn.execute(
            text(
                "INSERT INTO gcd_issue (id, number, barcode, key_date, series_id, title, notes) "
                "VALUES (88100, '1', NULL, '2024-06-00', 1, 'Issue', '')"
            )
        )
    return path


def _patch_gcd(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    import app.services.gcd_catalog_import_dashboard_service as gcd_dash

    monkeypatch.setattr(gcd_dash, "resolve_gcd_path", lambda override=None: path)
    monkeypatch.setattr(gcd_dash, "resolve_cache_path", lambda override=None: None)


def _full_cover_phone_geometry(*, width: int = 800, height: int = 1200) -> BarcodeRegionGeometry:
    fe = (0, int(height * 0.52), width, height)
    mb = (int(width * 0.16), int(height * 0.55), int(width * 0.74), height)
    ls = (0, int(height * 0.58), int(width * 0.30), int(height * 0.82))
    rc = (int(width * 0.74), int(height * 0.58), width, int(height * 0.82))
    return BarcodeRegionGeometry(
        full_expanded=fe,
        main_bars=mb,
        left_supplement=ls,
        right_cover_digit=rc,
        original_size=(width, height),
    )


def _worker_mocks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    barcode: str,
    image_size: tuple[int, int] = (800, 1200),
) -> Path:
    from PIL import Image

    img = tmp_path / "scan.jpg"
    Image.new("RGB", image_size, color=(4, 4, 4)).save(img, format="JPEG")
    supp = barcode[12:17]

    def _resolve_path(*args, **kwargs):
        rel = kwargs.get("storage_path") or (args[0] if args else "")
        if isinstance(rel, str) and "fullcover" in rel:
            fc = tmp_path / "scan_fullcover.jpg"
            if not fc.is_file():
                Image.new("RGB", image_size, color=(8, 8, 8)).save(fc, format="JPEG")
            return fc
        return img

    monkeypatch.setattr(worker, "resolve_photo_import_storage_path", _resolve_path)
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
    return img


def _new_item(session: Session, *, token: str, storage_path: str = "scan.jpg") -> IntakeSessionItem:
    session.add(User(id=1, email=f"{token}@example.com", password_hash="x"))
    intake = IntakeSession(
        user_id=1,
        session_token=token,
        status="active",
        expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    session.add(intake)
    session.commit()
    item = IntakeSessionItem(
        session_id=int(intake.id),
        user_id=1,
        storage_path=storage_path,
        status=ITEM_QUEUED,
    )
    session.add(item)
    session.commit()
    return item


def _fp_rows(session: Session, item_id: int) -> list[IntakeItemCandidate]:
    rows = session.exec(select(IntakeItemCandidate).where(IntakeItemCandidate.item_id == item_id)).all()
    return [r for r in rows if str(r.source or "") == "fingerprint"]


def _review_diag() -> dict:
    return {
        "gcd_match_count": 0,
        "status": "review_required",
        "reason": "fingerprint_review",
        "recovery_stage": P106_1_RECOVERY_STAGE,
        "review_decision": "needs_review_top_candidates",
        "needs_review_top_candidates": [
            {
                "series": "X-Men",
                "issue_number": "1",
                "publisher": "Marvel",
                "confidence": 0.72,
                "source": "fingerprint",
                "catalog_issue_id": 88100,
            }
        ],
    }


def test_upc_decoded_strip_region_requires_full_cover_no_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_gcd(monkeypatch, _empty_marvel_gcd_db(tmp_path))
    monkeypatch.setattr(worker, "AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP", False)
    _worker_mocks(tmp_path, monkeypatch, barcode=MARVEL_BC, image_size=(900, 280))
    monkeypatch.setattr(worker, "lookup_comicvine_by_barcode", lambda _b: None)
    monkeypatch.setattr(
        "app.services.p106_1_gcd_non_barcode_recovery_service.enrich_gap_diagnosis_with_gcd_non_barcode_recovery",
        lambda *a, **k: {**(k.get("prior_diagnosis") or {}), **_review_diag()},
    )

    engine = _engine()
    with Session(engine) as session:
        item = _new_item(session, token="strip")
        final = worker.process_intake_item(session, item_id=int(item.id))
        session.refresh(item)

    assert final == ITEM_NEEDS_FULL_COVER_PHOTO
    assert item.reason == FULL_COVER_USER_MESSAGE
    assert _fp_rows(session, int(item.id)) == []


def test_upc_decoded_comicvine_rejected_requires_full_cover_no_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_gcd(monkeypatch, _empty_marvel_gcd_db(tmp_path))
    monkeypatch.setattr(worker, "AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP", False)
    _worker_mocks(tmp_path, monkeypatch, barcode=MARVEL_BC, image_size=(900, 280))
    monkeypatch.setattr(
        worker,
        "lookup_comicvine_by_barcode",
        lambda _b: {
            "matched": True,
            "publisher": None,
            "series": "Chamber of Chills Magazine",
            "issue_number": "13",
            "cover_date": "1952-10-01",
        },
    )
    monkeypatch.setattr(
        "app.services.p106_1_gcd_non_barcode_recovery_service.enrich_gap_diagnosis_with_gcd_non_barcode_recovery",
        lambda *a, **k: {**(k.get("prior_diagnosis") or {}), **_review_diag()},
    )

    engine = _engine()
    with Session(engine) as session:
        item = _new_item(session, token="cv-reject")
        final = worker.process_intake_item(session, item_id=int(item.id))
        session.refresh(item)

    assert final == ITEM_NEEDS_FULL_COVER_PHOTO
    assert item.reason == FULL_COVER_USER_MESSAGE
    assert _fp_rows(session, int(item.id)) == []


def test_full_cover_followup_allows_fingerprint_when_barcode_sources_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_gcd(monkeypatch, _empty_marvel_gcd_db(tmp_path))
    monkeypatch.setattr(worker, "AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP", False)
    img = _worker_mocks(tmp_path, monkeypatch, barcode=MARVEL_BC, image_size=(1080, 1920))
    fc_rel = "data/intake/scan_fullcover.jpg"
    fc_path = tmp_path / "scan_fullcover.jpg"
    from PIL import Image

    Image.new("RGB", (800, 1200), color=(2, 2, 2)).save(fc_path, format="JPEG")

    monkeypatch.setattr(
        "app.services.p105_comic_barcode_regions.compute_barcode_region_geometry",
        lambda pil, **k: _full_cover_phone_geometry(width=800, height=1200),
    )
    monkeypatch.setattr(worker, "lookup_comicvine_by_barcode", lambda _b: None)
    monkeypatch.setattr(
        "app.services.p106_1_gcd_non_barcode_recovery_service.enrich_gap_diagnosis_with_gcd_non_barcode_recovery",
        lambda *a, **k: {**(k.get("prior_diagnosis") or {}), **_review_diag()},
    )

    engine = _engine()
    with Session(engine) as session:
        item = _new_item(session, token="fc-followup")
        item.barcode_read_json = json.dumps({"full_cover_storage_path": fc_rel})
        session.add(item)
        session.commit()
        final = worker.process_intake_item(session, item_id=int(item.id))
        session.refresh(item)

    assert final == ITEM_NEEDS_REVIEW
    assert len(_fp_rows(session, int(item.id))) >= 1


def test_full_cover_classifier_safe_allows_fingerprint_when_barcode_sources_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_gcd(monkeypatch, _empty_marvel_gcd_db(tmp_path))
    monkeypatch.setattr(worker, "AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP", False)
    _worker_mocks(tmp_path, monkeypatch, barcode=MARVEL_BC, image_size=(800, 1200))
    monkeypatch.setattr(
        "app.services.p105_comic_barcode_regions.compute_barcode_region_geometry",
        lambda pil, **k: _full_cover_phone_geometry(width=800, height=1200),
    )
    monkeypatch.setattr(worker, "lookup_comicvine_by_barcode", lambda _b: None)
    monkeypatch.setattr(
        "app.services.p106_1_gcd_non_barcode_recovery_service.enrich_gap_diagnosis_with_gcd_non_barcode_recovery",
        lambda *a, **k: {**(k.get("prior_diagnosis") or {}), **_review_diag()},
    )

    engine = _engine()
    with Session(engine) as session:
        item = _new_item(session, token="fc-safe")
        final = worker.process_intake_item(session, item_id=int(item.id))
        session.refresh(item)

    assert final == ITEM_NEEDS_REVIEW
    assert len(_fp_rows(session, int(item.id))) >= 1


def test_local_catalog_hit_bypasses_fingerprint_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_gcd(monkeypatch, _empty_marvel_gcd_db(tmp_path))
    _worker_mocks(tmp_path, monkeypatch, barcode=MARVEL_BC, image_size=(900, 280))
    enrich_called = {"v": False}
    monkeypatch.setattr(
        "app.services.p106_1_gcd_non_barcode_recovery_service.enrich_gap_diagnosis_with_gcd_non_barcode_recovery",
        lambda *a, **k: enrich_called.__setitem__("v", True) or {**(k.get("prior_diagnosis") or {})},
    )

    engine = _engine()
    with Session(engine) as session:
        session.add(User(id=1, email="local@example.com", password_hash="x"))
        pub = CatalogPublisher(name="Marvel", normalized_name="marvel")
        session.add(pub)
        session.commit()
        series = CatalogSeries(name="X-Men", normalized_name="x men", publisher_id=int(pub.id))
        session.add(series)
        session.commit()
        issue = CatalogIssue(
            series_id=int(series.id),
            publisher_id=int(pub.id),
            issue_number="1",
            normalized_issue_number="1",
        )
        session.add(issue)
        session.commit()
        session.add(
            CatalogUpc(upc=MARVEL_BC, normalized_upc=MARVEL_BC, issue_id=int(issue.id), source="test")
        )
        session.commit()
        intake = IntakeSession(
            user_id=1,
            session_token="local",
            expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
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
        final = worker.process_intake_item(session, item_id=int(item.id))

    assert enrich_called["v"] is False
    assert final in {ITEM_AUTO_MATCHED, ITEM_READY_FOR_REVIEW}
    assert _fp_rows(session, int(item.id)) == []
