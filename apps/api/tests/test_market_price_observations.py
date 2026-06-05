from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_manual_observation(client: TestClient) -> None:
    token = register_and_login(client, "p68-man@example.com")
    headers = auth_headers(token)
    res = client.post(
        "/api/v1/market-pricing/manual",
        headers=headers,
        json={"title": "Test Book", "publisher": "DC", "issue_number": "1", "total_price": 19.99},
    )
    assert res.status_code == 200
    assert res.json()["data"]["provider"] == "MANUAL"
