"""P89-02 fair market price estimation."""

from __future__ import annotations


def _trimmed_mean(values: list[float], trim: float = 0.15) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    cut = int(n * trim)
    core = sorted_vals[cut : n - cut] if n - 2 * cut >= 1 else sorted_vals
    return sum(core) / len(core)


def compute_market_price(
    *,
    active_prices: list[float],
    listing_confidence_scores: list[float] | None = None,
) -> float:
    if not active_prices:
        return 0.0
    base = _trimmed_mean(active_prices)
    if listing_confidence_scores:
        weights = [max(0.4, min(1.0, s)) for s in listing_confidence_scores[: len(active_prices)]]
        while len(weights) < len(active_prices):
            weights.append(0.75)
        weighted = sum(p * w for p, w in zip(active_prices, weights, strict=False)) / sum(weights)
        base = base * 0.65 + weighted * 0.35
    return round(max(base, 0.01), 2)


def _confidence_score(label: str) -> float:
    return {"HIGH": 1.0, "MEDIUM": 0.75, "LOW": 0.5}.get(label.upper(), 0.6)
