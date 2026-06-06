from fastapi.testclient import TestClient

from app.services.ebay_oauth import EbayOAuthAccessToken
from test_inventory import auth_headers, register_and_login


def test_providers_registry(client: TestClient) -> None:
    token = register_and_login(client, "p68-prov@example.com")
    res = client.get("/api/v1/market-pricing/providers", headers=auth_headers(token))
    assert res.status_code == 200
    providers = res.json()["data"]["providers"]
    types = {p["provider_type"] for p in providers}
    assert "INTERNAL_SALE" in types
    assert "EBAY_SOLD" in types


def test_providers_health_reports_ebay_authenticated(client: TestClient, monkeypatch) -> None:
    token = register_and_login(client, "p68-health@example.com")
    monkeypatch.setenv("EBAY_API_CLIENT_ID", "client-id")
    monkeypatch.setenv("EBAY_API_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("EBAY_ENVIRONMENT", "production")
    from app.core.config import get_settings

    get_settings.cache_clear()

    monkeypatch.setattr(
        "app.services.market_pricing_provider_health.acquire_ebay_oauth_access_token",
        lambda **kwargs: EbayOAuthAccessToken(
            access_token="token",
            token_type="Bearer",
            expires_in=7200,
            scope="https://api.ebay.com/oauth/api_scope",
            environment="production",
        ),
    )
    monkeypatch.setattr(
        "app.services.market_pricing_provider_health.probe_ebay_sold_search_availability",
        lambda **kwargs: (True, None),
    )

    res = client.get("/api/v1/market-pricing/providers/health", headers=auth_headers(token))
    assert res.status_code == 200
    providers = res.json()["data"]["providers"]
    ebay = next(row for row in providers if row["provider_type"] == "EBAY_SOLD")
    assert ebay["health_status"] == "AUTHENTICATED"
    assert ebay["enabled"] is True
    assert ebay["metadata_json"]["sold_search_available"] is True
    assert ebay["metadata_json"]["import_available"] is True
    assert ebay["metadata_json"]["last_error"] is None
