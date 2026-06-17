"""P100-12 photo import candidate matching tests."""

from __future__ import annotations

from sqlmodel import Session

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.models.photo_import import PhotoImportDetectedBook
from app.services.catalog_ingestion_service import normalize_issue_number, normalize_series_name
from app.services.photo_import_candidate_service import (
    PhotoImportMatchInput,
    build_match_input_from_detection,
    generate_scored_candidates,
    refresh_candidates_for_detection,
)


def _seed_series_issue(
    session: Session,
    *,
    publisher_name: str,
    series_name: str,
    issue_number: str,
) -> CatalogIssue:
    pub = CatalogPublisher(name=publisher_name, normalized_name=normalize_series_name(publisher_name))
    session.add(pub)
    session.flush()
    series = CatalogSeries(
        name=series_name,
        normalized_name=normalize_series_name(series_name),
        publisher_id=pub.id,
        start_year=1990,
    )
    session.add(series)
    session.flush()
    issue = CatalogIssue(
        series_id=int(series.id),
        publisher_id=int(pub.id),
        issue_number=issue_number,
        normalized_issue_number=normalize_issue_number(issue_number),
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    return issue


def test_exact_series_and_issue_match(session: Session) -> None:
    target = _seed_series_issue(session, publisher_name="Marvel", series_name="X-Factor", issue_number="104")
    inp = PhotoImportMatchInput(series_guess="X-Factor", issue_number_guess="104", publisher_guess="Marvel")
    scored, _terms = generate_scored_candidates(session, inp)
    assert scored, "expected candidates for X-Factor #104"
    assert int(scored[0].issue.id) == int(target.id)
    assert scored[0].matched_on in {"exact_series_issue_publisher", "exact_series_issue"}


def test_alternate_title_match(session: Session) -> None:
    target = _seed_series_issue(
        session,
        publisher_name="Marvel",
        series_name="Captain America: The Initiative",
        issue_number="1",
    )
    inp = PhotoImportMatchInput(
        series_guess="Captain America",
        issue_number_guess="1",
        alternate_titles=["Captain America: The Initiative"],
    )
    scored, _terms = generate_scored_candidates(session, inp)
    assert any(int(row.issue.id) == int(target.id) for row in scored)


def test_visible_issue_text_when_guess_null(session: Session) -> None:
    target = _seed_series_issue(session, publisher_name="Marvel", series_name="Foolkiller", issue_number="4")
    det = PhotoImportDetectedBook(
        session_id=1,
        image_id=1,
        user_id=1,
        ai_series="Foolkiller",
        ai_issue_number=None,
        ai_visible_issue_text="4",
    )
    inp = build_match_input_from_detection(det)
    assert inp.issue_number_guess == "4"
    scored, _terms = generate_scored_candidates(session, inp)
    assert scored
    assert int(scored[0].issue.id) == int(target.id)


def test_refresh_persists_candidates(session: Session) -> None:
    _seed_series_issue(session, publisher_name="Image", series_name="Babe", issue_number="3")
    det = PhotoImportDetectedBook(
        session_id=1,
        image_id=1,
        user_id=1,
        ai_series="Babe",
        ai_issue_number="3",
        candidate_count=0,
    )
    session.add(det)
    session.commit()
    session.refresh(det)
    refresh_candidates_for_detection(session, detected_book_id=int(det.id))
    session.refresh(det)
    assert det.candidate_count >= 1
    assert det.selected_catalog_issue_id is None
