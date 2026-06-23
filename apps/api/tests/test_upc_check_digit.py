from app.services.catalog_ingestion_service import upc_check_digit_valid


def test_dc_superman_barcode_valid() -> None:
    assert upc_check_digit_valid("761941343730")


def test_gpt_hallucinated_barcode_invalid() -> None:
    assert not upc_check_digit_valid("649857003921")
