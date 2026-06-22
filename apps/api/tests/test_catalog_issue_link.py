"""catalog_issue_link_service: barcode/UPC and text resolution to catalog_issue."""

from __future__ import annotations

from sqlmodel import Session

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc
from app.services.catalog_issue_link_service import resolve_catalog_issue_link


def _seed_issue(session: Session) -> CatalogIssue:
    pub = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(pub)
    session.flush()
    ser = CatalogSeries(publisher_id=pub.id, name="Amazing Spider-Man", normalized_name="amazing spider-man")
    session.add(ser)
    session.flush()
    iss = CatalogIssue(series_id=ser.id, publisher_id=pub.id, issue_number="300", normalized_issue_number="300")
    session.add(iss)
    session.commit()
    session.refresh(iss)
    return iss


def test_resolves_by_text(session: Session) -> None:
    iss = _seed_issue(session)
    result = resolve_catalog_issue_link(
        session, series="Amazing Spider-Man", issue_number="300", publisher="Marvel"
    )
    assert result.catalog_issue_id == int(iss.id)
    assert result.method == "text"


def test_resolves_by_upc(session: Session) -> None:
    iss = _seed_issue(session)
    session.add(
        CatalogUpc(issue_id=int(iss.id), upc="759606043879", normalized_upc="759606043879", source="test")
    )
    session.commit()
    result = resolve_catalog_issue_link(session, barcode="7 59606 04387 9")
    assert result.catalog_issue_id == int(iss.id)
    assert result.method == "upc"


def test_no_match_when_issue_mismatch(session: Session) -> None:
    _seed_issue(session)
    result = resolve_catalog_issue_link(
        session, series="Amazing Spider-Man", issue_number="999", publisher="Marvel"
    )
    assert result.catalog_issue_id is None
    assert result.method == "none"


def test_no_match_when_empty(session: Session) -> None:
    _seed_issue(session)
    result = resolve_catalog_issue_link(session)
    assert result.catalog_issue_id is None
