from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.grading_intelligence import GradePrediction
from grading_test_helpers import seed_analysis_with_condition_pipeline
from test_inventory import auth_headers, register_and_login


def test_grading_validation_api(client: TestClient) -> None:
    owner_email = "grading-val-api@example.com"
    outsider_email = "grading-val-outsider@example.com"
    owner_token = register_and_login(client, owner_email)
    outsider_token = register_and_login(client, outsider_email)

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == owner_email)).one()
        owner_user_id = int(owner.id or 0)
        analysis = seed_analysis_with_condition_pipeline(session, owner_user_id=owner_user_id)
        analysis_id = int(analysis.id)

    predict = client.post(
        "/api/v1/grading-intelligence/run/predictions",
        headers=auth_headers(owner_token),
        json={"analysis_id": analysis_id},
    )
    assert predict.status_code == 200, predict.text
    prediction_id = predict.json()["data"]["prediction"]["prediction"]["id"]
    predicted_grade = predict.json()["data"]["prediction"]["prediction"]["predicted_grade"]

    validation = client.post(
        "/api/v1/grading-validation/run/validation",
        headers=auth_headers(owner_token),
        json={"actual_grades": [{"prediction_id": prediction_id, "actual_grade": "8.0"}]},
    )
    calibration = client.post("/api/v1/grading-validation/run/calibration", headers=auth_headers(owner_token))
    reliability = client.post("/api/v1/grading-validation/run/reliability", headers=auth_headers(owner_token))
    outcomes = client.post("/api/v1/grading-validation/run/outcomes", headers=auth_headers(owner_token))
    dashboard = client.get("/api/v1/grading-validation/dashboard", headers=auth_headers(owner_token))
    validations = client.get("/api/v1/grading-validation/validations", headers=auth_headers(owner_token))
    outsider = client.get("/api/v1/grading-validation/validations", headers=auth_headers(outsider_token))

    assert validation.status_code == 200, validation.text
    assert calibration.status_code == 200, calibration.text
    assert reliability.status_code == 200, reliability.text
    assert outcomes.status_code == 200, outcomes.text
    assert dashboard.status_code == 200, dashboard.text
    assert validations.status_code == 200, validations.text
    assert outsider.json()["data"]["items"] == []

    with Session(get_engine()) as session:
        row = session.get(GradePrediction, prediction_id)
        assert row is not None
        assert row.predicted_grade == predicted_grade
