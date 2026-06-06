from __future__ import annotations

from decimal import Decimal

from sqlmodel import Session, select

from app.models import User
from app.schemas.recommendation_event import P73RecommendationEventCreatePayload
from app.schemas.recommendation_outcome import P73RecommendationOutcomeCreatePayload
from app.services.recommendation_analytics_service import build_recommendation_profitability
from app.services.recommendation_outcome_service import append_event, create_outcome
from fastapi.testclient import TestClient
from test_inventory import register_and_login


def test_profitability_totals_and_breakdown(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p73-profit@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p73-profit@example.com")).one().id or 0)
    row = create_outcome(
        session,
        owner_user_id=owner_id,
        payload=P73RecommendationOutcomeCreatePayload(
            recommendation_id="p-1",
            recommendation_type="BUY",
            recommendation_category="VARIANT",
            series="Batman",
            issue="423",
            publisher="DC",
            expected_profit=Decimal("100"),
            expected_roi_pct=Decimal("40"),
        ),
    )
    append_event(
        session,
        owner_user_id=owner_id,
        outcome_id=row.id,
        payload=P73RecommendationEventCreatePayload(
            event_type="SOLD",
            metadata_json={"actual_profit": 120, "actual_roi_pct": 48},
        ),
    )
    profit = build_recommendation_profitability(session, owner_user_id=owner_id)
    assert profit.expected_profit == Decimal("100")
    assert profit.actual_profit == Decimal("120")
    assert profit.actual_roi_pct == 48.0
    assert any(b.key == "DC" for b in profit.by_publisher)

    resp = client.get(
        "/api/v1/recommendation-feedback/profitability",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert float(resp.json()["data"]["actual_profit"]) == 120.0
