from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import ReleaseIssue, ReleaseSeries, User
from test_inventory import auth_headers, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_pull_list_crud_and_owner_scoping(client: TestClient, session: Session) -> None:
    email_a = "pull-list-a@example.com"
    email_b = "pull-list-b@example.com"
    token_a = register_and_login(client, email_a)
    token_b = register_and_login(client, email_b)
    owner_a = _owner_id(session, email_a)

    series = ReleaseSeries(
        owner_user_id=owner_a,
        publisher="DC",
        series_name="Batman",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    release = ReleaseIssue(
        owner_user_id=owner_a,
        release_uuid="pull-list-release-1",
        series_id=int(series.id or 0),
        issue_number="12",
        title="Batman #12",
        release_status="SCHEDULED",
        release_date=date.today() + timedelta(days=30),
        foc_date=date.today() + timedelta(days=7),
    )
    session.add(release)
    session.commit()
    session.refresh(release)

    create_resp = client.post(
        "/api/v1/pull-lists",
        headers=auth_headers(token_a),
        json={"publisher": "DC", "series_name": "Batman", "status": "ACTIVE"},
    )
    assert create_resp.status_code == 200, create_resp.text
    pull_list_id = create_resp.json()["data"]["pull_list"]["id"]

    attach_resp = client.post(
        f"/api/v1/pull-lists/{pull_list_id}/issues",
        headers=auth_headers(token_a),
        json={"release_id": int(release.id or 0)},
    )
    assert attach_resp.status_code == 200, attach_resp.text
    assert len(attach_resp.json()["data"]["issues"]) == 1
    assert attach_resp.json()["data"]["issues"][0]["issue_number"] == "12"

    detail = client.get(f"/api/v1/pull-lists/{pull_list_id}", headers=auth_headers(token_a))
    assert detail.status_code == 200
    assert detail.json()["data"]["pull_list"]["upcoming_issue_count"] >= 1

    list_resp = client.get("/api/v1/pull-lists?search=Batman", headers=auth_headers(token_a))
    assert list_resp.status_code == 200
    assert list_resp.json()["data"]["pagination"]["total_count"] >= 1

    patch_resp = client.patch(
        f"/api/v1/pull-lists/{pull_list_id}",
        headers=auth_headers(token_a),
        json={"status": "PAUSED"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["data"]["pull_list"]["status"] == "PAUSED"

    forbidden = client.get(f"/api/v1/pull-lists/{pull_list_id}", headers=auth_headers(token_b))
    assert forbidden.status_code == 404

    attach_forbidden = client.post(
        f"/api/v1/pull-lists/{pull_list_id}/issues",
        headers=auth_headers(token_b),
        json={"release_id": int(release.id or 0)},
    )
    assert attach_forbidden.status_code == 404


def test_derive_action_state_released() -> None:
    from app.services.pull_list import derive_action_state

    today = date(2026, 6, 1)
    assert derive_action_state(foc_date=date(2026, 5, 1), release_date=date(2026, 5, 28), today=today) == "RELEASED"
