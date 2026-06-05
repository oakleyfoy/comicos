from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from test_inventory import register_and_login
from test_p64_collector_assistant import seed_p64_upstream


def test_automation_subscriptions_and_run(client: TestClient, session: Session) -> None:
    email = "p65-auto@example.com"
    token = register_and_login(client, email)
    seed_p64_upstream(client, session, email)
    headers = {"Authorization": f"Bearer {token}"}
    subs = client.get("/api/v1/collector-automation/subscriptions", headers=headers)
    assert subs.status_code == 200
    assert len(subs.json()["data"]["subscriptions"]) >= 3
    run = client.post("/api/v1/collector-automation/run/DAILY_OPPORTUNITY_DIGEST", headers=headers)
    assert run.status_code == 200
    assert run.json()["data"]["status"] == "SUCCESS"
    runs = client.get("/api/v1/collector-automation/runs/latest", headers=headers)
    assert runs.status_code == 200
    assert len(runs.json()["data"]["runs"]) >= 1
