from __future__ import annotations

from sqlmodel import Session, select

from app.models import User
from app.models.release_event_history import P74ReleaseEventHistory
from app.services.release_import import import_release_feed
from test_release_import import _sample_feed
from test_inventory import register_and_login
from fastapi.testclient import TestClient


def test_event_history_after_import(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p74-hist@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p74-hist@example.com")).one().id or 0)
    import_release_feed(session, owner_user_id=owner_id, payload=_sample_feed())
    events = session.exec(
        select(P74ReleaseEventHistory).where(P74ReleaseEventHistory.owner_user_id == owner_id)
    ).all()
    assert any(e.event_type == "DISCOVERED" for e in events)

    resp = client.get(
        "/api/v1/release-monitoring/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
