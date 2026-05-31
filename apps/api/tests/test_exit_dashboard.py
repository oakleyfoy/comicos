from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.services.exit_candidates import persist_exit_candidates
from app.services.exit_dashboard import get_exit_dashboard
from app.services.grade_before_sell import persist_grade_before_sell_recommendations
from app.services.hold_sell_intelligence import persist_hold_sell_recommendations
from app.services.portfolio_rebalancing import persist_portfolio_rebalancing_recommendations
from app.services.sell_candidates import generate_sell_candidate_recommendations
from test_inventory import auth_headers, create_order, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _seed_exit_stack(client: TestClient, session: Session, email: str) -> tuple[str, int]:
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
            "replay_key": f"exit-dash-{email}",
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
    return token, owner_id


def test_sell_recommendation_on_dashboard(client: TestClient, session: Session) -> None:
    email = "ed-sell@example.com"
    _, owner_id = _seed_exit_stack(client, session, email)
    dash = get_exit_dashboard(session, owner_user_id=owner_id)
    assert len(dash.top_sell_recommendations) >= 1
    assert dash.top_sell_recommendations[0].recommendation == "SELL"


def test_grade_before_sell_on_dashboard(client: TestClient, session: Session) -> None:
    email = "ed-grade@example.com"
    _, owner_id = _seed_exit_stack(client, session, email)
    dash = get_exit_dashboard(session, owner_user_id=owner_id)
    assert any(i.recommendation == "GRADE_BEFORE_SELL" for i in dash.top_grade_before_sell)


def test_reduce_exposure_on_dashboard(client: TestClient, session: Session) -> None:
    email = "ed-rebal@example.com"
    _, owner_id = _seed_exit_stack(client, session, email)
    dash = get_exit_dashboard(session, owner_user_id=owner_id)
    assert any(i.action in {"REDUCE_EXPOSURE", "REVIEW_POSITION"} for i in dash.top_rebalance_actions)


def test_capital_recovery_on_dashboard(client: TestClient, session: Session) -> None:
    email = "ed-cap@example.com"
    _, owner_id = _seed_exit_stack(client, session, email)
    dash = get_exit_dashboard(session, owner_user_id=owner_id)
    assert len(dash.capital_recovery) >= 1
    assert dash.summary.estimated_capital_recovery > 0


def test_review_required_on_dashboard(client: TestClient, session: Session) -> None:
    email = "ed-review@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token)
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one()
    copy.current_fmv = Decimal("8.00")
    copy.acquisition_cost = Decimal("10.00")
    session.add(copy)
    session.commit()
    persist_hold_sell_recommendations(session, owner_user_id=owner_id)
    persist_grade_before_sell_recommendations(session, owner_user_id=owner_id)
    dash = get_exit_dashboard(session, owner_user_id=owner_id)
    assert dash.summary.review_required_count >= 1
    assert len(dash.review_required) >= 1


def test_summary_metrics(client: TestClient, session: Session) -> None:
    email = "ed-sum@example.com"
    _, owner_id = _seed_exit_stack(client, session, email)
    dash = get_exit_dashboard(session, owner_user_id=owner_id)
    assert dash.summary.total_exit_candidates >= 1
    assert dash.summary.sell_recommendations >= 1
    assert dash.summary.grade_before_sell_recommendations >= 1
    assert dash.summary.rebalance_actions >= 1


def test_deterministic_ordering(client: TestClient, session: Session) -> None:
    email = "ed-det@example.com"
    _, owner_id = _seed_exit_stack(client, session, email)
    d1 = get_exit_dashboard(session, owner_user_id=owner_id)
    d2 = get_exit_dashboard(session, owner_user_id=owner_id)
    assert [(i.item_type, i.item_id) for i in d1.top_sell_recommendations] == [
        (i.item_type, i.item_id) for i in d2.top_sell_recommendations
    ]


def test_api_owner_isolation(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "ed-a@example.com")
    token_b = register_and_login(client, "ed-b@example.com")
    _seed_exit_stack(client, session, "ed-a@example.com")
    rsp_a = client.get("/api/v1/exit-dashboard", headers=auth_headers(token_a))
    rsp_b = client.get("/api/v1/exit-dashboard", headers=auth_headers(token_b))
    assert len(rsp_a.json()["data"]["top_sell_recommendations"]) >= 1
    assert rsp_b.json()["data"]["summary"]["total_exit_candidates"] == 0
