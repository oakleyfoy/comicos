"""P101 modern catalog audit helpers."""

from __future__ import annotations

from app.services.p101_modern_catalog_audit_service import (
    canonical_focus_publisher_label,
    issue_year_key,
)


def test_canonical_focus_publisher_labels() -> None:
    assert canonical_focus_publisher_label("Marvel") == "Marvel"
    assert canonical_focus_publisher_label("DC Comics") == "DC"
    assert canonical_focus_publisher_label("Image Comics") == "Image"
    assert canonical_focus_publisher_label("BOOM! Studios") == "Boom"
    assert canonical_focus_publisher_label("Archie Comics") is None


def test_issue_year_key_prefers_cover_date() -> None:
    assert issue_year_key(2016, 2017) == 2016
    assert issue_year_key(None, 2019) == 2019
    assert issue_year_key(None, None) == "Unknown"
