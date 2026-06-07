"""P88 marketplace registry tests (P88-04 capabilities)."""

from app.services.marketplace.marketplace_registry import (
    detect_marketplace_from_url,
    list_supported_marketplace_codes,
    marketplace_definition,
    marketplace_display_name,
    normalize_marketplace_url,
)


def test_detect_marketplace_from_url() -> None:
    assert detect_marketplace_from_url("https://www.ebay.com/itm/123") == "EBAY"
    assert detect_marketplace_from_url("https://whatnot.com/live/abc") == "WHATNOT"
    assert detect_marketplace_from_url("https://example.com/x") == "OTHER"


def test_normalize_marketplace_url() -> None:
    assert (
        normalize_marketplace_url("https://www.ebay.com/itm/123/")
        == "https://ebay.com/itm/123"
    )


def test_marketplace_display_name() -> None:
    assert marketplace_display_name("EBAY") == "eBay"


def test_registry_capability_flags() -> None:
    ebay = marketplace_definition("EBAY")
    assert ebay.supports_search is True
    assert ebay.supports_listing_lookup is True
    assert ebay.supports_refresh is True
    midtown = marketplace_definition("MIDTOWN")
    assert midtown.supports_search is False


def test_supported_marketplace_codes() -> None:
    codes = list_supported_marketplace_codes()
    assert "EBAY" in codes
    assert "MYCOMICSHOP" in codes
    assert "WHATNOT" not in codes
