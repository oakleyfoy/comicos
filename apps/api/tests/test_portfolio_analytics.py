from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_portfolio_analytics_build(client: TestClient) -> None:
    token = register_and_login(client, "p67-port@example.com")
    headers = auth_headers(token)
    res = client.post("/api/v1/portfolio-analytics/build", headers=headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert "total_cost_basis" in data
    latest = client.get("/api/v1/portfolio-analytics/latest", headers=headers)
    assert latest.status_code == 200
