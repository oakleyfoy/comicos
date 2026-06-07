"""Tests for P88-02 eBay live search service."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from app.services.marketplace.ebay_search_service import (
    NormalizedMarketplaceListing,
    _canonical_item_id,
    _normalize_browse_item,
    build_live_search_params,
    search_comics,
)


def test_canonical_item_id_from_pipe_format() -> None:
    assert _canonical_item_id("v1|1234567890|0") == "1234567890"


def test_build_live_search_params_requires_terms() -> None:
    try:
        build_live_search_params(limit=5)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_normalize_browse_item_active_listing() -> None:
    item = {
        "itemId": "v1|5555555555|0",
        "title": "Absolute Batman #20",
        "itemWebUrl": "https://www.ebay.com/itm/5555555555",
        "price": {"value": "3.20", "currency": "USD"},
        "shippingOptions": [{"shippingCost": {"value": "4.95"}}],
        "condition": "Very Good",
        "seller": {"username": "comicshop123"},
        "buyingOptions": ["FIXED_PRICE"],
        "image": {"imageUrl": "https://i.ebayimg.com/example.jpg"},
    }
    normalized = _normalize_browse_item(item)
    assert normalized is not None
    assert normalized.item_id == "5555555555"
    assert normalized.price == 3.2
    assert normalized.shipping == 4.95
    assert normalized.seller == "comicshop123"


@patch("app.services.marketplace.ebay_search_service.acquire_ebay_oauth_access_token")
@patch("app.services.marketplace.ebay_search_service._get_with_retry")
def test_search_comics_returns_normalized(mock_get: MagicMock, mock_token: MagicMock) -> None:
    mock_token.return_value = MagicMock(access_token="token")
    mock_get.return_value = {
        "itemSummaries": [
            {
                "itemId": "v1|999|0",
                "title": "Test Comic",
                "itemWebUrl": "https://www.ebay.com/itm/999",
                "price": {"value": "1.00"},
            }
        ]
    }
    results = search_comics(title="Test Comic", limit=5, settings=MagicMock(ebay_environment="production"))
    assert len(results) == 1
    assert isinstance(results[0], NormalizedMarketplaceListing)
    assert results[0].item_id == "999"
