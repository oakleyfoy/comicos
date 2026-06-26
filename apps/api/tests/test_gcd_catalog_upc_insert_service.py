"""Tests for shared GCD catalog UPC insertion."""

from __future__ import annotations

from decimal import Decimal

from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc, CatalogVariant
from app.services.catalog_ingestion_service import normalize_upc
from app.services.gcd_barcode_import_service import GCD_SOURCE
from app.services.gcd_catalog_upc_insert_service import insert_catalog_upc_if_absent


def test_insert_returns_existing_id_without_duplicate_row(session: Session) -> None:
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
    issue_id = int(issue.id)
    variant = CatalogVariant(issue_id=issue_id, variant_name="Standard")
    session.add(variant)
    session.commit()

    normalized = "07148601984816"
    existing = CatalogUpc(
        upc=normalized,
        normalized_upc=normalized,
        issue_id=issue_id,
        variant_id=int(variant.id),
        source=GCD_SOURCE,
        confidence=Decimal("1.0"),
        barcode_type="upc",
    )
    session.add(existing)
    session.commit()
    existing_id = int(existing.id)

    learned: set[str] = set()
    upc_map: dict[str, int] = {}

    upc_id, created = insert_catalog_upc_if_absent(
        session,
        raw_upc=normalized,
        issue_id=issue_id,
        variant_id=int(variant.id),
        learned=learned,
        upc_map=upc_map,
    )
    assert created is False
    assert upc_id == existing_id
    assert upc_map[normalized] == issue_id

    rows = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == normalized)).all()
    assert len(rows) == 1


def test_insert_normalizes_before_lookup(session: Session) -> None:
    pub = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(pub)
    session.commit()
    series = CatalogSeries(name="X-Men", normalized_name="x men", publisher_id=int(pub.id))
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
    issue_id = int(issue.id)

    normalized = "07148601984816"
    session.add(
        CatalogUpc(
            upc=normalized,
            normalized_upc=normalized,
            issue_id=issue_id,
            source=GCD_SOURCE,
            confidence=Decimal("1.0"),
            barcode_type="upc",
        )
    )
    session.commit()

    learned: set[str] = set()
    upc_map: dict[str, int] = {}
    raw = normalized
    upc_id, created = insert_catalog_upc_if_absent(
        session,
        raw_upc=raw,
        issue_id=issue_id,
        variant_id=None,
        learned=learned,
        upc_map=upc_map,
    )
    assert created is False
    assert upc_id is not None
    assert len(session.exec(select(CatalogUpc)).all()) == 1
