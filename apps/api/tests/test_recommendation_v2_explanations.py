from __future__ import annotations

from app.services.recommendation_v2_components import IssueComponentBundle, ScoreComponentResult
from app.services.recommendation_v2_explanations import build_recommendation_decision


def test_explanations_for_watch_and_must_buy() -> None:
    watch_bundle = IssueComponentBundle(
        components=[
            ScoreComponentResult("NEW_NUMBER_ONE_SCORE", 45.0, 0.06, "New #1"),
            ScoreComponentResult("RISK_SCORE", 60.0, 0.1, "Weak franchise"),
        ],
        total_score=42.0,
        recommendation_tier="WATCH",
        recommendation_type="NEW_OPPORTUNITY",
        confidence_score=0.5,
    )
    watch = build_recommendation_decision(
        bundle=watch_bundle,
        series_name="Random Comic",
        issue_number="1",
        publisher="INDIE",
    )
    assert "WATCH" in watch.decision_summary
    assert watch.suggested_quantity == 0

    must_bundle = IssueComponentBundle(
        components=[
            ScoreComponentResult("INVESTMENT_NUMBER_ONE_SCORE", 88.0, 0.12, "TMNT franchise"),
            ScoreComponentResult("MARKET_DEMAND_SCORE", 90.0, 0.11, "Strong demand"),
        ],
        total_score=88.0,
        recommendation_tier="MUST_BUY",
        recommendation_type="INVESTMENT_NUMBER_ONE",
        confidence_score=0.9,
    )
    must = build_recommendation_decision(
        bundle=must_bundle,
        series_name="TMNT",
        issue_number="1",
        publisher="IDW",
    )
    assert "MUST BUY" in must.decision_summary
    assert must.suggested_quantity >= 1
