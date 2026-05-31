from __future__ import annotations

from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_production_readiness_api_routes(client: TestClient) -> None:
    owner_email = "prod-ready-api@example.com"
    owner_token = register_and_login(client, owner_email)

    dashboard = client.get("/api/v1/production-readiness/dashboard", headers=auth_headers(owner_token))
    checks = client.get("/api/v1/production-readiness/checks", headers=auth_headers(owner_token))
    checklist = client.get("/api/v1/production-readiness/checklist", headers=auth_headers(owner_token))
    certification = client.get("/api/v1/production-readiness/certification", headers=auth_headers(owner_token))
    assessment = client.get("/api/v1/production-readiness/assessment", headers=auth_headers(owner_token))
    run_readiness = client.post("/api/v1/production-readiness/run/readiness", headers=auth_headers(owner_token))
    run_cert = client.post("/api/v1/production-readiness/run/certification", headers=auth_headers(owner_token))

    assert dashboard.status_code == 200, dashboard.text
    assert checks.status_code == 200, checks.text
    assert checklist.status_code == 200, checklist.text
    assert certification.status_code == 200, certification.text
    assert assessment.status_code == 200, assessment.text
    assert run_readiness.status_code == 200, run_readiness.text
    assert run_cert.status_code == 200, run_cert.text

    assert "readiness_score" in dashboard.json()["data"]
    assert run_cert.json()["data"]["certification"]["certification_uuid"]
    assert run_cert.json()["data"]["assessment"]["assessment_uuid"]

    cert_list = client.get("/api/v1/production-readiness/certification", headers=auth_headers(owner_token))
    assert len(cert_list.json()["data"]["items"]) >= 1
