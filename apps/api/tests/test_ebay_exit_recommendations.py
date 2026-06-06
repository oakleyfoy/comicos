from __future__ import annotations

from app.models.sell_intelligence_platform import EXIT_HOLD, EXIT_SELL_NOW
from app.services.p71_sell_context import SellIntelCopyContext
from app.services.p71_sell_scoring import score_exit


def _ctx(**overrides) -> SellIntelCopyContext:
    base = dict(
        copy_id=1,
        title="Spider-Man",
        publisher="Marvel",
        issue_number="1",
        quantity=1,
        cost_basis=25.0,
        estimated_fmv=110.0,
        fmv_confidence=0.82,
        liquidity_score=80.0,
        sales_count=8,
        price_trend="RISING",
        unrealized_gain=85.0,
        unrealized_gain_pct=340.0,
        grade_status="graded",
        portfolio_share_pct=5.0,
        recommendation_hit_rate=70.0,
        market_weighted_median_sale=118.0,
        market_recent_median_30d=121.0,
        market_recent_median_90d=113.0,
        market_sales_velocity=4.5,
        market_liquidity_band="VERY_HIGH",
        market_liquidity_score=88.0,
        market_confidence_band="HIGH",
        market_provider_breakdown_json={"EBAY_SOLD": 8, "INTERNAL_SALE": 1},
        market_primary_provider="EBAY_SOLD",
        market_timing_signal="SELL_NOW",
        market_timing_reason="High liquidity and strong recent sales support an immediate exit.",
    )
    base.update(overrides)
    return SellIntelCopyContext(**base)


def test_exit_scoring_prefers_sell_now_for_strong_ebay_market() -> None:
    action, score, confidence, primary, secondary, factors = score_exit(_ctx())
    assert action == EXIT_SELL_NOW
    assert score >= 60
    assert confidence >= 0.7
    assert primary == "exit_window_favorable"
    assert "timing_window_open" in secondary
    assert factors["market_timing_signal"] == "SELL_NOW"
    assert factors["market_strength"] >= 70


def test_exit_scoring_preserves_hold_when_market_signal_is_soft() -> None:
    ctx = _ctx(
        estimated_fmv=35.0,
        fmv_confidence=0.38,
        liquidity_score=18.0,
        market_liquidity_score=18.0,
        market_sales_velocity=0.2,
        market_timing_signal="ACCUMULATE",
        market_timing_reason="Market is thin or weakening; waiting is safer than forcing a sale.",
        market_weighted_median_sale=31.0,
        unrealized_gain=2.0,
        unrealized_gain_pct=8.0,
        price_trend="FALLING",
        recommendation_hit_rate=10.0,
    )
    action, score, _confidence, primary, secondary, factors = score_exit(ctx)
    assert action == EXIT_HOLD
    assert score < 40
    assert primary in {"hold_for_better_signal", "insufficient_exit_signal"}
    assert "market_accumulation_signal" in secondary
    assert factors["market_timing_signal"] == "ACCUMULATE"
