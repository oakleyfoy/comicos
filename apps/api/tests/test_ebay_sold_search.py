from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import func, select

from app.models.market_pricing_engine import P68MarketPriceObservation
from app.schemas.ebay_sold_search import EbaySoldSearchPreviewResponse
from app.services.ebay_sold_search_service import (
    build_ebay_sold_search_request,
    normalize_ebay_sold_search_payload,
)
from test_inventory import auth_headers, register_and_login


def test_query_builder_prefers_exact_comic_terms() -> None:
    request = build_ebay_sold_search_request(
        title="Absolute Batman",
        issue_number="1",
        variant="Cover A",
        publisher="DC Comics",
        condition="CGC 9.8",
        limit=25,
    )
    assert request.query == "Absolute Batman 1 Cover A DC Comics CGC 9.8"
    assert request.params["q"] == request.query
    assert request.params["limit"] == 25
    assert request.params["filter"] == "soldItems:true"


def test_parser_handles_price_shipping_and_dates() -> None:
    request = build_ebay_sold_search_request(q="Absolute Batman 1", limit=25)
    payload = {
        "totalEntries": 1,
        "itemSummaries": [
            {
                "itemId": "v1|123",
                "title": "Absolute Batman #1 CGC 9.8",
                "price": {"value": "49.99", "currency": "USD"},
                "shippingOptions": [{"shippingCost": {"value": "5.50", "currency": "USD"}}],
                "endedDate": "2026-06-01T12:34:56.000Z",
                "condition": "Graded",
                "listingType": "AUCTION",
                "itemWebUrl": "https://example.test/item/123",
                "image": {"imageUrl": "https://example.test/image.jpg"},
                "seller": {"username": "graded-books"},
                "itemLocation": {"country": "US"},
            }
        ],
    }
    items = normalize_ebay_sold_search_payload(payload, request)
    assert len(items) == 1
    row = items[0]
    assert row.provider == "EBAY"
    assert row.provider_listing_id == "v1|123"
    assert row.sold_price == 49.99
    assert row.shipping_price == 5.5
    assert row.total_price == 55.49
    assert row.ended_at == datetime(2026, 6, 1, 12, 34, 56, tzinfo=timezone.utc)
    assert row.condition == "Graded"
    assert row.listing_type == "AUCTION"
    assert row.item_url == "https://example.test/item/123"
    assert row.image_url == "https://example.test/image.jpg"
    assert row.seller_location == "graded-books"
    assert row.raw_match_confidence >= 0.35
    assert "title matched search text" in row.match_notes or "broad marketplace preview match" in row.match_notes


def test_parser_handles_missing_optional_fields() -> None:
    request = build_ebay_sold_search_request(title="Teenage Mutant Ninja Turtles", issue_number="300", limit=25)
    payload = {
        "itemSummaries": [
            {
                "itemId": "listing-001",
                "title": "TMNT #300",
                "price": {"value": "10.00", "currency": "USD"},
            }
        ]
    }
    items = normalize_ebay_sold_search_payload(payload, request)
    assert len(items) == 1
    row = items[0]
    assert row.shipping_price is None
    assert row.total_price is None
    assert row.sold_at is None
    assert row.ended_at is None
    assert row.image_url is None
    assert row.seller_location is None
    assert row.match_notes


def test_route_returns_empty_list_and_writes_nothing(client: TestClient, session, monkeypatch) -> None:
    token = register_and_login(client, "ebay-sold-empty@example.com")
    monkeypatch.setenv("EBAY_API_CLIENT_ID", "client-id")
    monkeypatch.setenv("EBAY_API_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("EBAY_ENVIRONMENT", "production")
    from app.core.config import get_settings

    get_settings.cache_clear()

    before = int(session.scalar(select(func.count()).select_from(P68MarketPriceObservation)) or 0)
    monkeypatch.setattr(
        "app.api.market_pricing_engine_api.search_ebay_sold_listings",
        lambda **kwargs: EbaySoldSearchPreviewResponse(query="Batman 1", sold_search_available=True, total_items=0, limit=25, items=[]),
    )
    response = client.get(
        "/api/v1/market-pricing/ebay/sold-search",
        headers=auth_headers(token),
        params={"title": "Batman", "issue_number": "1"},
    )
    after = int(session.scalar(select(func.count()).select_from(P68MarketPriceObservation)) or 0)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["items"] == []
    assert after == before


def test_route_returns_controlled_error_on_ebay_failure(client: TestClient, monkeypatch) -> None:
    token = register_and_login(client, "ebay-sold-error@example.com")
    monkeypatch.setenv("EBAY_API_CLIENT_ID", "client-id")
    monkeypatch.setenv("EBAY_API_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("EBAY_ENVIRONMENT", "production")
    from app.core.config import get_settings

    get_settings.cache_clear()

    def raise_error(**kwargs):
        from app.services.ebay_sold_search_service import EbaySoldSearchApiError

        raise EbaySoldSearchApiError("eBay sold search failed with HTTP 500: boom")

    monkeypatch.setattr("app.api.market_pricing_engine_api.search_ebay_sold_listings", raise_error)

    response = client.get(
        "/api/v1/market-pricing/ebay/sold-search",
        headers=auth_headers(token),
        params={"q": "Batman"},
    )
    assert response.status_code == 502
    assert "eBay sold search failed" in response.json()["error"]["message"]
