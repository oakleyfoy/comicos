"""Catalog match must not override GPT series/issue with a conflicting barcode hit."""

from __future__ import annotations

from sqlmodel import Session

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc
from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.services.photo_import_catalog_match_service import match_read_to_catalog


def _seed_issue(
    session: Session,
    *,
    issue_id: int,
    series_name: str,
    issue_number: str,
) -> CatalogIssue:
    publisher = CatalogPublisher(name="Vertigo", normalized_name="vertigo")
    session.add(publisher)
    session.flush()
    series = CatalogSeries(
        name=series_name,
        normalized_name=series_name.lower(),
        publisher_id=publisher.id,
    )
    session.add(series)
    session.flush()
    issue = CatalogIssue(
        id=issue_id,
        series_id=series.id,
        publisher_id=publisher.id,
        issue_number=issue_number,
        normalized_issue_number=issue_number,
    )
    session.add(issue)
    session.flush()
    return issue


def test_barcode_demoted_when_it_conflicts_with_gpt_vision(session: Session) -> None:
    wrong = _seed_issue(session, issue_id=7001, series_name="Beautiful Stories for Ugly Children", issue_number="11")
    right = _seed_issue(session, issue_id=7002, series_name="Preacher", issue_number="58")
    session.add(
        CatalogUpc(
            issue_id=wrong.id,
            upc="76194120401705811",
            normalized_upc="76194120401705811",
            source="test",
        )
    )
    session.commit()

    read = PhotoImportVisionRead(
        session_id=1,
        image_id=1,
        publisher="Vertigo",
        series="Preacher",
        issue_number="58",
        issue_title="",
        barcode="761941204017 05811",
        confidence=0.6,
        reasoning="GPT says Preacher 58",
        raw_response={},
    )
    session.add(read)
    session.flush()

    match = match_read_to_catalog(session, read)
    assert match.catalog_issue_id == right.id
    assert match.method == "text"
    assert any(alt.catalog_issue_id == wrong.id for alt in match.alternates)
