from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import InventoryCopy, User
from app.models.grading_intelligence import GradingRecommendationReview
from grading_test_helpers import seed_analysis_with_condition_pipeline
from test_inventory import auth_headers, register_and_login


def test_grading_intelligence_api(client: TestClient) -> None:
    owner_email = "grading-api@example.com"
    outsider_email = "grading-api-outsider@example.com"
    owner_token = register_and_login(client, owner_email)
    outsider_token = register_and_login(client, outsider_email)

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == owner_email)).one()
        owner_user_id = int(owner.id or 0)
        analysis = seed_analysis_with_condition_pipeline(session, owner_user_id=owner_user_id)
        analysis_id = int(analysis.id)
        copy_count_before = len(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all())

    predict = client.post(
        "/api/v1/grading-intelligence/run/predictions",
        headers=auth_headers(owner_token),
        json={"analysis_id": analysis_id},
    )
    recs = client.post(
        "/api/v1/grading-intelligence/run/recommendations",
        headers=auth_headers(owner_token),
        json={"analysis_id": analysis_id},
    )
    roi = client.post(
        "/api/v1/grading-intelligence/run/roi",
        headers=auth_headers(owner_token),
        json={"analysis_id": analysis_id},
    )
    priorities = client.post("/api/v1/grading-intelligence/run/priorities", headers=auth_headers(owner_token))
    dashboard = client.get("/api/v1/grading-intelligence/dashboard", headers=auth_headers(owner_token))
    predictions = client.get("/api/v1/grading-intelligence/predictions", headers=auth_headers(owner_token))
    outsider_preds = client.get("/api/v1/grading-intelligence/predictions", headers=auth_headers(outsider_token))

    assert predict.status_code == 200, predict.text
    assert recs.status_code == 200, recs.text
    assert roi.status_code == 200, roi.text
    assert priorities.status_code == 200, priorities.text
    assert dashboard.status_code == 200, dashboard.text
    assert predictions.status_code == 200, predictions.text
    prediction_id = predict.json()["data"]["prediction"]["prediction"]["id"]
    detail = client.get(f"/api/v1/grading-intelligence/predictions/{prediction_id}", headers=auth_headers(owner_token))
    assert detail.status_code == 200, detail.text

    recommendation_id = recs.json()["data"]["recommendations"][0]["id"]
    reviewed = client.post(
        f"/api/v1/grading-intelligence/recommendations/{recommendation_id}/reviewed",
        headers=auth_headers(owner_token),
        json={"review_notes": "Looks reasonable for manual follow-up."},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert outsider_preds.json()["data"]["items"] == []

    with Session(get_engine()) as session:
        copy_count_after = len(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all())
        reviews = session.exec(select(GradingRecommendationReview)).all()
        assert len(reviews) >= 1
    assert copy_count_before == copy_count_after
