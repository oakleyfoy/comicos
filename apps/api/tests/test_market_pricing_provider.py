from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_providers_registry(client: TestClient) -> None:
    token = register_and_login(client, "p68-prov@example.com")
    res = client.get("/api/v1/market-pricing/providers", headers=auth_headers(token))
    assert res.status_code == 200
    providers = res.json()["data"]["providers"]
    types = {p["provider_type"] for p in providers}
    assert "INTERNAL_SALE" in types
    assert "EBAY_SOLD" in types
