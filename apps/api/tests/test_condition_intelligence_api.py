from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from test_scan_quality_agent import _seed_scan_image
from test_inventory import auth_headers, register_and_login


def test_condition_intelligence_api_routes(client: TestClient) -> None:
    owner_email = "ci-owner@example.com"
    outsider_email = "ci-outsider@example.com"
    owner_token = register_and_login(client, owner_email)
    outsider_token = register_and_login(client, outsider_email)

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == owner_email)).one()
        image = _seed_scan_image(session, owner_user_id=int(owner.id or 0))

    run_quality = client.post(
        "/api/v1/condition-intelligence/run/quality",
        headers=auth_headers(owner_token),
        json={"front_image_id": image.id},
    )
    analysis_id = run_quality.json()["data"]["analysis"]["id"]

    run_defects = client.post(
        "/api/v1/condition-intelligence/run/defects",
        headers=auth_headers(owner_token),
        json={"analysis_id": analysis_id},
    )
    run_profile = client.post(
        "/api/v1/condition-intelligence/run/profile",
        headers=auth_headers(owner_token),
        json={"analysis_id": analysis_id},
    )
    run_subgrades = client.post(
        "/api/v1/condition-intelligence/run/subgrades",
        headers=auth_headers(owner_token),
        json={"analysis_id": analysis_id},
    )

    dashboard = client.get("/api/v1/condition-intelligence/dashboard", headers=auth_headers(owner_token))
    analyses = client.get("/api/v1/condition-intelligence/analyses", headers=auth_headers(owner_token))
    detail = client.get(f"/api/v1/condition-intelligence/analyses/{analysis_id}", headers=auth_headers(owner_token))
    profiles = client.get("/api/v1/condition-intelligence/profiles", headers=auth_headers(owner_token))
    defects = client.get("/api/v1/condition-intelligence/defects", headers=auth_headers(owner_token))
    subgrades = client.get("/api/v1/condition-intelligence/subgrades", headers=auth_headers(owner_token))
    quality = client.get("/api/v1/condition-intelligence/quality", headers=auth_headers(owner_token))
    executions = client.get("/api/v1/condition-intelligence/executions", headers=auth_headers(owner_token))
    outsider_analyses = client.get("/api/v1/condition-intelligence/analyses", headers=auth_headers(outsider_token))

    assert run_quality.status_code == 200, run_quality.text
    assert run_defects.status_code == 200, run_defects.text
    assert run_profile.status_code == 200, run_profile.text
    assert run_subgrades.status_code == 200, run_subgrades.text
    assert dashboard.status_code == 200, dashboard.text
    assert analyses.status_code == 200, analyses.text
    assert detail.status_code == 200, detail.text
    assert profiles.status_code == 200, profiles.text
    assert defects.status_code == 200, defects.text
    assert subgrades.status_code == 200, subgrades.text
    assert quality.status_code == 200, quality.text
    assert executions.status_code == 200, executions.text
    assert len(analyses.json()["data"]["items"]) >= 1
    assert len(executions.json()["data"]["items"]) >= 4
    assert outsider_analyses.json()["data"]["items"] == []
    payload = str(run_profile.json())
    assert "predicted_grade" not in payload.lower()
    assert "roi" not in payload.lower()
