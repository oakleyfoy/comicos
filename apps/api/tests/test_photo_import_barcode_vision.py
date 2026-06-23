from app.services.photo_import_barcode_vision import (
    barcode_needs_focus_pass,
    sanitize_vision_barcode,
)


def test_sanitize_rejects_hallucinated_barcode() -> None:
    assert sanitize_vision_barcode("649857003921") == ""


def test_sanitize_accepts_dc_upc() -> None:
    assert sanitize_vision_barcode("761941343730") == "761941343730"


def test_needs_focus_when_empty_or_invalid() -> None:
    assert barcode_needs_focus_pass("")
    assert barcode_needs_focus_pass("649857003921")
    assert not barcode_needs_focus_pass("761941343730")
