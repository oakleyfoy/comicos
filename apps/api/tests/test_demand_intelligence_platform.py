from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.demand_intelligence import IssueDemandSnapshot
from app.models.external_catalog import ExternalCatalogIssue
from app.services.demand_refresh_service import run_demand_refresh
from app.services.demand_velocity_service import compute_demand_velocity
from app.services.external_catalog.league_of_comic_geeks import LOCG_SOURCE_NAME
def register_and_login(client: TestClient, email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    response = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    return response.json()["access_token"]


def _seed_locg_issue(session: Session) -> ExternalCatalogIssue:
    issue = ExternalCatalogIssue(
        source_name=LOCG_SOURCE_NAME,
        title="Test Series #1",
        publisher="Test Pub",
        series_name="Test Series",
        issue_number="1",
        release_date=date.today() + timedelta(days=14),
        pull_count=120,
        want_count=80,
        normalized_title_key="test series #1",
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    return issue


def test_demand_refresh_creates_snapshot(client: TestClient, session: Session) -> None:
    email = "p61-demand@example.com"
    register_and_login(client, email)
    _seed_locg_issue(session)
    run = run_demand_refresh(session, scope="ISSUE_UPCOMING", days_forward=90, refresh_locg=False)
    assert run.status == "SUCCESS"
    assert run.issues_refreshed >= 1
    snap = session.exec(select(IssueDemandSnapshot)).first()
    assert snap is not None
    assert snap.combined_demand_score > 0


def test_demand_api_refresh_and_list(client: TestClient, session: Session) -> None:
    email = "p61-demand-api@example.com"
    token = register_and_login(client, email)
    _seed_locg_issue(session)
    headers = {"Authorization": f"Bearer {token}"}
    post = client.post("/api/v1/demand/refresh", json={"scope": "ISSUE_UPCOMING", "days_forward": 90}, headers=headers)
    assert post.status_code == 200
    listed = client.get("/api/v1/demand/issues", headers=headers)
    assert listed.status_code == 200


def test_velocity_compute_after_refresh(client: TestClient, session: Session) -> None:
    email = "p61-velocity@example.com"
    token = register_and_login(client, email)
    _seed_locg_issue(session)
    run_demand_refresh(session, scope="ISSUE_UPCOMING", days_forward=90, refresh_locg=False)
    updated = compute_demand_velocity(session, window_days=7)
    assert updated >= 1
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post("/api/v1/velocity/compute", json={"window_days": [7]}, headers=headers)
    assert resp.status_code == 200


def test_platform_certification_endpoint(client: TestClient, session: Session) -> None:
    email = "p61-cert@example.com"
    token = register_and_login(client, email)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/v1/demand/platform/certification", headers=headers)
    assert resp.status_code == 200
