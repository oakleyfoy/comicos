from __future__ import annotations

from app.services.grading_intelligence_roi import (
    calculate_expected_graded_value,
    calculate_expected_profit,
    calculate_grading_cost,
    calculate_roi_percent,
)


def test_grading_roi_calculations_are_deterministic() -> None:
    raw = 25.0
    cost = calculate_grading_cost(grading_scale="PSA")
    graded = calculate_expected_graded_value(raw_value=raw, predicted_grade="9.8")
    profit = calculate_expected_profit(expected_graded_value=graded, raw_value=raw, grading_cost=cost)
    roi = calculate_roi_percent(expected_profit=profit, raw_value=raw, grading_cost=cost)
    assert cost == 30.0
    assert graded == 70.0
    assert profit == 15.0
    assert roi == round((15.0 / 55.0) * 100.0, 2)
