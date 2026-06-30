"""P106 → P106.1 → ComicVine intake routing and field-test instrumentation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401

from app.models.asset_ledger import User
from app.models.intake_queue import ITEM_NEEDS_REVIEW, ITEM_QUEUED, IntakeSession, IntakeSessionItem
from app.services.gcd_barcode_import_service import gcd_engine_from
from app.services.intake_barcode_confidence import CoverFingerprintOutcome
from app.services.p105_comic_barcode_read_service import ComicBarcodeReadResult
from app.services.p106_1_gcd_non_barcode_recovery_service import (
    P106_1_RECOVERY_STAGE,
    enrich_gap_diagnosis_with_gcd_non_barcode_recovery,
)
from app.services.p106_barcode_gap_resolver_service import P106_STATUS_REVIEW_REQUIRED
from app.services.scanner_barcode_field_test_service import (
    ScannerBarcodeResolutionTrace,
    build_scanner_barcode_event,
    load_recent_scanner_barcode_events,
)
import app.services.intake_worker_service as worker

MARVEL_BC = "75960620629200111"
SUPERMAN_BC = "76194134192701911"


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


def test_comicvine_runs_before_p106_1_fingerprint(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ComicVine is a barcode source and must be consulted before P106.1 fingerprint recovery."""
    _patch_gcd(monkeypatch, _empty_marvel_gcd_db(tmp_path))
    monkeypatch.setattr(worker, "AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP", False)
    _worker_mocks(tmp_path, monkeypatch, barcode=MARVEL_BC)

    call_order: list[str] = []

    def _track_enrich(*args, **kwargs):
        call_order.append("p106_1")
        return enrich_gap_diagnosis_with_gcd_non_barcode_recovery(*args, **kwargs)

    monkeypatch.setattr(
        "app.services.p106_1_gcd_non_barcode_recovery_service.enrich_gap_diagnosis_with_gcd_non_barcode_recovery",
        _track_enrich,
    )

    def _track_cv(_barcode: str):
        call_order.append("comicvine")
        return None

    monkeypatch.setattr(worker, "lookup_comicvine_by_barcode", _track_cv)

    engine = _engine()
    with Session(engine) as session:
        session.add(User(id=1, email="u@example.com", password_hash="x"))
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
            status=ITEM_QUEUED,
        )
        session.add(item)
        session.commit()

        worker.process_intake_item(session, item_id=int(item.id))
        session.refresh(item)

    assert "p106_1" in call_order
    assert "comicvine" in call_order
    # ComicVine (barcode source) must be tried before fingerprint recovery.
    assert call_order.index("comicvine") < call_order.index("p106_1")
    gap = __import__("json").loads(item.barcode_read_json or "{}").get("barcode_gap") or {}
    assert gap.get("recovery_stage") == P106_1_RECOVERY_STAGE


def test_comicvine_consulted_before_p106_1_auto_import(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When ComicVine misses, P106.1 GCD metadata recovery may still auto-import.

    ComicVine is a barcode source and is consulted before P106.1; a ComicVine miss
    (None) lets P106.1 GCD non-barcode recovery resolve the issue.
    """
    _patch_gcd(monkeypatch, _empty_marvel_gcd_db(tmp_path))
    monkeypatch.setattr(worker, "AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP", True)
    _worker_mocks(tmp_path, monkeypatch, barcode=MARVEL_BC)

    auto_diag = {
        "gcd_match_count": 1,
        "gcd_issue_id": 88100,
        "ready_to_auto_import": True,
        "status": "auto_import",
        "recovery_stage": P106_1_RECOVERY_STAGE,
        "reason": "unique_gcd_non_barcode_recovery",
    }

    monkeypatch.setattr(
        "app.services.p106_1_gcd_non_barcode_recovery_service.enrich_gap_diagnosis_with_gcd_non_barcode_recovery",
        lambda *a, **k: {**(k.get("prior_diagnosis") or {}), **auto_diag},
    )
    monkeypatch.setattr(
        "app.services.p106_barcode_gap_resolver_service.resolve_barcode_gap",
        lambda *a, **k: {
            "written": True,
            "result": {"action": "auto_import", "catalog_issue_id": 42, "variant_id": None},
        },
    )
    comicvine_called = {"v": False}
    monkeypatch.setattr(
        worker,
        "lookup_comicvine_by_barcode",
        lambda _b: comicvine_called.__setitem__("v", True) or None,
    )

    engine = _engine()
    with Session(engine) as session:
        session.add(User(id=1, email="u2@example.com", password_hash="x"))
        intake = IntakeSession(
            user_id=1,
            session_token="tok2",
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
        worker.process_intake_item(session, item_id=int(item.id))

    # ComicVine (barcode) is now consulted before P106.1 fingerprint recovery.
    assert comicvine_called["v"] is True


def test_field_test_event_includes_p106_1_fields(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    log_path = tmp_path / "field_test.jsonl"
    monkeypatch.setenv("SCANNER_BARCODE_FIELD_TEST_LOG", str(log_path))
    _patch_gcd(monkeypatch, _empty_marvel_gcd_db(tmp_path))
    monkeypatch.setattr(worker, "AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP", False)
    _worker_mocks(tmp_path, monkeypatch, barcode=MARVEL_BC)
    monkeypatch.setattr(worker, "lookup_comicvine_by_barcode", lambda _b: None)

    engine = _engine()
    with Session(engine) as session:
        session.add(User(id=1, email="u3@example.com", password_hash="x"))
        intake = IntakeSession(
            user_id=1,
            session_token="tok3",
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
        worker.process_intake_item(session, item_id=int(item.id))

    events = load_recent_scanner_barcode_events(log_path=log_path, limit=3)
    assert len(events) == 1
    ev = events[0]
    assert ev["p106_1_called"] is True
    assert ev.get("p106_1_status") == P106_STATUS_REVIEW_REQUIRED
    assert ev.get("p106_1_recovery_block_reason")


def test_trace_apply_p106_1_updates_gap_diagnosis() -> None:
    trace = ScannerBarcodeResolutionTrace(intake_item_id=1)
    trace.apply_p106_diagnosis({"status": "unresolved", "gcd_match_count": 0}, gcd_path=None)
    merged = {
        "status": P106_STATUS_REVIEW_REQUIRED,
        "gcd_match_count": 0,
        "recovery_stage": P106_1_RECOVERY_STAGE,
        "recovery_block_reason": "insufficient_series_or_title_hint",
        "p106_1_instrumentation": {
            "decision_reason": "insufficient_series_or_title_hint",
            "fingerprint_candidate_count": 1,
            "fingerprint_candidate_used": True,
        },
        "fingerprint_candidate_count": 1,
    }
    trace.apply_p106_1_from_diagnosis(merged, gcd_path=None)
    event = build_scanner_barcode_event(
        trace=trace,
        item=MagicMock(
            normalized_barcode=MARVEL_BC,
            match_source=None,
            selected_catalog_issue_id=None,
            matched_series=None,
            matched_issue_number=None,
            reason=None,
            error=None,
        ),
        final_status=ITEM_NEEDS_REVIEW,
        final_reason="review",
    )
    assert event["p106_1_called"] is True
    assert event["p106_1_fingerprint_candidate_count"] == 1
    assert event["p106_1_fingerprint_candidate_used"] is True
    assert event["recovery_block_reason"] == "insufficient_series_or_title_hint"
