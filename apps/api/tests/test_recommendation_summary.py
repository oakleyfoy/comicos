from __future__ import annotations

from sqlmodel import Session, select

from app.models import User
from app.schemas.recommendation_event import P73RecommendationEventCreatePayload
from app.schemas.recommendation_outcome import P73RecommendationOutcomeCreatePayload
from app.services.recommendation_outcome_service import append_event, build_feedback_summary, create_outcome
from test_inventory import register_and_login
from fastapi.testclient import TestClient


def test_summary_counts_and_attribution(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p73-summary@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p73-summary@example.com")).one().id or 0)
    buy = create_outcome(
        session,
        owner_user_id=owner_id,
        payload=P73RecommendationOutcomeCreatePayload(
            recommendation_id="rec-buy-1",
            recommendation_type="BUY",
            series="A",
            issue="1",
        ),
    )
    append_event(
        session,
        owner_user_id=owner_id,
        outcome_id=buy.id,
        payload=P73RecommendationEventCreatePayload(event_type="PURCHASED"),
    )
    summary = build_feedback_summary(session, owner_user_id=owner_id)
    assert summary.recommendations_created >= 1
    assert summary.purchased >= 1
    assert summary.attribution_samples >= 1

    resp = client.get(
        "/api/v1/recommendation-feedback/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["summary"]["recommendations_created"] >= 1
