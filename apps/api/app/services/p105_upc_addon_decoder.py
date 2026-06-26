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
    _decode_pyzbar_pil,
    _opencv_available,
    _pyzbar_available,
)

logger = logging.getLogger(__name__)

_EAN5_WEIGHTS = (3, 9, 3, 9)
ADDON_BARS_EXPAND_PX = 20

_DECODER_BASE_CONF = {"zxing": 0.94, "pyzbar": 0.91, "opencv": 0.88}


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

    def as_dict(self) -> dict[str, Any]:
        return {
            "decoder": self.decoder,
            "variant": self.variant,
            "decoded_text": self.decoded_text,
            "supplement": self.supplement,
            "confidence": round(self.confidence, 4),
            "elapsed_ms": round(self.elapsed_ms, 3),
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


def expanded_addon_bars_box(geometry: BarcodeRegionGeometry, image_width: int, image_height: int) -> Box:
    _text, bars_box = split_supplement_subregions(geometry.left_supplement)
    left, top, right, bottom = bars_box
    pad = ADDON_BARS_EXPAND_PX
    return _clamp_box((left - pad, top - pad, right + pad, bottom + pad), image_width, image_height)


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


def _upscale_lanczos(pil: Image.Image, factor: float) -> Image.Image:
    w, h = pil.size
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


def _decode_with_backend(backend: str, pil: Image.Image) -> list[str]:
    if backend == "zxing":
        return _decode_zxing_pil(pil)
    if backend == "pyzbar" and _pyzbar_available():
        return _decode_pyzbar_pil(pil)
    if backend == "opencv" and _opencv_available():
        return _decode_opencv_bgr(_bgr_from_pil(pil))
    return []


def _confidence_for_hit(backend: str, supplement: str) -> float:
    conf = _DECODER_BASE_CONF.get(backend, 0.7)
    if ean5_check_valid(supplement):
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
        if not _accept_addon_supplement(row.supplement, [row.decoded_text], main_upc):
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
            decoded_list = _decode_with_backend(backend, variant_img)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            if not decoded_list:
                rows.append(
                    _AddonDecoderRow(
                        decoder=backend,
                        variant=variant_name,
                        decoded_text="",
                        supplement="",
                        confidence=0.0,
                        elapsed_ms=elapsed_ms,
                    )
                )
                continue
            for decoded_text in decoded_list:
                all_raw.append(decoded_text)
                supplement = _supplement_from_merged([decoded_text], main_upc)
                conf = _confidence_for_hit(backend, supplement) if supplement else 0.0
                rows.append(
                    _AddonDecoderRow(
                        decoder=backend,
                        variant=variant_name,
                        decoded_text=decoded_text,
                        supplement=supplement,
                        confidence=conf,
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
) -> tuple[str, float, str, list[str]]:
    combined = _combined_addon_upc_crop(pil, geometry)
    best_supp, best_conf, best_method = "", 0.0, ""
    all_raw: list[str] = []
    for backend in ("zxing", "pyzbar", "opencv"):
        if backend == "zxing" and not _zxing_available():
            continue
        if backend == "pyzbar" and not _pyzbar_available():
            continue
        if backend == "opencv" and not _opencv_available():
            continue
        raw = _decode_with_backend(backend, combined)
        all_raw.extend(raw)
        supp = _supplement_from_merged(raw, main_upc)
        if supp:
            conf = _confidence_for_hit(backend, supp)
            if conf >= best_conf:
                best_supp, best_conf, best_method = supp, conf, f"{backend}:combined_strip"
    return best_supp, best_conf, best_method, all_raw


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

    expanded = crop_expanded_addon_bars(pil, geometry)
    _rows, _previews, microscope = run_addon_barcode_microscope(expanded, main_upc=main_upc)
    result.microscope_debug = microscope
    result.raw_candidates = list(microscope.get("all_raw") or [])
    result.attempts = [
        {
            "region": "addon_bars_microscope",
            "backend": r["decoder"],
            "variant": r["variant"],
            "supplement": r["supplement"],
            "confidence": r["confidence"],
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

    if not best_supp:
        fb_supp, fb_conf, fb_method, fb_raw = _fallback_combined_strip_decode(pil, geometry, main_upc=main_upc)
        result.raw_candidates = list(dict.fromkeys(result.raw_candidates + fb_raw))
        if fb_supp:
            best_supp, best_conf, best_method = fb_supp, fb_conf, fb_method
            result.attempts.append(
                {"region": "combined_strip", "backend": fb_method, "supplement": fb_supp, "confidence": fb_conf}
            )

    if best_supp and not _accept_addon_supplement(best_supp, result.raw_candidates, main_upc):
        logger.warning("p105.addon_decode rejected invalid check digit supplement=%s", best_supp)
        best_supp = ""
        best_conf = 0.0
        best_method = ""

    if best_supp:
        if not ean5_check_valid(best_supp):
            best_conf = min(best_conf, 0.82)
        result.supplement = best_supp
        result.confidence = best_conf
        result.method = best_method or "addon_bars_microscope"
        result.check_valid = ean5_check_valid(best_supp)
        result.reconstructed_full = f"{main_upc}{best_supp}"
        logger.info(
            "p105.addon_decode hit supplement=%s method=%s conf=%.2f check=%s microscope_rows=%d",
            best_supp,
            result.method,
            best_conf,
            result.check_valid,
            len(microscope.get("decoder_results") or []),
        )
    return result


def addon_debug_crops(
    pil: Image.Image,
    geometry: BarcodeRegionGeometry,
) -> dict[str, Image.Image]:
    w, h = pil.size
    text_box, _bars = split_supplement_subregions(geometry.left_supplement)
    expanded = expanded_addon_bars_box(geometry, w, h)
    return {
        "addon_bars_only": pil.crop(expanded),
        "supplement_text_only": pil.crop(_clamp_box(text_box, w, h)),
    }
