"""P61 Demand Intelligence certification runner (local/CI)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select, func

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, os.path.join(REPO_ROOT, "apps", "api"))

from app.db.session import get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.models.demand_intelligence import (  # noqa: E402
    DemandRefreshRun,
    DemandVelocitySnapshot,
    IssueDemandObservation,
    IssueDemandSnapshot,
    SpecOpportunitySnapshot,
    WeeklyDemandCaptureEvent,
    WeeklyDemandCaptureSchedule,
)
from app.models.external_catalog import ExternalCatalogIssue  # noqa: E402
from app.models.release_intelligence import ReleaseIssue  # noqa: E402
from app.services.demand_intelligence_certification import (  # noqa: E402
    certify_automation,
    certify_refresh,
    certify_spec,
    certify_velocity,
    get_demand_platform_certification,
)
from app.services.demand_refresh_service import run_demand_refresh  # noqa: E402
from app.services.demand_velocity_service import compute_demand_velocity  # noqa: E402
from app.services.external_catalog.league_of_comic_geeks import LOCG_SOURCE_NAME  # noqa: E402
from app.services.spec_opportunity_service import build_spec_opportunities  # noqa: E402
from app.services.weekly_demand_automation_service import (  # noqa: E402
    discover_capture_schedule,
    run_post_capture_pipeline,
)


def _pick_owner_id(session: Session, email: str | None) -> int:
    if email:
        user = session.exec(select(User).where(User.email == email)).first()
        if user and user.id is not None:
            return int(user.id)
        raise SystemExit(f"Owner not found: {email}")
    row = session.exec(
        select(ReleaseIssue.owner_user_id, func.count())
        .where(ReleaseIssue.owner_user_id.isnot(None))
        .group_by(ReleaseIssue.owner_user_id)
        .order_by(func.count().desc())
    ).first()
    if row and row[0] is not None:
        return int(row[0])
    user = session.exec(select(User).order_by(User.id.asc())).first()
    if user and user.id is not None:
        return int(user.id)
    raise SystemExit("No users in database")


def _ensure_locg_upcoming(session: Session) -> int:
    """Ensure at least one LoCG issue in the upcoming window for refresh."""
    existing = session.exec(
        select(ExternalCatalogIssue)
        .where(ExternalCatalogIssue.source_name == LOCG_SOURCE_NAME)
        .where(ExternalCatalogIssue.release_date >= date.today())
    ).first()
    if existing:
        return 1
    issue = ExternalCatalogIssue(
        source_name=LOCG_SOURCE_NAME,
        title="P61 Cert Series #1",
        publisher="Cert Pub",
        series_name="P61 Cert Series",
        issue_number="1",
        release_date=date.today() + timedelta(days=14),
        pull_count=150,
        want_count=90,
        normalized_title_key="p61 cert series #1",
    )
    session.add(issue)
    session.commit()
    return 1


def _login(client: TestClient, email: str, password: str) -> str:
    client.post("/auth/register", json={"email": email, "password": password})
    r = client.post("/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def main() -> int:
    parser = argparse.ArgumentParser(description="P61 demand intelligence certification")
    parser.add_argument("--owner-email", default=None, help="Owner for spec build (default: richest catalog)")
    parser.add_argument("--json-out", default=None, help="Write machine-readable report path")
    args = parser.parse_args()

    report: dict = {"steps": {}, "counts": {}, "certification": {}, "api": {}}

    with Session(get_engine()) as session:
        owner_id = _pick_owner_id(session, args.owner_email)
        owner = session.get(User, owner_id)
        report["owner_user_id"] = owner_id
        owner_email_str = owner.email if owner else None
        report["owner_email"] = owner_email_str

        seeded = _ensure_locg_upcoming(session)
        report["steps"]["locg_seed"] = {"ensured_upcoming_issues": seeded}

        refresh_run = run_demand_refresh(
            session,
            scope="ALL",
            days_forward=90,
            owner_user_id=owner_id,
            trigger_type="CERTIFICATION",
            refresh_locg=False,
        )
        report["steps"]["demand_refresh"] = {
            "run_id": refresh_run.id,
            "status": refresh_run.status,
            "issues_refreshed": refresh_run.issues_refreshed,
            "profiles_updated": refresh_run.profiles_updated,
        }

        velocity_updated = 0
        windows: dict[str, int] = {}
        for window in (7, 14, 28):
            n = compute_demand_velocity(session, window_days=window)
            windows[str(window)] = n
            velocity_updated += n
        report["steps"]["velocity_compute"] = {"rows_updated": velocity_updated, "by_window": windows}

        spec_snap = build_spec_opportunities(session, owner_user_id=owner_id, limit=50)
        report["steps"]["spec_build"] = {
            "snapshot_id": spec_snap.id,
            "row_count": spec_snap.row_count,
        }

        schedules = discover_capture_schedule(session, owner_user_id=owner_id)
        target = schedules[0] if schedules else None
        if target is None:
            raise SystemExit("No capture schedule row")
        pipeline_schedule = run_post_capture_pipeline(
            session,
            schedule=target,
            owner_user_id=owner_id,
        )
        report["steps"]["weekly_automation"] = {
            "schedule_id": pipeline_schedule.id,
            "release_date": pipeline_schedule.release_date.isoformat(),
            "status": pipeline_schedule.status,
        }

        report["counts"] = {
            "issue_demand_snapshot": session.exec(select(func.count()).select_from(IssueDemandSnapshot)).one(),
            "issue_demand_observation": session.exec(select(func.count()).select_from(IssueDemandObservation)).one(),
            "demand_velocity_snapshot": session.exec(select(func.count()).select_from(DemandVelocitySnapshot)).one(),
            "velocity_by_window": {
                str(w): session.exec(
                    select(func.count())
                    .select_from(DemandVelocitySnapshot)
                    .where(DemandVelocitySnapshot.window_days == w)
                ).one()
                for w in (7, 14, 28)
            },
            "spec_opportunity_snapshot": session.exec(select(func.count()).select_from(SpecOpportunitySnapshot)).one(),
            "weekly_capture_schedule": session.exec(select(func.count()).select_from(WeeklyDemandCaptureSchedule)).one(),
            "weekly_capture_event": session.exec(select(func.count()).select_from(WeeklyDemandCaptureEvent)).one(),
            "demand_refresh_run": session.exec(select(func.count()).select_from(DemandRefreshRun)).one(),
        }

        report["certification"] = {
            "refresh": certify_refresh(session).model_dump(mode="json"),
            "velocity": certify_velocity(session).model_dump(mode="json"),
            "spec": certify_spec(session, owner_user_id=owner_id).model_dump(mode="json"),
            "automation": certify_automation(session).model_dump(mode="json"),
            "platform": get_demand_platform_certification(session, owner_user_id=owner_id).model_dump(mode="json"),
        }

    cert_email = owner_email_str or f"p61-cert-runner-{owner_id}@example.com"
    password = "supersecret123"
    with TestClient(app) as client:
        # Register only when using synthetic cert email; production owners already exist.
        if cert_email.startswith("p61-cert-runner-"):
            client.post("/auth/register", json={"email": cert_email, "password": password})
        login = client.post("/auth/login", json={"email": cert_email, "password": password})
        if login.status_code != 200:
            token = _login(client, f"p61-cert-runner-{owner_id}@example.com", password)
        else:
            token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        endpoints = [
            ("GET", "/api/v1/demand/certification"),
            ("GET", "/api/v1/velocity/certification"),
            ("GET", "/api/v1/spec/certification"),
            ("GET", "/api/v1/automation/certification"),
            ("GET", "/api/v1/demand/platform/certification"),
        ]
        for method, path in endpoints:
            resp = client.request(method, path, headers=headers)
            body = resp.json() if resp.status_code == 200 else {"error": resp.text}
            certified = None
            if resp.status_code == 200 and isinstance(body.get("data"), dict):
                certified = body["data"].get("certified")
                if certified is None and "platform_ready" in body["data"]:
                    certified = body["data"].get("platform_ready")
            report["api"][path] = {
                "status_code": resp.status_code,
                "certified_flag": certified,
            }

    report["pass"] = all(
        [
            report["certification"]["refresh"].get("certified"),
            report["certification"]["velocity"].get("certified"),
            report["certification"]["spec"].get("certified"),
            report["certification"]["automation"].get("certified"),
            all(v.get("status_code") == 200 for v in report["api"].values()),
        ]
    )

    text = json.dumps(report, indent=2, default=str)
    print(text)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            f.write(text)

    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
