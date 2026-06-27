"""Regression: export_catalog_cache handles learned ComicIssueBarcode rows."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlmodel import Session

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.models.intake_queue import ComicIssueBarcode
from app.services.p101_catalog_cache_service import export_catalog_cache


def test_export_catalog_cache_includes_learned_barcodes(session: Session, tmp_path: Path) -> None:
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
    )
    session.add(issue)
    session.commit()
    session.add(
        ComicIssueBarcode(
            normalized_barcode="76194134192703921",
            catalog_issue_id=int(issue.id),
            source="manual",
        )
    )
    session.commit()

    cache_path = tmp_path / "cache.sqlite"
    count = export_catalog_cache(session, cache_path)
    assert count >= 1

    conn = sqlite3.connect(cache_path)
    learned = conn.execute("SELECT normalized_barcode FROM learned_barcode_cache").fetchall()
    enrich_count = conn.execute("SELECT COUNT(*) FROM catalog_enrichment_issue").fetchone()[0]
    conn.close()

    assert learned == [("76194134192703921",)]
    assert int(enrich_count) >= 1
