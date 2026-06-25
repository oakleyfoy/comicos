"""P102 classification smoke tests."""

from app.services.p101_catalog_cache_service import CatalogCacheContext, CatalogCacheMatcher
from app.services.p102_gcd_modern_acquisition_service import _classify_missing_row
from collections import Counter


def test_clean_primary_with_valid_barcode():
    ctx = CatalogCacheContext(
        matcher=CatalogCacheMatcher(exact_keys=set(), by_series_issue={}),
        upc_to_issue={},
        learned_barcodes=set(),
    )
    seen: Counter = Counter()
    cls, reason, bc, proj_i, proj_u = _classify_missing_row(
        focus_label="DC",
        publisher_raw="DC Comics",
        series="Superman",
        issue_number="39",
        year=2015,
        barcode_raw="76194134192703921",
        barcodes=["76194134192703921"],
        ctx=ctx,
        seen_gcd_keys=seen,
    )
    assert cls == "clean_primary_candidate"
    assert proj_i is True
    assert proj_u is True
    assert bc == "76194134192703921"


def test_reprint_digest_classified():
    ctx = CatalogCacheContext(
        matcher=CatalogCacheMatcher(exact_keys=set(), by_series_issue={}),
        upc_to_issue={},
        learned_barcodes=set(),
    )
    cls, *_ = _classify_missing_row(
        focus_label="Archie",
        publisher_raw="Archie",
        series="Archie Comics Digest",
        issue_number="250",
        year=2010,
        barcode_raw=None,
        barcodes=[],
        ctx=ctx,
        seen_gcd_keys=Counter(),
    )
    assert cls == "reprint_or_digest"
