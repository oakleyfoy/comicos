from __future__ import annotations

from decimal import Decimal

from sqlmodel import Session, select

from app.models import User
from app.schemas.recommendation_outcome import P73RecommendationOutcomeCreatePayload
from app.services.recommendation_analytics_service import build_category_performance_read, _load_owner_data
from app.services.recommendation_confidence_service import build_recommendation_confidence
from app.services.recommendation_feedback_engine import load_grading_context, load_market_context
from app.services.recommendation_outcome_service import create_outcome
from fastapi.testclient import TestClient
from test_inventory import register_and_login


def test_confidence_scores_in_range(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p73-conf@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p73-conf@example.com")).one().id or 0)
    create_outcome(
        session,
        owner_user_id=owner_id,
        payload=P73RecommendationOutcomeCreatePayload(
            recommendation_id="conf-1",
            recommendation_type="BUY",
            expected_roi_pct=Decimal("40"),
            actual_roi_pct=Decimal("39"),
        ),
    )
    outcomes, _ = _load_owner_data(session, owner_id)
    conf = build_recommendation_confidence(
        outcomes=outcomes,
        category_rows=build_category_performance_read(outcomes),
        market=load_market_context(session, owner_user_id=owner_id),
        grading=load_grading_context(session, owner_user_id=owner_id),
    )
    assert 0 <= conf.buy_confidence <= 100

    resp = client.get(
        "/api/v1/recommendation-feedback/confidence",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert 0 <= data["buy_confidence"] <= 100
