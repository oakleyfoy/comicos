"""P106 batch resolve from P103.5 upc_conflicts.csv."""

from __future__ import annotations

import csv
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc, CatalogVariant
from app.models.intake_queue import ComicIssueBarcode, MATCH_SOURCE_MANUAL
from app.services.gcd_barcode_import_service import gcd_engine_from
from app.services.p103_gcd_enrichment_helpers import extract_gcd_issue_id
from app.services.p106_barcode_gap_resolver_service import (
    DEFAULT_P1035_BATCH_REPORT,
    load_p1035_upc_conflict_rows,
    resolve_p1035_upc_conflicts_from_csv,
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
        conn.execute(text("INSERT INTO gcd_publisher (id, name) VALUES (1, 'DC Comics')"))
        for i, row in enumerate(rows, start=1):
            sid = row.get("series_id", i)
            conn.execute(
                text("INSERT INTO gcd_series (id, name, year_began, publisher_id) VALUES (:id, :name, 2018, 1)"),
                {"id": sid, "name": row.get("series", "Series")},
            )
            conn.execute(
                text(
                    "INSERT INTO gcd_issue (id, number, barcode, key_date, series_id, title, notes) "
                    "VALUES (:id, :num, :bc, '2018-01-00', :sid, 'T', '')"
                ),
                {
                    "id": row["gcd_issue_id"],
                    "num": row["number"],
                    "bc": row["barcode"],
                    "sid": sid,
                },
            )
    return path


def _seed_jl(session: Session, *, issue_number: str) -> int:
    pub = CatalogPublisher(name="DC", normalized_name="dc")
    session.add(pub)
    session.flush()
    series = CatalogSeries(name="Justice League", normalized_name="justice league", publisher_id=pub.id)
    session.add(series)
    session.flush()
    issue = CatalogIssue(
        series_id=int(series.id),
        publisher_id=pub.id,
        issue_number=issue_number,
        normalized_issue_number=issue_number,
        cover_date=date(2018, 1, 1),
    )
    session.add(issue)
    session.flush()
    session.add(CatalogVariant(issue_id=int(issue.id), variant_name="Standard"))
    session.commit()
    return int(issue.id)


def _write_upc_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "catalog_issue_id",
        "conflicting_barcode",
        "reason",
        "gcd_candidate",
        "existing_conflicting_catalog_issue_id",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_csv_row_auto_attaches_existing_catalog_issue(session: Session, tmp_path: Path) -> None:
    bc = "76194134349501111"
    issue_id = _seed_jl(session, issue_number="11")
    gcd_path = _gcd_db(
        tmp_path,
        rows=[{"gcd_issue_id": 1660187, "series": "Justice League", "number": "11", "barcode": bc}],
    )
    csv_path = tmp_path / "upc_conflicts.csv"
    _write_upc_csv(
        csv_path,
        [
            {
                "catalog_issue_id": str(issue_id),
                "conflicting_barcode": bc,
                "reason": "learned_barcode_conflict",
                "gcd_candidate": json.dumps({"gcd_issue_id": 1660187, "gcd_barcode": bc}),
                "existing_conflicting_catalog_issue_id": "",
            }
        ],
    )
    report_path = tmp_path / "report.json"
    report = resolve_p1035_upc_conflicts_from_csv(
        session,
        csv_path=csv_path,
        gcd_path=gcd_path,
        cache_path=None,
        limit=50,
        confirm_write=True,
        report_path=report_path,
    )
    assert report["counts"]["auto_attached"] == 1
    assert extract_gcd_issue_id(session.get(CatalogIssue, issue_id).external_source_ids) == 1660187
    assert report_path.is_file()


def test_csv_row_auto_imports_missing_catalog_issue(session: Session, tmp_path: Path) -> None:
    bc = "76194134199903921"
    gcd_path = _gcd_db(
        tmp_path,
        rows=[{"gcd_issue_id": 9001, "series": "New", "number": "1", "barcode": bc}],
    )
    csv_path = tmp_path / "upc_conflicts.csv"
    _write_upc_csv(
        csv_path,
        [
            {
                "catalog_issue_id": "",
                "conflicting_barcode": bc,
                "reason": "upc_mapped_elsewhere",
                "gcd_candidate": json.dumps({"gcd_issue_id": 9001}),
                "existing_conflicting_catalog_issue_id": "",
            }
        ],
    )
    report = resolve_p1035_upc_conflicts_from_csv(
        session,
        csv_path=csv_path,
        gcd_path=gcd_path,
        cache_path=None,
        limit=50,
        confirm_write=True,
        report_path=tmp_path / "report.json",
    )
    assert report["counts"]["auto_imported"] == 1


def test_already_resolved_row_skipped(session: Session, tmp_path: Path) -> None:
    bc = "76194134349501111"
    issue_id = _seed_jl(session, issue_number="11")
    session.add(
        CatalogUpc(
            upc=bc,
            normalized_upc=bc,
            issue_id=issue_id,
            source="manual",
            confidence=Decimal("1"),
        )
    )
    session.commit()
    gcd_path = _gcd_db(
        tmp_path,
        rows=[{"gcd_issue_id": 1, "series": "JL", "number": "11", "barcode": bc}],
    )
    csv_path = tmp_path / "upc_conflicts.csv"
    _write_upc_csv(
        csv_path,
        [
            {
                "catalog_issue_id": str(issue_id),
                "conflicting_barcode": bc,
                "reason": "learned_barcode_conflict",
                "gcd_candidate": "{}",
                "existing_conflicting_catalog_issue_id": "",
            }
        ],
    )
    report = resolve_p1035_upc_conflicts_from_csv(
        session,
        csv_path=csv_path,
        gcd_path=gcd_path,
        cache_path=None,
        limit=50,
        confirm_write=True,
        report_path=tmp_path / "report.json",
    )
    assert report["counts"]["already_resolved"] == 1


def test_conflicting_barcode_does_not_overwrite(session: Session, tmp_path: Path) -> None:
    bc = "76194134349501111"
    owner = _seed_jl(session, issue_number="11")
    other = _seed_jl(session, issue_number="99")
    session.add(
        CatalogUpc(
            upc=bc,
            normalized_upc=bc,
            issue_id=other,
            source="manual",
            confidence=Decimal("1"),
        )
    )
    session.commit()
    gcd_path = _gcd_db(
        tmp_path,
        rows=[{"gcd_issue_id": 1660187, "series": "Justice League", "number": "11", "barcode": bc}],
    )
    csv_path = tmp_path / "upc_conflicts.csv"
    _write_upc_csv(
        csv_path,
        [
            {
                "catalog_issue_id": str(owner),
                "conflicting_barcode": bc,
                "reason": "upc_mapped_elsewhere",
                "gcd_candidate": json.dumps({"gcd_issue_id": 1660187}),
                "existing_conflicting_catalog_issue_id": str(other),
            }
        ],
    )
    report = resolve_p1035_upc_conflicts_from_csv(
        session,
        csv_path=csv_path,
        gcd_path=gcd_path,
        cache_path=None,
        limit=50,
        confirm_write=True,
        report_path=tmp_path / "report.json",
    )
    assert report["counts"]["conflicts"] == 1
    row = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == bc)).one()
    assert int(row.issue_id or 0) == other


def test_no_gcd_hit_unresolved(session: Session, tmp_path: Path) -> None:
    bc = "76194134194901111"
    issue_id = _seed_jl(session, issue_number="1")
    gcd_path = _gcd_db(tmp_path, rows=[])
    csv_path = tmp_path / "upc_conflicts.csv"
    _write_upc_csv(
        csv_path,
        [
            {
                "catalog_issue_id": str(issue_id),
                "conflicting_barcode": bc,
                "reason": "barcode_validation_failed",
                "gcd_candidate": "{}",
                "existing_conflicting_catalog_issue_id": "",
            }
        ],
    )
    report = resolve_p1035_upc_conflicts_from_csv(
        session,
        csv_path=csv_path,
        gcd_path=gcd_path,
        cache_path=None,
        limit=50,
        confirm_write=True,
        dry_run=True,
        report_path=tmp_path / "report.json",
    )
    assert report["counts"]["unresolved"] == 1
    assert report["dry_run"] is True


def test_batch_report_written_and_dry_run_counts(session: Session, tmp_path: Path) -> None:
    bc = "76194134349501111"
    issue_id = _seed_jl(session, issue_number="11")
    gcd_path = _gcd_db(
        tmp_path,
        rows=[{"gcd_issue_id": 1660187, "series": "Justice League", "number": "11", "barcode": bc}],
    )
    csv_path = tmp_path / "upc_conflicts.csv"
    _write_upc_csv(
        csv_path,
        [
            {
                "catalog_issue_id": str(issue_id),
                "conflicting_barcode": bc,
                "reason": "learned_barcode_conflict",
                "gcd_candidate": json.dumps({"gcd_issue_id": 1660187}),
                "existing_conflicting_catalog_issue_id": "",
            }
        ],
    )
    report_path = tmp_path / "batch.json"
    report = resolve_p1035_upc_conflicts_from_csv(
        session,
        csv_path=csv_path,
        gcd_path=gcd_path,
        cache_path=None,
        limit=50,
        confirm_write=False,
        dry_run=True,
        report_path=report_path,
    )
    assert report_path.is_file()
    assert report["counts"]["auto_attached"] == 1
    assert report["counts"]["scanned"] == 1
    loaded = json.loads(report_path.read_text(encoding="utf-8"))
    assert loaded["counts"]["auto_attached"] == 1


def test_load_p1035_rows_dedupes(session: Session, tmp_path: Path) -> None:
    csv_path = tmp_path / "upc.csv"
    _write_upc_csv(
        csv_path,
        [
            {
                "catalog_issue_id": "1",
                "conflicting_barcode": "76194134349501111",
                "reason": "x",
                "gcd_candidate": "{}",
                "existing_conflicting_catalog_issue_id": "",
            },
            {
                "catalog_issue_id": "1",
                "conflicting_barcode": "76194134349501111",
                "reason": "x",
                "gcd_candidate": "{}",
                "existing_conflicting_catalog_issue_id": "",
            },
        ],
    )
    rows = load_p1035_upc_conflict_rows(csv_path, limit=50)
    assert len(rows) == 1
