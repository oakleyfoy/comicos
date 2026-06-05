from app.models.market_pricing_engine import P68MarketPriceObservation, PROVIDER_INTERNAL_SALE
from app.services.market_price_identity_matching import IdentityTarget, score_observation_match
from app.services.printing_intelligence import PRINTING_KIND_REPRINT, PRINTING_KIND_FIRST


def test_reprint_blocked() -> None:
    obs = P68MarketPriceObservation(
        owner_user_id=1,
        provider=PROVIDER_INTERNAL_SALE,
        title="Tigress Island",
        publisher="Image Comics",
        issue_number="1",
        printing_number=4,
        printing_kind=PRINTING_KIND_REPRINT,
        raw_or_graded="raw",
        sold_price=10,
        total_price=10,
    )
    target = IdentityTarget(
        title="Tigress Island",
        publisher="Image Comics",
        issue_number="1",
        variant_label=None,
        printing_number=1,
        printing_kind=PRINTING_KIND_FIRST,
        raw_or_graded="raw",
        grade=None,
    )
    score, _, rejected, _ = score_observation_match(obs, target)
    assert score == 0.0
    assert rejected == "printing_mismatch"
