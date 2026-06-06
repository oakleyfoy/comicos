from __future__ import annotations

from app.services.grade_probability_engine import estimate_grade_probabilities
from app.services.grading_cost_service import estimate_grading_costs
from app.services.grading_roi_service import calculate_grading_roi
from app.services.pressing_intelligence_service import DO_NOT_PRESS, PRESS, recommend_pressing


def _roi(raw: float, *, graded_anchor: float | None = None):
    probs = estimate_grade_probabilities(
        publisher="DC",
        release_year=2024,
        ownership_source=None,
        condition_notes="NM",
    )
    costs = estimate_grading_costs(raw_fmv=raw, release_year=2024, include_press=False)
    return calculate_grading_roi(
        raw_fmv=raw,
        blended_fmv=raw,
        graded_fmv=graded_anchor,
        probabilities=probs,
        costs=costs,
    )


def test_press_when_defects_and_positive_roi() -> None:
    roi = _roi(22.0, graded_anchor=95.0)
    rec = recommend_pressing(
        raw_fmv=22.0,
        liquidity_score=55.0,
        roi=roi,
        condition_notes="light crease",
        expected_roi_pct=roi.expected_roi_pct,
        release_year=2024,
    )
    assert rec.recommendation == PRESS


def test_do_not_press_when_value_too_low() -> None:
    roi = _roi(8.0)
    rec = recommend_pressing(
        raw_fmv=8.0,
        liquidity_score=10.0,
        roi=roi,
        condition_notes=None,
        expected_roi_pct=roi.expected_roi_pct,
        release_year=2024,
    )
    assert rec.recommendation == DO_NOT_PRESS
