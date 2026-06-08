"""P90-03 advisor action prioritization (0–100)."""

from __future__ import annotations

from typing import Any

from app.services.advisor_evidence import dedupe_evidence_string, format_evidence_for_display
from app.services.advisor_proposal_dedupe import comic_label_from_title
from app.services.collector_alert_priority_service import PriorityInputs, compute_priority_score


def rank_advisor_actions(actions: list[dict[str, Any]], *, limit: int = 10) -> list[dict[str, Any]]:
    """Sort advisor action dicts by priority score and trim."""
    scored: list[tuple[float, dict[str, Any]]] = []
    for action in actions:
        alert_type = str(action.get("alert_type") or _category_to_alert_type(str(action.get("category", ""))))
        score = compute_priority_score(
            PriorityInputs(
                alert_type=alert_type,
                severity=str(action.get("severity") or "MEDIUM"),
                confidence=str(action.get("confidence") or "MEDIUM"),
                profit_signal=float(action.get("profit_signal") or 0.0),
                urgency_signal=float(action.get("urgency_signal") or 0.0),
                marketplace_activity=float(action.get("marketplace_activity") or 0.0),
                release_days=action.get("release_days"),
            )
        )
        enriched = dict(action)
        enriched["priority_score"] = score
        scored.append((score, enriched))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:limit]]


def rank_mixed_top_actions(actions: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    ranked = rank_advisor_actions(actions, limit=max(limit, len(actions)))
    out: list[dict[str, Any]] = []
    for idx, action in enumerate(ranked[:limit], start=1):
        category = str(action.get("category") or "ALERT").upper()
        comic = comic_label_from_title(str(action.get("comic") or action.get("title") or "Action"))
        reason_raw = dedupe_evidence_string(
            str(action.get("primary_reason") or action.get("reason") or action.get("summary") or "")
        )
        primary, _, _ = format_evidence_for_display(reason_raw)
        out.append(
            {
                "rank": idx,
                "category": category,
                "title": comic,
                "detail": primary or reason_raw,
                "priority_score": float(action.get("priority_score") or 0.0),
                "action_route": str(action.get("action_route") or "/automation-center"),
                "potential_upside": action.get("potential_upside"),
                "profit_potential": action.get("profit_potential"),
                "value_increase": action.get("value_increase"),
                "action_url": action.get("action_url"),
                "action_url_type": action.get("action_url_type"),
                "has_verified_listing": action.get("has_verified_listing"),
                "marketplace_name": action.get("marketplace_name"),
            }
        )
    return out


def _category_to_alert_type(category: str) -> str:
    mapping = {
        "BUY": "BUY_OPPORTUNITY",
        "SELL": "SELL_OPPORTUNITY",
        "GRADE": "GRADE_OPPORTUNITY",
        "WATCH": "COLLECTION_GAP",
    }
    return mapping.get(category.upper(), "PORTFOLIO_ACTION")
