"""GCD deep barcode search (barcode / notes / isbn)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from app.services.gcd_barcode_import_service import gcd_engine_from
from app.services.gcd_barcode_search_service import (
    find_gcd_rows_by_normalized_barcode,
    search_gcd_barcode_fields,
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
                "series_id INTEGER, title TEXT, notes TEXT, isbn TEXT)"
            )
        )
        conn.execute(text("INSERT INTO gcd_publisher (id, name) VALUES (1, 'DC Comics')"))
        for i, row in enumerate(rows, start=1):
            sid = row.get("series_id", i)
            conn.execute(
                text("INSERT INTO gcd_series (id, name, year_began, publisher_id) VALUES (:id, :name, 2018, 1)"),
                {"id": sid, "name": row.get("series", "Series")},
            )
            conn.execute(
                text(
                    "INSERT INTO gcd_issue (id, number, barcode, key_date, series_id, title, notes, isbn) "
                    "VALUES (:id, :num, :bc, '2018-01-00', :sid, 'T', :notes, :isbn)"
                ),
                {
                    "id": row["gcd_issue_id"],
                    "num": row["number"],
                    "bc": row.get("barcode"),
                    "sid": sid,
                    "notes": row.get("notes"),
                    "isbn": row.get("isbn"),
                },
            )
    return path


def test_exact_hit_in_barcode_field(tmp_path: Path) -> None:
    bc = "76194134349501111"
    gcd_path = _gcd_db(
        tmp_path,
        rows=[{"gcd_issue_id": 1, "series": "Justice League", "number": "11", "barcode": bc}],
    )
    report = search_gcd_barcode_fields(gcd_path, bc)
    assert report.final_reason == "gcd_exact_barcode_match"
    assert len(report.gcd_exact_hits) == 1
    assert find_gcd_rows_by_normalized_barcode(gcd_path, bc)[0]["gcd_issue_id"] == 1


def test_upc12_prefix_without_full_supplement_is_prefix_not_exact(tmp_path: Path) -> None:
    bc = "76194134349501111"
    gcd_path = _gcd_db(
        tmp_path,
        rows=[{"gcd_issue_id": 1, "series": "JL", "number": "11", "barcode": "76194134349503921"}],
    )
    report = search_gcd_barcode_fields(gcd_path, bc)
    assert not report.gcd_exact_hits
    assert report.gcd_prefix_hits or report.final_reason == "gcd_prefix_or_partial_match_only"


def test_barcode_embedded_in_notes(tmp_path: Path) -> None:
    bc = "76194134199903921"
    gcd_path = _gcd_db(
        tmp_path,
        rows=[
            {
                "gcd_issue_id": 9,
                "series": "Notes Series",
                "number": "1",
                "barcode": None,
                "notes": f"Direct market UPC {bc} on cover",
            }
        ],
    )
    report = search_gcd_barcode_fields(gcd_path, bc)
    assert len(report.gcd_exact_hits) == 1
    assert report.gcd_exact_hits[0].source_field == "notes"
    assert len(report.gcd_notes_hits) == 1
    assert find_gcd_rows_by_normalized_barcode(gcd_path, bc)


def test_no_gcd_hit_unresolved_reason(tmp_path: Path) -> None:
    bc = "76194134194901111"
    gcd_path = _gcd_db(tmp_path, rows=[])
    report = search_gcd_barcode_fields(gcd_path, bc)
    assert report.final_reason == "no_gcd_barcode_match"
    assert not report.gcd_exact_hits
    assert not find_gcd_rows_by_normalized_barcode(gcd_path, bc)
