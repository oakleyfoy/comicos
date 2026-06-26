"""P103 regression: duplicate catalog_upc must not abort batched writes."""

from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc, CatalogVariant
from app.services.gcd_barcode_import_service import GCD_SOURCE
from app.services.p103_gcd_catalog_enrichment_service import EnrichmentFilters
from app.services.p103_gcd_enrichment_fast import _GcdIndex
from app.services.p103_gcd_enrichment_write_service import run_p103_enrichment_write_batch


def _minimal_cache(path: Path, issue_id: int, *, has_upc: int = 0) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
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
    )
    conn.execute(
        """
        INSERT INTO catalog_enrichment_issue VALUES
        (?, 2018, 1, 10, 'dc comics', 'batman', '1', 'DC Comics', 'Batman', '1',
         NULL, NULL, NULL, NULL, NULL, '{}', NULL, NULL, ?)
        """,
        (issue_id, has_upc),
    )
    conn.commit()
    conn.close()


def test_p103_all_write_tolerates_existing_catalog_upc(session: Session, tmp_path: Path, monkeypatch) -> None:
    normalized = "07148601984816"
    pub = CatalogPublisher(name="DC Comics", normalized_name="dc comics")
    session.add(pub)
    session.commit()
    series = CatalogSeries(name="Batman", normalized_name="batman", publisher_id=int(pub.id))
    session.add(series)
    session.commit()
    issue = CatalogIssue(
        series_id=int(series.id),
        publisher_id=int(pub.id),
        issue_number="1",
        normalized_issue_number="1",
        cover_date=date(2018, 1, 1),
    )
    session.add(issue)
    session.commit()
    issue_id = int(issue.id)
    variant = CatalogVariant(issue_id=issue_id, variant_name="Standard")
    session.add(variant)
    session.commit()

    session.add(
        CatalogUpc(
            upc=normalized,
            normalized_upc=normalized,
            issue_id=issue_id,
            variant_id=int(variant.id),
            source=GCD_SOURCE,
            confidence=Decimal("1.0"),
            barcode_type="upc",
        )
    )
    session.commit()

    cache = tmp_path / "cache.sqlite"
    _minimal_cache(cache, issue_id=issue_id, has_upc=0)
    gcd = tmp_path / "gcd.sqlite"
    sqlite3.connect(gcd).close()

    gcd_row = {
        "issue_id": 9001,
        "gcd_publisher_id": 1,
        "gcd_series_id": 2,
        "publisher_name": "DC Comics",
        "series_name": "Batman",
        "number": "1",
        "barcode": normalized,
        "key_date": None,
        "year_began": 2018,
        "title": "GCD title fill",
        "notes": "Notes",
    }

    def _fake_index(*args, **kwargs):
        from app.services.p103_gcd_enrichment_fast import EnrichmentIssueSnapshot

        snap = EnrichmentIssueSnapshot(
            issue_id=issue_id,
            year=2018,
            publisher_id=int(pub.id),
            series_id=int(series.id),
            publisher_norm="dc comics",
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
            has_upc=False,
        )
        key = (snap.publisher_norm, snap.series_norm, snap.issue_norm)
        return _GcdIndex(exact={key: gcd_row}, by_series_issue={}, rows_loaded=1)

    monkeypatch.setattr(
        "app.services.p103_gcd_enrichment_write_service.load_gcd_index_for_enrichment",
        lambda *args, **kwargs: _fake_index(),
    )

    filters = EnrichmentFilters(
        publisher=None,
        year_from=2009,
        year_to=2026,
        limit=1,
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

    assert report.errors == []
    assert report.updated_issues == 1
    assert report.inserted_upcs == 0
    assert len(session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == normalized)).all()) == 1

    session.refresh(issue)
    assert issue.title == "GCD title fill"
