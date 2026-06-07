"""P90 FMV trend tests."""

from __future__ import annotations

from app.services.fmv_trend_service import compute_trend_score


def test_trend_up_and_down() -> None:
    up_dir, up_score = compute_trend_score(current_value=110, prior_value=100)
    assert up_dir == "UP"
    assert up_score > 0
    down_dir, down_score = compute_trend_score(current_value=90, prior_value=100)
    assert down_dir == "DOWN"
    assert down_score < 0


def test_trend_flat_when_missing_prior() -> None:
    direction, score = compute_trend_score(current_value=50, prior_value=None)
    assert direction == "FLAT"
    assert score == 0.0
