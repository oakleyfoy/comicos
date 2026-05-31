from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import InventoryCopy, Order, User
from app.models.spec_intelligence import SpecRecommendationReview
from spec_test_helpers import seed_spec_release_inputs
from test_inventory import auth_headers, register_and_login


def test_spec_intelligence_api(client: TestClient) -> None:
    owner_email = "spec-api@example.com"
    outsider_email = "spec-api-outsider@example.com"
    owner_token = register_and_login(client, owner_email)
    outsider_token = register_and_login(client, outsider_email)

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == owner_email)).one()
        owner_user_id = int(owner.id or 0)
        seed_spec_release_inputs(session, owner_user_id=owner_user_id)
        inventory_count_before = len(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all())
        order_count_before = len(session.exec(select(Order).where(Order.user_id == owner_user_id)).all())

    scoring = client.post("/api/v1/spec-intelligence/run/scoring", headers=auth_headers(owner_token))
    recommendations = client.post("/api/v1/spec-intelligence/run/recommendations", headers=auth_headers(owner_token))
    weekly = client.post("/api/v1/spec-intelligence/run/weekly-buy-list", headers=auth_headers(owner_token))
    dashboard = client.get("/api/v1/spec-intelligence/dashboard", headers=auth_headers(owner_token))
    scores = client.get("/api/v1/spec-intelligence/scores", headers=auth_headers(owner_token))
    recs = client.get("/api/v1/spec-intelligence/recommendations", headers=auth_headers(owner_token))
    buy_lists = client.get("/api/v1/spec-intelligence/weekly-buy-lists", headers=auth_headers(owner_token))
    executions = client.get("/api/v1/spec-intelligence/executions", headers=auth_headers(owner_token))
    outsider_scores = client.get("/api/v1/spec-intelligence/scores", headers=auth_headers(outsider_token))

    assert scoring.status_code == 200, scoring.text
    assert recommendations.status_code == 200, recommendations.text
    assert weekly.status_code == 200, weekly.text
    assert dashboard.status_code == 200, dashboard.text
    assert scores.status_code == 200, scores.text
    assert recs.status_code == 200, recs.text
    assert buy_lists.status_code == 200, buy_lists.text
    assert executions.status_code == 200, executions.text
    assert outsider_scores.json()["data"]["items"] == []

    recommendation_id = recommendations.json()["data"]["recommendations"][0]["id"]
    reviewed = client.post(
        f"/api/v1/spec-intelligence/recommendations/{recommendation_id}/reviewed",
        headers=auth_headers(owner_token),
        json={"review_notes": "Track manually"},
    )
    accepted = client.post(
        f"/api/v1/spec-intelligence/recommendations/{recommendation_id}/accepted",
        headers=auth_headers(owner_token),
        json={"review_notes": "Good candidate"},
    )
    dismissed = client.post(
        f"/api/v1/spec-intelligence/recommendations/{recommendation_id}/dismissed",
        headers=auth_headers(owner_token),
        json={"review_notes": "Skip this week"},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert accepted.status_code == 200, accepted.text
    assert dismissed.status_code == 200, dismissed.text

    with Session(get_engine()) as session:
        inventory_count_after = len(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all())
        order_count_after = len(session.exec(select(Order).where(Order.user_id == owner_user_id)).all())
        reviews = session.exec(select(SpecRecommendationReview)).all()
        assert len(reviews) >= 3

    assert inventory_count_before == inventory_count_after
    assert order_count_before == order_count_after
