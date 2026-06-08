"""P90-08 Buy recommendation trust, classification, and evidence sanitization."""

from __future__ import annotations

from typing import Any

from sqlmodel import Session

from app.models.p82_p84_collector_expansion import MarketplaceAcquisitionOpportunity
from app.services.advisor_evidence import dedupe_evidence_string, format_evidence_for_display
from app.services.p82_listing_url_safety import is_safe_marketplace_listing_url

RECOMMENDATION_TYPE_LABELS = {
    "VERIFIED_DEAL": "Verified Deal",
    "RECOMMENDED_BUY": "Recommended Buy",
    "WATCHLIST_BUY": "Watch",
}

PRICE_SOURCE_LABELS = {
    "VERIFIED_LISTING": "Verified marketplace listing",
    "P82_OPPORTUNITY": "Recommendation estimate",
    "MARKET_PRICE_SNAPSHOT": "Market pricing snapshot",
    "FMV_ESTIMATE": "FMV estimate",
    "UNKNOWN": "Unknown",
}

_STRONG_BUY_RECS = frozenset({"STRONG_BUY", "GOOD_BUY", "SPEC_BUY", "UNDERVALUED"})

_FALSE_VERIFIED_PHRASES = (
    "verified listing",
    "verified marketplace listing",
    "live listing",
    "active listing",
)


def _verified_listing_is_actionable(verified: dict[str, Any] | None) -> bool:
    if not verified or not verified.get("listing_url"):
        return False
    url = str(verified["listing_url"])
    item_id = str(verified.get("item_id") or verified.get("external_listing_id") or "")
    if not is_safe_marketplace_listing_url(listing_url=url, external_listing_id=item_id):
        return False
    price = float(verified.get("total_cost") or verified.get("price") or 0)
    return price > 0


def classify_buy_recommendation(
    *,
    has_verified_listing: bool,
    best_verified_listing: dict[str, Any] | None,
    recommendation: str = "",
    alert_type: str = "",
) -> str:
    if has_verified_listing and _verified_listing_is_actionable(best_verified_listing):
        return "VERIFIED_DEAL"
    rec = (recommendation or "").strip().upper()
    at = (alert_type or "").strip().upper()
    if rec in _STRONG_BUY_RECS or at in {"BUY_OPPORTUNITY", "PRICE_DROP"}:
        return "RECOMMENDED_BUY"
    if rec == "WATCH" or at in {"WATCHLIST_MATCH", "COLLECTION_GAP"}:
        return "WATCHLIST_BUY"
    if rec:
        return "RECOMMENDED_BUY"
    return "WATCHLIST_BUY"


def resolve_price_source(
    *,
    recommendation_type: str,
    has_verified_listing: bool,
) -> tuple[str, str]:
    if recommendation_type == "VERIFIED_DEAL" and has_verified_listing:
        return "VERIFIED_LISTING", PRICE_SOURCE_LABELS["VERIFIED_LISTING"]
    if recommendation_type in {"RECOMMENDED_BUY", "WATCHLIST_BUY"}:
        return "P82_OPPORTUNITY", PRICE_SOURCE_LABELS["P82_OPPORTUNITY"]
    return "UNKNOWN", PRICE_SOURCE_LABELS["UNKNOWN"]


def sanitize_buy_evidence(
    *,
    reason: str,
    primary_reason: str,
    supporting_signals: list[str],
    has_verified_listing: bool,
) -> tuple[str, str, list[str]]:
    """Remove false verified-listing phrases when no verified listing exists."""
    if has_verified_listing:
        merged = dedupe_evidence_string(reason or primary_reason)
        primary, supporting, _ = format_evidence_for_display(merged)
        if supporting_signals:
            from app.services.advisor_evidence import dedupe_evidence_segments as _dedupe

            supporting = _dedupe([*supporting_signals, *supporting])[:3]
        return merged, primary or merged, supporting[:3]

    def clean_segment(seg: str) -> str | None:
        lower = seg.lower().strip()
        if not lower:
            return None
        if "no verified" in lower or "recommendation only" in lower:
            return seg.strip()
        for phrase in _FALSE_VERIFIED_PHRASES:
            if phrase in lower and "no verified" not in lower:
                return None
        if "estimated savings" in lower:
            return None
        return seg.strip()

    from app.services.advisor_evidence import dedupe_evidence_segments, split_evidence_segments

    segments = dedupe_evidence_segments(
        split_evidence_segments(reason or primary_reason)
        + list(supporting_signals or [])
    )
    kept = [s for s in (clean_segment(x) for x in segments) if s]
    kept = dedupe_evidence_segments(kept)
    if not kept:
        kept = ["Strong buy signal based on collection and value data"]
    merged = " · ".join(kept)
    primary, supporting, _ = format_evidence_for_display(merged)
    return merged, primary or kept[0], supporting[:3]


def dedupe_evidence_segments(a: list[str], b: list[str] | None = None) -> list[str]:
    from app.services.advisor_evidence import dedupe_evidence_segments as _dedupe

    return _dedupe([*(a or []), *(b or [])])


def _explanation_copy(
    *,
    recommendation_type: str,
    reasons: list[str],
    discount: float,
    ownership: str,
) -> dict[str, str]:
    gap = any("gap" in (r or "").lower() for r in reasons) or ownership == "GAP"
    why_book = "Strong score and collection relevance."
    if gap:
        why_book = "This title fills a gap in your collection."
    why_now = (
        "Verified listing price is below estimated value."
        if recommendation_type == "VERIFIED_DEAL"
        else "Estimated value is above the target buy price."
    )
    why_me = "Matched to your collection profile and buy signals." if not gap else "You are missing this issue in your collection."
    if recommendation_type == "VERIFIED_DEAL":
        action = "Buy now if the listing condition matches your collecting goals."
    elif recommendation_type == "WATCHLIST_BUY":
        action = "Add to your watchlist and search when a verified listing appears."
    else:
        action = "Review the opportunity and search marketplaces for a verified listing."
    return {
        "why_this_book": why_book,
        "why_now": why_now,
        "why_for_me": why_me,
        "recommended_action": action,
    }


def trust_fields_for_opportunity(
    row: MarketplaceAcquisitionOpportunity,
    *,
    summary: dict[str, Any],
    has_verified_listing: bool,
) -> dict[str, Any]:
    verified = summary.get("best_verified_listing")
    verified_dict = verified if isinstance(verified, dict) else None
    rec_type = classify_buy_recommendation(
        has_verified_listing=has_verified_listing and _verified_listing_is_actionable(verified_dict),
        best_verified_listing=verified_dict,
        recommendation=str(row.recommendation or ""),
    )
    is_verified = rec_type == "VERIFIED_DEAL"
    price_source, price_source_label = resolve_price_source(
        recommendation_type=rec_type,
        has_verified_listing=is_verified,
    )
    fmv = float(row.estimated_fmv or 0)
    ask = float(row.asking_price or 0)
    discount = float(row.discount_to_fmv or 0)
    if fmv > 0 and ask > 0 and discount <= 0:
        discount = round((fmv - ask) / fmv * 100.0, 1)

    current_price: float | None = None
    estimated_savings: float | None = None
    target_buy_price = round(ask, 2) if ask > 0 else None
    if is_verified and verified_dict:
        current_price = round(float(verified_dict.get("total_cost") or verified_dict.get("price") or 0), 2)
        if fmv > 0 and current_price:
            estimated_savings = round(max(0.0, fmv - current_price), 2)
    potential_upside_amount = round(max(0.0, fmv - ask), 2) if fmv and ask else None
    potential_upside_percent = round(discount, 0) if discount else None

    reasons = list(row.reasons_json or [])
    explanations = _explanation_copy(
        recommendation_type=rec_type,
        reasons=reasons,
        discount=discount,
        ownership=str(row.ownership_status or ""),
    )
    return {
        "recommendation_type": rec_type,
        "recommendation_type_label": RECOMMENDATION_TYPE_LABELS.get(rec_type, rec_type),
        "is_verified_deal": is_verified,
        "is_recommendation_only": not is_verified,
        "price_source": price_source,
        "price_source_label": price_source_label,
        "target_buy_price": target_buy_price,
        "estimated_value": round(fmv, 2) if fmv else None,
        "current_price": current_price,
        "estimated_savings": estimated_savings if is_verified else None,
        "potential_upside_amount": potential_upside_amount if not is_verified else None,
        "potential_upside_percent": potential_upside_percent if not is_verified else None,
        **explanations,
    }


def apply_buy_trust_to_action(
    session: Session,
    *,
    owner_user_id: int,
    item: dict[str, Any],
) -> None:
    """Mutates advisor BUY action dict with trust fields and clean evidence."""
    entity_id = int(item.get("entity_id") or 0)
    entity_type = str(item.get("entity_type") or "")
    row: MarketplaceAcquisitionOpportunity | None = None
    summary: dict[str, Any] = {}
    if entity_type == "marketplace_acquisition" and entity_id > 0:
        row = session.get(MarketplaceAcquisitionOpportunity, entity_id)
        if row and row.owner_user_id == owner_user_id:
            from app.services.marketplace.marketplace_listing_service import listing_summary_for_opportunity

            summary = listing_summary_for_opportunity(
                session,
                owner_user_id=owner_user_id,
                opportunity_id=entity_id,
            )

    has_verified = bool(item.get("has_verified_listing"))
    verified_raw = item.get("best_verified_listing") or summary.get("best_verified_listing")
    verified_dict = verified_raw if isinstance(verified_raw, dict) else None
    if verified_dict and not _verified_listing_is_actionable(verified_dict):
        has_verified = False
        item["has_verified_listing"] = False

    rec_type = classify_buy_recommendation(
        has_verified_listing=has_verified,
        best_verified_listing=verified_dict,
        recommendation=str(row.recommendation if row else ""),
        alert_type=str(item.get("alert_type") or ""),
    )
    is_verified = rec_type == "VERIFIED_DEAL"
    item["has_verified_listing"] = is_verified
    item["recommendation_type"] = rec_type
    item["recommendation_type_label"] = RECOMMENDATION_TYPE_LABELS.get(rec_type, rec_type)
    item["is_verified_deal"] = is_verified
    item["is_recommendation_only"] = not is_verified

    price_source, price_source_label = resolve_price_source(
        recommendation_type=rec_type,
        has_verified_listing=is_verified,
    )
    item["price_source"] = price_source
    item["price_source_label"] = price_source_label

    fmv = float(row.estimated_fmv or 0) if row else 0.0
    ask = float(row.asking_price or 0) if row else 0.0
    discount = float(row.discount_to_fmv or 0) if row else 0.0
    if row:
        trust = trust_fields_for_opportunity(row, summary=summary, has_verified_listing=is_verified)
        item.update({k: trust.get(k) for k in trust if k not in item or item.get(k) is None})
        item.update(
            {
                "target_buy_price": trust.get("target_buy_price"),
                "estimated_value": trust.get("estimated_value"),
                "current_price": trust.get("current_price"),
                "estimated_savings": trust.get("estimated_savings"),
                "potential_upside_amount": trust.get("potential_upside_amount"),
                "potential_upside_percent": trust.get("potential_upside_percent"),
                "why_this_book": trust.get("why_this_book"),
                "why_now": trust.get("why_now"),
                "why_for_me": trust.get("why_for_me"),
                "recommended_action": trust.get("recommended_action"),
            }
        )
        if is_verified and trust.get("estimated_savings") is not None:
            item["potential_upside"] = trust["estimated_savings"]
        elif trust.get("potential_upside_amount") is not None:
            item["potential_upside"] = trust["potential_upside_amount"]

    merged, primary, supporting = sanitize_buy_evidence(
        reason=str(item.get("reason") or ""),
        primary_reason=str(item.get("primary_reason") or ""),
        supporting_signals=list(item.get("supporting_signals") or []),
        has_verified_listing=is_verified,
    )
    if is_verified:
        mp = item.get("marketplace_name") or "marketplace"
        primary = f"{discount:.0f}% below estimated value" if discount else primary
        supporting = dedupe_evidence_segments(
            [f"Verified marketplace listing on {mp}", *supporting]
        )[:3]
    else:
        primary = "Strong buy signal based on collection and value data"
        supporting = dedupe_evidence_segments(
            [
                f"{discount:.0f}% target discount" if discount else "",
                *[r for r in (row.reasons_json or []) if row][:2],
            ]
        )[:3]

    item["reason"] = dedupe_evidence_string(" · ".join([primary, *supporting]))
    item["primary_reason"] = primary
    item["supporting_signals"] = supporting
    _, _, hidden = format_evidence_for_display(item["reason"])
    item["hidden_signal_count"] = hidden
