"""P103 whole-catalog (--all) execution mode tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue
from app.services.p103_gcd_catalog_enrichment_service import (
    EnrichmentFilters,
    validate_enrichment_filters,
)
from app.services.p103_gcd_enrichment_audit_helpers import build_overall_assertion_failures
from app.services.p103_gcd_enrichment_fast import (
    EnrichmentIssueSnapshot,
    load_catalog_enrichment_scope,
    plan_enrichment_updates,
)
from app.services.p101_catalog_cache_service import CatalogCacheContext, CatalogCacheMatcher


_ENRICHMENT_TABLE = """
CREATE TABLE catalog_issue_cache (
  issue_id INTEGER PRIMARY KEY,
  publisher_norm TEXT NOT NULL,
  series_norm TEXT NOT NULL,
  issue_norm TEXT NOT NULL,
  year INTEGER
);
CREATE TABLE catalog_upc_cache (
  normalized_upc TEXT PRIMARY KEY,
  issue_id INTEGER NOT NULL
);
CREATE TABLE learned_barcode_cache (
  normalized_barcode TEXT PRIMARY KEY
);
CREATE TABLE catalog_enrichment_issue (
  issue_id INTEGER PRIMARY KEY,
  year INTEGER,
  publisher_id INTEGER,
  series_id INTEGER,
  publisher_norm TEXT NOT NULL,
  series_norm TEXT NOT NULL,
  issue_norm TEXT NOT NULL,
  publisher_name TEXT,
  series_name TEXT,
  issue_number TEXT,
  cover_date TEXT,
  release_date TEXT,
  store_date TEXT,
  title TEXT,
  description TEXT,
  external_source_ids TEXT,
  variant_printing TEXT,
  variant_variant_name TEXT,
  has_upc INTEGER NOT NULL DEFAULT 0
);
"""


def _write_test_enrichment_cache(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(_ENRICHMENT_TABLE)
    rows = [
        (
            101,
            2018,
            1,
            10,
            "dc comics",
            "batman",
            "1",
            "DC Comics",
            "Batman",
            "1",
            None,
            None,
            None,
            None,
            None,
            "{}",
            None,
            None,
            0,
        ),
        (
            202,
            2019,
            2,
            20,
            "marvel comics",
            "spider man",
            "1",
            "Marvel Comics",
            "Spider-Man",
            "1",
            None,
            None,
            None,
            None,
            None,
            "{}",
            None,
            None,
            1,
        ),
    ]
    conn.executemany(
        """
        INSERT INTO catalog_enrichment_issue
        (issue_id, year, publisher_id, series_id, publisher_norm, series_norm, issue_norm,
         publisher_name, series_name, issue_number, cover_date, release_date, store_date,
         title, description, external_source_ids, variant_printing, variant_variant_name, has_upc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()


def test_validate_all_mode_without_publisher() -> None:
    filters = validate_enrichment_filters(
        write_batch=False,
        limit=100,
        publisher=None,
        year=None,
        year_from=None,
        year_to=None,
        confirm_write=None,
        all_catalog=True,
    )
    assert filters is not None
    assert filters.all_catalog is True
    assert filters.publisher is None
    assert filters.year_filter_explicit is False


def test_validate_scoped_still_requires_publisher() -> None:
    with pytest.raises(ValueError, match="--publisher is required"):
        validate_enrichment_filters(
            write_batch=False,
            limit=None,
            publisher=None,
            year=2018,
            year_from=None,
            year_to=None,
            confirm_write=None,
            all_catalog=False,
        )


def test_all_dry_run_scope_spans_multiple_publishers(tmp_path: Path) -> None:
    cache = tmp_path / "cache.sqlite"
    _write_test_enrichment_cache(cache)
    filters = EnrichmentFilters(
        publisher=None,
        year_from=2009,
        year_to=2026,
        limit=None,
        all_catalog=True,
        year_filter_explicit=False,
    )
    scope = load_catalog_enrichment_scope(cache, filters=filters)
    publishers = {s.publisher_name for s in scope}
    assert publishers == {"DC Comics", "Marvel Comics"}


def test_all_write_does_not_insert_catalog_issue(session: Session, tmp_path: Path, monkeypatch) -> None:
    from app.services.p103_gcd_enrichment_fast import _GcdIndex
    from app.services.p103_gcd_enrichment_write_service import run_p103_enrichment_write_batch

    monkeypatch.setattr(
        "app.services.p103_gcd_enrichment_write_service._load_gcd_index",
        lambda *args, **kwargs: _GcdIndex(exact={}, by_series_issue={}, rows_loaded=0),
    )

    before = len(session.exec(select(CatalogIssue)).all())
    cache = tmp_path / "cache.sqlite"
    _write_test_enrichment_cache(cache)
    gcd = tmp_path / "gcd.sqlite"
    sqlite3.connect(gcd).close()

    filters = EnrichmentFilters(
        publisher=None,
        year_from=2009,
        year_to=2026,
        limit=5,
        all_catalog=True,
        year_filter_explicit=False,
    )
    report = run_p103_enrichment_write_batch(
        session,
        gcd_path=gcd,
        cache_path=cache,
        filters=filters,
        rollback_collector={"upc_ids": [], "issue_snapshots": []},
    )
    after = len(session.exec(select(CatalogIssue)).all())
    assert after == before
    assert report.updated_issues == 0


def test_all_write_respects_no_overwrite_upc() -> None:
    snap = EnrichmentIssueSnapshot(
        issue_id=1,
        year=2018,
        publisher_id=1,
        series_id=2,
        publisher_norm="dc",
        series_norm="batman",
        issue_norm="1",
        publisher_name="DC Comics",
        series_name="Batman",
        issue_number="1",
        cover_date=None,
        release_date=None,
        store_date=None,
        title=None,
        description=None,
        external_source_ids={},
        variant_printing=None,
        variant_variant_name=None,
        has_upc=True,
    )
    ctx = CatalogCacheContext(
        matcher=CatalogCacheMatcher(exact_keys=set(), by_series_issue={}),
        upc_to_issue={},
        learned_barcodes=set(),
    )
    gcd = {
        "gcd_issue_id": 99,
        "barcode": "76194134192703921",
        "calendar_date": __import__("datetime").date(2018, 3, 1),
        "title": "Test",
        "notes": "Note",
        "issue_number": "1",
        "series": "Batman",
        "publisher": "DC Comics",
    }
    planned, conflicts, upc_n = plan_enrichment_updates(snap, gcd, ctx=ctx)
    assert upc_n == 0
    assert not any(p.get("field") == "catalog_upc" for p in planned)


def test_all_catalog_audit_passes_zero_insert_fixture() -> None:
    report = {
        "updated_issues": 2500,
        "inserted_upcs": 0,
        "written_rows": [{"catalog_issue_id": i, "inserted_upc": False} for i in range(2500)],
        "errors": [],
        "filters": {"all_catalog": True},
    }
    rollback = {"upc_ids": [], "issue_snapshots": [{}] * 2500}
    written = report["written_rows"]
    fails = build_overall_assertion_failures(
        report_counts_ok=True,
        report_failures=[],
        issues_found_in_db=2500,
        expected_updated=2500,
        expected_inserted_upcs=0,
        job_inserted_upc_count=0,
        tracks_job_upc_inserts=True,
        barcode_pass=True,
        barcode_tests=[],
        error_count=0,
    )
    assert fails == []
    assert len(written) == 2500
    assert rollback["upc_ids"] == []
