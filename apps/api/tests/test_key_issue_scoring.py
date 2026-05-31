from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import ReleaseIssue, ReleaseSeries, User
from app.models.key_issue_intelligence import KeyIssueProfile
from app.services.key_issue_engine import run_key_issue_detection_for_owner
from app.services.key_issue_scoring import apply_key_issue_scoring_for_owner, score_key_issue_profile
from test_inventory import register_and_login


def test_key_issue_scoring_produces_overall_score(client: TestClient) -> None:
    email = "key-issue-scoring@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        series = ReleaseSeries(
            owner_user_id=owner_id,
            publisher="Marvel",
            series_name="Amazing Fantasy",
            series_type="LIMITED",
            status="ACTIVE",
        )
        session.add(series)
        session.commit()
        session.refresh(series)
        issue = ReleaseIssue(
            owner_user_id=owner_id,
            release_uuid="ki-af-15",
            series_id=int(series.id or 0),
            issue_number="15",
            title="Amazing Fantasy #15 First Appearance",
            release_status="SCHEDULED",
        )
        session.add(issue)
        session.commit()
        session.refresh(issue)
        run_key_issue_detection_for_owner(session, owner_user_id=owner_id)
        profile = session.exec(select(KeyIssueProfile).where(KeyIssueProfile.release_issue_id == issue.id)).one()
        breakdown = score_key_issue_profile(session, profile=profile, issue=issue, series=series)
        assert breakdown.overall_key_issue_score > 0
        updated = apply_key_issue_scoring_for_owner(session, owner_user_id=owner_id)
        assert updated >= 1
