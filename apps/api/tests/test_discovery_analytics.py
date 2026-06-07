from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.p81_discovery_analytics import P81DiscoveryAnalyticsSnapshot
from test_inventory import auth_headers, register_and_login
from test_p81_discovery_helpers import seed_release_number_one


def test_discovery_analytics_dashboard_and_snapshots(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p81-analytics@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p81-analytics@example.com")).one().id or 0)
    seed_release_number_one(session, owner_user_id=owner_id)
    client.post("/api/v1/discovery/dashboard/refresh", headers=auth_headers(token))

    analytics = client.get("/api/v1/discovery/analytics", headers=auth_headers(token))
    assert analytics.status_code == 200
    assert analytics.json()["data"]["activity"]["opportunities_discovered"] >= 1

    opp = client.get("/api/v1/discovery/opportunity-analytics", headers=auth_headers(token))
    assert opp.status_code == 200
    assert isinstance(opp.json()["data"]["categories"], list)

    dash = client.post("/api/v1/discovery/analytics-dashboard/refresh", headers=auth_headers(token))
    assert dash.status_code == 200, dash.text
    d = dash.json()["data"]
    assert d["activity"]["opportunities_discovered"] >= 1
    assert "personalization_impact" in d
    assert d["snapshot_ids"]["activity"] is not None

    snaps = session.exec(select(P81DiscoveryAnalyticsSnapshot).where(P81DiscoveryAnalyticsSnapshot.owner_user_id == owner_id)).all()
    assert len(snaps) >= 1
