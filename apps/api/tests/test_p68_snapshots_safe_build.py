"""P68 snapshot build returns controlled ERROR envelope, not HTTP 500."""

from __future__ import annotations

from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_p68_snapshots_latest_returns_200(client: TestClient) -> None:
    token = register_and_login(client, "p68-latest@example.com")
    resp = client.get("/api/v1/market-pricing/snapshots/latest", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data.get("status") in {"OK", "EMPTY"}
    assert "items" in data


def test_p68_snapshots_build_returns_200_envelope(client: TestClient) -> None:
    token = register_and_login(client, "p68-build@example.com")
    resp = client.post("/api/v1/market-pricing/snapshots/build", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data.get("status") in {"OK", "ERROR"}
    assert "built" in data
