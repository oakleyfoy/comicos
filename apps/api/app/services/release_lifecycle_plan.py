"""P86 release lifecycle date plan (pure logic)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models.p86_release_lifecycle import (
    LIFECYCLE_STAGE_EARLY_DISCOVERY,
    LIFECYCLE_STAGE_POST_RELEASE_CLEANUP,
    LIFECYCLE_STAGE_PREORDER_ACCURACY,
    LIFECYCLE_STAGE_RELEASE_DAY_REFRESH,
    LIFECYCLE_STAGES,
)

WEEKS_BEFORE_POST = 8
WEEKS_AFTER_PREORDER = 8
WEEKS_AFTER_EARLY = 12

PRODUCTION_OWNER_EMAIL = "ofoy@att.net"
SCHEDULE_TIME = "22:00"
SCHEDULE_TIMEZONE = "America/Chicago"


@dataclass(frozen=True)
class LifecyclePlanItem:
    target_release_date: date
    lifecycle_stage: str


@dataclass(frozen=True)
class WeeklyLifecyclePlan:
    anchor_release_date: date
    run_date: date
    items: tuple[LifecyclePlanItem, ...]


def current_release_wednesday(*, today: date | None = None) -> date:
    """Wednesday for the active comic release week (upcoming Wed Mon–Wed; same week Wed Thu–Sun)."""
    anchor = today or date.today()
    weekday = anchor.weekday()
    if weekday <= 2:
        return anchor + timedelta(days=2 - weekday)
    return anchor - timedelta(days=weekday - 2)


def lifecycle_stage_for_offset_weeks(offset_weeks: int) -> str:
    if offset_weeks == -WEEKS_BEFORE_POST:
        return LIFECYCLE_STAGE_POST_RELEASE_CLEANUP
    if offset_weeks == 0:
        return LIFECYCLE_STAGE_RELEASE_DAY_REFRESH
    if offset_weeks == WEEKS_AFTER_PREORDER:
        return LIFECYCLE_STAGE_PREORDER_ACCURACY
    if offset_weeks == WEEKS_AFTER_EARLY:
        return LIFECYCLE_STAGE_EARLY_DISCOVERY
    raise ValueError(f"unsupported lifecycle offset weeks: {offset_weeks}")


def capture_date_for_anchor(*, anchor: date, offset_weeks: int) -> date:
    return anchor + timedelta(days=7 * offset_weeks)


def build_weekly_lifecycle_plan(*, anchor: date | None = None, run_date: date | None = None) -> WeeklyLifecyclePlan:
    t = anchor or current_release_wednesday()
    batch_day = run_date or date.today()
    offsets = (-WEEKS_BEFORE_POST, 0, WEEKS_AFTER_PREORDER, WEEKS_AFTER_EARLY)
    items = tuple(
        LifecyclePlanItem(
            target_release_date=capture_date_for_anchor(anchor=t, offset_weeks=offset),
            lifecycle_stage=lifecycle_stage_for_offset_weeks(offset),
        )
        for offset in offsets
    )
    return WeeklyLifecyclePlan(anchor_release_date=t, run_date=batch_day, items=items)


def sequential_execution_order(items: list[LifecyclePlanItem]) -> list[LifecyclePlanItem]:
    stage_rank = {stage: idx for idx, stage in enumerate(LIFECYCLE_STAGES)}
    return sorted(items, key=lambda item: stage_rank.get(item.lifecycle_stage, 99))


def compute_next_wednesday_schedule_at(
    *,
    schedule_time: str = SCHEDULE_TIME,
    timezone_name: str = SCHEDULE_TIMEZONE,
    from_moment: datetime | None = None,
) -> datetime:
    tz = ZoneInfo(timezone_name)
    now_local = (from_moment or datetime.now(timezone.utc)).astimezone(tz)
    hour_str, minute_str = schedule_time.split(":", maxsplit=1)
    hour, minute = int(hour_str), int(minute_str)
    weekday = now_local.weekday()
    days_until_wed = (2 - weekday) % 7
    target_local = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_until_wed)
    if days_until_wed == 0 and target_local <= now_local:
        target_local += timedelta(days=7)
    return target_local.astimezone(timezone.utc)
