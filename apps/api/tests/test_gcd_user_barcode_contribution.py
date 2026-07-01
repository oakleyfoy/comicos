"""Tests for user-contributed GCD barcode rows."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from app.services.gcd_barcode_import_service import gcd_engine_from
from app.services.gcd_barcode_search_service import find_gcd_rows_by_normalized_barcode
from app.services.gcd_user_barcode_contribution_service import (
    contribute_barcode_to_gcd,
    find_gcd_issue_by_identity,
)


def _empty_gcd(tmp_path: Path) -> Path:
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
    return path


def test_contribute_inserts_new_gcd_issue_with_barcode(tmp_path: Path) -> None:
    gcd_path = _empty_gcd(tmp_path)
    barcode = "75960620629200111"
    gcd_issue_id = contribute_barcode_to_gcd(
        gcd_path,
        series="The Amazing Spider-Man",
        issue_number="122",
        publisher="Marvel",
        barcode=barcode,
        year=2023,
        facsimile=True,
        intake_item_id=94,
    )
    assert gcd_issue_id >= 9_000_000_000
    hits = find_gcd_rows_by_normalized_barcode(gcd_path, barcode)
    assert hits
    assert int(hits[0]["gcd_issue_id"]) == gcd_issue_id
    found = find_gcd_issue_by_identity(
        gcd_path,
        series="Amazing Spider-Man",
        issue_number="122",
        publisher="Marvel",
    )
    assert found is not None
    assert str(found["barcode_raw"]) == barcode


def test_contribute_updates_barcode_on_existing_issue(tmp_path: Path) -> None:
    gcd_path = _empty_gcd(tmp_path)
    engine = gcd_engine_from(str(gcd_path))
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO gcd_publisher (id, name) VALUES (1, 'Marvel')"))
        conn.execute(
            text(
                "INSERT INTO gcd_series (id, name, year_began, publisher_id) "
                "VALUES (10, 'Amazing Spider-Man', 1963, 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO gcd_issue (id, number, barcode, key_date, series_id, title, notes) "
                "VALUES (500, '122', NULL, '1973-06-00', 10, 'Green Goblin Last Stand', 'facsimile')"
            )
        )
    new_id = contribute_barcode_to_gcd(
        gcd_path,
        series="The Amazing Spider-Man",
        issue_number="122",
        publisher="Marvel",
        barcode="75960620629200111",
        facsimile=True,
    )
    assert new_id == 500
    hits = find_gcd_rows_by_normalized_barcode(gcd_path, "75960620629200111")
    assert hits and int(hits[0]["gcd_issue_id"]) == 500
