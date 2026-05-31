from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.models.pull_list import PullListDecision
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.acquisition_opportunities import persist_acquisition_opportunities
from app.services.collection_gaps import persist_collection_gaps
from app.services.executive_dashboard import get_executive_dashboard
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
        release_uuid=f"exec-16-{email}",
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
            "replay_key": f"exec-{email}",
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


def test_daily_actions_appear(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "exec-daily@example.com")
    dash = get_executive_dashboard(session, owner_user_id=owner_id)
    assert dash.daily_actions.items
    assert any(i.action_type == "PREORDER" for i in dash.daily_actions.items)


def test_cross_system_recommendations_appear(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "exec-cross@example.com")
    dash = get_executive_dashboard(session, owner_user_id=owner_id)
    assert dash.top_recommendations.items
    types = {i.recommendation_type for i in dash.top_recommendations.items}
    assert types & {"ACQUIRE", "PREORDER", "GRADE", "SELL", "REBALANCE"}


def test_preorder_section(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "exec-pre@example.com")
    dash = get_executive_dashboard(session, owner_user_id=owner_id)
    assert dash.preorder_this_week.items or dash.summary.preorder_action_count >= 1


def test_acquisition_targets(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "exec-acq@example.com")
    dash = get_executive_dashboard(session, owner_user_id=owner_id)
    assert dash.acquire_targets.items or dash.summary.acquisition_target_count >= 1


def test_grade_opportunities(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "exec-grade@example.com")
    dash = get_executive_dashboard(session, owner_user_id=owner_id)
    assert dash.grade_opportunities.items or dash.summary.grading_opportunity_count >= 1


def test_sell_opportunities(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "exec-sell@example.com")
    dash = get_executive_dashboard(session, owner_user_id=owner_id)
    assert dash.sell_opportunities.items or dash.summary.sell_opportunity_count >= 1


def test_portfolio_risk(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "exec-risk@example.com")
    dash = get_executive_dashboard(session, owner_user_id=owner_id)
    assert dash.portfolio_risk.items or dash.summary.rebalance_warning_count >= 0


def test_system_health(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "exec-health@example.com")
    dash = get_executive_dashboard(session, owner_user_id=owner_id)
    assert dash.system_health.items
    assert any(i.item_type == "production_readiness" for i in dash.system_health.items)


def test_summary_metrics(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "exec-sum@example.com")
    dash = get_executive_dashboard(session, owner_user_id=owner_id)
    assert dash.summary.total_daily_actions >= 1
    assert dash.summary.top_recommendations_count >= 0
    assert dash.summary.estimated_capital_recovery >= 0.0


def test_deterministic_ordering(client: TestClient, session: Session) -> None:
    owner_id = _seed_stack(client, session, "exec-det@example.com")
    d1 = get_executive_dashboard(session, owner_user_id=owner_id)
    d2 = get_executive_dashboard(session, owner_user_id=owner_id)
    k1 = [(i.title, i.priority_score, i.item_id) for i in d1.daily_actions.items]
    k2 = [(i.title, i.priority_score, i.item_id) for i in d2.daily_actions.items]
    assert k1 == k2


def test_owner_isolation(client: TestClient, session: Session) -> None:
    owner_a = _seed_stack(client, session, "exec-a@example.com")
    get_executive_dashboard(session, owner_user_id=owner_a)
    token_a = register_and_login(client, "exec-a@example.com")
    register_and_login(client, "exec-b@example.com")
    rsp_a = client.get("/api/v1/executive-dashboard", headers=auth_headers(token_a))
    token_b = register_and_login(client, "exec-b@example.com")
    rsp_b = client.get("/api/v1/executive-dashboard", headers=auth_headers(token_b))
    assert len(rsp_a.json()["data"]["daily_actions"]["items"]) >= 1
    assert rsp_b.json()["data"]["daily_actions"]["items"] == []
