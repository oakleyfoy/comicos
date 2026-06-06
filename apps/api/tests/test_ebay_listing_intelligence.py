from __future__ import annotations

from app.models.sell_intelligence_platform import LISTING_AUCTION, LISTING_BIN, LIQ_HIGH, LIQ_LOW
from app.services.p71_sell_context import SellIntelCopyContext
from app.services.p71_sell_scoring import score_listing, score_liquidity


def _ctx(**overrides) -> SellIntelCopyContext:
    base = dict(
        copy_id=1,
        title="Batman",
        publisher="DC",
        issue_number="1",
        quantity=1,
        cost_basis=20.0,
        estimated_fmv=80.0,
        fmv_confidence=0.75,
        liquidity_score=65.0,
        sales_count=4,
        price_trend="STABLE",
        unrealized_gain=60.0,
        unrealized_gain_pct=300.0,
        grade_status="graded",
        portfolio_share_pct=4.0,
        recommendation_hit_rate=55.0,
        market_weighted_median_sale=82.0,
        market_recent_median_30d=84.0,
        market_recent_median_90d=79.0,
        market_sales_velocity=2.5,
        market_liquidity_band=LIQ_HIGH,
        market_liquidity_score=72.0,
        market_confidence_band="HIGH",
        market_provider_breakdown_json={"EBAY_SOLD": 5},
        market_primary_provider="EBAY_SOLD",
        market_timing_signal="SELL_SOON",
        market_timing_reason="Market depth is healthy, but there is still room to capture a stronger sale.",
    )
    base.update(overrides)
    return SellIntelCopyContext(**base)


def test_listing_scoring_reflects_ebay_weighted_median_and_timing() -> None:
    high = score_listing(_ctx(market_liquidity_band="VERY_HIGH", market_liquidity_score=88.0, market_timing_signal="SELL_NOW"))
    low = score_listing(
        _ctx(
            estimated_fmv=62.0,
            market_weighted_median_sale=62.0,
            market_liquidity_band=LIQ_LOW,
            market_liquidity_score=18.0,
            market_sales_velocity=0.3,
            market_timing_signal="HOLD",
            market_timing_reason="Market is thin or weakening; waiting is safer than forcing a sale.",
            fmv_confidence=0.42,
        )
    )

    assert high[0] is not None
    assert high[7] == LISTING_BIN
    assert high[6] < low[6]
    assert high[-1]["market_timing_signal"] == "SELL_NOW"
    assert high[-1]["market_weighted_median_sale"] == 82.0
    assert low[7] == LISTING_AUCTION


def test_liquidity_scoring_promotes_velocity_and_strength() -> None:
    hot_band, hot_score, hot_velocity, _obs, _demand, _conf, hot_days, hot_factors = score_liquidity(
        _ctx(market_liquidity_band="VERY_HIGH", market_liquidity_score=90.0, market_sales_velocity=5.0, market_timing_signal="SELL_NOW")
    )
    cold_band, cold_score, cold_velocity, _obs2, _demand2, _conf2, cold_days, cold_factors = score_liquidity(
        _ctx(market_liquidity_band=LIQ_LOW, market_liquidity_score=15.0, market_sales_velocity=0.1, market_timing_signal="HOLD")
    )

    assert hot_band == "VERY_HIGH"
    assert hot_score > cold_score
    assert hot_velocity > cold_velocity
    assert hot_days < cold_days
    assert hot_factors["market_timing_signal"] == "SELL_NOW"
    assert cold_factors["market_timing_signal"] == "HOLD"
