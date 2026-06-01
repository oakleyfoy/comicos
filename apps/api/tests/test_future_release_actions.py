from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.future_release_match import FutureReleaseMatch
from app.services.future_release_action_engine import (
    determine_action_type,
    generate_future_release_actions,
    score_action_priority,
)
from app.services.future_release_actions import persist_future_release_actions
from test_inventory import auth_headers, create_order, register_and_login
from test_future_release_matches import (
    _battle_beast_items,
    _import_future_lunar_issue,
    _owner_id,
)


def test_action_generation_preorder_now_and_this_week() -> None:
    today = date(2026, 6, 1)
    assert determine_action_type(foc_date=today + timedelta(days=3), today=today) == "PREORDER_NOW"
    assert determine_action_type(foc_date=today + timedelta(days=10), today=today) == "PREORDER_THIS_WEEK"
    assert determine_action_type(foc_date=today + timedelta(days=30), today=today) == "WATCH"


def test_priority_scoring_thresholds() -> None:
    today = date(2026, 6, 1)
    assert score_action_priority(
        action_type="PREORDER_NOW",
        foc_date=today + timedelta(days=3),
        today=today,
    ) >= 95.0
    assert score_action_priority(
        action_type="PREORDER_THIS_WEEK",
        foc_date=today + timedelta(days=7),
        today=today,
    ) >= 85.0


def test_missed_foc_detection() -> None:
    today = date.today()
    assert determine_action_type(foc_date=today - timedelta(days=2), today=today) == "MISSED_FOC"
    match = FutureReleaseMatch(
        owner_user_id=1,
        series_name="Battle Beast",
        issue_number="16",
        publisher="Image",
        foc_date=today - timedelta(days=1),
        release_date=today + timedelta(days=14),
        release_id=99,
        variant_count=2,
        confidence=1.0,
    )
    actions = generate_future_release_actions([match])
    assert len(actions) == 1
    assert actions[0].action_type == "MISSED_FOC"


def test_end_to_end_action_pipeline(client: TestClient, session: Session) -> None:
    email = "fra-pipeline@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items(["14", "15"]))
    today = date.today()
    _import_future_lunar_issue(
        session,
        owner_user_id=owner_id,
        issue_number="16",
        foc_date=today + timedelta(days=2),
        release_date=today + timedelta(days=21),
    )
    client.get("/api/v1/future-release-actions/latest", headers=auth_headers(token))
    assert persist_future_release_actions(session, owner_user_id=owner_id) >= 0

    response = client.get("/api/v1/future-release-actions", headers=auth_headers(token))
    assert response.status_code == 200
    item = response.json()["data"]["items"][0]
    assert item["action_type"] == "PREORDER_NOW"
    assert item["priority_score"] >= 95.0
