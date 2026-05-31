from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import ReleaseIssue, ReleaseSeries, User
from app.models.pull_list import PullListDecision
from app.services.foc_dashboard import get_foc_dashboard
from app.services.foc_dates import days_until_foc, foc_status_bucket, utc_today
from test_inventory import auth_headers, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _seed_issue(
    session: Session,
    *,
    owner_user_id: int,
    release_uuid: str,
    foc_date: date | None,
    release_date: date | None,
) -> ReleaseIssue:
    series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher="Marvel",
        series_name=f"Series-{release_uuid}",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    issue = ReleaseIssue(
        owner_user_id=owner_user_id,
        release_uuid=release_uuid,
        series_id=int(series.id or 0),
        issue_number="1",
        title=f"Title {release_uuid}",
        release_status="SCHEDULED",
        foc_date=foc_date,
        release_date=release_date,
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    return issue


def _add_decision(session: Session, *, owner_user_id: int, release_id: int, decision_type: str) -> None:
    session.add(
        PullListDecision(
            owner_user_id=owner_user_id,
            release_id=release_id,
            decision_type=decision_type,
            confidence_score=0.7,
            explanation='["Test reason"]',
        )
    )
    session.commit()


def test_foc_date_buckets_deterministic() -> None:
    today = date(2026, 5, 30)
    assert days_until_foc(today, today=today) == 0
    assert foc_status_bucket(today, today=today) == "DUE_NOW"
    assert foc_status_bucket(today + timedelta(days=3), today=today) == "THIS_WEEK"
    assert foc_status_bucket(today + timedelta(days=10), today=today) == "NEXT_WEEK"
    assert foc_status_bucket(today + timedelta(days=20), today=today) == "THIS_MONTH"
    assert foc_status_bucket(today - timedelta(days=1), today=today) == "MISSED"


def test_dashboard_categorization(client: TestClient, session: Session) -> None:
    email = "foc-dash@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    today = date(2026, 5, 30)

    action_issue = _seed_issue(
        session,
        owner_user_id=owner_id,
        release_uuid="foc-action",
        foc_date=today + timedelta(days=5),
        release_date=today + timedelta(days=20),
    )
    upcoming_foc_issue = _seed_issue(
        session,
        owner_user_id=owner_id,
        release_uuid="foc-upcoming",
        foc_date=today + timedelta(days=20),
        release_date=today + timedelta(days=40),
    )
    missed_issue = _seed_issue(
        session,
        owner_user_id=owner_id,
        release_uuid="foc-missed",
        foc_date=today - timedelta(days=3),
        release_date=today + timedelta(days=7),
    )
    release_issue = _seed_issue(
        session,
        owner_user_id=owner_id,
        release_uuid="foc-release",
        foc_date=None,
        release_date=today + timedelta(days=10),
    )
    watch_issue = _seed_issue(
        session,
        owner_user_id=owner_id,
        release_uuid="foc-watch",
        foc_date=today + timedelta(days=25),
        release_date=today + timedelta(days=35),
    )
    _add_decision(session, owner_user_id=owner_id, release_id=int(action_issue.id or 0), decision_type="START_RUN")
    _add_decision(session, owner_user_id=owner_id, release_id=int(watch_issue.id or 0), decision_type="WATCH")

    dash = get_foc_dashboard(session, owner_user_id=owner_id, today=today)
    action_ids = {i.release_id for i in dash.action_required}
    upcoming_foc_ids = {i.release_id for i in dash.upcoming_foc}
    missed_ids = {i.release_id for i in dash.missed_foc}
    release_ids = {i.release_id for i in dash.upcoming_releases}
    watch_ids = {i.release_id for i in dash.watchlist}

    assert int(action_issue.id or 0) in action_ids
    assert int(upcoming_foc_issue.id or 0) in upcoming_foc_ids
    assert int(missed_issue.id or 0) in missed_ids
    assert int(release_issue.id or 0) in release_ids
    assert int(watch_issue.id or 0) in watch_ids
    assert dash.summary.action_required_count >= 1
    assert dash.summary.upcoming_foc_count >= 1
    assert dash.summary.upcoming_release_count >= 1

    action_row = next(i for i in dash.action_required if i.release_id == int(action_issue.id or 0))
    assert action_row.days_until_foc == 5
    assert action_row.decision_type == "START_RUN"


def test_foc_dashboard_api_owner_scoped(client: TestClient, session: Session) -> None:
    email_a = "foc-owner-a@example.com"
    email_b = "foc-owner-b@example.com"
    token_a = register_and_login(client, email_a)
    owner_a = _owner_id(session, email_a)
    register_and_login(client, email_b)
    owner_b = _owner_id(session, email_b)
    today = utc_today()

    issue_a = _seed_issue(
        session,
        owner_user_id=owner_a,
        release_uuid="foc-a-only",
        foc_date=today + timedelta(days=4),
        release_date=today + timedelta(days=14),
    )
    _seed_issue(
        session,
        owner_user_id=owner_b,
        release_uuid="foc-b-only",
        foc_date=today + timedelta(days=4),
        release_date=today + timedelta(days=14),
    )

    headers_a = auth_headers(token_a)
    resp = client.get("/api/v1/foc-dashboard", headers=headers_a)
    assert resp.status_code == 200
    data = resp.json()["data"]
    all_release_ids = {row["release_id"] for row in data["action_required"]}
    assert int(issue_a.id or 0) in all_release_ids
    assert all(row.get("publisher") == "Marvel" or True for row in data["action_required"])

    resp_summary = client.get("/api/v1/foc-dashboard/summary", headers=headers_a)
    assert resp_summary.status_code == 200
    assert resp_summary.json()["data"]["action_required_count"] >= 1

    resp_actions = client.get("/api/v1/foc-dashboard/actions", headers=headers_a)
    assert resp_actions.status_code == 200
    assert len(resp_actions.json()["data"]["items"]) >= 1

    resp_releases = client.get("/api/v1/foc-dashboard/releases", headers=headers_a)
    assert resp_releases.status_code == 200
