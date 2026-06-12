"""Unit tests for the inventory display-metadata resolver source-priority chains."""

from __future__ import annotations

from datetime import date

from app.models.release_intelligence import ReleaseIssue
from app.services.inventory_display_metadata import (
    classify_cover_source,
    compute_release_status,
    resolve_inventory_display_metadata,
)

TODAY = date(2026, 6, 12)


def _release_issue(*, release_date: date | None, foc_date: date | None) -> ReleaseIssue:
    return ReleaseIssue(
        owner_user_id=1,
        series_id=1,
        issue_number="1",
        title="Test",
        release_date=release_date,
        foc_date=foc_date,
        release_status="unknown",
    )


def test_cover_source_priority_catalog_wins() -> None:
    assert (
        classify_cover_source(has_catalog_cover=True, source_image_url="https://x/y.jpg")
        == "catalog_cover"
    )


def test_cover_source_priority_remote_then_local_then_placeholder() -> None:
    assert classify_cover_source(has_catalog_cover=False, source_image_url="https://x/y.jpg") == "retailer_remote"
    assert classify_cover_source(has_catalog_cover=False, source_image_url="data/uploads/cover.png") == "local_saved_html"
    assert classify_cover_source(has_catalog_cover=False, source_image_url=None) == "placeholder"


def test_compute_release_status_from_date() -> None:
    assert compute_release_status(release_date=date(2026, 1, 1), today=TODAY) == "released"
    assert compute_release_status(release_date=date(2026, 12, 1), today=TODAY) == "not_released_yet"
    assert compute_release_status(release_date=None, today=TODAY) == "unknown"


def test_matched_item_uses_catalog_cover_and_copy_dates() -> None:
    metadata = resolve_inventory_display_metadata(
        catalog_cover_fetch_path="/files/cover-images/42",
        source_image_url="https://midtown/img.jpg",
        copy_release_date=date(2026, 5, 1),
        copy_release_status="unknown",
        order_item_foc_date=date(2026, 4, 1),
        catalog_match_id=99,
        enrichment_status="matched",
        today=TODAY,
    )
    assert metadata.cover_image_url == "/files/cover-images/42"
    assert metadata.cover_source == "catalog_cover"
    assert metadata.release_date == date(2026, 5, 1)
    assert metadata.foc_date == date(2026, 4, 1)
    assert metadata.release_status == "released"
    assert metadata.needs_catalog_review is False


def test_release_and_foc_fall_back_to_release_issue() -> None:
    metadata = resolve_inventory_display_metadata(
        catalog_cover_fetch_path=None,
        source_image_url=None,
        copy_release_date=None,
        copy_release_status="unknown",
        order_item_foc_date=None,
        catalog_match_id=7,
        enrichment_status="matched",
        release_issue=_release_issue(release_date=date(2026, 3, 1), foc_date=date(2026, 2, 1)),
        today=TODAY,
    )
    assert metadata.release_date == date(2026, 3, 1)
    assert metadata.foc_date == date(2026, 2, 1)
    assert metadata.release_status == "released"
    # Catalog matched + dates resolved -> not flagged for review.
    assert metadata.needs_catalog_review is False


def test_unmatched_item_uses_source_image_and_needs_review() -> None:
    metadata = resolve_inventory_display_metadata(
        catalog_cover_fetch_path=None,
        source_image_url="https://midtown/cover.jpg",
        copy_release_date=None,
        copy_release_status="unknown",
        order_item_foc_date=None,
        catalog_match_id=None,
        enrichment_status="needs_review",
        today=TODAY,
    )
    assert metadata.cover_image_url == "https://midtown/cover.jpg"
    assert metadata.cover_source == "retailer_remote"
    assert metadata.release_date is None
    assert metadata.foc_date is None
    assert metadata.release_status == "unknown"
    assert metadata.needs_catalog_review is True


def test_local_saved_html_only_marks_cover_source() -> None:
    metadata = resolve_inventory_display_metadata(
        catalog_cover_fetch_path=None,
        source_image_url="data/retailer_html_upload/4272232/cover.png",
        copy_release_date=None,
        copy_release_status="unknown",
        order_item_foc_date=None,
        catalog_match_id=None,
        enrichment_status=None,
        today=TODAY,
    )
    assert metadata.cover_source == "local_saved_html"
    assert metadata.needs_catalog_review is True


def test_explicit_stored_release_status_preserved_without_date() -> None:
    metadata = resolve_inventory_display_metadata(
        catalog_cover_fetch_path=None,
        source_image_url=None,
        copy_release_date=None,
        copy_release_status="not_released_yet",
        order_item_foc_date=None,
        catalog_match_id=12,
        enrichment_status="matched",
        today=TODAY,
    )
    assert metadata.release_status == "not_released_yet"
