"""P90-02 FMV trend analysis from historical values."""

from __future__ import annotations


def compute_trend_score(*, current_value: float, prior_value: float | None) -> tuple[str, float]:
    if prior_value is None or prior_value <= 0 or current_value <= 0:
        return "FLAT", 0.0
    pct = (current_value - prior_value) / prior_value * 100.0
    score = max(-100.0, min(100.0, round(pct * 2.0, 1)))
    if pct >= 5.0:
        return "UP", score
    if pct <= -5.0:
        return "DOWN", score
    return "FLAT", score
