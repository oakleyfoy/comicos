"""Tests for marketplace monitoring service."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.services.marketplace.ebay_search_service import NormalizedMarketplaceListing
from test_inventory import auth_headers, register_and_login


def test_new_listing_creates_alert(client: TestClient) -> None:
    token = register_and_login(client, "p88-mon-new@example.com")
    client.post(
        "/api/v1/marketplace-monitoring/saved-searches",
        headers=auth_headers(token),
        json={"name": "Mon", "series": "Absolute Batman", "issue_number": "20"},
    )
    listing = NormalizedMarketplaceListing(
        marketplace="EBAY",
        item_id="111122223333",
        title="Absolute Batman #20",
        url="https://www.ebay.com/itm/111122223333",
        price=5.0,
        shipping=0.0,
        condition="NM",
        seller="s",
        listing_type="FIXED_PRICE",
        end_time=None,
        image_url="",
    )
    with patch("app.services.marketplace.marketplace_monitoring_service.search_comics", return_value=[listing]):
        listed = client.get("/api/v1/marketplace-monitoring/saved-searches", headers=auth_headers(token))
        sid = listed.json()["data"]["items"][0]["id"]
        client.post(f"/api/v1/marketplace-monitoring/saved-searches/{sid}/run", headers=auth_headers(token))
    alerts = client.get("/api/v1/marketplace-monitoring/alerts", headers=auth_headers(token))
    assert alerts.status_code == 200
    assert len(alerts.json()["data"]["items"]) >= 1


@patch("app.services.marketplace.marketplace_monitoring_service.search_comics")
def test_dry_run_writes_nothing(mock_search: object, client: TestClient) -> None:
    mock_search.return_value = [
        NormalizedMarketplaceListing(
            marketplace="EBAY",
            item_id="777788889999",
            title="Book",
            url="https://www.ebay.com/itm/777788889999",
            price=1.0,
            shipping=0.0,
            condition="",
            seller="",
            listing_type="",
            end_time=None,
            image_url="",
        )
    ]
    token = register_and_login(client, "p88-mon-dry@example.com")
    create = client.post(
        "/api/v1/marketplace-monitoring/saved-searches",
        headers=auth_headers(token),
        json={"name": "Dry", "series": "Book", "issue_number": "1"},
    )
    sid = create.json()["data"]["id"]
    run = client.post(
        f"/api/v1/marketplace-monitoring/saved-searches/{sid}/run?dry_run=true",
        headers=auth_headers(token),
    )
    assert run.status_code == 200
    alerts = client.get("/api/v1/marketplace-monitoring/alerts", headers=auth_headers(token))
    assert alerts.json()["data"]["items"] == []
