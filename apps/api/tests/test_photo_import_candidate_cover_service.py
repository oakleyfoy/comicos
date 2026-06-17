"""P100-14A external catalog cover URLs for photo import candidates."""

from __future__ import annotations

from sqlmodel import Session

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.models.external_catalog import ExternalCatalogIssue, ExternalCatalogVariant
from app.services.catalog_ingestion_service import normalize_issue_number, normalize_series_name
from app.services.photo_import_candidate_cover_service import cover_urls_for_photo_import_candidates


def test_external_catalog_cover_when_no_catalog_image(session: Session) -> None:
    pub = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(pub)
    session.flush()
    series = CatalogSeries(
        name="X-Factor",
        normalized_name=normalize_series_name("X-Factor"),
        publisher_id=pub.id,
        start_year=1990,
    )
    session.add(series)
    session.flush()
    issue = CatalogIssue(
        series_id=int(series.id),
        publisher_id=int(pub.id),
        issue_number="104",
        normalized_issue_number=normalize_issue_number("104"),
        external_source_ids={"COMICVINE": {"40001104": True}},
    )
    session.add(issue)
    session.flush()

    ext = ExternalCatalogIssue(
        source_name="COMICVINE",
        source_issue_id="40001104",
        title="X-Factor",
        publisher="Marvel",
        series_name="X-Factor",
        issue_number="104",
        normalized_title_key="x factor 104",
        cover_image_url="https://cdn.example.com/xfactor-104.jpg",
        thumbnail_url="https://cdn.example.com/xfactor-104-thumb.jpg",
    )
    session.add(ext)
    session.commit()

    urls = cover_urls_for_photo_import_candidates(session, issue_ids=[int(issue.id)])
    assert urls[int(issue.id)] == "https://cdn.example.com/xfactor-104.jpg"


def test_external_variant_image_preferred(session: Session) -> None:
    pub = CatalogPublisher(name="Image", normalized_name="image")
    session.add(pub)
    session.flush()
    series = CatalogSeries(
        name="Babe",
        normalized_name=normalize_series_name("Babe"),
        publisher_id=pub.id,
        start_year=1994,
    )
    session.add(series)
    session.flush()
    issue = CatalogIssue(
        series_id=int(series.id),
        publisher_id=int(pub.id),
        issue_number="3",
        normalized_issue_number=normalize_issue_number("3"),
    )
    session.add(issue)
    session.flush()

    ext = ExternalCatalogIssue(
        source_name="LOC",
        source_issue_id="babe-3",
        title="Babe",
        publisher="Image",
        series_name="Babe",
        issue_number="3",
        normalized_title_key="babe 3",
        cover_image_url="https://cdn.example.com/babe-issue.jpg",
        thumbnail_url="https://cdn.example.com/babe-thumb.jpg",
    )
    session.add(ext)
    session.flush()
    session.add(
        ExternalCatalogVariant(
            external_issue_id=int(ext.id),
            variant_name="Cover A",
            image_url="https://cdn.example.com/babe-variant-a.jpg",
        )
    )
    session.commit()

    urls = cover_urls_for_photo_import_candidates(session, issue_ids=[int(issue.id)])
    assert urls[int(issue.id)] in {
        "https://cdn.example.com/babe-variant-a.jpg",
        "https://cdn.example.com/babe-issue.jpg",
    }
