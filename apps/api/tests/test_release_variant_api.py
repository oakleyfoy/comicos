from __future__ import annotations

from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_release_variant_api(client: TestClient) -> None:
    token = register_and_login(client, "variant-api@example.com")
    variants = client.get("/api/v1/release-intelligence/variants", headers=auth_headers(token))
    assert variants.status_code == 200
    top = client.get("/api/v1/release-intelligence/variants/top", headers=auth_headers(token))
    assert top.status_code == 200
    ratio = client.get("/api/v1/release-platform/ratio-variants", headers=auth_headers(token))
    assert ratio.status_code == 200
    recent = client.get("/api/v1/release-platform/new-variants", headers=auth_headers(token))
    assert recent.status_code == 200
    dashboard = client.get("/api/v1/release-intelligence/dashboard", headers=auth_headers(token))
    assert dashboard.status_code == 200
    assert "variant_count" in dashboard.json()["data"]
