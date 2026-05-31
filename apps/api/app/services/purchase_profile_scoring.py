from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.models.purchase_profile import DEFAULT_PROFILE_TYPE, PURCHASE_PROFILE_TYPES

PROFILE_PRESETS: Final[dict[str, dict[str, float | str]]] = {
    "INVESTOR": {
        "display_name": "Investor",
        "description": "Prioritize speculation and grading upside for resale-focused collecting.",
        "risk_tolerance": 0.65,
        "variant_interest": 0.45,
        "grading_interest": 0.75,
        "completionist_score": 0.35,
        "speculation_score": 0.85,
    },
    "COLLECTOR": {
        "display_name": "Collector",
        "description": "Balanced collecting across reads, keys, and long-term series enjoyment.",
        "risk_tolerance": 0.50,
        "variant_interest": 0.50,
        "grading_interest": 0.50,
        "completionist_score": 0.50,
        "speculation_score": 0.50,
    },
    "READER": {
        "display_name": "Reader",
        "description": "Focus on story consumption with lower grading and speculation emphasis.",
        "risk_tolerance": 0.35,
        "variant_interest": 0.30,
        "grading_interest": 0.25,
        "completionist_score": 0.55,
        "speculation_score": 0.20,
    },
    "VARIANT_HUNTER": {
        "display_name": "Variant Hunter",
        "description": "Emphasize variant coverage and chase covers across the catalog.",
        "risk_tolerance": 0.55,
        "variant_interest": 0.90,
        "grading_interest": 0.45,
        "completionist_score": 0.60,
        "speculation_score": 0.40,
    },
    "LONG_TERM_HOLD": {
        "display_name": "Long-Term Hold",
        "description": "Prioritize graded preservation and run completion for long horizons.",
        "risk_tolerance": 0.40,
        "variant_interest": 0.35,
        "grading_interest": 0.80,
        "completionist_score": 0.85,
        "speculation_score": 0.35,
    },
}


def preset_for_profile_type(profile_type: str) -> dict[str, float | str]:
    key = profile_type.strip().upper()
    if key not in PURCHASE_PROFILE_TYPES:
        key = DEFAULT_PROFILE_TYPE
    return dict(PROFILE_PRESETS[key])


@dataclass(frozen=True)
class EngineWeights:
    quantity_weight: float
    variant_weight: float
    budget_weight: float


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def compute_engine_weights(
    *,
    profile_type: str,
    risk_tolerance: float,
    variant_interest: float,
    grading_interest: float,
    completionist_score: float,
    speculation_score: float,
) -> EngineWeights:
    """Deterministic normalized weights for future quantity, variant, and budget engines."""
    rt = _clamp01(risk_tolerance)
    vi = _clamp01(variant_interest)
    gi = _clamp01(grading_interest)
    cs = _clamp01(completionist_score)
    sp = _clamp01(speculation_score)

    quantity_raw = 0.35 * cs + 0.25 * (1.0 - rt) + 0.20 * (1.0 - vi) + 0.20 * (0.5 if profile_type == "READER" else 0.35)
    variant_raw = 0.55 * vi + 0.20 * (1.0 if profile_type == "VARIANT_HUNTER" else 0.0) + 0.15 * sp + 0.10 * rt
    budget_raw = 0.30 * rt + 0.25 * sp + 0.25 * gi + 0.20 * (1.0 - cs)

    total = quantity_raw + variant_raw + budget_raw
    if total <= 0:
        return EngineWeights(quantity_weight=1 / 3, variant_weight=1 / 3, budget_weight=1 / 3)
    return EngineWeights(
        quantity_weight=round(quantity_raw / total, 6),
        variant_weight=round(variant_raw / total, 6),
        budget_weight=round(budget_raw / total, 6),
    )
