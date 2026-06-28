"""P106.1 GCD non-barcode recovery tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text
from sqlmodel import Session

from app.services.gcd_barcode_import_service import gcd_engine_from
from app.services.p106_barcode_gap_resolver_service import (
    P106_STATUS_REVIEW_REQUIRED,
    resolve_barcode_gap,
)
from app.services.p106_1_gcd_non_barcode_recovery_service import (
    IntakeGcdRecoveryHints,
    P106_1_IMPORT_REASON,
    P106_1_RECOVERY_STAGE,
    _score_candidate_breakdown,
    build_p106_1_intake_hint_snapshot,
    diagnose_gcd_non_barcode_recovery,
    enrich_gap_diagnosis_with_gcd_non_barcode_recovery,
    gather_intake_gcd_recovery_hints,
    has_reliable_series_hint,
)


def _gcd_db(tmp_path: Path, *, rows: list[dict]) -> Path:
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
        conn.execute(text("INSERT INTO gcd_publisher (id, name) VALUES (2, 'DC Comics')"))
        for i, row in enumerate(rows, start=1):
            pub_id = row.get("publisher_id", 1)
            conn.execute(
                text(
                    "INSERT INTO gcd_series (id, name, year_began, publisher_id) VALUES (:id, :name, :yb, :pid)"
                ),
                {
                    "id": row.get("series_id", i),
                    "name": row["series"],
                    "yb": row.get("year_began", 2024),
                    "pid": pub_id,
                },
            )
            conn.execute(
                text(
                    "INSERT INTO gcd_issue (id, number, barcode, key_date, series_id, title, notes) "
                    "VALUES (:id, :num, :bc, :kd, :sid, :title, :notes)"
                ),
                {
                    "id": row["gcd_issue_id"],
                    "num": row["number"],
                    "bc": row.get("barcode"),
                    "kd": row.get("key_date", "2024-01-00"),
                    "sid": row.get("series_id", i),
                    "title": row.get("title", "Test"),
                    "notes": row.get("notes", ""),
                },
            )
    return path


@dataclass
class _FakeIntakeItem:
    id: int = 1
    matched_publisher: str | None = None
    matched_series: str | None = None
    matched_issue_number: str | None = None
    matched_year: str | None = None


def test_insufficient_metadata_sets_recovery_stage(session: Session, tmp_path: Path) -> None:
    gcd_path = _gcd_db(tmp_path, rows=[])
    hints = IntakeGcdRecoveryHints(
        publisher=None,
        series=None,
        issue_number=None,
        year=None,
        ocr_title=None,
        ocr_issue_number=None,
        ocr_publisher=None,
    )
    diag = diagnose_gcd_non_barcode_recovery(
        session,
        barcode="75960620629200111",
        gcd_path=gcd_path,
        cache_path=None,
        hints=hints,
        image_path=None,
        prior_diagnosis={"gcd_match_count": 0},
    )
    assert diag["recovery_stage"] == P106_1_RECOVERY_STAGE
    assert diag["recovery_reason"] == "insufficient_metadata"
    assert diag["ready_to_auto_import"] is False


def test_unique_empty_barcode_candidate_auto_import(session: Session, tmp_path: Path) -> None:
    bc = "75960620629200111"
    gcd_path = _gcd_db(
        tmp_path,
        rows=[
            {
                "gcd_issue_id": 88001,
                "series": "Amazing Spider-Man",
                "number": "1",
                "barcode": None,
                "title": "Facsimile Edition",
                "notes": "facsimile reprint",
                "key_date": "2024-06-00",
            }
        ],
    )
    hints = IntakeGcdRecoveryHints(
        publisher="Marvel",
        series="Amazing Spider-Man",
        issue_number="1",
        year=2024,
        ocr_title=None,
        ocr_issue_number=None,
        ocr_publisher=None,
        facsimile_or_reprint=True,
        series_norm_aliases=["amazing spider man"],
    )
    diag = diagnose_gcd_non_barcode_recovery(
        session,
        barcode=bc,
        gcd_path=gcd_path,
        cache_path=None,
        hints=hints,
        image_path=None,
        prior_diagnosis={"gcd_match_count": 0, "normalized_barcode": bc},
    )
    assert diag["ready_to_auto_import"] is True
    assert diag["gcd_issue_id"] == 88001
    assert diag["proposed_action"] == "auto_import"
    assert diag["import_reason"] == P106_1_IMPORT_REASON

    out = resolve_barcode_gap(session, barcode=bc, gcd_path=gcd_path, diagnosis=diag, confirm_write=True)
    assert out["written"] is True
    assert int(out["result"]["catalog_issue_id"]) > 0


def test_ambiguous_candidates_review_required(session: Session, tmp_path: Path) -> None:
    bc = "75960620629200111"
    gcd_path = _gcd_db(
        tmp_path,
        rows=[
            {
                "gcd_issue_id": 88010,
                "series": "Amazing Spider-Man",
                "number": "1",
                "barcode": None,
                "title": "First printing",
                "key_date": "2024-06-00",
                "series_id": 1,
            },
            {
                "gcd_issue_id": 88011,
                "series": "The Amazing Spider-Man",
                "number": "1",
                "barcode": None,
                "title": "Variant cover",
                "key_date": "2024-07-00",
                "series_id": 2,
            },
        ],
    )
    hints = IntakeGcdRecoveryHints(
        publisher="Marvel",
        series="Amazing Spider-Man",
        issue_number="1",
        year=2024,
        ocr_title=None,
        ocr_issue_number=None,
        ocr_publisher=None,
        series_norm_aliases=["amazing spider man", "the amazing spider man"],
    )
    diag = diagnose_gcd_non_barcode_recovery(
        session,
        barcode=bc,
        gcd_path=gcd_path,
        cache_path=None,
        hints=hints,
        image_path=None,
        prior_diagnosis={"gcd_match_count": 0},
    )
    assert diag["ready_to_auto_import"] is False
    assert diag["status"] == P106_STATUS_REVIEW_REQUIRED
    assert diag["reason"] == "ambiguous_gcd_non_barcode_candidates"
    assert len(diag["gcd_non_barcode_ranked"]) >= 2


def test_enrich_skips_when_gcd_barcode_already_matched(session: Session, tmp_path: Path) -> None:
    gcd_path = _gcd_db(tmp_path, rows=[])
    item = _FakeIntakeItem(matched_publisher="Marvel", matched_issue_number="1")
    prior = {"gcd_match_count": 1, "ready_to_auto_import": True}
    out = enrich_gap_diagnosis_with_gcd_non_barcode_recovery(
        session,
        item=item,
        barcode="75960620629200111",
        gcd_path=gcd_path,
        cache_path=None,
        image_path=None,
        image_bytes=None,
        prior_diagnosis=prior,
        p105=None,
    )
    assert out is prior


@patch("app.services.p106_1_gcd_non_barcode_recovery_service.extract_ocr_signal")
def test_facsimile_ocr_boosts_facsimile_gcd_row(
    mock_ocr: MagicMock,
    session: Session,
    tmp_path: Path,
) -> None:
    bc = "75960620629200111"
    gcd_path = _gcd_db(
        tmp_path,
        rows=[
            {
                "gcd_issue_id": 88020,
                "series": "Amazing Spider-Man",
                "number": "1",
                "barcode": None,
                "title": "Facsimile Edition",
                "notes": "2024 facsimile",
                "key_date": "2024-06-00",
            },
            {
                "gcd_issue_id": 88021,
                "series": "Amazing Spider-Man",
                "number": "1",
                "barcode": None,
                "title": "Regular issue",
                "notes": "",
                "key_date": "2024-06-00",
                "series_id": 2,
            },
        ],
    )
    mock_ocr.return_value = MagicMock(
        confidence=0.9,
        title="Amazing Spider-Man",
        issue_number="1",
        publisher="Marvel",
        raw_text="Facsimile Edition reprint",
    )
    item = _FakeIntakeItem(matched_year="2024")
    hints = gather_intake_gcd_recovery_hints(
        session,
        item=item,
        normalized_barcode=bc,
        image_path=None,
        image_bytes=b"fake",
        p105=None,
    )
    assert hints.facsimile_or_reprint is True
    assert hints.publisher == "Marvel"
    assert hints.issue_number == "1"

    diag = diagnose_gcd_non_barcode_recovery(
        session,
        barcode=bc,
        gcd_path=gcd_path,
        cache_path=None,
        hints=hints,
        image_path=None,
        prior_diagnosis={"gcd_match_count": 0},
    )
    assert diag.get("ready_to_auto_import") is True
    assert diag.get("gcd_issue_id") == 88020
    assert diag.get("proposed_action") == "auto_import"


def test_has_reliable_series_hint_rejects_blank_and_generic() -> None:
    assert has_reliable_series_hint(None) is False
    assert has_reliable_series_hint("") is False
    assert has_reliable_series_hint("Marvel") is False
    assert has_reliable_series_hint("Facsimile Edition") is False
    assert has_reliable_series_hint("Amazing Spider-Man") is True


@patch("app.services.p106_1_gcd_non_barcode_recovery_service.extract_ocr_signal")
def test_low_confidence_ocr_still_propagates_title_and_facsimile(
    mock_ocr: MagicMock,
    session: Session,
    tmp_path: Path,
) -> None:
    mock_ocr.return_value = MagicMock(
        confidence=0.22,
        title="Amazing Spider-Man",
        issue_number="1",
        publisher="Marvel",
        raw_text="Facsimile Edition Amazing Spider-Man #1",
    )
    item = _FakeIntakeItem(matched_issue_number="1")
    hints = gather_intake_gcd_recovery_hints(
        session,
        item=item,
        normalized_barcode="75960620629200111",
        image_path=None,
        image_bytes=b"fake",
        p105=None,
    )
    assert hints.ocr_title == "Amazing Spider-Man"
    assert hints.facsimile_or_reprint is True
    assert hints.series == "Amazing Spider-Man"
    assert has_reliable_series_hint(hints.series)


def test_build_intake_hint_snapshot_includes_fingerprint_count(session: Session, tmp_path: Path) -> None:
    item = _FakeIntakeItem(matched_publisher="Marvel", matched_issue_number="1")
    _, snapshot = build_p106_1_intake_hint_snapshot(
        session,
        item=item,
        barcode="75960620629200111",
        image_path=None,
        image_bytes=None,
        p105=None,
    )
    assert snapshot["barcode"] == "75960620629200111"
    assert "fingerprint_candidate_count" in snapshot
    assert snapshot["image_bytes_present"] is False
    assert has_reliable_series_hint(None) is False
    assert has_reliable_series_hint("") is False
    assert has_reliable_series_hint("Marvel") is False
    assert has_reliable_series_hint("Facsimile Edition") is False
    assert has_reliable_series_hint("Amazing Spider-Man") is True


def test_blank_series_hint_does_not_award_series_pts(session: Session, tmp_path: Path) -> None:
    gcd_path = _gcd_db(
        tmp_path,
        rows=[
            {
                "gcd_issue_id": 88100,
                "series": "X-Men",
                "number": "1",
                "barcode": None,
                "title": "First issue",
                "series_id": 1,
            },
            {
                "gcd_issue_id": 88101,
                "series": "Avengers",
                "number": "1",
                "barcode": None,
                "title": "First issue",
                "series_id": 2,
            },
        ],
    )
    hints = IntakeGcdRecoveryHints(
        publisher="Marvel",
        series=None,
        issue_number="1",
        year=2024,
        ocr_title=None,
        ocr_issue_number=None,
        ocr_publisher=None,
        series_norm_aliases=[],
    )
    rows = [
        {"gcd_issue_id": 88100, "publisher": "Marvel", "series": "X-Men", "issue_number": "1", "title": "First issue", "pub_year": 2024},
        {"gcd_issue_id": 88101, "publisher": "Marvel", "series": "Avengers", "issue_number": "1", "title": "First issue", "pub_year": 2024},
    ]
    for row in rows:
        _, breakdown = _score_candidate_breakdown(session, row=row, hints=hints, image_path=None)
        assert breakdown["series_pts"] == 0
        assert breakdown["series_match_state"] == "unavailable"
        assert breakdown["series_match_failed"] is None


def test_broad_marvel_issue_one_pool_without_discriminators(session: Session, tmp_path: Path) -> None:
    bc = "75960620629200111"
    gcd_path = _gcd_db(
        tmp_path,
        rows=[
            {"gcd_issue_id": 88110, "series": "X-Men", "number": "1", "barcode": None, "series_id": 1},
            {"gcd_issue_id": 88111, "series": "Avengers", "number": "1", "barcode": None, "series_id": 2},
        ],
    )
    hints = IntakeGcdRecoveryHints(
        publisher="Marvel",
        series=None,
        issue_number="1",
        year=2024,
        ocr_title=None,
        ocr_issue_number=None,
        ocr_publisher=None,
        series_norm_aliases=[],
    )
    diag = diagnose_gcd_non_barcode_recovery(
        session,
        barcode=bc,
        gcd_path=gcd_path,
        cache_path=None,
        hints=hints,
        image_path=None,
        prior_diagnosis={"gcd_match_count": 0},
    )
    assert diag["ready_to_auto_import"] is False
    assert diag["recovery_block_reason"] == "insufficient_series_or_title_hint"
    assert diag["reason"] == "insufficient_series_or_title_hint"


def test_reliable_series_filters_unrelated_marvel_issue_one(session: Session, tmp_path: Path) -> None:
    bc = "75960620629200111"
    gcd_path = _gcd_db(
        tmp_path,
        rows=[
            {
                "gcd_issue_id": 88120,
                "series": "Amazing Spider-Man",
                "number": "1",
                "barcode": None,
                "title": "Facsimile",
                "notes": "facsimile",
                "series_id": 1,
            },
            {"gcd_issue_id": 88121, "series": "X-Men", "number": "1", "barcode": None, "series_id": 2},
        ],
    )
    hints = IntakeGcdRecoveryHints(
        publisher="Marvel",
        series="Amazing Spider-Man",
        issue_number="1",
        year=2024,
        ocr_title=None,
        ocr_issue_number=None,
        ocr_publisher=None,
        facsimile_or_reprint=True,
        series_norm_aliases=["amazing spider man"],
    )
    diag = diagnose_gcd_non_barcode_recovery(
        session,
        barcode=bc,
        gcd_path=gcd_path,
        cache_path=None,
        hints=hints,
        image_path=None,
        prior_diagnosis={"gcd_match_count": 0},
    )
    assert diag["ready_to_auto_import"] is True
    assert diag["gcd_issue_id"] == 88120


def test_reliable_series_clear_winner_among_compatible_variants(session: Session, tmp_path: Path) -> None:
    bc = "75960620629200111"
    gcd_path = _gcd_db(
        tmp_path,
        rows=[
            {
                "gcd_issue_id": 88130,
                "series": "Amazing Spider-Man",
                "number": "1",
                "barcode": None,
                "title": "Facsimile Edition",
                "notes": "facsimile reprint",
                "key_date": "2024-06-00",
                "series_id": 1,
            },
            {
                "gcd_issue_id": 88131,
                "series": "Amazing Spider-Man",
                "number": "1",
                "barcode": None,
                "title": "Regular",
                "notes": "",
                "key_date": "2024-06-00",
                "series_id": 2,
            },
        ],
    )
    hints = IntakeGcdRecoveryHints(
        publisher="Marvel",
        series="Amazing Spider-Man",
        issue_number="1",
        year=2024,
        ocr_title=None,
        ocr_issue_number=None,
        ocr_publisher=None,
        facsimile_or_reprint=True,
        series_norm_aliases=["amazing spider man"],
    )
    diag = diagnose_gcd_non_barcode_recovery(
        session,
        barcode=bc,
        gcd_path=gcd_path,
        cache_path=None,
        hints=hints,
        image_path=None,
        prior_diagnosis={"gcd_match_count": 0},
    )
    assert diag["ready_to_auto_import"] is True
    assert diag["gcd_issue_id"] == 88130
