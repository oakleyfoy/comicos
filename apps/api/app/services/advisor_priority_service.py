"""P90-03 advisor action prioritization (0–100)."""

from __future__ import annotations

from typing import Any

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
        comic = str(action.get("comic") or action.get("title") or "Action")
        out.append(
            {
                "rank": idx,
                "category": category,
                "title": f"{category.title()} {comic}".replace("Buy buy", "Buy").replace("Sell sell", "Sell"),
                "detail": str(action.get("reason") or action.get("summary") or ""),
                "priority_score": float(action.get("priority_score") or 0.0),
                "action_route": str(action.get("action_route") or "/automation-center"),
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
