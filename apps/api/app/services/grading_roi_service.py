"""P72-01 grading ROI calculations (read-only advisory)."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.grade_probability_engine import GradeProbabilityDistribution
from app.services.grading_cost_service import GradingCostBreakdown

GRADE_FMV_MULTIPLIERS: dict[str, float] = {
    "9.8": 4.5,
    "9.6": 3.2,
    "9.4": 2.4,
    "9.2": 1.8,
    "other": 1.25,
}


@dataclass(frozen=True)
class GradingRoiResult:
    raw_fmv: float
    expected_graded_fmv: float
    total_cost: float
    expected_profit: float
    expected_roi_pct: float
    grade_fmv_breakdown: dict[str, float]
    calculation_json: dict


def _graded_fmv_at_grade(*, raw_fmv: float, graded_fmv: float | None, grade_key: str) -> float:
    if graded_fmv and graded_fmv > 0:
        mult = GRADE_FMV_MULTIPLIERS.get(grade_key, 1.25)
        anchor = graded_fmv / GRADE_FMV_MULTIPLIERS.get("9.6", 3.2)
        return round(max(raw_fmv * mult, anchor * mult), 2)
    mult = GRADE_FMV_MULTIPLIERS.get(grade_key, 1.25)
    return round(raw_fmv * mult, 2)


def calculate_grading_roi(
    *,
    raw_fmv: float,
    blended_fmv: float | None,
    graded_fmv: float | None,
    probabilities: GradeProbabilityDistribution,
    costs: GradingCostBreakdown,
) -> GradingRoiResult:
    base = blended_fmv if blended_fmv and blended_fmv > 0 else raw_fmv
    dist = probabilities.as_dict()
    breakdown: dict[str, float] = {}
    expected = 0.0
    for grade_key, prob in dist.items():
        fmv_at = _graded_fmv_at_grade(raw_fmv=base, graded_fmv=graded_fmv, grade_key=grade_key)
        breakdown[grade_key] = fmv_at
        expected += fmv_at * prob
    expected = round(expected, 2)
    profit = round(expected - raw_fmv - costs.total_cost, 2)
    roi = round((profit / costs.total_cost * 100.0) if costs.total_cost > 0 else 0.0, 2)
    return GradingRoiResult(
        raw_fmv=round(raw_fmv, 2),
        expected_graded_fmv=expected,
        total_cost=costs.total_cost,
        expected_profit=profit,
        expected_roi_pct=roi,
        grade_fmv_breakdown=breakdown,
        calculation_json={
            "formula_profit": "expected_graded_fmv - raw_fmv - total_cost",
            "formula_roi": "expected_profit / total_cost * 100",
            "cost_breakdown": {
                "grading_fee": costs.grading_fee,
                "pressing_fee": costs.pressing_fee,
                "cleaning_fee": costs.cleaning_fee,
                "shipping_fee": costs.shipping_fee,
                "insurance_fee": costs.insurance_fee,
            },
        },
    )
