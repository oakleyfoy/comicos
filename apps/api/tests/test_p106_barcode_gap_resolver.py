"""P106 barcode gap auto-resolver tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc, CatalogVariant
from app.models.intake_queue import ComicIssueBarcode, MATCH_SOURCE_MANUAL
from app.models.p105_barcode_repair import P105MissingBarcodeQueue, P105_QUEUE_PENDING
from app.models.p106_barcode_gap import (
    P106_STATUS_AUTO_ATTACHED,
    P106_STATUS_AUTO_IMPORTED,
    P106_STATUS_CONFLICT,
    P106_STATUS_REVIEW_REQUIRED,
    P106_STATUS_UNRESOLVED,
    BarcodeGapResolutionQueue,
)
from app.services.gcd_barcode_import_service import gcd_engine_from
from app.services.p103_gcd_enrichment_helpers import extract_gcd_issue_id
from app.services.p106_barcode_gap_resolver_service import (
    P106_IMPORT_REASON,
    P106_META_KEY,
    diagnose_barcode_gap,
    merge_barcode_gap_into_barcode_read,
    resolve_barcode_gap,
    resolve_barcode_gaps_from_scanner_queue,
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
            conn.execute(
                text(
                    "INSERT INTO gcd_series (id, name, year_began, publisher_id) VALUES (:id, :name, 2018, 1)"
                ),
                {"id": row.get("series_id", i), "name": row["series"]},
            )
            conn.execute(
                text(
                    "INSERT INTO gcd_issue (id, number, barcode, key_date, series_id, title, notes) "
                    "VALUES (:id, :num, :bc, :kd, :sid, :title, '')"
                ),
                {
                    "id": row["gcd_issue_id"],
                    "num": row["number"],
                    "bc": row["barcode"],
                    "kd": row.get("key_date", "2018-03-00"),
                    "sid": row.get("series_id", i),
                    "title": row.get("title", "Test"),
                },
            )
    return path


def _seed_jl_issue(session: Session, *, issue_number: str = "11", publisher_name: str = "DC") -> int:
    pub = CatalogPublisher(name=publisher_name, normalized_name=publisher_name.lower())
    session.add(pub)
    session.flush()
    series = CatalogSeries(
        name="Justice League",
        normalized_name="justice league",
        publisher_id=pub.id,
        start_year=2018,
    )
    session.add(series)
    session.flush()
    issue = CatalogIssue(
        series_id=int(series.id),
        publisher_id=pub.id,
        issue_number=issue_number,
        normalized_issue_number=issue_number,
        title="Drowned Earth Part Two",
        cover_date=date(2018, 12, 1),
    )
    session.add(issue)
    session.flush()
    session.add(CatalogVariant(issue_id=int(issue.id), variant_name="Standard"))
    session.commit()
    return int(issue.id)


def test_auto_import_unknown_barcode_unique_gcd(session: Session, tmp_path: Path) -> None:
    bc = "76194134199903921"
    gcd_path = _gcd_db(
        tmp_path,
        rows=[
            {
                "gcd_issue_id": 9001,
                "series": "New Series",
                "number": "1",
                "barcode": bc,
                "title": "First",
            }
        ],
    )
    diag = diagnose_barcode_gap(session, barcode=bc, gcd_path=gcd_path, cache_path=None)
    assert diag["ready_to_auto_import"] is True
    assert diag["proposed_action"] == "auto_import"

    out = resolve_barcode_gap(session, barcode=bc, gcd_path=gcd_path, confirm_write=True)
    assert out["written"] is True
    issue_id = int(out["result"]["catalog_issue_id"])
    issue = session.get(CatalogIssue, issue_id)
    assert issue is not None
    assert extract_gcd_issue_id(issue.external_source_ids) == 9001
    upc = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == bc)).first()
    assert upc is not None and int(upc.issue_id or 0) == issue_id
    meta = (issue.external_source_ids or {}).get(P106_META_KEY) or {}
    assert meta.get("import_reason") == P106_IMPORT_REASON


def test_auto_attach_existing_catalog_issue(session: Session, tmp_path: Path) -> None:
    bc = "76194134349501111"
    issue_id = _seed_jl_issue(session, issue_number="11")
    gcd_path = _gcd_db(
        tmp_path,
        rows=[{"gcd_issue_id": 1660187, "series": "Justice League", "number": "11", "barcode": bc}],
    )
    out = resolve_barcode_gap(session, barcode=bc, gcd_path=gcd_path, confirm_write=True)
    assert out["written"] is True
    assert int(out["result"]["catalog_issue_id"]) == issue_id
    issue = session.get(CatalogIssue, issue_id)
    assert extract_gcd_issue_id(issue.external_source_ids) == 1660187
    assert session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == bc)).first() is not None


def test_barcode_exact_match_bypasses_p1035_publisher_mismatch(session: Session, tmp_path: Path) -> None:
    """Publisher label differs from GCD but series+issue + exact barcode still attach."""
    bc = "76194134349501111"
    issue_id = _seed_jl_issue(session, publisher_name="DC Comics")
    gcd_path = _gcd_db(
        tmp_path,
        rows=[{"gcd_issue_id": 1660187, "series": "Justice League", "number": "11", "barcode": bc}],
    )
    diag = diagnose_barcode_gap(session, barcode=bc, gcd_path=gcd_path)
    assert diag["ready_to_auto_import"] is True
    assert diag["bypass_p1035_text_matching"] is True
    resolve_barcode_gap(session, barcode=bc, gcd_path=gcd_path, confirm_write=True)
    assert extract_gcd_issue_id(session.get(CatalogIssue, issue_id).external_source_ids) == 1660187


def test_catalog_upc_conflict_creates_review_not_overwrite(session: Session, tmp_path: Path) -> None:
    bc = "76194134349501111"
    owner = _seed_jl_issue(session, issue_number="11")
    other = _seed_jl_issue(session, issue_number="12")
    session.add(
        CatalogUpc(
            upc=bc,
            normalized_upc=bc,
            issue_id=other,
            source="manual",
            confidence=1,
        )
    )
    session.commit()
    gcd_path = _gcd_db(
        tmp_path,
        rows=[{"gcd_issue_id": 1660187, "series": "Justice League", "number": "11", "barcode": bc}],
    )
    diag = diagnose_barcode_gap(session, barcode=bc, gcd_path=gcd_path)
    assert diag["status"] == P106_STATUS_CONFLICT
    resolve_barcode_gap(session, barcode=bc, gcd_path=gcd_path, confirm_write=True)
    row = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == bc)).one()
    assert int(row.issue_id or 0) == other
    queue = session.exec(select(BarcodeGapResolutionQueue)).first()
    assert queue is not None and queue.status == P106_STATUS_CONFLICT


def test_learned_barcode_conflict_review(session: Session, tmp_path: Path) -> None:
    bc = "76194134349501111"
    owner = _seed_jl_issue(session, issue_number="11")
    other = _seed_jl_issue(session, issue_number="99")
    session.add(
        ComicIssueBarcode(
            normalized_barcode=bc,
            catalog_issue_id=other,
            source=MATCH_SOURCE_MANUAL,
        )
    )
    session.commit()
    gcd_path = _gcd_db(
        tmp_path,
        rows=[{"gcd_issue_id": 1660187, "series": "Justice League", "number": "11", "barcode": bc}],
    )
    diag = diagnose_barcode_gap(session, barcode=bc, gcd_path=gcd_path)
    assert diag["status"] == P106_STATUS_CONFLICT
    resolve_barcode_gap(session, barcode=bc, gcd_path=gcd_path, confirm_write=True)
    assert session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == bc)).first() is None


def test_multiple_gcd_same_barcode_review(session: Session, tmp_path: Path) -> None:
    bc = "76194134349509999"
    gcd_path = _gcd_db(
        tmp_path,
        rows=[
            {"gcd_issue_id": 1, "series": "A", "number": "1", "barcode": bc, "series_id": 1},
            {"gcd_issue_id": 2, "series": "B", "number": "2", "barcode": bc, "series_id": 2},
        ],
    )
    diag = diagnose_barcode_gap(session, barcode=bc, gcd_path=gcd_path)
    assert diag["status"] == P106_STATUS_REVIEW_REQUIRED
    out = resolve_barcode_gap(session, barcode=bc, gcd_path=gcd_path, confirm_write=True)
    assert out["written"] is True
    assert session.get(BarcodeGapResolutionQueue, out["queue_id"]).status == P106_STATUS_REVIEW_REQUIRED


def test_no_gcd_unresolved(session: Session, tmp_path: Path) -> None:
    bc = "76194134194901111"
    gcd_path = _gcd_db(tmp_path, rows=[])
    diag = diagnose_barcode_gap(session, barcode=bc, gcd_path=gcd_path)
    assert diag["status"] == P106_STATUS_UNRESOLVED
    out = resolve_barcode_gap(session, barcode=bc, gcd_path=gcd_path, confirm_write=True)
    assert out["written"] is True
    assert session.get(BarcodeGapResolutionQueue, out["queue_id"]).status == P106_STATUS_UNRESOLVED


def test_rollback_metadata_on_auto_import(session: Session, tmp_path: Path) -> None:
    bc = "76194134199903921"
    gcd_path = _gcd_db(
        tmp_path,
        rows=[{"gcd_issue_id": 42, "series": "S", "number": "1", "barcode": bc}],
    )
    out = resolve_barcode_gap(session, barcode=bc, gcd_path=gcd_path, confirm_write=True)
    rollback = out.get("rollback") or {}
    assert rollback.get("import_reason") == P106_IMPORT_REASON
    assert "created_issue_ids" in rollback or "issue_snapshots" in rollback or out["result"].get("catalog_issue_id")


def test_scanner_diagnostic_ready_flag(session: Session, tmp_path: Path) -> None:
    bc = "76194134349501111"
    _seed_jl_issue(session, issue_number="11")
    gcd_path = _gcd_db(
        tmp_path,
        rows=[{"gcd_issue_id": 1660187, "series": "Justice League", "number": "11", "barcode": bc}],
    )
    diag = diagnose_barcode_gap(session, barcode=bc, gcd_path=gcd_path)
    merged = merge_barcode_gap_into_barcode_read(None, diag)
    import json

    payload = json.loads(merged)
    assert payload["barcode_gap"]["ready_to_auto_import"] is True


def test_batch_scanner_queue(session: Session, tmp_path: Path) -> None:
    bc = "76194134349500311"
    _seed_jl_issue(session, issue_number="3")
    gcd_path = _gcd_db(
        tmp_path,
        rows=[{"gcd_issue_id": 1615986, "series": "Justice League", "number": "3", "barcode": bc}],
    )
    session.add(P105MissingBarcodeQueue(barcode=bc, status=P105_QUEUE_PENDING))
    session.commit()
    batch = resolve_barcode_gaps_from_scanner_queue(
        session, gcd_path=gcd_path, cache_path=None, limit=10, confirm_write=True
    )
    assert batch["processed"] == 1
    assert batch["outcomes"][0]["written"] is True
    assert int(batch["outcomes"][0]["result"]["catalog_issue_id"]) > 0
