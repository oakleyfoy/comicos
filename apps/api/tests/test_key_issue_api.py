from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import ReleaseIssue, ReleaseSeries, User
from release_platform_test_helpers import seed_release_platform_horizons
from test_inventory import auth_headers, register_and_login


def test_key_issue_api_refresh_and_dashboard(client: TestClient) -> None:
    email = "key-issue-api@example.com"
    token = register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        seed_release_platform_horizons(session, owner_user_id=owner_id)
        tmnt = ReleaseSeries(
            owner_user_id=owner_id,
            publisher="IDW",
            series_name="TMNT",
            series_type="ONGOING",
            status="ACTIVE",
        )
        session.add(tmnt)
        session.commit()
        session.refresh(tmnt)
        session.add(
            ReleaseIssue(
                owner_user_id=owner_id,
                release_uuid="ki-api-tmnt-300",
                series_id=int(tmnt.id or 0),
                issue_number="300",
                title="TMNT #300",
                release_status="SCHEDULED",
            )
        )
        session.commit()

    refresh = client.post("/api/v1/key-issues/refresh", headers=auth_headers(token))
    dashboard = client.get("/api/v1/key-issues/dashboard", headers=auth_headers(token))
    milestones = client.get("/api/v1/key-issues/milestones", headers=auth_headers(token))
    first_apps = client.get("/api/v1/key-issues/first-appearances", headers=auth_headers(token))

    assert refresh.status_code == 200, refresh.text
    assert dashboard.status_code == 200, dashboard.text
    assert milestones.status_code == 200
    assert first_apps.status_code == 200
    assert refresh.json()["data"]["scores_updated"] >= 0
    assert dashboard.json()["data"]["total_profiles"] >= 1
