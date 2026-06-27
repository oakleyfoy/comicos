from app.core.config import get_settings
from app.services.catalog_ingestion_service import direct_market_requires_supplement_key
from app.services.gcd_barcode_search_service import gcd_upc12_has_full_barcode_variants
from app.services.photo_import_catalog_match_service import _upc_match


def test_upc_match_skips_direct_market_12_digit(session) -> None:
    assert _upc_match(session, "761941341927") is None
    assert direct_market_requires_supplement_key("761941341927")


def test_field_test_barcodes_require_supplement_when_12_only() -> None:
    """Regression: prefixes from real scans, not a one-off allowlist."""
    twelve_only = [
        "761568002140",
        "856470008172",
        "709853041559",
        "859990002019",
    ]
    for base in twelve_only:
        assert direct_market_requires_supplement_key(base) is True
        full = f"{base}00911"
        assert direct_market_requires_supplement_key(full) is False


def test_gcd_discovers_supplement_requirement_for_unknown_prefix() -> None:
    gcd_path = get_settings().gcd_sqlite_path
    if not gcd_path.is_file():
        return
    assert gcd_upc12_has_full_barcode_variants(gcd_path, "761568002140")
    assert direct_market_requires_supplement_key("761568002140", gcd_path=gcd_path)
