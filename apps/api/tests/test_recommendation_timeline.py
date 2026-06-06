from __future__ import annotations

from sqlmodel import Session, select

from app.models import User
from app.schemas.recommendation_event import P73RecommendationEventCreatePayload
from app.schemas.recommendation_outcome import P73RecommendationOutcomeCreatePayload
from app.services.recommendation_outcome_service import append_event, build_timeline, create_outcome
from test_inventory import register_and_login
from fastapi.testclient import TestClient


def test_lifecycle_timeline_order(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p73-timeline@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p73-timeline@example.com")).one().id or 0)
    outcome = create_outcome(
        session,
        owner_user_id=owner_id,
        payload=P73RecommendationOutcomeCreatePayload(
            recommendation_id="rec-timeline-1",
            series="X-Men",
            issue="1",
            recommendation_type="GRADE",
            inventory_copy_id=None,
        ),
    )
    for et in ("VIEWED", "PURCHASED", "HELD", "GRADED", "SOLD"):
        append_event(
            session,
            owner_user_id=owner_id,
            outcome_id=outcome.id,
            payload=P73RecommendationEventCreatePayload(event_type=et),
        )
    timeline = build_timeline(session, owner_user_id=owner_id, outcome_id=outcome.id)
    assert timeline[0].event_type == "RECOMMENDED"
    assert timeline[-1].event_type == "SOLD"
    assert all(timeline[i].created_at <= timeline[i + 1].created_at for i in range(len(timeline) - 1))

    detail = client.get(
        f"/api/v1/recommendation-feedback/outcomes/{outcome.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail.status_code == 200
    assert len(detail.json()["data"]["timeline"]) >= 6
