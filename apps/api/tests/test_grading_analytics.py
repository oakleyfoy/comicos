from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_grading_analytics_build(client: TestClient) -> None:
    token = register_and_login(client, "p67-grade@example.com")
    headers = auth_headers(token)
    res = client.post("/api/v1/grading-analytics/build", headers=headers)
    assert res.status_code == 200
    latest = client.get("/api/v1/grading-analytics/latest", headers=headers)
    assert latest.status_code == 200
