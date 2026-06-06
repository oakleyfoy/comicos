from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.schemas.recommendation_outcome import P73RecommendationOutcomeCreatePayload
from app.services.recommendation_analytics_service import build_recommendation_performance
from app.services.recommendation_outcome_service import create_outcome
from test_inventory import auth_headers, register_and_login


def test_p73_recommendation_feedback_performance_endpoint(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p73-perf@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p73-perf@example.com")).one().id or 0)
    create_outcome(
        session,
        owner_user_id=owner_id,
        payload=P73RecommendationOutcomeCreatePayload(
            recommendation_id="perf-1",
            recommendation_type="SELL",
            actual_roi_pct=Decimal("15"),
        ),
    )
    perf = build_recommendation_performance(session, owner_user_id=owner_id)
    assert perf.snapshot_id > 0
    resp = client.get(
        "/api/v1/recommendation-feedback/performance",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["accuracy"]["average_return_pct"] == 15.0


def test_recommendation_performance_build(client: TestClient) -> None:
    token = register_and_login(client, "p67-rec@example.com")
    headers = auth_headers(token)
    res = client.post("/api/v1/recommendation-performance/build", headers=headers)
    assert res.status_code == 200
    latest = client.get("/api/v1/recommendation-performance/latest", headers=headers)
    assert latest.status_code == 200
