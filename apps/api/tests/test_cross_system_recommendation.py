from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, ReleaseIssue, ReleaseSeries, User
from app.models.cross_system_recommendation import CrossSystemRecommendation
from app.models.pull_list import PullListDecision
from app.services.acquisition_opportunities import persist_acquisition_opportunities
from app.services.collection_gaps import persist_collection_gaps
from app.services.cross_system_recommendation import list_latest_cross_system_recommendations
from app.services.cross_system_recommendation_engine import (
    build_cross_system_candidates,
    generate_cross_system_recommendations,
)
from app.services.exit_candidates import persist_exit_candidates
from app.services.grade_before_sell import persist_grade_before_sell_recommendations
from app.services.hold_sell_intelligence import persist_hold_sell_recommendations
from app.services.portfolio_rebalancing import persist_portfolio_rebalancing_recommendations
from app.services.purchase_budgets import get_purchase_budget_row
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


def _seed_release(
    session: Session,
    *,
    owner_user_id: int,
    series_name: str,
    issue_number: str,
    foc_date: date,
) -> ReleaseIssue:
    series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher="Image",
        series_name=series_name,
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    issue = ReleaseIssue(
        owner_user_id=owner_user_id,
        release_uuid=f"{series_name}-{issue_number}-x",
        series_id=int(series.id or 0),
        issue_number=issue_number,
        title=f"{series_name} {issue_number}",
        release_status="SCHEDULED",
        foc_date=foc_date,
        release_date=foc_date + timedelta(days=21),
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    return issue


def _seed_stack(client: TestClient, session: Session, email: str) -> int:
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
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

    issue16 = _seed_release(
        session,
        owner_user_id=owner_id,
        series_name="Battle Beast",
        issue_number="16",
        foc_date=date.today() + timedelta(days=5),
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
    session.commit()

    assert grade_inv is not None
    client.post(
        "/grading-candidates",
        json={
            "inventory_item_id": grade_inv,
            "target_grader": "PSA",
            "candidate_priority": "HIGH",
            "replay_key": f"csr-{email}",
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
    return owner_id


def test_multi_system_recommendation_generated(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "csr-multi@example.com")
    generate_cross_system_recommendations(session, owner_user_id=owner_id)
    items, _ = list_latest_cross_system_recommendations(session, owner_user_id=owner_id)
    acquire = next(i for i in items if i.recommendation_type == "ACQUIRE" and i.title.endswith("#3"))
    assert len(acquire.source_systems) >= 2
    assert acquire.recommendation_rank >= 1


def test_confidence_boost_works(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "csr-conf@example.com")
    generate_cross_system_recommendations(session, owner_user_id=owner_id)
    items, _ = list_latest_cross_system_recommendations(session, owner_user_id=owner_id)
    acquire = next(i for i in items if i.title.endswith("#3") and i.recommendation_type == "ACQUIRE")
    assert acquire.confidence_score >= 0.58


def test_conflict_resolution_grade_over_sell(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "csr-conflict@example.com")
    candidates = build_cross_system_candidates(session, owner_user_id=owner_id)
    beast = [c for c in candidates if c.title == "Battle Beast #1"]
    assert len(beast) == 1
    assert beast[0].recommendation_type == "GRADE"
    assert "Resolved GRADE vs SELL" in beast[0].rationale or "grading" in beast[0].rationale.lower()


def test_ranking_works(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "csr-rank@example.com")
    generate_cross_system_recommendations(session, owner_user_id=owner_id)
    items, _ = list_latest_cross_system_recommendations(session, owner_user_id=owner_id)
    ranks = [i.recommendation_rank for i in items]
    assert ranks == sorted(ranks)
    assert min(ranks) == 1
    assert ranks == list(range(1, len(ranks) + 1))


def test_budget_aware_prioritization(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "csr-budget@example.com")
    budget = get_purchase_budget_row(session, owner_user_id=owner_id)
    budget.monthly_budget = 75.0
    budget.is_active = True
    session.add(budget)
    session.commit()
    generate_cross_system_recommendations(session, owner_user_id=owner_id)
    items, _ = list_latest_cross_system_recommendations(session, owner_user_id=owner_id)
    acquire = next((i for i in items if i.recommendation_type == "ACQUIRE"), None)
    preorder = next((i for i in items if i.recommendation_type == "PREORDER"), None)
    assert acquire is not None
    if preorder is not None:
        assert acquire.recommendation_rank <= preorder.recommendation_rank
        assert "Budget constrained" in acquire.rationale or "Budget constrained" in preorder.rationale


def test_deterministic_ordering(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "csr-det@example.com")
    c1 = build_cross_system_candidates(session, owner_user_id=owner_id)
    c2 = build_cross_system_candidates(session, owner_user_id=owner_id)
    k1 = [(c.recommendation_type, c.title, c.priority_score, c.confidence_score) for c in c1]
    k2 = [(c.recommendation_type, c.title, c.priority_score, c.confidence_score) for c in c2]
    assert k1 == k2


def test_idempotency(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "csr-idem@example.com")
    first = generate_cross_system_recommendations(session, owner_user_id=owner_id)
    second = generate_cross_system_recommendations(session, owner_user_id=owner_id)
    assert first >= 1
    assert second == 0


def test_owner_isolation(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "csr-a@example.com")
    owner_a = _seed_stack(client, session, "csr-a@example.com")
    generate_cross_system_recommendations(session, owner_user_id=owner_a)
    token_b = register_and_login(client, "csr-b@example.com")
    rsp_a = client.get("/api/v1/cross-system-recommendations/latest", headers=auth_headers(token_a))
    rsp_b = client.get("/api/v1/cross-system-recommendations/latest", headers=auth_headers(token_b))
    assert len(rsp_a.json()["data"]["items"]) >= 1
    assert rsp_b.json()["data"]["pagination"]["total_count"] == 0
