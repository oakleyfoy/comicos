from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from app.models.pull_list import PullListAutomationRun, PullListAutomationSchedule
from app.services.lunar_scheduler import compute_next_run_at

DEFAULT_SCHEDULE_TIME = "06:15"
DEFAULT_TIMEZONE = "America/Chicago"


def get_platform_schedule(session: Session) -> PullListAutomationSchedule:
    row = session.exec(select(PullListAutomationSchedule).order_by(PullListAutomationSchedule.id.asc())).first()
    if row is not None:
        return row
    row = PullListAutomationSchedule(
        enabled=True,
        schedule_time=DEFAULT_SCHEDULE_TIME,
        timezone=DEFAULT_TIMEZONE,
        next_run_at=compute_next_run_at(schedule_time=DEFAULT_SCHEDULE_TIME, timezone_name=DEFAULT_TIMEZONE),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def is_schedule_due(session: Session, *, moment: datetime | None = None) -> bool:
    now = moment or datetime.now(timezone.utc)
    config = get_platform_schedule(session)
    if not config.enabled or config.next_run_at is None:
        return False
    return config.next_run_at <= now


def advance_schedule_after_run(session: Session, *, moment: datetime | None = None) -> PullListAutomationSchedule:
    now = moment or datetime.now(timezone.utc)
    config = get_platform_schedule(session)
    config.next_run_at = compute_next_run_at(
        schedule_time=config.schedule_time,
        timezone_name=config.timezone,
        from_moment=now + timedelta(seconds=1),
    )
    config.updated_at = datetime.now(timezone.utc)
    session.add(config)
    session.commit()
    session.refresh(config)
    return config


def verify_upstream_refresh_order(session: Session, *, moment: datetime | None = None) -> tuple[bool, str]:
    """Advisory check: release/recommendation activity should precede pull-list refresh."""
    from app.models.lunar_scheduler import LunarScheduledRun
    from app.models.recommendation_v2 import RecommendationRunV2

    now = moment or datetime.now(timezone.utc)
    config = get_platform_schedule(session)
    tz = ZoneInfo(config.timezone)
    local_day_start = now.astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)

    lunar = session.exec(
        select(LunarScheduledRun)
        .where(LunarScheduledRun.completed_at.is_not(None))
        .order_by(LunarScheduledRun.completed_at.desc())
    ).first()
    rec = session.exec(
        select(RecommendationRunV2)
        .where(RecommendationRunV2.status == "COMPLETED")
        .order_by(RecommendationRunV2.completed_at.desc())
    ).first()

    if lunar is None or lunar.completed_at is None or lunar.completed_at < local_day_start:
        return False, "Release intelligence (Lunar) has not completed for the current schedule day."
    if rec is None or rec.completed_at is None or rec.completed_at < local_day_start:
        return False, "Recommendation intelligence has not completed for the current schedule day."
    return True, "Release Intelligence → Recommendation Intelligence → Pull List Refresh order satisfied."
