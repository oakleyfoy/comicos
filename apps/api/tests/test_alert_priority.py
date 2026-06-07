"""P90 alert priority tests."""

from __future__ import annotations

from app.services.collector_alert_priority_service import PriorityInputs, compute_priority_score


def test_priority_higher_for_strong_buy_profit() -> None:
    low = compute_priority_score(
        PriorityInputs(alert_type="BUY_OPPORTUNITY", severity="MEDIUM", confidence="MEDIUM", profit_signal=5.0)
    )
    high = compute_priority_score(
        PriorityInputs(alert_type="BUY_OPPORTUNITY", severity="HIGH", confidence="HIGH", profit_signal=35.0)
    )
    assert high > low
    assert 0 <= high <= 100


def test_release_proximity_boosts_score() -> None:
    far = compute_priority_score(
        PriorityInputs(alert_type="RELEASE_ALERT", severity="MEDIUM", confidence="MEDIUM", release_days=20)
    )
    soon = compute_priority_score(
        PriorityInputs(alert_type="RELEASE_ALERT", severity="MEDIUM", confidence="MEDIUM", release_days=2)
    )
    assert soon > far
