"""P72-01 pressing recommendation engine."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.grading_roi_service import GradingRoiResult

PRESS = "PRESS"
DO_NOT_PRESS = "DO_NOT_PRESS"


@dataclass(frozen=True)
class PressingRecommendation:
    recommendation: str
    press_uplift_pct: float
    rationale: str
    factors_json: dict


def recommend_pressing(
    *,
    raw_fmv: float,
    liquidity_score: float,
    roi: GradingRoiResult,
    condition_notes: str | None,
    expected_roi_pct: float,
    release_year: int | None = None,
) -> PressingRecommendation:
    notes = (condition_notes or "").lower()
    has_defects = any(k in notes for k in ("crease", "bend", "warp", "dent", "non-color"))
    uplift = 0.12 if has_defects else 0.06
    modern = release_year is not None and release_year >= 2015
    if raw_fmv >= 15 and raw_fmv <= 120 and liquidity_score >= 25 and expected_roi_pct >= 40 and has_defects:
        return PressingRecommendation(
            recommendation=PRESS,
            press_uplift_pct=round(uplift * 100, 1),
            rationale="Condition notes suggest pressable defects with positive grading ROI.",
            factors_json={"liquidity_score": liquidity_score, "has_defects": has_defects},
        )
    if (
        modern
        and 15 <= raw_fmv <= 120
        and liquidity_score >= 30
        and expected_roi_pct >= 75
        and not has_defects
    ):
        return PressingRecommendation(
            recommendation=PRESS,
            press_uplift_pct=round(uplift * 100, 1),
            rationale="Modern key with strong grading economics; optional press may improve grade odds.",
            factors_json={"liquidity_score": liquidity_score, "modern": True},
        )
    if raw_fmv < 15 or expected_roi_pct < 25:
        return PressingRecommendation(
            recommendation=DO_NOT_PRESS,
            press_uplift_pct=0.0,
            rationale="Low raw value or ROI does not justify pressing cost.",
            factors_json={"liquidity_score": liquidity_score},
        )
    return PressingRecommendation(
        recommendation=DO_NOT_PRESS,
        press_uplift_pct=round(uplift * 100, 1),
        rationale="Pressing optional; grade without press is acceptable.",
        factors_json={"liquidity_score": liquidity_score, "has_defects": has_defects},
    )
