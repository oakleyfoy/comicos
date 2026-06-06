from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_p71_platform_build_and_certify(client: TestClient) -> None:
    token = register_and_login(client, "p71-platform@example.com")
    headers = auth_headers(token)
    build = client.post("/api/v1/sell-intelligence/platform/build", headers=headers)
    assert build.status_code == 200
    assert len(build.json()["data"]["steps"]) >= 5
    cert = client.get("/api/v1/sell-intelligence/platform/certification", headers=headers)
    assert cert.status_code == 200
    assert cert.json()["data"]["certified"] is True


def test_p71_endpoints_after_build(client: TestClient) -> None:
    token = register_and_login(client, "p71-api@example.com")
    headers = auth_headers(token)
    client.post("/api/v1/sell-intelligence/platform/build", headers=headers)
    for path in (
        "/api/v1/sell-intelligence/exit-recommendations",
        "/api/v1/sell-intelligence/listing-intelligence",
        "/api/v1/sell-intelligence/liquidity",
        "/api/v1/sell-intelligence/exit-queue",
        "/api/v1/sell-intelligence/dashboard",
    ):
        res = client.get(path, headers=headers)
        assert res.status_code == 200, path


def test_p71_owner_isolation(client: TestClient) -> None:
    token_a = register_and_login(client, "p71-a@example.com")
    client.post("/api/v1/sell-intelligence/platform/build", headers=auth_headers(token_a))
    token_b = register_and_login(client, "p71-b@example.com")
    res = client.get("/api/v1/sell-intelligence/dashboard", headers=auth_headers(token_b))
    assert res.status_code == 404
