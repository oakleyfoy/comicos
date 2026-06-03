from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.models.daily_action_engine import DailyCollectorAction
from app.models.pull_list import PullListDecision
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.acquisition_opportunities import persist_acquisition_opportunities
from app.services.collection_gaps import persist_collection_gaps
from app.services.daily_action_engine import (
    _build_drafts,
    generate_daily_actions,
    list_latest_daily_actions,
)
from app.services.exit_candidates import persist_exit_candidates
from app.services.grade_before_sell import persist_grade_before_sell_recommendations
from app.services.hold_sell_intelligence import persist_hold_sell_recommendations
from app.services.portfolio_rebalancing import persist_portfolio_rebalancing_recommendations
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


def _seed_stack(client: TestClient, session: Session, email: str, *, foc_days: int = 3) -> int:
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
    foc_date = date.today() + timedelta(days=foc_days)
    issue16 = ReleaseIssue(
        owner_user_id=owner_id,
        release_uuid=f"daily-16-{email}",
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
        PullListDecision(
            owner_user_id=owner_id,
            release_id=int(issue16.id or 0),
            decision_type="CONTINUE_RUN",
            confidence_score=0.85,
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
            "replay_key": f"daily-{email}",
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


def test_preorder_action_generated(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "da-pre@example.com", foc_days=3)
    generate_daily_actions(session, owner_user_id=owner_id)
    items, _ = list_latest_daily_actions(session, owner_user_id=owner_id)
    pre = next(i for i in items if i.action_type == "PREORDER" and i.title == "Battle Beast #16")
    assert pre.priority_score >= 90.0
    assert pre.due_date is not None


def test_acquisition_action_generated(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "da-acq@example.com")
    generate_daily_actions(session, owner_user_id=owner_id)
    items, _ = list_latest_daily_actions(session, owner_user_id=owner_id)
    assert any(i.action_type == "ACQUIRE" and i.title.endswith("#3") for i in items)


def test_grade_action_generated(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "da-grade@example.com")
    generate_daily_actions(session, owner_user_id=owner_id)
    items, _ = list_latest_daily_actions(session, owner_user_id=owner_id)
    assert any(i.action_type == "GRADE" for i in items)


def test_sell_action_generated(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "da-sell@example.com")
    generate_daily_actions(session, owner_user_id=owner_id)
    items, _ = list_latest_daily_actions(session, owner_user_id=owner_id)
    assert any(i.action_type == "SELL" for i in items)


def test_rebalance_action_generated(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "da-rebal@example.com")
    generate_daily_actions(session, owner_user_id=owner_id)
    items, _ = list_latest_daily_actions(session, owner_user_id=owner_id)
    assert any(i.action_type == "REBALANCE" for i in items)


def test_due_date_generation(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "da-due@example.com", foc_days=3)
    generate_daily_actions(session, owner_user_id=owner_id)
    items, _ = list_latest_daily_actions(session, owner_user_id=owner_id)
    pre = next(i for i in items if i.action_type == "PREORDER" and "16" in i.title)
    assert pre.due_date == date.today() + timedelta(days=3)


def test_deterministic_ordering(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "da-det@example.com")
    d1 = _build_drafts(session, owner_user_id=owner_id)
    d2 = _build_drafts(session, owner_user_id=owner_id)
    k1 = [(d.action_type, d.title, d.priority_score, d.due_date) for d in d1]
    k2 = [(d.action_type, d.title, d.priority_score, d.due_date) for d in d2]
    assert k1 == k2


def test_idempotency(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "da-idem@example.com")
    first = generate_daily_actions(session, owner_user_id=owner_id)
    second = generate_daily_actions(session, owner_user_id=owner_id)
    assert first >= 1
    assert second == 0


def test_owner_isolation(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "da-a@example.com")
    owner_a = _seed_stack(client, session, "da-a@example.com")
    generate_daily_actions(session, owner_user_id=owner_a)
    token_b = register_and_login(client, "da-b@example.com")
    rsp_a = client.get("/api/v1/daily-actions/latest", headers=auth_headers(token_a))
    rsp_b = client.get("/api/v1/daily-actions/latest", headers=auth_headers(token_b))
    assert len(rsp_a.json()["data"]["items"]) >= 1
    assert rsp_b.json()["data"]["pagination"]["total_count"] == 0
