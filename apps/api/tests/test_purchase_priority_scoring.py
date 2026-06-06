from app.services.purchase_priority_score import (
    P74_ACTION_BUY,
    P74_ACTION_MUST_BUY,
    P74_ACTION_PASS,
    P74_ACTION_WATCH,
    compute_purchase_priority_score,
)


def test_high_scores_must_buy() -> None:
    score, action = compute_purchase_priority_score(
        recommendation_score=90,
        demand_score=85,
        is_number_one=True,
        is_key_signal=True,
        variant_count=3,
        has_ratio_variant=True,
        watchlist_match=True,
        market_signal_strength=50,
        owned_quantity=0,
        ordered_quantity=0,
        foc_days=3,
    )
    assert score >= 85
    assert action == P74_ACTION_MUST_BUY


def test_low_scores_pass() -> None:
    score, action = compute_purchase_priority_score(
        recommendation_score=30,
        demand_score=25,
        is_number_one=False,
        is_key_signal=False,
        variant_count=1,
        has_ratio_variant=False,
        watchlist_match=False,
        market_signal_strength=0,
        owned_quantity=5,
        ordered_quantity=2,
        foc_days=None,
    )
    assert action in {P74_ACTION_PASS, P74_ACTION_WATCH}
    assert score < 70
