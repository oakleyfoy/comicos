from __future__ import annotations

from datetime import date

from app.models.p86_release_lifecycle import (
    LIFECYCLE_STAGE_EARLY_DISCOVERY,
    LIFECYCLE_STAGE_POST_RELEASE_CLEANUP,
    LIFECYCLE_STAGE_PREORDER_ACCURACY,
    LIFECYCLE_STAGE_RELEASE_DAY_REFRESH,
)
from app.services.release_lifecycle_plan import (
    build_weekly_lifecycle_plan,
    capture_date_for_anchor,
    current_release_wednesday,
    lifecycle_stage_for_offset_weeks,
    sequential_execution_order,
)
from app.services.release_lifecycle_plan import LifecyclePlanItem


def test_current_release_wednesday_on_wednesday() -> None:
    assert current_release_wednesday(today=date(2026, 6, 10)) == date(2026, 6, 10)


def test_current_release_wednesday_monday_uses_upcoming_wednesday() -> None:
    assert current_release_wednesday(today=date(2026, 6, 8)) == date(2026, 6, 10)


def test_weekly_plan_four_dates_example_june_2026() -> None:
    plan = build_weekly_lifecycle_plan(anchor=date(2026, 6, 10), run_date=date(2026, 6, 10))
    assert plan.anchor_release_date == date(2026, 6, 10)
    by_date = {item.target_release_date: item.lifecycle_stage for item in plan.items}
    assert by_date[date(2026, 4, 15)] == LIFECYCLE_STAGE_POST_RELEASE_CLEANUP
    assert by_date[date(2026, 6, 10)] == LIFECYCLE_STAGE_RELEASE_DAY_REFRESH
    assert by_date[date(2026, 8, 5)] == LIFECYCLE_STAGE_PREORDER_ACCURACY
    assert by_date[date(2026, 9, 2)] == LIFECYCLE_STAGE_EARLY_DISCOVERY


def test_lifecycle_stage_assignment_offsets() -> None:
    assert lifecycle_stage_for_offset_weeks(-8) == LIFECYCLE_STAGE_POST_RELEASE_CLEANUP
    assert lifecycle_stage_for_offset_weeks(0) == LIFECYCLE_STAGE_RELEASE_DAY_REFRESH
    assert lifecycle_stage_for_offset_weeks(8) == LIFECYCLE_STAGE_PREORDER_ACCURACY
    assert lifecycle_stage_for_offset_weeks(12) == LIFECYCLE_STAGE_EARLY_DISCOVERY


def test_capture_date_for_anchor() -> None:
    anchor = date(2026, 6, 10)
    assert capture_date_for_anchor(anchor=anchor, offset_weeks=-8) == date(2026, 4, 15)
    assert capture_date_for_anchor(anchor=anchor, offset_weeks=12) == date(2026, 9, 2)


def test_sequential_execution_order() -> None:
    items = [
        LifecyclePlanItem(date(2026, 9, 2), LIFECYCLE_STAGE_EARLY_DISCOVERY),
        LifecyclePlanItem(date(2026, 4, 15), LIFECYCLE_STAGE_POST_RELEASE_CLEANUP),
        LifecyclePlanItem(date(2026, 8, 5), LIFECYCLE_STAGE_PREORDER_ACCURACY),
        LifecyclePlanItem(date(2026, 6, 10), LIFECYCLE_STAGE_RELEASE_DAY_REFRESH),
    ]
    ordered = sequential_execution_order(items)
    assert [i.lifecycle_stage for i in ordered] == [
        LIFECYCLE_STAGE_POST_RELEASE_CLEANUP,
        LIFECYCLE_STAGE_RELEASE_DAY_REFRESH,
        LIFECYCLE_STAGE_PREORDER_ACCURACY,
        LIFECYCLE_STAGE_EARLY_DISCOVERY,
    ]
