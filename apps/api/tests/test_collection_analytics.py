from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_collection_analytics_build(client: TestClient) -> None:
    token = register_and_login(client, "p67-coll@example.com")
    res = client.post("/api/v1/collection-analytics/build", headers=auth_headers(token))
    assert res.status_code == 200
    assert res.json()["data"]["total_holdings"] >= 0
