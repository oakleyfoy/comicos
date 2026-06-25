"""P102 write-batch CLI validation."""

import pytest

from app.services.p102_gcd_modern_acquisition_write_service import (
    MAX_WRITE_BATCH_LIMIT,
    validate_write_batch_args,
)


def test_write_batch_requires_safety_flags():
    with pytest.raises(ValueError, match="confirm-write"):
        validate_write_batch_args(
            write_batch=True,
            limit=50,
            publisher="DC",
            year=2018,
            year_from=None,
            year_to=None,
            confirm_write=None,
        )


def test_write_batch_ok_dc_2018():
    f = validate_write_batch_args(
        write_batch=True,
        limit=100,
        publisher="DC",
        year=2018,
        year_from=None,
        year_to=None,
        confirm_write="YES",
    )
    assert f is not None
    assert f.publisher == "DC"
    assert f.year_from == 2018
    assert f.year_to == 2018
    assert f.limit == 100


def test_write_batch_limit_cap():
    with pytest.raises(ValueError, match=str(MAX_WRITE_BATCH_LIMIT)):
        validate_write_batch_args(
            write_batch=True,
            limit=101,
            publisher="DC",
            year=2018,
            year_from=None,
            year_to=None,
            confirm_write="YES",
            large_batch=False,
        )


def test_large_write_batch_allows_2500():
    f = validate_write_batch_args(
        write_batch=True,
        limit=2500,
        publisher="DC",
        year=None,
        year_from=2009,
        year_to=2026,
        confirm_write="YES",
        large_batch=True,
    )
    assert f is not None
    assert f.limit == 2500


def test_dry_run_mode_returns_none():
    assert (
        validate_write_batch_args(
            write_batch=False,
            limit=None,
            publisher=None,
            year=None,
            year_from=None,
            year_to=None,
            confirm_write=None,
        )
        is None
    )


def test_write_batch_timer_summary():
    from app.services.p102_gcd_write_batch_fast import WriteBatchTimer

    t = WriteBatchTimer(preload_sec=1.0, commit_sec=9.0, commits=2)
    s = t.summary(inserted=500, elapsed_total=600.0)
    assert s["rows_per_min"] == 50.0
    assert s["estimated_sec_10k"] == 12000.0


def test_classify_uses_normalized_upc_in_guard():
    from collections import Counter

    from app.services.p101_catalog_cache_service import CatalogCacheContext, CatalogCacheMatcher
    from app.services.p102_gcd_modern_acquisition_service import _classify_missing_row

    ctx = CatalogCacheContext(
        matcher=CatalogCacheMatcher(exact_keys=set(), by_series_issue={}),
        upc_to_issue={"76194134918303611": 99},
        learned_barcodes=set(),
    )
    cls, reason, _bc, project_issue, project_upc = _classify_missing_row(
        focus_label="DC",
        publisher_raw="DC Comics",
        series="Test Series",
        issue_number="1",
        year=2020,
        barcode_raw=None,
        barcodes=["76194134918303611"],
        ctx=ctx,
        seen_gcd_keys=Counter(),
    )
    assert cls == "duplicate_or_conflict"
    assert reason == "barcode_already_on_catalog_upc"
    assert project_issue is False
    assert project_upc is False
