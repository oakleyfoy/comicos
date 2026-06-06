from __future__ import annotations

from sqlmodel import Session, select

from app.models import User
from app.services.release_import import import_release_feed
from app.services.release_monitoring_service import build_release_monitoring_dashboard
from test_release_import import _sample_feed
from test_inventory import register_and_login
from fastapi.testclient import TestClient


def test_dashboard_populated(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p74-dash@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p74-dash@example.com")).one().id or 0)
    import_release_feed(session, owner_user_id=owner_id, payload=_sample_feed())
    dash = build_release_monitoring_dashboard(session, owner_user_id=owner_id, persist=True)
    assert dash.snapshot_id > 0
    assert dash.upcoming.next_30_days
    assert dash.recent_changes

    resp = client.get(
        "/api/v1/release-monitoring/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["snapshot_id"] > 0


def test_p74_03_analytics_dashboard_payload(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p74-analytics-dash@example.com")
    owner_id = int(
        session.exec(select(User).where(User.email == "p74-analytics-dash@example.com")).one().id or 0
    )
    import_release_feed(session, owner_user_id=owner_id, payload=_sample_feed())
    resp = client.get(
        "/api/v1/release-monitoring/analytics-dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["snapshot_id"] > 0
    assert "foc_accuracy" in body
    assert "quantity_accuracy" in body
    assert "best_categories" in body
    assert "certification_status" in body
