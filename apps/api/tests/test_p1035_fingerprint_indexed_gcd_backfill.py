"""Tests for fingerprint-indexed P103.5 GCD backfill helpers."""

from __future__ import annotations

from app.services.p1035_fingerprint_indexed_gcd_backfill_service import (
    _identity_fields_present,
    _is_comicvine_primary,
)
from app.services.p103_gcd_enrichment_fast import EnrichmentIssueSnapshot


def _snap(**kwargs) -> EnrichmentIssueSnapshot:
    base = dict(
        issue_id=1,
        year=2024,
        publisher_id=1,
        series_id=1,
        publisher_norm="marvel",
        series_norm="x men",
        issue_norm="1",
        publisher_name="Marvel",
        series_name="X-Men",
        issue_number="1",
        cover_date=None,
        release_date=None,
        store_date=None,
        title=None,
        description=None,
        external_source_ids={"_primary_source": "COMICVINE"},
        variant_printing=None,
        variant_variant_name=None,
        has_upc=False,
    )
    base.update(kwargs)
    return EnrichmentIssueSnapshot(**base)


def test_comicvine_primary_detection() -> None:
    assert _is_comicvine_primary({"_primary_source": "COMICVINE"}) is True
    assert _is_comicvine_primary({"_primary_source": "GCD"}) is False


def test_identity_fields_require_publisher_series_or_title() -> None:
    assert _identity_fields_present(_snap()) is True
    assert _identity_fields_present(_snap(series_name="", title="Annual")) is True
    assert _identity_fields_present(_snap(publisher_name="")) is False
    assert _identity_fields_present(_snap(series_name="", title="")) is False
