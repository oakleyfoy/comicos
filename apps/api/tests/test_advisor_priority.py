"""P90-03 advisor priority tests."""

from app.services.advisor_priority_service import rank_mixed_top_actions


def test_rank_mixed_top_actions_limit() -> None:
    actions = [
        {"category": "BUY", "comic": "A", "alert_type": "BUY_OPPORTUNITY", "confidence": "HIGH", "severity": "HIGH", "profit_signal": 20.0},
        {"category": "SELL", "comic": "B", "alert_type": "SELL_OPPORTUNITY", "confidence": "MEDIUM", "severity": "MEDIUM", "profit_signal": 10.0},
        {"category": "GRADE", "comic": "C", "alert_type": "GRADE_OPPORTUNITY", "confidence": "LOW", "severity": "LOW", "profit_signal": 2.0},
    ]
    top = rank_mixed_top_actions(actions, limit=2)
    assert len(top) == 2
    assert top[0]["rank"] == 1
