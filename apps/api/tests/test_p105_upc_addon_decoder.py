from PIL import Image

from app.services.p105_upc_addon_decoder import (
    UpAddonDecodeResult,
    _AddonDecoderRow,
    _accept_addon_supplement,
    _majority_vote_supplement,
    build_addon_preprocessing_variants,
    ean5_check_digit,
    ean5_check_valid,
    expanded_addon_bars_box,
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


def test_expanded_addon_bars_box_pad() -> None:
    from app.services.p105_comic_barcode_regions import BarcodeRegionGeometry

    geo = BarcodeRegionGeometry(
        full_expanded=(0, 0, 100, 100),
        main_bars=(60, 10, 90, 50),
        left_supplement=(10, 10, 60, 50),
        right_cover_digit=(90, 10, 100, 50),
    )
    box = expanded_addon_bars_box(geo, 100, 100)
    _text, bars = split_supplement_subregions(geo.left_supplement)
    assert (box[2] - box[0]) >= (bars[2] - bars[0])
    assert (box[3] - box[1]) >= (bars[3] - bars[1])


def test_build_addon_preprocessing_variant_count() -> None:
    img = Image.new("RGB", (40, 30), (200, 200, 200))
    variants = build_addon_preprocessing_variants(img)
    names = {n for n, _ in variants}
    assert "original" in names
    assert "upscale8x_threshold" in names
    assert len(variants) == 11


def test_majority_vote_picks_weighted_winner() -> None:
    rows = [
        _AddonDecoderRow("pyzbar", "upscale8x", FULL := f"{MAIN}03921", "03921", 0.91, 1.0),
        _AddonDecoderRow("opencv", "clahe", FULL, "03921", 0.88, 2.0),
        _AddonDecoderRow("pyzbar", "grayscale", f"{MAIN}02111", "02111", 0.91, 1.0),
    ]
    winner, conf, method, meta = _majority_vote_supplement(rows, main_upc=MAIN)
    assert winner == "03921"
    assert conf > 0
    assert meta["vote_counts"]["03921"] == 2


def test_majority_vote_requires_acceptable_supplement() -> None:
    rows = [
        _AddonDecoderRow("pyzbar", "original", "03921", "03921", 0.91, 1.0),
    ]
    winner, _, _, _ = _majority_vote_supplement(rows, main_upc=MAIN)
    assert winner == ""
