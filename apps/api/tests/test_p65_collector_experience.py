from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from test_inventory import register_and_login
from test_p64_collector_assistant import seed_p64_upstream
from test_p63_market_helpers import owner_id


def test_p65_certification_non_mutation(client: TestClient, session: Session) -> None:
    email = "p65-cert@example.com"
    token = register_and_login(client, email)
    oid = seed_p64_upstream(client, session, email)
    headers = {"Authorization": f"Bearer {token}"}
    cert = client.get("/api/v1/collector-workspace/platform/certification", headers=headers)
    assert cert.status_code == 200
    data = cert.json()["data"]
    assert data["non_mutation"]["certified"] is True
    assert data["checks"]["task_generation"] is True
    assert data["checks"]["owner_isolation"] is True
    assert data["certified"] is True


def test_owner_isolation_tasks(client: TestClient, session: Session) -> None:
    email_a = "p65-owner-a@example.com"
    email_b = "p65-owner-b@example.com"
    token_a = register_and_login(client, email_a)
    register_and_login(client, email_b)
    seed_p64_upstream(client, session, email_a)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    client.post("/api/v1/collector-workspace/tasks/build", headers=headers_a)
    oid_b = owner_id(session, email_b)
    from app.services.collector_workspace_service import get_latest_task_snapshot

    snap_b = get_latest_task_snapshot(session, owner_user_id=oid_b)
    assert snap_b is None
