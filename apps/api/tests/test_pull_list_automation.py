from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import ReleaseIssue, ReleaseSeries, User
from app.models.pull_list import PullListDecision, PullListIssue
from app.models.recommendation_v2 import RecommendationRunV2, RecommendationScoreV2
from app.services.foc_dashboard import get_foc_dashboard
from app.services.foc_dates import utc_today
from app.services.pull_list import attach_release_to_pull_list, create_pull_list, derive_action_state
from app.services.pull_list_automation import run_pull_list_refresh
from app.services.pull_list_decisions import generate_pull_list_decisions
from app.services.pull_list_scheduler import verify_upstream_refresh_order
from app.schemas.pull_list import PullListCreate, PullListIssueAttachRequest
from test_inventory import auth_headers, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _seed_owner_catalog(session: Session, *, owner_user_id: int) -> ReleaseIssue:
    series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher="Marvel",
        series_name="X-Men",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    today = utc_today()
    issue = ReleaseIssue(
        owner_user_id=owner_user_id,
        release_uuid="pla-xmen-1",
        series_id=int(series.id or 0),
        issue_number="1",
        title="X-Men #1",
        release_status="SCHEDULED",
        foc_date=today + timedelta(days=5),
        release_date=today + timedelta(days=20),
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    run = RecommendationRunV2(owner_user_id=owner_user_id, status="COMPLETED")
    session.add(run)
    session.commit()
    session.refresh(run)
    session.add(
        RecommendationScoreV2(
            owner_user_id=owner_user_id,
            recommendation_run_id=int(run.id or 0),
            release_issue_id=int(issue.id or 0),
            total_score=80.0,
            recommendation_tier="STRONG_BUY",
            recommendation_type="INVESTMENT_NUMBER_ONE",
            confidence_score=0.9,
        )
    )
    session.commit()
    return issue


def test_generate_pull_list_decisions_idempotent(client: TestClient, session: Session) -> None:
    email = "pla-idem@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _seed_owner_catalog(session, owner_user_id=owner_id)
    first = generate_pull_list_decisions(session, owner_user_id=owner_id)
    second = generate_pull_list_decisions(session, owner_user_id=owner_id)
    assert first >= 1
    assert second == 0
    count = len(session.exec(select(PullListDecision).where(PullListDecision.owner_user_id == owner_id)).all())
    assert count == first


def test_run_pull_list_refresh_records_run(client: TestClient, session: Session) -> None:
    email = "pla-run@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _seed_owner_catalog(session, owner_user_id=owner_id)
    run = run_pull_list_refresh(session, owner_user_ids=[owner_id])
    assert run.status == "SUCCESS"
    assert run.owners_processed == 1
    assert run.decisions_created >= 1
    assert run.runtime_ms >= 0

    dash_before = get_foc_dashboard(session, owner_user_id=owner_id, today=utc_today())
    run2 = run_pull_list_refresh(session, owner_user_ids=[owner_id])
    dash_after = get_foc_dashboard(session, owner_user_id=owner_id, today=utc_today())
    assert run2.decisions_created == 0
    assert dash_before.summary.action_required_count == dash_after.summary.action_required_count


def test_action_state_transitions_deterministic() -> None:
    today = date(2026, 6, 1)
    assert (
        derive_action_state(foc_date=today + timedelta(days=30), release_date=today + timedelta(days=40), today=today)
        == "UPCOMING"
    )
    assert (
        derive_action_state(foc_date=today + timedelta(days=10), release_date=today + timedelta(days=40), today=today)
        == "FOC_APPROACHING"
    )
    assert (
        derive_action_state(foc_date=today - timedelta(days=1), release_date=today + timedelta(days=10), today=today)
        == "MISSED"
    )
    assert derive_action_state(foc_date=today - timedelta(days=5), release_date=today, today=today) == "RELEASED"


def test_sync_action_states_on_refresh(client: TestClient, session: Session) -> None:
    email = "pla-state@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    issue = _seed_owner_catalog(session, owner_user_id=owner_id)
    pl = create_pull_list(session, owner_user_id=owner_id, payload=PullListCreate(publisher="Marvel", series_name="X-Men"))
    attach_release_to_pull_list(
        session,
        owner_user_id=owner_id,
        pull_list_id=pl.pull_list.id,
        payload=PullListIssueAttachRequest(release_id=int(issue.id or 0)),
    )
    run_pull_list_refresh(session, owner_user_ids=[owner_id], today=utc_today())
    pl_issue = session.exec(select(PullListIssue).where(PullListIssue.release_id == int(issue.id or 0))).one()
    assert pl_issue.action_state == "FOC_APPROACHING"


def test_pull_list_automation_api(client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    email = "pla-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _seed_owner_catalog(session, owner_user_id=owner_id)

    denied = client.post("/api/v1/pull-list-automation/run", headers=auth_headers(token))
    assert denied.status_code == 403

    runs = client.get("/api/v1/pull-list-automation/runs", headers=auth_headers(token))
    assert runs.status_code == 200

    monkeypatch.setenv("OPS_ADMIN_EMAILS", "pla-ops-admin@example.com")
    get_settings.cache_clear()
    ops_token = register_and_login(client, "pla-ops-admin@example.com")
    ok = client.post("/api/v1/pull-list-automation/run", headers=auth_headers(ops_token))
    assert ok.status_code == 200
    assert ok.json()["data"]["run"]["status"] == "SUCCESS"

    latest = client.get("/api/v1/pull-list-automation/latest", headers=auth_headers(token))
    assert latest.status_code == 200


def test_upstream_order_check(client: TestClient, session: Session) -> None:
    ok, message = verify_upstream_refresh_order(session)
    assert isinstance(ok, bool)
    assert message
