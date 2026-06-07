"""P90 alert priority scoring (0–100)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

_CONF = {"HIGH": 1.0, "MEDIUM": 0.72, "LOW": 0.45}
_SEV = {"CRITICAL": 1.0, "HIGH": 0.85, "MEDIUM": 0.6, "LOW": 0.35}
_TYPE_WEIGHT = {
    "BUY_OPPORTUNITY": 1.0,
    "SELL_OPPORTUNITY": 1.05,
    "GRADE_OPPORTUNITY": 0.95,
    "COLLECTION_GAP": 0.9,
    "PRICE_DROP": 0.88,
    "RELEASE_ALERT": 0.82,
    "WATCHLIST_MATCH": 0.86,
    "PORTFOLIO_ACTION": 0.8,
}


@dataclass(frozen=True)
class PriorityInputs:
    alert_type: str
    severity: str
    confidence: str
    profit_signal: float = 0.0
    urgency_signal: float = 0.0
    marketplace_activity: float = 0.0
    release_days: int | None = None


def _clamp(score: float) -> float:
    return max(0.0, min(100.0, round(score, 2)))


def compute_priority_score(inputs: PriorityInputs) -> float:
    """Rank alerts: profit, confidence, urgency, release proximity, marketplace activity."""
    conf = _CONF.get((inputs.confidence or "MEDIUM").upper(), 0.72)
    sev = _SEV.get((inputs.severity or "MEDIUM").upper(), 0.6)
    type_w = _TYPE_WEIGHT.get(inputs.alert_type, 0.75)
    profit = min(40.0, max(0.0, inputs.profit_signal))
    urgency = min(25.0, max(0.0, inputs.urgency_signal))
    activity = min(10.0, max(0.0, inputs.marketplace_activity))
    release_boost = 0.0
    if inputs.release_days is not None:
        if inputs.release_days <= 3:
            release_boost = 15.0
        elif inputs.release_days <= 7:
            release_boost = 10.0
        elif inputs.release_days <= 14:
            release_boost = 5.0
    base = 18.0 * type_w + 22.0 * conf + 12.0 * sev
    return _clamp(base + profit + urgency + activity + release_boost)


def profit_signal_from_discount(discount_pct: float | None) -> float:
    if discount_pct is None or discount_pct <= 0:
        return 0.0
    return min(40.0, discount_pct * 0.8)


def profit_signal_from_amount(amount: float | None) -> float:
    if amount is None or amount <= 0:
        return 0.0
    return min(40.0, amount / 25.0)


def urgency_from_age_days(days: int | None) -> float:
    if days is None:
        return 0.0
    if days >= 30:
        return 20.0
    if days >= 14:
        return 12.0
    if days >= 7:
        return 6.0
    return 0.0


def release_days_until(release_at: datetime | None) -> int | None:
    if release_at is None:
        return None
    now = datetime.now(timezone.utc)
    if release_at.tzinfo is None:
        release_at = release_at.replace(tzinfo=timezone.utc)
    delta = (release_at.date() - now.date()).days
    return delta
