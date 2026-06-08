from datetime import date

from sqlmodel import Session

from app.models import User
from app.models.external_catalog import ExternalCatalogIssue
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.import_catalog_resolution_service import (
    normalize_import_publisher_key,
    normalize_import_title,
    resolve_import_catalog_match,
    score_catalog_candidate,
    CatalogCandidateRow,
    _pick_resolution,
    ScoredCatalogCandidate,
)
from app.services.import_release_lifecycle_service import enrich_import_item_lifecycle


def test_publisher_alias_image_comics() -> None:
    assert normalize_import_publisher_key("Image Comics") == "image"


def test_publisher_alias_dark_horse() -> None:
    assert normalize_import_publisher_key("Dark Horse Comics") == "dark horse"


def test_publisher_alias_boom() -> None:
    assert normalize_import_publisher_key("Boom! Studios") == "boom"


def test_title_normalization_shaolin_cowboy() -> None:
    left = normalize_import_title("Shaolin Cowboy Staying A.I. Live")
    right = normalize_import_title("Shaolin Cowboy: Staying A.I. Live")
    assert left == right


def test_title_normalization_terminal_volume() -> None:
    assert normalize_import_title("Terminal") == normalize_import_title("Terminal Vol 1")


def test_strong_title_issue_match_accepts_over_issue_only_ties() -> None:
    winner = CatalogCandidateRow(
        source="ExternalCatalogIssue",
        source_id=6830,
        publisher="Marvel Comics",
        title="Jeff the Land Shark",
        issue_number="1",
        release_date=date(2025, 6, 18),
    )
    tie = CatalogCandidateRow(
        source="ReleaseIssue",
        source_id=32,
        publisher="DC Comics",
        title="Animal Man",
        issue_number="1",
        release_date=date(2026, 10, 13),
    )
    scored = [
        ScoredCatalogCandidate(
            candidate=winner,
            score=62,
            reasons=["issue_number_exact", "title_overlap_good", "release_date_present"],
        ),
        ScoredCatalogCandidate(
            candidate=tie,
            score=58,
            reasons=["issue_number_exact", "publisher_alias_match", "release_date_present"],
        ),
    ]
    result = _pick_resolution(scored)
    assert result.matched is True
    assert result.source == "ExternalCatalogIssue"
    assert result.source_id == 6830


def test_ambiguous_candidates_not_auto_applied() -> None:
    candidate_a = CatalogCandidateRow(
        source="ReleaseIssue",
        source_id=1,
        publisher="Image",
        title="Terminal",
        issue_number="1",
        release_date=date(2026, 7, 22),
    )
    candidate_b = CatalogCandidateRow(
        source="ReleaseIssue",
        source_id=2,
        publisher="Image",
        title="Terminal City",
        issue_number="1",
        release_date=date(2026, 7, 22),
    )
    scored = [
        ScoredCatalogCandidate(candidate=candidate_a, score=62, reasons=["issue_number_exact"]),
        ScoredCatalogCandidate(candidate=candidate_b, score=60, reasons=["issue_number_exact"]),
    ]
    result = _pick_resolution(scored)
    assert result.matched is False
    assert result.possible_match is True
    assert result.rejected_reason == "ambiguous_candidates"
    assert len(result.top_candidates) == 2


def test_terminal_lifecycle_resolution(session: Session) -> None:
    user = User(email="terminal-res@example.com", password_hash="x")
    session.add(user)
    session.commit()
    session.refresh(user)
    assert user.id is not None

    series = ReleaseSeries(
        owner_user_id=user.id,
        publisher="Image",
        series_name="Terminal",
        series_type="ongoing",
        status="active",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    assert series.id is not None

    issue = ReleaseIssue(
        owner_user_id=user.id,
        series_id=series.id,
        issue_number="1",
        title="Terminal #1",
        release_date=date(2026, 7, 22),
        release_status="scheduled",
    )
    session.add(issue)
    session.commit()

    item = {
        "publisher": "Image Comics",
        "title": "Terminal",
        "issue_number": "1",
        "release_status": "unknown",
        "order_status": "ordered",
    }
    enriched = enrich_import_item_lifecycle(
        session,
        owner_user_id=user.id,
        item=item,
        today=date(2026, 6, 8),
    )
    assert enriched["catalog_match_matched"] is True
    assert enriched["parsed_release_date"] == "2026-07-22"
    assert enriched["release_lifecycle_status"] == "PREORDER"


def test_shaolin_cowboy_external_catalog_match(session: Session) -> None:
    user = User(email="shaolin-res@example.com", password_hash="x")
    session.add(user)
    session.commit()
    session.refresh(user)
    assert user.id is not None

    row = ExternalCatalogIssue(
        source_name="locg",
        title="Shaolin Cowboy: Staying A.I. Live #1",
        publisher="Dark Horse",
        series_name="Shaolin Cowboy: Staying A.I. Live",
        issue_number="1",
        release_date=date(2026, 7, 1),
    )
    session.add(row)
    session.commit()

    resolution = resolve_import_catalog_match(
        session,
        owner_user_id=user.id,
        item={
            "publisher": "Dark Horse",
            "title": "Shaolin Cowboy Staying A.I. Live",
            "issue_number": "1",
        },
    )
    assert resolution.matched is True
    assert resolution.release_date == date(2026, 7, 1)

    enriched = enrich_import_item_lifecycle(
        session,
        owner_user_id=user.id,
        item={
            "publisher": "Dark Horse",
            "title": "Shaolin Cowboy Staying A.I. Live",
            "issue_number": "1",
            "order_status": "ordered",
        },
        today=date(2026, 6, 8),
    )
    assert enriched["release_lifecycle_status"] == "PREORDER"
    assert enriched["catalog_release_source_text"] == "Verified release date from catalog"


def test_score_terminal_candidate() -> None:
    scored = score_catalog_candidate(
        input_publisher="Image Comics",
        input_title="Terminal",
        input_issue_number="1",
        input_cover_name=None,
        input_cover_artist=None,
        candidate=CatalogCandidateRow(
            source="ReleaseIssue",
            source_id=9,
            publisher="Image",
            title="Terminal Vol 1",
            issue_number="1",
            release_date=date(2026, 7, 22),
        ),
    )
    assert scored.score >= 70


def test_jeff_the_land_shark_superstar_issue_1_resolves(session: Session) -> None:
    user = User(email="jeff-land-shark-1@example.com", password_hash="x")
    session.add(user)
    session.commit()
    session.refresh(user)
    assert user.id is not None

    row = ExternalCatalogIssue(
        source_name="locg",
        title="Jeff the Land Shark #1",
        publisher="Marvel Comics",
        series_name="Jeff the Land Shark",
        issue_number="1",
        release_date=date(2025, 6, 18),
        cover_image_url="https://example.com/jeff-1.jpg",
    )
    session.add(row)
    session.commit()

    resolution = resolve_import_catalog_match(
        session,
        owner_user_id=user.id,
        item={
            "publisher": None,
            "title": "Jeff The Land Shark Superstar",
            "issue_number": "1",
            "cover_name": "Cover A Regular Gurihiru Cover",
        },
    )
    assert resolution.matched is True
    assert resolution.source == "ExternalCatalogIssue"
    assert resolution.release_date == date(2025, 6, 18)
    assert "Jeff" in (resolution.series_title or "")

    enriched = enrich_import_item_lifecycle(
        session,
        owner_user_id=user.id,
        item={
            "publisher": None,
            "title": "Jeff The Land Shark Superstar",
            "issue_number": "1",
            "release_status": "unknown",
            "order_status": "ordered",
        },
        today=date(2026, 6, 8),
    )
    assert enriched["catalog_match_matched"] is True
    assert enriched["release_lifecycle_status"] in {"RELEASED_NOT_RECEIVED", "OVERDUE"}


def test_jeff_the_land_shark_superstar_issue_2_resolves(session: Session) -> None:
    user = User(email="jeff-land-shark-2@example.com", password_hash="x")
    session.add(user)
    session.commit()
    session.refresh(user)
    assert user.id is not None

    row = ExternalCatalogIssue(
        source_name="locg",
        title="Jeff the Land Shark #2",
        publisher="Marvel Comics",
        series_name="Jeff the Land Shark",
        issue_number="2",
        release_date=date(2025, 7, 23),
        cover_image_url="https://example.com/jeff-2.jpg",
    )
    session.add(row)
    session.commit()

    resolution = resolve_import_catalog_match(
        session,
        owner_user_id=user.id,
        item={
            "publisher": "DC",
            "title": "Jeff The Land Shark Superstar",
            "issue_number": "2",
        },
    )
    assert resolution.matched is True
    assert resolution.source == "ExternalCatalogIssue"
    assert resolution.release_date == date(2025, 7, 23)

    enriched = enrich_import_item_lifecycle(
        session,
        owner_user_id=user.id,
        item={
            "publisher": "DC",
            "title": "Jeff The Land Shark Superstar",
            "issue_number": "2",
            "release_status": "unknown",
        },
        today=date(2026, 6, 8),
    )
    assert enriched["catalog_match_matched"] is True
    assert enriched["parsed_release_date"] == "2025-07-23"
