from app.services.p71_sell_context import SellIntelCopyContext
from app.services.p71_sell_scoring import score_liquidity


def test_liquidity_bands() -> None:
    ctx = SellIntelCopyContext(
        copy_id=1,
        title="T",
        publisher="M",
        issue_number="1",
        quantity=1,
        cost_basis=1,
        estimated_fmv=10,
        fmv_confidence=0.6,
        liquidity_score=80,
        sales_count=10,
        price_trend="RISING",
        unrealized_gain=9,
        unrealized_gain_pct=900,
        grade_status="raw",
        portfolio_share_pct=1,
        recommendation_hit_rate=0,
    )
    band, score, _v, obs, _d, _c, days, _ = score_liquidity(ctx)
    assert band == "HIGH"
    assert score >= 55
    assert obs == 10
    assert days < 60
