from app.services.purchase_priority_score import P74_ACTION_BUY, P74_ACTION_PASS
from app.services.quantity_recommendation_service import recommend_quantity


def test_strong_buy_defaults_to_two() -> None:
    qty, reason = recommend_quantity(
        purchase_action=P74_ACTION_BUY,
        priority_score=78,
        owned_quantity=0,
        ordered_quantity=0,
        is_number_one=False,
        demand_score=72,
        foc_days=5,
    )
    assert qty >= 2
    assert reason


def test_pass_recommends_zero() -> None:
    qty, _ = recommend_quantity(
        purchase_action=P74_ACTION_PASS,
        priority_score=40,
        owned_quantity=0,
        ordered_quantity=0,
        is_number_one=False,
        demand_score=40,
        foc_days=None,
    )
    assert qty == 0
