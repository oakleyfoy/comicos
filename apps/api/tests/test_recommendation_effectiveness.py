from __future__ import annotations

from decimal import Decimal

from sqlmodel import Session, select

from app.models import User
from app.schemas.recommendation_outcome import P73RecommendationOutcomeCreatePayload
from app.services.recommendation_analytics_service import _accuracy_metrics, _load_owner_data
from app.services.recommendation_feedback_engine import build_recommendation_effectiveness
from app.services.recommendation_outcome_service import create_outcome
from fastapi.testclient import TestClient
from test_inventory import register_and_login


def test_effectiveness_buy_accuracy_label(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p73-eff@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p73-eff@example.com")).one().id or 0)
    create_outcome(
        session,
        owner_user_id=owner_id,
        payload=P73RecommendationOutcomeCreatePayload(
            recommendation_id="eff-1",
            recommendation_type="BUY",
            expected_roi_pct=Decimal("42"),
            actual_roi_pct=Decimal("39"),
        ),
    )
    outcomes, events = _load_owner_data(session, owner_id)
    eff = build_recommendation_effectiveness(outcomes, _accuracy_metrics(outcomes, events))
    buy = next(t for t in eff.by_type if t.recommendation_type == "BUY")
    assert buy.expected_roi_pct == 42.0
    assert buy.actual_roi_pct == 39.0
    assert buy.accuracy_label == "HIGH"

    resp = client.get(
        "/api/v1/recommendation-feedback/effectiveness",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    by_type = resp.json()["data"]["by_type"]
    assert any(r["recommendation_type"] == "BUY" for r in by_type)
