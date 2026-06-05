from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_recommendation_performance_build(client: TestClient) -> None:
    token = register_and_login(client, "p67-rec@example.com")
    headers = auth_headers(token)
    res = client.post("/api/v1/recommendation-performance/build", headers=headers)
    assert res.status_code == 200
    latest = client.get("/api/v1/recommendation-performance/latest", headers=headers)
    assert latest.status_code == 200
