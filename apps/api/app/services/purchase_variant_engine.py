"""P53-03 Variant Intelligence Engine — cover-level BUY / WATCH / AVOID guidance."""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.purchase_quantity import PurchaseQuantityRecommendation
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.schemas.purchase_profile import PurchasePreferenceRead, PurchaseProfileRead
from app.services.purchase_profiles import get_purchase_preferences, get_purchase_profile
from app.services.purchase_variant_classifier import (
    classify_purchase_variant_type,
    parse_ratio_denominator,
    ratio_risk_tier,
)

REC_BUY = "BUY"
REC_WATCH = "WATCH"
REC_AVOID = "AVOID"

ELITE_TIERS = frozenset({"MUST_BUY", "STRONG_BUY"})
STRONG_TIERS = frozenset({"MUST_BUY", "STRONG_BUY", "BUY"})


@dataclass(frozen=True)
class VariantRecommendationResult:
    release_id: int
    variant_id: int | None
    cover_label: str
    variant_type: str
    recommendation: str
    confidence_score: float
    rationale: str


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _profile_variant_tolerance(profile_type: str, variant_interest: float) -> float:
    key = profile_type.strip().upper()
    base = {
        "INVESTOR": 0.45,
        "COLLECTOR": 0.55,
        "READER": 0.20,
        "VARIANT_HUNTER": 0.85,
        "LONG_TERM_HOLD": 0.40,
    }.get(key, 0.50)
    return _clamp01(0.65 * base + 0.35 * variant_interest)


def _elite_signal(*, recommendation_tier: str, quantity_confidence: float) -> bool:
    tier = recommendation_tier.strip().upper()
    return tier == "MUST_BUY" and quantity_confidence >= 0.82


def _strong_recommendation(*, recommendation_tier: str) -> bool:
    return recommendation_tier.strip().upper() in ELITE_TIERS


def _high_confidence(quantity_confidence: float) -> bool:
    return quantity_confidence >= 0.72


def evaluate_variant_recommendation(
    *,
    variant_type: str,
    cover_label: str,
    ratio_denominator: int | None,
    quantity_recommended: int,
    recommendation_tier: str,
    quantity_confidence: float,
    profile: PurchaseProfileRead,
    preferences: PurchasePreferenceRead,
    series_name: str = "",
    weak_metadata: bool = False,
) -> tuple[str, float, str]:
    vtype = variant_type.strip().upper()
    tier = recommendation_tier.strip().upper()
    tolerance = _profile_variant_tolerance(profile.profile_type, preferences.variant_interest)
    profile_key = profile.profile_type.strip().upper()

    if quantity_recommended <= 0:
        return (
            REC_AVOID,
            round(_clamp01(0.55 + quantity_confidence * 0.2), 4),
            f"No purchase quantity allocated; avoid {cover_label} for {series_name or 'this release'}.",
        )

    if vtype == "COVER_A":
        conf = round(_clamp01(0.62 + quantity_confidence * 0.35), 4)
        return REC_BUY, conf, "Primary cover recommended when purchase quantity is above zero."

    if vtype == "OPEN_ORDER":
        rec = REC_WATCH
        conf = round(_clamp01(0.48 + quantity_confidence * 0.28), 4)
        rationale = f"Open-order cover {cover_label}; monitor before adding to pull."
        if profile_key == "READER":
            return REC_AVOID, conf, "Reader profile prioritizes Cover A only; avoid alternate open-order covers."
        if _high_confidence(quantity_confidence) and tolerance >= 0.62 and tier in STRONG_TIERS:
            return REC_BUY, round(conf + 0.12, 4), f"Strong recommendation fit for {profile_key.replace('_', ' ').title()} collecting."
        if profile_key == "VARIANT_HUNTER" and tier in STRONG_TIERS:
            return REC_BUY, round(conf + 0.08, 4), "Variant Hunter profile tolerates open-order chase covers."
        return rec, conf, rationale

    if vtype == "INCENTIVE":
        conf = round(_clamp01(0.45 + quantity_confidence * 0.30), 4)
        if profile_key == "LONG_TERM_HOLD" and _strong_recommendation(recommendation_tier=tier):
            return REC_BUY, round(conf + 0.1, 4), "Long-term hold profile allows selective incentive variants."
        if preferences.variant_interest >= 0.72 and tier in ELITE_TIERS:
            return REC_BUY, round(conf + 0.08, 4), "High variant interest with strong issue recommendation supports incentive buy."
        if profile_key == "READER":
            return REC_AVOID, conf, "Reader profile avoids incentive variants."
        return REC_WATCH, conf, f"Incentive variant {cover_label}; watch unless signals strengthen."

    if vtype == "RATIO":
        risk = ratio_risk_tier(ratio_denominator)
        conf = round(_clamp01(0.40 + quantity_confidence * 0.32), 4)
        ratio_label = f"1:{ratio_denominator}" if ratio_denominator else "ratio"
        if risk == "extreme":
            if _elite_signal(recommendation_tier=tier, quantity_confidence=quantity_confidence) and (
                profile_key == "VARIANT_HUNTER" or preferences.variant_interest >= 0.75
            ):
                return REC_WATCH, round(conf + 0.05, 4), f"{ratio_label} is high risk; elite signal warrants watch-only guidance."
            return REC_AVOID, conf, f"{ratio_label} ratio variant avoided unless elite franchise signal is present."
        if risk == "high":
            if tier in ELITE_TIERS and tolerance >= 0.55:
                return REC_WATCH, conf, f"{ratio_label} is high risk; watch under strong tier only."
            return REC_AVOID, round(conf - 0.05, 4), f"{ratio_label} ratio carries elevated risk for this profile."
        if risk == "moderate":
            if tier in ELITE_TIERS and tolerance >= 0.50:
                return REC_WATCH, conf, f"{ratio_label} acceptable to watch on stronger recommendations."
            return REC_AVOID, conf, f"{ratio_label} requires stronger recommendation strength."
        # low risk 1:10
        if tier in ELITE_TIERS and (_high_confidence(quantity_confidence) or profile_key == "INVESTOR"):
            buy_conf = round(_clamp01(conf + 0.15 + tolerance * 0.1), 4)
            return REC_BUY, buy_conf, f"{ratio_label} is the lowest-risk ratio tier with strong issue signal."
        if tier in STRONG_TIERS and tolerance >= 0.55:
            return REC_WATCH, conf, f"{ratio_label} ratio variant is watchable with solid recommendation strength."
        return REC_AVOID, conf, f"{ratio_label} ratio variant deferred pending stronger signals."

    if vtype == "STORE_EXCLUSIVE":
        conf = round(_clamp01(0.42 + quantity_confidence * 0.25), 4)
        if weak_metadata:
            return REC_AVOID, conf, "Store exclusive with weak metadata; avoid inflated risk."
        if profile_key == "VARIANT_HUNTER" and tier in STRONG_TIERS:
            return REC_WATCH, conf, "Store exclusive variant is watchable for variant-focused collectors."
        return REC_WATCH, conf, f"Store exclusive {cover_label}; verify availability before buying."

    # UNKNOWN
    conf = round(_clamp01(0.38 + quantity_confidence * 0.30), 4)
    if quantity_confidence >= 0.75 and tolerance >= 0.65:
        return REC_WATCH, conf, f"Unclassified variant {cover_label}; watch with caution."
    return REC_AVOID, conf, f"Unclassified variant {cover_label}; insufficient confidence for purchase."


def _variants_for_issue(session: Session, *, issue_id: int) -> list[ReleaseVariant]:
    return list(
        session.exec(
            select(ReleaseVariant).where(ReleaseVariant.issue_id == issue_id).order_by(ReleaseVariant.id.asc())
        ).all()
    )


def _latest_quantity_by_release(session: Session, *, owner_user_id: int) -> dict[int, PurchaseQuantityRecommendation]:
    rows = session.exec(
        select(PurchaseQuantityRecommendation)
        .where(PurchaseQuantityRecommendation.owner_user_id == owner_user_id)
        .order_by(PurchaseQuantityRecommendation.created_at.desc(), PurchaseQuantityRecommendation.id.desc())
    ).all()
    latest: dict[int, PurchaseQuantityRecommendation] = {}
    for row in rows:
        if row.release_id not in latest:
            latest[row.release_id] = row
    return latest


def generate_variant_recommendations(session: Session, *, owner_user_id: int) -> list[VariantRecommendationResult]:
    profile = get_purchase_profile(session, owner_user_id=owner_user_id)
    preferences = get_purchase_preferences(session, owner_user_id=owner_user_id)
    qty_by_release = _latest_quantity_by_release(session, owner_user_id=owner_user_id)

    results: list[VariantRecommendationResult] = []
    for release_id in sorted(qty_by_release.keys()):
        qty_row: PurchaseQuantityRecommendation = qty_by_release[release_id]
        issue = session.get(ReleaseIssue, release_id)
        if issue is None or issue.owner_user_id != owner_user_id:
            continue
        series = session.get(ReleaseSeries, issue.series_id)
        series_name = series.series_name if series else ""
        variants = _variants_for_issue(session, issue_id=release_id)
        seen_cover_a = False

        for variant in variants:
            vtype, label = classify_purchase_variant_type(variant=variant)
            if vtype == "COVER_A":
                seen_cover_a = True
            combined = f"{variant.variant_name} {variant.variant_type}"
            ratio_denom = parse_ratio_denominator(text=combined, ratio_value=variant.ratio_value)
            weak_meta = not variant.variant_name.strip() or variant.variant_type.upper() == "UNKNOWN"
            rec, conf, rationale = evaluate_variant_recommendation(
                variant_type=vtype,
                cover_label=label,
                ratio_denominator=ratio_denom,
                quantity_recommended=int(qty_row.quantity_recommended),
                recommendation_tier=qty_row.recommendation_tier,
                quantity_confidence=float(qty_row.confidence_score),
                profile=profile,
                preferences=preferences,
                series_name=series_name,
                weak_metadata=weak_meta,
            )
            results.append(
                VariantRecommendationResult(
                    release_id=release_id,
                    variant_id=int(variant.id) if variant.id is not None else None,
                    cover_label=label,
                    variant_type=vtype,
                    recommendation=rec,
                    confidence_score=conf,
                    rationale=rationale,
                )
            )

        if not seen_cover_a:
            rec, conf, rationale = evaluate_variant_recommendation(
                variant_type="COVER_A",
                cover_label="Cover A",
                ratio_denominator=None,
                quantity_recommended=int(qty_row.quantity_recommended),
                recommendation_tier=qty_row.recommendation_tier,
                quantity_confidence=float(qty_row.confidence_score),
                profile=profile,
                preferences=preferences,
                series_name=series_name,
                weak_metadata=False,
            )
            results.append(
                VariantRecommendationResult(
                    release_id=release_id,
                    variant_id=None,
                    cover_label="Cover A",
                    variant_type="COVER_A",
                    recommendation=rec,
                    confidence_score=conf,
                    rationale=rationale,
                )
            )

    return results
