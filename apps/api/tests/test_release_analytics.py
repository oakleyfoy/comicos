from __future__ import annotations

from sqlmodel import Session, select

from app.models.p74_release_analytics import P74ReleaseAnalyticsSnapshot
from app.services.release_analytics_service import build_release_analytics_read, persist_release_analytics
from app.services.release_import import import_release_feed
from fastapi.testclient import TestClient
from test_inventory import register_and_login
from test_release_import import _sample_feed

from app.models import User


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_release_analytics_snapshot_persisted(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p74-analytics@example.com")
    owner_id = _owner_id(session, "p74-analytics@example.com")
    import_release_feed(session, owner_user_id=owner_id, payload=_sample_feed())
    snap = persist_release_analytics(session, owner_user_id=owner_id)
    assert snap.id is not None
    assert snap.outcomes_tracked >= 0
    rows = session.exec(
        select(P74ReleaseAnalyticsSnapshot).where(P74ReleaseAnalyticsSnapshot.owner_user_id == owner_id)
    ).all()
    assert rows

    read = build_release_analytics_read(session, owner_user_id=owner_id)
    assert read.snapshot_id > 0

    resp = client.get(
        "/api/v1/release-monitoring/analytics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["snapshot_id"] > 0
    assert "platform_confidence_pct" in data
