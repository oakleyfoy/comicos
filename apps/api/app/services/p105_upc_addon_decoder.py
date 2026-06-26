"""Decode 5-digit UPC/EAN add-on from bar strips (primary supplement path for P105)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from PIL import Image

from app.services.catalog_ingestion_service import merge_comic_upc_decodes, upc_check_digit_valid
from app.services.p105_comic_barcode_regions import BarcodeRegionGeometry, Box, _clamp_box
from app.services.photo_import_upc_barcode_decoder import (
    _bgr_from_pil,
    _decode_opencv_bgr,
    _decode_pyzbar_pil,
    _opencv_available,
    _preprocess_pil_variants,
    _pyzbar_available,
    collect_raw_upc_candidates_from_pil,
)

logger = logging.getLogger(__name__)

_EAN5_WEIGHTS = (3, 9, 3, 9)


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


def split_supplement_subregions(left_supplement: Box) -> tuple[Box, Box]:
    """Split anchored left box: printed text (left) vs add-on bars (right, against UPC)."""
    left, top, right, bottom = left_supplement
    width = max(1, right - left)
    text_right = left + max(8, int(width * 0.42))
    bars_left = left + max(4, int(width * 0.32))
    text_box = (left, top, text_right, bottom)
    bars_box = (bars_left, top, right, bottom)
    return text_box, bars_box


def _zxing_available() -> bool:
    try:
        import zxingcpp  # noqa: F401

        return True
    except ImportError:
        return False


def _decode_zxing_pil(pil: Image.Image) -> list[str]:
    try:
        import zxingcpp
    except ImportError:
        return []
    try:
        results = zxingcpp.read_barcodes(pil)
    except Exception:  # noqa: BLE001
        return []
    out: list[str] = []
    for item in results:
        text = (getattr(item, "text", None) or "").strip()
        if text:
            out.append(text)
    return out


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


def _combined_addon_upc_crop(pil: Image.Image, geometry: BarcodeRegionGeometry) -> Image.Image:
    w, h = pil.size
    ls = geometry.left_supplement
    mb = geometry.main_bars
    box = _clamp_box((ls[0], min(ls[1], mb[1]), mb[2], max(ls[3], mb[3])), w, h)
    return pil.crop(box)


def _collect_from_pil(
    pil: Image.Image,
    *,
    label: str,
    backend: str,
    main_upc: str,
) -> tuple[str, float, list[str]]:
    candidates: list[str] = []
    if backend == "zxing":
        candidates.extend(_decode_zxing_pil(pil))
    elif backend == "pyzbar":
        if _pyzbar_available():
            candidates.extend(_decode_pyzbar_pil(pil))
    elif backend == "opencv":
        if _opencv_available():
            candidates.extend(_decode_opencv_bgr(_bgr_from_pil(pil)))
    elif backend == "merged":
        candidates.extend(collect_raw_upc_candidates_from_pil(pil))
    else:
        return "", 0.0, []

    supp = _supplement_from_merged(candidates, main_upc)
    if not supp:
        return "", 0.0, candidates

    conf = 0.72
    if backend == "zxing":
        conf = 0.94
    elif backend == "pyzbar":
        conf = 0.91
    elif backend == "opencv":
        conf = 0.88
    elif backend == "merged":
        conf = 0.86
    if ean5_check_valid(supp):
        conf = min(0.99, conf + 0.06)
    logger.debug("p105.addon_decode %s/%s supplement=%s candidates=%d", label, backend, supp, len(candidates))
    return supp, conf, candidates


def _decode_custom_ean5_bars(addon_bars: Image.Image) -> tuple[str, float]:
    """Last-resort: upscale + library pass on isolated add-on bar strip."""
    best = ""
    best_conf = 0.0
    w, h = addon_bars.size
    scales = [1.0, 2.0, 3.0] if max(w, h) < 220 else [1.0, 1.5]
    for scale in scales:
        if scale != 1.0:
            resized = addon_bars.resize(
                (max(1, int(w * scale)), max(1, int(h * scale))),
                Image.Resampling.LANCZOS,
            )
        else:
            resized = addon_bars
        for variant in _preprocess_pil_variants(resized):
            for backend, base_conf in (("pyzbar", 0.78), ("opencv", 0.74)):
                supp, conf, _ = _collect_from_pil(variant, label="custom_bars", backend=backend, main_upc="")
                if len(supp) == 5 and conf > best_conf:
                    best, best_conf = supp, base_conf
                    if ean5_check_valid(supp):
                        best_conf = min(0.92, base_conf + 0.08)
    return best, best_conf


def decode_upc_addon(
    pil: Image.Image,
    geometry: BarcodeRegionGeometry,
    *,
    main_upc: str,
) -> UpAddonDecodeResult:
    """Decode 5-digit supplement from add-on bars (ZXing → pyzbar → OpenCV → custom bars)."""
    result = UpAddonDecodeResult(base_upc=main_upc)
    if len(main_upc) != 12 or not upc_check_digit_valid(main_upc):
        return result

    w, h = pil.size
    _text_box, bars_box = split_supplement_subregions(geometry.left_supplement)
    addon_bars = pil.crop(_clamp_box(bars_box, w, h))
    combined = _combined_addon_upc_crop(pil, geometry)
    full_ls = pil.crop(geometry.left_supplement)

    stages: list[tuple[str, Image.Image, str]] = []
    if _zxing_available():
        stages.extend(
            [
                ("combined_strip", combined, "zxing"),
                ("addon_bars", addon_bars, "zxing"),
                ("left_supplement", full_ls, "zxing"),
            ]
        )
    if _pyzbar_available():
        stages.extend(
            [
                ("combined_strip", combined, "pyzbar"),
                ("addon_bars", addon_bars, "pyzbar"),
                ("left_supplement", full_ls, "pyzbar"),
            ]
        )
    if _opencv_available():
        stages.extend(
            [
                ("combined_strip", combined, "opencv"),
                ("addon_bars", addon_bars, "opencv"),
            ]
        )
    stages.extend(
        [
            ("combined_strip", combined, "merged"),
            ("addon_bars", addon_bars, "merged"),
        ]
    )

    all_candidates: list[str] = []
    best_supp = ""
    best_conf = 0.0
    best_method = ""

    for label, crop, backend in stages:
        supp, conf, raw = _collect_from_pil(crop, label=label, backend=backend, main_upc=main_upc)
        all_candidates.extend(raw)
        result.attempts.append({"region": label, "backend": backend, "supplement": supp, "confidence": conf})
        if supp and conf >= best_conf:
            best_supp, best_conf, best_method = supp, conf, f"{backend}:{label}"

    if not best_supp:
        custom, custom_conf = _decode_custom_ean5_bars(addon_bars)
        if custom:
            best_supp, best_conf, best_method = custom, custom_conf, "custom_bars"
            result.attempts.append(
                {"region": "addon_bars", "backend": "custom_bars", "supplement": custom, "confidence": custom_conf}
            )

    result.raw_candidates = list(dict.fromkeys(all_candidates))
    if best_supp and not _accept_addon_supplement(best_supp, all_candidates, main_upc):
        logger.warning("p105.addon_decode rejected invalid check digit supplement=%s", best_supp)
        best_supp = ""
        best_conf = 0.0
        best_method = ""

    if best_supp:
        if not ean5_check_valid(best_supp):
            best_conf = min(best_conf, 0.82)
        result.supplement = best_supp
        result.confidence = best_conf
        result.method = best_method
        result.check_valid = ean5_check_valid(best_supp)
        result.reconstructed_full = f"{main_upc}{best_supp}"
        logger.info(
            "p105.addon_decode hit supplement=%s method=%s conf=%.2f check=%s",
            best_supp,
            best_method,
            best_conf,
            result.check_valid,
        )
    return result


def addon_debug_crops(
    pil: Image.Image,
    geometry: BarcodeRegionGeometry,
) -> dict[str, Image.Image]:
    w, h = pil.size
    text_box, bars_box = split_supplement_subregions(geometry.left_supplement)
    return {
        "addon_bars_only": pil.crop(_clamp_box(bars_box, w, h)),
        "supplement_text_only": pil.crop(_clamp_box(text_box, w, h)),
    }
