from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import ReleaseIssue, ReleaseSeries, User
from app.services.recommendation_v2_components import compute_run_start_value_score
from test_inventory import register_and_login


def test_run_start_value_for_supported_number_one(client: TestClient, session: Session) -> None:
    email = "run-start@example.com"
    register_and_login(client, email)
    owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
    series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="Image",
        series_name="Invincible",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    issue = ReleaseIssue(
        owner_user_id=owner_id,
        release_uuid="run-start-1",
        series_id=int(series.id or 0),
        issue_number="1",
        title="Invincible #1",
        release_status="SCHEDULED",
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    score, explain = compute_run_start_value_score(session, owner_user_id=owner_id, issue=issue, series=series)
    assert score >= 55.0
    assert "run" in explain.lower() or "Run" in explain
