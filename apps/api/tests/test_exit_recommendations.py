from app.models.sell_intelligence_platform import EXIT_SELL_NOW
from app.services.p71_sell_context import SellIntelCopyContext
from app.services.p71_sell_scoring import score_exit


def test_exit_sell_now_on_gain_and_liquidity() -> None:
    ctx = SellIntelCopyContext(
        copy_id=1,
        title="Spider-Man",
        publisher="Marvel",
        issue_number="300",
        quantity=1,
        cost_basis=100,
        estimated_fmv=200,
        fmv_confidence=0.7,
        liquidity_score=60,
        sales_count=5,
        price_trend="RISING",
        unrealized_gain=100,
        unrealized_gain_pct=100,
        grade_status="raw",
        portfolio_share_pct=5,
        recommendation_hit_rate=70,
    )
    action, score, _conf, _primary, _sec, _f = score_exit(ctx)
    assert score >= 50
    assert action in (EXIT_SELL_NOW, "TRIM_POSITION", "GRADE_THEN_SELL")
