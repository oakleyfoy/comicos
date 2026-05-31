from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import ReleaseIssue, ReleaseSeries, User
from app.models.purchase_budget import PurchaseBudgetAllocation
from app.models.purchase_quantity import PurchaseQuantityRecommendation
from app.models.recommendation_v2 import RecommendationRunV2, RecommendationScoreV2
from app.schemas.purchase_budget import PurchaseBudgetUpdate
from app.schemas.purchase_profile import PurchaseProfileUpdate
from app.services.purchase_budget_engine import generate_budget_allocations
from app.services.purchase_budgets import (
    generate_purchase_budget_allocations,
    update_purchase_budget,
    build_purchase_budget_summary,
)
from app.services.purchase_profiles import set_purchase_profile
from app.services.purchase_quantities import generate_purchase_quantities
from test_inventory import auth_headers, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _seed_series_issue(
    session: Session,
    *,
    owner_user_id: int,
    uuid_suffix: str,
    title: str,
) -> ReleaseIssue:
    series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher="Marvel",
        series_name=f"Budget Series {uuid_suffix}",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    issue = ReleaseIssue(
        owner_user_id=owner_user_id,
        release_uuid=f"budget-{uuid_suffix}",
        series_id=int(series.id or 0),
        issue_number="1",
        title=title,
        release_status="SCHEDULED",
        release_date=date.today() + timedelta(days=21),
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    return issue


def _seed_v2(
    session: Session,
    *,
    owner_user_id: int,
    issue: ReleaseIssue,
    tier: str,
    confidence: float = 0.8,
) -> None:
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
            recommendation_tier=tier,
            recommendation_type="NEW_OPPORTUNITY",
            confidence_score=confidence,
        )
    )
    session.commit()


def _seed_qty_row(
    session: Session,
    *,
    owner_user_id: int,
    issue: ReleaseIssue,
    tier: str,
    quantity: int,
    confidence: float,
) -> None:
    session.add(
        PurchaseQuantityRecommendation(
            owner_user_id=owner_user_id,
            release_id=int(issue.id or 0),
            recommendation_tier=tier,
            quantity_recommended=quantity,
            confidence_score=confidence,
            rationale="test",
        )
    )
    session.commit()


def test_must_buy_receives_more_than_pass(client: TestClient, session: Session) -> None:
    email = "pb-tier@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    must = _seed_series_issue(session, owner_user_id=owner_id, uuid_suffix="must", title="Must Buy")
    pas = _seed_series_issue(session, owner_user_id=owner_id, uuid_suffix="pass", title="Pass")
    _seed_qty_row(session, owner_user_id=owner_id, issue=must, tier="MUST_BUY", quantity=3, confidence=0.9)
    _seed_qty_row(session, owner_user_id=owner_id, issue=pas, tier="PASS", quantity=0, confidence=0.4)
    update_purchase_budget(
        session,
        owner_user_id=owner_id,
        payload=PurchaseBudgetUpdate(monthly_budget=500.0, weekly_budget=125.0),
    )
    results, _ = generate_budget_allocations(session, owner_user_id=owner_id)
    by_release = {r.release_id: r for r in results}
    assert by_release[int(must.id or 0)].allocated_amount > 0
    assert by_release[int(pas.id or 0)].allocated_amount == 0.0


def test_budget_totals_reconcile(client: TestClient, session: Session) -> None:
    email = "pb-recon@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    issue = _seed_series_issue(session, owner_user_id=owner_id, uuid_suffix="one", title="One")
    _seed_qty_row(session, owner_user_id=owner_id, issue=issue, tier="STRONG_BUY", quantity=2, confidence=0.85)
    update_purchase_budget(session, owner_user_id=owner_id, payload=PurchaseBudgetUpdate(monthly_budget=500.0))
    generate_purchase_budget_allocations(session, owner_user_id=owner_id)
    summary = build_purchase_budget_summary(session, owner_user_id=owner_id)
    assert summary.total_budget == 500.0
    assert summary.allocated_budget >= 0
    assert summary.remaining_budget == round(500.0 - summary.allocated_budget, 2)
    assert summary.allocated_budget <= 500.0


def test_tier_priority_order(client: TestClient, session: Session) -> None:
    email = "pb-priority@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    must = _seed_series_issue(session, owner_user_id=owner_id, uuid_suffix="m", title="M")
    strong = _seed_series_issue(session, owner_user_id=owner_id, uuid_suffix="s", title="S")
    _seed_qty_row(session, owner_user_id=owner_id, issue=must, tier="MUST_BUY", quantity=2, confidence=0.88)
    _seed_qty_row(session, owner_user_id=owner_id, issue=strong, tier="STRONG_BUY", quantity=2, confidence=0.88)
    update_purchase_budget(session, owner_user_id=owner_id, payload=PurchaseBudgetUpdate(monthly_budget=500.0))
    results, _ = generate_budget_allocations(session, owner_user_id=owner_id)
    must_row = next(r for r in results if r.release_id == int(must.id or 0))
    strong_row = next(r for r in results if r.release_id == int(strong.id or 0))
    assert must_row.priority_rank < strong_row.priority_rank
    assert must_row.allocated_amount >= strong_row.allocated_amount


def test_profile_influence_reader_lower_utilization(client: TestClient, session: Session) -> None:
    email = "pb-reader@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    issue = _seed_series_issue(session, owner_user_id=owner_id, uuid_suffix="r", title="R")
    _seed_qty_row(session, owner_user_id=owner_id, issue=issue, tier="MUST_BUY", quantity=2, confidence=0.9)
    update_purchase_budget(session, owner_user_id=owner_id, payload=PurchaseBudgetUpdate(monthly_budget=500.0))
    set_purchase_profile(session, owner_user_id=owner_id, payload=PurchaseProfileUpdate(profile_type="INVESTOR"))
    inv_results, _ = generate_budget_allocations(session, owner_user_id=owner_id)
    set_purchase_profile(session, owner_user_id=owner_id, payload=PurchaseProfileUpdate(profile_type="READER"))
    read_results, _ = generate_budget_allocations(session, owner_user_id=owner_id)
    inv_amt = sum(r.allocated_amount for r in inv_results)
    read_amt = sum(r.allocated_amount for r in read_results)
    assert inv_amt > read_amt


def test_idempotent_generate(client: TestClient, session: Session) -> None:
    email = "pb-idem@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    issue = _seed_series_issue(session, owner_user_id=owner_id, uuid_suffix="i", title="I")
    _seed_v2(session, owner_user_id=owner_id, issue=issue, tier="BUY")
    generate_purchase_quantities(session, owner_user_id=owner_id)
    update_purchase_budget(session, owner_user_id=owner_id, payload=PurchaseBudgetUpdate(monthly_budget=500.0))
    first = generate_purchase_budget_allocations(session, owner_user_id=owner_id)
    assert first >= 1
    second = generate_purchase_budget_allocations(session, owner_user_id=owner_id)
    assert second == 0


def test_api_owner_isolation(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "pb-a@example.com")
    token_b = register_and_login(client, "pb-b@example.com")
    owner_a = _owner_id(session, "pb-a@example.com")
    issue = _seed_series_issue(session, owner_user_id=owner_a, uuid_suffix="a", title="A")
    _seed_qty_row(session, owner_user_id=owner_a, issue=issue, tier="BUY", quantity=1, confidence=0.7)
    client.patch(
        "/api/v1/purchase-budget",
        headers=auth_headers(token_a),
        json={"monthly_budget": 500},
    )
    client.post("/api/v1/purchase-budget/allocations/generate", headers=auth_headers(token_a))
    a_sum = client.get("/api/v1/purchase-budget/summary", headers=auth_headers(token_a))
    b_sum = client.get("/api/v1/purchase-budget/summary", headers=auth_headers(token_b))
    assert a_sum.json()["data"]["allocated_budget"] > 0
    assert b_sum.json()["data"]["allocated_budget"] == 0


def test_deterministic_outputs(client: TestClient, session: Session) -> None:
    email = "pb-det@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    issue = _seed_series_issue(session, owner_user_id=owner_id, uuid_suffix="d", title="D")
    _seed_qty_row(session, owner_user_id=owner_id, issue=issue, tier="WATCH", quantity=1, confidence=0.6)
    update_purchase_budget(session, owner_user_id=owner_id, payload=PurchaseBudgetUpdate(monthly_budget=400.0))
    r1, _ = generate_budget_allocations(session, owner_user_id=owner_id)
    r2, _ = generate_budget_allocations(session, owner_user_id=owner_id)
    assert [(x.release_id, x.allocated_amount, x.priority_rank) for x in r1] == [
        (x.release_id, x.allocated_amount, x.priority_rank) for x in r2
    ]
