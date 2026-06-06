from __future__ import annotations

from sqlmodel import Session, select

from app.models import User
from app.models.p74_foc_purchase import P74RecommendationChangeEvent
from app.services.foc_purchase_intelligence_service import CHANGE_NEW, generate_foc_purchase_snapshot
from app.services.release_import import import_release_feed
from test_release_import import _sample_feed
from test_inventory import register_and_login
from fastapi.testclient import TestClient


def test_initial_recommendation_emits_new_change(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p74-recchg@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p74-recchg@example.com")).one().id or 0)
    import_release_feed(session, owner_user_id=owner_id, payload=_sample_feed())
    generate_foc_purchase_snapshot(session, owner_user_id=owner_id)
    events = session.exec(
        select(P74RecommendationChangeEvent).where(P74RecommendationChangeEvent.owner_user_id == owner_id)
    ).all()
    assert any(e.change_kind == CHANGE_NEW for e in events)

    resp = client.get(
        "/api/v1/release-monitoring/recommendation-changes",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    items = data["items"] if isinstance(data, dict) else data
    assert len(items) >= 1
