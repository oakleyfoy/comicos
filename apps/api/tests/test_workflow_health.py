from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from test_inventory import auth_headers, register_and_login


def test_workflow_health_api(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p85-health@example.com")
    resp = client.get("/api/v1/platform/workflow-health", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["health_score"] >= 0
    assert "issues" in data
    assert "inventory" in data["empty_workflows"]
