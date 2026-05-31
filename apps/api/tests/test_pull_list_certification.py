from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import ReleaseIssue, ReleaseSeries, User
from app.models.pull_list import PullListCertificationRun
from app.models.recommendation_v2 import RecommendationRunV2, RecommendationScoreV2
from app.services.pull_list_certification import run_pull_list_certification
from test_inventory import auth_headers, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _seed_catalog(session: Session, *, owner_user_id: int) -> None:
    series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher="MARVEL",
        series_name="Cert Test",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    issue = ReleaseIssue(
        owner_user_id=owner_user_id,
        release_uuid="cert-plat-1",
        series_id=int(series.id or 0),
        issue_number="1",
        title="Cert Test #1",
        release_status="SCHEDULED",
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    run = RecommendationRunV2(owner_user_id=owner_user_id, status="COMPLETED")
    session.add(run)
    session.commit()
    session.refresh(run)
    session.add(
        RecommendationScoreV2(
            owner_user_id=owner_user_id,
            recommendation_run_id=int(run.id or 0),
            release_issue_id=int(issue.id or 0),
            total_score=80.0,
            recommendation_tier="STRONG_BUY",
            recommendation_type="INVESTMENT_NUMBER_ONE",
            confidence_score=0.9,
        )
    )
    session.commit()


def test_run_pull_list_certification_persists_run(client: TestClient, session: Session) -> None:
    email = "plc-cert@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _seed_catalog(session, owner_user_id=owner_id)
    report = run_pull_list_certification(session, owner_user_id=owner_id)
    assert report.readiness_score >= 0
    assert report.certification_result in {"NOT_READY", "READY_WITH_WARNINGS", "APPROVED_FOR_PRODUCTION"}
    assert len(report.checks) >= 1
    row = session.exec(select(PullListCertificationRun).where(PullListCertificationRun.owner_user_id == owner_id)).one()
    assert row.readiness_score == report.readiness_score
    assert row.certification_result == report.certification_result


def test_certification_api_latest_and_run_ops(client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    email = "plc-cert-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _seed_catalog(session, owner_user_id=owner_id)
    run_pull_list_certification(session, owner_user_id=owner_id)
    latest = client.get("/api/v1/pull-list-certification/latest", headers=auth_headers(token))
    assert latest.status_code == 200
    runs = client.get("/api/v1/pull-list-certification/runs", headers=auth_headers(token))
    assert runs.status_code == 200
    assert runs.json()["data"]["items"]

    denied = client.post("/api/v1/pull-list-certification/run", headers=auth_headers(token))
    assert denied.status_code == 403

    ops_email = "plc-cert-ops@example.com"
    monkeypatch.setenv("OPS_ADMIN_EMAILS", ops_email)
    get_settings.cache_clear()
    ops_token = register_and_login(client, ops_email)
    _seed_catalog(session, owner_user_id=_owner_id(session, ops_email))
    ok = client.post("/api/v1/pull-list-certification/run", headers=auth_headers(ops_token))
    assert ok.status_code == 200
    assert ok.json()["data"]["run"]["readiness_score"] >= 0
