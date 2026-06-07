"""P89-01 sell candidate exit confidence (rule-based)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfidenceInputs:
    has_fmv: bool
    has_cost: bool
    has_identity: bool
    has_grade_status: bool
    hold_sell_agrees: bool | None
    grade_signal: bool
    profit_ratio: float | None


def score_exit_confidence(inputs: ConfidenceInputs) -> str:
    score = 0.0
    if inputs.has_fmv:
        score += 0.28
    if inputs.has_cost:
        score += 0.22
    if inputs.has_identity:
        score += 0.15
    if inputs.has_grade_status:
        score += 0.1
    if inputs.hold_sell_agrees is True:
        score += 0.15
    elif inputs.hold_sell_agrees is False:
        score -= 0.05
    if inputs.grade_signal:
        score += 0.05
    if inputs.profit_ratio is not None and inputs.profit_ratio >= 0.25:
        score += 0.1
    if score >= 0.72:
        return "HIGH"
    if score >= 0.45:
        return "MEDIUM"
    return "LOW"
