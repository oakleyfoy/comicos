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


def test_captain_america_subtitle_not_issue_number(session: Session) -> None:
    _seed_series_issue(
        session,
        publisher_name="Marvel",
        series_name="Captain America: The Initiative",
        issue_number="1",
    )
    det = PhotoImportDetectedBook(
        session_id=1,
        image_id=1,
        user_id=1,
        ai_series="Captain America",
        ai_issue_number=None,
        ai_subtitle_guess="THE INITIATIVE",
        ai_publisher="Marvel",
    )
    inp = build_match_input_from_detection(det)
    assert inp.issue_number_guess == ""
    scored, _terms = generate_scored_candidates(session, inp)
    assert scored
    assert scored[0].matched_on in {
        "visible_text_no_issue",
        "series_publisher_no_issue",
        "series_no_issue",
        "fuzzy_series_publisher_no_issue",
        "fuzzy_series_no_issue",
    }
    assert scored[0].match_score <= 72.0


def test_babe_subtitle_not_issue_number(session: Session) -> None:
    _seed_series_issue(session, publisher_name="Image", series_name="Babe", issue_number="3")
    _seed_series_issue(session, publisher_name="Image", series_name="Babe", issue_number="4")
    det = PhotoImportDetectedBook(
        session_id=1,
        image_id=1,
        user_id=1,
        ai_series="Babe",
        ai_issue_number=None,
        ai_subtitle_guess="INTRODUCING THE SPIRITS",
    )
    scored, _ = generate_scored_candidates(session, build_match_input_from_detection(det))
    assert scored
    assert all(row.match_score <= 65.0 for row in scored)


def test_foolkiller_series_level_candidates(session: Session) -> None:
    pub = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(pub)
    session.flush()
    series = CatalogSeries(
        name="Foolkiller",
        normalized_name=normalize_series_name("Foolkiller"),
        publisher_id=pub.id,
        start_year=1990,
    )
    session.add(series)
    session.flush()
    for num in ("1", "2", "3", "4"):
        session.add(
            CatalogIssue(
                series_id=int(series.id),
                publisher_id=int(pub.id),
                issue_number=num,
                normalized_issue_number=normalize_issue_number(num),
            )
        )
    session.commit()

    det = PhotoImportDetectedBook(
        session_id=1,
        image_id=1,
        user_id=1,
        ai_series="Foolkiller",
        ai_visible_title_text="FOOLKILLER",
        ai_issue_number=None,
    )
    scored, _ = generate_scored_candidates(session, build_match_input_from_detection(det))
    assert len(scored) >= 2
    assert all(row.series.name == "Foolkiller" for row in scored)


def test_apply_sanitization_on_ai_book_entry() -> None:
    from app.services.photo_import_ai_recognition_service import _normalize_book_entry

    book = _normalize_book_entry({"issue_number_guess": "THE INITIATIVE", "series_guess": "Captain America"})
    assert book["issue_number_guess"] is None
    assert "INITIATIVE" in str(book["subtitle_guess"]).upper()


# ---- P100-13D: unknown-issue fallback, aliases, subtitle ranking ----


def test_foolkiller_unknown_issue_returns_candidates(session: Session) -> None:
    pub = CatalogPublisher(name="Marvel Comics", normalized_name=normalize_series_name("Marvel Comics"))
    session.add(pub)
    session.flush()
    series = CatalogSeries(
        name="Foolkiller",
        normalized_name=normalize_series_name("Foolkiller"),
        publisher_id=pub.id,
        start_year=1990,
    )
    session.add(series)
    session.flush()
    for num in ("1", "2", "3", "4"):
        session.add(
            CatalogIssue(
                series_id=int(series.id),
                publisher_id=int(pub.id),
                issue_number=num,
                normalized_issue_number=normalize_issue_number(num),
            )
        )
    session.commit()

    det = PhotoImportDetectedBook(
        session_id=1,
        image_id=1,
        user_id=1,
        ai_series="Foolkiller",
        ai_publisher="Marvel Comics",
        ai_issue_number=None,
    )
    scored, _ = generate_scored_candidates(session, build_match_input_from_detection(det))
    assert scored, "Foolkiller (issue unknown) must return candidates, not Needs match"
    assert all(row.series.name == "Foolkiller" for row in scored)


def test_captain_america_initiative_unknown_issue_returns_candidates(session: Session) -> None:
    _seed_series_issue(
        session,
        publisher_name="Marvel",
        series_name="Captain America: The Initiative",
        issue_number="1",
    )
    det = PhotoImportDetectedBook(
        session_id=1,
        image_id=1,
        user_id=1,
        ai_series="Captain America",
        ai_publisher="Marvel",
        ai_issue_number=None,
        ai_subtitle_guess="The Initiative",
    )
    scored, _ = generate_scored_candidates(session, build_match_input_from_detection(det))
    assert scored, "Captain America + The Initiative (issue unknown) must return candidates"


def test_babes_alias_falls_back_to_babe(session: Session) -> None:
    _seed_series_issue(session, publisher_name="Image", series_name="Babe", issue_number="1")
    _seed_series_issue(session, publisher_name="Image", series_name="Babe", issue_number="2")
    det = PhotoImportDetectedBook(
        session_id=1,
        image_id=1,
        user_id=1,
        ai_series="Babes",
        ai_publisher="Image Comics",
        ai_issue_number=None,
    )
    scored, _ = generate_scored_candidates(session, build_match_input_from_detection(det))
    assert scored, "Babes should alias to Babe and return candidates"
    assert any(row.series.name == "Babe" for row in scored)


def test_xmen_evil_subtitle_does_not_autoselect(session: Session) -> None:
    pub = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(pub)
    session.flush()
    series = CatalogSeries(
        name="X-Men",
        normalized_name=normalize_series_name("X-Men"),
        publisher_id=pub.id,
        start_year=1991,
    )
    session.add(series)
    session.flush()
    for num in ("205", "206", "207"):
        session.add(
            CatalogIssue(
                series_id=int(series.id),
                publisher_id=int(pub.id),
                issue_number=num,
                normalized_issue_number=normalize_issue_number(num),
            )
        )
    session.commit()

    det = PhotoImportDetectedBook(
        session_id=1,
        image_id=1,
        user_id=1,
        ai_series="X-Men",
        ai_publisher="Marvel",
        ai_issue_number=None,
        ai_subtitle_guess="Evil",
    )
    scored, _ = generate_scored_candidates(session, build_match_input_from_detection(det))
    assert scored, "X-Men should still show candidates"
    # Weak single-word subtitle must not boost any specific issue to high confidence.
    assert scored[0].match_score < 70.0
    assert all(row.matched_on != "visible_text_no_issue" for row in scored)


def test_unknown_issue_with_candidates_is_needs_selection(session: Session) -> None:
    _seed_series_issue(session, publisher_name="Marvel", series_name="Foolkiller", issue_number="1")
    det = PhotoImportDetectedBook(
        session_id=1,
        image_id=1,
        user_id=1,
        ai_series="Foolkiller",
        ai_publisher="Marvel",
        ai_issue_number=None,
    )
    session.add(det)
    session.commit()
    session.refresh(det)
    refresh_candidates_for_detection(session, detected_book_id=int(det.id))

    from app.services.photo_import_detection_service import detection_to_read

    session.refresh(det)
    read = detection_to_read(session, det)
    assert read.candidate_count >= 1
    assert read.review_status == "needs_selection"
    assert read.needs_match is False


def test_unknown_issue_without_candidates_is_needs_match(session: Session) -> None:
    det = PhotoImportDetectedBook(
        session_id=1,
        image_id=1,
        user_id=1,
        ai_series="Zzz Nonexistent Series Title",
        ai_issue_number=None,
    )
    session.add(det)
    session.commit()
    session.refresh(det)
    refresh_candidates_for_detection(session, detected_book_id=int(det.id))

    from app.services.photo_import_detection_service import detection_to_read

    session.refresh(det)
    read = detection_to_read(session, det)
    assert read.candidate_count == 0
    assert read.review_status == "needs_match"
    assert read.needs_match is True


def test_weak_fuzzy_match_not_bulk_confirmable(session: Session) -> None:
    _seed_series_issue(session, publisher_name="Marvel", series_name="Foolkiller", issue_number="1")
    det = PhotoImportDetectedBook(
        session_id=1,
        image_id=1,
        user_id=1,
        ai_series="Foolkiller",
        ai_publisher="Marvel",
        ai_issue_number=None,
        ai_confidence=0.95,
    )
    session.add(det)
    session.commit()
    session.refresh(det)
    refresh_candidates_for_detection(session, detected_book_id=int(det.id))
    session.refresh(det)

    from app.services.photo_import_detection_service import _best_candidate
    from app.services.photo_import_review_rules import qualifies_for_bulk_high_confidence_confirm

    best = _best_candidate(session, int(det.id))
    # Simulate the user having selected the candidate (so can_confirm gate passes) before bulk check.
    det.selected_catalog_issue_id = best.catalog_issue_id if best else None
    assert qualifies_for_bulk_high_confidence_confirm(det, best_candidate=best) is False
