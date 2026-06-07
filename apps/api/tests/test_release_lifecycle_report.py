from __future__ import annotations

from datetime import date

from sqlmodel import Session

from app.models.p86_release_lifecycle import P86ReleaseLifecycleRun, RUN_STATUS_BLOCKED, RUN_STATUS_COMPLETE
from app.services.release_lifecycle_plan import build_weekly_lifecycle_plan
from app.services.release_lifecycle_report_service import (
    build_weekly_report_title,
    compute_overall_status,
    finalize_weekly_lifecycle_report,
    get_latest_lifecycle_report,
)


def test_compute_overall_status_complete_with_warnings() -> None:
    runs = [
        P86ReleaseLifecycleRun(
            owner_id=1,
            run_date=date(2026, 6, 10),
            anchor_release_date=date(2026, 6, 10),
            target_release_date=date(2026, 6, 10),
            lifecycle_stage="RELEASE_DAY_REFRESH",
            command="x",
            status="COMPLETE_WITH_WARNINGS",
            crosswalk_skipped=True,
        )
    ]
    assert compute_overall_status(runs) == "COMPLETE_WITH_WARNINGS"
    assert "COMPLETE_WITH_WARNINGS" in build_weekly_report_title("COMPLETE_WITH_WARNINGS")


def test_finalize_persists_report(client, session: Session) -> None:
    from app.models import User

    user = User(email="p86-finalize@example.com", password_hash="x", is_active=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    owner_id = int(user.id or 0)
    plan = build_weekly_lifecycle_plan(anchor=date(2026, 6, 10), run_date=date(2026, 6, 10))
    runs = [
        P86ReleaseLifecycleRun(
            owner_id=owner_id,
            run_date=plan.run_date,
            anchor_release_date=plan.anchor_release_date,
            target_release_date=date(2026, 4, 15),
            lifecycle_stage="POST_RELEASE_CLEANUP",
            command="x",
            status=RUN_STATUS_COMPLETE,
            issue_count=1,
            variant_count=2,
            crosswalk_skipped=True,
        ),
        P86ReleaseLifecycleRun(
            owner_id=owner_id,
            run_date=plan.run_date,
            anchor_release_date=plan.anchor_release_date,
            target_release_date=date(2026, 9, 2),
            lifecycle_stage="EARLY_DISCOVERY",
            command="x",
            status=RUN_STATUS_BLOCKED,
            crosswalk_skipped=True,
        ),
    ]
    for r in runs:
        session.add(r)
    session.commit()
    for r in runs:
        session.refresh(r)
    report = finalize_weekly_lifecycle_report(session, owner_id=owner_id, plan=plan, runs=runs)
    assert report is not None
    latest = get_latest_lifecycle_report(session, owner_id=owner_id)
    assert latest.status == "NEEDS_ATTENTION"
    assert latest.title
    assert "POST_RELEASE_CLEANUP" in latest.body
