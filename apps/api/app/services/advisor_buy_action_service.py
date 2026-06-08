"""Resolve direct buy action URLs for Collector Advisor (P90-07)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from sqlmodel import Session

from app.services.advisor_evidence import dedupe_evidence_string, format_evidence_for_display
from app.services.marketplace.marketplace_listing_service import listing_summary_for_opportunity


def _marketplace_search_route(title: str) -> str:
    q = quote(title.strip())
    return f"/buy-opportunities?search={q}" if q else "/buy-opportunities"


def resolve_buy_action_target(
    session: Session,
    *,
    owner_user_id: int,
    entity_type: str,
    entity_id: int,
    comic_title: str,
    fallback_route: str,
) -> dict[str, Any]:
    if entity_type == "marketplace_acquisition" and entity_id > 0:
        summary = listing_summary_for_opportunity(
            session,
            owner_user_id=owner_user_id,
            opportunity_id=entity_id,
        )
        verified = summary.get("best_verified_listing")
        if isinstance(verified, dict) and verified.get("listing_url"):
            return {
                "has_verified_listing": True,
                "verified_listing_count": int(summary.get("verified_listing_count") or 0),
                "action_url": str(verified["listing_url"]),
                "action_url_type": "MARKETPLACE_LISTING",
                "best_verified_listing": verified,
                "best_total_cost": summary.get("best_total_cost"),
                "marketplace_name": verified.get("marketplace_name") or verified.get("marketplace"),
            }
        return {
            "has_verified_listing": False,
            "verified_listing_count": int(summary.get("verified_listing_count") or 0),
            "action_url": f"/marketplace-opportunity/{entity_id}",
            "action_url_type": "OPPORTUNITY_DETAIL",
            "best_verified_listing": None,
            "best_total_cost": None,
            "marketplace_name": None,
        }

    title = (comic_title or "").strip()
    if title:
        return {
            "has_verified_listing": False,
            "verified_listing_count": 0,
            "action_url": _marketplace_search_route(title),
            "action_url_type": "MARKETPLACE_SEARCH",
            "best_verified_listing": None,
            "best_total_cost": None,
            "marketplace_name": None,
        }
    return {
        "has_verified_listing": False,
        "verified_listing_count": 0,
        "action_url": fallback_route or "/buy-opportunities",
        "action_url_type": "OPPORTUNITY_DETAIL",
        "best_verified_listing": None,
        "best_total_cost": None,
        "marketplace_name": None,
    }


def enrich_buy_action_dict(
    session: Session,
    *,
    owner_user_id: int,
    item: dict[str, Any],
) -> None:
    target = resolve_buy_action_target(
        session,
        owner_user_id=owner_user_id,
        entity_type=str(item.get("entity_type") or ""),
        entity_id=int(item.get("entity_id") or 0),
        comic_title=str(item.get("comic") or item.get("title") or ""),
        fallback_route=str(item.get("action_route") or ""),
    )
    item.update(target)
    if target["has_verified_listing"]:
        mp = target.get("marketplace_name") or "marketplace"
        savings = item.get("potential_upside")
        parts = [str(item.get("primary_reason") or item.get("reason") or "")]
        parts.append(f"Verified marketplace listing on {mp}")
        if savings:
            parts.append(f"Estimated savings ${float(savings):.0f}")
        merged = dedupe_evidence_string(" · ".join(p for p in parts if p))
        primary, supporting, hidden = format_evidence_for_display(merged)
        item["reason"] = merged
        item["primary_reason"] = primary or merged
        item["supporting_signals"] = supporting
        item["hidden_signal_count"] = hidden
    else:
        note = "Recommendation only · no verified listing yet"
        merged = dedupe_evidence_string(f"{item.get('primary_reason') or item.get('reason') or ''} · {note}")
        primary, supporting, hidden = format_evidence_for_display(merged)
        item["reason"] = merged
        item["primary_reason"] = primary or merged
        item["supporting_signals"] = supporting
        item["hidden_signal_count"] = hidden


def enrich_buy_action_dicts(session: Session, *, owner_user_id: int, items: list[dict[str, Any]]) -> None:
    for item in items:
        if str(item.get("category") or "").upper() != "BUY":
            continue
        enrich_buy_action_dict(session, owner_user_id=owner_user_id, item=item)
