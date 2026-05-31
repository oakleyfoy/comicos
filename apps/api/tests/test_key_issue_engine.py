from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import ReleaseIssue, ReleaseSeries, User
from app.models.key_issue_intelligence import KeyIssueProfile
from app.services.key_issue_engine import detect_key_issues_for_issue, run_key_issue_detection_for_owner
from test_inventory import register_and_login


def test_key_issue_engine_detects_anniversary_and_milestone(client: TestClient) -> None:
    email = "key-issue-engine@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        series = ReleaseSeries(
            owner_user_id=owner_id,
            publisher="IDW",
            series_name="Teenage Mutant Ninja Turtles",
            series_type="ONGOING",
            status="ACTIVE",
        )
        session.add(series)
        session.commit()
        session.refresh(series)
        milestone = ReleaseIssue(
            owner_user_id=owner_id,
            release_uuid="ki-tmnt-300",
            series_id=int(series.id or 0),
            issue_number="300",
            title="TMNT #300",
            release_status="SCHEDULED",
        )
        anniversary = ReleaseIssue(
            owner_user_id=owner_id,
            release_uuid="ki-transformers-ann",
            series_id=int(series.id or 0),
            issue_number="1",
            title="Transformers 40th Anniversary Special",
            release_status="SCHEDULED",
        )
        session.add(milestone)
        session.add(anniversary)
        session.commit()
        session.refresh(milestone)
        session.refresh(anniversary)

        milestone_types = {row.key_issue_type for row in detect_key_issues_for_issue(issue=milestone, series=series)}
        anniversary_types = {row.key_issue_type for row in detect_key_issues_for_issue(issue=anniversary, series=series)}
        assert "MILESTONE_NUMBERING" in milestone_types
        assert "ANNIVERSARY" in anniversary_types

        created = run_key_issue_detection_for_owner(session, owner_user_id=owner_id)
        assert created >= 2
        assert session.exec(select(KeyIssueProfile)).first() is not None
