"""Decode 5-digit UPC/EAN add-on from bar strips (primary supplement path for P105)."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageEnhance, ImageOps

from app.services.catalog_ingestion_service import merge_comic_upc_decodes, upc_check_digit_valid
from app.services.p105_comic_barcode_regions import BarcodeRegionGeometry, Box, _clamp_box, pil_to_jpeg_bytes
from app.services.photo_import_upc_barcode_decoder import (
    _bgr_from_pil,
    _decode_opencv_bgr,
    _opencv_available,
    _pyzbar_available,
)

logger = logging.getLogger(__name__)

_EAN5_WEIGHTS = (3, 9, 3, 9)
ADDON_BARS_EXPAND_PX = 20

_DECODER_BASE_CONF = {"custom_ean5": 0.93, "zxing": 0.94, "pyzbar": 0.91, "opencv": 0.88}


@dataclass
class UpAddonDecodeResult:
    supplement: str = ""
    confidence: float = 0.0
    method: str = ""
    check_valid: bool = False
    base_upc: str = ""
    reconstructed_full: str = ""
    raw_candidates: list[str] = field(default_factory=list)
    attempts: list[dict[str, Any]] = field(default_factory=list)
    microscope_debug: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "supplement": self.supplement,
            "confidence": round(self.confidence, 3),
            "method": self.method,
            "check_valid": self.check_valid,
            "base_upc": self.base_upc,
            "reconstructed_full": self.reconstructed_full,
            "raw_candidates": list(self.raw_candidates),
            "attempts": list(self.attempts),
            "microscope": {
                "vote": self.microscope_debug.get("vote"),
                "decoder_result_count": len(self.microscope_debug.get("decoder_results") or []),
            },
        }


@dataclass
class _AddonDecoderRow:
    decoder: str
    variant: str
    decoded_text: str
    supplement: str
    confidence: float
    elapsed_ms: float
    trusted: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "decoder": self.decoder,
            "variant": self.variant,
            "decoded_text": self.decoded_text,
            "supplement": self.supplement,
            "confidence": round(self.confidence, 4),
            "elapsed_ms": round(self.elapsed_ms, 3),
            "trusted": self.trusted,
        }


def ean5_check_digit(data4: str) -> int:
    if len(data4) != 4 or not data4.isdigit():
        return -1
    digits = [int(ch) for ch in data4]
    total = sum(d * w for d, w in zip(digits, _EAN5_WEIGHTS, strict=True))
    return (10 - (total % 10)) % 10


def ean5_check_valid(digits5: str) -> bool:
    if len(digits5) != 5 or not digits5.isdigit():
        return False
    expected = ean5_check_digit(digits5[:4])
    return expected >= 0 and expected == int(digits5[4])


# --- Standalone EAN-5 add-on symbology (for rotated/isolated comic add-ons) ----
# Comic add-ons are frequently printed rotated 90 deg and ABOVE the main UPC, so
# they are never adjacent to it. No mainstream library decodes a standalone,
# rotated EAN-5 add-on, so we decode it ourselves. An EAN-5's checksum is encoded
# in the bar parity (all 5 printed digits are data), which makes a successful
# decode self-validating and trustworthy.
_EAN5_A = {
    "0": "0001101", "1": "0011001", "2": "0010011", "3": "0111101", "4": "0100011",
    "5": "0110001", "6": "0101111", "7": "0111011", "8": "0110111", "9": "0001011",
}
_EAN5_B = {
    "0": "0100111", "1": "0110011", "2": "0011011", "3": "0100001", "4": "0011101",
    "5": "0111001", "6": "0000101", "7": "0010001", "8": "0001001", "9": "0010111",
}
_EAN5_PARITY = {
    0: "GGLLL", 1: "GLGLL", 2: "GLLGL", 3: "GLLLG", 4: "LGGLL",
    5: "LLGGL", 6: "LLLGG", 7: "LGLGL", 8: "LGLLG", 9: "LLGLG",
}
_EAN5_START = "1011"
_EAN5_SEP = "01"
_EAN5_A_REV = {v: k for k, v in _EAN5_A.items()}
_EAN5_B_REV = {v: k for k, v in _EAN5_B.items()}


def ean5_addon_checksum(digits5: str) -> int:
    """EAN-5 parity checksum (selects the bar parity pattern). All 5 digits are data."""
    n = [int(c) for c in digits5]
    return (3 * (n[0] + n[2] + n[4]) + 9 * (n[1] + n[3])) % 10


def ean5_encode_modules(digits5: str) -> str:
    """Encode 5 data digits to the 47-module bit string (1=bar, 0=space)."""
    parity = _EAN5_PARITY[ean5_addon_checksum(digits5)]
    out = _EAN5_START
    for i, ch in enumerate(digits5):
        if i:
            out += _EAN5_SEP
        out += (_EAN5_A if parity[i] == "L" else _EAN5_B)[ch]
    return out


def decode_ean5_modules(bits: str) -> str | None:
    """Decode a 47-module EAN-5 bit string; returns digits only if parity matches checksum."""
    if len(bits) != 47 or not bits.startswith(_EAN5_START):
        return None
    digits: list[str] = []
    parity: list[str] = []
    pos = 4
    for i in range(5):
        if i:
            if bits[pos:pos + 2] != _EAN5_SEP:
                return None
            pos += 2
        chunk = bits[pos:pos + 7]
        pos += 7
        if chunk in _EAN5_A_REV:
            digits.append(_EAN5_A_REV[chunk])
            parity.append("L")
        elif chunk in _EAN5_B_REV:
            digits.append(_EAN5_B_REV[chunk])
            parity.append("G")
        else:
            return None
    supp = "".join(digits)
    if _EAN5_PARITY[ean5_addon_checksum(supp)] != "".join(parity):
        return None
    return supp


def _runs_to_bits(runs: list[int], unit: float, first_is_bar: bool) -> str:
    bits: list[str] = []
    is_bar = first_is_bar
    for r in runs:
        n = max(1, round(r / unit))
        bits.append(("1" if is_bar else "0") * n)
        is_bar = not is_bar
    return "".join(bits)


def decode_ean5_run_lengths(runs: list[int], flags: list[bool]) -> str | None:
    """Decode from alternating bar/space run lengths; searches for the ~47-module symbol."""
    n = len(runs)
    for start in range(n):
        if not flags[start]:
            continue
        for count in range(11, min(n - start, 40) + 1):
            seg = runs[start:start + count]
            if len(seg) < 11:
                continue
            unit = sum(seg) / 47.0
            if unit < 0.6:
                continue
            bits = _runs_to_bits(seg, unit, True)
            if len(bits) == 47:
                supp = decode_ean5_modules(bits)
                if supp:
                    return supp
    return None


def _scanline_runs(vals: list[int], thr: float) -> tuple[list[int], list[bool]]:
    runs: list[int] = []
    flags: list[bool] = []
    i = 0
    n = len(vals)
    while i < n:
        dark = vals[i] < thr
        j = i
        while j < n and (vals[j] < thr) == dark:
            j += 1
        runs.append(j - i)
        flags.append(dark)
        i = j
    return runs, flags


# A real add-on spans many bar-height pixels, so it decodes on many scanlines; a
# random bar pattern that happens to pass the EAN-5 checksum hits only 1-2 lines.
_CUSTOM_EAN5_MIN_SUPPORT = 3


def custom_ean5_tally(pil: Image.Image) -> dict[str, int]:
    """Scan a crop at all 90-deg orientations; count scanline hits per decoded value."""
    work = pil.convert("RGB")
    longest = max(work.size)
    if longest > 900:
        scale = 900.0 / longest
        work = work.resize(
            (max(1, int(work.width * scale)), max(1, int(work.height * scale))),
            Image.Resampling.LANCZOS,
        )
    tally: dict[str, int] = {}
    for angle in (0, 90, 180, 270):
        rot = work.rotate(angle, expand=True) if angle else work
        gray = ImageOps.grayscale(rot)
        gw, gh = gray.size
        if gw < 47 or gh < 4:
            continue
        px = gray.load()
        step = max(1, gh // 200)
        for yi in range(0, gh, step):
            vals = [px[x, yi] for x in range(gw)]
            lo = min(vals)
            hi = max(vals)
            if hi - lo < 40:
                continue
            thr = (lo + hi) / 2.0
            runs, flags = _scanline_runs(vals, thr)
            supp = decode_ean5_run_lengths(runs, flags)
            if supp:
                tally[supp] = tally.get(supp, 0) + 1
    return tally


def custom_ean5_candidates(pil: Image.Image) -> list[tuple[str, str]]:
    """Decode standalone EAN-5 add-on(s) with multi-scanline consensus to reject flukes."""
    tally = custom_ean5_tally(pil)
    if not tally:
        return []
    best = max(tally.values())
    threshold = max(_CUSTOM_EAN5_MIN_SUPPORT, (best + 1) // 2)
    keep = [(supp, count) for supp, count in tally.items() if count >= threshold]
    keep.sort(key=lambda t: -t[1])
    return [(supp, "EAN5") for supp, _count in keep]


def split_supplement_subregions(left_supplement: Box) -> tuple[Box, Box]:
    """Split anchored left box: printed text (left) vs add-on bars (right, against UPC)."""
    left, top, right, bottom = left_supplement
    width = max(1, right - left)
    text_right = left + max(8, int(width * 0.42))
    bars_left = left + max(4, int(width * 0.32))
    text_box = (left, top, text_right, bottom)
    bars_box = (bars_left, top, right, bottom)
    return text_box, bars_box


def expanded_addon_bars_box(geometry: BarcodeRegionGeometry, image_width: int, image_height: int) -> Box:
    _text, bars_box = split_supplement_subregions(geometry.left_supplement)
    left, top, right, bottom = bars_box
    pad = ADDON_BARS_EXPAND_PX
    return _clamp_box((left - pad, top - pad, right + pad, bottom + pad), image_width, image_height)


def addon_strip_box(geometry: BarcodeRegionGeometry, image_width: int, image_height: int) -> Box:
    """ROI covering the add-on wherever it sits relative to the main UPC.

    On many comics the EAN-5 add-on is printed rotated 90 deg and ABOVE the main
    UPC-A (not adjacent to its right). So the search box extends generously
    UPWARD and to the LEFT of the main bars, while still spanning the full
    horizontal strip for the conventional right-side layout.
    """
    boxes = [geometry.left_supplement, geometry.main_bars, geometry.right_cover_digit]
    left = min(b[0] for b in boxes)
    top = min(b[1] for b in boxes)
    right = max(b[2] for b in boxes)
    bottom = max(b[3] for b in boxes)
    mb = geometry.main_bars
    bw = max(1, mb[2] - mb[0])
    bh = max(1, mb[3] - mb[1])
    pad = ADDON_BARS_EXPAND_PX
    up = int(bh * 1.8)
    side = int(bw * 0.5)
    return _clamp_box((left - side - pad, top - up - pad, right + pad, bottom + pad), image_width, image_height)


def crop_addon_strip(pil: Image.Image, geometry: BarcodeRegionGeometry) -> Image.Image:
    w, h = pil.size
    return pil.crop(addon_strip_box(geometry, w, h))


def crop_expanded_addon_bars(pil: Image.Image, geometry: BarcodeRegionGeometry) -> Image.Image:
    w, h = pil.size
    return pil.crop(expanded_addon_bars_box(geometry, w, h))


def _zxing_available() -> bool:
    try:
        import zxingcpp  # noqa: F401

        return True
    except ImportError:
        return False


def _decode_zxing_pil(pil: Image.Image) -> list[str]:
    return [text for text, _typ in _decode_zxing_symbols(pil)]


def _decode_zxing_symbols(pil: Image.Image) -> list[tuple[str, str]]:
    """ZXing-C++ decode returning (text, format) pairs, with EAN/UPC add-ons enabled."""
    try:
        import zxingcpp
    except ImportError:
        return []
    # Add-on (EAN-2/EAN-5 supplement) reading is OFF by default; turn it on.
    kwargs: dict[str, Any] = {}
    add_on = getattr(zxingcpp, "EanAddOnSymbol", None)
    if add_on is not None and hasattr(add_on, "Read"):
        kwargs["ean_add_on_symbol"] = add_on.Read
    try:
        results = zxingcpp.read_barcodes(pil, **kwargs)
    except TypeError:
        try:
            results = zxingcpp.read_barcodes(pil)
        except Exception:  # noqa: BLE001
            return []
    except Exception:  # noqa: BLE001
        return []
    out: list[tuple[str, str]] = []
    for item in results:
        text = (getattr(item, "text", None) or "").strip()
        if not text:
            continue
        fmt = str(getattr(item, "format", "") or "")
        out.append((text, fmt))
    return out


def _decode_pyzbar_symbols(pil: Image.Image) -> list[tuple[str, str]]:
    """pyzbar/ZBar decode returning (text, symbol_type) so EAN-5 add-ons are trusted."""
    if not _pyzbar_available():
        return []
    try:
        from pyzbar.pyzbar import decode as pyzbar_decode
    except Exception:  # noqa: BLE001
        return []
    out: list[tuple[str, str]] = []
    for sym in pyzbar_decode(pil):
        try:
            text = sym.data.decode("utf-8", errors="ignore").strip()
        except AttributeError:
            text = str(sym.data).strip()
        if not text:
            continue
        out.append((text, str(getattr(sym, "type", "") or "")))
    return out


def _decode_symbols(backend: str, pil: Image.Image) -> list[tuple[str, str]]:
    if backend == "zxing":
        return _decode_zxing_symbols(pil)
    if backend == "pyzbar":
        return _decode_pyzbar_symbols(pil)
    if backend == "opencv" and _opencv_available():
        return [(text, "") for text in _decode_opencv_bgr(_bgr_from_pil(pil))]
    return []


def _is_ean5_type(symbol_type: str) -> bool:
    return symbol_type.upper().replace("-", "").replace("_", "") in {"EAN5", "ADDON5", "UPCEANEXTENSION"}


def supplements_from_symbols(
    symbols: list[tuple[str, str]],
    main_upc: str,
) -> list[tuple[str, bool]]:
    """Extract 5-digit supplements from decoded symbols.

    Returns (supplement, trusted). ``trusted`` is True for library-verified
    EAN-5 add-on symbols and for 12+5 / 17-digit results anchored to the main
    UPC — these have passed the decoder's own parity/structure checks.
    """
    out: dict[str, bool] = {}

    def _add(supp: str, trusted: bool) -> None:
        if len(supp) == 5 and supp.isdigit():
            out[supp] = out.get(supp, False) or trusted

    texts = [t for t, _ in symbols]
    for text, typ in symbols:
        digits = _digits_only(text)
        if _is_ean5_type(typ) and len(digits) == 5:
            _add(digits, True)
        elif len(digits) >= 17 and digits[:12] == main_upc:
            _add(digits[12:17], True)

    merged = merge_comic_upc_decodes(texts)
    if merged and len(merged) >= 17 and merged[:12] == main_upc:
        _add(merged[12:17], True)

    return [(supp, trusted) for supp, trusted in out.items()]


def _digits_only(raw: str) -> str:
    return "".join(ch for ch in raw if ch.isdigit())


def _supplement_from_merged(candidates: list[str], main_upc: str) -> str:
    if len(main_upc) != 12:
        return ""
    merged = merge_comic_upc_decodes(candidates)
    if merged and len(merged) >= 17 and merged[:12] == main_upc:
        return merged[12:17]
    for raw in candidates:
        digits = _digits_only(raw)
        if len(digits) >= 17 and digits[:12] == main_upc:
            return digits[12:17]
        if len(digits) == 5:
            return digits
    return ""


def _accept_addon_supplement(supp: str, candidates: list[str], main_upc: str) -> bool:
    if ean5_check_valid(supp):
        return True
    merged = merge_comic_upc_decodes(candidates)
    if merged and len(merged) >= 17 and merged[:12] == main_upc and merged[12:17] == supp:
        return True
    for raw in candidates:
        digits = _digits_only(raw)
        if len(digits) >= 17 and digits[:12] == main_upc and digits[12:17] == supp:
            return True
    return False


def _gray_np(pil: Image.Image) -> Any:
    import numpy as np

    return np.asarray(ImageOps.grayscale(pil.convert("RGB")), dtype=np.uint8)


def _rgb_from_gray_array(gray: Any) -> Image.Image:
    from PIL import Image as PilImage

    return PilImage.fromarray(gray).convert("RGB")


def _clahe_rgb(pil: Image.Image) -> Image.Image:
    if not _opencv_available():
        return ImageOps.autocontrast(ImageOps.grayscale(pil)).convert("RGB")
    import cv2

    gray = _gray_np(pil)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return _rgb_from_gray_array(clahe.apply(gray))


def _otsu_threshold_rgb(pil: Image.Image) -> Image.Image:
    if not _opencv_available():
        return ImageOps.autocontrast(ImageOps.grayscale(pil)).convert("RGB")
    import cv2

    gray = _gray_np(pil)
    _th, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return _rgb_from_gray_array(binary)


def _adaptive_threshold_rgb(pil: Image.Image) -> Image.Image:
    if not _opencv_available():
        return _otsu_threshold_rgb(pil)
    import cv2

    gray = _gray_np(pil)
    block = max(3, min(31, (min(gray.shape) // 8) | 1))
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, 2
    )
    return _rgb_from_gray_array(binary)


# Cap the longest edge after upscaling so the wider full-strip ROI stays fast.
ADDON_UPSCALE_MAX_EDGE_PX = 2800


def _upscale_lanczos(pil: Image.Image, factor: float) -> Image.Image:
    w, h = pil.size
    longest = max(w, h) * factor
    if longest > ADDON_UPSCALE_MAX_EDGE_PX:
        factor = max(1.0, ADDON_UPSCALE_MAX_EDGE_PX / max(w, h))
    return pil.resize((max(1, int(w * factor)), max(1, int(h * factor))), Image.Resampling.LANCZOS)


def build_addon_preprocessing_variants(crop: Image.Image) -> list[tuple[str, Image.Image]]:
    """Preprocessing variants for add-on bar microscope (all RGB)."""
    base = crop.convert("RGB")
    gray = ImageOps.grayscale(base).convert("RGB")
    clahe = _clahe_rgb(base)
    adaptive = _adaptive_threshold_rgb(base)
    otsu = _otsu_threshold_rgb(base)
    inverted = ImageOps.invert(ImageOps.grayscale(base)).convert("RGB")
    sharpened = ImageEnhance.Sharpness(base).enhance(2.5)
    up4 = _upscale_lanczos(base, 4.0)
    up8 = _upscale_lanczos(base, 8.0)
    up8_clahe = _clahe_rgb(up8)
    up8_thresh = _otsu_threshold_rgb(up8)

    return [
        ("original", base),
        ("grayscale", gray),
        ("clahe", clahe),
        ("adaptive_threshold", adaptive),
        ("otsu_threshold", otsu),
        ("inverted", inverted),
        ("sharpened", sharpened),
        ("upscale4x", up4),
        ("upscale8x", up8),
        ("upscale8x_clahe", up8_clahe),
        ("upscale8x_threshold", up8_thresh),
    ]


def _preview_images_from_variants(variants: list[tuple[str, Image.Image]]) -> dict[str, Image.Image]:
    by_name = dict(variants)
    previews: dict[str, Image.Image] = {}
    if "original" in by_name:
        previews["addon_original"] = by_name["original"]
    if "grayscale" in by_name:
        previews["addon_gray"] = by_name["grayscale"]
    if "clahe" in by_name:
        previews["addon_clahe"] = by_name["clahe"]
    if "otsu_threshold" in by_name:
        previews["addon_threshold"] = by_name["otsu_threshold"]
    if "upscale4x" in by_name:
        previews["addon_upscale4x"] = by_name["upscale4x"]
    if "upscale8x" in by_name:
        previews["addon_upscale8x"] = by_name["upscale8x"]
    return previews


def _confidence_for_hit(backend: str, trusted: bool) -> float:
    conf = _DECODER_BASE_CONF.get(backend, 0.7)
    if trusted:
        conf = min(0.99, conf + 0.06)
    return conf


def _majority_vote_supplement(
    rows: list[_AddonDecoderRow],
    *,
    main_upc: str,
) -> tuple[str, float, str, dict[str, Any]]:
    tally: dict[str, float] = {}
    vote_counts: dict[str, int] = {}
    for row in rows:
        if len(row.supplement) != 5:
            continue
        # Trust library-verified add-on symbols; otherwise require structural acceptance.
        if not row.trusted and not _accept_addon_supplement(row.supplement, [row.decoded_text], main_upc):
            continue
        tally[row.supplement] = tally.get(row.supplement, 0.0) + row.confidence
        vote_counts[row.supplement] = vote_counts.get(row.supplement, 0) + 1
    if not tally:
        return "", 0.0, "", {"winner": "", "tally": {}, "vote_counts": {}}

    winner = max(tally, key=tally.get)
    votes = vote_counts[winner]
    avg_conf = tally[winner] / max(1, votes)
    boost = min(0.05, votes * 0.01)
    confidence = min(0.99, avg_conf + boost)
    best_row = max(
        (r for r in rows if r.supplement == winner),
        key=lambda r: r.confidence,
        default=None,
    )
    method = f"vote:{best_row.decoder}+{best_row.variant}" if best_row else "vote:majority"
    vote_meta = {
        "winner": winner,
        "tally": {k: round(v, 4) for k, v in tally.items()},
        "vote_counts": vote_counts,
        "winning_votes": votes,
    }
    return winner, confidence, method, vote_meta


def run_addon_barcode_microscope(
    expanded_addon_crop: Image.Image,
    *,
    main_upc: str,
) -> tuple[list[_AddonDecoderRow], dict[str, Image.Image], dict[str, Any]]:
    """Run all decoders on all preprocessing variants; return rows + debug previews."""
    variants = build_addon_preprocessing_variants(expanded_addon_crop)
    previews = _preview_images_from_variants(variants)
    rows: list[_AddonDecoderRow] = []
    all_raw: list[str] = []

    # Custom standalone EAN-5 scanner runs once on the full crop (handles rotation
    # internally) and is the path that actually reads rotated comic add-ons.
    t_custom = time.perf_counter()
    custom_hits = custom_ean5_candidates(expanded_addon_crop)
    custom_ms = (time.perf_counter() - t_custom) * 1000.0
    for supp, _typ in custom_hits:
        all_raw.append(supp)
        rows.append(
            _AddonDecoderRow(
                decoder="custom_ean5",
                variant="scanlines",
                decoded_text=supp,
                supplement=supp,
                confidence=_confidence_for_hit("custom_ean5", True),
                elapsed_ms=custom_ms,
                trusted=True,
            )
        )

    decoders: list[str] = []
    if _zxing_available():
        decoders.append("zxing")
    if _pyzbar_available():
        decoders.append("pyzbar")
    if _opencv_available():
        decoders.append("opencv")

    for variant_name, variant_img in variants:
        for backend in decoders:
            t0 = time.perf_counter()
            symbols = _decode_symbols(backend, variant_img)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            for text, _typ in symbols:
                all_raw.append(text)
            supplements = supplements_from_symbols(symbols, main_upc)
            if not supplements:
                rows.append(
                    _AddonDecoderRow(
                        decoder=backend,
                        variant=variant_name,
                        decoded_text=" ".join(t for t, _ in symbols),
                        supplement="",
                        confidence=0.0,
                        elapsed_ms=elapsed_ms,
                    )
                )
                continue
            for supplement, trusted in supplements:
                conf = _confidence_for_hit(backend, trusted)
                rows.append(
                    _AddonDecoderRow(
                        decoder=backend,
                        variant=variant_name,
                        decoded_text=" ".join(t for t, _ in symbols),
                        supplement=supplement,
                        confidence=conf,
                        trusted=trusted,
                        elapsed_ms=elapsed_ms,
                    )
                )

    winner, conf, method, vote = _majority_vote_supplement(rows, main_upc=main_upc)
    vote["method"] = method
    vote["confidence"] = round(conf, 4)
    vote["expanded_size"] = {"width": expanded_addon_crop.width, "height": expanded_addon_crop.height}
    debug = {
        "preview_images": previews,
        "decoder_results": [r.as_dict() for r in rows],
        "vote": vote,
        "all_raw": list(dict.fromkeys(all_raw)),
    }
    return rows, previews, debug


def write_addon_microscope_debug(base_dir: Path, addon: UpAddonDecodeResult) -> None:
    """Write addon_*.jpg previews and decoder_results.json."""
    ms = addon.microscope_debug
    if not ms:
        return
    base_dir.mkdir(parents=True, exist_ok=True)
    for name, pil in (ms.get("preview_images") or {}).items():
        filename = f"{name}.jpg" if not name.endswith(".jpg") else name
        (base_dir / filename).write_bytes(pil_to_jpeg_bytes(pil))
    payload = {
        "supplement": addon.supplement,
        "method": addon.method,
        "confidence": addon.confidence,
        "check_valid": addon.check_valid,
        "vote": ms.get("vote"),
        "decoder_results": ms.get("decoder_results") or [],
    }
    (base_dir / "decoder_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("p105.addon_microscope_debug_saved dir=%s rows=%d", base_dir, len(payload["decoder_results"]))


def _combined_addon_upc_crop(pil: Image.Image, geometry: BarcodeRegionGeometry) -> Image.Image:
    w, h = pil.size
    ls = geometry.left_supplement
    mb = geometry.main_bars
    box = _clamp_box((ls[0], min(ls[1], mb[1]), mb[2], max(ls[3], mb[3])), w, h)
    return pil.crop(box)


def _fallback_combined_strip_decode(
    pil: Image.Image,
    geometry: BarcodeRegionGeometry,
    *,
    main_upc: str,
) -> tuple[str, float, str, bool, list[str]]:
    combined = _combined_addon_upc_crop(pil, geometry)
    best_supp, best_conf, best_method, best_trusted = "", 0.0, "", False
    all_raw: list[str] = []
    for supp, _typ in custom_ean5_candidates(combined):
        conf = _confidence_for_hit("custom_ean5", True)
        all_raw.append(supp)
        if conf >= best_conf:
            best_supp, best_conf, best_method, best_trusted = supp, conf, "custom_ean5:combined_strip", True
    for backend in ("zxing", "pyzbar", "opencv"):
        if backend == "zxing" and not _zxing_available():
            continue
        if backend == "pyzbar" and not _pyzbar_available():
            continue
        if backend == "opencv" and not _opencv_available():
            continue
        symbols = _decode_symbols(backend, combined)
        all_raw.extend(t for t, _ in symbols)
        for supp, trusted in supplements_from_symbols(symbols, main_upc):
            conf = _confidence_for_hit(backend, trusted)
            if conf >= best_conf:
                best_supp, best_conf, best_method, best_trusted = supp, conf, f"{backend}:combined_strip", trusted
    return best_supp, best_conf, best_method, best_trusted, all_raw


def decode_upc_addon(
    pil: Image.Image,
    geometry: BarcodeRegionGeometry,
    *,
    main_upc: str,
) -> UpAddonDecodeResult:
    """Decode 5-digit supplement via expanded add-on microscope, then combined-strip fallback."""
    result = UpAddonDecodeResult(base_upc=main_upc)
    if len(main_upc) != 12 or not upc_check_digit_valid(main_upc):
        return result

    strip = crop_addon_strip(pil, geometry)
    rows, _previews, microscope = run_addon_barcode_microscope(strip, main_upc=main_upc)
    result.microscope_debug = microscope
    result.raw_candidates = list(microscope.get("all_raw") or [])
    result.attempts = [
        {
            "region": "addon_strip_microscope",
            "backend": r["decoder"],
            "variant": r["variant"],
            "supplement": r["supplement"],
            "confidence": r["confidence"],
            "trusted": r["trusted"],
            "decoded_text": r["decoded_text"],
            "elapsed_ms": r["elapsed_ms"],
        }
        for r in microscope.get("decoder_results") or []
        if r.get("supplement")
    ]

    vote = microscope.get("vote") or {}
    best_supp = str(vote.get("winner") or "")
    best_conf = float(vote.get("confidence") or 0.0)
    best_method = str(vote.get("method") or "")
    best_trusted = any(r.trusted and r.supplement == best_supp for r in rows) if best_supp else False

    if not best_supp:
        fb_supp, fb_conf, fb_method, fb_trusted, fb_raw = _fallback_combined_strip_decode(
            pil, geometry, main_upc=main_upc
        )
        result.raw_candidates = list(dict.fromkeys(result.raw_candidates + fb_raw))
        if fb_supp:
            best_supp, best_conf, best_method, best_trusted = fb_supp, fb_conf, fb_method, fb_trusted
            result.attempts.append(
                {"region": "combined_strip", "backend": fb_method, "supplement": fb_supp, "confidence": fb_conf}
            )

    # Reject only UNTRUSTED supplements that fail structural acceptance. A
    # library-verified EAN-5 (trusted) has already passed the decoder's parity
    # check and must not be dropped because of the (informational) self-check.
    if best_supp and not best_trusted and not _accept_addon_supplement(best_supp, result.raw_candidates, main_upc):
        logger.warning("p105.addon_decode rejected unverified supplement=%s", best_supp)
        best_supp = ""
        best_conf = 0.0
        best_method = ""
        best_trusted = False

    if best_supp:
        if not best_trusted:
            best_conf = min(best_conf, 0.82)
        result.supplement = best_supp
        result.confidence = best_conf
        result.method = best_method or "addon_strip_microscope"
        result.check_valid = best_trusted
        result.reconstructed_full = f"{main_upc}{best_supp}"
        logger.info(
            "p105.addon_decode hit supplement=%s method=%s conf=%.2f trusted=%s microscope_rows=%d",
            best_supp,
            result.method,
            best_conf,
            best_trusted,
            len(microscope.get("decoder_results") or []),
        )
    return result


def addon_debug_crops(
    pil: Image.Image,
    geometry: BarcodeRegionGeometry,
) -> dict[str, Image.Image]:
    w, h = pil.size
    text_box, _bars = split_supplement_subregions(geometry.left_supplement)
    return {
        "addon_bars_only": crop_addon_strip(pil, geometry),
        "supplement_text_only": pil.crop(_clamp_box(text_box, w, h)),
    }
