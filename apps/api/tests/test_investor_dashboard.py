from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_investor_dashboard_requires_snapshots(client: TestClient) -> None:
    token = register_and_login(client, "p67-inv@example.com")
    headers = auth_headers(token)
    empty = client.get("/api/v1/investor-dashboard/latest", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["data"]["status"] == "EMPTY"
    client.post("/api/v1/portfolio-analytics/platform/build", headers=headers)
    res = client.get("/api/v1/investor-dashboard/latest", headers=headers)
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "OK"
    assert "portfolio_health_score" in res.json()["data"]
