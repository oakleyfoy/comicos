from __future__ import annotations

import pytest
from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.db.session import get_engine
from app.models import InventoryCopy, User
from app.models.production_readiness import ProductionReadinessCheck, ProductionReadinessRun
from app.models.pull_list import PullListDecision
from app.models.release_imports import ReleaseImportRun
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.models.recommendation_v2 import RecommendationRunV2, RecommendationScoreV2
from app.services.acquisition_opportunities import persist_acquisition_opportunities
from app.services.collection_gaps import persist_collection_gaps
from app.services.exit_candidates import persist_exit_candidates
from app.services.final_platform_certification import run_final_platform_certification
from app.services.grade_before_sell import persist_grade_before_sell_recommendations
from app.services.hold_sell_intelligence import persist_hold_sell_recommendations
from app.services.portfolio_rebalancing import persist_portfolio_rebalancing_recommendations
from app.services.production_readiness import run_production_readiness_check, validate_production_readiness
from app.services.recovery_recommendations import build_operations_dashboard
from app.services.sell_candidates import generate_sell_candidate_recommendations
from test_inventory import auth_headers, create_order, register_and_login

def test_validate_production_readiness_persists_owner_scoped_checks(client: TestClient) -> None:
    owner_email = "prod-ready-owner@example.com"
    outsider_email = "prod-ready-outsider@example.com"
    owner_token = register_and_login(client, owner_email)
    outsider_token = register_and_login(client, outsider_email)

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == owner_email)).one()
        owner_user_id = int(owner.id or 0)
        checks = validate_production_readiness(session, owner_user_id=owner_user_id)
        assert len(checks) == 5
        assert {check.subsystem for check in checks} == {
            "marketplace",
            "forecast",
            "data_protection",
            "agent_platform",
            "operations",
        }

    list_resp = client.get("/api/v1/production-readiness/checks", headers=auth_headers(owner_token))
    assert list_resp.status_code == 200, list_resp.text
    assert len(list_resp.json()["data"]["items"]) >= 5

    outsider_resp = client.get("/api/v1/production-readiness/checks", headers=auth_headers(outsider_token))
    assert outsider_resp.json()["data"]["items"] == []


def test_production_readiness_checks_are_append_only(client: TestClient) -> None:
    owner_email = "prod-ready-append@example.com"
    owner_token = register_and_login(client, owner_email)

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == owner_email)).one()
        owner_user_id = int(owner.id or 0)
        validate_production_readiness(session, owner_user_id=owner_user_id)
        validate_production_readiness(session, owner_user_id=owner_user_id)
        count = len(
            session.exec(select(ProductionReadinessCheck)).all(),
        )
        assert count >= 10

    run = client.post("/api/v1/production-readiness/run/readiness", headers=auth_headers(owner_token))
    assert run.status_code == 200, run.text
    assert len(run.json()["data"]["checks"]) == 5
    assert len(run.json()["data"]["checklist_items"]) == 8


def _seed_go_live_stack(client: TestClient, session: Session, email: str) -> int:
    token = register_and_login(client, email)
    owner = session.exec(select(User).where(User.email == email)).one()
    owner_id = int(owner.id or 0)
    session.add(
        ReleaseImportRun(
            owner_user_id=owner_id,
            import_type="JSON",
            file_name="prod-ready.json",
            records_processed=5,
            records_created=5,
            status="COMPLETED",
        )
    )
    session.commit()
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
                "quantity": 3,
                "raw_item_price": 10.00,
            },
            {
                "title": "Battle Beast",
                "publisher": "Image",
                "issue_number": "4",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 10.00,
            },
        ],
    )
    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).all())
    for copy in copies:
        copy.current_fmv = Decimal("35.00")
        session.add(copy)
    session.commit()
    series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="Image",
        series_name="Battle Beast",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    foc = date.today() + timedelta(days=4)
    issue16 = ReleaseIssue(
        owner_user_id=owner_id,
        release_uuid=f"prod-rdy-16-{email}",
        series_id=int(series.id or 0),
        issue_number="16",
        title="Battle Beast 16",
        release_status="SCHEDULED",
        foc_date=foc,
        release_date=foc + timedelta(days=21),
    )
    session.add(issue16)
    session.commit()
    session.refresh(issue16)
    session.add(
        ReleaseVariant(
            issue_id=int(issue16.id or 0),
            variant_uuid=f"pr-{email}",
            variant_name="Cover A",
            variant_type="STANDARD",
            source_item_code="PR-16",
        )
    )
    session.add(
        PullListDecision(
            owner_user_id=owner_id,
            release_id=int(issue16.id or 0),
            decision_type="CONTINUE_RUN",
            confidence_score=0.8,
            explanation='["FOC"]',
        )
    )
    v2 = RecommendationRunV2(owner_user_id=owner_id, status="COMPLETED")
    session.add(v2)
    session.commit()
    session.refresh(v2)
    session.add(
        RecommendationScoreV2(
            owner_user_id=owner_id,
            recommendation_run_id=int(v2.id or 0),
            release_issue_id=int(issue16.id or 0),
            total_score=82.0,
            recommendation_tier="STRONG_BUY",
            recommendation_type="INVESTMENT_NUMBER_ONE",
            confidence_score=0.85,
        )
    )
    session.commit()
    persist_collection_gaps(session, owner_user_id=owner_id)
    persist_acquisition_opportunities(session, owner_user_id=owner_id)
    persist_exit_candidates(session, owner_user_id=owner_id)
    persist_hold_sell_recommendations(session, owner_user_id=owner_id)
    persist_grade_before_sell_recommendations(session, owner_user_id=owner_id)
    persist_portfolio_rebalancing_recommendations(session, owner_user_id=owner_id)
    generate_sell_candidate_recommendations(session, owner_user_id=owner_id)
    run_final_platform_certification(session, owner_user_id=owner_id)
    return owner_id


def test_run_production_readiness_check_persists(client: TestClient, session: Session) -> None:
    owner_id = _seed_go_live_stack(client, session, "prod-go-live@example.com")
    result = run_production_readiness_check(session, owner_user_id=owner_id)
    assert result.run.readiness_score >= 0
    assert result.run.go_live_result in {"NOT_READY", "READY_WITH_WARNINGS", "GO_LIVE_APPROVED"}
    assert len(result.checks) >= 10
    assert result.run.report.domain_scores
    row = session.exec(select(ProductionReadinessRun).where(ProductionReadinessRun.owner_user_id == owner_id)).one()
    assert row.readiness_score == result.run.readiness_score


def test_production_readiness_latest_api(client: TestClient, session: Session) -> None:
    email = "prod-latest@example.com"
    token = register_and_login(client, email)
    owner_id = _seed_go_live_stack(client, session, email)
    run_production_readiness_check(session, owner_user_id=owner_id)
    latest = client.get("/api/v1/production-readiness/latest", headers=auth_headers(token))
    assert latest.status_code == 200
    assert latest.json()["data"]["run"]["readiness_score"] >= 0


def test_production_readiness_run_ops_admin(client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    email = "prod-ops@example.com"
    token = register_and_login(client, email)
    owner_id = _seed_go_live_stack(client, session, email)
    denied = client.post("/api/v1/production-readiness/run", headers=auth_headers(token))
    assert denied.status_code == 403
    monkeypatch.setenv("OPS_ADMIN_EMAILS", email)
    get_settings.cache_clear()
    ok = client.post("/api/v1/production-readiness/run", headers=auth_headers(token))
    assert ok.status_code == 200
    assert ok.json()["data"]["validation"]["run"]["owner_id"] == owner_id


def test_ops_panel_shows_production_readiness(client: TestClient, session: Session) -> None:
    owner_id = _seed_go_live_stack(client, session, "prod-panel@example.com")
    run_production_readiness_check(session, owner_user_id=owner_id)
    dash = build_operations_dashboard(session, owner_user_id=owner_id)
    assert dash.production_readiness is not None
    assert dash.production_readiness.readiness_score >= 0
