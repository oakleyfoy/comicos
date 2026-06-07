"""P90-03 portfolio impact service tests."""

from app.services.portfolio_impact_service import compute_portfolio_impact


def test_portfolio_impact_empty() -> None:
    impact = compute_portfolio_impact(buy_actions=[], sell_actions=[], grade_actions=[])
    assert impact["portfolio_impact_total"] == 0.0
    assert impact["portfolio_score"] >= 0
