"""Read-only regressions for inventory intelligence rollup endpoints."""

from fastapi.testclient import TestClient


def _register(client: TestClient, email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    response = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    return response.json()["access_token"]


def _hdr(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_inventory_intelligence_summary_stable_across_reads(client: TestClient) -> None:
    tok = _register(client, "intel-read-stable@example.com")
    hdrs = _hdr(tok)
    r1 = client.get("/inventory-intelligence/summary", headers=hdrs)
    r2 = client.get("/inventory-intelligence/summary", headers=hdrs)
    assert r1.status_code == r2.status_code == 200
    assert r1.json() == r2.json()
