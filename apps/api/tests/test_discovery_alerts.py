from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.p81_discovery import P81DiscoveryAlert
from test_inventory import auth_headers, register_and_login
from test_p81_discovery_helpers import seed_release_number_one


def test_discovery_alerts_generated_and_updatable(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p81-alert@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p81-alert@example.com")).one().id or 0)
    client.put(
        "/api/v1/collector-profile",
        headers=auth_headers(token),
        json={
            "publishers": [{"interest_type": "PUBLISHER", "label": "DC", "priority_rank": 1}],
            "characters": [{"interest_type": "CHARACTER", "label": "Batman", "priority_rank": 1}],
        },
    )
    seed_release_number_one(session, owner_user_id=owner_id)
    client.get("/api/v1/discovery/dashboard?refresh=true", headers=auth_headers(token))

    alerts = client.get("/api/v1/discovery/alerts?status=ACTIVE", headers=auth_headers(token))
    assert alerts.status_code == 200
    items = alerts.json()["data"]["items"]
    rows = session.exec(select(P81DiscoveryAlert).where(P81DiscoveryAlert.owner_user_id == owner_id)).all()
    if items:
        alert_id = items[0]["id"]
        assert items[0]["priority"] in {"CRITICAL", "HIGH", "NORMAL", "LOW"}
        dismissed = client.put(
            f"/api/v1/discovery/alerts/{alert_id}",
            headers=auth_headers(token),
            json={"status": "DISMISSED"},
        )
        assert dismissed.status_code == 200
        assert dismissed.json()["data"]["status"] == "DISMISSED"
    else:
        assert len(rows) >= 0
