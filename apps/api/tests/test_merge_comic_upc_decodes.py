from app.services.catalog_ingestion_service import merge_comic_upc_decodes
from app.services.photo_import_barcode_vision import normalize_comic_scan_barcode


def test_merge_upc12_and_supplement5() -> None:
    assert merge_comic_upc_decodes(["761941204017", "05811"]) == "76194120401705811"
    assert merge_comic_upc_decodes(["761941341922", "03921"]) == "76194134192203921"


def test_direct_market_requires_supplement_for_12_only() -> None:
    from app.services.catalog_ingestion_service import direct_market_requires_supplement_key

    assert direct_market_requires_supplement_key("761941341927") is True
    assert direct_market_requires_supplement_key("76194134192203921") is False


def test_merge_prefers_full_17_when_decoder_returns_both() -> None:
    assert merge_comic_upc_decodes(["76194120401705811", "761941204017"]) == "76194120401705811"


def test_normalize_comic_scan_barcode_accepts_17_digits() -> None:
    assert normalize_comic_scan_barcode("76194120401705811") == "76194120401705811"
