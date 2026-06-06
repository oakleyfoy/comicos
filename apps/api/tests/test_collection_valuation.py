from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from test_inventory import auth_headers, register_and_login


def test_collection_forecast_horizons(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p83-forecast@example.com")
    resp = client.get("/api/v1/collection-valuation/forecast", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["current_value"] >= 0
    horizons = {h["horizon"] for h in data["horizons"]}
    assert horizons == {"30_DAYS", "90_DAYS", "6_MONTHS", "12_MONTHS"}


def test_collection_risk_score(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p83-risk@example.com")
    resp = client.get("/api/v1/collection-valuation/risk", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["risk_category"] in {"LOW_RISK", "MODERATE_RISK", "HIGH_RISK"}
    assert 0 <= data["risk_score"] <= 100


def test_collection_valuation_dashboard(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p83-dash@example.com")
    resp = client.get("/api/v1/collection-valuation/dashboard", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "forecast" in data and "risk" in data and "optimization" in data
