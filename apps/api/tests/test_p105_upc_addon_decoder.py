from PIL import Image

from app.services.p105_upc_addon_decoder import (
    UpAddonDecodeResult,
    _AddonDecoderRow,
    _accept_addon_supplement,
    _majority_vote_supplement,
    build_addon_preprocessing_variants,
    custom_ean5_candidates,
    decode_ean5_modules,
    decode_ean5_run_lengths,
    ean5_addon_checksum,
    ean5_check_digit,
    ean5_check_valid,
    ean5_encode_modules,
    expanded_addon_bars_box,
    split_supplement_subregions,
)

MAIN = "761941341927"


def _render_ean5(digits: str, *, module_px: int = 3, height: int = 60, quiet: int = 12) -> Image.Image:
    """Render a standalone EAN-5 add-on as a black/white bar image."""
    bits = ean5_encode_modules(digits)
    width = quiet * 2 + len(bits) * module_px
    img = Image.new("RGB", (width, height), "white")
    px = img.load()
    x = quiet
    for bit in bits:
        if bit == "1":
            for dx in range(module_px):
                for y in range(height):
                    px[x + dx, y] = (0, 0, 0)
        x += module_px
    return img


def test_ean5_addon_checksum_03921() -> None:
    assert ean5_addon_checksum("03921") == 5


def test_ean5_encode_decode_round_trip() -> None:
    for digits in ("03921", "00000", "12345", "99999", "51234", "76543"):
        assert decode_ean5_modules(ean5_encode_modules(digits)) == digits


def test_ean5_encode_length_is_47_modules() -> None:
    assert len(ean5_encode_modules("03921")) == 47


def test_decode_ean5_run_lengths_from_clean_runs() -> None:
    bits = ean5_encode_modules("03921")
    runs: list[int] = []
    flags: list[bool] = []
    i = 0
    while i < len(bits):
        j = i
        while j < len(bits) and bits[j] == bits[i]:
            j += 1
        runs.append((j - i) * 4)  # 4px per module
        flags.append(bits[i] == "1")
        i = j
    assert decode_ean5_run_lengths(runs, flags) == "03921"


def test_custom_scanner_decodes_rendered_addon() -> None:
    img = _render_ean5("03921")
    assert ("03921", "EAN5") in custom_ean5_candidates(img)


def test_custom_scanner_decodes_rotated_addon() -> None:
    img = _render_ean5("03921").rotate(90, expand=True)
    assert ("03921", "EAN5") in custom_ean5_candidates(img)


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


def test_majority_vote_trusts_library_ean5_addon() -> None:
    """A library-verified EAN-5 add-on wins even though its self-check formula fails."""
    from app.services.p105_upc_addon_decoder import ean5_check_valid

    assert ean5_check_valid("03921") is False  # the printed digits are not self-checking
    rows = [
        _AddonDecoderRow("pyzbar", "upscale8x", "03921", "03921", 0.97, 1.0, trusted=True),
    ]
    winner, conf, _method, _meta = _majority_vote_supplement(rows, main_upc=MAIN)
    assert winner == "03921"
    assert conf > 0.9


def test_supplements_from_symbols_trusts_ean5_type() -> None:
    from app.services.p105_upc_addon_decoder import supplements_from_symbols

    supps = supplements_from_symbols([("03921", "EAN5")], MAIN)
    assert ("03921", True) in supps


def test_supplements_from_symbols_extracts_from_combined() -> None:
    from app.services.p105_upc_addon_decoder import supplements_from_symbols

    supps = supplements_from_symbols([(MAIN, "UPCA"), ("03921", "EAN5")], MAIN)
    assert ("03921", True) in supps


def test_supplements_from_symbols_ignores_untyped_standalone_five() -> None:
    from app.services.p105_upc_addon_decoder import supplements_from_symbols

    # An untyped bare 5-digit decode (e.g. OpenCV mis-read) is not trusted.
    supps = supplements_from_symbols([("03921", "")], MAIN)
    assert supps == []


def test_addon_strip_box_spans_full_barcode() -> None:
    from app.services.p105_comic_barcode_regions import BarcodeRegionGeometry
    from app.services.p105_upc_addon_decoder import addon_strip_box

    geo = BarcodeRegionGeometry(
        full_expanded=(0, 0, 400, 200),
        main_bars=(150, 20, 300, 120),
        left_supplement=(90, 20, 150, 120),
        right_cover_digit=(300, 20, 340, 120),
    )
    box = addon_strip_box(geo, 400, 200)
    assert box[0] <= 90
    assert box[2] >= 340
