from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, ReleaseIssue, ReleaseSeries, User
from app.models.pull_list import PullListDecision
from app.models.unified_collector_intelligence import UnifiedCollectorRecommendation
from app.services.acquisition_opportunities import persist_acquisition_opportunities
from app.services.collection_gaps import persist_collection_gaps
from app.services.exit_candidates import persist_exit_candidates
from app.services.grade_before_sell import persist_grade_before_sell_recommendations
from app.services.hold_sell_intelligence import persist_hold_sell_recommendations
from app.services.portfolio_rebalancing import persist_portfolio_rebalancing_recommendations
from app.services.sell_candidates import generate_sell_candidate_recommendations
from app.services.unified_collector_intelligence import (
    generate_unified_collector_recommendations,
    list_latest_unified_collector_recommendations,
)
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
        release_uuid=f"{series_name}-{issue_number}-uuid",
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

    today = date.today()
    issue16 = _seed_release(
        session,
        owner_user_id=owner_id,
        series_name="Battle Beast",
        issue_number="16",
        foc_date=today + timedelta(days=5),
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
            "replay_key": f"uni-{email}",
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


def test_preorder_recommendation_generated(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "uni-pre@example.com")
    generate_unified_collector_recommendations(session, owner_user_id=owner_id)
    items, _ = list_latest_unified_collector_recommendations(session, owner_user_id=owner_id)
    assert any(i.recommendation_type == "PREORDER" and "16" in i.title for i in items)


def test_acquire_recommendation_generated(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "uni-acq@example.com")
    generate_unified_collector_recommendations(session, owner_user_id=owner_id)
    items, _ = list_latest_unified_collector_recommendations(session, owner_user_id=owner_id)
    acquire = [i for i in items if i.recommendation_type == "ACQUIRE" and "#3" in i.title]
    assert acquire
    assert "P54_PORTFOLIO" in acquire[0].source_systems or "P55_ACQUISITION" in acquire[0].source_systems


def test_grade_recommendation_generated(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "uni-grade@example.com")
    generate_unified_collector_recommendations(session, owner_user_id=owner_id)
    items, _ = list_latest_unified_collector_recommendations(session, owner_user_id=owner_id)
    assert any(i.recommendation_type == "GRADE" for i in items)


def test_sell_recommendation_generated(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "uni-sell@example.com")
    generate_unified_collector_recommendations(session, owner_user_id=owner_id)
    items, _ = list_latest_unified_collector_recommendations(session, owner_user_id=owner_id)
    assert any(i.recommendation_type == "SELL" for i in items)


def test_rebalance_recommendation_generated(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "uni-rebal@example.com")
    generate_unified_collector_recommendations(session, owner_user_id=owner_id)
    items, _ = list_latest_unified_collector_recommendations(session, owner_user_id=owner_id)
    assert any(i.recommendation_type == "REBALANCE" for i in items)


def test_multi_system_confidence_boost(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "uni-multi@example.com")
    generate_unified_collector_recommendations(session, owner_user_id=owner_id)
    items, _ = list_latest_unified_collector_recommendations(session, owner_user_id=owner_id)
    merged = next(i for i in items if i.recommendation_type == "ACQUIRE" and "#3" in i.title)
    assert len(merged.source_systems) >= 2
    assert merged.confidence_score >= 0.58


def test_idempotency(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "uni-idem@example.com")
    first = generate_unified_collector_recommendations(session, owner_user_id=owner_id)
    second = generate_unified_collector_recommendations(session, owner_user_id=owner_id)
    assert first >= 1
    assert second == 0
    count = len(
        session.exec(
            select(UnifiedCollectorRecommendation).where(UnifiedCollectorRecommendation.owner_user_id == owner_id)
        ).all()
    )
    assert count == first


def test_owner_isolation(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "uni-a@example.com")
    register_and_login(client, "uni-b@example.com")
    owner_a = _seed_stack(client, session, "uni-a@example.com")
    generate_unified_collector_recommendations(session, owner_user_id=owner_a)
    token_b = register_and_login(client, "uni-b@example.com")
    rsp_a = client.get("/api/v1/unified-intelligence/latest", headers=auth_headers(token_a))
    rsp_b = client.get("/api/v1/unified-intelligence/latest", headers=auth_headers(token_b))
    assert rsp_a.status_code == 200
    assert len(rsp_a.json()["data"]["items"]) >= 1
    assert rsp_b.json()["data"]["pagination"]["total_count"] == 0
