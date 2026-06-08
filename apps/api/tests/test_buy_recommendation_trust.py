"""P90-08 buy recommendation trust classification."""

from __future__ import annotations

from app.services.buy_recommendation_trust_service import (
    classify_buy_recommendation,
    resolve_price_source,
    sanitize_buy_evidence,
)


def test_simulated_opportunity_is_recommended_buy() -> None:
    rec = classify_buy_recommendation(
        has_verified_listing=False,
        best_verified_listing=None,
        recommendation="GOOD_BUY",
    )
    assert rec == "RECOMMENDED_BUY"
    src, label = resolve_price_source(recommendation_type=rec, has_verified_listing=False)
    assert src == "P82_OPPORTUNITY"
    assert label == "Recommendation estimate"


def test_verified_listing_is_verified_deal() -> None:
    verified = {
        "listing_url": "https://www.ebay.com/itm/1234567890",
        "price": 4.49,
        "total_cost": 4.49,
        "marketplace": "EBAY",
    }
    rec = classify_buy_recommendation(
        has_verified_listing=True,
        best_verified_listing=verified,
        recommendation="GOOD_BUY",
    )
    assert rec == "VERIFIED_DEAL"
    src, _ = resolve_price_source(recommendation_type=rec, has_verified_listing=True)
    assert src == "VERIFIED_LISTING"


def test_sanitize_removes_false_verified_phrases() -> None:
    merged, primary, supporting = sanitize_buy_evidence(
        reason="55% below FMV · verified listing · 26% below FMV",
        primary_reason="55% below FMV",
        supporting_signals=["verified listing"],
        has_verified_listing=False,
    )
    assert "verified listing" not in merged.lower() or "no verified" in merged.lower()
    assert primary
    assert all("verified listing" not in s.lower() for s in supporting)


def test_simulated_url_not_verified_deal() -> None:
    verified = {
        "listing_url": "https://www.ebay.com/itm/SIM-EBAY-P82-15",
        "price": 4.49,
        "item_id": "SIM-EBAY-P82-15",
    }
    rec = classify_buy_recommendation(
        has_verified_listing=True,
        best_verified_listing=verified,
        recommendation="STRONG_BUY",
    )
    assert rec == "RECOMMENDED_BUY"
