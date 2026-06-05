from __future__ import annotations

from datetime import date

from app.services.collector_display_identity import (
    format_collector_issue_display,
    parse_series_volume,
    resolve_collector_display_title,
)


def test_distinct_series_names() -> None:
    a = format_collector_issue_display(series_name="Batman", issue_number="11")
    b = format_collector_issue_display(series_name="Absolute Batman", issue_number="11")
    c = format_collector_issue_display(series_name="Batman and Robin", issue_number="11")
    assert a == "Batman #11"
    assert b == "Absolute Batman #11"
    assert c == "Batman and Robin #11"
    assert len({a, b, c}) == 3


def test_volume_format() -> None:
    assert parse_series_volume("Batman Vol 4") == ("Batman", 4)
    out = format_collector_issue_display(series_name="Batman Vol 4", issue_number="11")
    assert out == "Batman Vol 4 #11"


def test_year_format() -> None:
    out = format_collector_issue_display(
        series_name="Batman",
        issue_number="11",
        release_date=date(2025, 3, 1),
    )
    assert out == "Batman (2025) #11"


def test_resolve_legacy_title() -> None:
    out = resolve_collector_display_title(
        None,
        title="Batman #11",
        issue_number="11",
    )
    assert out == "Batman #11"
