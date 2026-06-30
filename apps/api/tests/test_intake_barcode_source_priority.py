"""Regression: barcode sources always win; fingerprint must never outlive a barcode match.

Pipeline order under test:
    Local catalog -> Learned barcode -> GCD barcode -> ComicVine barcode
        -> (only if all miss) OCR / fingerprint recovery (P106.1).

A successful barcode resolution must clear any fingerprint review artifacts and
skip / discard P106 fingerprint review.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401
from app.models.asset_ledger import User
from app.models.intake_queue import (
    ITEM_AUTO_MATCHED,
    ITEM_NEEDS_REVIEW,
    ITEM_QUEUED,
    ITEM_READY_FOR_REVIEW,
    IntakeItemCandidate,
    IntakeSession,
    IntakeSessionItem,
)
from app.services.gcd_barcode_import_service import gcd_engine_from
from app.services.intake_barcode_confidence import CoverFingerprintOutcome
from app.services.p105_comic_barcode_read_service import ComicBarcodeReadResult
from app.services.p106_1_gcd_non_barcode_recovery_service import P106_1_RECOVERY_STAGE
import app.services.intake_worker_service as worker

MARVEL_BC = "75960620629200111"


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


def _empty_marvel_gcd_db(tmp_path: Path) -> Path:
    """GCD with no barcode on the issue row -> GCD barcode lookup misses."""
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


def _worker_mocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, barcode: str) -> None:
    from PIL import Image

    img = tmp_path / "scan.jpg"
    Image.new("RGB", (800, 1200), color=(4, 4, 4)).save(img, format="JPEG")
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


def _new_item(session: Session, *, token: str) -> IntakeSessionItem:
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
        storage_path="scan.jpg",
        status=ITEM_QUEUED,
    )
    session.add(item)
    session.commit()
    return item


def _fingerprint_rows(session: Session, item_id: int) -> list[IntakeItemCandidate]:
    rows = session.exec(
        select(IntakeItemCandidate).where(IntakeItemCandidate.item_id == item_id)
    ).all()
    return [r for r in rows if str(r.source or "") == "fingerprint"]


def _barcode_gap(item: IntakeSessionItem) -> dict:
    import json

    payload = json.loads(item.barcode_read_json or "{}")
    gap = payload.get("barcode_gap")
    return gap if isinstance(gap, dict) else {}


# --- Test 1: ComicVine resolves the barcode -> fingerprint cleared / skipped ---
def test_comicvine_barcode_success_clears_and_skips_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_gcd(monkeypatch, _empty_marvel_gcd_db(tmp_path))
    monkeypatch.setattr(worker, "AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP", False)
    _worker_mocks(tmp_path, monkeypatch, barcode=MARVEL_BC)

    enrich_called = {"v": False}

    def _track_enrich(*args, **kwargs):
        enrich_called["v"] = True
        return {**(kwargs.get("prior_diagnosis") or {})}

    monkeypatch.setattr(
        "app.services.p106_1_gcd_non_barcode_recovery_service.enrich_gap_diagnosis_with_gcd_non_barcode_recovery",
        _track_enrich,
    )

    # Local catalog miss + learned miss (no rows). GCD miss (empty barcode). ComicVine success.
    cv_candidate = {
        "source": "comicvine",
        "catalog_issue_id": None,
        "variant_id": None,
        "publisher": "Marvel",
        "series": "X-Men",
        "issue_number": "1",
        "cover_url": None,
        "year": "2024",
        "confidence": 0.8,
    }
    monkeypatch.setattr(worker, "_resolve_comicvine_candidate", lambda session, *, barcode: dict(cv_candidate))

    engine = _engine()
    with Session(engine) as session:
        item = _new_item(session, token="cv-success")
        item_id = int(item.id)
        # Simulate fingerprint having already executed earlier in a prior pass.
        session.add(
            IntakeItemCandidate(
                item_id=item_id,
                source="fingerprint",
                rank=0,
                score=70.0,
                series="Four Color",
                issue_number="1",
                publisher="Dell",
            )
        )
        session.commit()

        final = worker.process_intake_item(session, item_id=item_id)
        session.refresh(item)

    assert enrich_called["v"] is False, "P106.1 fingerprint recovery must not run once ComicVine resolves the barcode"
    assert _fingerprint_rows(session, item_id) == []
    assert _barcode_gap(item).get("needs_review_top_candidates") in (None, [])
    assert item.match_source == "comicvine"
    assert final in {ITEM_READY_FOR_REVIEW, ITEM_AUTO_MATCHED}


# --- Test 2: all barcode sources miss -> fingerprint review executes and persists ---
def test_all_barcode_sources_miss_runs_fingerprint_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_gcd(monkeypatch, _empty_marvel_gcd_db(tmp_path))
    monkeypatch.setattr(worker, "AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP", False)
    _worker_mocks(tmp_path, monkeypatch, barcode=MARVEL_BC)

    comicvine_called = {"v": False}
    monkeypatch.setattr(
        worker,
        "lookup_comicvine_by_barcode",
        lambda _b: comicvine_called.__setitem__("v", True) or None,
    )

    review_diag = {
        "gcd_match_count": 0,
        "status": "review_required",
        "reason": "ambiguous_gcd_non_barcode_candidates",
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
    monkeypatch.setattr(
        "app.services.p106_1_gcd_non_barcode_recovery_service.enrich_gap_diagnosis_with_gcd_non_barcode_recovery",
        lambda *a, **k: {**(k.get("prior_diagnosis") or {}), **review_diag},
    )

    engine = _engine()
    with Session(engine) as session:
        item = _new_item(session, token="all-miss")
        item_id = int(item.id)
        final = worker.process_intake_item(session, item_id=item_id)
        session.refresh(item)

    assert comicvine_called["v"] is True, "ComicVine barcode lookup must be attempted before fingerprint review"
    assert final == ITEM_NEEDS_REVIEW
    assert _barcode_gap(item).get("needs_review_top_candidates"), "fingerprint review candidates should remain"
    assert len(_fingerprint_rows(session, item_id)) >= 1


# --- Test 3: local catalog hit -> ComicVine and fingerprint never called ---
def test_local_catalog_hit_skips_comicvine_and_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc

    _patch_gcd(monkeypatch, _empty_marvel_gcd_db(tmp_path))
    _worker_mocks(tmp_path, monkeypatch, barcode=MARVEL_BC)

    comicvine_called = {"v": False}
    monkeypatch.setattr(
        worker,
        "lookup_comicvine_by_barcode",
        lambda _b: comicvine_called.__setitem__("v", True) or None,
    )
    enrich_called = {"v": False}
    monkeypatch.setattr(
        "app.services.p106_1_gcd_non_barcode_recovery_service.enrich_gap_diagnosis_with_gcd_non_barcode_recovery",
        lambda *a, **k: enrich_called.__setitem__("v", True) or {**(k.get("prior_diagnosis") or {})},
    )

    engine = _engine()
    with Session(engine) as session:
        session.add(User(id=1, email="local-hit@example.com", password_hash="x"))
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
            session_token="local-hit",
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
        session.refresh(item)

    assert comicvine_called["v"] is False, "ComicVine must not be called when local catalog resolves the barcode"
    assert enrich_called["v"] is False, "Fingerprint recovery must not run when local catalog resolves the barcode"
    assert final in {ITEM_AUTO_MATCHED, ITEM_READY_FOR_REVIEW}
    assert _fingerprint_rows(session, int(item.id)) == []
