"""P53-02 Quantity Recommendation Engine — deterministic copy counts from V2 + profile."""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from app.models.pull_list import PullListDecision
from app.models.recommendation_v2 import RecommendationScoreV2
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.schemas.purchase_profile import PurchasePreferenceRead, PurchaseProfileRead
from app.services.purchase_profiles import get_purchase_preferences, get_purchase_profile

ALLOWED_QUANTITIES = (0, 1, 2, 3, 5)

TIER_QUANTITY_BOUNDS: dict[str, tuple[int, int]] = {
    "PASS": (0, 0),
    "WATCH": (1, 1),
    "BUY": (1, 2),
    "STRONG_BUY": (2, 3),
    "MUST_BUY": (3, 5),
}

TIER_STRENGTH: dict[str, float] = {
    "PASS": 0.30,
    "WATCH": 0.50,
    "BUY": 0.70,
    "STRONG_BUY": 0.85,
    "MUST_BUY": 1.00,
}

PROFILE_QUANTITY_OFFSET: dict[str, float] = {
    "INVESTOR": 0.22,
    "COLLECTOR": 0.0,
    "READER": -0.22,
    "VARIANT_HUNTER": 0.0,
    "LONG_TERM_HOLD": 0.10,
}

PROFILE_TIER_ALIGNMENT: dict[str, dict[str, float]] = {
    "INVESTOR": {
        "MUST_BUY": 1.0,
        "STRONG_BUY": 0.92,
        "BUY": 0.75,
        "WATCH": 0.45,
        "PASS": 0.35,
    },
    "READER": {
        "MUST_BUY": 0.55,
        "STRONG_BUY": 0.70,
        "BUY": 0.88,
        "WATCH": 0.90,
        "PASS": 0.85,
    },
    "COLLECTOR": {
        "MUST_BUY": 0.82,
        "STRONG_BUY": 0.85,
        "BUY": 0.88,
        "WATCH": 0.80,
        "PASS": 0.75,
    },
    "VARIANT_HUNTER": {
        "MUST_BUY": 0.78,
        "STRONG_BUY": 0.80,
        "BUY": 0.82,
        "WATCH": 0.78,
        "PASS": 0.72,
    },
    "LONG_TERM_HOLD": {
        "MUST_BUY": 0.88,
        "STRONG_BUY": 0.90,
        "BUY": 0.86,
        "WATCH": 0.72,
        "PASS": 0.68,
    },
}


@dataclass(frozen=True)
class QuantityRecommendationResult:
    release_id: int
    recommendation_tier: str
    quantity_recommended: int
    confidence_score: float
    rationale: str
    pull_list_decision: str | None


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _quantity_options(lo: int, hi: int) -> tuple[int, ...]:
    return tuple(q for q in ALLOWED_QUANTITIES if lo <= q <= hi)


def compute_quantity_bias(
    *,
    profile_type: str,
    risk_tolerance: float,
    speculation_score: float,
    grading_interest: float,
    recommendation_tier: str,
) -> float:
    """0.0 = low end of tier band, 1.0 = high end."""
    key = profile_type.strip().upper()
    profile_offset = PROFILE_QUANTITY_OFFSET.get(key, 0.0)
    must_boost = 0.12 if key == "INVESTOR" and recommendation_tier == "MUST_BUY" else 0.0
    grading_boost = 0.08 * grading_interest if key == "LONG_TERM_HOLD" else 0.0
    reader_damp = -0.10 * speculation_score if key == "READER" else 0.0
    raw = (
        0.50
        + profile_offset
        + must_boost
        + grading_boost
        + reader_damp
        + 0.18 * (risk_tolerance - 0.5)
        + 0.14 * (speculation_score - 0.5)
        + 0.08 * (grading_interest - 0.5)
    )
    return _clamp01(raw)


def pick_quantity_for_tier(*, recommendation_tier: str, bias: float) -> int:
    tier = recommendation_tier.strip().upper()
    lo, hi = TIER_QUANTITY_BOUNDS.get(tier, (0, 0))
    options = _quantity_options(lo, hi)
    if not options:
        return 0
    if len(options) == 1:
        return options[0]
    idx = int(round(bias * (len(options) - 1)))
    idx = max(0, min(len(options) - 1, idx))
    return options[idx]


def compute_confidence_score(
    *,
    recommendation_tier: str,
    profile_type: str,
    v2_confidence: float,
    pull_decision: str | None,
    pull_confidence: float | None,
) -> float:
    tier = recommendation_tier.strip().upper()
    tier_strength = TIER_STRENGTH.get(tier, 0.5)
    align_map = PROFILE_TIER_ALIGNMENT.get(profile_type.strip().upper(), PROFILE_TIER_ALIGNMENT["COLLECTOR"])
    profile_align = align_map.get(tier, 0.75)
    franchise = _clamp01(v2_confidence)
    pull_factor = 0.0
    if pull_decision in {"START_RUN", "CONTINUE_RUN"} and pull_confidence is not None:
        pull_factor = _clamp01(pull_confidence)
    elif pull_decision == "WATCH" and pull_confidence is not None:
        pull_factor = _clamp01(pull_confidence) * 0.65
    franchise_blend = _clamp01(0.72 * franchise + 0.28 * pull_factor)
    return round(_clamp01(tier_strength * 0.42 + franchise_blend * 0.38 + profile_align * 0.20), 4)


def build_quantity_rationale(
    *,
    recommendation_tier: str,
    profile_type: str,
    pull_decision: str | None,
    series_name: str,
    v2_confidence: float,
) -> str:
    tier = recommendation_tier.strip().upper()
    profile = profile_type.strip().upper().replace("_", " ").title()
    if tier == "PASS":
        return f"Recommendation tier PASS; no purchase quantity suggested for {series_name or 'this release'}."
    if pull_decision == "CONTINUE_RUN":
        return "Existing active run with high recommendation confidence."
    if pull_decision == "START_RUN" and tier in {"MUST_BUY", "STRONG_BUY"}:
        return f"Strong franchise launch and {profile.lower()} profile alignment."
    if tier in {"MUST_BUY", "STRONG_BUY"} and v2_confidence >= 0.7:
        return f"Strong recommendation strength with {profile.lower()} profile."
    if tier == "BUY":
        return f"Moderate recommendation strength with {profile.lower()} profile."
    if tier == "WATCH":
        return f"Watch-tier signal; single-copy guidance for {profile.lower()} collecting."
    return f"Profile-aware quantity guidance for {profile.lower()} collecting."


def compute_quantity_recommendation(
    *,
    release_id: int,
    recommendation_tier: str,
    v2_confidence: float,
    profile: PurchaseProfileRead,
    preferences: PurchasePreferenceRead,
    pull_decision: str | None,
    pull_confidence: float | None,
    series_name: str = "",
) -> QuantityRecommendationResult:
    tier = recommendation_tier.strip().upper()
    bias = compute_quantity_bias(
        profile_type=profile.profile_type,
        risk_tolerance=preferences.risk_tolerance,
        speculation_score=preferences.speculation_score,
        grading_interest=preferences.grading_interest,
        recommendation_tier=tier,
    )
    quantity = pick_quantity_for_tier(recommendation_tier=tier, bias=bias)
    confidence = compute_confidence_score(
        recommendation_tier=tier,
        profile_type=profile.profile_type,
        v2_confidence=v2_confidence,
        pull_decision=pull_decision,
        pull_confidence=pull_confidence,
    )
    rationale = build_quantity_rationale(
        recommendation_tier=tier,
        profile_type=profile.profile_type,
        pull_decision=pull_decision,
        series_name=series_name,
        v2_confidence=v2_confidence,
    )
    return QuantityRecommendationResult(
        release_id=release_id,
        recommendation_tier=tier,
        quantity_recommended=quantity,
        confidence_score=confidence,
        rationale=rationale,
        pull_list_decision=pull_decision,
    )


def generate_quantity_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    v2_by_issue: dict[int, RecommendationScoreV2],
    pull_by_release: dict[int, PullListDecision],
    profile: PurchaseProfileRead | None = None,
    preferences: PurchasePreferenceRead | None = None,
) -> list[QuantityRecommendationResult]:
    """Compute quantity recommendations for all releases with V2 scores (read-only inputs)."""
    if profile is None:
        profile = get_purchase_profile(session, owner_user_id=owner_user_id)
    if preferences is None:
        preferences = get_purchase_preferences(session, owner_user_id=owner_user_id)

    results: list[QuantityRecommendationResult] = []
    for release_id in sorted(v2_by_issue.keys()):
        v2 = v2_by_issue[release_id]
        issue = session.get(ReleaseIssue, release_id)
        if issue is None or issue.owner_user_id != owner_user_id:
            continue
        series = session.get(ReleaseSeries, issue.series_id) if issue else None
        pull = pull_by_release.get(release_id)
        pull_type = pull.decision_type if pull else None
        pull_conf = float(pull.confidence_score) if pull else None
        results.append(
            compute_quantity_recommendation(
                release_id=release_id,
                recommendation_tier=v2.recommendation_tier,
                v2_confidence=float(v2.confidence_score),
                profile=profile,
                preferences=preferences,
                pull_decision=pull_type,
                pull_confidence=pull_conf,
                series_name=series.series_name if series else "",
            )
        )
    return results
