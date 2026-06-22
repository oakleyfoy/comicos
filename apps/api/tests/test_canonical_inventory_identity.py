"""Canonical inventory identity resolver: catalog -> legacy -> metadata key."""

from __future__ import annotations

from decimal import Decimal

from sqlmodel import Session

from app.models import (
    ComicIssue,
    ComicTitle,
    InventoryCopy,
    Publisher,
    Variant,
)
from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.services.canonical_inventory_identity_service import resolve_identity_for_copy


def _copy(session: Session, **fields) -> InventoryCopy:
    copy = InventoryCopy(user_id=1, copy_number=1, acquisition_cost=Decimal("0"), **fields)
    session.add(copy)
    session.commit()
    session.refresh(copy)
    return copy


def test_resolves_from_catalog(session: Session) -> None:
    pub = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(pub)
    session.flush()
    ser = CatalogSeries(publisher_id=pub.id, name="Amazing Spider-Man", normalized_name="amazing spider-man")
    session.add(ser)
    session.flush()
    iss = CatalogIssue(series_id=ser.id, publisher_id=pub.id, issue_number="300", normalized_issue_number="300")
    session.add(iss)
    session.commit()

    copy = _copy(session, catalog_issue_id=int(iss.id))
    identity = resolve_identity_for_copy(session, copy)
    assert identity.source == "catalog"
    assert identity.title == "Amazing Spider-Man"
    assert identity.issue_number == "300"
    assert identity.publisher == "Marvel"
    assert identity.catalog_issue_id == int(iss.id)


def test_resolves_from_legacy_spine(session: Session) -> None:
    pub = Publisher(name="DC")
    session.add(pub)
    session.flush()
    title = ComicTitle(publisher_id=pub.id, name="Batman")
    session.add(title)
    session.flush()
    issue = ComicIssue(comic_title_id=title.id, issue_number="404")
    session.add(issue)
    session.flush()
    variant = Variant(comic_issue_id=issue.id, cover_name="Cover A")
    session.add(variant)
    session.commit()

    copy = _copy(session, variant_id=int(variant.id))
    identity = resolve_identity_for_copy(session, copy)
    assert identity.source == "legacy"
    assert identity.title == "Batman"
    assert identity.issue_number == "404"
    assert identity.publisher == "DC"
    assert identity.catalog_issue_id is None


def test_resolves_from_metadata_key(session: Session) -> None:
    copy = _copy(session, metadata_identity_key="Image|Saga|12|Cover A")
    identity = resolve_identity_for_copy(session, copy)
    assert identity.source == "metadata"
    assert identity.title == "Saga"
    assert identity.issue_number == "12"
    assert identity.publisher == "Image"


def test_unknown_when_no_identity(session: Session) -> None:
    copy = _copy(session)
    identity = resolve_identity_for_copy(session, copy)
    assert identity.source == "unknown"
    assert identity.title == "Unknown"
