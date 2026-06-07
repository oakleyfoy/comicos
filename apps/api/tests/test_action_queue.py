"""P90 action queue tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.p90_collector_alert import P90CollectorAlert, utc_now
from app.services.collector_action_queue_service import build_action_queue
from test_inventory import register_and_login


def test_action_queue_ranking(client: TestClient, session: Session) -> None:
    from app.models import User

    register_and_login(client, "p90-queue@example.com")
    user = session.exec(select(User).where(User.email == "p90-queue@example.com")).one()
    owner_id = int(user.id)
    session.add(
        P90CollectorAlert(
            owner_user_id=owner_id,
            alert_type="SELL_OPPORTUNITY",
            severity="MEDIUM",
            priority_score=50,
            title="Sell low",
            summary="",
            source_system="test",
            entity_type="x",
            entity_id=1,
            status="NEW",
            confidence="MEDIUM",
            reason="",
            action_route="/sell-candidates",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
    )
    session.add(
        P90CollectorAlert(
            owner_user_id=owner_id,
            alert_type="BUY_OPPORTUNITY",
            severity="HIGH",
            priority_score=90,
            title="Buy high",
            summary="",
            source_system="test",
            entity_type="x",
            entity_id=2,
            status="NEW",
            confidence="HIGH",
            reason="",
            action_route="/buy-opportunities",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
    )
    session.commit()
    queue = build_action_queue(session, owner_user_id=owner_id, limit=10)
    assert len(queue) == 2
    assert queue[0].title == "Buy high"
    assert queue[0].rank == 1
    assert queue[1].rank == 2
