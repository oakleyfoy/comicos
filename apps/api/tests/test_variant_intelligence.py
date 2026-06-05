from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from test_p66_helpers import seed_p66_owner


def test_variant_intelligence_build_and_latest(client: TestClient, session: Session) -> None:
    email = "p66-var@example.com"
    _, token = seed_p66_owner(client, session, email)
    headers = {"Authorization": f"Bearer {token}"}
    build = client.post("/api/v1/variant-intelligence/build", headers=headers)
    assert build.status_code == 200
    latest = client.get("/api/v1/variant-intelligence/latest", headers=headers)
    assert latest.status_code == 200
    data = latest.json()["data"]
    assert data["total_items"] >= 3
    tiers = {i["variant_tier"] for i in data["items"]}
    assert len(tiers) >= 1
