"""P86 release lifecycle dashboard and run listing."""

from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.p86_release_lifecycle import (
    P86ReleaseLifecycleRun,
    RUN_STATUS_BLOCKED,
    RUN_STATUS_COMPLETE,
    RUN_STATUS_COMPLETE_WITH_WARNINGS,
    RUN_STATUS_FAILED,
    RUN_STATUS_RUNNING,
)
from app.schemas.release_lifecycle import (
    P86ReleaseLifecycleAutomationRead,
    P86ReleaseLifecycleDashboardRead,
    P86ReleaseLifecycleLatestReportRead,
    P86ReleaseLifecyclePlanItemRead,
    P86ReleaseLifecyclePlanRead,
    P86ReleaseLifecycleRunRead,
    P86ReleaseLifecycleRunListRead,
)
from app.services.release_lifecycle_plan import build_weekly_lifecycle_plan, current_release_wednesday
from app.services.release_lifecycle_report_service import (
    get_latest_lifecycle_report,
    has_ever_completed_lifecycle_batch,
)


def _to_read(row: P86ReleaseLifecycleRun) -> P86ReleaseLifecycleRunRead:
    return P86ReleaseLifecycleRunRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_id),
        run_date=row.run_date,
        anchor_release_date=row.anchor_release_date,
        target_release_date=row.target_release_date,
        lifecycle_stage=row.lifecycle_stage,
        command=row.command,
        status=row.status,
        started_at=row.started_at,
        completed_at=row.completed_at,
        elapsed_seconds=row.elapsed_seconds,
        parent_queue_count=row.parent_queue_count,
        parent_captured_count=row.parent_captured_count,
        issue_count=row.issue_count,
        variant_count=row.variant_count,
        warnings=list(row.warnings_json or []),
        failures=list(row.failures_json or []),
        raw_path=row.raw_path,
        crosswalk_skipped=bool(row.crosswalk_skipped),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def build_lifecycle_plan_read(*, today: date | None = None) -> P86ReleaseLifecyclePlanRead:
    plan = build_weekly_lifecycle_plan(anchor=current_release_wednesday(today=today), run_date=today or date.today())
    return P86ReleaseLifecyclePlanRead(
        anchor_release_date=plan.anchor_release_date,
        run_date=plan.run_date,
        items=[
            P86ReleaseLifecyclePlanItemRead(
                target_release_date=item.target_release_date,
                lifecycle_stage=item.lifecycle_stage,
            )
            for item in plan.items
        ],
    )


def list_lifecycle_runs(
    session: Session,
    *,
    owner_id: int,
    limit: int = 50,
    offset: int = 0,
) -> P86ReleaseLifecycleRunListRead:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(P86ReleaseLifecycleRun)
        .where(P86ReleaseLifecycleRun.owner_id == owner_id)
        .order_by(P86ReleaseLifecycleRun.started_at.desc(), P86ReleaseLifecycleRun.id.desc())
    ).all()
    page = rows[offset : offset + limit]
    return P86ReleaseLifecycleRunListRead(
        items=[_to_read(r) for r in page],
        total_items=len(rows),
        limit=limit,
        offset=offset,
    )


def _status_for_plan_item(
    session: Session,
    *,
    owner_id: int,
    anchor: date,
    target_release_date: date,
    lifecycle_stage: str,
) -> P86ReleaseLifecycleRun | None:
    return session.exec(
        select(P86ReleaseLifecycleRun)
        .where(P86ReleaseLifecycleRun.owner_id == owner_id)
        .where(P86ReleaseLifecycleRun.anchor_release_date == anchor)
        .where(P86ReleaseLifecycleRun.target_release_date == target_release_date)
        .where(P86ReleaseLifecycleRun.lifecycle_stage == lifecycle_stage)
        .order_by(P86ReleaseLifecycleRun.started_at.desc(), P86ReleaseLifecycleRun.id.desc())
    ).first()


def build_lifecycle_dashboard(session: Session, *, owner_id: int) -> P86ReleaseLifecycleDashboardRead:
    plan = build_lifecycle_plan_read()
    anchor = plan.anchor_release_date
    this_week: list[P86ReleaseLifecyclePlanItemRead] = []
    for item in plan.items:
        latest = _status_for_plan_item(
            session,
            owner_id=owner_id,
            anchor=anchor,
            target_release_date=item.target_release_date,
            lifecycle_stage=item.lifecycle_stage,
        )
        this_week.append(
            P86ReleaseLifecyclePlanItemRead(
                target_release_date=item.target_release_date,
                lifecycle_stage=item.lifecycle_stage,
                status=latest.status if latest else "NOT_STARTED",
                issue_count=latest.issue_count if latest else None,
                variant_count=latest.variant_count if latest else None,
                elapsed_seconds=latest.elapsed_seconds if latest else None,
                warnings=list(latest.warnings_json or []) if latest else [],
                failures=list(latest.failures_json or []) if latest else [],
                run_id=int(latest.id or 0) if latest else None,
            )
        )

    recent = list_lifecycle_runs(session, owner_id=owner_id, limit=20, offset=0).items
    failed_blocked = [
        r
        for r in recent
        if r.status in {RUN_STATUS_BLOCKED, RUN_STATUS_FAILED}
    ]

    upcoming_anchor = anchor + timedelta(days=7)
    upcoming_plan = build_weekly_lifecycle_plan(anchor=upcoming_anchor)
    upcoming = [
        P86ReleaseLifecyclePlanItemRead(
            target_release_date=item.target_release_date,
            lifecycle_stage=item.lifecycle_stage,
        )
        for item in upcoming_plan.items
    ]

    latest_success = session.exec(
        select(P86ReleaseLifecycleRun)
        .where(P86ReleaseLifecycleRun.owner_id == owner_id)
        .where(P86ReleaseLifecycleRun.status.in_([RUN_STATUS_COMPLETE, RUN_STATUS_COMPLETE_WITH_WARNINGS]))
        .order_by(P86ReleaseLifecycleRun.completed_at.desc(), P86ReleaseLifecycleRun.id.desc())
        .limit(8)
    ).all()

    running_count = session.exec(
        select(P86ReleaseLifecycleRun)
        .where(P86ReleaseLifecycleRun.owner_id == owner_id)
        .where(P86ReleaseLifecycleRun.status == RUN_STATUS_RUNNING)
    ).all()

    latest_report = get_latest_lifecycle_report(session, owner_id=owner_id)
    has_run = has_ever_completed_lifecycle_batch(session, owner_id=owner_id)
    cron_hint = (
        "No weekly lifecycle run has completed yet. Configure Render Cron "
        "(see docs/render/P86_RENDER_CRON_BLUEPRINT.yaml) or run manually."
        if not has_run
        else "Weekly runs are recorded when Render Cron or POST /run-weekly completes."
    )
    automation = P86ReleaseLifecycleAutomationRead(
        has_completed_weekly_run=has_run,
        cron_setup_hint=cron_hint,
        last_report_at=latest_report.created_at,
        last_report_status=None if latest_report.status == "EMPTY" else latest_report.status,
    )

    return P86ReleaseLifecycleDashboardRead(
        anchor_release_date=anchor,
        run_date=plan.run_date,
        this_week_plan=this_week,
        recent_runs=recent,
        failed_or_blocked=failed_blocked,
        upcoming_lifecycle_dates=upcoming,
        latest_successful=[_to_read(r) for r in latest_success],
        active_running_count=len(running_count),
        latest_report=latest_report,
        automation=automation,
    )
