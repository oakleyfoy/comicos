from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from test_inventory import auth_headers, register_and_login


def test_command_center_payload(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p84-cc@example.com")
    resp = client.get("/api/v1/collector-command-center", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert resp.status_code == 200
    assert data.get("status") in {"OK", "ERROR"}
    assert "budget_status" in data
    assert data.get("marketplace_deals") == []
