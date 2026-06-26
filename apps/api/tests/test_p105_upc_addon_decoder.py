from app.services.p105_upc_addon_decoder import (
    UpAddonDecodeResult,
    _accept_addon_supplement,
    ean5_check_digit,
    ean5_check_valid,
    split_supplement_subregions,
)

MAIN = "761941341927"


def test_ean5_check_digit_example() -> None:
    assert ean5_check_digit("0011") == 8
    assert ean5_check_valid("00118") is True


def test_accept_supplement_from_full_barcode_merge() -> None:
    full = f"{MAIN}03921"
    assert _accept_addon_supplement("03921", [full], MAIN) is True


def test_reject_invalid_standalone_five_digit() -> None:
    assert _accept_addon_supplement("03921", ["03921"], MAIN) is False


def test_split_supplement_subregions_width() -> None:
    text, bars = split_supplement_subregions((100, 10, 200, 50))
    assert text[0] == 100
    assert bars[2] == 200
    assert text[2] >= text[0]
    assert bars[0] < bars[2]


def test_up_addon_result_to_dict() -> None:
    row = UpAddonDecodeResult(supplement="00118", method="pyzbar:test", confidence=0.9, check_valid=True)
    d = row.to_dict()
    assert d["supplement"] == "00118"
    assert d["method"] == "pyzbar:test"
