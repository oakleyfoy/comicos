"""Map LoCG external catalog rows → Recommendation Decision Engine signal inputs.

This module is the integration contract for External Catalog Intelligence.
It does not change ranking weights or compute final BUY/WATCH/PASS today; it
materializes structured decision inputs the RDE can consume once wired.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

from app.models.external_catalog import (
    ExternalCatalogCreator,
    ExternalCatalogIssue,
    ExternalCatalogVariant,
)
from app.services.foc_dates import days_until_foc, foc_status_bucket
from app.services.external_catalog.importance_signals import detect_importance_signals

# Documented contract: extracted LoCG field → future RDE signal family.
FIELD_TO_DECISION_SIGNAL: dict[str, str] = {
    "creators": "creator_significance",
    "creator_credits": "creator_significance",
    "publisher": "audience_market_context",
    "imprint": "audience_market_context",
    "universe": "audience_market_context",
    "description": "narrative_catalyst_detection",
    "story_summary": "narrative_catalyst_detection",
    "issue_number": "issue_position_signals",
    "title": "issue_position_signals",
    "variants": "cover_recommendation_and_ratio_risk",
    "variant_count": "cover_recommendation_and_ratio_risk",
    "pull_count": "demand_score",
    "want_count": "demand_score",
    "foc_date": "preorder_urgency",
    "release_date": "buying_window",
    "price": "risk_reward_and_roi",
    "cover_image_url": "cover_review_and_selection",
    "thumbnail_url": "cover_review_and_selection",
    "high_resolution_image_url": "cover_review_and_selection",
    "importance_signals_json": "narrative_catalyst_detection",
    "is_first_issue": "issue_position_signals",
    "is_milestone_issue": "issue_position_signals",
}


@dataclass
class VariantDecisionIntel:
    cover_label: str | None
    variant_name: str | None
    artist: str | None
    ratio_value: int | None
    ratio_risk_tier: str
    cover_recommendation_hint: str
    image_url: str | None
    variant_detail_url: str | None
    price: float | None


@dataclass
class ExternalCatalogDecisionSignals:
    """Structured inputs for Recommendation Decision Engine (preview / future merge)."""

    creator_significance_score: float
    creator_credits: list[dict[str, str]]
    audience_market_context: dict[str, str | None]
    narrative_catalysts: list[str]
    narrative_matched_phrases: dict[str, str]
    issue_position: dict[str, Any]
    variant_intel: list[VariantDecisionIntel]
    demand_score: float
    demand_components: dict[str, int | None]
    foc_urgency: str | None
    foc_days_remaining: int | None
    buying_window: str | None
    release_days_until: int | None
    price_usd: float | None
    risk_reward_hint: str
    cover_review_assets: dict[str, str | None]
    signal_field_map: dict[str, str] = field(default_factory=lambda: dict(FIELD_TO_DECISION_SIGNAL))
    source_system: str = "EXTERNAL_CATALOG_LOCG"


def _demand_score(pull: int | None, want: int | None) -> tuple[float, dict[str, int | None]]:
    pull_v = pull or 0
    want_v = want or 0
    # Deterministic 0–100 preview; RDE may replace with calibrated model later.
    raw = min(100.0, (pull_v * 0.06) + (want_v * 0.04))
    if pull_v >= 500 or want_v >= 800:
        raw = min(100.0, raw + 12.0)
    return round(raw, 2), {"pull_count": pull, "want_count": want}


def _creator_significance(creators: list[dict[str, Any]], *, demand: float) -> tuple[float, list[dict[str, str]]]:
    credits: list[dict[str, str]] = []
    score = 40.0
    for row in creators:
        name = (row.get("creator_name") or "").strip()
        role_display = (row.get("role_display") or row.get("role") or "").strip()
        if not name:
            continue
        credits.append({"creator_name": name, "role": role_display})
        role_u = role_display.upper()
        if "WRITER" in role_u:
            score += 8.0
        if "ARTIST" in role_u or "COVER" in role_u:
            score += 6.0
    score = min(100.0, score + demand * 0.15)
    return round(score, 2), credits


def _ratio_risk_tier(ratio: int | None) -> str:
    if ratio is None:
        return "STANDARD"
    if ratio >= 50:
        return "HIGH"
    if ratio >= 25:
        return "MEDIUM"
    return "LOW"


def _cover_hint(ratio: int | None, cover_label: str | None) -> str:
    if ratio and ratio >= 25:
        return "RATIO_SPEC_OPTION"
    if cover_label and cover_label.upper() != "A":
        return "ALT_COVER_OPTION"
    return "PRIMARY_COVER"


def _buying_window(release_date: date | None, *, today: date) -> tuple[str | None, int | None]:
    if release_date is None:
        return None, None
    days = (release_date - today).days
    if days < 0:
        return "RELEASED", days
    if days <= 14:
        return "IMMEDIATE", days
    if days <= 45:
        return "NEAR_TERM", days
    if days <= 90:
        return "FORWARD_WINDOW", days
    return "DISTANT", days


def _risk_reward_hint(price: float | None, *, demand: float, ratio_max: int | None) -> str:
    if price is None:
        return "UNKNOWN_COVER_PRICE"
    if price >= 6.0 and (ratio_max or 0) >= 25:
        return "HIGH_COVER_PRICE_RATIO_RISK"
    if demand >= 70.0 and price <= 5.0:
        return "FAVORABLE_DEMAND_TO_PRICE"
    if price <= 4.0:
        return "STANDARD_RISK"
    return "ELEVATED_COVER_PRICE"


def build_decision_signals_from_normalized(
    *,
    norm_like: Any,
    creators: list[dict[str, Any]],
    variants: list[dict[str, Any]],
    today: date | None = None,
) -> dict[str, Any]:
    """Build RDE-oriented signal bundle from normalized ingest payload."""
    ref = today or date.today()
    demand, demand_parts = _demand_score(
        getattr(norm_like, "pull_count", None),
        getattr(norm_like, "want_count", None),
    )
    creator_score, creator_credits = _creator_significance(creators, demand=demand)

    importance = getattr(norm_like, "importance_signals_json", None) or detect_importance_signals(
        title=getattr(norm_like, "title", ""),
        series_name=getattr(norm_like, "series_name", ""),
        issue_number=getattr(norm_like, "issue_number", None),
        description=getattr(norm_like, "description", None),
        story_summary=getattr(norm_like, "story_summary", None),
        imprint=getattr(norm_like, "imprint", None),
        universe=getattr(norm_like, "universe", None),
    )

    foc_date = getattr(norm_like, "foc_date", None)
    release_date = getattr(norm_like, "release_date", None)
    foc_days = days_until_foc(foc_date, today=ref) if foc_date else None
    buying_window, release_days = _buying_window(release_date, today=ref)

    variant_intel: list[VariantDecisionIntel] = []
    ratio_max: int | None = None
    for v in variants:
        ratio = v.get("ratio_value")
        if ratio is not None:
            ratio_max = max(ratio_max or 0, int(ratio))
        variant_intel.append(
            VariantDecisionIntel(
                cover_label=v.get("cover_label"),
                variant_name=v.get("variant_name"),
                artist=v.get("artist"),
                ratio_value=ratio,
                ratio_risk_tier=_ratio_risk_tier(ratio),
                cover_recommendation_hint=_cover_hint(ratio, v.get("cover_label")),
                image_url=v.get("image_url"),
                variant_detail_url=v.get("variant_detail_url"),
                price=v.get("price"),
            )
        )

    price = getattr(norm_like, "price", None)
    bundle = ExternalCatalogDecisionSignals(
        creator_significance_score=creator_score,
        creator_credits=creator_credits,
        audience_market_context={
            "publisher": getattr(norm_like, "publisher", None),
            "imprint": getattr(norm_like, "imprint", None),
            "universe": getattr(norm_like, "universe", None),
        },
        narrative_catalysts=list(importance.get("signals") or []),
        narrative_matched_phrases=dict(importance.get("matched_phrases") or {}),
        issue_position={
            "is_first_issue": bool(importance.get("first_issue")),
            "is_milestone_issue": bool(importance.get("is_milestone_issue")),
            "milestone_issue_number": importance.get("milestone_issue_number"),
        },
        variant_intel=variant_intel,
        demand_score=demand,
        demand_components=demand_parts,
        foc_urgency=foc_status_bucket(foc_date, today=ref) if foc_date else None,
        foc_days_remaining=foc_days,
        buying_window=buying_window,
        release_days_until=release_days,
        price_usd=price,
        risk_reward_hint=_risk_reward_hint(price, demand=demand, ratio_max=ratio_max),
        cover_review_assets={
            "cover_image_url": getattr(norm_like, "cover_image_url", None),
            "thumbnail_url": getattr(norm_like, "thumbnail_url", None),
            "high_resolution_image_url": getattr(norm_like, "high_resolution_image_url", None),
        },
    )
    payload = asdict(bundle)
    payload["variant_intel"] = [asdict(v) for v in variant_intel]
    return payload


def build_decision_signals_for_issue_row(
    issue: ExternalCatalogIssue,
    *,
    variants: list[ExternalCatalogVariant],
    creators: list[ExternalCatalogCreator],
    today: date | None = None,
) -> dict[str, Any]:
    creator_dicts = [
        {
            "creator_name": c.creator_name,
            "role": c.role,
            "role_display": c.role_display,
        }
        for c in creators
    ]
    variant_dicts = [
        {
            "cover_label": v.cover_label,
            "variant_name": v.variant_name,
            "artist": v.artist,
            "ratio_value": v.ratio_value,
            "price": v.price,
            "image_url": v.image_url,
            "variant_detail_url": v.variant_detail_url,
        }
        for v in variants
    ]
    return build_decision_signals_from_normalized(
        norm_like=issue,
        creators=creator_dicts,
        variants=variant_dicts,
        today=today,
    )
