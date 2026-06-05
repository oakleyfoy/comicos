"""P67 platform integration tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_p67_platform_build_and_certify(client: TestClient) -> None:
    token = register_and_login(client, "p67-platform@example.com")
    headers = auth_headers(token)
    build = client.post("/api/v1/portfolio-analytics/platform/build", headers=headers)
    assert build.status_code == 200
    payload = build.json()["data"]
    assert len(payload["steps"]) == 5
    cert = client.get("/api/v1/portfolio-analytics/platform/certification", headers=headers)
    assert cert.status_code == 200
    assert cert.json()["data"]["certified"] is True


def test_p67_owner_isolation(client: TestClient) -> None:
    token_a = register_and_login(client, "p67-owner-a@example.com")
    client.post("/api/v1/portfolio-analytics/platform/build", headers=auth_headers(token_a))
    token_b = register_and_login(client, "p67-owner-b@example.com")
    latest = client.get("/api/v1/investor-dashboard/latest", headers=auth_headers(token_b))
    assert latest.status_code == 404
