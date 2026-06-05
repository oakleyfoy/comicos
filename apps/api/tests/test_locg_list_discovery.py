from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.services.external_catalog.locg_list_discovery import (
    EXPECTED_MINIMUM_ISSUE_COUNT,
    _scroll_stable_rounds_needed,
    audit_list_html,
    validate_discovery_threshold,
)

CAPTURE_LIST = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "locg_browser_capture"
    / "2026-06-10"
    / "list_page.html"
)


@pytest.mark.skipif(not CAPTURE_LIST.is_file(), reason="captured list_page.html not present")
def test_audit_partial_capture_list_page() -> None:
    html = CAPTURE_LIST.read_text(encoding="utf-8")
    audit = audit_list_html(
        html,
        page_url="https://leagueofcomicgeeks.com/comics/new-comics/2026/06/10",
    )
    assert audit.total_li_issue_rows >= 150
    assert len(audit.all_issue_urls) == audit.total_li_issue_rows
    assert audit.final_parent_issue_queue_count < audit.total_li_issue_rows
    assert audit.final_variant_queue_count > 0
    assert audit.parent_issue_rows > 0
    assert audit.variant_rows > 0
    assert audit.total_release_rows_reconciled == audit.total_li_issue_rows
    assert audit.unique_variant_urls > audit.unique_parent_issue_urls
    # Saved capture can have 230+ variant-inclusive rows but still lack ~234 parent issues.
    if audit.total_li_issue_rows < EXPECTED_MINIMUM_ISSUE_COUNT:
        with pytest.raises(RuntimeError, match="below expected threshold"):
            validate_discovery_threshold(audit)
    else:
        assert audit.parent_issue_rows < EXPECTED_MINIMUM_ISSUE_COUNT


def test_scroll_stable_detects_unchanged_row_counts() -> None:
    assert _scroll_stable_rounds_needed([165, 331, 589, 589]) == 4
    assert _scroll_stable_rounds_needed([100, 200, 300]) is None


def test_discovery_report_shape() -> None:
    html = '<html><title>Test</title><li class="issue" data-comic="1" data-parent="0"></li></html>'
    audit = audit_list_html(html, page_url="https://example.com/", page_title="Test")
    report = audit.to_report_dict()
    assert report["expected_minimum_issue_count"] == EXPECTED_MINIMUM_ISSUE_COUNT
    assert "first_20_urls" in report
    assert report["discovery_timestamp"]
    assert "scroll_discovery" in report
    assert "discovery_row_count_log" in report


def test_validate_threshold_fails_small_page() -> None:
    audit = audit_list_html("<html></html>", page_url="https://example.com/")
    with pytest.raises(RuntimeError):
        validate_discovery_threshold(audit)
