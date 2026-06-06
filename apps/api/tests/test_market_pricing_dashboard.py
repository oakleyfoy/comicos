"""Regression: Market & FMV dashboard read-only GETs (no rebuild POSTs)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_market_fmv_dashboard_market_sales_list(client: TestClient) -> None:
    """Dashboard `apiClient.getMarketSales()` → GET /market-sales."""
    token = register_and_login(client, "market-dash-sales@example.com")
    response = client.get("/market-sales", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    assert response.headers.get("content-type", "").startswith("application/json")
    body = response.json()
    assert "items" in body
    assert isinstance(body["items"], list)


def test_market_fmv_dashboard_ingestion_summary_v1(client: TestClient) -> None:
    """`useMarketIntelligencePanels` ingestion → GET /api/v1/market/market-ingestion/batches."""
    token = register_and_login(client, "market-dash-ingest@example.com")
    response = client.get(
        "/api/v1/market/market-ingestion/batches?limit=25&offset=0",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    assert response.headers.get("content-type", "").startswith("application/json")
    envelope = response.json()
    assert set(envelope.keys()) == {"data", "meta"}
    assert "items" in envelope["data"]
    assert "pagination" in envelope["data"]
    pag = envelope["data"]["pagination"]
    assert pag["limit"] == 25
    assert pag["offset"] == 0
    assert "status_counts" in envelope["data"]


def test_market_fmv_dashboard_routes_registered_on_app(client: TestClient) -> None:
    """OpenAPI includes legacy market-sales and P39-07 ingestion list paths."""
    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    paths = spec.json().get("paths", {})
    assert "/market-sales" in paths
    assert "/api/v1/market/market-ingestion/batches" in paths
