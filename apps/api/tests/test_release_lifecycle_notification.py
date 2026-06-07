from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.p82_p84_collector_expansion import CollectorNotification
from app.models.p86_release_lifecycle import P86ReleaseLifecycleRun, RUN_STATUS_BLOCKED, RUN_STATUS_COMPLETE
from app.services.release_lifecycle_plan import build_weekly_lifecycle_plan
from app.services.release_lifecycle_report_service import finalize_weekly_lifecycle_report
from test_inventory import auth_headers, register_and_login


def test_notification_created_on_finalize(client: TestClient, session: Session) -> None:
    email = "p86-notif@example.com"
    register_and_login(client, email)
    owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
    plan = build_weekly_lifecycle_plan(anchor=date(2026, 6, 10), run_date=date(2026, 6, 10))
    run = P86ReleaseLifecycleRun(
        owner_id=owner_id,
        run_date=plan.run_date,
        anchor_release_date=plan.anchor_release_date,
        target_release_date=date(2026, 6, 10),
        lifecycle_stage="RELEASE_DAY_REFRESH",
        command="x",
        status=RUN_STATUS_BLOCKED,
        crosswalk_skipped=True,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    finalize_weekly_lifecycle_report(session, owner_id=owner_id, plan=plan, runs=[run])
    row = session.exec(
        select(CollectorNotification).where(
            CollectorNotification.owner_user_id == owner_id,
            CollectorNotification.notification_type == "RELEASE_LIFECYCLE_REPORT",
        )
    ).first()
    assert row is not None
    assert row.priority == "HIGH"
    assert row.action_url == "/release-lifecycle"


def test_normal_priority_when_all_complete(client: TestClient, session: Session) -> None:
    email = "p86-notif-ok@example.com"
    register_and_login(client, email)
    owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
    plan = build_weekly_lifecycle_plan(anchor=date(2026, 6, 10), run_date=date(2026, 6, 12))
    run = P86ReleaseLifecycleRun(
        owner_id=owner_id,
        run_date=plan.run_date,
        anchor_release_date=plan.anchor_release_date,
        target_release_date=date(2026, 6, 10),
        lifecycle_stage="RELEASE_DAY_REFRESH",
        command="x",
        status=RUN_STATUS_COMPLETE,
        crosswalk_skipped=True,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    finalize_weekly_lifecycle_report(session, owner_id=owner_id, plan=plan, runs=[run])
    row = session.exec(
        select(CollectorNotification).where(
            CollectorNotification.owner_user_id == owner_id,
            CollectorNotification.notification_type == "RELEASE_LIFECYCLE_REPORT",
        )
    ).first()
    assert row is not None
    assert row.priority == "NORMAL"
