from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.services.grade_before_sell import persist_grade_before_sell_recommendations
from app.services.grade_before_sell_engine import (
    _roi,
    _value_gain,
    generate_grade_before_sell_recommendations,
)
from test_inventory import auth_headers, create_order, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _inventory_id(client: TestClient, token: str) -> int:
    rsp = create_order(client, token)
    order_id = rsp["order_id"]
    detail = client.get(f"/orders/{order_id}", headers=auth_headers(token))
    return detail.json()["items"][0]["inventory_copy_ids"][0]


def _create_grading_candidate(
    client: TestClient,
    token: str,
    inv_id: int,
    *,
    replay_key: str,
    raw: str,
    graded: str,
    cost: str,
    priority: str = "HIGH",
) -> None:
    rsp = client.post(
        "/grading-candidates",
        json={
            "inventory_item_id": inv_id,
            "target_grader": "PSA",
            "candidate_priority": priority,
            "replay_key": replay_key,
            "estimated_raw_value": raw,
            "estimated_graded_value": graded,
            "estimated_grading_cost": cost,
        },
        headers=auth_headers(token),
    )
    assert rsp.status_code in (200, 201), rsp.text


def test_strong_grading_upside_grade_before_sell(client: TestClient, session: Session) -> None:
    email = "gbs-strong@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    inv_id = _inventory_id(client, token)
    _create_grading_candidate(
        client,
        token,
        inv_id,
        replay_key="gbs-strong-1",
        raw="100.00",
        graded="400.00",
        cost="40.00",
    )
    row = generate_grade_before_sell_recommendations(session, owner_user_id=owner_id)[0]
    assert row.recommendation == "GRADE_BEFORE_SELL"
    assert row.expected_value_gain == 260.0
    assert row.expected_roi == 6.5
    assert row.confidence_score > 0


def test_weak_grading_upside_sell_raw(client: TestClient, session: Session) -> None:
    email = "gbs-weak@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    inv_id = _inventory_id(client, token)
    _create_grading_candidate(
        client,
        token,
        inv_id,
        replay_key="gbs-weak-1",
        raw="100.00",
        graded="110.00",
        cost="40.00",
    )
    row = generate_grade_before_sell_recommendations(session, owner_user_id=owner_id)[0]
    assert row.recommendation == "SELL_RAW"
    assert row.expected_value_gain < 0
    assert row.expected_roi < 0.25


def test_uncertain_valuation_hold_for_review(client: TestClient, session: Session) -> None:
    email = "gbs-review@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _inventory_id(client, token)
    row = generate_grade_before_sell_recommendations(session, owner_user_id=owner_id)[0]
    assert row.recommendation == "HOLD_FOR_REVIEW"
    assert "uncertain" in row.rationale.lower()


def test_roi_and_value_gain_formulas() -> None:
    gain = _value_gain(expected_graded=400.0, current=100.0, cost=40.0)
    assert gain == 260.0
    assert _roi(gain=gain, cost=40.0) == 6.5


def test_idempotency(client: TestClient, session: Session) -> None:
    email = "gbs-idem@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    inv_id = _inventory_id(client, token)
    _create_grading_candidate(
        client,
        token,
        inv_id,
        replay_key="gbs-idem-1",
        raw="100.00",
        graded="400.00",
        cost="40.00",
    )
    first = persist_grade_before_sell_recommendations(session, owner_user_id=owner_id)
    assert first == 1
    second = persist_grade_before_sell_recommendations(session, owner_user_id=owner_id)
    assert second == 0


def test_deterministic_outputs(client: TestClient, session: Session) -> None:
    email = "gbs-det@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    inv_id = _inventory_id(client, token)
    _create_grading_candidate(
        client,
        token,
        inv_id,
        replay_key="gbs-det-1",
        raw="50.00",
        graded="150.00",
        cost="35.00",
    )
    r1 = generate_grade_before_sell_recommendations(session, owner_user_id=owner_id)
    r2 = generate_grade_before_sell_recommendations(session, owner_user_id=owner_id)
    assert [(x.inventory_item_id, x.recommendation, x.expected_roi) for x in r1] == [
        (x.inventory_item_id, x.recommendation, x.expected_roi) for x in r2
    ]


def test_api_owner_isolation(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "gbs-a@example.com")
    token_b = register_and_login(client, "gbs-b@example.com")
    owner_a = _owner_id(session, "gbs-a@example.com")
    inv_id = _inventory_id(client, token_a)
    _create_grading_candidate(
        client,
        token_a,
        inv_id,
        replay_key="gbs-a-1",
        raw="100.00",
        graded="300.00",
        cost="40.00",
    )
    client.get("/api/v1/grade-before-sell/latest", headers=auth_headers(token_a))
    list_a = client.get("/api/v1/grade-before-sell", headers=auth_headers(token_a))
    list_b = client.get("/api/v1/grade-before-sell", headers=auth_headers(token_b))
    assert len(list_a.json()["data"]["items"]) == 1
    assert len(list_b.json()["data"]["items"]) == 0
    assert owner_a > 0
