"""P88 manual marketplace URL import API tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_import_valid_ebay_url(client: TestClient) -> None:
    token = register_and_login(client, "p88-import@example.com")
    resp = client.post(
        "/api/v1/buy-opportunities/import-url",
        headers=auth_headers(token),
        json={"url": "https://www.ebay.com/itm/9876543210", "notes": "manual test"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["message"] == "Marketplace imported successfully."
    assert data["source"]["marketplace"] == "EBAY"
    assert data["source"]["source_type"] == "MANUAL_IMPORT"
    assert data["source"]["source_url"] == "https://ebay.com/itm/9876543210"


def test_import_rejects_invalid_url(client: TestClient) -> None:
    token = register_and_login(client, "p88-import-bad@example.com")
    resp = client.post(
        "/api/v1/buy-opportunities/import-url",
        headers=auth_headers(token),
        json={"url": "http://www.ebay.com/itm/1"},
    )
    assert resp.status_code == 422


def test_list_sources_after_import(client: TestClient) -> None:
    token = register_and_login(client, "p88-list@example.com")
    client.post(
        "/api/v1/buy-opportunities/import-url",
        headers=auth_headers(token),
        json={"url": "https://www.mycomicshop.com/search?T=123"},
    )
    listed = client.get("/api/v1/buy-opportunities/sources", headers=auth_headers(token))
    assert listed.status_code == 200
    items = listed.json()["data"]["items"]
    assert len(items) >= 1


def test_ebay_integration_status(client: TestClient) -> None:
    token = register_and_login(client, "p88-ebay-status@example.com")
    resp = client.get("/api/v1/marketplace/integration/ebay", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["status"] in {"Configured", "Not Configured"}
    assert "client_id_present" in body
