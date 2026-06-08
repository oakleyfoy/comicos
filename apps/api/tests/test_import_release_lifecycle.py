from datetime import date

from app.services.import_release_lifecycle_service import (
    compute_import_release_lifecycle,
    enrich_import_item_lifecycle,
    resolve_best_release_date,
)


def test_future_release_date_becomes_preorder() -> None:
    lifecycle = compute_import_release_lifecycle(
        best_release_date=date(2026, 6, 17),
        today=date(2026, 6, 8),
        order_status="preordered",
    )
    assert lifecycle["release_lifecycle_status"] == "PREORDER"
    assert lifecycle["is_preorder"] is True
    assert lifecycle["release_status"] == "not_released_yet"
    assert lifecycle["days_until_release"] == 9
    assert lifecycle["lifecycle_sort_bucket"] == 10
    assert lifecycle["lifecycle_display_label"] == "Upcoming Release"


def test_past_release_date_not_received() -> None:
    lifecycle = compute_import_release_lifecycle(
        best_release_date=date(2026, 6, 1),
        today=date(2026, 6, 8),
        order_status="ordered",
    )
    assert lifecycle["release_lifecycle_status"] == "RELEASED_NOT_RECEIVED"
    assert lifecycle["is_released_not_received"] is True


def test_overdue_after_grace_period() -> None:
    lifecycle = compute_import_release_lifecycle(
        best_release_date=date(2026, 5, 1),
        today=date(2026, 6, 8),
        order_status="ordered",
    )
    assert lifecycle["release_lifecycle_status"] == "OVERDUE"
    assert lifecycle["is_overdue"] is True
    assert lifecycle["lifecycle_display_label"] == "Possibly Missing"


def test_received_item() -> None:
    lifecycle = compute_import_release_lifecycle(
        best_release_date=date(2026, 5, 1),
        today=date(2026, 6, 8),
        order_status="received",
    )
    assert lifecycle["release_lifecycle_status"] == "RECEIVED"


def test_missing_release_date_unknown() -> None:
    lifecycle = compute_import_release_lifecycle(
        best_release_date=None,
        today=date(2026, 6, 8),
        order_status="ordered",
    )
    assert lifecycle["release_lifecycle_status"] == "UNKNOWN"
    assert lifecycle["lifecycle_sort_bucket"] == 40


def test_catalog_release_date_overrides_missing_import_date() -> None:
    best = resolve_best_release_date(
        release_issue_date=date(2026, 6, 17),
        external_catalog_date=None,
        parsed_import_date=None,
        draft_release_date=None,
    )
    assert best == date(2026, 6, 17)


def test_batwoman_style_preorder_enrichment() -> None:
    item = {
        "publisher": "DC",
        "title": "Batwoman Vol 3",
        "issue_number": "4",
        "release_date": "2026-06-17",
        "release_status": "unknown",
        "order_status": "ordered",
    }
    enriched = enrich_import_item_lifecycle(
        None,
        owner_user_id=None,
        item=item,
        today=date(2026, 6, 8),
    )
    assert enriched["release_lifecycle_status"] == "PREORDER"
    assert enriched["days_until_release"] == 9
    assert enriched["release_status"] == "not_released_yet"
    assert "Jun 17, 2026" in enriched["lifecycle_display_detail"]
