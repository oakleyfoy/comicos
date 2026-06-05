"""P68-03 FMV calculation from normalized observations."""

from __future__ import annotations

from datetime import date, timedelta
from statistics import median

from app.models.market_pricing_engine import P68MarketPriceObservation


def _trimmed_mean(values: list[float], trim_frac: float = 0.1) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    k = int(len(xs) * trim_frac)
    if k * 2 >= len(xs):
        return sum(xs) / len(xs)
    trimmed = xs[k : len(xs) - k]
    return sum(trimmed) / len(trimmed) if trimmed else sum(xs) / len(xs)


def _remove_outliers_iqr(values: list[float]) -> list[float]:
    if len(values) < 4:
        return values
    xs = sorted(values)
    q1 = xs[len(xs) // 4]
    q3 = xs[(3 * len(xs)) // 4]
    iqr = max(q3 - q1, 0.01)
    lo = q1 - 1.5 * iqr
    hi = q3 + 1.5 * iqr
    return [v for v in values if lo <= v <= hi]


def _recency_weight(sale_date: date | None, *, today: date) -> float:
    if sale_date is None:
        return 0.7
    days = (today - sale_date).days
    if days <= 30:
        return 1.0
    if days <= 90:
        return 0.85
    if days <= 180:
        return 0.7
    return 0.5


def compute_fmv_bundle(
    observations: list[P68MarketPriceObservation],
    *,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    if not observations:
        return {
            "raw_fmv": None,
            "graded_fmv": None,
            "blended_fmv": None,
            "low_sale": None,
            "high_sale": None,
            "median_sale": None,
            "average_sale": None,
            "sales_count": 0,
            "liquidity_score": 0.0,
            "confidence": 0.0,
            "price_trend_30d": "STABLE",
            "price_trend_90d": "STABLE",
            "primary_provider": "",
        }

    def bucket(kind: str) -> list[float]:
        prices: list[float] = []
        weights: list[float] = []
        for o in observations:
            if o.raw_or_graded != kind:
                continue
            prices.append(float(o.total_price or o.sold_price))
            weights.append(_recency_weight(o.sale_date, today=today) * float(o.confidence or 0.5))
        cleaned = _remove_outliers_iqr(prices)
        return cleaned

    raw_prices = bucket("raw")
    graded_prices = bucket("graded")
    all_prices = _remove_outliers_iqr([float(o.total_price or o.sold_price) for o in observations])

    def fmv_from(prices: list[float]) -> float | None:
        if not prices:
            return None
        return round(_trimmed_mean(prices), 2)

    raw_fmv = fmv_from(raw_prices)
    graded_fmv = fmv_from(graded_prices)
    blended = fmv_from(all_prices)

    providers = {o.provider for o in observations}
    avg_conf = sum(float(o.confidence) for o in observations) / len(observations)
    conf = min(0.95, avg_conf * 0.4 + min(len(observations), 10) * 0.05)
    if "INTERNAL_SALE" in providers:
        conf = min(0.95, conf + 0.1)

    recent_30 = [o for o in observations if o.sale_date and (today - o.sale_date).days <= 30]
    recent_90 = [o for o in observations if o.sale_date and (today - o.sale_date).days <= 90]
    trend_30 = "RISING" if len(recent_30) >= 3 else "STABLE"
    trend_90 = "RISING" if len(recent_90) >= 5 else "STABLE"

    primary = "INTERNAL_SALE" if "INTERNAL_SALE" in providers else (next(iter(providers)) if providers else "")

    return {
        "raw_fmv": raw_fmv,
        "graded_fmv": graded_fmv,
        "blended_fmv": blended,
        "low_sale": round(min(all_prices), 2) if all_prices else None,
        "high_sale": round(max(all_prices), 2) if all_prices else None,
        "median_sale": round(median(all_prices), 2) if all_prices else None,
        "average_sale": round(sum(all_prices) / len(all_prices), 2) if all_prices else None,
        "sales_count": len(observations),
        "liquidity_score": round(min(100.0, len(observations) * 8.0 + len(recent_30) * 5.0), 2),
        "confidence": round(conf, 3),
        "price_trend_30d": trend_30,
        "price_trend_90d": trend_90,
        "primary_provider": primary,
    }
