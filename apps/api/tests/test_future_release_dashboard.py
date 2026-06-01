from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.services.future_release_dashboard import (
    build_future_release_dashboard,
    build_future_release_dashboard_summary,
)
from test_inventory import auth_headers, create_order, register_and_login
from test_future_release_matches import (
    _battle_beast_items,
    _import_future_lunar_issue,
    _owner_id,
)


def test_future_release_dashboard_sections(client: TestClient, session: Session) -> None:
    email = "frd-sections@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items([str(n) for n in range(1, 16)]))
    today = date.today()
    _import_future_lunar_issue(
        session,
        owner_user_id=owner_id,
        issue_number="16",
        foc_date=today + timedelta(days=2),
        release_date=today + timedelta(days=21),
    )

    dash = build_future_release_dashboard(session, owner_user_id=owner_id)
    assert len(dash.next_issues) >= 1
    assert dash.next_issues[0].next_issue == "16"
    assert len(dash.upcoming_foc) >= 1
    assert len(dash.preorder_now) >= 1
    assert dash.preorder_now[0].action_type == "PREORDER_NOW"


def test_future_release_dashboard_summary_counts(client: TestClient, session: Session) -> None:
    email = "frd-summary@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items(["1", "2", "3", "4", "5"]))
    today = date.today()
    _import_future_lunar_issue(
        session,
        owner_user_id=owner_id,
        issue_number="6",
        foc_date=today + timedelta(days=5),
        release_date=today + timedelta(days=20),
    )

    summary = build_future_release_dashboard_summary(session, owner_user_id=owner_id, refresh=True)
    assert summary.active_runs >= 1
    assert summary.upcoming_issues >= 1
    assert summary.foc_this_week >= 1
    assert summary.preorder_now >= 0


def test_future_release_dashboard_api(client: TestClient, session: Session) -> None:
    email = "frd-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items(["14", "15"]))
    today = date.today()
    _import_future_lunar_issue(
        session,
        owner_user_id=owner_id,
        issue_number="16",
        foc_date=today - timedelta(days=1),
        release_date=today + timedelta(days=14),
    )

    full = client.get("/api/v1/future-release-dashboard", headers=auth_headers(token))
    assert full.status_code == 200
    data = full.json()["data"]
    assert "next_issues" in data
    assert "missed_foc" in data
    assert len(data["missed_foc"]) >= 1

    summary = client.get("/api/v1/future-release-dashboard/summary", headers=auth_headers(token))
    assert summary.status_code == 200
    assert summary.json()["data"]["missed_foc"] >= 1
