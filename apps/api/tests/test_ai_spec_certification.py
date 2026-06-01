from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.ai_spec_certification import AISpecCertificationRun
from app.services.ai_spec_certification import run_ai_spec_certification
from app.services.recovery_recommendations import build_operations_dashboard
from test_industry_scanner_automation import _import_lunar_issue, _owner_id
from test_inventory import auth_headers, register_and_login


def test_run_ai_spec_certification_persists(client: TestClient, session: Session) -> None:
    email = "ai-spec-cert-persist@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    report = run_ai_spec_certification(session, owner_user_id=owner_id)
    assert report.readiness_score >= 60.0
    assert report.status == "SUCCESS"
    assert report.certification_result in {"APPROVED_FOR_PRODUCTION", "READY_WITH_WARNINGS", "NOT_READY"}
    assert len(report.checks) >= 8
    assert report.report.domain_scores["input"] >= 50.0
    row = session.exec(
        select(AISpecCertificationRun).where(AISpecCertificationRun.owner_user_id == owner_id)
    ).one()
    assert row.readiness_score == report.readiness_score


def test_certification_domain_scores_with_lunar_stack(client: TestClient, session: Session) -> None:
    email = "ai-spec-cert-stack@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _import_lunar_issue(session, owner_user_id=owner_id)
    report = run_ai_spec_certification(session, owner_user_id=owner_id)
    assert report.readiness_score >= 85.0
    assert report.certification_result in {"APPROVED_FOR_PRODUCTION", "READY_WITH_WARNINGS"}
    assert report.input_score >= 75.0
    assert report.baseline_score >= 75.0
    assert report.ai_eval_score >= 75.0
    assert report.top20_score >= 75.0
    assert report.automation_score >= 75.0
    assert report.dashboard_score >= 50.0
    assert report.determinism_score >= 50.0


def test_certification_api_and_ops_panel(client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    email = "ai-spec-cert-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _import_lunar_issue(session, owner_user_id=owner_id)
    run_ai_spec_certification(session, owner_user_id=owner_id)

    latest = client.get("/api/v1/ai-spec-certification/latest", headers=auth_headers(token))
    assert latest.status_code == 200
    assert latest.json()["data"]["readiness_score"] >= 85.0

    runs = client.get("/api/v1/ai-spec-certification/runs", headers=auth_headers(token))
    assert runs.status_code == 200
    assert runs.json()["data"]["pagination"]["total_count"] >= 1

    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    forbidden = client.post("/api/v1/ai-spec-certification/run", headers=auth_headers(token))
    assert forbidden.status_code == 403

    ops = build_operations_dashboard(session, owner_user_id=owner_id)
    assert ops.ai_spec_certification is not None
    assert ops.ai_spec_certification.readiness_score >= 85.0
