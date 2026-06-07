"""Tests for P82 listing URL safety classification (no network, no DB writes)."""

from __future__ import annotations

from app.services.p82_listing_url_safety import (
    classify_p82_listing_url,
    is_safe_marketplace_listing_url,
    is_simulated_external_listing_id,
)


def test_simulated_external_ids() -> None:
    assert is_simulated_external_listing_id("SIM-EBAY-P82-1")
    assert is_simulated_external_listing_id("P82-TEST-1")
    assert is_simulated_external_listing_id("CERT-P82-001")
    assert not is_simulated_external_listing_id("1234567890")


def test_classify_simulated_as_suspicious() -> None:
    assert (
        classify_p82_listing_url(
            listing_url="https://www.ebay.com/itm/SIM-EBAY-P82-1",
            external_listing_id="SIM-EBAY-P82-1",
        )
        == "simulated_external_id"
    )


def test_numeric_ebay_url_likely_safe() -> None:
    assert (
        classify_p82_listing_url(
            listing_url="https://www.ebay.com/itm/123456789012",
            external_listing_id="123456789012",
        )
        == "likely_safe_ebay"
    )
    assert is_safe_marketplace_listing_url(
        listing_url="https://www.ebay.com/itm/123456789012",
        external_listing_id="123456789012",
    )


def test_ebay_non_numeric_unsafe() -> None:
    assert not is_safe_marketplace_listing_url(
        listing_url="https://www.ebay.com/itm/not-a-number",
        external_listing_id="not-a-number",
    )
    assert (
        classify_p82_listing_url(
            listing_url="https://www.ebay.com/itm/not-a-number",
            external_listing_id="not-a-number",
        )
        == "ebay_non_numeric"
    )
