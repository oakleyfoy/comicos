"""P88-02 live marketplace search API tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.services.marketplace.adapters.base import AdapterOperationResult
from app.services.marketplace.ebay_search_service import NormalizedMarketplaceListing
from test_inventory import auth_headers, register_and_login


def test_search_marketplace_stores_listings(client: TestClient) -> None:
    token = register_and_login(client, "p88-live-search@example.com")
    scan = client.post(
        "/api/v1/marketplace-acquisition/scan",
        headers=auth_headers(token),
        json={
            "title": "Absolute Batman #20",
            "series": "Absolute Batman",
            "issue": "20",
            "publisher": "DC",
            "asking_price": 5.0,
            "external_listing_id": "SIM-EBAY-P88-TEST",
        },
    )
    assert scan.status_code == 200

    listing = NormalizedMarketplaceListing(
        marketplace="EBAY",
        item_id="8888888888",
        title="Absolute Batman #20",
        url="https://www.ebay.com/itm/8888888888",
        price=3.2,
        shipping=4.95,
        condition="Very Fine",
        seller="comicshop123",
        listing_type="FIXED_PRICE",
        end_time=None,
        image_url="",
    )

    mock_adapter = MagicMock()
    mock_adapter.search.return_value = AdapterOperationResult(status="OK", listings=(listing,))

    with patch(
        "app.services.marketplace.marketplace_live_search_service.get_marketplace_adapter",
        return_value=mock_adapter,
    ):
        resp = client.post(
            "/api/v1/buy-opportunities/search-marketplace",
            headers=auth_headers(token),
            json={},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["listings_found"] >= 1
    assert data["new_listings"] >= 1

    listed = client.get("/api/v1/marketplace-acquisition/opportunities", headers=auth_headers(token))
    opps = listed.json()["data"]["items"]
    assert any(o.get("active_listing_count", 0) >= 1 for o in opps)

    opp_id = opps[0]["id"]
    listings = client.get(f"/api/v1/buy-opportunities/{opp_id}/listings", headers=auth_headers(token))
    assert listings.status_code == 200
    items = listings.json()["data"]["items"]
    assert len(items) >= 1
    assert items[0]["listing_url"].startswith("https://")


def test_duplicate_search_does_not_duplicate_listings(client: TestClient) -> None:
    token = register_and_login(client, "p88-live-dedupe@example.com")
    client.post(
        "/api/v1/marketplace-acquisition/scan",
        headers=auth_headers(token),
        json={
            "title": "Test Book #1",
            "series": "Test Book",
            "issue": "1",
            "asking_price": 2.0,
            "external_listing_id": "SIM-DEDUPE",
        },
    )
    listing = NormalizedMarketplaceListing(
        marketplace="EBAY",
        item_id="7777777777",
        title="Test Book #1",
        url="https://www.ebay.com/itm/7777777777",
        price=2.0,
        shipping=0.0,
        condition="NM",
        seller="s",
        listing_type="FIXED_PRICE",
        end_time=None,
        image_url="",
    )
    mock_adapter = MagicMock()
    mock_adapter.search.return_value = AdapterOperationResult(status="OK", listings=(listing,))

    with patch(
        "app.services.marketplace.marketplace_live_search_service.get_marketplace_adapter",
        return_value=mock_adapter,
    ):
        first = client.post(
            "/api/v1/buy-opportunities/search-marketplace",
            headers=auth_headers(token),
            json={},
        )
        second = client.post(
            "/api/v1/buy-opportunities/search-marketplace",
            headers=auth_headers(token),
            json={},
        )
    assert first.json()["data"]["new_listings"] >= 1
    assert second.json()["data"]["new_listings"] == 0
    assert second.json()["data"]["updated_listings"] >= 1
