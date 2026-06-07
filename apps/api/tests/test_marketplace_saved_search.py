"""Tests for marketplace saved search API."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_saved_search_crud(client: TestClient) -> None:
    token = register_and_login(client, "p88-saved-search@example.com")
    create = client.post(
        "/api/v1/marketplace-monitoring/saved-searches",
        headers=auth_headers(token),
        json={
            "name": "Absolute Batman #20",
            "series": "Absolute Batman",
            "issue_number": "20",
            "publisher": "DC",
            "min_discount_to_fmv": 20,
        },
    )
    assert create.status_code == 200, create.text
    sid = create.json()["data"]["id"]

    listed = client.get("/api/v1/marketplace-monitoring/saved-searches", headers=auth_headers(token))
    assert listed.status_code == 200
    assert any(item["id"] == sid for item in listed.json()["data"]["items"])

    patched = client.patch(
        f"/api/v1/marketplace-monitoring/saved-searches/{sid}",
        headers=auth_headers(token),
        json={"is_active": False, "max_price": 15.0},
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["is_active"] is False

    deleted = client.delete(
        f"/api/v1/marketplace-monitoring/saved-searches/{sid}",
        headers=auth_headers(token),
    )
    assert deleted.status_code == 200


@patch("app.services.marketplace.marketplace_monitoring_service.search_comics")
def test_manual_run_saved_search(mock_search, client: TestClient) -> None:
    from app.services.marketplace.ebay_search_service import NormalizedMarketplaceListing

    mock_search.return_value = [
        NormalizedMarketplaceListing(
            marketplace="EBAY",
            item_id="9999999999",
            title="Absolute Batman #20",
            url="https://www.ebay.com/itm/9999999999",
            price=8.0,
            shipping=0.0,
            condition="NM",
            seller="shop",
            listing_type="FIXED_PRICE",
            end_time=None,
            image_url="",
        )
    ]
    token = register_and_login(client, "p88-run-search@example.com")
    create = client.post(
        "/api/v1/marketplace-monitoring/saved-searches",
        headers=auth_headers(token),
        json={"name": "Run test", "series": "Absolute Batman", "issue_number": "20"},
    )
    sid = create.json()["data"]["id"]
    run = client.post(
        f"/api/v1/marketplace-monitoring/saved-searches/{sid}/run",
        headers=auth_headers(token),
    )
    assert run.status_code == 200, run.text
    body = run.json()["data"]["run"]
    assert body["listings_found"] >= 1
