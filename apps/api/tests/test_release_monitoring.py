from __future__ import annotations

from test_release_import import _sample_feed
from app.services.release_import import import_release_feed
from app.services.release_monitoring_service import build_upcoming_releases
from sqlmodel import Session, select
from app.models import User
from test_inventory import register_and_login
from fastapi.testclient import TestClient


def test_upcoming_releases_after_import(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p74-mon@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p74-mon@example.com")).one().id or 0)
    import_release_feed(session, owner_user_id=owner_id, payload=_sample_feed())
    upcoming = build_upcoming_releases(session, owner_user_id=owner_id)
    assert len(upcoming.next_30_days) >= 1

    resp = client.get(
        "/api/v1/release-monitoring/upcoming",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["next_30_days"]
