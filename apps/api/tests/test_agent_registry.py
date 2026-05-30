from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.agent_seed import seed_foundational_agents
from test_inventory import auth_headers, register_and_login


def test_agent_registry_routes_registration_duplicate_enable_disable_and_listing(client: TestClient) -> None:
    token = register_and_login(client, "agent-registry@example.com")

    created = client.post(
        "/api/v1/agents",
        headers=auth_headers(token),
        json={
            "code": "Inventory_Agent_Runtime",
            "name": "Inventory Runtime Agent",
            "description": "Deterministic inventory execution placeholder.",
            "version": "1.0.0",
            "enabled": False,
            "capabilities": [
                {"capability_code": "inventory.write", "capability_name": "Inventory Write"},
                {"capability_code": "inventory.read", "capability_name": "Inventory Read"},
            ],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()["data"]
    agent_id = body["id"]
    assert body["code"] == "inventory_agent_runtime"
    assert body["enabled"] is False
    assert [row["capability_code"] for row in body["capabilities"]] == ["inventory.read", "inventory.write"]

    listing = client.get("/api/v1/agents?limit=20&offset=0", headers=auth_headers(token))
    assert listing.status_code == 200, listing.text
    listing_items = listing.json()["data"]["items"]
    assert [row["code"] for row in listing_items] == ["inventory_agent_runtime"]

    detail = client.get(f"/api/v1/agents/{agent_id}", headers=auth_headers(token))
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["id"] == agent_id

    duplicate = client.post(
        "/api/v1/agents",
        headers=auth_headers(token),
        json={
            "code": "inventory_agent_runtime",
            "name": "Duplicate Agent",
            "description": "Should be rejected.",
            "version": "1.0.1",
            "enabled": True,
            "capabilities": [],
        },
    )
    assert duplicate.status_code == 409, duplicate.text

    enabled = client.post(f"/api/v1/agents/{agent_id}/enable", headers=auth_headers(token))
    disabled = client.post(f"/api/v1/agents/{agent_id}/disable", headers=auth_headers(token))
    assert enabled.status_code == 200, enabled.text
    assert disabled.status_code == 200, disabled.text
    assert enabled.json()["data"]["enabled"] is True
    assert disabled.json()["data"]["enabled"] is False


def test_agent_seed_service_is_deterministic_and_disabled_by_default(client: TestClient, session) -> None:
    token = register_and_login(client, "agent-seed@example.com")

    first = seed_foundational_agents(session)
    second = seed_foundational_agents(session)

    assert [row.code for row in first] == [
        "inventory_agent",
        "pricing_agent",
        "market_agent",
        "analytics_agent",
        "marketplace_research_agent",
        "new_release_research_agent",
        "pricing_intelligence_agent",
        "catalog_intelligence_agent",
    ]
    assert [row.id for row in first] == [row.id for row in second]
    assert all(row.enabled is False for row in second)

    listing = client.get("/api/v1/agents?limit=20&offset=0", headers=auth_headers(token))
    assert listing.status_code == 200, listing.text
    assert [row["code"] for row in listing.json()["data"]["items"]] == [
        "inventory_agent",
        "pricing_agent",
        "market_agent",
        "analytics_agent",
        "marketplace_research_agent",
        "new_release_research_agent",
        "pricing_intelligence_agent",
        "catalog_intelligence_agent",
    ]
