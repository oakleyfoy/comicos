from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.future_release_certification import FutureReleaseCertificationRun
from app.services.future_release_certification import run_future_release_certification
from app.services.recovery_recommendations import build_operations_dashboard
from test_inventory import auth_headers, create_order, register_and_login
from test_future_release_matches import (
    _battle_beast_items,
    _import_future_lunar_issue,
    _owner_id,
)


def test_run_future_release_certification_persists(client: TestClient, session: Session) -> None:
    email = "frc-persist@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    report = run_future_release_certification(session, owner_user_id=owner_id)
    assert report.readiness_score >= 80.0
    assert report.certification_result in {"APPROVED_FOR_PRODUCTION", "READY_WITH_WARNINGS"}
    assert len(report.checks) >= 7
    assert report.report.domain_scores["foc_intelligence"] >= 90.0
    row = session.exec(
        select(FutureReleaseCertificationRun).where(FutureReleaseCertificationRun.owner_user_id == owner_id)
    ).one()
    assert row.readiness_score == report.readiness_score


def test_certification_domain_scores_with_stack(client: TestClient, session: Session) -> None:
    email = "frc-stack@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items([str(n) for n in range(1, 16)]))
    today = date.today()
    _import_future_lunar_issue(
        session,
        owner_user_id=owner_id,
        issue_number="16",
        foc_date=today + timedelta(days=2),
        release_date=today + timedelta(days=21),
    )
    report = run_future_release_certification(session, owner_user_id=owner_id)
    assert report.readiness_score >= 90.0
    assert report.certification_result == "APPROVED_FOR_PRODUCTION"
    assert report.run_detection_score >= 90.0
    assert report.next_issue_detection_score >= 75.0
    assert report.release_matching_score >= 75.0
    assert report.dashboard_score >= 90.0


def test_certification_api_and_ops_panel(client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    email = "frc-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    run_future_release_certification(session, owner_user_id=owner_id)
    latest = client.get("/api/v1/future-release-certification/latest", headers=auth_headers(token))
    assert latest.status_code == 200
    assert latest.json()["data"]["readiness_score"] >= 80.0

    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    forbidden = client.post("/api/v1/future-release-certification/run", headers=auth_headers(token))
    assert forbidden.status_code == 403

    ops = build_operations_dashboard(session, owner_user_id=owner_id)
    assert ops.future_release_certification is not None
    assert ops.future_release_certification.readiness_score >= 80.0
