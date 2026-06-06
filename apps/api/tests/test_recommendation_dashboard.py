from __future__ import annotations

from decimal import Decimal

from sqlmodel import Session, select

from app.models import User
from app.schemas.recommendation_event import P73RecommendationEventCreatePayload
from app.schemas.recommendation_outcome import P73RecommendationOutcomeCreatePayload
from app.services.recommendation_analytics_service import build_recommendation_performance_dashboard
from app.services.recommendation_outcome_service import append_event, create_outcome
from fastapi.testclient import TestClient
from test_inventory import register_and_login


def test_dashboard_sections_populated(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p73-dash@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p73-dash@example.com")).one().id or 0)
    win = create_outcome(
        session,
        owner_user_id=owner_id,
        payload=P73RecommendationOutcomeCreatePayload(
            recommendation_id="d-win",
            recommendation_type="BUY",
            recommendation_category="FIRST_APPEARANCE",
            series="Amazing",
            issue="129",
            expected_roi_pct=Decimal("20"),
            actual_roi_pct=Decimal("80"),
            actual_profit=Decimal("200"),
        ),
    )
    append_event(
        session,
        owner_user_id=owner_id,
        outcome_id=win.id,
        payload=P73RecommendationEventCreatePayload(event_type="PURCHASED"),
    )
    dash = build_recommendation_performance_dashboard(session, owner_user_id=owner_id)
    assert dash.performance_summary.snapshot_id > 0
    assert dash.adoption_metrics.purchase_rate_pct > 0
    assert dash.profitability_metrics.actual_profit >= Decimal("200")
    assert len(dash.category_performance) >= 4
    assert dash.top_wins

    resp = client.get(
        "/api/v1/recommendation-feedback/performance-dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["performance_summary"]["snapshot_id"] > 0
    assert body["top_wins"]
