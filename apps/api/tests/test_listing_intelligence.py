from app.services.p71_sell_context import SellIntelCopyContext
from app.services.p71_sell_scoring import score_listing


def test_listing_bin_when_liquid() -> None:
    ctx = SellIntelCopyContext(
        copy_id=1,
        title="Book",
        publisher="DC",
        issue_number="1",
        quantity=1,
        cost_basis=10,
        estimated_fmv=50,
        fmv_confidence=0.8,
        liquidity_score=70,
        sales_count=8,
        price_trend="STABLE",
        unrealized_gain=40,
        unrealized_gain_pct=400,
        grade_status="raw",
        portfolio_share_pct=2,
        recommendation_hit_rate=50,
    )
    bin_p, _auc, lo, hi, profit, roi, days, rec, _ = score_listing(ctx)
    assert bin_p == 48.5
    assert profit == 40
    assert rec == "BUY_IT_NOW"
    assert lo is not None and hi is not None
    assert days >= 7
