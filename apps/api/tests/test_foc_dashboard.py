from __future__ import annotations

from sqlmodel import Session, select

from app.models import User
from app.services.foc_purchase_intelligence_service import build_foc_dashboard
from app.services.release_import import import_release_feed
from test_release_import import _sample_feed
from test_inventory import register_and_login
from fastapi.testclient import TestClient


def test_foc_dashboard_payload(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p74-focdash@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p74-focdash@example.com")).one().id or 0)
    import_release_feed(session, owner_user_id=owner_id, payload=_sample_feed())
    dash = build_foc_dashboard(session, owner_user_id=owner_id)
    assert dash.snapshot_id > 0
    assert dash.recommended_preorders is not None
    assert dash.foc_watch.snapshot_id > 0

    resp = client.get(
        "/api/v1/release-monitoring/foc-dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["snapshot_id"] > 0
    assert "foc_this_week" in body
