"""GCD barcode backfill: mapping, validation, conflict/learned safety, dry-run vs write."""

from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401
from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc, CatalogVariant
from app.models.intake_queue import ComicIssueBarcode
from app.services.gcd_barcode_import_service import (
    extract_barcodes,
    gcd_engine_from,
    run_gcd_backfill,
)

FULL = "76194134192703921"  # DC prefix + 03921 -> issue 39


def _local_engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_superman_39(session: Session, *, cover_year: int = 2015) -> int:
    pub = CatalogPublisher(name="DC Comics", normalized_name="dc comics")
    session.add(pub)
    session.commit()
    series = CatalogSeries(name="Superman", normalized_name="superman", publisher_id=pub.id, start_year=2011)
    session.add(series)
    session.commit()
    issue = CatalogIssue(
        series_id=int(series.id),
        publisher_id=pub.id,
        issue_number="39",
        normalized_issue_number="39",
        cover_date=date(cover_year, 4, 1),
    )
    session.add(issue)
    session.commit()
    session.add(CatalogVariant(issue_id=int(issue.id), variant_name="Standard"))
    session.commit()
    return int(issue.id)


def _gcd_db(tmp_path, *, barcode: str = FULL, series="Superman", publisher="DC Comics", number="39", key_date="2015-04-00"):
    engine = gcd_engine_from(str(tmp_path / "gcd.sqlite"))
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE gcd_publisher (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(text("CREATE TABLE gcd_series (id INTEGER PRIMARY KEY, name TEXT, year_began INTEGER, publisher_id INTEGER)"))
        conn.execute(text("CREATE TABLE gcd_issue (id INTEGER PRIMARY KEY, number TEXT, barcode TEXT, key_date TEXT, series_id INTEGER)"))
        conn.execute(text("INSERT INTO gcd_publisher (id, name) VALUES (1, :n)"), {"n": publisher})
        conn.execute(text("INSERT INTO gcd_series (id, name, year_began, publisher_id) VALUES (1, :n, 2011, 1)"), {"n": series})
        conn.execute(
            text("INSERT INTO gcd_issue (id, number, barcode, key_date, series_id) VALUES (1, :num, :bc, :kd, 1)"),
            {"num": number, "bc": barcode, "kd": key_date},
        )
    return engine


def test_extract_barcodes_handles_spacing_and_multiple():
    assert extract_barcodes("76194134192703921") == ["76194134192703921"]
    assert extract_barcodes("7 61941 34192 7 03921") == ["76194134192703921"]
    assert "76194134192703921" in extract_barcodes("76194134192703921; 75960601234500111")
    assert extract_barcodes("") == []
    assert extract_barcodes(None) == []


def test_dryrun_matches_and_projects_insert(tmp_path):
    engine = _local_engine()
    with Session(engine) as session:
        issue_id = _seed_superman_39(session)
        gcd = _gcd_db(tmp_path)

        stats = run_gcd_backfill(session, gcd, write=False)

        assert stats.rows_with_barcode == 1
        assert stats.matched_local_issues == 1
        assert stats.projected_inserts == 1
        assert stats.duplicate_conflicts == 0
        assert stats.rejected_validation == 0
        # dry-run writes nothing
        assert session.exec(select(CatalogUpc)).first() is None
        assert any(s["validation_status"] == "exact_match" and s["local_issue_id"] == issue_id for s in stats.samples)


def test_write_inserts_catalog_upc(tmp_path):
    engine = _local_engine()
    with Session(engine) as session:
        issue_id = _seed_superman_39(session)
        gcd = _gcd_db(tmp_path)

        stats = run_gcd_backfill(session, gcd, write=True)

        assert stats.written == 1
        row = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == FULL)).one()
        assert row.issue_id == issue_id
        assert row.source == "GCD"


def test_user_confirmed_barcode_is_preferred(tmp_path):
    engine = _local_engine()
    with Session(engine) as session:
        issue_id = _seed_superman_39(session)
        session.add(ComicIssueBarcode(normalized_barcode=FULL, catalog_issue_id=issue_id, source="manual"))
        session.commit()
        gcd = _gcd_db(tmp_path)

        stats = run_gcd_backfill(session, gcd, write=True)

        assert stats.skipped_learned == 1
        assert stats.projected_inserts == 0
        assert stats.written == 0
        assert session.exec(select(CatalogUpc)).first() is None


def test_existing_conflicting_upc_never_overwritten(tmp_path):
    engine = _local_engine()
    with Session(engine) as session:
        issue_id = _seed_superman_39(session)
        session.add(CatalogUpc(upc=FULL, normalized_upc=FULL, issue_id=issue_id + 999, source="MANUAL"))
        session.commit()
        gcd = _gcd_db(tmp_path)

        stats = run_gcd_backfill(session, gcd, write=True)

        assert stats.duplicate_conflicts == 1
        assert stats.written == 0
        row = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == FULL)).one()
        assert row.issue_id == issue_id + 999  # untouched
        assert row.source == "MANUAL"


def test_validation_rejects_modern_upc_on_pre1976_record(tmp_path):
    engine = _local_engine()
    with Session(engine) as session:
        _seed_superman_39(session, cover_year=1952)
        gcd = _gcd_db(tmp_path, key_date="1952-04-00")

        stats = run_gcd_backfill(session, gcd, write=True)

        assert stats.matched_local_issues == 1
        assert stats.rejected_validation == 1
        assert stats.projected_inserts == 0
        assert session.exec(select(CatalogUpc)).first() is None


def test_unmatched_when_series_absent(tmp_path):
    engine = _local_engine()
    with Session(engine) as session:
        _seed_superman_39(session)
        gcd = _gcd_db(tmp_path, series="Obscure Indie Title", publisher="Tiny Press")

        stats = run_gcd_backfill(session, gcd, write=True)

        assert stats.unmatched_rows == 1
        assert stats.matched_local_issues == 0
        assert stats.written == 0
