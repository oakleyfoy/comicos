"""Deterministic P71 sell/listing scoring (recommendations only)."""

from __future__ import annotations

from app.models.sell_intelligence_platform import (
    EXIT_GRADE_THEN_SELL,
    EXIT_HOLD,
    EXIT_SELL_NOW,
    EXIT_TRIM,
    EXIT_WATCH,
    LISTING_AUCTION,
    LISTING_BIN,
    LISTING_EITHER,
    LIQ_HIGH,
    LIQ_LOW,
    LIQ_MEDIUM,
)
from app.services.p71_sell_context import SellIntelCopyContext


def _has_market_inputs(ctx: SellIntelCopyContext) -> bool:
    return any(
        [
            ctx.market_weighted_median_sale > 0,
            ctx.market_recent_median_30d > 0,
            ctx.market_recent_median_90d > 0,
            ctx.market_sales_velocity > 0,
            ctx.market_liquidity_score > 0,
            bool(ctx.market_provider_breakdown_json),
            bool(ctx.market_primary_provider),
        ]
    )


def score_exit(ctx: SellIntelCopyContext) -> tuple[str, float, float, str, list[str], dict]:
    score = 0.0
    secondary: list[str] = []
    has_market = _has_market_inputs(ctx)
    effective_liquidity_score = ctx.market_liquidity_score if has_market and ctx.market_liquidity_score > 0 else ctx.liquidity_score
    effective_velocity = ctx.market_sales_velocity if has_market and ctx.market_sales_velocity > 0 else min(10.0, float(ctx.sales_count))
    effective_timing_signal = ctx.market_timing_signal
    if not has_market:
        if effective_liquidity_score >= 60 and ctx.price_trend == "RISING" and ctx.fmv_confidence >= 0.7:
            effective_timing_signal = "SELL_NOW"
        elif effective_liquidity_score >= 45 and ctx.price_trend in {"RISING", "STABLE"}:
            effective_timing_signal = "SELL_SOON"
    market_strength = min(
        100.0,
        max(
            0.0,
            (effective_liquidity_score * 0.55)
            + (min(10.0, max(0.0, effective_velocity)) * 6.0)
            + (ctx.fmv_confidence * 22.0)
            + (8.0 if ctx.market_primary_provider == "EBAY_SOLD" else 0.0)
            + (4.0 if effective_timing_signal == "SELL_NOW" else 0.0)
            + (2.0 if effective_timing_signal == "SELL_SOON" else 0.0),
        ),
    )
    factors: dict = {
        "unrealized_gain_pct": round(ctx.unrealized_gain_pct, 2),
        "fmv_confidence": round(ctx.fmv_confidence, 3),
        "liquidity_score": round(ctx.liquidity_score, 2),
        "quantity": ctx.quantity,
        "price_trend": ctx.price_trend,
        "portfolio_share_pct": round(ctx.portfolio_share_pct, 2),
        "market_weighted_median_sale": round(ctx.market_weighted_median_sale, 2),
        "market_recent_median_30d": round(ctx.market_recent_median_30d, 2),
        "market_recent_median_90d": round(ctx.market_recent_median_90d, 2),
        "market_sales_velocity": round(effective_velocity, 3),
        "market_liquidity_band": ctx.market_liquidity_band,
        "market_timing_signal": effective_timing_signal,
        "market_timing_reason": ctx.market_timing_reason,
        "market_provider_breakdown": ctx.market_provider_breakdown_json,
        "market_primary_provider": ctx.market_primary_provider,
        "market_strength": round(market_strength, 2),
    }

    if ctx.unrealized_gain_pct >= 35:
        score += 32
        secondary.append("strong_unrealized_gain")
    elif ctx.unrealized_gain_pct >= 12:
        score += 18
        secondary.append("moderate_unrealized_gain")

    if ctx.price_trend == "RISING":
        score += 12
        secondary.append("positive_velocity_trend")
    elif ctx.price_trend == "FALLING":
        score += 8
        secondary.append("protect_gain_before_softening")

    if ctx.portfolio_share_pct >= 10:
        score += 14
        secondary.append("portfolio_concentration")

    if ctx.quantity >= 2:
        score += 10
        secondary.append("quantity_trim_candidate")

    if ctx.liquidity_score >= 55:
        score += 12
        secondary.append("liquid_market")
    elif ctx.liquidity_score < 25:
        score -= 8
        secondary.append("thin_market")

    if ctx.fmv_confidence >= 0.65:
        score += 8
    elif ctx.fmv_confidence < 0.4:
        score -= 6
        secondary.append("low_market_confidence")

    if ctx.recommendation_hit_rate >= 60:
        score += 5
        secondary.append("recommendation_track_record_support")
    if effective_timing_signal == "SELL_NOW":
        score += 10
        secondary.append("timing_window_open")
    elif effective_timing_signal == "SELL_SOON":
        score += 6
        secondary.append("timing_window_favorable")
    elif effective_timing_signal == "ACCUMULATE":
        score -= 5
        secondary.append("market_accumulation_signal")
    if market_strength >= 70:
        score += 10
        secondary.append("ebay_market_strength")
    elif market_strength <= 30:
        score -= 8
        secondary.append("weak_market_depth")

    action = EXIT_HOLD
    primary = "hold_for_better_signal"
    if ctx.grade_status == "raw" and ctx.estimated_fmv >= 75 and ctx.unrealized_gain_pct >= 20 and ctx.liquidity_score >= 40:
        if score >= 45 and market_strength >= 40:
            action = EXIT_GRADE_THEN_SELL
            primary = "grade_then_capture_premium"
    if score >= 42 and (effective_liquidity_score < 35 or effective_timing_signal == "SELL_SOON"):
        action = EXIT_WATCH
        primary = "profit_present_but_timing_not_peak"
    if ctx.quantity >= 3 or ctx.portfolio_share_pct >= 12:
        if score >= 40 and market_strength >= 35:
            action = EXIT_TRIM
            primary = "trim_concentrated_position"
    if score >= 58 and ctx.liquidity_score >= 45 and market_strength >= 50:
        action = EXIT_SELL_NOW
        primary = "exit_window_favorable"
    elif score < 25:
        action = EXIT_HOLD
        primary = "insufficient_exit_signal"

    confidence = min(0.98, 0.3 + ctx.fmv_confidence * 0.24 + min(score, 90) / 210 + market_strength / 600)
    return action, round(min(100.0, max(0.0, score)), 2), round(confidence, 3), primary, secondary[:6], factors


def score_listing(ctx: SellIntelCopyContext) -> tuple[float | None, float | None, float | None, float | None, float, float, float, str, dict]:
    fmv = ctx.market_weighted_median_sale or ctx.estimated_fmv
    if fmv <= 0:
        return None, None, None, None, 0.0, 0.0, 60.0, LISTING_EITHER, {"fmv_missing": True}
    has_market = _has_market_inputs(ctx)
    if not has_market:
        low = round(fmv * 0.88, 2)
        high = round(fmv * 1.05, 2)
        bin_price = round(fmv * 0.97, 2)
        auction = round(fmv * 0.82, 2)
        profit = round(fmv - ctx.cost_basis, 2)
        roi = round((profit / ctx.cost_basis * 100.0) if ctx.cost_basis > 0 else 0.0, 2)
        days = max(7.0, min(120.0, (100.0 - ctx.liquidity_score) * 0.6 + max(0, 10 - ctx.sales_count) * 3))
        rec = LISTING_BIN if ctx.liquidity_score >= 55 else LISTING_AUCTION if ctx.liquidity_score < 30 else LISTING_EITHER
        return bin_price, auction, low, high, profit, roi, round(days, 1), rec, {
            "fmv": fmv,
            "sales_count": ctx.sales_count,
            "market_confidence": ctx.fmv_confidence,
        }
    confidence = max(0.0, min(1.0, ctx.fmv_confidence))
    liquidity = max(0.0, min(100.0, ctx.market_liquidity_score or ctx.liquidity_score))
    spread = max(0.06, min(0.24, 0.18 - confidence * 0.06 - liquidity / 1200.0))
    low = round(fmv * (1 - spread), 2)
    high = round(fmv * (1 + spread * 0.55), 2)
    bin_discount = 0.03 + max(0.0, 0.08 - confidence * 0.05)
    bin_price = round(fmv * (1 - bin_discount), 2)
    auction_discount = 0.18 + max(0.0, 0.08 - liquidity / 1000.0)
    auction = round(fmv * (1 - auction_discount), 2)
    profit = round(fmv - ctx.cost_basis, 2)
    roi = round((profit / ctx.cost_basis * 100.0) if ctx.cost_basis > 0 else 0.0, 2)
    timing = ctx.market_timing_signal
    if ctx.market_liquidity_band == "VERY_HIGH" or liquidity >= 75:
        days = 2.0
    elif ctx.market_liquidity_band == LIQ_HIGH or liquidity >= 55:
        days = 5.0
    elif ctx.market_liquidity_band == LIQ_MEDIUM or liquidity >= 30:
        days = 14.0
    else:
        days = 35.0
    days += max(0.0, 4.0 - min(4.0, ctx.market_sales_velocity))
    if timing == "SELL_NOW":
        days = max(1.0, days - 2.0)
    elif timing == "ACCUMULATE":
        days = max(21.0, days + 7.0)
    if ctx.market_liquidity_band == LIQ_HIGH or liquidity >= 55:
        rec = LISTING_BIN
    elif ctx.market_liquidity_band == LIQ_LOW or liquidity < 30:
        rec = LISTING_AUCTION
    else:
        rec = LISTING_EITHER
    return bin_price, auction, low, high, profit, roi, round(days, 1), rec, {
        "fmv": fmv,
        "sales_count": ctx.sales_count,
        "market_confidence": ctx.fmv_confidence,
        "market_weighted_median_sale": ctx.market_weighted_median_sale,
        "market_recent_median_30d": ctx.market_recent_median_30d,
        "market_recent_median_90d": ctx.market_recent_median_90d,
        "market_sales_velocity": ctx.market_sales_velocity,
        "market_liquidity_band": ctx.market_liquidity_band,
        "market_timing_signal": ctx.market_timing_signal,
        "market_timing_reason": ctx.market_timing_reason,
    }


def score_liquidity(ctx: SellIntelCopyContext) -> tuple[str, float, float, int, float, float, float, dict]:
    if not _has_market_inputs(ctx):
        velocity = min(100.0, ctx.sales_count * 12.0 + ctx.liquidity_score * 0.35)
        demand = min(100.0, 40.0 + (16.0 if ctx.price_trend == "RISING" else 0.0))
        obs = ctx.sales_count
        conf = ctx.fmv_confidence
        score = min(100.0, ctx.liquidity_score * 0.55 + velocity * 0.25 + demand * 0.1 + conf * 20.0)
        if score >= 55:
            band = LIQ_HIGH
        elif score >= 30:
            band = LIQ_MEDIUM
        else:
            band = LIQ_LOW
        days = max(5.0, min(150.0, (100.0 - score) * 0.8 + 10))
        return band, round(score, 2), round(velocity, 2), obs, round(demand, 2), round(conf, 3), round(days, 1), {
            "price_trend": ctx.price_trend,
            "market_timing_signal": ctx.market_timing_signal,
            "market_timing_reason": ctx.market_timing_reason,
            "market_sales_velocity": ctx.market_sales_velocity,
            "market_liquidity_band": ctx.market_liquidity_band,
        }
    velocity = min(100.0, (ctx.market_sales_velocity * 18.0) + ctx.sales_count * 8.0 + ctx.liquidity_score * 0.25)
    demand = min(100.0, 40.0 + (16.0 if ctx.price_trend == "RISING" else 0.0) + (6.0 if ctx.market_timing_signal == "SELL_NOW" else 0.0))
    obs = ctx.sales_count
    conf = ctx.fmv_confidence
    score = min(100.0, ctx.liquidity_score * 0.4 + velocity * 0.3 + demand * 0.1 + conf * 18.0)
    if ctx.market_timing_signal == "SELL_NOW":
        score = min(100.0, score + 10.0)
    elif ctx.market_timing_signal == "SELL_SOON":
        score = min(100.0, score + 5.0)
    elif ctx.market_timing_signal == "ACCUMULATE":
        score = max(0.0, score - 6.0)
    if score >= 75:
        band = "VERY_HIGH"
    elif score >= 55:
        band = LIQ_HIGH
    elif score >= 30:
        band = LIQ_MEDIUM
    else:
        band = LIQ_LOW
    if band == "VERY_HIGH":
        days = 2.0
    elif band == LIQ_HIGH:
        days = 7.0
    elif band == LIQ_MEDIUM:
        days = 14.0
    else:
        days = 35.0
    days += max(0.0, 3.0 - min(3.0, ctx.market_sales_velocity))
    return band, round(score, 2), round(velocity, 2), obs, round(demand, 2), round(conf, 3), round(days, 1), {
        "price_trend": ctx.price_trend,
        "market_timing_signal": ctx.market_timing_signal,
        "market_timing_reason": ctx.market_timing_reason,
        "market_sales_velocity": ctx.market_sales_velocity,
        "market_liquidity_band": ctx.market_liquidity_band,
    }
