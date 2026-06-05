from __future__ import annotations

from app.services.external_catalog.locg_adaptive_delay import (
    CONSECUTIVE_CLEAN_PAGES_TO_DECREASE,
    DELAY_DECREASE_ON_CLEAN_STREAK_SECONDS,
    DELAY_INCREASE_ON_THROTTLE_SECONDS,
    AdaptiveDelayController,
)


def test_increase_on_throttle_and_decrease_after_clean_streak() -> None:
    ctrl = AdaptiveDelayController(min_delay_seconds=0.75, max_delay_seconds=1.5)
    start = ctrl.current_delay_seconds
    ctrl.record_issue_outcome(had_429=True, had_cloudflare=False, succeeded=True)
    after_bump = min(
        ctrl.max_delay_seconds,
        round(start + DELAY_INCREASE_ON_THROTTLE_SECONDS, 3),
    )
    assert ctrl.current_delay_seconds == after_bump
    assert ctrl.consecutive_clean_pages == 0

    for _ in range(CONSECUTIVE_CLEAN_PAGES_TO_DECREASE):
        ctrl.record_issue_outcome(had_429=False, had_cloudflare=False, succeeded=True)
    assert ctrl.current_delay_seconds == round(after_bump - DELAY_DECREASE_ON_CLEAN_STREAK_SECONDS, 3)


def test_sample_pre_goto_within_bounds() -> None:
    ctrl = AdaptiveDelayController(min_delay_seconds=0.75, max_delay_seconds=1.5)
    for _ in range(50):
        sample = ctrl.sample_pre_goto_delay()
        assert 0.75 <= sample <= 1.5
