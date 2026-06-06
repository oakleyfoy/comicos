from __future__ import annotations

from sqlmodel import Session, select

from app.models import User
from app.schemas.recommendation_outcome import P73RecommendationOutcomeCreatePayload
from app.services.recommendation_feedback_engine import build_category_calibration
from app.services.recommendation_analytics_service import _load_owner_data
from app.services.recommendation_outcome_service import create_outcome
from fastapi.testclient import TestClient
from test_inventory import register_and_login


def test_calibration_categories(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p73-cal@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p73-cal@example.com")).one().id or 0)
    create_outcome(
        session,
        owner_user_id=owner_id,
        payload=P73RecommendationOutcomeCreatePayload(
            recommendation_id="cal-1",
            recommendation_type="BUY",
            recommendation_category="FIRST_APPEARANCE",
        ),
    )
    outcomes, _ = _load_owner_data(session, owner_id)
    rows = build_category_calibration(outcomes)
    assert len(rows) == 7
    fa = next(r for r in rows if r.calibration_category == "FIRST_APPEARANCE")
    assert fa.recommendation_count >= 1

    resp = client.get(
        "/api/v1/recommendation-feedback/calibration",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    payload = resp.json()["data"]
    items = payload["items"] if isinstance(payload, dict) else payload
    assert len(items) == 7
