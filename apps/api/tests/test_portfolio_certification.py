from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import User
from app.models.portfolio_certification import PortfolioCertificationRun
from app.services.portfolio_certification import run_portfolio_certification
from test_inventory import auth_headers, create_order, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_run_portfolio_certification_persists(client: TestClient, session: Session) -> None:
    email = "pc-cert@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    user = session.exec(select(User).where(User.id == owner_id)).one()
    report = run_portfolio_certification(session, owner_user_id=owner_id, user=user)
    assert report.readiness_score >= 90.0
    assert report.certification_result == "APPROVED_FOR_PRODUCTION"
    assert report.report.health_status == "HEALTHY"
    assert len(report.checks) >= 7
    row = session.exec(select(PortfolioCertificationRun).where(PortfolioCertificationRun.owner_user_id == owner_id)).one()
    assert row.readiness_score == report.readiness_score


def test_certification_domain_scores(client: TestClient, session: Session) -> None:
    email = "pc-domains@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    user = session.exec(select(User).where(User.id == owner_id)).one()
    report = run_portfolio_certification(session, owner_user_id=owner_id, user=user)
    assert report.run_completeness_score == 100.0
    assert report.missing_issue_score == 100.0
    assert report.grade_candidate_score == 100.0
    assert report.determinism_score == 100.0


def test_certification_api_latest_and_ops(client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    email = "pc-cert-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    user = session.exec(select(User).where(User.id == owner_id)).one()
    run_portfolio_certification(session, owner_user_id=owner_id, user=user)
    latest = client.get("/api/v1/portfolio-certification/latest", headers=auth_headers(token))
    assert latest.status_code == 200
    assert latest.json()["data"]["readiness_score"] >= 90.0
    forbidden = client.post("/api/v1/portfolio-certification/run", headers=auth_headers(token))
    assert forbidden.status_code == 403


def test_sell_scenario_with_inventory(client: TestClient, session: Session) -> None:
    email = "pc-inv@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    user = session.exec(select(User).where(User.id == owner_id)).one()
    create_order(
        client,
        token,
        items=[
            {
                "title": "Amazing Spider-Man",
                "publisher": "Marvel",
                "issue_number": "300",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 5,
                "raw_item_price": 10.00,
            }
        ],
    )
    report = run_portfolio_certification(session, owner_user_id=owner_id, user=user)
    assert report.sell_candidate_score >= 66.0
