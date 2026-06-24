from app.services.catalog_ingestion_service import comic_barcode_lookup_variants


def test_comic_barcode_lookup_variants_includes_12_and_17_digit_keys() -> None:
    raw = "76194134192203921"
    keys = comic_barcode_lookup_variants(raw)
    assert "76194134192203921" in keys
    assert any(len(k) == 12 for k in keys)
