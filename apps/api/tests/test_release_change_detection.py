from __future__ import annotations

from sqlmodel import Session, select

from app.models import User
from app.models.release_event_history import P74_EVENT_DISCOVERED, P74ReleaseChangeRecord
from app.services.release_import import import_release_feed
from test_release_import import _sample_feed
from test_inventory import register_and_login
from fastapi.testclient import TestClient


def test_import_creates_discovery_change(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p74-chg@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p74-chg@example.com")).one().id or 0)
    import_release_feed(session, owner_user_id=owner_id, payload=_sample_feed())
    changes = session.exec(
        select(P74ReleaseChangeRecord).where(P74ReleaseChangeRecord.owner_user_id == owner_id)
    ).all()
    assert any(c.change_type == "NEW_ISSUE" for c in changes)
    resp = client.get(
        "/api/v1/release-monitoring/changes",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    items = data["items"] if isinstance(data, dict) else data
    assert len(items) >= 1
