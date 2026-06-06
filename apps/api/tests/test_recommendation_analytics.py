from __future__ import annotations

from decimal import Decimal

from sqlmodel import Session, select

from app.models import User
from app.schemas.recommendation_event import P73RecommendationEventCreatePayload
from app.schemas.recommendation_outcome import P73RecommendationOutcomeCreatePayload
from app.services.recommendation_analytics_service import build_recommendation_analytics
from app.services.recommendation_outcome_service import append_event, create_outcome
from fastapi.testclient import TestClient
from test_inventory import register_and_login


def _seed_owner(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_analytics_funnel_and_snapshot(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p73-analytics@example.com")
    owner_id = _seed_owner(session, "p73-analytics@example.com")
    create_outcome(
        session,
        owner_user_id=owner_id,
        payload=P73RecommendationOutcomeCreatePayload(
            recommendation_id="a-1",
            recommendation_type="BUY",
            recommendation_category="KEY_ISSUE",
            series="X-Men",
            issue="1",
            publisher="Marvel",
            expected_profit=Decimal("50"),
            expected_roi_pct=Decimal("30"),
        ),
    )
    o2 = create_outcome(
        session,
        owner_user_id=owner_id,
        payload=P73RecommendationOutcomeCreatePayload(
            recommendation_id="a-2",
            recommendation_type="GRADE",
            series="Spawn",
            issue="1",
        ),
    )
    append_event(
        session,
        owner_user_id=owner_id,
        outcome_id=o2.id,
        payload=P73RecommendationEventCreatePayload(event_type="VIEWED"),
    )
    analytics = build_recommendation_analytics(session, owner_user_id=owner_id, persist=True)
    assert analytics.funnel.recommendations_generated >= 2
    assert analytics.funnel.viewed >= 1
    assert analytics.snapshot_id > 0

    resp = client.get(
        "/api/v1/recommendation-feedback/analytics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["funnel"]["recommendations_generated"] >= 2
