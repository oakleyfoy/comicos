from app.models.market_pricing_engine import PROVIDER_INTERNAL_SALE, P68MarketPriceObservation
from app.services.fmv_calculation_engine import compute_fmv_bundle


def test_outlier_trimmed_median() -> None:
    obs = [
        P68MarketPriceObservation(owner_user_id=1, provider=PROVIDER_INTERNAL_SALE, title="T", publisher="DC", issue_number="1", raw_or_graded="raw", sold_price=10, total_price=10, confidence=0.9),
        P68MarketPriceObservation(owner_user_id=1, provider=PROVIDER_INTERNAL_SALE, title="T", publisher="DC", issue_number="1", raw_or_graded="raw", sold_price=11, total_price=11, confidence=0.9),
        P68MarketPriceObservation(owner_user_id=1, provider=PROVIDER_INTERNAL_SALE, title="T", publisher="DC", issue_number="1", raw_or_graded="raw", sold_price=200, total_price=200, confidence=0.9),
    ]
    bundle = compute_fmv_bundle(obs)
    assert bundle["median_sale"] is not None
    assert float(bundle["median_sale"]) < 50
