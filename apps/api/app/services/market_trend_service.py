"""P89-02 marketplace price trend from snapshot history."""

from __future__ import annotations


def compute_trend_direction(*, current_average: float, prior_average: float | None) -> str:
    if prior_average is None or prior_average <= 0 or current_average <= 0:
        return "FLAT"
    change = (current_average - prior_average) / prior_average
    if change >= 0.05:
        return "UP"
    if change <= -0.05:
        return "DOWN"
    return "FLAT"
