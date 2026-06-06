from __future__ import annotations

from decimal import Decimal

from sqlmodel import Session, select

from app.models import User
from app.schemas.recommendation_outcome import P73RecommendationOutcomeCreatePayload
from app.services.recommendation_feedback_engine import run_recommendation_feedback_engine
from app.services.recommendation_outcome_service import create_outcome
from fastapi.testclient import TestClient
from test_inventory import register_and_login


def test_quality_dashboard_payload(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p73-qdash@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p73-qdash@example.com")).one().id or 0)
    create_outcome(
        session,
        owner_user_id=owner_id,
        payload=P73RecommendationOutcomeCreatePayload(
            recommendation_id="qd-1",
            recommendation_type="SELL",
            recommendation_category="VARIANT",
            actual_roi_pct=Decimal("25"),
        ),
    )
    dash = run_recommendation_feedback_engine(session, owner_user_id=owner_id, persist=True)
    assert dash.bundle_snapshot_id > 0
    assert dash.confidence.sell_confidence >= 0
    assert len(dash.category_calibration) == 7

    resp = client.get(
        "/api/v1/recommendation-feedback/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["bundle_snapshot_id"] > 0
    assert body["confidence"]["sell_confidence"] >= 0
