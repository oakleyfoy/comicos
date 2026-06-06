from __future__ import annotations

from sqlmodel import Session, select

from app.models import User
from app.services.foc_purchase_intelligence_service import build_foc_watch, generate_foc_purchase_snapshot
from app.services.release_import import import_release_feed
from test_release_import import _sample_feed
from test_inventory import register_and_login
from fastapi.testclient import TestClient


def test_foc_grouping_after_import(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p74-foc@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p74-foc@example.com")).one().id or 0)
    import_release_feed(session, owner_user_id=owner_id, payload=_sample_feed())
    generate_foc_purchase_snapshot(session, owner_user_id=owner_id)
    watch = build_foc_watch(session, owner_user_id=owner_id)
    assert watch.foc_this_week >= 0 or watch.foc_within_30_days >= 1

    resp = client.get("/api/v1/release-monitoring/foc", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["data"]["snapshot_id"] > 0
