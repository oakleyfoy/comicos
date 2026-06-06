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


def test_p72_grading_roi_service_breakdown() -> None:
    from app.services.grade_probability_engine import estimate_grade_probabilities
    from app.services.grading_cost_service import estimate_grading_costs
    from app.services.grading_roi_service import calculate_grading_roi

    raw = 22.0
    probs = estimate_grade_probabilities(
        publisher="DC",
        release_year=2024,
        ownership_source=None,
        condition_notes="NM",
    )
    costs = estimate_grading_costs(raw_fmv=raw, release_year=2024)
    result = calculate_grading_roi(
        raw_fmv=raw,
        blended_fmv=raw,
        graded_fmv=95.0,
        probabilities=probs,
        costs=costs,
    )
    assert result.expected_profit == round(result.expected_graded_fmv - raw - result.total_cost, 2)
