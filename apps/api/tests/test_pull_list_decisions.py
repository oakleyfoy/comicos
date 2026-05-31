from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import ReleaseIssue, ReleaseSeries, User
from app.models.pull_list import PullList, PullListIssue
from app.models.recommendation_v2 import RecommendationRunV2, RecommendationScoreV2
from app.services.pull_list import attach_release_to_pull_list, create_pull_list
from app.services.pull_list_decision_engine import (
    DECISION_CONTINUE_RUN,
    DECISION_PASS,
    DECISION_START_RUN,
    DECISION_WATCH,
    evaluate_pull_list_decision,
)
from app.services.pull_list_decisions import generate_pull_list_decisions
from app.schemas.pull_list import PullListCreate
from app.schemas.pull_list import PullListIssueAttachRequest
from test_inventory import auth_headers, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _seed_v2_score(
    session: Session,
    *,
    owner_user_id: int,
    issue: ReleaseIssue,
    tier: str,
    rec_type: str,
    total: float,
    confidence: float,
) -> None:
    run = RecommendationRunV2(owner_user_id=owner_user_id, status="COMPLETED")
    session.add(run)
    session.commit()
    session.refresh(run)
    session.add(
        RecommendationScoreV2(
            owner_user_id=owner_user_id,
            recommendation_run_id=int(run.id or 0),
            release_issue_id=int(issue.id or 0),
            total_score=total,
            recommendation_tier=tier,
            recommendation_type=rec_type,
            confidence_score=confidence,
        )
    )
    session.commit()


def test_continue_run_for_pull_list_issue(client: TestClient, session: Session) -> None:
    email = "pld-continue@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="DC",
        series_name="Batman",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    issue = ReleaseIssue(
        owner_user_id=owner_id,
        release_uuid="pld-batman-12",
        series_id=int(series.id or 0),
        issue_number="12",
        title="Batman #12",
        release_status="SCHEDULED",
        release_date=date.today() + timedelta(days=14),
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    pl = create_pull_list(session, owner_user_id=owner_id, payload=PullListCreate(publisher="DC", series_name="Batman"))
    attach_release_to_pull_list(
        session,
        owner_user_id=owner_id,
        pull_list_id=pl.pull_list.id,
        payload=PullListIssueAttachRequest(release_id=int(issue.id or 0)),
    )
    result = evaluate_pull_list_decision(session, owner_user_id=owner_id, issue=issue, series=series, v2=None)
    assert result.decision_type == DECISION_CONTINUE_RUN
    assert result.reasons


def test_start_run_strong_number_one(client: TestClient, session: Session) -> None:
    email = "pld-start@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="IDW",
        series_name="TMNT",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    issue = ReleaseIssue(
        owner_user_id=owner_id,
        release_uuid="pld-tmnt-1",
        series_id=int(series.id or 0),
        issue_number="1",
        title="TMNT #1",
        release_status="SCHEDULED",
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    v2_row = RecommendationScoreV2(
        owner_user_id=owner_id,
        recommendation_run_id=1,
        release_issue_id=int(issue.id or 0),
        total_score=82.0,
        recommendation_tier="STRONG_BUY",
        recommendation_type="INVESTMENT_NUMBER_ONE",
        confidence_score=0.88,
    )
    run = RecommendationRunV2(owner_user_id=owner_id, status="COMPLETED")
    session.add(run)
    session.commit()
    session.refresh(run)
    v2_row.recommendation_run_id = int(run.id or 0)
    session.add(v2_row)
    session.commit()
    result = evaluate_pull_list_decision(session, owner_user_id=owner_id, issue=issue, series=series, v2=v2_row)
    assert result.decision_type == DECISION_START_RUN


def test_watch_mid_tier_without_launch_signals(client: TestClient, session: Session) -> None:
    email = "pld-watch@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="INDIE",
        series_name="Obscure ZZZ",
        series_type="LIMITED",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    issue = ReleaseIssue(
        owner_user_id=owner_id,
        release_uuid="pld-obscure-5",
        series_id=int(series.id or 0),
        issue_number="5",
        title="Obscure ZZZ #5",
        release_status="SCHEDULED",
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    run = RecommendationRunV2(owner_user_id=owner_id, status="COMPLETED")
    session.add(run)
    session.commit()
    session.refresh(run)
    v2 = RecommendationScoreV2(
        owner_user_id=owner_id,
        recommendation_run_id=int(run.id or 0),
        release_issue_id=int(issue.id or 0),
        total_score=52.0,
        recommendation_tier="WATCH",
        recommendation_type="FRANCHISE_OPPORTUNITY",
        confidence_score=0.62,
    )
    result = evaluate_pull_list_decision(session, owner_user_id=owner_id, issue=issue, series=series, v2=v2)
    assert result.decision_type == DECISION_WATCH


def test_pass_weak_recommendation(client: TestClient, session: Session) -> None:
    email = "pld-pass@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="INDIE",
        series_name="Weak Series",
        series_type="LIMITED",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    issue = ReleaseIssue(
        owner_user_id=owner_id,
        release_uuid="pld-weak-1",
        series_id=int(series.id or 0),
        issue_number="1",
        title="Weak Series #1",
        release_status="SCHEDULED",
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    run = RecommendationRunV2(owner_user_id=owner_id, status="COMPLETED")
    session.add(run)
    session.commit()
    session.refresh(run)
    v2 = RecommendationScoreV2(
        owner_user_id=owner_id,
        recommendation_run_id=int(run.id or 0),
        release_issue_id=int(issue.id or 0),
        total_score=28.0,
        recommendation_tier="PASS",
        recommendation_type="NEW_OPPORTUNITY",
        confidence_score=0.4,
    )
    result = evaluate_pull_list_decision(session, owner_user_id=owner_id, issue=issue, series=series, v2=v2)
    assert result.decision_type == DECISION_PASS


def test_generate_and_api_owner_scoped(client: TestClient, session: Session) -> None:
    email_a = "pld-api-a@example.com"
    email_b = "pld-api-b@example.com"
    token_a = register_and_login(client, email_a)
    register_and_login(client, email_b)
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
    issue = ReleaseIssue(
        owner_user_id=owner_a,
        release_uuid="pld-api-12",
        series_id=int(series.id or 0),
        issue_number="12",
        title="Batman #12",
        release_status="SCHEDULED",
        release_date=date.today() + timedelta(days=21),
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    _seed_v2_score(
        session,
        owner_user_id=owner_a,
        issue=issue,
        tier="BUY",
        rec_type="USER_PREFERENCE_MATCH",
        total=65.0,
        confidence=0.7,
    )
    pl = create_pull_list(session, owner_user_id=owner_a, payload=PullListCreate(publisher="DC", series_name="Batman"))
    attach_release_to_pull_list(
        session,
        owner_user_id=owner_a,
        pull_list_id=pl.pull_list.id,
        payload=PullListIssueAttachRequest(release_id=int(issue.id or 0)),
    )
    generate_pull_list_decisions(session, owner_user_id=owner_a)
    list_resp = client.get("/api/v1/pull-list-decisions", headers=auth_headers(token_a))
    assert list_resp.status_code == 200
    items = list_resp.json()["data"]["items"]
    assert len(items) >= 1
    decision_id = items[0]["id"]
    detail = client.get(f"/api/v1/pull-list-decisions/{decision_id}", headers=auth_headers(token_a))
    assert detail.status_code == 200
    assert detail.json()["data"]["decision_type"] == "CONTINUE_RUN"

    token_b = register_and_login(client, email_b)
    assert client.get(f"/api/v1/pull-list-decisions/{decision_id}", headers=auth_headers(token_b)).status_code == 404


def test_decision_generation_is_deterministic(client: TestClient, session: Session) -> None:
    email = "pld-deterministic@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="DC",
        series_name="Detective",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    issue = ReleaseIssue(
        owner_user_id=owner_id,
        release_uuid="pld-det-1",
        series_id=int(series.id or 0),
        issue_number="1",
        title="Detective #1",
        release_status="SCHEDULED",
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    _seed_v2_score(
        session,
        owner_user_id=owner_id,
        issue=issue,
        tier="STRONG_BUY",
        rec_type="INVESTMENT_NUMBER_ONE",
        total=80.0,
        confidence=0.9,
    )
    r1 = evaluate_pull_list_decision(
        session,
        owner_user_id=owner_id,
        issue=issue,
        series=series,
        v2=session.exec(select(RecommendationScoreV2).where(RecommendationScoreV2.release_issue_id == issue.id)).one(),
    )
    r2 = evaluate_pull_list_decision(
        session,
        owner_user_id=owner_id,
        issue=issue,
        series=series,
        v2=session.exec(select(RecommendationScoreV2).where(RecommendationScoreV2.release_issue_id == issue.id)).one(),
    )
    assert r1 == r2
