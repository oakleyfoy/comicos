from datetime import date

from sqlmodel import Session

from app.models import User
from app.models.asset_ledger import CoverImage
from app.models.external_catalog import ExternalCatalogIssue, ExternalCatalogMatch, ExternalCatalogVariant
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.import_cover_resolver import resolve_import_cover


def test_resolve_import_cover_null_safe_without_match(session: Session) -> None:
    result = resolve_import_cover(session, {"title": "Terminal", "issue_number": "1"})
    assert result.cover_image_url is None
    assert result.cover_thumbnail_url is None
    assert result.has_cover_image is False
    assert result.cover_resolution_debug is not None
    assert result.cover_resolution_debug.get("outcome") == "none"
    assert result.cover_resolution_debug.get("reason") == "no_owner_user_for_catalog_or_hydrate"


def test_resolve_import_cover_prefers_external_variant_image(session: Session) -> None:
    issue = ExternalCatalogIssue(
        source_name="locg",
        title="Terminal #1",
        publisher="Image",
        series_name="Terminal",
        issue_number="1",
        release_date=date(2026, 7, 22),
        cover_image_url="https://example.com/issue-cover.jpg",
        thumbnail_url="https://example.com/issue-thumb.jpg",
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    assert issue.id is not None

    variant = ExternalCatalogVariant(
        external_issue_id=issue.id,
        cover_label="Cover B",
        variant_name="Ryan Ottley Variant",
        artist="Ryan Ottley",
        image_url="https://example.com/variant-cover.jpg",
    )
    session.add(variant)
    session.commit()

    result = resolve_import_cover(
        session,
        {
            "title": "Terminal",
            "issue_number": "1",
            "cover_name": "Cover B Variant Ryan Ottley Cover",
            "cover_artist": "Ryan Ottley",
            "catalog_match_source": "ExternalCatalogIssue",
            "catalog_match_source_id": issue.id,
        },
    )
    assert result.cover_image_url == "https://example.com/variant-cover.jpg"
    assert result.cover_image_source == "external_catalog_variant"
    assert result.has_cover_image is True
    assert result.cover_resolution_debug is not None
    assert result.cover_resolution_debug.get("outcome") == "external_catalog_variant"


def test_resolve_import_cover_falls_back_from_release_issue_match(session: Session) -> None:
    user = User(email="cover-resolver@example.com", password_hash="x")
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

    release_issue = ReleaseIssue(
        owner_user_id=user.id,
        series_id=series.id,
        issue_number="1",
        title="Terminal #1",
        release_date=date(2026, 7, 22),
        release_status="scheduled",
    )
    session.add(release_issue)
    session.commit()
    session.refresh(release_issue)
    assert release_issue.id is not None

    external_issue = ExternalCatalogIssue(
        source_name="locg",
        title="Terminal #1",
        publisher="Image",
        series_name="Terminal",
        issue_number="1",
        release_date=date(2026, 7, 22),
        cover_image_url="https://example.com/terminal-cover.jpg",
        thumbnail_url="https://example.com/terminal-thumb.jpg",
    )
    session.add(external_issue)
    session.commit()
    session.refresh(external_issue)
    assert external_issue.id is not None

    match = ExternalCatalogMatch(
        external_issue_id=external_issue.id,
        owner_user_id=user.id,
        release_issue_id=release_issue.id,
        match_status="matched",
        match_confidence=0.98,
    )
    session.add(match)
    session.commit()

    result = resolve_import_cover(
        session,
        {
            "title": "Terminal",
            "issue_number": "1",
            "catalog_match_source": "ReleaseIssue",
            "catalog_match_source_id": release_issue.id,
        },
        owner_user_id=user.id,
    )
    assert result.cover_thumbnail_url == "https://example.com/terminal-thumb.jpg"
    assert result.cover_image_source == "external_catalog_issue"
    assert result.has_cover_image is True


def test_resolve_import_cover_picks_cover_letter_over_issue_fallback(session: Session) -> None:
    issue = ExternalCatalogIssue(
        source_name="locg",
        title="If Destruction Be Our Lot #2",
        publisher="Image",
        series_name="If Destruction Be Our Lot",
        issue_number="2",
        release_date=date(2026, 6, 17),
        cover_image_url="https://example.com/issue-default.jpg",
        thumbnail_url="https://example.com/issue-default-thumb.jpg",
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    assert issue.id is not None

    cover_a = ExternalCatalogVariant(
        external_issue_id=issue.id,
        cover_label="Cover A",
        variant_name="Regular",
        artist="Dani",
        image_url="https://example.com/cover-a.jpg",
    )
    cover_b = ExternalCatalogVariant(
        external_issue_id=issue.id,
        cover_label="Cover B",
        variant_name="Variant",
        artist="Other",
        image_url="https://example.com/cover-b.jpg",
    )
    session.add(cover_a)
    session.add(cover_b)
    session.commit()

    result_a = resolve_import_cover(
        session,
        {
            "title": "If Destruction Be Our Lot",
            "issue_number": "2",
            "cover_name": "Cover A Regular Dani Cover",
            "catalog_match_source": "ExternalCatalogIssue",
            "catalog_match_source_id": issue.id,
        },
    )
    result_b = resolve_import_cover(
        session,
        {
            "title": "If Destruction Be Our Lot",
            "issue_number": "2",
            "cover_name": "Cover B Variant Other Cover",
            "catalog_match_source": "ExternalCatalogIssue",
            "catalog_match_source_id": issue.id,
        },
    )
    assert result_a.cover_image_url == "https://example.com/cover-a.jpg"
    assert result_b.cover_image_url == "https://example.com/cover-b.jpg"


def test_resolve_import_cover_rejects_stale_external_issue_for_wrong_issue_number(
    session: Session,
) -> None:
    user = User(email="cover-stale@example.com", password_hash="x")
    session.add(user)
    session.commit()
    session.refresh(user)
    assert user.id is not None

    issue_17 = ExternalCatalogIssue(
        source_name="locg",
        title="Absolute Batman #17",
        publisher="DC",
        series_name="Absolute Batman",
        issue_number="17",
        release_date=date(2026, 6, 17),
        cover_image_url="https://example.com/batman-17.jpg",
    )
    issue_18 = ExternalCatalogIssue(
        source_name="locg",
        title="Absolute Batman #18",
        publisher="DC",
        series_name="Absolute Batman",
        issue_number="18",
        release_date=date(2026, 7, 15),
        cover_image_url="https://example.com/batman-18.jpg",
    )
    session.add(issue_17)
    session.add(issue_18)
    session.commit()
    session.refresh(issue_17)
    session.refresh(issue_18)
    assert issue_17.id is not None and issue_18.id is not None

    stale = resolve_import_cover(
        session,
        {
            "publisher": "DC",
            "title": "Absolute Batman",
            "issue_number": "18",
            "cover_name": "Cover A",
            "catalog_match_source": "ExternalCatalogIssue",
            "catalog_match_source_id": issue_17.id,
        },
        owner_user_id=user.id,
    )
    assert stale.cover_image_url == "https://example.com/batman-18.jpg"
    assert stale.cover_image_source == "external_catalog_issue"


def test_resolve_import_cover_uses_draft_cover_fallback(session: Session) -> None:
    cover = CoverImage(
        draft_import_id=42,
        source_type="upload",
        original_filename="cover.jpg",
        storage_path="cover-images/test/cover.jpg",
        mime_type="image/jpeg",
        sha256_hash="abc123",
    )
    session.add(cover)
    session.commit()
    session.refresh(cover)
    assert cover.id is not None

    result = resolve_import_cover(
        session,
        {"title": "Fallback Test", "issue_number": "1"},
        draft_import_id=42,
    )
    assert result.cover_image_source == "draft_cover_image"
    assert result.cover_image_url is not None
    assert result.has_cover_image is True


def test_resolve_import_cover_prefers_line_upload_over_draft_fallback(session: Session) -> None:
    cover = CoverImage(
        draft_import_id=99,
        source_type="upload",
        original_filename="scan.jpg",
        storage_path="cover-images/test/scan.jpg",
        mime_type="image/jpeg",
        sha256_hash="scanhash",
    )
    session.add(cover)
    session.commit()
    session.refresh(cover)
    assert cover.id is not None

    result = resolve_import_cover(
        session,
        {
            "title": "Line Scan",
            "issue_number": "1",
            "import_line_cover_image_id": cover.id,
        },
        draft_import_id=99,
        allow_draft_cover_fallback=False,
    )
    assert result.cover_image_source == "draft_cover_image"
    assert result.cover_image_source_id == cover.id
    assert result.has_cover_image is True


def test_resolve_import_cover_prefers_line_upload_over_draft_fallback(session: Session) -> None:
    cover = CoverImage(
        draft_import_id=99,
        source_type="upload",
        original_filename="scan.jpg",
        storage_path="cover-images/test/scan.jpg",
        mime_type="image/jpeg",
        sha256_hash="scanhash",
    )
    session.add(cover)
    session.commit()
    session.refresh(cover)
    assert cover.id is not None

    result = resolve_import_cover(
        session,
        {
            "title": "Line Scan",
            "issue_number": "1",
            "import_line_cover_image_id": cover.id,
        },
        draft_import_id=99,
        allow_draft_cover_fallback=False,
    )
    assert result.cover_image_source == "draft_cover_image"
    assert result.cover_image_source_id == cover.id
    assert result.has_cover_image is True
