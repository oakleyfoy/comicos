"""P86 weekly lifecycle report, notification, and briefing hooks."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models.p82_p84_collector_expansion import CollectorBriefing, CollectorNotification, utc_now
from app.models.p86_release_lifecycle import (
    P86ReleaseLifecycleReport,
    P86ReleaseLifecycleRun,
    REPORT_STATUS_COMPLETE,
    REPORT_STATUS_COMPLETE_WITH_WARNINGS,
    REPORT_STATUS_FAILED,
    REPORT_STATUS_NEEDS_ATTENTION,
    RUN_STATUS_BLOCKED,
    RUN_STATUS_COMPLETE,
    RUN_STATUS_COMPLETE_WITH_WARNINGS,
    RUN_STATUS_FAILED,
)
from app.schemas.release_lifecycle import P86ReleaseLifecycleLatestReportRead, P86ReleaseLifecycleRunRead
from app.services.release_lifecycle_plan import WeeklyLifecyclePlan

NOTIFICATION_TYPE = "RELEASE_LIFECYCLE_REPORT"
ACTION_URL = "/release-lifecycle"


def _run_to_json(run: P86ReleaseLifecycleRun) -> dict:
    return P86ReleaseLifecycleRunRead(
        id=int(run.id or 0),
        owner_id=int(run.owner_id),
        run_date=run.run_date,
        anchor_release_date=run.anchor_release_date,
        target_release_date=run.target_release_date,
        lifecycle_stage=run.lifecycle_stage,
        command=run.command,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        elapsed_seconds=run.elapsed_seconds,
        parent_queue_count=run.parent_queue_count,
        parent_captured_count=run.parent_captured_count,
        issue_count=run.issue_count,
        variant_count=run.variant_count,
        warnings=list(run.warnings_json or []),
        failures=list(run.failures_json or []),
        raw_path=run.raw_path,
        crosswalk_skipped=bool(run.crosswalk_skipped),
        created_at=run.created_at,
        updated_at=run.updated_at,
    ).model_dump(mode="json")


def compute_overall_status(runs: list[P86ReleaseLifecycleRun]) -> str:
    if not runs:
        return REPORT_STATUS_FAILED
    statuses = {r.status for r in runs}
    if RUN_STATUS_FAILED in statuses:
        return REPORT_STATUS_NEEDS_ATTENTION
    if RUN_STATUS_BLOCKED in statuses:
        return REPORT_STATUS_NEEDS_ATTENTION
    if RUN_STATUS_COMPLETE_WITH_WARNINGS in statuses:
        return REPORT_STATUS_COMPLETE_WITH_WARNINGS
    if all(s == RUN_STATUS_COMPLETE for s in statuses):
        return REPORT_STATUS_COMPLETE
    return REPORT_STATUS_NEEDS_ATTENTION


def _format_run_line(run: P86ReleaseLifecycleRun) -> str:
    issues = run.issue_count if run.issue_count is not None else "—"
    variants = run.variant_count if run.variant_count is not None else "—"
    extra = ""
    if run.failures_json:
        extra = f" — {run.failures_json[0][:120]}"
    elif run.warnings_json:
        extra = f" — warning: {run.warnings_json[0][:80]}"
    return (
        f"{run.lifecycle_stage}\n"
        f"{run.target_release_date.isoformat()} — {run.status} — {issues} issues / {variants} variants{extra}"
    )


def build_weekly_report_body(*, runs: list[P86ReleaseLifecycleRun]) -> str:
    lines = ["Release Lifecycle Weekly Summary", ""]
    for run in runs:
        lines.append(_format_run_line(run))
        lines.append("")
    lines.append("Crosswalk: skipped")
    return "\n".join(lines).strip()


def build_weekly_report_title(overall_status: str) -> str:
    if overall_status in {REPORT_STATUS_NEEDS_ATTENTION, REPORT_STATUS_FAILED}:
        return "Weekly Release Lifecycle Run — NEEDS ATTENTION"
    if overall_status == REPORT_STATUS_COMPLETE_WITH_WARNINGS:
        return "Weekly Release Lifecycle Run — COMPLETE_WITH_WARNINGS"
    return "Weekly Release Lifecycle Run — COMPLETE"


def notification_title(overall_status: str) -> str:
    if overall_status in {REPORT_STATUS_NEEDS_ATTENTION, REPORT_STATUS_FAILED}:
        return "Release Lifecycle Weekly Run Needs Attention"
    return "Release Lifecycle Weekly Run Complete"


def notification_priority(runs: list[P86ReleaseLifecycleRun]) -> str:
    if any(r.status in {RUN_STATUS_FAILED, RUN_STATUS_BLOCKED} for r in runs):
        return "HIGH"
    return "NORMAL"


def persist_weekly_lifecycle_report(
    session: Session,
    *,
    owner_id: int,
    plan: WeeklyLifecyclePlan,
    runs: list[P86ReleaseLifecycleRun],
) -> P86ReleaseLifecycleReport:
    overall = compute_overall_status(runs)
    body = build_weekly_report_body(runs=runs)
    title = build_weekly_report_title(overall)
    run_reads = [_run_to_json(r) for r in runs]
    row = P86ReleaseLifecycleReport(
        owner_id=owner_id,
        anchor_release_date=plan.anchor_release_date,
        run_date=plan.run_date,
        overall_status=overall,
        title=title,
        body=body,
        runs_json=run_reads,
        action_url=ACTION_URL,
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def create_lifecycle_report_notification(
    session: Session,
    *,
    owner_id: int,
    report: P86ReleaseLifecycleReport,
    runs: list[P86ReleaseLifecycleRun],
) -> None:
    session.add(
        CollectorNotification(
            owner_user_id=owner_id,
            notification_type=NOTIFICATION_TYPE,
            priority=notification_priority(runs),
            title=notification_title(report.overall_status),
            message=report.body[:4000],
            related_entity_type="release_lifecycle_report",
            related_entity_id=int(report.id or 0),
            action_url=ACTION_URL,
            status="UNREAD",
            reasons_json=[report.title],
            created_at=utc_now(),
        )
    )


def _merge_briefing_section(
    session: Session,
    *,
    owner_id: int,
    briefing_type: str,
    briefing_date: date,
    report: P86ReleaseLifecycleReport,
) -> None:
    row = session.exec(
        select(CollectorBriefing)
        .where(
            CollectorBriefing.owner_user_id == owner_id,
            CollectorBriefing.briefing_type == briefing_type,
            CollectorBriefing.briefing_date == briefing_date,
        )
        .order_by(CollectorBriefing.id.desc())
        .limit(1)
    ).first()
    snippet = report.body.splitlines()[0:8]
    section = {
        "title": report.title,
        "overall_status": report.overall_status,
        "summary_lines": snippet,
        "action_url": ACTION_URL,
    }
    if row is None:
        session.add(
            CollectorBriefing(
                owner_user_id=owner_id,
                briefing_type=briefing_type,
                briefing_date=briefing_date,
                sections_json={"release_lifecycle": section},
                top_actions_json=["Review release lifecycle weekly report"],
                created_at=utc_now(),
            )
        )
        return
    sections = dict(row.sections_json or {})
    sections["release_lifecycle"] = section
    row.sections_json = sections
    actions = list(row.top_actions_json or [])
    if "Review release lifecycle weekly report" not in actions:
        actions.insert(0, "Review release lifecycle weekly report")
    row.top_actions_json = actions[:8]
    session.add(row)


def append_report_to_briefings(session: Session, *, owner_id: int, report: P86ReleaseLifecycleReport) -> None:
    day = report.run_date
    _merge_briefing_section(session, owner_id=owner_id, briefing_type="DAILY", briefing_date=day, report=report)
    _merge_briefing_section(session, owner_id=owner_id, briefing_type="WEEKLY", briefing_date=day, report=report)


def finalize_weekly_lifecycle_report(
    session: Session,
    *,
    owner_id: int,
    plan: WeeklyLifecyclePlan,
    runs: list[P86ReleaseLifecycleRun],
) -> P86ReleaseLifecycleReport | None:
    if not runs:
        return None
    report = persist_weekly_lifecycle_report(session, owner_id=owner_id, plan=plan, runs=runs)
    create_lifecycle_report_notification(session, owner_id=owner_id, report=report, runs=runs)
    append_report_to_briefings(session, owner_id=owner_id, report=report)
    session.commit()
    session.refresh(report)
    return report


def get_latest_lifecycle_report(session: Session, *, owner_id: int) -> P86ReleaseLifecycleLatestReportRead:
    row = session.exec(
        select(P86ReleaseLifecycleReport)
        .where(P86ReleaseLifecycleReport.owner_id == owner_id)
        .order_by(P86ReleaseLifecycleReport.created_at.desc(), P86ReleaseLifecycleReport.id.desc())
    ).first()
    if row is None:
        return P86ReleaseLifecycleLatestReportRead(status="EMPTY")
    runs = [P86ReleaseLifecycleRunRead.model_validate(item) for item in (row.runs_json or [])]
    return P86ReleaseLifecycleLatestReportRead(
        status=row.overall_status,
        title=row.title,
        body=row.body,
        created_at=row.created_at,
        runs=runs,
        action_url=row.action_url,
        report_id=int(row.id or 0),
    )


def has_ever_completed_lifecycle_batch(session: Session, *, owner_id: int) -> bool:
    report = session.exec(
        select(P86ReleaseLifecycleReport.id).where(P86ReleaseLifecycleReport.owner_id == owner_id).limit(1)
    ).first()
    if report is not None:
        return True
    run = session.exec(
        select(P86ReleaseLifecycleRun.id)
        .where(P86ReleaseLifecycleRun.owner_id == owner_id)
        .where(P86ReleaseLifecycleRun.completed_at.is_not(None))
        .limit(1)
    ).first()
    return run is not None
