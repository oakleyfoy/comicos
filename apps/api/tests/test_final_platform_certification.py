from __future__ import annotations

import pytest
from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import InventoryCopy, User
from app.models.final_platform_certification import FinalPlatformCertificationRun
from app.models.pull_list import PullListDecision
from app.models.release_imports import ReleaseImportRun
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.models.recommendation_v2 import RecommendationRunV2, RecommendationScoreV2
from app.services.acquisition_certification import run_acquisition_certification
from app.services.acquisition_opportunities import persist_acquisition_opportunities
from app.services.collection_gaps import persist_collection_gaps
from app.services.exit_certification import run_exit_certification
from app.services.exit_candidates import persist_exit_candidates
from app.services.final_platform_certification import run_final_platform_certification
from app.services.grade_before_sell import persist_grade_before_sell_recommendations
from app.services.hold_sell_intelligence import persist_hold_sell_recommendations
from app.services.portfolio_certification import run_portfolio_certification
from app.services.portfolio_rebalancing import persist_portfolio_rebalancing_recommendations
from app.services.pull_list_automation import run_pull_list_refresh
from app.services.pull_list_certification import run_pull_list_certification
from app.services.purchase_budgets import generate_purchase_budget_allocations
from app.services.purchase_profiles import get_purchase_profile
from app.services.purchase_quantities import generate_purchase_quantities
from app.services.purchase_variants import generate_purchase_variants
from app.services.recovery_recommendations import build_operations_dashboard
from app.services.sell_candidates import generate_sell_candidate_recommendations
from test_inventory import auth_headers, create_order, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _battle_beast_items(numbers: list[str]) -> list[dict]:
    return [
        {
            "title": "Battle Beast",
            "publisher": "Image",
            "issue_number": num,
            "cover_name": "Cover A",
            "printing": None,
            "ratio": None,
            "variant_type": None,
            "cover_artist": None,
            "quantity": 5 if num == "1" else 1,
            "raw_item_price": 10.00,
        }
        for num in numbers
    ]


def _seed_platform_stack(client: TestClient, session: Session, email: str) -> int:
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    user = session.exec(select(User).where(User.id == owner_id)).one()

    session.add(
        ReleaseImportRun(
            owner_user_id=owner_id,
            import_type="JSON",
            file_name="cert-seed.json",
            records_processed=10,
            records_created=10,
            status="COMPLETED",
        )
    )
    session.commit()

    create_order(client, token, items=_battle_beast_items(["1", "2", "4", "5"]))
    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).all())
    grade_inv: int | None = None
    for copy in copies:
        if "Battle Beast" in (copy.metadata_identity_key or ""):
            copy.current_fmv = Decimal("40.00")
            if grade_inv is None:
                grade_inv = int(copy.id or 0)
        else:
            copy.current_fmv = Decimal("25.00")
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
    foc_date = date.today() + timedelta(days=5)
    issue16 = ReleaseIssue(
        owner_user_id=owner_id,
        release_uuid=f"final-16-{email}",
        series_id=int(series.id or 0),
        issue_number="16",
        title="Battle Beast 16",
        release_status="SCHEDULED",
        foc_date=foc_date,
        release_date=foc_date + timedelta(days=21),
    )
    session.add(issue16)
    session.commit()
    session.refresh(issue16)
    session.add(
        ReleaseVariant(
            issue_id=int(issue16.id or 0),
            variant_uuid=f"var-{email}",
            variant_name="Cover A",
            variant_type="STANDARD",
            source_item_code="BB-16-A",
        )
    )
    session.add(
        PullListDecision(
            owner_user_id=owner_id,
            release_id=int(issue16.id or 0),
            decision_type="CONTINUE_RUN",
            confidence_score=0.82,
            explanation='["FOC approaching"]',
        )
    )
    run = RecommendationRunV2(owner_user_id=owner_id, status="COMPLETED")
    session.add(run)
    session.commit()
    session.refresh(run)
    session.add(
        RecommendationScoreV2(
            owner_user_id=owner_id,
            recommendation_run_id=int(run.id or 0),
            release_issue_id=int(issue16.id or 0),
            total_score=85.0,
            recommendation_tier="STRONG_BUY",
            recommendation_type="INVESTMENT_NUMBER_ONE",
            confidence_score=0.88,
        )
    )
    session.commit()

    assert grade_inv is not None
    client.post(
        "/grading-candidates",
        json={
            "inventory_item_id": grade_inv,
            "target_grader": "PSA",
            "candidate_priority": "HIGH",
            "replay_key": f"final-{email}",
            "estimated_raw_value": "100.00",
            "estimated_graded_value": "400.00",
            "estimated_grading_cost": "40.00",
        },
        headers=auth_headers(token),
    )

    persist_collection_gaps(session, owner_user_id=owner_id)
    persist_acquisition_opportunities(session, owner_user_id=owner_id)
    persist_exit_candidates(session, owner_user_id=owner_id)
    persist_hold_sell_recommendations(session, owner_user_id=owner_id)
    persist_grade_before_sell_recommendations(session, owner_user_id=owner_id)
    persist_portfolio_rebalancing_recommendations(session, owner_user_id=owner_id)
    generate_sell_candidate_recommendations(session, owner_user_id=owner_id)

    get_purchase_profile(session, owner_user_id=owner_id)
    generate_purchase_quantities(session, owner_user_id=owner_id)
    generate_purchase_variants(session, owner_user_id=owner_id)
    generate_purchase_budget_allocations(session, owner_user_id=owner_id)
    run_pull_list_refresh(session, owner_user_ids=[owner_id])

    run_pull_list_certification(session, owner_user_id=owner_id)
    run_portfolio_certification(session, owner_user_id=owner_id, user=user)
    run_acquisition_certification(session, owner_user_id=owner_id)
    run_exit_certification(session, owner_user_id=owner_id)
    return owner_id


def test_final_certification_run_persists(client: TestClient, session: Session) -> None:
    owner_id = _seed_platform_stack(client, session, "final-cert@example.com")
    report = run_final_platform_certification(session, owner_user_id=owner_id)
    assert report.readiness_score >= 0
    assert report.certification_result in {"NOT_READY", "READY_WITH_WARNINGS", "APPROVED_FOR_PRODUCTION"}
    assert report.health_status in {"HEALTHY", "WARNING", "UNHEALTHY"}
    assert len(report.checks) >= 10
    assert report.report.domain_scores
    row = session.exec(
        select(FinalPlatformCertificationRun).where(FinalPlatformCertificationRun.owner_user_id == owner_id)
    ).one()
    assert row.readiness_score == report.readiness_score


def test_domain_scores_generated(client: TestClient, session: Session) -> None:
    owner_id = _seed_platform_stack(client, session, "final-domains@example.com")
    report = run_final_platform_certification(session, owner_user_id=owner_id)
    scores = report.report.domain_scores
    for key in (
        "release_intelligence",
        "recommendation_intelligence",
        "pull_list",
        "purchase",
        "portfolio",
        "acquisition",
        "exit",
        "unified_intelligence",
        "daily_actions",
        "cross_system",
        "executive_dashboard",
        "determinism",
        "operations",
    ):
        assert key in scores
        assert 0.0 <= scores[key] <= 100.0


def test_deterministic_ordering_stable(client: TestClient, session: Session) -> None:
    owner_id = _seed_platform_stack(client, session, "final-det@example.com")
    r1 = run_final_platform_certification(session, owner_user_id=owner_id)
    r2 = run_final_platform_certification(session, owner_user_id=owner_id)
    assert r1.report.domain_scores.keys() == r2.report.domain_scores.keys()


def test_owner_isolation(client: TestClient, session: Session) -> None:
    owner_a = _seed_platform_stack(client, session, "final-a@example.com")
    run_final_platform_certification(session, owner_user_id=owner_a)
    token_a = register_and_login(client, "final-a@example.com")
    register_and_login(client, "final-b@example.com")
    rsp_a = client.get("/api/v1/final-platform-certification/latest", headers=auth_headers(token_a))
    token_b = register_and_login(client, "final-b@example.com")
    rsp_b = client.get("/api/v1/final-platform-certification/latest", headers=auth_headers(token_b))
    assert rsp_a.status_code == 200
    assert rsp_b.status_code == 404


def test_ops_panel_includes_final_certification(client: TestClient, session: Session) -> None:
    owner_id = _seed_platform_stack(client, session, "final-ops@example.com")
    run_final_platform_certification(session, owner_user_id=owner_id)
    dash = build_operations_dashboard(session, owner_user_id=owner_id)
    assert dash.final_platform_certification is not None
    assert dash.final_platform_certification.readiness_score >= 0


def test_api_run_requires_ops_admin(client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    email = "final-api@example.com"
    token = register_and_login(client, email)
    owner_id = _seed_platform_stack(client, session, email)
    denied = client.post("/api/v1/final-platform-certification/run", headers=auth_headers(token))
    assert denied.status_code == 403
    monkeypatch.setenv("OPS_ADMIN_EMAILS", email)
    get_settings.cache_clear()
    ok = client.post("/api/v1/final-platform-certification/run", headers=auth_headers(token))
    assert ok.status_code == 200
    assert ok.json()["data"]["run"]["owner_id"] == owner_id
