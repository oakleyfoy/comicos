from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from test_p63_market_helpers import owner_id
from test_p66_helpers import seed_p66_owner
from test_inventory import register_and_login


def test_p66_certification(client: TestClient, session: Session) -> None:
    email = "p66-cert@example.com"
    _, token = seed_p66_owner(client, session, email)
    headers = {"Authorization": f"Bearer {token}"}
    cert = client.get("/api/v1/variant-decision/platform/certification", headers=headers)
    assert cert.status_code == 200
    data = cert.json()["data"]
    assert data["non_mutation"]["certified"] is True
    assert data["checks"]["variant_scoring"] is True
    assert data["certified"] is True


def test_integration_latest(client: TestClient, session: Session) -> None:
    email = "p66-int@example.com"
    _, token = seed_p66_owner(client, session, email)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/variant-decision/platform/build", headers=headers)
    resp = client.get("/api/v1/variant-decision/integration/latest", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["readiness_status"] == "SUCCESS"


def test_owner_isolation(client: TestClient, session: Session) -> None:
    email_a = "p66-iso-a@example.com"
    email_b = "p66-iso-b@example.com"
    _, token_a = seed_p66_owner(client, session, email_a)
    register_and_login(client, email_b)
    headers = {"Authorization": f"Bearer {token_a}"}
    client.post("/api/v1/variant-decision/platform/build", headers=headers)
    from app.services.variant_decision_engine import get_latest_variant_decision_snapshot

    assert get_latest_variant_decision_snapshot(session, owner_user_id=owner_id(session, email_b)) is None
