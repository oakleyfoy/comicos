from __future__ import annotations

from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_collector_analytics_endpoints(client: TestClient) -> None:
    token = register_and_login(client, "p77-analytics@example.com")
    h = auth_headers(token)
    client.put(
        "/api/v1/collector-profile/budget",
        headers=h,
        json={"monthly_budget": 500, "budget_period": "MONTHLY"},
    )

    analytics = client.get("/api/v1/collector-profile/analytics", headers=h)
    assert analytics.status_code == 200
    assert "profile_summary" in analytics.json()["data"]

    budget = client.get("/api/v1/collector-profile/budget-analytics", headers=h)
    assert budget.status_code == 200
    assert budget.json()["data"]["forecast"]["status"] in {"ON TRACK", "AT RISK", "OVER BUDGET"}

    goals = client.get("/api/v1/collector-profile/goal-analytics", headers=h)
    assert goals.status_code == 200

    rec = client.get("/api/v1/collector-profile/recommendation-analytics", headers=h)
    assert rec.status_code == 200
    assert "impact" in rec.json()["data"]

    dash = client.get("/api/v1/collector-profile/analytics-dashboard", headers=h)
    assert dash.status_code == 200, dash.text
    body = dash.json()["data"]
    assert body.get("analytics_snapshot_id") is not None
    assert "profile_influence" in body
    assert "personalization_performance" in body
