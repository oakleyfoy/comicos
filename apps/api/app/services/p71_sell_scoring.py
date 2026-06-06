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


def score_exit(ctx: SellIntelCopyContext) -> tuple[str, float, float, str, list[str], dict]:
    score = 0.0
    secondary: list[str] = []
    factors: dict = {
        "unrealized_gain_pct": round(ctx.unrealized_gain_pct, 2),
        "fmv_confidence": round(ctx.fmv_confidence, 3),
        "liquidity_score": round(ctx.liquidity_score, 2),
        "quantity": ctx.quantity,
        "price_trend": ctx.price_trend,
        "portfolio_share_pct": round(ctx.portfolio_share_pct, 2),
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

    action = EXIT_HOLD
    primary = "hold_for_better_signal"
    if ctx.grade_status == "raw" and ctx.estimated_fmv >= 75 and ctx.unrealized_gain_pct >= 20 and ctx.liquidity_score >= 40:
        if score >= 45:
            action = EXIT_GRADE_THEN_SELL
            primary = "grade_then_capture_premium"
    if ctx.quantity >= 3 or ctx.portfolio_share_pct >= 12:
        if score >= 40:
            action = EXIT_TRIM
            primary = "trim_concentrated_position"
    if score >= 58 and ctx.liquidity_score >= 45:
        action = EXIT_SELL_NOW
        primary = "exit_window_favorable"
    elif score >= 42 and ctx.liquidity_score < 35:
        action = EXIT_WATCH
        primary = "profit_present_but_illiquid"
    elif score < 25:
        action = EXIT_HOLD
        primary = "insufficient_exit_signal"

    confidence = min(0.95, 0.35 + ctx.fmv_confidence * 0.25 + min(score, 80) / 200)
    return action, round(min(100.0, max(0.0, score)), 2), round(confidence, 3), primary, secondary[:6], factors


def score_listing(ctx: SellIntelCopyContext) -> tuple[float | None, float | None, float | None, float | None, float, float, float, str, dict]:
    fmv = ctx.estimated_fmv
    if fmv <= 0:
        return None, None, None, None, 0.0, 0.0, 60.0, LISTING_EITHER, {"fmv_missing": True}
    low = round(fmv * 0.88, 2)
    high = round(fmv * 1.05, 2)
    bin_price = round(fmv * 0.97, 2)
    auction = round(fmv * 0.82, 2)
    profit = round(fmv - ctx.cost_basis, 2)
    roi = round((profit / ctx.cost_basis * 100.0) if ctx.cost_basis > 0 else 0.0, 2)
    days = max(7.0, min(120.0, (100.0 - ctx.liquidity_score) * 0.6 + max(0, 10 - ctx.sales_count) * 3))
    if ctx.liquidity_score >= 55:
        rec = LISTING_BIN
    elif ctx.liquidity_score < 30:
        rec = LISTING_AUCTION
    else:
        rec = LISTING_EITHER
    return bin_price, auction, low, high, profit, roi, round(days, 1), rec, {
        "fmv": fmv,
        "sales_count": ctx.sales_count,
        "market_confidence": ctx.fmv_confidence,
    }


def score_liquidity(ctx: SellIntelCopyContext) -> tuple[str, float, float, int, float, float, float, dict]:
    velocity = min(100.0, ctx.sales_count * 12.0 + ctx.liquidity_score * 0.35)
    demand = min(100.0, 40.0 + (12.0 if ctx.price_trend == "RISING" else 0.0))
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
    }
