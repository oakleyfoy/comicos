from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from test_inventory import auth_headers, register_and_login


def test_collection_scenario_market_gain(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p83-scenario@example.com")
    resp = client.post(
        "/api/v1/collection-valuation/scenario",
        headers=auth_headers(token),
        json={"scenario_type": "MARKET_GAIN"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["scenario_type"] == "MARKET_GAIN"
    assert data["projected_value"] >= 0
    assert data["explanation"]
