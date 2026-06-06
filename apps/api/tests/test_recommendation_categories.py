from __future__ import annotations

from decimal import Decimal

from sqlmodel import Session, select

from app.models import User
from app.schemas.recommendation_outcome import P73RecommendationOutcomeCreatePayload
from app.services.recommendation_analytics_service import build_recommendation_categories
from app.services.recommendation_outcome_service import create_outcome
from fastapi.testclient import TestClient
from test_inventory import register_and_login


def test_category_performance_buy_grade(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p73-cat@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p73-cat@example.com")).one().id or 0)
    create_outcome(
        session,
        owner_user_id=owner_id,
        payload=P73RecommendationOutcomeCreatePayload(
            recommendation_id="c-buy",
            recommendation_type="BUY",
        ),
    )
    create_outcome(
        session,
        owner_user_id=owner_id,
        payload=P73RecommendationOutcomeCreatePayload(
            recommendation_id="c-grade",
            recommendation_type="GRADE",
            expected_roi_pct=Decimal("55"),
            actual_roi_pct=Decimal("58"),
        ),
    )
    cats = build_recommendation_categories(session, owner_user_id=owner_id)
    by_type = {c.recommendation_type: c for c in cats}
    assert by_type["BUY"].recommendation_count >= 1
    assert by_type["GRADE"].average_roi_pct == 58.0

    resp = client.get(
        "/api/v1/recommendation-feedback/categories",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    payload = resp.json()["data"]
    items = payload["items"] if isinstance(payload, dict) else payload
    assert len(items) >= 4
