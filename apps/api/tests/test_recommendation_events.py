from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.recommendation_action_event import P73RecommendationActionEvent
from app.schemas.recommendation_event import P73RecommendationEventCreatePayload
from app.schemas.recommendation_outcome import P73RecommendationOutcomeCreatePayload
from app.services.recommendation_outcome_service import append_event, create_outcome
from test_inventory import register_and_login


def test_append_multiple_events(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p73-events@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p73-events@example.com")).one().id or 0)
    outcome = create_outcome(
        session,
        owner_user_id=owner_id,
        payload=P73RecommendationOutcomeCreatePayload(
            recommendation_id="rec-p73-1",
            series="Absolute Batman",
            issue="1",
            recommendation_type="BUY",
            recommendation_category="PURCHASE",
        ),
    )
    append_event(
        session,
        owner_user_id=owner_id,
        outcome_id=outcome.id,
        payload=P73RecommendationEventCreatePayload(event_type="VIEWED"),
    )
    append_event(
        session,
        owner_user_id=owner_id,
        outcome_id=outcome.id,
        payload=P73RecommendationEventCreatePayload(event_type="PURCHASED"),
    )
    events = session.exec(
        select(P73RecommendationActionEvent).where(P73RecommendationActionEvent.outcome_id == outcome.id)
    ).all()
    assert len(events) >= 3

    resp = client.post(
        f"/api/v1/recommendation-feedback/outcomes/{outcome.id}/event",
        headers={"Authorization": f"Bearer {token}"},
        json={"event_type": "HELD"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["event_type"] == "HELD"
