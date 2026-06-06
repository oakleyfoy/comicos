"""P77 budget API smoke tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_collector_budget_tracking(client: TestClient) -> None:
    token = register_and_login(client, "p77-budget-spec@example.com")
    h = auth_headers(token)
    put = client.put(
        "/api/v1/collector-profile/budget",
        headers=h,
        json={"monthly_budget": 250, "budget_period": "MONTHLY"},
    )
    assert put.status_code == 200
    status = client.get("/api/v1/collector-profile/budget-status", headers=h)
    assert status.status_code == 200
    assert status.json()["data"]["monthly_budget"] == 250
