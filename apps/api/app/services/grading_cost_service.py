"""P72-01 configurable grading cost model (advisory only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

GRADING_COST_CGC_MODERN = "CGC_MODERN"
GRADING_COST_CGC_VINTAGE = "CGC_VINTAGE"

DEFAULT_COSTS: dict[str, float] = {
    GRADING_COST_CGC_MODERN: 22.0,
    GRADING_COST_CGC_VINTAGE: 38.0,
    "CGC_PRESSING": 12.0,
    "CGC_CLEANING": 8.0,
    "SHIPPING": 12.0,
    "INSURANCE": 4.0,
}


@dataclass(frozen=True)
class GradingCostBreakdown:
    grading_tier: str
    grading_fee: float
    pressing_fee: float
    cleaning_fee: float
    shipping_fee: float
    insurance_fee: float
    total_cost: float
    factors_json: dict


def _is_vintage(*, release_year: int | None, today: date | None = None) -> bool:
    today = today or date.today()
    if release_year is None:
        return False
    return release_year < today.year - 25


def estimate_grading_costs(
    *,
    raw_fmv: float,
    include_press: bool = False,
    include_cleaning: bool = False,
    release_year: int | None = None,
    grader: str = "CGC",
) -> GradingCostBreakdown:
    vintage = _is_vintage(release_year=release_year)
    tier = GRADING_COST_CGC_VINTAGE if vintage else GRADING_COST_CGC_MODERN
    grading_fee = DEFAULT_COSTS[tier]
    pressing_fee = DEFAULT_COSTS["CGC_PRESSING"] if include_press else 0.0
    cleaning_fee = DEFAULT_COSTS["CGC_CLEANING"] if include_cleaning else 0.0
    shipping_fee = DEFAULT_COSTS["SHIPPING"]
    insurance_fee = max(DEFAULT_COSTS["INSURANCE"], round(raw_fmv * 0.02, 2))
    total = round(grading_fee + pressing_fee + cleaning_fee + shipping_fee + insurance_fee, 2)
    return GradingCostBreakdown(
        grading_tier=tier,
        grading_fee=grading_fee,
        pressing_fee=pressing_fee,
        cleaning_fee=cleaning_fee,
        shipping_fee=shipping_fee,
        insurance_fee=insurance_fee,
        total_cost=total,
        factors_json={
            "grader": grader,
            "vintage": vintage,
            "release_year": release_year,
            "raw_fmv": raw_fmv,
        },
    )
