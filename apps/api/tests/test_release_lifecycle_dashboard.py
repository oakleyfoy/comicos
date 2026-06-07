from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.p86_release_lifecycle import P86ReleaseLifecycleRun, RUN_STATUS_FAILED
from app.services.release_lifecycle_service import build_lifecycle_dashboard
from app.services.release_lifecycle_plan import build_weekly_lifecycle_plan
from test_inventory import auth_headers, register_and_login


def test_dashboard_payload(client: TestClient, session: Session) -> None:
    email = "p86-dash@example.com"
    token = register_and_login(client, email)
    owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
    session.add(
        P86ReleaseLifecycleRun(
            owner_id=owner_id,
            run_date=date(2026, 6, 10),
            anchor_release_date=date(2026, 6, 10),
            target_release_date=date(2026, 6, 10),
            lifecycle_stage="RELEASE_DAY_REFRESH",
            command="capture",
            status="COMPLETE",
            issue_count=50,
            variant_count=120,
            elapsed_seconds=90.0,
            completed_at=datetime.now(timezone.utc),
        )
    )
    session.commit()

    dash = build_lifecycle_dashboard(session, owner_id=owner_id)
    assert dash.anchor_release_date is not None
    assert len(dash.this_week_plan) == 4
    assert dash.latest_successful
    assert dash.latest_successful[0].issue_count == 50

    resp = client.get("/api/v1/release-lifecycle/dashboard", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["this_week_plan"]) == 4
    assert data["latest_successful"]
    assert "automation" in data
    assert "latest_report" in data


def test_latest_report_endpoint_empty(client: TestClient) -> None:
    token = register_and_login(client, "p86-latest-empty@example.com")
    resp = client.get("/api/v1/release-lifecycle/latest-report", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "EMPTY"


def test_dashboard_includes_latest_report(client: TestClient, session: Session) -> None:
    email = "p86-dash-report@example.com"
    token = register_and_login(client, email)
    owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
    plan = build_weekly_lifecycle_plan(anchor=date(2026, 6, 10), run_date=date(2026, 6, 10))
    from app.services.release_lifecycle_report_service import finalize_weekly_lifecycle_report

    run = P86ReleaseLifecycleRun(
        owner_id=owner_id,
        run_date=plan.run_date,
        anchor_release_date=plan.anchor_release_date,
        target_release_date=date(2026, 6, 10),
        lifecycle_stage="RELEASE_DAY_REFRESH",
        command="x",
        status="COMPLETE",
        crosswalk_skipped=True,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    finalize_weekly_lifecycle_report(session, owner_id=owner_id, plan=plan, runs=[run])
    resp = client.get("/api/v1/release-lifecycle/dashboard", headers=auth_headers(token))
    data = resp.json()["data"]
    assert data["latest_report"]["status"] != "EMPTY"
    assert data["automation"]["has_completed_weekly_run"] is True


def test_plan_endpoint(client: TestClient) -> None:
    token = register_and_login(client, "p86-plan@example.com")
    resp = client.get("/api/v1/release-lifecycle/plan", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["items"]) == 4


def test_runs_list(client: TestClient, session: Session) -> None:
    email = "p86-runs@example.com"
    token = register_and_login(client, email)
    owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
    session.add(
        P86ReleaseLifecycleRun(
            owner_id=owner_id,
            run_date=date(2026, 6, 10),
            anchor_release_date=date(2026, 6, 10),
            target_release_date=date(2026, 4, 15),
            lifecycle_stage="POST_RELEASE_CLEANUP",
            command="x",
            status=RUN_STATUS_FAILED,
            failures_json=["timeout"],
        )
    )
    session.commit()
    resp = client.get("/api/v1/release-lifecycle/runs", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["data"]["pagination"]["total_count"] >= 1
