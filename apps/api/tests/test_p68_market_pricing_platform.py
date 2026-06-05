from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_p68_certification_and_build(client: TestClient) -> None:
    token = register_and_login(client, "p68-plat@example.com")
    headers = auth_headers(token)
    cert = client.get("/api/v1/market-pricing/certification", headers=headers)
    assert cert.status_code == 200
    assert cert.json()["data"]["certified"] is True
    build = client.post("/api/v1/market-pricing/snapshots/build", headers=headers)
    assert build.status_code == 200
