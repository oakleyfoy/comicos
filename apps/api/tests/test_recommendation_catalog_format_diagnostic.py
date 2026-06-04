"""Catalog format filtering for signal bucket diagnostics."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.recommendation_signal_bucket_diagnostic import (
    PRODUCT_FORMAT_SINGLE_ISSUE,
    PRODUCT_FORMAT_TRADE_PAPERBACK,
    _format_usable,
    _select_catalog_pair,
    classify_catalog_product_format,
)


def _row(series_name: str, issue_number: str, title: str) -> tuple[SimpleNamespace, SimpleNamespace]:
    series = SimpleNamespace(series_name=series_name, publisher="Test Pub", series_type="ongoing")
    issue = SimpleNamespace(
        id=1,
        issue_number=issue_number,
        title=title,
        foc_date=None,
        release_date=None,
    )
    return issue, series


def test_youngblood_tp_classified_trade_paperback() -> None:
    issue, series = _row("Youngblood", "1", "Youngblood TP #1")
    assert classify_catalog_product_format(issue, series) == PRODUCT_FORMAT_TRADE_PAPERBACK
    assert not _format_usable(PRODUCT_FORMAT_TRADE_PAPERBACK, include_books=False)


def test_single_issue_beats_tp_when_both_exist() -> None:
    tp = _row("Youngblood", "1", "Youngblood TP #1")
    comic = _row("Youngblood", "12", "Youngblood #12")
    pair, candidates, reason, fmt, excluded = _select_catalog_pair(
        [tp, comic],
        include_books=False,
        strict_title=None,
        index_pair=None,
    )
    assert pair is not None
    assert pair[1].series_name == "Youngblood"
    assert pair[0].issue_number == "12"
    assert fmt == PRODUCT_FORMAT_SINGLE_ISSUE
    assert reason == "preferred_single_issue_catalog_row"
    assert excluded is False
    assert sum(1 for c in candidates if c["usable_for_spec_diagnostic"]) == 1


def test_only_tp_reports_no_usable_match() -> None:
    tp = _row("Youngblood", "1", "Youngblood TP #1")
    pair, candidates, reason, fmt, excluded = _select_catalog_pair(
        [tp],
        include_books=False,
        strict_title=None,
        index_pair=None,
    )
    assert pair is None
    assert reason == "no_usable_single_issue_in_catalog"
    assert excluded is True
    assert candidates[0]["excluded_by_format_filter"] is True


def test_tp_included_with_include_books() -> None:
    tp = _row("Youngblood", "1", "Youngblood TP #1")
    pair, _candidates, _reason, fmt, excluded = _select_catalog_pair(
        [tp],
        include_books=True,
        strict_title=None,
        index_pair=None,
    )
    assert pair is not None
    assert fmt == PRODUCT_FORMAT_TRADE_PAPERBACK
    assert excluded is False
