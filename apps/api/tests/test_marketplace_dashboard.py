from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.services.marketplace_seed import ensure_marketplace_definitions
from test_inventory import auth_headers, register_and_login


def test_marketplace_dashboard_endpoints_and_owner_scoping(client: TestClient) -> None:
    owner_token = register_and_login(client, "marketplace-dashboard-owner@example.com")
    outsider_token = register_and_login(client, "marketplace-dashboard-outsider@example.com")

    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)

    dashboard = client.get("/api/v1/marketplace-dashboard", headers=auth_headers(owner_token))
    health = client.get("/api/v1/marketplace-dashboard/health", headers=auth_headers(owner_token))
    analytics = client.get("/api/v1/marketplace-dashboard/analytics", headers=auth_headers(owner_token))
    validation = client.get("/api/v1/marketplace-dashboard/validation", headers=auth_headers(owner_token))
    connectors = client.get("/api/v1/marketplace-dashboard/connectors", headers=auth_headers(owner_token))
    accounts = client.get("/api/v1/marketplace-dashboard/accounts", headers=auth_headers(owner_token))
    denied = client.get("/api/v1/marketplace-dashboard", headers=auth_headers(outsider_token))

    assert dashboard.status_code == 200, dashboard.text
    assert health.status_code == 200, health.text
    assert analytics.status_code == 200, analytics.text
    assert validation.status_code == 200, validation.text
    assert connectors.status_code == 200, connectors.text
    assert accounts.status_code == 200, accounts.text

    body = dashboard.json()["data"]
    outsider_body = denied.json()["data"]
    assert "summary_cards" in body
    assert outsider_body["summary_cards"]["listings"] == 0
    assert "validation_checks" in body
    assert "health_components" in body
    assert connectors.json()["data"]["total_items"] >= 4
    assert len(validation.json()["data"]["checks"]) == 6
