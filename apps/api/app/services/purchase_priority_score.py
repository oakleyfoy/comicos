"""P74-02 deterministic purchase priority scoring (0–100; advisory only)."""

from __future__ import annotations

P74_ACTION_MUST_BUY = "MUST_BUY"
P74_ACTION_BUY = "BUY"
P74_ACTION_WATCH = "WATCH"
P74_ACTION_PASS = "PASS"


def _clamp_score(value: float) -> int:
    return int(max(0, min(100, round(value))))


def compute_purchase_priority_score(
    *,
    recommendation_score: float,
    demand_score: float,
    is_number_one: bool,
    is_key_signal: bool,
    variant_count: int,
    has_ratio_variant: bool,
    watchlist_match: bool,
    market_signal_strength: float,
    owned_quantity: int,
    ordered_quantity: int,
    foc_days: int | None,
) -> tuple[int, str]:
    score = 40.0
    score += recommendation_score * 0.35
    score += demand_score * 0.25
    if is_number_one:
        score += 12.0
    if is_key_signal:
        score += 8.0
    if variant_count >= 2:
        score += 4.0
    if has_ratio_variant:
        score += 6.0
    if watchlist_match:
        score += 10.0
    score += min(8.0, market_signal_strength * 0.08)
    if foc_days is not None and 0 <= foc_days <= 7:
        score += 8.0
    elif foc_days is not None and 0 <= foc_days <= 14:
        score += 4.0
    overbought = owned_quantity + ordered_quantity
    if overbought >= 4:
        score -= 15.0
    elif overbought >= 2:
        score -= 6.0
    # budget placeholder — neutral
    priority = _clamp_score(score)
    if priority >= 85:
        return priority, P74_ACTION_MUST_BUY
    if priority >= 70:
        return priority, P74_ACTION_BUY
    if priority >= 50:
        return priority, P74_ACTION_WATCH
    return priority, P74_ACTION_PASS
