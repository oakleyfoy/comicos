"""P103 enrichment validation and helper tests."""

import pytest

from app.services.p103_gcd_catalog_enrichment_service import (
    MAX_ENRICHMENT_WRITE_LIMIT,
    validate_enrichment_filters,
)
from app.services.p103_gcd_enrichment_helpers import (
    classify_printing_label,
    classify_variant_label,
    gcd_row_to_plan_inputs,
    is_blank,
    parse_key_date,
)


def test_validate_write_requires_confirm():
    with pytest.raises(ValueError, match="confirm-write"):
        validate_enrichment_filters(
            write_batch=True,
            limit=50,
            publisher="DC",
            year=2018,
            year_from=None,
            year_to=None,
            confirm_write=None,
        )


def test_validate_write_limit_cap():
    with pytest.raises(ValueError, match=str(MAX_ENRICHMENT_WRITE_LIMIT)):
        validate_enrichment_filters(
            write_batch=True,
            limit=MAX_ENRICHMENT_WRITE_LIMIT + 1,
            publisher="DC",
            year=2018,
            year_from=None,
            year_to=None,
            confirm_write="YES",
        )


def test_dry_run_filters_dc_year():
    f = validate_enrichment_filters(
        write_batch=False,
        limit=None,
        publisher="DC",
        year=2018,
        year_from=None,
        year_to=None,
        confirm_write=None,
    )
    assert f is not None
    assert f.publisher == "DC"
    assert f.year_from == 2018


def test_gcd_row_to_plan_inputs_variant_printing():
    row = gcd_row_to_plan_inputs(
        {
            "issue_id": 1,
            "gcd_series_id": 2,
            "gcd_publisher_id": 3,
            "publisher_name": "DC Comics",
            "series_name": "Batman",
            "number": "1",
            "barcode": None,
            "key_date": "2018-03-00",
            "year_began": 2016,
            "title": "Test",
            "notes": "Second print variant cover",
        }
    )
    assert row["variant_label"] is not None
    assert row["calendar_date"] is not None


def test_is_blank_and_key_date():
    assert is_blank(None)
    assert is_blank("")
    cal, y, m = parse_key_date("2018-05-01", None)
    assert cal is not None and cal.year == 2018 and m == 5


def test_plan_enrichment_updates_in_memory():
    from app.services.p101_catalog_cache_service import CatalogCacheContext, CatalogCacheMatcher
    from app.services.p103_gcd_enrichment_fast import EnrichmentIssueSnapshot, plan_enrichment_updates

    snap = EnrichmentIssueSnapshot(
        issue_id=1,
        year=2018,
        publisher_id=1,
        series_id=2,
        publisher_norm="dc",
        series_norm="batman",
        issue_norm="1",
        publisher_name="DC Comics",
        series_name="Batman",
        issue_number="1",
        cover_date=None,
        release_date=None,
        store_date=None,
        title=None,
        description=None,
        external_source_ids={},
        variant_printing=None,
        variant_variant_name=None,
        has_upc=False,
    )
    ctx = CatalogCacheContext(
        matcher=CatalogCacheMatcher(exact_keys=set(), by_series_issue={}),
        upc_to_issue={},
        learned_barcodes=set(),
    )
    gcd = {
        "gcd_issue_id": 99,
        "barcode": "76194134192703921",
        "calendar_date": __import__("datetime").date(2018, 3, 1),
        "title": "Test",
        "notes": "Note",
        "issue_number": "1",
        "series": "Batman",
        "publisher": "DC Comics",
    }
    planned, conflicts, upc_n = plan_enrichment_updates(snap, gcd, ctx=ctx)
    assert upc_n == 1
    assert any(p["field"] == "catalog_upc" for p in planned)
    assert not conflicts
