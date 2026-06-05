from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from test_inventory import register_and_login
from test_p64_collector_assistant import seed_p64_upstream


def test_narratives_build_and_latest(client: TestClient, session: Session) -> None:
    email = "p65-narr@example.com"
    token = register_and_login(client, email)
    seed_p64_upstream(client, session, email)
    headers = {"Authorization": f"Bearer {token}"}
    build = client.post("/api/v1/collector-narratives/build", headers=headers)
    assert build.status_code == 200
    latest = client.get("/api/v1/collector-narratives/latest", headers=headers)
    assert latest.status_code == 200
    data = latest.json()["data"]
    assert data["snapshot_id"] >= 1
    kinds = {i["narrative_kind"] for i in data["items"]}
    assert "WEEKLY_BRIEFING" in kinds
