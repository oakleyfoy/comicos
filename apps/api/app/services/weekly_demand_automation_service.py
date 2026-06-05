"""P61-04 Weekly Automated Capture orchestration."""

from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.demand_intelligence import (
    CAPTURE_STATUS_CERTIFIED,
    CAPTURE_STATUS_FAILED,
    CAPTURE_STATUS_PENDING,
    CAPTURE_STATUS_RUNNING,
    WeeklyDemandCaptureEvent,
    WeeklyDemandCaptureSchedule,
    utc_now,
)
from app.models.external_catalog import ExternalCatalogIssue
from app.services.demand_refresh_service import run_demand_refresh
from app.services.demand_velocity_service import compute_demand_velocity
from app.services.external_catalog.league_of_comic_geeks import LOCG_SOURCE_NAME


def _next_wednesdays(*, count: int = 4) -> list[date]:
    today = date.today()
    # Wednesday = 2
    days_ahead = (2 - today.weekday()) % 7
    first = today + timedelta(days=days_ahead or 7)
    return [first + timedelta(days=7 * i) for i in range(count)]


def discover_capture_schedule(session: Session, *, owner_user_id: int | None = None) -> list[WeeklyDemandCaptureSchedule]:
    created: list[WeeklyDemandCaptureSchedule] = []
    for release_date in _next_wednesdays(count=6):
        existing = session.exec(
            select(WeeklyDemandCaptureSchedule).where(WeeklyDemandCaptureSchedule.release_date == release_date)
        ).first()
        if existing:
            created.append(existing)
            continue
        row = WeeklyDemandCaptureSchedule(
            release_date=release_date,
            status=CAPTURE_STATUS_PENDING,
            owner_user_id=owner_user_id,
        )
        session.add(row)
        created.append(row)
    session.commit()
    for row in created:
        session.refresh(row)
    return created


def list_capture_schedule(session: Session) -> list[WeeklyDemandCaptureSchedule]:
    return session.exec(
        select(WeeklyDemandCaptureSchedule).order_by(WeeklyDemandCaptureSchedule.release_date.asc())
    ).all()


def _log_event(session: Session, *, schedule_id: int, step: str, status: str, message: str) -> None:
    session.add(
        WeeklyDemandCaptureEvent(
            schedule_id=schedule_id,
            step=step,
            status=status,
            message=message,
        )
    )


def run_post_capture_pipeline(
    session: Session,
    *,
    schedule: WeeklyDemandCaptureSchedule,
    owner_user_id: int | None,
) -> WeeklyDemandCaptureSchedule:
    schedule.status = CAPTURE_STATUS_RUNNING
    schedule.updated_at = utc_now()
    session.add(schedule)
    session.flush()
    sid = int(schedule.id or 0)
    try:
        _log_event(session, schedule_id=sid, step="demand_refresh", status="START", message="issue upcoming refresh")
        run_demand_refresh(
            session,
            scope="ISSUE_UPCOMING",
            days_forward=14,
            owner_user_id=owner_user_id,
            trigger_type="WEEKLY_CAPTURE",
        )
        _log_event(session, schedule_id=sid, step="demand_velocity", status="START", message="compute velocity")
        for window in (7, 14, 28):
            compute_demand_velocity(session, window_days=window)
        if owner_user_id is not None:
            from app.services.collector_intelligence_automation import run_collector_intelligence_pipeline

            _log_event(session, schedule_id=sid, step="collector_intelligence", status="START", message="P62 suite")
            run_collector_intelligence_pipeline(session, owner_user_id=int(owner_user_id))
            _log_event(session, schedule_id=sid, step="collector_intelligence", status="SUCCESS", message="P62 suite done")
        schedule.status = CAPTURE_STATUS_CERTIFIED
        schedule.details_json = {
            **(schedule.details_json or {}),
            "post_capture_completed_at": utc_now().isoformat(),
        }
        _log_event(session, schedule_id=sid, step="complete", status="SUCCESS", message="post-capture pipeline done")
    except Exception as exc:  # noqa: BLE001
        schedule.status = CAPTURE_STATUS_FAILED
        schedule.details_json = {**(schedule.details_json or {}), "error": str(exc)}
        _log_event(session, schedule_id=sid, step="complete", status="FAILED", message=str(exc))
    schedule.updated_at = utc_now()
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    return schedule


def mark_schedule_from_locg_cert(
    session: Session,
    *,
    release_date: date,
    certification_path: str,
    passed: bool,
    owner_user_id: int | None = None,
) -> WeeklyDemandCaptureSchedule:
    row = session.exec(
        select(WeeklyDemandCaptureSchedule).where(WeeklyDemandCaptureSchedule.release_date == release_date)
    ).first()
    if row is None:
        row = WeeklyDemandCaptureSchedule(release_date=release_date, owner_user_id=owner_user_id)
    row.certification_path = certification_path
    row.status = CAPTURE_STATUS_CERTIFIED if passed else CAPTURE_STATUS_FAILED
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    if passed:
        run_post_capture_pipeline(session, schedule=row, owner_user_id=owner_user_id)
    return row


def sync_schedule_from_catalog(session: Session) -> int:
    """Ensure schedule rows exist for max LoCG release_date in catalog."""
    issue = session.exec(
        select(ExternalCatalogIssue)
        .where(
            ExternalCatalogIssue.source_name == LOCG_SOURCE_NAME,
            ExternalCatalogIssue.release_date.is_not(None),
        )
        .order_by(ExternalCatalogIssue.release_date.desc())
    ).first()
    if issue is None or issue.release_date is None:
        return 0
    release_date = issue.release_date
    discover_capture_schedule(session)
    existing = session.exec(
        select(WeeklyDemandCaptureSchedule).where(WeeklyDemandCaptureSchedule.release_date == release_date)
    ).first()
    if existing:
        return 0
    session.add(WeeklyDemandCaptureSchedule(release_date=release_date, status=CAPTURE_STATUS_CERTIFIED))
    session.commit()
    return 1
