from __future__ import annotations

import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import InventoryCopy, User
from app.models.exit_certification import ExitCertificationRun
from app.services.exit_certification import run_exit_certification
from app.services.exit_candidates import persist_exit_candidates
from app.services.grade_before_sell import persist_grade_before_sell_recommendations
from app.services.hold_sell_intelligence import persist_hold_sell_recommendations
from app.services.portfolio_rebalancing import persist_portfolio_rebalancing_recommendations
from app.services.recovery_recommendations import build_operations_dashboard
from app.services.sell_candidates import generate_sell_candidate_recommendations
from test_inventory import auth_headers, create_order, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _seed_exit_stack(client: TestClient, session: Session, email: str) -> int:
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(
        client,
        token,
        items=[
            {
                "title": "Battle Beast",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 5,
                "raw_item_price": 10.00,
            },
            {
                "title": "Batman",
                "publisher": "DC",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 10.00,
            },
            {
                "title": "Filler",
                "publisher": "Image",
                "issue_number": "9",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 5.00,
            },
        ],
    )
    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).all())
    grade_inv: int | None = None
    for copy in copies:
        if "Battle Beast" in (copy.metadata_identity_key or ""):
            copy.current_fmv = Decimal("40.00")
            if grade_inv is None:
                grade_inv = int(copy.id or 0)
        elif "Batman" in (copy.metadata_identity_key or ""):
            copy.current_fmv = Decimal("90.00")
        else:
            copy.current_fmv = Decimal("10.00")
        session.add(copy)
    session.commit()

    assert grade_inv is not None
    client.post(
        "/grading-candidates",
        json={
            "inventory_item_id": grade_inv,
            "target_grader": "PSA",
            "candidate_priority": "HIGH",
            "replay_key": f"exit-cert-{email}",
            "estimated_raw_value": "100.00",
            "estimated_graded_value": "400.00",
            "estimated_grading_cost": "40.00",
        },
        headers=auth_headers(token),
    )

    persist_exit_candidates(session, owner_user_id=owner_id)
    persist_hold_sell_recommendations(session, owner_user_id=owner_id)
    persist_grade_before_sell_recommendations(session, owner_user_id=owner_id)
    persist_portfolio_rebalancing_recommendations(session, owner_user_id=owner_id)
    generate_sell_candidate_recommendations(session, owner_user_id=owner_id)
    return owner_id


def test_run_exit_certification_persists(client: TestClient, session: Session) -> None:
    email = "ex-cert@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    report = run_exit_certification(session, owner_user_id=owner_id)
    assert report.readiness_score >= 90.0
    assert report.certification_result == "APPROVED_FOR_PRODUCTION"
    assert report.report.health_status == "HEALTHY"
    assert len(report.checks) >= 7
    row = session.exec(select(ExitCertificationRun).where(ExitCertificationRun.owner_user_id == owner_id)).one()
    assert row.readiness_score == report.readiness_score


def test_certification_domain_scores(client: TestClient, session: Session) -> None:
    email = "ex-domains@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    report = run_exit_certification(session, owner_user_id=owner_id)
    assert report.exit_candidate_score == 100.0
    assert report.hold_sell_score == 100.0
    assert report.grade_before_sell_score == 100.0
    assert report.determinism_score == 100.0


def test_certification_api_latest_and_ops(client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    email = "ex-cert-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    run_exit_certification(session, owner_user_id=owner_id)
    latest = client.get("/api/v1/exit-certification/latest", headers=auth_headers(token))
    assert latest.status_code == 200
    assert latest.json()["data"]["readiness_score"] >= 90.0
    forbidden = client.post("/api/v1/exit-certification/run", headers=auth_headers(token))
    assert forbidden.status_code == 403


def test_certification_rerun_appends_history(client: TestClient, session: Session) -> None:
    email = "ex-rerun@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    run_exit_certification(session, owner_user_id=owner_id)
    run_exit_certification(session, owner_user_id=owner_id)
    rows = session.exec(select(ExitCertificationRun).where(ExitCertificationRun.owner_user_id == owner_id)).all()
    assert len(rows) == 2


def test_exit_stack_certification_and_ops_panel(client: TestClient, session: Session) -> None:
    email = "ex-stack@example.com"
    owner_id = _seed_exit_stack(client, session, email)
    report = run_exit_certification(session, owner_user_id=owner_id)
    assert report.readiness_score >= 90.0
    assert report.certification_result == "APPROVED_FOR_PRODUCTION"
    codes = {c.check_code for c in report.checks}
    assert "hold_sell_sell_recommendation" in codes
    assert "gbs_grade_before_sell" in codes
    assert "rebalance_duplicate_capital" in codes
    assert "dashboard_top_sell_recommendations" in codes
    dash = build_operations_dashboard(session, owner_user_id=owner_id)
    assert dash.exit_certification is not None
    assert dash.exit_certification.readiness_score >= 90.0
