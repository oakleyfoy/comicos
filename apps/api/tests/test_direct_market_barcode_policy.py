from app.services.catalog_ingestion_service import direct_market_requires_supplement_key
from app.services.photo_import_catalog_match_service import _upc_match


def test_upc_match_skips_direct_market_12_digit(session) -> None:
    assert _upc_match(session, "761941341927") is None
    assert direct_market_requires_supplement_key("761941341927")
